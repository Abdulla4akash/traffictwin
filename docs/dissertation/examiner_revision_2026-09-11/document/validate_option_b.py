"""Bind Option B preservation checks to the owner's exact Git baseline."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Callable
from pathlib import Path

from validate_final_pass import FINAL_PASS_BASELINE, git_bytes, restore_final_pass
from validate_platform_connection import (
    PLATFORM_INTEGRATION_BASE,
    restore_platform_connection,
)

BASELINE = "9b49efc34a482e5abaab804efcd857b368087c52"
PACKAGE = "docs/dissertation/examiner_revision_2026-09-11"
BASELINE_SHA256 = "1f9b0280010cb13e622678e71122296e7360f649e517496559c98303cd086ced"
CLOSE_BASELINE = "2c29392cbf04bf060aacb0f03f1fbb900842d54a"
CLOSE_BASELINE_SHA256 = "307862fcc37558df585b0e867a0766aa3616cd810ee0595df398dd3ffaf0cf89"
CLOSE_LEDGER_SHA256 = "75fda6f1fcac0fe9f38d8df150cfd4b62619a10bedf11c04f6bf46c7a9cfb65d"
PROJECT_TITLE = "Dynamic Resource Management for Intelligent Transportation System Applications"
PREVIOUS_TITLE = (
    "TrafficTwin: Admission and Dispatch Semantics in Vehicular Edge Computing "
    "under a Frozen MAPPO Policy"
)
PRE_TITLE_MARKDOWN_SHA256 = "938213d74d9093008a6493dd992fa1157fe4758f266c59f5f2dfd78e8314b4f3"
EDITORIAL_BASELINE = "7075b2576292cc9a98854bf5664449df66617b96"
EDITORIAL_BASELINE_SHA256 = "1458bc73b4533bcfe051bcb4957007e0762613e3c60bfffaa8c107b402c007e8"
EDITORIAL_LEDGER_SHA256 = "b0bc1ec096fe58cab2baf1db414618c92ad7bb81ac81f6bd72345248e16237f9"
CONTRIBUTIONS_BASELINE = "da499546207afe33d878eca2ba709f5efbb1e673"
CONTRIBUTIONS_BASELINE_SHA256 = "f3867b5ff9d2937faab842b14409914e2747452e1cc2c5093961b2860f394537"
CONTRIBUTIONS_LEDGER_SHA256 = "e181ea6b38731f324f85caa31ba68611c89657c154366b8c46d4640b08cfc371"


def section(text: str, number: str) -> str:
    start = re.search(r"(?m)^### " + re.escape(number) + r" .*$", text)
    assert start, number
    end = re.search(r"(?m)^#{2,3} ", text[start.end() :])
    return text[start.start() : start.end() + end.start() if end else len(text)]


def appendix(text: str, letter: str) -> str:
    tail = text.split("## Appendix " + letter + ". ", 1)[1]
    return tail.split("\n## Appendix ", 1)[0]


def check_contributions(
    root: Path,
    here: Path,
    revised: str,
    table_parser: Callable[[str], dict[str, list[str]]],
) -> tuple[str, dict[str, bool]]:
    """Bind the owner's contributions and designated trims to the reviewed source."""
    baseline = subprocess.check_output(  # noqa: S603 -- fixed read-only Git arguments
        [
            "/usr/bin/git",
            "show",
            f"{CONTRIBUTIONS_BASELINE}:{PACKAGE}/TrafficTwin_Dissertation.md",
        ],
        cwd=root,
        text=True,
    )
    ledger = (here / "evidence/CONTRIBUTIONS_OPERATIONS_2026-09-15.json").read_bytes()
    record = json.loads(ledger)
    checks = {
        "contributions_baseline_hash": hashlib.sha256(baseline.encode()).hexdigest()
        == CONTRIBUTIONS_BASELINE_SHA256
        == record["baseline_markdown_sha256"],
        "contributions_authorised_operation_ledger_hash": hashlib.sha256(ledger).hexdigest()
        == CONTRIBUTIONS_LEDGER_SHA256,
    }
    restored = revised
    reversible = True
    for op in reversed(record["operations"]):
        if not op["new"] or restored.count(op["new"]) != 1:
            reversible = False
            break
        restored = restored.replace(op["new"], op["old"], 1)
    checks["contributions_only_A_B_and_F1_source_changes"] = reversible and restored == baseline
    paragraphs = record["contribution_paragraphs"]
    checks["contributions_seven_paragraphs_once_in_order_at_end_of_1_3"] = (
        len(paragraphs) == 7
        and all(revised.count(body) == 1 for body in paragraphs)
        and section(revised, "1.3").rstrip().endswith("\n\n".join(paragraphs))
    )
    for i, deletion in enumerate(record["deletions"], 1):
        checks[f"contributions_B_deletion_{i}_absent"] = deletion["body"] not in revised
    checks["contributions_3_4_equivalent_shares_statement_retained"] = (
        "84.8% for ingress-to-round-robin and 15.2% for the additional round-robin-to-per-task step"
        in section(revised, "3.4")
    )
    for number in ["1.2", "3.2", "3.3", "3.4", "3.5", "3.6"]:
        checks[f"contributions_section_{number}_byte_identical_to_da49954"] = section(
            revised, number
        ) == section(baseline, number)
    checks["contributions_all_twenty_table_bodies_unchanged"] = (
        table_parser(revised) == table_parser(baseline) and len(table_parser(revised)) == 20
    )
    checks["contributions_references_1_to_46_unchanged"] = (
        revised.split("## References\n", 1)[1].split("## Appendix A.", 1)[0]
        == baseline.split("## References\n", 1)[1].split("## Appendix A.", 1)[0]
    )
    verification = (
        next(
            paragraph
            for paragraph in baseline.split("\n\n")
            if paragraph.startswith("I designed the research questions")
        )
        .split("I ran or authorised every campaign,", 1)[1]
        .split(" The contribution is", 1)[0]
    )
    checks["contributions_author_verification_and_declaration_pointer_retained"] = (
        "I ran or authorised every campaign," + verification in section(revised, "3.7")
        and "contribution statement (Section 3.7)" in revised.split("## Acknowledgements", 1)[0]
    )
    if record["fallback_F1_used"]:
        body = record["fallback_F1_body"]
        checks["contributions_F1_only_after_count_failure_and_verbatim"] = (
            record["before_F1_counts"]["words"] > 8950
            and body in section(baseline, "3.7")
            and body not in section(revised, "3.7")
            and revised.count(body) == appendix(revised, "D").count(body) == 1
            and appendix(revised, "D").split("\n\n")[1].endswith(body)
        )
    count_path = here / "evidence" / record["run_count_derivation"]
    checks["contributions_run_count_derivation_present_and_pinned"] = (
        count_path.is_file()
        and hashlib.sha256(count_path.read_bytes()).hexdigest()
        == record["run_count_derivation_sha256"]
    )
    count = json.loads(count_path.read_text())
    runs = [run for group in count["components"] for run in group["runs"]]
    checks["contributions_run_inventory_sum_and_deduplication"] = (
        sum(group["count"] for group in count["components"])
        == len(runs)
        == len({run["original_summary_sha256"] for run in runs})
        == count["completed_campaign_inventory_total"]
        == 82
    )
    receipt_checks = []
    for run in runs:
        path = root / run["receipt"]
        raw = path.read_bytes()
        value = json.loads(raw)
        for part in run["json_pointer"].strip("/").split("/"):
            value = value[int(part)] if isinstance(value, list) else value[part]
        receipt_checks.append(
            hashlib.sha256(raw).hexdigest() == run["receipt_sha256"]
            and (
                value == run["observed_horizon"] in (3600, 10800)
                if run["observed_horizon"] is not None
                else run["original_summary_sha256"]
                == value.get("sha256", value.get("full_summary_sha256"))
            )
        )
    checks["contributions_run_receipts_and_observed_horizons_match"] = all(receipt_checks)
    checks["contributions_count_fallback_honours_missing_summary_horizons"] = (
        not count["exact_number_printed"]
        and count["printed_value"] == "more than eighty"
        and count["completed_campaign_inventory_total"] > 80
        and count["components_without_per_run_summary_horizons"] == ["E1", "E2c", "E2d"]
        and count["direct_summary_horizon_count"]
        == sum(run["observed_horizon"] is not None for run in runs)
        == 56
        and "and more than eighty full evaluator runs" in paragraphs[5]
    )
    return restored, checks


