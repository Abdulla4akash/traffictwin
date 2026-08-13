#!/usr/bin/env python3
"""Strict final E2 research product validator — Lane 12.

Fails closed on: numeric/source drift, missing admission, absolute path/secret
leakage, false Kubernetes claim, task-replication wording, missing limitation or
offered denominator, unavailable->zero, broken route, export mismatch.
Deterministic, no timestamps, no research launch.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Ensure src on path when invoked as script
_SYS_ROOT: Path = Path(__file__).resolve().parents[1]
_SRC: Path = _SYS_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

TOL: float = 1e-12

EXPECTED_BASE_SHA: str = "4f1ef5bc82585e2a719387a71c38e188f3f43594"
EXPECTED_CAMPAIGN_BASE: str = "6e3fd0d385c20c7262e096f2d7da4995a7d9c21b"
EXPECTED_EVIDENCE_BASE: str = "bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6"

EXPECTED_HEADS: dict[str, str] = {
    "e2b": "fe2ed4e9bd9043b19b96a5f179390db629b01ccb",
    "e2c": "1a08d6e148a1e8c430da39c3d575eda3f8ea5929",
    "e2d": "80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761",
}
EXPECTED_MANIFESTS: dict[str, str] = {
    "e2b": "9383ec767dccf2f390b498e0c20283a74cd64fa521d6137fe23ce38d0022af91",
    "e2c": "fcaf2ee34b68ca4e4ef2e088d72ce2c5a410cf66ff9934a451fd8047204c480a",
    "e2d": "f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740",
}
EXPECTED_ACTOR: str = "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208"
EXPECTED_TRACE: str = "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"
EXPECTED_PACKAGE_FINGERPRINT: str = (
    "195f2e89ab4e775d1577c92a59409026fccaa2d9ebd1d973177dabd93ba83269"
)
EXPECTED_RECEIPT_FINGERPRINT: str = (
    "45e8c2782ff40495e472bc0e6de3ba3be1610fdb974f88b7ffd12a754d031ebc"
)

PINNED_E2B: dict[str, float] = {
    "off": 0.683619229,
    "jsq": 0.675681775,
    "ingress_dla": 0.715773211,
    "dla": 0.694939919,
}
PINNED_E2C_PER: list[float] = [
    -0.022097034972,
    -0.020519134179,
    -0.021447383092,
    -0.020825491499,
]
PINNED_E2C_MEAN: float = -0.021222260935
PINNED_E2C_CI: list[float] = [-0.02233525407, -0.0201092678]
PINNED_E2D_PER: list[float] = [
    0.004636732564,
    0.005867285642,
    0.005071796666,
    0.005509919752,
]
PINNED_E2D_MEAN: float = 0.005271433656
PINNED_E2D_CI: list[float] = [0.004422143925, 0.006120723387]
PINNED_E2D_VS_PER: list[float] = [
    0.026733767536,
    0.026386419821,
    0.026519179758,
    0.026335411251,
]
PINNED_E2D_VS_MEAN: float = 0.026493694591
PINNED_E2D_VS_CI: list[float] = [0.026210763951, 0.026776625232]

ACCOUNTING: dict[str, float | int] = {
    "offered": 13076234,
    "admitted": 10594205,
    "rejected_total": 2482029,
    "forwarded": 600885,
    "deadline_success": 9475948,
    "offered_attainment": 0.724669503,
    "admitted_diagnostic": 0.8944463506228169,
}

REQUIRED_LIMITATIONS: tuple[str, ...] = (
    "manchester incident hour",
    "four matched provisional fleet draws",
    "evaluator seed 0",
    "fixed 1x",
    "zero backhaul",
    "inherited deadline gate",
    "frozen vehicle actor",
    "does not observe current rsu load",
    "does not choose execution rsu",
    "e2b one-draw descriptive",
    "reuses already-observed e2c controls",
    "not independent held-out replication",
    "accounting records, not independent replicates",
    "no ordinary/free-flow control",
    "physical return is not independently instrumented",
)
REQUIRED_NONCLAIMS: tuple[str, ...] = (
    "kubernetes deployment",
    "cluster orchestration",
    "autonomous infrastructure control",
    "learned infrastructure placement",
    "learned rsu scheduler",
    "mappo choosing execution rsu",
    "mappo observing current rsu load",
    "manchester-wide",
    "population-wide",
    "physical rsu deployment",
    "physical result-return verification",
    "universal jsq superiority",
    "universal per_task_dla superiority",
    "free-flow validation",
    "independent held-out e2d replication",
    "task-level statistical replication",
    "zero-backhaul realism",
)

UNAVAILABLE_FIELDS: tuple[str, ...] = (
    "gate_rejected",
    "capacity_rejected",
    "started",
    "compute_completed",
    "returned",
    "dropped",
)

_REPO_ROOT: Path = Path(__file__).resolve().parents[1]

_ABS_PATH_RE: re.Pattern[str] = re.compile(r"(/Users/|/home/|/tmp/|/var/folders/|[A-Za-z]:\\)")
_SECRET_RE: re.Pattern[str] = re.compile(
    r"(password|secret|api[_-]?key|credential|private[_-]?key)", re.I
)
_SECRET_NEEDLES: tuple[str, ...] = (
    "password",
    "secret",
    "api-key",
    "api_key",
    "credential",
    "private_key",
    "private-key",
)


def _is_phrase_directly_negated(lower: str, phrase_start: int) -> bool:
    """Return True if phrase at phrase_start is directly negated by its nearby grammar."""
    window: str = lower[max(0, phrase_start - 80) : phrase_start]
    tokens: list[str] = re.findall(r"\b\w+\b", window)
    last_tokens: list[str] = tokens[-4:] if len(tokens) >= 4 else tokens
    negation_words: set[str] = {"not", "no", "without", "never", "non"}
    if any(t in negation_words for t in last_tokens):
        return True
    # Handle multi-word negation when immediately before phrase
    tail_immediate: str = window[-20:] if len(window) > 20 else window
    if re.search(r"\b(is|are|was|were)\s+not\s*$", tail_immediate.strip()):
        return True
    if re.search(
        r"\b(isn\'t|aren\'t|wasn\'t|weren\'t|doesn\'t|didn\'t|cannot|can\'t|won\'t|does\s+not|did\s+not)\s*$",  # noqa: E501
        tail_immediate.strip(),
    ):
        return True
    # Structural Non-claims ... include: list negates the phrase
    if "non-claim" in lower:
        nc_idx: int = lower.find("non-claim")
        if nc_idx != -1 and nc_idx < phrase_start:
            inc_idx: int = lower.find("include", nc_idx)
            incs_idx: int = lower.find("includes", nc_idx)
            use_inc: int = inc_idx if inc_idx != -1 else incs_idx
            if use_inc != -1 and use_inc < phrase_start:
                return True
            colon_idx: int = lower.find(":", nc_idx)
            if colon_idx != -1 and nc_idx < colon_idx < phrase_start:
                return True
    # Disjunctive scope: "not actual X or Y" — Y is still negated
    stripped: str = window.strip()
    if stripped.endswith("or") or stripped.endswith("or ") or re.search(r"\bor\s*$", stripped):
        earlier: str = lower[:phrase_start]
        not_idx: int = earlier.rfind("not ")
        if not_idx != -1 and phrase_start - not_idx < 100:
            return True
        if re.search(r"\b(no|without|never)\b[^.;]{0,60}$", earlier):
            return True
    if stripped.endswith(",") and "not " in lower[max(0, phrase_start - 80) : phrase_start]:
        earlier2: str = lower[:phrase_start]
        if earlier2.rfind("not ") > earlier2.rfind("."):
            return True
    return False


def _contains_affirming_secret(text: str) -> bool:
    """Return True if text contains a secret keyword affirmatively.

    Unlike Kubernetes claim detection, secret leakage has no claim-verb
    requirement; any non-negated occurrence of a secret keyword is a leak.
    "no secrets" / "without credential" are legitimate non-leak mentions.
    Phrase-bound: only the secret's own nearby construction suppresses it,
    and semicolon-separated clauses are independent units.
    """
    units: list[str] = _split_into_units(text)
    for unit in units:
        lower: str = unit.lower()
        for needle in _SECRET_NEEDLES:
            idx: int = lower.find(needle)
            while idx != -1:
                # phrase-bound leakage check — "secret leakage" check-name is not a leak
                surrounding: str = lower[max(0, idx - 20) : idx + len(needle) + 20]
                if "leakage" in surrounding:
                    idx = lower.find(needle, idx + 1)
                    continue
                prefix_for_structural: str = lower[max(0, idx - 40) : idx]
                # structural list suppresses only when it governs the secret
                if (
                    "non-claim" in prefix_for_structural
                    or "not claimed" in prefix_for_structural
                    or "explicitly not" in prefix_for_structural
                ):
                    if (
                        "include" in lower[:idx]
                        and lower.find("non-claim") < idx
                        and (":" in lower[:idx] or "include" in lower[max(0, idx - 60) : idx])
                    ):
                        idx = lower.find(needle, idx + 1)
                        continue
                    if _is_phrase_directly_negated(lower, idx):
                        idx = lower.find(needle, idx + 1)
                        continue
                if _is_phrase_directly_negated(lower, idx):
                    idx = lower.find(needle, idx + 1)
                    continue
                return True
            # while
    return False


def _split_into_units(text: str) -> list[str]:
    units: list[str] = []
    for raw_line in text.splitlines():
        line: str = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            # Headings: also split semicolon clauses into independent units
            for seg in re.split(r"\s*;\s*", line):
                seg = seg.strip()
                if seg:
                    units.append(seg)
            continue
        # Bullet / ordered list: split semicolon clauses
        m_bullet = re.match(r"^[-*]\s+(.*)", line)
        m_ordered = re.match(r"^\d+\.\s+(.*)", line)
        if m_bullet is not None:
            content = m_bullet.group(1).strip()
            if content:
                for seg in re.split(r"\s*;\s*", content):
                    seg = seg.strip()
                    if seg:
                        units.append(seg)
            continue
        if m_ordered is not None:
            content = m_ordered.group(1).strip()
            if content:
                for seg in re.split(r"\s*;\s*", content):
                    seg = seg.strip()
                    if seg:
                        units.append(seg)
            continue
        # Otherwise split into sentences on .!? followed by space, then semicolon clauses
        parts: list[str] = re.split(r"(?<=[.!?])\s+", line)
        for part in parts:
            for seg in re.split(r"\s*;\s*", part):
                seg = seg.strip()
                if seg:
                    units.append(seg)
    return units


def _contains_affirming(text: str, phrase: str) -> bool:
    needle: str = phrase.lower()
    units: list[str] = _split_into_units(text)
    claim_verbs: tuple[str, ...] = (
        "performs",
        "perform",
        "does",
        "doing",
        "did",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "has",
        "have",
        "had",
        "carries",
        "carry",
        "carrying",
        "provides",
        "provide",
        "implements",
        "implement",
        "deploys",
        "deploy",
        "orchestrates",
        "orchestrate",
        "uses",
        "use",
        "using",
        "offers",
        "ensures",
        "executes",
        "runs",
        "contains",
        "includes",
    )
    for unit in units:
        lower: str = unit.lower()
        if needle not in lower:
            continue
        # Find each occurrence of the phrase — phrase-bound negation, not unit-wide
        start_idx: int = lower.find(needle)
        while start_idx != -1:
            if _is_phrase_directly_negated(lower, start_idx):
                start_idx = lower.find(needle, start_idx + 1)
                continue
            # For bare list items that are just noun phrases without a claiming verb,
            # don't flag (these are legitimate non-claims listings like
            # "actual Kubernetes deployment / cluster orchestration")
            has_verb: bool = any(
                re.search(r"\b" + re.escape(v) + r"\b", lower) is not None for v in claim_verbs
            )
            if not has_verb:
                start_idx = lower.find(needle, start_idx + 1)
                continue
            return True
        # while no affirming occurrence in this unit
    return False


def _fail(errors: list[str], msg: str) -> None:
    errors.append(msg)


def _check_base_receipt(errors: list[str]) -> None:
    p: Path = _REPO_ROOT / "docs/closure/e2_product_lane12_base_receipt.json"
    if not p.exists():
        _fail(errors, f"base receipt missing: {p}")
        return
    try:
        data: dict[str, object] = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        _fail(errors, f"base receipt not valid JSON: {exc}")
        return
    got_base = data.get("BASE_INTEGRATION_SHA")
    if got_base != EXPECTED_BASE_SHA:
        _fail(
            errors,
            f"BASE_INTEGRATION_SHA drift: expected {EXPECTED_BASE_SHA!r}, got {got_base!r}",
        )
    if data.get("controller_campaign_base") != EXPECTED_CAMPAIGN_BASE:
        _fail(
            errors,
            f"campaign base drift: {data.get('controller_campaign_base')!r}",
        )
    if data.get("lane") != 12:
        _fail(errors, f"receipt lane must be 12, got {data.get('lane')!r}")


def _check_builtin(errors: list[str]) -> None:
    try:
        from traffictwin.evidence_admission.e2_research import (  # type: ignore[import-untyped, unused-ignore]
            load_admitted_builtin_e2_research,
        )
        from traffictwin.experiments.e2_research_artifact import (  # type: ignore[import-untyped, unused-ignore]
            builtin_e2_research_json,
            validate_e2_research_artifact,
        )

        text: str = builtin_e2_research_json()
        if not text.strip():
            _fail(errors, "builtin_e2_research_json empty")
            return
        if "/Users/" in text or "/home/" in text:
            _fail(errors, "builtin JSON contains absolute path")
        pkg = validate_e2_research_artifact(text)
        pkg2, receipt = load_admitted_builtin_e2_research()
        if pkg.fingerprint() != pkg2.fingerprint():
            _fail(
                errors,
                "builtin fingerprint mismatch between validate and admitted load",
            )
        if receipt.package_fingerprint != EXPECTED_PACKAGE_FINGERPRINT:
            _fail(
                errors,
                f"package fingerprint drift: {receipt.package_fingerprint!r} "
                f"expected {EXPECTED_PACKAGE_FINGERPRINT!r}",
            )
        if receipt.receipt_fingerprint != EXPECTED_RECEIPT_FINGERPRINT:
            _fail(
                errors,
                f"receipt fingerprint drift: {receipt.receipt_fingerprint!r} "
                f"expected {EXPECTED_RECEIPT_FINGERPRINT!r}",
            )
        if receipt.package_fingerprint == receipt.receipt_fingerprint:
            _fail(errors, "package and receipt fingerprints must be distinct")
        if receipt.standing != "OWNER-AUTHORIZED PRODUCT ADMISSION":
            _fail(
                errors,
                f"receipt standing must be OWNER-AUTHORIZED PRODUCT ADMISSION, "
                f"got {receipt.standing!r}",
            )
        if receipt.admission_mode != "ADMITTED_RESEARCH":
            _fail(
                errors,
                f"admission_mode must be ADMITTED_RESEARCH, got {receipt.admission_mode!r}",
            )
        try:
            receipt.verify()
        except Exception as exc:
            _fail(errors, f"receipt.verify failed: {exc}")
    except Exception as exc:
        _fail(errors, f"builtin/admission load failed: {exc}")


def _close(a: float, b: float) -> bool:
    return abs(float(a) - float(b)) <= TOL


def _check_numerics(errors: list[str]) -> None:
    try:
        from traffictwin.evidence_admission.e2_research import (
            load_admitted_builtin_e2_research,
        )
        from traffictwin.experiments.e2_comparison import (  # type: ignore[import-untyped, unused-ignore]
            build_e2_comparison_view,
        )
        from traffictwin.experiments.e2_task_accounting import (  # type: ignore[import-untyped, unused-ignore]
            build_e2_seed1_task_accounting,
        )

        pkg, _receipt = load_admitted_builtin_e2_research()
        si = pkg.source_identities
        if si.base_sha != EXPECTED_EVIDENCE_BASE:
            _fail(errors, f"source base_sha drift: {si.base_sha!r}")
        if si.actor.sha256 != EXPECTED_ACTOR:
            _fail(errors, "actor sha drift")
        if si.trace.sha256 != EXPECTED_TRACE:
            _fail(errors, "trace sha drift")
        for k in ("e2b", "e2c", "e2d"):
            head_got: str = getattr(si.research_heads, k)
            if head_got != EXPECTED_HEADS[k]:
                _fail(errors, f"research head {k} drift")
            man_got: str = si.manifest_sha256_by_study[k]
            if man_got != EXPECTED_MANIFESTS[k]:
                _fail(errors, f"manifest {k} drift")
        if pkg.replication_unit != "fleet_draw":
            _fail(
                errors,
                f"replication_unit must be fleet_draw, got {pkg.replication_unit!r}",
            )
        if pkg.evaluator_seed != 0:
            _fail(errors, f"evaluator_seed must be 0, got {pkg.evaluator_seed!r}")

        comp = build_e2_comparison_view(pkg)
        if not _close(comp.e2b.off, PINNED_E2B["off"]):
            _fail(errors, f"E2b off drift: {comp.e2b.off!r}")
        if not _close(comp.e2b.jsq, PINNED_E2B["jsq"]):
            _fail(errors, f"E2b jsq drift: {comp.e2b.jsq!r}")
        if not _close(comp.e2b.ingress_dla, PINNED_E2B["ingress_dla"]):
            _fail(errors, "E2b ingress_dla drift")
        if not _close(comp.e2b.dla, PINNED_E2B["dla"]):
            _fail(errors, "E2b dla drift")
        for a, e in zip(comp.e2c.per_seed_values, PINNED_E2C_PER, strict=True):
            if not _close(float(a), float(e)):
                _fail(errors, f"E2c per-seed drift: {a!r} vs {e!r}")
        if not _close(float(comp.e2c.mean), PINNED_E2C_MEAN):
            _fail(errors, f"E2c mean drift: {comp.e2c.mean!r}")
        if not _close(float(comp.e2c.lower), PINNED_E2C_CI[0]):
            _fail(errors, "E2c CI lower drift")
        if not _close(float(comp.e2c.upper), PINNED_E2C_CI[1]):
            _fail(errors, "E2c CI upper drift")
        for a, e in zip(comp.e2d.per_seed_values, PINNED_E2D_PER, strict=True):
            if not _close(float(a), float(e)):
                _fail(errors, f"E2d per-seed drift {a!r} vs {e!r}")
        if not _close(float(comp.e2d.mean), PINNED_E2D_MEAN):
            _fail(errors, "E2d mean drift")
        if not _close(float(comp.e2d.lower), PINNED_E2D_CI[0]):
            _fail(errors, "E2d lower drift")
        if not _close(float(comp.e2d.upper), PINNED_E2D_CI[1]):
            _fail(errors, "E2d upper drift")
        if not _close(float(comp.e2d_vs_common_target.mean), PINNED_E2D_VS_MEAN):
            _fail(errors, "E2d vs dla mean drift")
        if not _close(float(comp.e2d_vs_common_target.lower), PINNED_E2D_VS_CI[0]):
            _fail(errors, "E2d vs dla lower drift")
        if not _close(float(comp.e2d_vs_common_target.upper), PINNED_E2D_VS_CI[1]):
            _fail(errors, "E2d vs dla upper drift")

        acc = build_e2_seed1_task_accounting(pkg)
        for k in (
            "offered",
            "admitted",
            "rejected_total",
            "forwarded",
            "deadline_success",
        ):
            got = getattr(acc, k)
            want = ACCOUNTING[k]
            if got != want:
                _fail(errors, f"accounting {k} drift: {got!r} vs {want!r}")
        if not _close(
            float(acc.offered_deadline_attainment),
            float(ACCOUNTING["offered_attainment"]),
        ):
            _fail(errors, "accounting offered_attainment drift")
        if not _close(
            float(acc.admitted_deadline_attainment),
            float(ACCOUNTING["admitted_diagnostic"]),
        ):
            _fail(errors, "accounting admitted_diagnostic drift")
        if acc.headline_denominator != "offered":
            _fail(
                errors,
                f"headline denominator must be offered, got {acc.headline_denominator!r}",
            )
        if not acc.conservation_holds:
            _fail(errors, "conservation must hold")
        entry = acc.unavailable["gate_rejected"]
        if entry.value is not None:
            _fail(errors, "gate_rejected must be None/UNAVAILABLE")
        for f in UNAVAILABLE_FIELDS:
            ent = acc.unavailable[f]
            if ent.value is not None:
                _fail(errors, f"unavailable {f} must be None")
            if not ent.reason or len(ent.reason.strip()) < 10:
                _fail(errors, f"unavailable {f} reason missing")
            if ent.status != "UNAVAILABLE":
                _fail(errors, f"unavailable {f} status must be UNAVAILABLE")
    except Exception as exc:
        _fail(errors, f"numeric check failed: {exc}")


def _check_strategies(errors: list[str]) -> None:
    try:
        from traffictwin.experiments.e2_strategy_semantics import (  # type: ignore[import-untyped, unused-ignore]
            e2_strategy_semantics,
        )

        sems = e2_strategy_semantics()
        ids: set[str] = {s.strategy_id for s in sems}
        for need in ("off", "jsq", "ingress_dla", "dla", "per_task_dla"):
            if need not in ids:
                _fail(errors, f"missing strategy {need}")
        for s in sems:
            if s.is_learned:
                _fail(
                    errors,
                    f"strategy {s.strategy_id} is_learned must be False",
                )
            if not s.is_deterministic:
                _fail(
                    errors,
                    f"strategy {s.strategy_id} is_deterministic must be True",
                )
            joined: str = " ".join([s.execution_placement, s.infrastructure_authority, s.admission])
            for phrase in ("kubernetes deployment", "cluster orchestration"):
                if _contains_affirming(joined, phrase):
                    _fail(
                        errors,
                        f"strategy {s.strategy_id} falsely claims {phrase}",
                    )
            if _contains_affirming(joined, "learned placement") or _contains_affirming(
                joined, "learned scheduler"
            ):
                _fail(
                    errors,
                    f"strategy {s.strategy_id} falsely claims learned placement",
                )
    except Exception as exc:
        _fail(errors, f"strategy check failed: {exc}")


def _check_limitations(errors: list[str]) -> None:
    try:
        from traffictwin.evidence_admission.e2_research import (
            load_admitted_builtin_e2_research,
        )

        pkg, _ = load_admitted_builtin_e2_research()
        low_lims: list[str] = [s.lower() for s in pkg.limitations]
        for phrase in REQUIRED_LIMITATIONS:
            if not any(phrase.lower() in lim for lim in low_lims):
                _fail(errors, f"required limitation missing: {phrase!r}")
        low_ncs: list[str] = [s.lower() for s in pkg.non_claims]
        for phrase in REQUIRED_NONCLAIMS:
            if not any(phrase.lower() in nc for nc in low_ncs):
                _fail(errors, f"required non_claim missing: {phrase!r}")
        doc: str = (_REPO_ROOT / "docs/e2_research_product.md").read_text(encoding="utf-8")
        if "0.724669503" not in doc:
            _fail(
                errors,
                "docs/e2_research_product.md missing offered attainment 0.724669503",
            )
        if "0.8944463506228169" not in doc:
            _fail(
                errors,
                "docs/e2_research_product.md missing admitted diagnostic",
            )
        if "fleet_draw" not in doc:
            _fail(errors, "docs missing replication_unit fleet_draw")
        if "ADMITTED RESEARCH" not in doc or "OWNER-AUTHORIZED PRODUCT ADMISSION" not in doc:
            _fail(errors, "docs missing admission badges")
    except Exception as exc:
        _fail(errors, f"limitations check failed: {exc}")


def _check_absolute_path_secret(errors: list[str]) -> None:
    try:
        from traffictwin.evidence_admission.e2_research import (
            load_admitted_builtin_e2_research,
        )
        from traffictwin.reporting.e2_research import (  # type: ignore[import-untyped, unused-ignore]
            build_e2_research_exports,
        )

        pkg, receipt = load_admitted_builtin_e2_research()
        exports = build_e2_research_exports(pkg, receipt)
        for name, text in (
            ("json", exports.json),
            ("csv", exports.csv),
            ("markdown", exports.markdown),
        ):
            if _ABS_PATH_RE.search(text):
                _fail(errors, f"export {name} contains absolute path")
            if re.search(r"[A-Za-z]:\\", text):
                _fail(errors, f"export {name} contains Windows absolute path")
            if _SECRET_RE.search(text.lower()):
                _fail(errors, f"export {name} contains secret-like keyword")
            if '"timestamp"' in text.lower() or '"admitted_at"' in text.lower():
                _fail(errors, f"export {name} contains timestamp key")
        for p in [
            _REPO_ROOT / "docs/e2_research_product.md",
            _REPO_ROOT / "docs/closure/e2_product_traceability.json",
            _REPO_ROOT / "docs/closure/e2_product_lane12_base_receipt.json",
        ]:
            if not p.exists():
                continue
            txt: str = p.read_text(encoding="utf-8")
            if _ABS_PATH_RE.search(txt):
                _fail(errors, f"{p.name} contains absolute path")
            if _contains_affirming_secret(txt):
                _fail(errors, f"{p.name} contains secret keyword")
            # Also catch single-backslash Windows paths like C:\Users\...
            if re.search(r"[A-Za-z]:\\", txt):
                _fail(errors, f"{p.name} contains Windows absolute path")
    except Exception as exc:
        _fail(errors, f"path/secret check failed: {exc}")


def _check_kubernetes_claim(errors: list[str]) -> None:
    try:
        docs: str = (_REPO_ROOT / "docs/e2_research_product.md").read_text(encoding="utf-8")
        for phrase in (
            "kubernetes deployment",
            "cluster orchestration",
            "kubernetes cluster",
        ):
            if _contains_affirming(docs, phrase):
                _fail(
                    errors,
                    f"docs falsely claims affirming '{phrase}' as real deployment",
                )
        status: str = (_REPO_ROOT / "docs/implementation-status.md").read_text(encoding="utf-8")
        e2_start: int = status.find("## E2 Research Product")
        e2_sec: str = status[e2_start : e2_start + 8000] if e2_start != -1 else status
        for phrase in ("kubernetes deployment", "cluster orchestration"):
            if _contains_affirming(e2_sec, phrase):
                _fail(errors, f"implementation-status falsely claims '{phrase}'")
        for phrase in (
            "supervisor approval",
            "randy confirmation",
            "research approval",
        ):
            if _contains_affirming(docs, phrase):
                _fail(errors, f"docs falsely claims affirming '{phrase}'")
            if _contains_affirming(e2_sec, phrase):
                _fail(
                    errors,
                    f"implementation-status falsely claims '{phrase}'",
                )
    except Exception as exc:
        _fail(errors, f"k8s claim check failed: {exc}")


def _check_task_replication(errors: list[str]) -> None:
    try:
        docs: str = (_REPO_ROOT / "docs/e2_research_product.md").read_text(encoding="utf-8")
        if "accounting records" not in docs.lower():
            _fail(errors, "docs missing 'accounting records' wording")
        for phrase in (
            "task-level statistical replication",
            "tasks are statistical replications",
            "tasks are replicates",
        ):
            if _contains_affirming(docs, phrase):
                _fail(
                    errors,
                    f"docs falsely affirms task replication '{phrase}'",
                )
        if "fleet_draw" not in docs:
            _fail(errors, "docs missing fleet_draw replication_unit")
        tr: dict[str, object] = json.loads(
            (_REPO_ROOT / "docs/closure/e2_product_traceability.json").read_text(encoding="utf-8")
        )
        pinned = tr.get("pinned_identities", {})
        assert isinstance(pinned, dict)
        if pinned.get("replication_unit") != "fleet_draw":
            _fail(errors, "traceability replication_unit drift")
    except Exception as exc:
        _fail(errors, f"task replication check failed: {exc}")


def _check_routes(errors: list[str]) -> None:
    checks: list[tuple[Path, str]] = [
        (_REPO_ROOT / "src/traffictwin/ui/pages/home.py", "Inspect real E2 research"),
        (
            _REPO_ROOT / "src/traffictwin/ui/pages/resource_strategy_explorer.py",
            "Load TrafficTwin E2 research",
        ),
        (
            _REPO_ROOT / "src/traffictwin/ui/app_pages/resource_strategy.py",
            "RESOURCE_STRATEGY_EXPLORER",
        ),
        (
            _REPO_ROOT / "src/traffictwin/ui/navigation_v07.py",
            "RESOURCE_STRATEGY_EXPLORER",
        ),
        (
            _REPO_ROOT / "src/traffictwin/ui/components/e2_research.py",
            "render_e2_research",
        ),
    ]
    for path, needle in checks:
        if not path.exists():
            _fail(errors, f"route file missing: {path}")
            continue
        txt: str = path.read_text(encoding="utf-8")
        if needle not in txt:
            _fail(errors, f"route {path.name} missing marker {needle!r}")
    docs: str = (_REPO_ROOT / "docs/e2_research_product.md").read_text(encoding="utf-8")
    if "Inspect real E2 research" not in docs or "Load TrafficTwin E2 research" not in docs:
        _fail(errors, "docs missing route description")


def _check_exports_mismatch(errors: list[str]) -> None:
    try:
        from traffictwin.evidence_admission.e2_research import (
            load_admitted_builtin_e2_research,
        )
        from traffictwin.reporting.e2_research import (
            build_e2_research_exports,
        )

        pkg, receipt = load_admitted_builtin_e2_research()
        a = build_e2_research_exports(pkg, receipt)
        b = build_e2_research_exports(pkg, receipt)
        if a.json != b.json or a.csv != b.csv or a.markdown != b.markdown:
            _fail(errors, "exports not deterministic (two builds differ)")
        j: dict[str, object] = json.loads(a.json)
        task_acc = j.get("task_accounting", {})
        assert isinstance(task_acc, dict)
        if task_acc.get("offered") != ACCOUNTING["offered"]:
            _fail(errors, "export offered drift")
        dens = task_acc.get("denominators", {})
        assert isinstance(dens, dict)
        if dens.get("headline_denominator") != "offered":
            _fail(errors, "export headline_denominator must be offered")
        unav = task_acc.get("unavailable", {})
        assert isinstance(unav, dict)
        for f in UNAVAILABLE_FIELDS:
            entry = unav.get(f, {})
            assert isinstance(entry, dict)
            if entry.get("value") == 0 or entry.get("null_value") == 0:
                _fail(errors, f"export unavailable {f} must not be 0")
            if entry.get("value") != "UNAVAILABLE":
                _fail(errors, f"export unavailable {f} must be 'UNAVAILABLE'")
        prov = j.get("provenance", {})
        assert isinstance(prov, dict)
        if prov.get("actor_sha256") != EXPECTED_ACTOR:
            _fail(errors, "export actor sha drift")
        if prov.get("trace_sha256") != EXPECTED_TRACE:
            _fail(errors, "export trace sha drift")
    except Exception as exc:
        _fail(errors, f"export mismatch check failed: {exc}")


def _check_fingerprint_labels(errors: list[str]) -> None:
    try:
        docs: str = (_REPO_ROOT / "docs/e2_research_product.md").read_text(encoding="utf-8")
        status: str = (_REPO_ROOT / "docs/implementation-status.md").read_text(encoding="utf-8")
        # Docs must label package fingerprint distinctly from receipt fingerprint
        if EXPECTED_PACKAGE_FINGERPRINT not in docs:
            _fail(errors, "docs missing package fingerprint")
        if EXPECTED_RECEIPT_FINGERPRINT not in docs:
            _fail(errors, "docs missing receipt fingerprint")
        # Verify correct labeling: package label near package fp, receipt label near receipt fp
        lower_docs: str = docs.lower()
        pkg_idx: int = lower_docs.find(EXPECTED_PACKAGE_FINGERPRINT.lower())
        rec_idx: int = lower_docs.find(EXPECTED_RECEIPT_FINGERPRINT.lower())
        if pkg_idx != -1:
            ctx_pkg: str = lower_docs[max(0, pkg_idx - 80) : pkg_idx]
            if "package" not in ctx_pkg:
                _fail(errors, "package fingerprint not labeled as package in docs")
        if rec_idx != -1:
            ctx_rec: str = lower_docs[max(0, rec_idx - 80) : rec_idx]
            if "receipt" not in ctx_rec:
                _fail(errors, "receipt fingerprint not labeled as receipt in docs")
        # Same for implementation-status E2 section
        e2_start: int = status.find("## E2 Research Product")
        e2_sec: str = status[e2_start : e2_start + 8000] if e2_start != -1 else status
        if EXPECTED_PACKAGE_FINGERPRINT not in e2_sec:
            _fail(errors, "implementation-status missing package fingerprint")
        if EXPECTED_RECEIPT_FINGERPRINT not in e2_sec:
            _fail(errors, "implementation-status missing receipt fingerprint")
        # Traceability must contain both separate named fields
        tr: dict[str, object] = json.loads(
            (_REPO_ROOT / "docs/closure/e2_product_traceability.json").read_text(encoding="utf-8")
        )
        adm = tr.get("admission", {})
        assert isinstance(adm, dict)
        if adm.get("package_fingerprint") != EXPECTED_PACKAGE_FINGERPRINT:
            _fail(errors, "traceability package_fingerprint mismatch")
        if adm.get("receipt_fingerprint") != EXPECTED_RECEIPT_FINGERPRINT:
            _fail(errors, "traceability receipt_fingerprint mismatch")
        if adm.get("package_fingerprint") == adm.get("receipt_fingerprint"):
            _fail(errors, "traceability package and receipt fingerprints must be distinct")
    except Exception as exc:
        _fail(errors, f"fingerprint label check failed: {exc}")


def main() -> int:
    errors: list[str] = []
    _check_base_receipt(errors)
    _check_builtin(errors)
    _check_numerics(errors)
    _check_strategies(errors)
    _check_limitations(errors)
    _check_absolute_path_secret(errors)
    _check_kubernetes_claim(errors)
    _check_task_replication(errors)
    _check_routes(errors)
    _check_exports_mismatch(errors)
    _check_fingerprint_labels(errors)

    try:
        docs: str = (_REPO_ROOT / "docs/e2_research_product.md").read_text(encoding="utf-8")
        if len(docs) > 20000:
            _fail(
                errors,
                "docs/e2_research_product.md too long — must be concise, not giant design doc",
            )
        for phrase in (
            "supervisor approved",
            "randy approved",
            "kubernetes approved",
            "research approved",
        ):
            if _contains_affirming(docs, phrase):
                _fail(errors, f"docs claims forbidden approval '{phrase}'")
    except Exception as exc:
        _fail(errors, f"docs approval check failed: {exc}")

    if errors:
        print("E2 research product validation FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("E2 research product validation PASSED")
    print(f"  base {EXPECTED_BASE_SHA}")
    print(
        f"  heads e2b {EXPECTED_HEADS['e2b']} e2c {EXPECTED_HEADS['e2c']} "
        f"e2d {EXPECTED_HEADS['e2d']}"
    )
    print(f"  actor {EXPECTED_ACTOR[:12]}… trace {EXPECTED_TRACE[:12]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
