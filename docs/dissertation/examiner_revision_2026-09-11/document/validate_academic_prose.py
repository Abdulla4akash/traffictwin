"""Scientific preservation checks for the authorised 17 September prose edit.

Only repeated numerical catalogues in 4.3 and C.8 may be omitted. Their exact
values remain in the named results/proof blocks. Historical receipts are not
rewritten, and table payloads, algorithms and the full proof stay byte-identical.
"""

import json
import re
import subprocess
from collections import Counter
from pathlib import Path

BASE = "3eb469027a30933473204d95cc663c5b0a2f4afc"
HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
PACKAGE = "docs/dissertation/examiner_revision_2026-09-11"


def baseline() -> str:
    return subprocess.check_output(  # noqa: S603 -- fixed read-only Git object
        ["git", "show", f"{BASE}:{PACKAGE}/TrafficTwin_Dissertation.tex"],  # noqa: S607
        cwd=ROOT,
        text=True,
    )


def numeric(value: str) -> list[str]:
    # Ignore identifiers and cross-references, preserving scientific signs,
    # precision and comma grouping even when a value ends a sentence.
    value = re.sub(
        r"\\(?:cite|ref|eqref|label)\{[^}]*\}|\\hyperref\[[^]]*\]\{[^}]*\}",
        "",
        value,
    )
    value = value.replace(r"\ensuremath{-}", "-")
    value = re.sub(r"\b(?:E|O|RQ)[0-9]+[bcd]?\b|\bStudy [789]\b", "", value)
    return re.findall(r"(?<![\w.])[-+]?\d+(?:[,.]\d+)*(?!\w)", value)


# Each entry removes only a duplicate from the named block. The scientific
# location that retains the estimate or boundary is checked independently.
REPEATED_NUMBERS = {
    193: {
        "+4.137": 144,
        "-3.504": 144,
        "+0.631": 144,
        "3.5": 41,
        "4.1": 41,
        "0.6": 41,
        "+0.649": 150,
        "+0.193": 150,
        "+0.550": 150,
    },
    365: {"500": 342, "38.889": 342, "538.889": 342, "1,000": 343, "538": 343, "1": 342},
    367: {"100": 354, "112.929": 354, "91.818": 353},
}


def scientific_checks(tex: str | None = None) -> dict[str, bool]:
    from validate_prose_pass import blocks, table_environments

    tex = tex if tex is not None else (HERE / "TrafficTwin_Dissertation.tex").read_text()
    old = baseline()
    previous, current = blocks(old), blocks(tex)
    checks = {}
    checks["academic_same_source_block_ids"] = set(previous) == set(current)
    checks["academic_headings_and_numbering_unchanged"] = all(
        current.get(n) == value for n, value in previous.items() if value[0] == "heading"
    ) and re.findall(
        r"\\(?:label|renewcommand\{\\the(?:table|figure)\})\{[^}]+\}", tex
    ) == re.findall(r"\\(?:label|renewcommand\{\\the(?:table|figure)\})\{[^}]+\}", old)
    old_tables, new_tables = table_environments(old), table_environments(tex)
    checks["academic_all_26_table_payloads_unchanged"] = len(old_tables) == len(
        new_tables
    ) == 26 and [(kind, text.split(r"\toprule", 1)[-1]) for kind, text in old_tables] == [
        (kind, text.split(r"\toprule", 1)[-1]) for kind, text in new_tables
    ]
    for n, (kind, text) in previous.items():
        if kind in {"equation", "algorithm", "proposition"} or (
            318 <= n <= 355 and kind != "table"
        ):
            checks[f"academic_equation_algorithm_or_proof_block_{n}_unchanged"] = current.get(
                n
            ) == (kind, text)
        expected = numeric(text)
        for number, location in REPEATED_NUMBERS.get(n, {}).items():
            expected.remove(number)
            checks[f"academic_duplicate_{n}_{number}_retained_in_{location}"] = (
                number in numeric(current[location][1])
            )
        # Preserve order as well as values: interval endpoints and estimates
        # must retain their original numerical associations within each block.
        # N moves with the cost explanation from 170 into 169, with no numbers.
        checks[f"academic_block_{n}_numerical_content_preserved"] = (
            numeric(current[n][1]) == expected
        )
    checks["academic_all_citation_keys_and_evidence_links_preserved"] = Counter(
        re.findall(
            r"\\cite\{[^}]+\}|\\hyperref\[source-s\d+\]\{[^}]+\}|\\href\{\\detokenize\{[^}]+\}\}",
            tex,
        )
    ) == Counter(
        re.findall(
            r"\\cite\{[^}]+\}|\\hyperref\[source-s\d+\]\{[^}]+\}|\\href\{\\detokenize\{[^}]+\}\}",
            old,
        )
    )
    checks["academic_bibliography_unchanged"] = (
        tex.split(r"\bibitem{", 1)[1].split(r"\end{thebibliography}", 1)[0]
        == old.split(r"\bibitem{", 1)[1].split(r"\end{thebibliography}", 1)[0]
    )
    checks["academic_redundant_proof_replaced_by_specific_crossreferences"] = (
        all(
            ref in current[363][1] for ref in (r"\ref{sec:C.2}", r"\ref{sec:C.3}", r"\ref{sec:C.5}")
        )
        and r"\begin{proof}" not in current[363][1]
    )
    checks["academic_c8_numerical_and_adverse_boundaries_crossreferenced"] = all(
        ref in current[n][1]
        for n, ref in (
            (366, r"\ref{sec:C.4}"),
            (366, r"\ref{sec:C.6}"),
            (367, r"\ref{sec:C.7}"),
            (367, r"\ref{tab:C1}"),
        )
    )
    # These exact retained scientific paragraphs cover the principal guardrails.
    for n in (99, 101, 108, 313, 315, 178, 203, 205, 385, 390, 391, 395, 399, 401, 402):
        checks[f"academic_scientific_boundary_{n}_unchanged"] = current[n] == previous[n]
    checks["academic_descriptive_shares_not_causal"] = (
        "descriptive shares of arm-mean differences" in current[147][1]
        and "neither identify causal mechanism shares" in current[147][1]
        and "without assigning causal shares" in current[193][1]
    )
    checks["academic_followup_reuse_and_prospective_protocol"] = all(
        phrase in current[150][1]
        for phrase in (
            "reused its eight joint blocks",
            "protocol sealed before the new outcomes",
            "post-hoc additions are outside the original three-contrast family",
            "adjusted across all ten new contrasts",
            "sharing training seed 100",
            "does not establish robustness to independent training",
            "proposed by an AI assistant and authorised by me",
        )
    )
    checks["academic_three_trace_scope_and_caveats"] = all(
        phrase in current[152][1]
        for phrase in (
            "same demand-scaled Manchester network",
            "protocol sealed before outcomes",
            "all fifteen intervals adjusted as one family",
            "This descriptive pattern",
            "weekend trace carries the entry-channel fix",
            "evening peak and event night retain the legacy slot-reuse convention",
            "without isolating density as the cause",
        )
    )
    checks["academic_contribution_is_adaptation_with_bounded_evidence"] = (
        "adaptation and evaluation of established scheduling principles" in current[183][1]
        and "one evaluator and one network" in current[183][1]
    )
    return checks


if __name__ == "__main__":
    checks = scientific_checks()
    print(
        json.dumps({"baseline": BASE, "checks": checks, "passed": all(checks.values())}, indent=2)
    )
    raise SystemExit(0 if all(checks.values()) else 1)