def check_editorial_fixes(
    root: Path,
    here: Path,
    revised: str,
    table_parser: Callable[[str], dict[str, list[str]]],
) -> tuple[str, dict[str, bool]]:
    """Check current content, then undo only the owner's six-point revision."""
    baseline = subprocess.check_output(  # noqa: S603 -- fixed read-only Git arguments
        [
            "/usr/bin/git",
            "show",
            f"{EDITORIAL_BASELINE}:{PACKAGE}/TrafficTwin_Dissertation.md",
        ],
        cwd=root,
        text=True,
    )
    ledger = (here / "evidence/EDITORIAL_FIX_OPERATIONS_2026-09-15.json").read_bytes()
    record = json.loads(ledger)
    checks = {
        "editorial_baseline_hash": hashlib.sha256(baseline.encode()).hexdigest()
        == EDITORIAL_BASELINE_SHA256
        == record["baseline_markdown_sha256"],
        "editorial_authorised_operation_ledger_hash": hashlib.sha256(ledger).hexdigest()
        == EDITORIAL_LEDGER_SHA256,
    }
    restored = revised
    reversible = True
    for op in reversed(record["operations"]):
        if not op["new"] or restored.count(op["new"]) != 1:
            reversible = False
            break
        restored = restored.replace(op["new"], op["old"], 1)
    checks["editorial_only_authorised_source_changes"] = reversible and restored == baseline
    before, after = table_parser(baseline), table_parser(revised)
    checks["editorial_table_identifiers_only_10_to_8_and_11_to_9"] = set(after) == (
        (set(before) - {"10", "11"}) | {"8", "9"}
    )
    checks["editorial_main_tables_have_no_numbering_hole"] = list(
        table_parser(revised.split("## References\n", 1)[0])
    ) == ["1", "2", "3", "3a", "4", "5", "6", "7", "8", "9"]
    for number, rows in before.items():
        target = record["table_numbers"].get(number, number)
        checks[f"editorial_table_{number}_to_{target}_byte_identical"] = rows == after.get(target)
    figure = record["figure_move"]["body"]
    checks["editorial_figure_2_moved_verbatim_to_2_3"] = (
        figure in section(baseline, "1.1")
        and section(revised, "2.3").count(figure) == revised.count(figure) == 1
        and figure not in section(revised, "1.1")
        and hashlib.sha256(figure.encode()).hexdigest() == record["figure_move"]["sha256"]
    )
    closing = record["closing_move"]["body"]
    checks["editorial_overall_conclusion_moved_verbatim_to_section_4_opening"] = (
        closing in section(baseline, "4.4")
        and revised.split("## 4. Conclusion\n\n", 1)[1].startswith(closing + "\n\n")
        and revised.count(closing) == 1
        and closing not in section(revised, "4.4")
        and hashlib.sha256(closing.encode()).hexdigest() == record["closing_move"]["sha256"]
    )
    for number in ["1.2", "3.5"]:
        checks[f"editorial_both_new_sources_cited_in_{number}"] = all(
            f"[[{reference}]](#ref-{reference})" in section(revised, number)
            for reference in [45, 46]
        )
    checks["editorial_references_1_to_44_unchanged"] = (
        baseline.split("## References\n", 1)[1].split("## Appendix A.", 1)[0].strip()
        == revised.split("## References\n", 1)[1].split('<a id="ref-45">', 1)[0].strip()
    )
    for number in ["3.2", "3.3", "3.4", "3.6"]:
        checks[f"editorial_section_{number}_byte_identical_to_7075b25"] = section(
            revised, number
        ) == section(baseline, number)
    # Check earlier appendix bodies in the actual manuscript as well as the undo image.
    for name in ["OPTION_B_OPERATIONS.json", "OPTION_B_CLOSE_OPERATIONS.json"]:
        previous = json.loads((here / "evidence" / name).read_text())
        checks[f"editorial_{name.removesuffix('.json').lower()}_moves_still_verbatim"] = all(
            appendix(revised, move["appendix"]).count(move["body"]) == 1
            for move in previous["moves"]
        )
    return restored, checks


