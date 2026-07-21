"""Deterministic, bounded, read-only search over local research records."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from html.parser import HTMLParser
from pathlib import Path
from typing import cast
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, model_validator

SEARCH_SCHEMA_VERSION = "1.0"
SEARCH_CONTRACT_VERSION = "registry-search-v1"
SEARCH_CAPABILITY_ID = "REP-05"
DEFAULT_SEARCH_LIMIT = 50
MAX_SEARCH_LIMIT = 200
MAX_QUERY_CHARACTERS = 256
MAX_QUERY_TOKENS = 16
MAX_CANDIDATE_DOCUMENTS = 20_000
MAX_DOCUMENT_CHARACTERS = 64_000
MAX_REPORT_FILES = 500
MAX_REPORT_BYTES = 2_000_000
MAX_SNIPPET_CHARACTERS = 320
MAX_RESULT_TITLE_CHARACTERS = 4_000
MAX_RESULT_REFERENCE_CHARACTERS = 4_000
ABSOLUTE_PATH_REDACTION = "[redacted absolute path]"

_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
_WINDOWS_PATH = re.compile(r"(?i)(?<![\w])(?:[a-z]:[\\/][^\s\"'<>]+)")
_FILE_URI = re.compile(r"(?i)file://[^\s\"'<>]+")
_HOME_PATH = re.compile(r"(?<![\w])~[/\\][^\s\"'<>]+")
_POSIX_PATH = re.compile(r"(?<![/\w])/(?!/)[^\s\"'<>]+")
_INVALID_TEXT = re.compile("[^\x09\x0a\x0d\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]")
_TEXT_REPORT_SUFFIXES = frozenset({".md", ".html", ".json", ".svg", ".tex"})
_REPORT_SUFFIXES = _TEXT_REPORT_SUFFIXES | {".pdf"}
_FIELD_WEIGHTS = {"reference": 12, "title": 10, "metadata": 6, "text": 3}


class RegistrySearchError(ValueError):
    """Raised when a safe bounded registry search cannot be completed."""


class SearchCategory(StrEnum):
    """Closed REP-05 result categories in deterministic tie-break order."""

    FINDING = "finding"
    ANNOTATION = "annotation"
    REPORT = "report"
    RUN = "run"
    EXPERIMENT = "experiment"
    EVIDENCE_REFERENCE = "evidence_reference"


class RegistrySearchHit(BaseModel):
    """One ranked, path-safe REP-05 result."""

    model_config = ConfigDict(extra="forbid")

    rank: int = Field(ge=1)
    category: SearchCategory
    title: str = Field(min_length=1, max_length=MAX_RESULT_TITLE_CHARACTERS)
    snippet: str = Field(min_length=1, max_length=MAX_SNIPPET_CHARACTERS)
    reference: str = Field(min_length=1, max_length=MAX_RESULT_REFERENCE_CHARACTERS)
    score: int = Field(ge=1)
    matched_terms: list[str] = Field(min_length=1, max_length=MAX_QUERY_TOKENS)
    redaction_count: int = Field(ge=0)


class RegistrySearchResult(BaseModel):
    """Complete bounded response for one read-only search."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SEARCH_SCHEMA_VERSION
    capability_id: str = SEARCH_CAPABILITY_ID
    contract_version: str = SEARCH_CONTRACT_VERSION
    query: str = Field(min_length=1, max_length=MAX_QUERY_CHARACTERS)
    normalised_terms: list[str] = Field(min_length=1, max_length=MAX_QUERY_TOKENS)
    selected_categories: list[SearchCategory] = Field(min_length=1)
    candidate_count: int = Field(ge=0)
    matching_count: int = Field(ge=0)
    returned_count: int = Field(ge=0)
    omitted_match_count: int = Field(ge=0)
    skipped_report_count: int = Field(ge=0)
    redaction_count: int = Field(ge=0)
    hits: list[RegistrySearchHit]
    limitations: list[str]

    @model_validator(mode="after")
    def validate_counts(self) -> RegistrySearchResult:
        """Require all published counts to reconcile."""

        if self.returned_count != len(self.hits):
            raise ValueError("returned_count must equal the number of hits")
        if self.matching_count != self.returned_count + self.omitted_match_count:
            raise ValueError("matching_count must reconcile returned and omitted matches")
        return self

    def canonical_json(self) -> str:
        """Return a byte-stable representation of the result."""

        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    def fingerprint(self) -> str:
        """Fingerprint this exact query, scope, inventory, and ranked result."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class RegistrySearchContract(BaseModel):
    """Published REP-05 query, ranking, bounding, and redaction contract."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SEARCH_SCHEMA_VERSION
    capability_id: str = SEARCH_CAPABILITY_ID
    contract_version: str = SEARCH_CONTRACT_VERSION
    categories: list[SearchCategory]
    default_result_limit: int
    maximum_result_limit: int
    maximum_query_characters: int
    maximum_query_tokens: int
    maximum_candidate_documents: int
    maximum_report_files: int
    maximum_report_bytes: int
    matching_policy: str
    ranking_policy: list[str]
    tie_break_policy: str
    redaction_policy: list[str]
    read_only_guarantees: list[str]
    indexed_sources: dict[str, str]
    exclusions: list[str]
    limitations: list[str]

    def canonical_json(self) -> str:
        """Return the canonical contract representation."""

        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def fingerprint(self) -> str:
        """Fingerprint the exact published search contract."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class _Document:
    category: SearchCategory
    title: str
    reference: str
    metadata: str
    text: str
    redaction_count: int


@dataclass(frozen=True)
class _ScoredDocument:
    document: _Document
    score: int
    snippet: str


@dataclass
class _CollectionState:
    documents: list[_Document]
    skipped_reports: int = 0
    redaction_count: int = 0


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._suppressed_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.casefold() in {"script", "style"}:
            self._suppressed_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style"} and self._suppressed_depth:
            self._suppressed_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._suppressed_depth:
            self.parts.append(data)

    def text(self) -> str:
        return " ".join(self.parts)


def registry_search_contract() -> RegistrySearchContract:
    """Return the immutable REP-05 v1 search contract."""

    return RegistrySearchContract(
        categories=list(SearchCategory),
        default_result_limit=DEFAULT_SEARCH_LIMIT,
        maximum_result_limit=MAX_SEARCH_LIMIT,
        maximum_query_characters=MAX_QUERY_CHARACTERS,
        maximum_query_tokens=MAX_QUERY_TOKENS,
        maximum_candidate_documents=MAX_CANDIDATE_DOCUMENTS,
        maximum_report_files=MAX_REPORT_FILES,
        maximum_report_bytes=MAX_REPORT_BYTES,
        matching_policy=(
            "Unicode NFKC case-folded AND matching over unique alphanumeric query terms; every "
            "term must occur in at least one sanitised field"
        ),
        ranking_policy=[
            "fields are weighted reference=12, title=10, metadata=6, text=3",
            "exact whole-field phrase, field-prefix phrase, and contained phrase receive 80x, "
            "40x, and 20x the field weight",
            "each term receives its best exact-token, token-prefix, or substring score of 8x, "
            "4x, or 2x the field weight",
            "scores are integer-only and category-neutral",
        ],
        tie_break_policy=(
            "descending score, then category declaration order, normalised title, and reference"
        ),
        redaction_policy=[
            "redact POSIX, Windows, home-relative, and file-URI absolute paths before matching",
            "show report basenames and typed local references, never workspace or registry paths",
            "preserve ordinary domain identifiers and bundle-relative evidence references",
            "publish redaction counts without exposing removed text",
        ],
        read_only_guarantees=[
            "open an existing SQLite registry in mode=ro immutable mode and set "
            "PRAGMA query_only=ON",
            "never initialise, migrate, index, update, or delete registry state",
            "read only direct, non-symlink files under a non-symlink workspace/reports directory",
        ],
        indexed_sources={
            SearchCategory.FINDING.value: (
                "stored bundle validation findings and structured report rule/finding records"
            ),
            SearchCategory.ANNOTATION.value: "append-only analyst annotation records",
            SearchCategory.REPORT.value: (
                "report basename, format, metadata, and bounded UTF-8 text where supported"
            ),
            SearchCategory.RUN.value: "registered run identifiers, status, and metadata",
            SearchCategory.EXPERIMENT.value: (
                "registered experiment identifiers, status, question, hypothesis, and design"
            ),
            SearchCategory.EVIDENCE_REFERENCE.value: (
                "run/experiment EvidencePack metadata and structured report claim references"
            ),
        },
        exclusions=[
            "raw bundle tables and source rows",
            "binary PDF body text; PDF metadata remains searchable",
            "report files outside workspace/reports, nested files, and symbolic links",
            "external services, web content, semantic embeddings, and LLM-generated terms",
        ],
        limitations=[
            "Ranking is deterministic lexical relevance, not scientific importance.",
            "A match does not validate, endorse, or establish causality for its content.",
            "The search is rebuilt from current local records on each request; no mutable index "
            "is created.",
        ],
    )


def search_registry(
    registry_path: str | Path,
    query: str,
    *,
    workspace_path: str | Path | None = None,
    categories: Sequence[SearchCategory | str] | None = None,
    limit: int = DEFAULT_SEARCH_LIMIT,
) -> RegistrySearchResult:
    """Search local registry records and report projections without changing either source."""

    display_query, terms, query_redactions = _parse_query(query)
    selected = _selected_categories(categories)
    if limit < 1 or limit > MAX_SEARCH_LIMIT:
        raise RegistrySearchError(f"limit must be between 1 and {MAX_SEARCH_LIMIT}")

    state = _CollectionState(documents=[], redaction_count=query_redactions)
    registry = Path(registry_path)
    if registry.exists():
        if not registry.is_file():
            raise RegistrySearchError("registry path must be a file")
        _collect_registry_documents(registry, state, selected)
    if workspace_path is not None and (
        SearchCategory.REPORT in selected
        or SearchCategory.FINDING in selected
        or SearchCategory.EVIDENCE_REFERENCE in selected
    ):
        _collect_report_documents(Path(workspace_path), state, selected)

    scored = [
        item
        for document in state.documents
        if (item := _score_document(document, terms)) is not None
    ]
    category_order = {category: index for index, category in enumerate(SearchCategory)}
    scored.sort(
        key=lambda item: (
            -item.score,
            category_order[item.document.category],
            _normalise(item.document.title),
            item.document.reference,
        )
    )
    selected_hits = scored[:limit]
    hits = [
        RegistrySearchHit(
            rank=index,
            category=item.document.category,
            title=item.document.title,
            snippet=item.snippet,
            reference=item.document.reference,
            score=item.score,
            matched_terms=terms,
            redaction_count=item.document.redaction_count,
        )
        for index, item in enumerate(selected_hits, start=1)
    ]
    return RegistrySearchResult(
        query=display_query,
        normalised_terms=terms,
        selected_categories=selected,
        candidate_count=len(state.documents),
        matching_count=len(scored),
        returned_count=len(hits),
        omitted_match_count=len(scored) - len(hits),
        skipped_report_count=state.skipped_reports,
        redaction_count=state.redaction_count,
        hits=hits,
        limitations=registry_search_contract().limitations,
    )


def _parse_query(query: str) -> tuple[str, list[str], int]:
    raw_display = " ".join(query.split())
    if not raw_display:
        raise RegistrySearchError("query must not be empty")
    if len(raw_display) > MAX_QUERY_CHARACTERS:
        raise RegistrySearchError(f"query must contain at most {MAX_QUERY_CHARACTERS} characters")
    display, redaction_count = _redact_text(raw_display)
    matchable = display.replace(ABSOLUTE_PATH_REDACTION, " ")
    terms = list(dict.fromkeys(_TOKEN.findall(unicodedata.normalize("NFKC", matchable).casefold())))
    if not terms:
        raise RegistrySearchError("query must contain at least one non-path alphanumeric term")
    if len(terms) > MAX_QUERY_TOKENS:
        raise RegistrySearchError(f"query must contain at most {MAX_QUERY_TOKENS} unique terms")
    return display, terms, redaction_count


def _selected_categories(
    categories: Sequence[SearchCategory | str] | None,
) -> list[SearchCategory]:
    if categories is None:
        return list(SearchCategory)
    try:
        requested = {SearchCategory(category) for category in categories}
    except ValueError as exc:
        choices = ", ".join(category.value for category in SearchCategory)
        raise RegistrySearchError(f"category must be one of: {choices}") from exc
    if not requested:
        raise RegistrySearchError("at least one search category must be selected")
    return [category for category in SearchCategory if category in requested]


def _collect_registry_documents(
    path: Path,
    state: _CollectionState,
    selected: list[SearchCategory],
) -> None:
    uri = f"file:{quote(str(path.resolve()), safe='/')}?mode=ro&immutable=1"
    try:
        with sqlite3.connect(uri, uri=True) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=ON")
            tables = {
                str(row["name"])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                )
            }
            if SearchCategory.EXPERIMENT in selected and "experiments" in tables:
                _collect_payload_table(
                    conn,
                    state,
                    table="experiments",
                    identifier="experiment_id",
                    category=SearchCategory.EXPERIMENT,
                )
            if SearchCategory.RUN in selected and "runs" in tables:
                _collect_payload_table(
                    conn,
                    state,
                    table="runs",
                    identifier="run_id",
                    category=SearchCategory.RUN,
                )
            if SearchCategory.ANNOTATION in selected and "analyst_annotations" in tables:
                _collect_annotations(conn, state)
            if SearchCategory.EVIDENCE_REFERENCE in selected:
                _collect_evidence_packs(conn, state, tables)
            if SearchCategory.FINDING in selected and "bundle_imports" in tables:
                _collect_validation_findings(conn, state)
    except sqlite3.Error as exc:
        raise RegistrySearchError(f"registry could not be read: {exc}") from exc


def _collect_payload_table(
    conn: sqlite3.Connection,
    state: _CollectionState,
    *,
    table: str,
    identifier: str,
    category: SearchCategory,
) -> None:
    rows = conn.execute(
        f"SELECT {identifier}, status, payload FROM {table} ORDER BY {identifier}"  # noqa: S608
    )
    for row in rows:
        raw_payload = str(row["payload"])
        payload = _parse_json(raw_payload)
        body = _flatten_json(payload) if payload is not None else raw_payload
        _append_document(
            state,
            category=category,
            title=str(row[identifier]),
            reference=f"{category.value}:{row[identifier]}",
            metadata=f"status {row['status']}",
            text=body,
        )


def _collect_annotations(conn: sqlite3.Connection, state: _CollectionState) -> None:
    rows = conn.execute(
        """
        SELECT sequence, annotation_id, target_kind, target_id, target_fingerprint,
               author_label, note, decision_label, created_at
        FROM analyst_annotations
        ORDER BY sequence, annotation_id
        """
    )
    for row in rows:
        target = f"{row['target_kind']}:{row['target_id']}"
        _append_document(
            state,
            category=SearchCategory.ANNOTATION,
            title=str(row["annotation_id"]),
            reference=f"annotation:{row['annotation_id']}",
            metadata=(
                f"sequence {row['sequence']} target {target} decision {row['decision_label']} "
                f"author {row['author_label']} created {row['created_at']} "
                f"fingerprint {row['target_fingerprint'] or 'unavailable'}"
            ),
            text=str(row["note"]),
        )


def _collect_evidence_packs(
    conn: sqlite3.Connection,
    state: _CollectionState,
    tables: set[str],
) -> None:
    configurations = [
        ("evidence_packs", "run_id", "run"),
        ("experiment_evidence_packs", "experiment_id", "experiment"),
    ]
    for table, owner_column, owner_label in configurations:
        if table not in tables:
            continue
        rows = conn.execute(
            f"""SELECT pack_id, {owner_column}, source_fingerprint, payload_json, stored_at
                FROM {table} ORDER BY pack_id"""  # noqa: S608
        )
        for row in rows:
            raw_payload = str(row["payload_json"])
            payload = _parse_json(raw_payload)
            body = _flatten_json(payload) if payload is not None else raw_payload
            _append_document(
                state,
                category=SearchCategory.EVIDENCE_REFERENCE,
                title=str(row["pack_id"]),
                reference=f"evidence_pack:{row['pack_id']}",
                metadata=(
                    f"{owner_label} {row[owner_column]} source fingerprint "
                    f"{row['source_fingerprint'] or 'unavailable'} stored {row['stored_at']}"
                ),
                text=body,
            )


def _collect_validation_findings(conn: sqlite3.Connection, state: _CollectionState) -> None:
    rows = conn.execute(
        """SELECT bundle_id, run_id, validation_report_json
           FROM bundle_imports ORDER BY bundle_id"""
    )
    for row in rows:
        payload = _parse_json(str(row["validation_report_json"]))
        if not isinstance(payload, dict):
            continue
        findings = payload.get("findings")
        if not isinstance(findings, list):
            continue
        for index, finding in enumerate(findings, start=1):
            if not isinstance(finding, dict):
                continue
            title = str(
                finding.get("finding_id")
                or finding.get("code")
                or f"validation-finding-{index:04d}"
            )
            _append_document(
                state,
                category=SearchCategory.FINDING,
                title=title,
                reference=f"bundle:{row['bundle_id']}#finding:{index:04d}",
                metadata=f"bundle {row['bundle_id']} run {row['run_id']}",
                text=_flatten_json(finding),
            )


def _collect_report_documents(
    workspace: Path,
    state: _CollectionState,
    selected: list[SearchCategory],
) -> None:
    report_dir = workspace / "reports"
    if report_dir.is_symlink():
        raise RegistrySearchError("workspace report directory must not be a symbolic link")
    if not report_dir.is_dir():
        return
    paths = [
        path
        for path in sorted(report_dir.iterdir(), key=lambda item: item.name)
        if path.suffix.casefold() in _REPORT_SUFFIXES
    ]
    if len(paths) > MAX_REPORT_FILES:
        raise RegistrySearchError(
            f"report inventory exceeds the {MAX_REPORT_FILES}-file search ceiling"
        )
    for path in paths:
        if path.is_symlink() or not path.is_file():
            state.skipped_reports += 1
            continue
        try:
            size = path.stat().st_size
        except OSError:
            state.skipped_reports += 1
            continue
        payload: object | None = None
        body = ""
        if path.suffix.casefold() in _TEXT_REPORT_SUFFIXES:
            if size > MAX_REPORT_BYTES:
                state.skipped_reports += 1
                continue
            try:
                raw_text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                state.skipped_reports += 1
                continue
            if path.suffix.casefold() == ".html":
                parser = _VisibleTextParser()
                parser.feed(raw_text)
                body = parser.text()
            elif path.suffix.casefold() == ".json":
                payload = _parse_json(raw_text)
                body = _flatten_json(payload) if payload is not None else raw_text
            else:
                body = raw_text
        else:
            body = "PDF binary body text is not indexed"

        report_title = path.name
        report_type = "unknown"
        if isinstance(payload, dict):
            report_title = str(payload.get("title") or path.name)
            report_type = str(payload.get("report_type") or "unknown")
        if SearchCategory.REPORT in selected:
            _append_document(
                state,
                category=SearchCategory.REPORT,
                title=report_title,
                reference=f"report:{path.name}",
                metadata=(
                    f"file {path.name} format {path.suffix.casefold().removeprefix('.')} "
                    f"report type {report_type} size bytes {size}"
                ),
                text=body,
            )
        if isinstance(payload, dict):
            if SearchCategory.FINDING in selected:
                _collect_structured_findings(payload, path.name, state)
            if SearchCategory.EVIDENCE_REFERENCE in selected:
                _collect_claim_references(payload, path.name, state)


def _collect_structured_findings(
    payload: dict[str, object],
    report_name: str,
    state: _CollectionState,
) -> None:
    seen: set[str] = set()
    for index, finding in enumerate(_find_dicts(payload, "findings"), start=1):
        title = str(
            finding.get("finding_id") or finding.get("code") or f"report-finding-{index:04d}"
        )
        identity = f"finding:{title}:{_flatten_json(finding)}"
        if identity in seen:
            continue
        seen.add(identity)
        _append_document(
            state,
            category=SearchCategory.FINDING,
            title=title,
            reference=f"report:{report_name}#finding:{index:04d}",
            metadata=f"report {report_name}",
            text=_flatten_json(finding),
        )
    snapshots = payload.get("claim_snapshots")
    if not isinstance(snapshots, list):
        return
    rule_index = 0
    for snapshot in snapshots:
        if not isinstance(snapshot, dict) or snapshot.get("claim_kind") != "rule_result":
            continue
        rule_index += 1
        title = str(snapshot.get("artifact_key") or f"rule-result-{rule_index:04d}")
        _append_document(
            state,
            category=SearchCategory.FINDING,
            title=title,
            reference=f"report:{report_name}#rule-result:{rule_index:04d}",
            metadata=f"report {report_name} structured rule result",
            text=_flatten_json(snapshot),
        )


def _collect_claim_references(
    payload: dict[str, object],
    report_name: str,
    state: _CollectionState,
) -> None:
    references = payload.get("claim_references")
    if not isinstance(references, list):
        return
    for index, reference in enumerate(references, start=1):
        if not isinstance(reference, dict):
            continue
        title = str(
            reference.get("artifact_key")
            or reference.get("claim_id")
            or f"claim-reference-{index:04d}"
        )
        _append_document(
            state,
            category=SearchCategory.EVIDENCE_REFERENCE,
            title=title,
            reference=f"report:{report_name}#claim:{index:04d}",
            metadata=f"report {report_name} claim reference",
            text=_flatten_json(reference),
        )


def _find_dicts(value: object, key: str, *, depth: int = 0) -> list[dict[str, object]]:
    if depth > 12:
        return []
    found: list[dict[str, object]] = []
    if isinstance(value, dict):
        selected = value.get(key)
        if isinstance(selected, list):
            found.extend(item for item in selected if isinstance(item, dict))
        for nested_key, item in sorted(value.items()):
            if nested_key != key:
                found.extend(_find_dicts(item, key, depth=depth + 1))
    elif isinstance(value, list):
        for item in value:
            found.extend(_find_dicts(item, key, depth=depth + 1))
    return found


def _append_document(
    state: _CollectionState,
    *,
    category: SearchCategory,
    title: str,
    reference: str,
    metadata: str,
    text: str,
) -> None:
    if len(state.documents) >= MAX_CANDIDATE_DOCUMENTS:
        raise RegistrySearchError(
            f"search inventory exceeds the {MAX_CANDIDATE_DOCUMENTS}-document ceiling"
        )
    values = []
    redactions = 0
    for value in (title, reference, metadata, text[:MAX_DOCUMENT_CHARACTERS]):
        safe, count = _redact_text(value)
        values.append(_collapse_whitespace(safe))
        redactions += count
    safe_title, safe_reference, safe_metadata, safe_text = values
    state.redaction_count += redactions
    state.documents.append(
        _Document(
            category=category,
            title=_truncate(safe_title or "[untitled]", MAX_RESULT_TITLE_CHARACTERS),
            reference=_truncate(
                safe_reference or f"{category.value}:[redacted]",
                MAX_RESULT_REFERENCE_CHARACTERS,
            ),
            metadata=safe_metadata,
            text=safe_text,
            redaction_count=redactions,
        )
    )


def _score_document(document: _Document, terms: list[str]) -> _ScoredDocument | None:
    fields = {
        "reference": document.reference,
        "title": document.title,
        "metadata": document.metadata,
        "text": document.text,
    }
    normalised = {name: _normalise(value) for name, value in fields.items()}
    if any(not any(term in value for value in normalised.values()) for term in terms):
        return None
    phrase = " ".join(terms)
    score = 0
    for name, value in normalised.items():
        weight = _FIELD_WEIGHTS[name]
        if value == phrase:
            score += 80 * weight
        elif value.startswith(f"{phrase} "):
            score += 40 * weight
        elif phrase in value:
            score += 20 * weight
    for term in terms:
        best = 0
        for name, value in normalised.items():
            weight = _FIELD_WEIGHTS[name]
            tokens = value.split()
            if term in tokens:
                best = max(best, 8 * weight)
            elif any(token.startswith(term) for token in tokens):
                best = max(best, 4 * weight)
            elif term in value:
                best = max(best, 2 * weight)
        score += best
    snippet = _best_snippet(fields, normalised, terms)
    return _ScoredDocument(document=document, score=score, snippet=snippet)


def _best_snippet(
    fields: dict[str, str],
    normalised: dict[str, str],
    terms: list[str],
) -> str:
    matching = [
        name
        for name in ("text", "metadata", "title", "reference")
        if any(term in normalised[name] for term in terms) and fields[name]
    ]
    selected = matching[0] if matching else "title"
    words = fields[selected].split()
    first_index = 0
    for index, word in enumerate(words):
        normalised_word = _normalise(word)
        if any(term in normalised_word for term in terms):
            first_index = index
            break
    start = max(0, first_index - 10)
    end = min(len(words), start + 42)
    snippet = " ".join(words[start:end])
    if start:
        snippet = f"… {snippet}"
    if end < len(words):
        snippet = f"{snippet} …"
    if len(snippet) > MAX_SNIPPET_CHARACTERS:
        snippet = snippet[: MAX_SNIPPET_CHARACTERS - 2].rstrip() + " …"
    return snippet or fields["title"][:MAX_SNIPPET_CHARACTERS]


def _normalise(value: str) -> str:
    return " ".join(_TOKEN.findall(unicodedata.normalize("NFKC", value).casefold()))


def _parse_json(value: str) -> object | None:
    try:
        return cast(object, json.loads(value))
    except (json.JSONDecodeError, TypeError):
        return None


def _flatten_json(value: object) -> str:
    parts: list[str] = []
    size = 0

    def visit(item: object, *, depth: int) -> None:
        nonlocal size
        if depth > 12 or size >= MAX_DOCUMENT_CHARACTERS:
            return
        if isinstance(item, dict):
            for key, nested in sorted(item.items(), key=lambda pair: str(pair[0])):
                visit(str(key), depth=depth + 1)
                visit(nested, depth=depth + 1)
        elif isinstance(item, list):
            for nested in item:
                visit(nested, depth=depth + 1)
        elif item is not None:
            text = str(item)
            remaining = MAX_DOCUMENT_CHARACTERS - size
            selected = text[:remaining]
            parts.append(selected)
            size += len(selected) + 1

    visit(value, depth=0)
    return " ".join(parts)


def _redact_text(value: str) -> tuple[str, int]:
    result = _INVALID_TEXT.sub("�", value)
    count = 0
    for pattern in (_FILE_URI, _WINDOWS_PATH, _HOME_PATH, _POSIX_PATH):
        result, replacements = pattern.subn(ABSOLUTE_PATH_REDACTION, result)
        count += replacements
    return result, count


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 2].rstrip() + " …"
