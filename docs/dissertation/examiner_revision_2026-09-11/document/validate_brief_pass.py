"""Check the registered-brief pass against 2f1af28 without rewriting evidence."""

import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path

BASE = "2f1af28400c827ab671200507d1f2e147c1570b7"
PACKAGE = "docs/dissertation/examiner_revision_2026-09-11"
HERE = Path(__file__).resolve().parents[1]
TITLE = "Dynamic Resource Management for Intelligent Transportation System Applications"
TABLE_TITLE = "Brief deliverables and where they are addressed"
LABELS = (
    "(A) An investigation into a suitable methodology for fulfilling the project objectives.",
    "(B) Design and implementation of a few ITS service use cases.",
    "(C) An investigation into the run-time profile of data-intensive ITS services.",
    "(D) An investigation into the suitability of existing (Cloud) resource management strategies "
    "for the fulfilment of ITS service requirements.",
    "(E) Proposal of strategies for dynamic management of resources using available "
    "devices and clouds.",
)


def baseline() -> str:
    return subprocess.check_output(  # noqa: S603 -- fixed read-only Git object
        ["/usr/bin/git", "show", f"{BASE}:{PACKAGE}/TrafficTwin_Dissertation.tex"],
        cwd=HERE.parents[2],
        text=True,
    )


def references(tex: str) -> dict[int, str]:
    return {
        int(n): payload
        for n, payload in re.findall(
            r"\\bibitem\{ref(\d+)\}(.*?)(?=\\bibitem\{|\\end\{thebibliography\})", tex, re.S
        )
    }


def checks(here: Path = HERE, tex_override: str | None = None) -> dict[str, bool]:
    from validate_prose_pass import blocks, body, table_environments, word_counts

    tex = (
        tex_override
        if tex_override is not None
        else (here / "TrafficTwin_Dissertation.tex").read_text()
    )
    old = baseline()
    current = blocks(tex)
    brief_match = re.search(r"% BEGIN BRIEF DELIVERABLES(.*?)% END BRIEF DELIVERABLES", tex, re.S)
    brief = brief_match[1] if brief_match else ""
    result = {}
    result["brief_title_in_metadata_and_original_cover_parbox"] = (
        "pdftitle={" + TITLE + "}" in tex
        and r"\parbox{0.72\textwidth}{\centering\Large\bfseries " + TITLE + r"\par}\par" in tex
    )
    # Derive the retired title from the historical object, avoiding a live literal pin.
    retired = re.search(r"pdftitle=\{([^}]+)\}", old)[1]
    retired_suffix = retired.split("for ", 1)[1]
    paths = [here / "TrafficTwin_Dissertation.tex"]
    paths += list((here / "document").glob("validate*.py"))
    paths += [
        p
        for p in here.rglob("README*")
        if p.is_file() and "evidence" not in p.relative_to(here).parts
    ]
    result["brief_old_title_absent_from_tex_validators_readmes"] = all(
        retired_suffix not in (tex if p.name == "TrafficTwin_Dissertation.tex" else p.read_text())
        for p in paths
    )
    result["brief_table_five_verbatim_labels"] = all(label in brief for label in LABELS)
    result["brief_table_in_section_1_4_between_blocks_50_and_51"] = bool(
        brief_match
        and tex.index("% END SOURCE BLOCK 050")
        < brief_match.start()
        < brief_match.end()
        < tex.index("% BEGIN SOURCE BLOCK 051")
    )
    result["brief_unnumbered_table_structure_and_lot_entry"] = (
        all(
            value in brief
            for value in (
                r"\begingroup",
                r"\singlespacing\footnotesize",
                r"\endgroup",
                r"\multicolumn{2}{@{}l}{\textbf{" + TABLE_TITLE + r"}}\\",
                r"\phantomsection\label{tab:brief}",
                r"\addcontentsline{lot}{table}{" + TABLE_TITLE + "}",
                r"@{}>{\hsize=1.05\hsize\linewidth=\hsize}Y>{\hsize=.95\hsize\linewidth=\hsize}Y@{}",
            )
        )
        and r"\renewcommand{\thetable}" not in brief
    )
    result["brief_citation_once_in_body_and_lead"] = (
        re.findall(r"\\cite\{[^}]*\bref48\b[^}]*\}", body(tex)) == [r"\cite{ref48}"]
        and tex.count(r"\cite{ref48}") == 1
        and r"maps the registered project brief's deliverables to this report \cite{ref48}."
        in brief
    )
    refs = references(tex)
    from validate_prose_pass import citation_reference_checks

    result["brief_references_preserved_except_exact_citation_pass_edits"] = all(
        citation_reference_checks(tex).values()
    )
    result["brief_ref48_once_after_ref47"] = (
        list(refs) == list(range(1, 49))
        and tex.count(r"\bibitem{ref48}") == 1
        and "S. Sampaio (proposer)." in refs.get(48, "")
        and "project-id-237" in refs.get(48, "")
        and TITLE in refs.get(48, "")
    )
    verification = re.search(
        r"I ran or authorised every campaign,.*?frozen evaluator source\.", old, re.S
    )
    # This exact sentence is in cf8b514, predating its deletion in 2f1af28.
    if verification is None:
        from validate_prose_pass import baseline as prose_baseline

        verification = re.search(
            r"I ran or authorised every campaign,.*?frozen evaluator source\.",
            prose_baseline(),
            re.S,
        )
    clean_paragraph = re.sub(r"\s*\\hyperref\[source-s12\]\{\[S12\]\}", "", current[178][1])
    result["brief_section_3_7_verification_restored_verbatim"] = bool(
        verification
        and verification[0] in clean_paragraph
        and "recomputed the block-0 paired effect" in current[178][1]
    )
    result["brief_section_3_7_three_sentences"] = (
        len(re.findall(r"\.\s+(?=[A-Z])|\.$", clean_paragraph)) == 3
    )
    result["brief_ambiguous_review_phrases_absent"] = all(
        value not in body(tex) for value in ("as validation and scoping", "Their dependence")
    )
    result["brief_operator_units_single_rounded_mean"] = (
        "On the morning trace, this mean effect corresponds to about 24,000 additional tasks "
        r"per hour meeting their deadline (Table~\ref{tab:E1})." in current[145][1]
    )
    without_brief = tex[: brief_match.start()] + tex[brief_match.end() :] if brief_match else tex
    old_tables, new_tables = table_environments(old), table_environments(without_brief)
    result["brief_all_existing_table_environments_byte_identical"] = new_tables == old_tables

    def numeric(table: str) -> list[str]:
        return re.findall(r"[-+]?\d+(?:[,.]\d+)*", table)

    result["brief_all_existing_table_numeric_tokens_byte_identical"] = len(old_tables) == len(
        new_tables
    ) and [numeric(t) for _, t in old_tables] == [numeric(t) for _, t in new_tables]
    tag = r"\\hyperref\[source-s\d+\]\{\[S\d+\]\}"
    result["brief_all_fifty_source_tags_preserved"] = (
        Counter(re.findall(tag, body(tex))) == Counter(re.findall(tag, body(old)))
        and len(re.findall(tag, body(tex))) == 50
    )
    counts = word_counts(tex)["after"]
    result["brief_displayed_source_counts_match_count_exemplar_words"] = (
        rf"\textbf{{Word count: {counts['strict']:,}}}" in tex
        and f"{counts['prose_only']:,} excluding tables and pseudocode." in tex
    )
    return result