def check_closing_moves(
    root: Path,
    here: Path,
    revised: str,
    table_parser: Callable[[str], dict[str, list[str]]],
) -> tuple[str, dict[str, bool]]:
    """Undo only the pinned closing operations before checking the older contract."""
    baseline = subprocess.check_output(  # noqa: S603 -- fixed read-only Git arguments
        [
            "/usr/bin/git",
            "show",
            f"{CLOSE_BASELINE}:{PACKAGE}/TrafficTwin_Dissertation.md",
        ],
        cwd=root,
        text=True,
    )
    ledger = (here / "evidence/OPTION_B_CLOSE_OPERATIONS.json").read_bytes()
    record = json.loads(ledger)
    checks = {
        "close_baseline_hash": hashlib.sha256(baseline.encode()).hexdigest()
        == CLOSE_BASELINE_SHA256
        == record["baseline_markdown_sha256"],
        "close_authorised_operation_ledger_hash": hashlib.sha256(ledger).hexdigest()
        == CLOSE_LEDGER_SHA256,
    }
    restored = revised
    reversible = True
    for op in reversed(record["operations"]):
        if not op["new"] or restored.count(op["new"]) != 1:
            reversible = False
            break
        restored = restored.replace(op["new"], op["old"], 1)
    checks["close_only_authorised_moves_trims_and_ethics_confirmation"] = (
        reversible and restored == baseline
    )
    for n in range(2, 7):
        checks[f"close_section_3_{n}_byte_identical_to_2c29392"] = section(
            revised, f"3.{n}"
        ) == section(baseline, f"3.{n}")
    before, after = table_parser(baseline), table_parser(revised)
    checks["close_table_identifiers_only_9_to_a1"] = set(after) == ((set(before) - {"9"}) | {"A1"})
    for number, rows in before.items():
        target = "A1" if number == "9" else number
        checks[f"close_table_{number}_to_{target}_byte_identical"] = rows == after.get(target)
    for i, move in enumerate(record["moves"], 1):
        body = move["body"]
        checks[f"close_move_{i}_verbatim_at_destination"] = (
            body in section(baseline, move["source_section"])
            and appendix(revised, move["appendix"]).count(body) == 1
            and body not in section(revised, move["source_section"])
            and hashlib.sha256(body.encode()).hexdigest() == move["sha256"]
        )
    for i, (source, pointer) in enumerate(
        dict.fromkeys((m["source_section"], m["pointer"]) for m in record["moves"]), 1
    ):
        checks[f"close_pointer_{i}_exactly_once"] = section(revised, source).count(pointer) == 1
    checks["close_no_owner_note_in_manuscript"] = "[Owner note:" not in revised
    checks["close_stakes_name_both_requirement_classes"] = all(
        phrase in section(revised, "1.1")
        for phrase in [
            "100 ms for automated-driving information sharing",
            "500 ms for platooning reporting",
            "clause 5.2, Table 5.2-1",
            "does not validate the simulation",
        ]
    )
    checks["close_ethics_outcome_attributed_and_cited"] = (
        "my University of Manchester Ethics Decision Tool check on 15 September 2026"
        " indicated that ethics approval was not required [[44]](#ref-44)."
    ) in section(revised, "1.4")
    # Current copies of all earlier moves must still exist, not only their undo image.
    prior = json.loads((here / "evidence/OPTION_B_OPERATIONS.json").read_text())
    checks["close_prior_moves_still_verbatim_in_current_appendices"] = all(
        appendix(revised, move["appendix"]).count(move["body"]) == 1 for move in prior["moves"]
    )
    return restored, checks