def normal(text: str) -> str:
    return " ".join(text.split())


def pdf_checks(path: Path, tex: str | None = None) -> dict[str, bool]:
    import pymupdf as fitz

    doc = fitz.open(path)
    texts = [normal(page.get_text()) for page in doc]
    full = " ".join(texts)
    result = {}
    info = subprocess.check_output(  # noqa: S603 -- read-only selected PDF metadata
        ["/opt/homebrew/bin/pdfinfo", str(path)], text=True
    )
    result["brief_pdf_text_cover_and_pdfinfo_title"] = (
        TITLE in texts[0]
        and doc.metadata["title"] == TITLE
        and bool(re.search(r"^Title:\s*" + re.escape(TITLE) + r"\s*$", info, re.M))
    )
    result["brief_title_page_fits_on_one_page"] = (
        all(
            value in texts[0]
            for value in (TITLE, "Supervisor: Dr Sandra Sampaio", "Student ID: 14185028")
        )
        and "Contents" in texts[1]
    )
    table_pages = [i for i, text in enumerate(texts) if "Deliverable (brief wording)" in text]
    result["brief_pdf_table_title_present"] = TABLE_TITLE in full
    labels_present = []
    for index in table_pages:
        page = doc[index]
        # Read the left column independently of the interleaved right-column mappings.
        left = page.get_text(
            clip=fitz.Rect(0, 0, 316, page.rect.height), flags=fitz.TEXT_DEHYPHENATE
        )
        # Source checks preserve literal hyphens; PDF extraction can retain both
        # lexical and discretionary line-end hyphens. Ignore these consistently.
        visible = normal(re.sub(r"(?<=\w)-\s*(?=\w)", "", left))
        labels_present.append(all(label.replace("-", "") in visible for label in LABELS))
    result["brief_pdf_all_verbatim_labels_on_one_page"] = len(
        table_pages
    ) == 1 and labels_present == [True]
    lot = next((text for text in texts if "List of Tables" in text), "")
    result["brief_pdf_lot_lists_brief_table"] = TABLE_TITLE in lot
    result["brief_pdf_no_retired_title"] = (
        re.search(r"pdftitle=\{([^}]+)\}", baseline())[1] not in full
    )
    return result


if __name__ == "__main__":
    from validate_prose_pass import word_counts

    result = checks()
    if os.environ.get("TRAFFICTWIN_REVIEW_PDF"):
        result.update(pdf_checks(Path(os.environ["TRAFFICTWIN_REVIEW_PDF"])))
    record = {
        "baseline_commit": BASE,
        "checks": result,
        "word_counts": word_counts(),
        "passed": all(result.values()),
    }
    print(json.dumps(record, indent=2))
    raise SystemExit(0 if record["passed"] else 1)