def check_option_b(
    root: Path,
    here: Path,
    revised: str,
    table_parser: Callable[[str], dict[str, list[str]]],
) -> dict[str, bool]:
    # Each newer, explicitly authorised layer recovers the exact preceding manuscript.
    revised, final_checks = restore_final_pass(root, here, revised)
    historical_counts = json.loads(
        git_bytes(root, FINAL_PASS_BASELINE, PACKAGE + "/document/WORD_COUNT.json")
    )
    revised, platform_checks = restore_platform_connection(
        root, here, revised, historical_counts=historical_counts
    )
    revised, contributions_checks = check_contributions(root, here, revised, table_parser)
    revised, editorial_checks = check_editorial_fixes(root, here, revised, table_parser)
    # The owner authorised only the first-line title change after 10ca7f2.
    # This restoration validates the immutable historical Markdown title decision.
    # The live LaTeX/PDF title is checked separately against PROJECT_TITLE.
    requested_heading = (
        git_bytes(root, FINAL_PASS_BASELINE, PACKAGE + "/TrafficTwin_Dissertation.md")
        .decode()
        .splitlines(keepends=True)[0]
    )
    title_checks = {"title_matches_original_project_name": revised.startswith(requested_heading)}
    if revised.startswith(requested_heading):
        revised = "# " + PREVIOUS_TITLE + "\n" + revised[len(requested_heading) :]
    title_checks["title_revision_preserves_all_other_manuscript_bytes"] = (
        hashlib.sha256(revised.encode()).hexdigest() == PRE_TITLE_MARKDOWN_SHA256
    )
    revised, closing_checks = check_closing_moves(root, here, revised, table_parser)
    baseline = subprocess.check_output(  # noqa: S603 -- fixed read-only Git arguments
        ["/usr/bin/git", "show", f"{BASELINE}:{PACKAGE}/TrafficTwin_Dissertation.md"],
        cwd=root,
        text=True,
    )
    record = json.loads((here / "evidence/OPTION_B_OPERATIONS.json").read_text())
    operations = record["operations"]
    checks = {
        "option_b_baseline_hash": hashlib.sha256(baseline.encode()).hexdigest()
        == BASELINE_SHA256
        == record["baseline_markdown_sha256"],
        "option_b_section_1_2_byte_identical": section(baseline, "1.2") == section(revised, "1.2"),
    }
    # Reverse the recorded, reviewable additions/moves to prove no residual edit.
    restored = revised
    reversible = True
    for op in reversed(operations):
        if not op["new"]:
            # These two paragraph removals share B.2's single source pointer.
            continue
        if restored.count(op["new"]) != 1:
            reversible = False
            break
        restored = restored.replace(op["new"], op["old"], 1)
    # Empty replacements need their exact former location, independent of the log.
    if reversible:
        boundary = "\n\n### 2.8 Cyclic comparator and retrospective measurement design"
        omitted = [op["old"].rstrip("\n") for op in operations if not op["new"]]
        restored = restored.replace(boundary, "\n\n" + "\n\n".join(omitted) + boundary, 1)
    checks["option_b_all_other_source_bytes_preserved"] = reversible and restored == baseline
    tags = {
        op["source"]: op["new"].split("\n\n")[1]
        for op in operations
        if op["kind"] == "objective_tag"
    }
    remark_op = next(op for op in operations if op["kind"] == "addition_remark")
    remark = remark_op["new"].split("\n\n", 1)[1]
    for n in range(2, 7):
        number = f"3.{n}"
        actual = section(revised, number)
        actual = actual.replace(tags[number] + "\n\n", "", 1)
        actual = actual.replace("**Setting.** ", "").replace("**Results.** ", "")
        if n == 2:
            actual = actual.replace("(Section 4.4).", "(Section 4.3).", 1)
        elif n == 4:
            actual = actual.replace(
                "separate fixtures in Appendix D, Table D2.",
                "separate fixtures in Table 8.",
                1,
            )
        elif n == 5:
            actual = actual.replace(remark + "\n\n", "", 1)
        checks[f"option_b_section_{number}_only_explicit_exceptions"] = actual == section(
            baseline, number
        )
    before, after = table_parser(baseline), table_parser(revised)
    for number, rows in before.items():
        target = "D2" if number == "8" and record["overflow_used"] else number
        checks[f"option_b_table_{number}_to_{target}_byte_identical"] = rows == after.get(target)
    for i, move in enumerate(record["moves"], 1):
        body = move["body"]
        checks[f"option_b_move_{i}_baseline_and_appendix_identical"] = (
            body in section(baseline, move["source_section"])
            and appendix(revised, move["appendix"]).count(body) == 1
            and body not in section(revised, move["source_section"])
            and hashlib.sha256(body.encode()).hexdigest() == move["sha256"]
        )
    for i, (source, pointer) in enumerate(
        dict.fromkeys((m["source_section"], m["pointer"]) for m in record["moves"]), 1
    ):
        checks[f"option_b_pointer_{i}_exactly_once"] = section(revised, source).count(pointer) == 1
    checks["option_b_all_seven_objective_tags"] = len(tags) == 7 and all(
        section(revised, number).split("\n\n")[1] == tag
        and len(re.findall(r"\b[\w'-]+\b", tag)) <= 10
        and re.search(r"O[1-5]", tag)
        and re.search(r"RQ[1-3]", tag)
        for number, tag in tags.items()
    )
    checks["option_b_remark_at_most_fifty_words"] = len(re.findall(r"\b[\w'-]+\b", remark)) <= 50
    checks["option_b_additions_present"] = all(
        phrase in revised
        for phrase in [
            "### 4.2 Analysis of the project approach",
            "### 2.9 Method selection and alternatives",
            "**Ethical and professional considerations.**",
            "**Complexity and scope.**",
            "**Execution quality.**",
            "**Challenges.**",
            "[Owner note:",
            "1.19 million",
        ]
    )
    checks["option_b_original_bibliography_unchanged"] = (
        baseline.split("## References\n", 1)[1].split("## Appendix A.", 1)[0].strip()
        == revised.split("## References\n", 1)[1].split('<a id="ref-42">', 1)[0].strip()
    )
    checks["option_b_overflow_only_after_count_failure"] = (
        not record["overflow_used"] or record["before_overflow_counts"]["words"] > 9000
    )
    # The integration base already contains the separately approved platform.
    # Bind only this new document layer to its exact composed predecessor.
    changed = subprocess.check_output(  # noqa: S603 -- fixed read-only Git arguments
        [
            "/usr/bin/git",
            "diff",
            "--name-only",
            PLATFORM_INTEGRATION_BASE,
            FINAL_PASS_BASELINE,
        ],
        cwd=root,
        text=True,
    ).splitlines()
    checks["platform_connection_tracked_changes_within_revision_package"] = all(
        name.startswith(PACKAGE + "/") for name in changed
    )
    checks.update(closing_checks)
    checks.update(title_checks)
    checks.update(editorial_checks)
    checks.update(contributions_checks)
    checks.update(platform_checks)
    checks.update(final_checks)
    return checks


if __name__ == "__main__":
    from validate_revision import tables

    package_dir = Path(__file__).resolve().parents[1]
    result = check_option_b(
        package_dir.parents[2],
        package_dir,
        (package_dir / "TrafficTwin_Dissertation.md").read_text(),
        tables,
    )
    print(json.dumps({"passed": all(result.values()), "checks": result}, indent=2))
    raise SystemExit(0 if all(result.values()) else 1)
