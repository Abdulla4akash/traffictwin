"""Verify the authorised final pass, then recover the exact published manuscript."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from functools import cache
from pathlib import Path

from validate_exemplar_alignment import baseline_bytes, checks as exemplar_checks, review_pdf_path

PACKAGE = "docs/dissertation/examiner_revision_2026-09-11"
FINAL_PASS_BASELINE = "a8cffe753047c4b7498dded39f61aac3e57f87e4"  # noqa: S105 -- Git identity
FINAL_PASS_BASELINE_SHA256 = "7851287ff2be9307cf3665e42df09a192f13ecb50d670ed2564a6d043948334b"  # noqa: S105 -- SHA-256
FINAL_PASS_LEDGER_SHA256 = "c156ae31df24ccfd1da770f5b83ccb6844c68aac52491043fc6cc0ea7b719107"  # noqa: S105 -- SHA-256
LEDGER = "evidence/FINAL_PASS_OPERATIONS_2026-09-16.json"
FOLLOWUP_SHA = "fe8c8d9e4f725665508e47e61dc6e3286d005450"
TRACE_SHA = "c95e4f86d6dd83207ed3c810826ca48768af8471"
FOLLOWUP_PATH = "docs/dissertation/followups_2026-09-15"
TRACE_PATH = "docs/research/three_traces_2026-09-16"
COUNT_RECEIPT = "evidence/FINAL_FULL_RUN_COUNT_2026-09-16.json"
CAPTURE_RECEIPT = "evidence/FINAL_PLATFORM_CAPTURE_2026-09-16.json"
ADAPTER_RECEIPT = "evidence/TOS_ADAPTER_VALIDATION_2026-09-16.json"
OWNER = {
    "award": "MSc Artificial Intelligence",
    "student_id": "14185028",
    "author": "S M Abdulla Al Mamun",
    "faculty": "Faculty of Science and Engineering",
    "school": "School of Engineering",
    "department": "Department of Computer Science",
}
DELETIONS = {
    "G.4": (
        "Matched conditions support attribution within the evaluator, "
        "while replication defines which uncertainty the intervals address."
    ),
    "G.5": (
        "These difficulties made evidence boundaries and retention part of the method "
        "rather than administrative details."
    ),
    "G.8": (
        "Live admission and immediate reservations protect this older-report model; "
        "stale capacity, delayed acknowledgements or dispersed arrivals would change it."
    ),
    "G.9": (
        "This distinction explains why a source-correct result can be scientifically useful "
        "while remaining conditional on simulation semantics."
    ),
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@cache
def git_bytes(root: Path, commit: str, path: str) -> bytes:
    return subprocess.check_output(  # noqa: S603 -- read-only Git object lookup
        ["/usr/bin/git", "show", f"{commit}:{path}"], cwd=root
    )


def section(text: str, number: str) -> str:
    match = re.search(r"(?ms)^### " + re.escape(number) + r" .*?(?=^### |^## |\Z)", text)
    return match[0] if match else ""


def appendix(text: str, letter: str) -> str:
    match = re.search(r"(?ms)^## Appendix " + letter + r"\. .*?(?=^## Appendix |\Z)", text)
    return match[0] if match else ""


def table_rows(text: str, number: str) -> list[list[str]]:
    match = re.search(r"(?ms)^\*Table " + re.escape(number) + r"\. .*?\n\n((?:\|[^\n]*\n?)+)", text)
    return (
        [list(map(str.strip, row.strip("|").split("|"))) for row in match[1].splitlines()][2:]
        if match
        else []
    )


def signed(value: float) -> str:
    return f"{value:+.3f}".replace("-", "−")


def expected_row(label: str, contrast: str, values: dict) -> list[str]:
    return [
        label,
        contrast,
        signed(values["mean_pp"]),
        f"[{signed(values['low_pp'])}, {signed(values['high_pp'])}]",
    ]


def numerical_checks(root: Path, revised: str) -> dict[str, bool]:
    """Compute expected displayed cells from immutable analysis objects, not the ledger."""
    followup = json.loads(git_bytes(root, FOLLOWUP_SHA, FOLLOWUP_PATH + "/ANALYSIS.json"))
    traces = json.loads(git_bytes(root, TRACE_SHA, TRACE_PATH + "/ANALYSIS.json"))
    specifications = [
        ("07_two_choice", "per_task_minus_two_choice", "7", "Per-task − two-choice"),
        ("07_two_choice", "two_choice_minus_ingress", "7", "Two-choice − ingress"),
        (
            "07_two_choice",
            "two_choice_minus_round_robin",
            "7",
            "Two-choice − round-robin",
        ),
        (
            "08_half_speed",
            "per_task_dla_minus_causal_round_robin",
            "8",
            "Per-task − round-robin at half speed",
        ),
        (
            "08_half_speed",
            "change_in_per_task_minus_round_robin_gap",
            "8",
            "Change in per-task − round-robin gap",
        ),
        (
            "09_second_actor",
            "per_task_dla_minus_ingress_dla",
            "9",
            "Per-task − ingress",
        ),
        (
            "09_second_actor",
            "per_task_dla_minus_causal_round_robin",
            "9",
            "Per-task − round-robin",
        ),
    ]
    expected_a = []
    for study, contrast, label, description in specifications:
        row = next(
            x for x in followup["contrasts"] if x["study"] == study and x["contrast"] == contrast
        )
        expected_a.append(expected_row(label, description, row["all_ten_family95"]))
    expected_b = []
    for trace, label in [
        ("we", "Weekend"),
        ("wd_pm", "PM peak"),
        ("ev", "Event night"),
    ]:
        for contrast, description in [
            ("per_task_dla_minus_ingress_dla", "Per-task − ingress"),
            ("dla_minus_ingress_dla", "Common-target − ingress"),
            ("per_task_dla_minus_causal_round_robin", "Per-task − round-robin"),
            ("per_task_dla_minus_dla_p2c", "Per-task − two-choice"),
        ]:
            row = next(
                x for x in traces["contrasts"] if x["trace"] == trace and x["contrast"] == contrast
            )
            expected_b.append(expected_row(label, description, row["all_fifteen_family95"]))
    checks = {
        "final_table_7a_seven_rows_match_pinned_all_ten_intervals": table_rows(revised, "7a")
        == expected_a,
        "final_table_7b_twelve_rows_match_pinned_all_fifteen_intervals": table_rows(revised, "7b")
        == expected_b,
        "final_original_and_new_interval_families_separate": all(
            phrase in section(revised, "3.4")
            for phrase in [
                "post-hoc",
                "ten-contrast",
                "All-fifteen",
                "no pooling or cross-trace test",
            ]
        ),
    }
    checks.update(
        {f"final_deleted_{item}_absent": body not in revised for item, body in DELETIONS.items()}
    )
    return checks


def run_count_checks(root: Path, here: Path, revised: str) -> dict[str, bool]:
    record = json.loads((here / COUNT_RECEIPT).read_text())
    rows = record["runs"]
    groups = Counter(row["group"] for row in rows)
    old_count = json.loads((here / "evidence/CONTRIBUTIONS_RUN_COUNT_2026-09-15.json").read_text())
    old_rows = [run for group in old_count["components"] for run in group["runs"]]
    old_hashes = {run["original_summary_sha256"] for run in old_rows}
    new_receipts = []
    for row in rows:
        if row["group"] not in ("followups_7_9", "traces_10_12"):
            continue
        commit = FOLLOWUP_SHA if row["group"] == "followups_7_9" else TRACE_SHA
        # Absolute paths in the historical counting receipt are locators, never dependencies.
        relative = "docs/" + row["receipt"].split("docs/", 1)[1]
        raw = git_bytes(root, commit, relative)
        source = json.loads(raw)
        new_receipts.append(
            digest(raw) == row["receipt_sha256"]
            and source["status"] == "passed"
            and source["configuration"]["steps"] == row["observed_horizon"] > 300
            and all(
                source["configuration"][key] == value for key, value in row["configuration"].items()
            )
            and source["output_sha256"]["summary.json"] == row["original_summary_sha256"]
        )
    abstract = revised.split("## Abstract\n", 1)[1].split("## 1.", 1)[0]
    scale = (
        "The programme evaluated seven infrastructure policies in "
        f"{record['total_distinct_full_runs']} full evaluator runs "
        "across five Manchester scenarios, "
        "with the confirmation and follow-up studies under protocols sealed before outcomes."
    )
    return {
        "final_full_run_inventory_counts_distinct_executions": (
            len(rows)
            == len({row["original_summary_sha256"] for row in rows})
            == record["total_distinct_full_runs"]
            == 274
            and groups["followups_7_9"] == record["new_followup_full_runs"] == 72
            and groups["traces_10_12"] == record["new_three_trace_full_runs"] == 120
            and record["initial_distinct_full_run_records"] == len(old_hashes) == 82
            and {
                row["original_summary_sha256"]
                for row in rows
                if row["group"] not in ("followups_7_9", "traces_10_12")
            }
            == old_hashes
        ),
        "final_all_192_new_full_run_receipts_match_fixed_git_objects": len(new_receipts) == 192
        and all(new_receipts),
        "final_initial_count_receipt_preserved": digest(
            (here / "evidence/CONTRIBUTIONS_RUN_COUNT_2026-09-15.json").read_bytes()
        )
        == record["previous_count_receipt_sha256"],
        "final_abstract_full_scale_sentence_once": abstract.count(scale) == 1
        and "initial programme" not in abstract,
        "final_seven_policies_and_five_scenarios_in_count_receipt": set(record["seven_policies"])
        == {
            "off",
            "jsq",
            "dla",
            "ingress_dla",
            "per_task_dla",
            "causal_round_robin",
            "dla_p2c",
        }
        and set(record["five_scenarios"])
        == {"incident", "morning", "weekend", "PM peak", "event night"},
        "final_C5_and_ownership_remain_initial_programme": (
            "Designing and executing the initial comparison of six infrastructure policies"
        )
        in section(revised, "1.3")
        and "more than eighty full evaluator runs" in section(revised, "1.3")
        and (
            "I designed the research questions and the initial evaluation experiments "
            "in this report:"
        )
        in section(revised, "3.7"),
    }


def restore_final_pass(root: Path, here: Path, revised: str) -> tuple[str, dict[str, bool]]:
    """Reverse only the hash-bound operation ledger before all older protection layers."""
    baseline_raw = git_bytes(root, FINAL_PASS_BASELINE, PACKAGE + "/TrafficTwin_Dissertation.md")
    baseline = baseline_raw.decode()
    ledger_raw = (here / LEDGER).read_bytes()
    ledger = json.loads(ledger_raw)
    checks = {
        "final_pass_baseline_is_exact_published_a8cffe7": ledger.get(
            "baseline", ledger.get("baseline_commit")
        )
        == FINAL_PASS_BASELINE
        and digest(baseline_raw)
        == FINAL_PASS_BASELINE_SHA256
        == ledger["baseline_markdown_sha256"],
        "final_pass_authorised_operation_ledger_hash": digest(ledger_raw)
        == FINAL_PASS_LEDGER_SHA256,
        "final_pass_owner_word_count_stop_waiver_recorded": ledger.get("word_count_stop_waived")
        is True,
        "final_pass_all_nine_fallback_steps_reported": ledger.get("fallback_steps_used")
        == [f"G.{n}" for n in range(1, 10)],
    }
    restored = revised
    reversible = True
    for operation in reversed(ledger["operations"]):
        if not operation["new"] or restored.count(operation["new"]) != 1:
            reversible = False
            break
        restored = restored.replace(operation["new"], operation["old"], 1)
    checks["final_pass_only_owner_authorised_source_operations"] = (
        reversible and restored == baseline
    )
    required_receipts = {COUNT_RECEIPT, CAPTURE_RECEIPT, ADAPTER_RECEIPT}
    pins = ledger.get("receipt_sha256", {})
    checks["final_pass_required_receipts_pinned_by_ledger"] = required_receipts <= set(pins)
    for path, expected in pins.items():
        target = here / path
        checks["final_pinned_" + path] = (
            target.is_file()
            and digest(
                baseline_bytes(here, path)
                if path
                in {
                    CAPTURE_RECEIPT,
                    "assets/traffictwin_platform_real_data.pdf",
                    "assets/traffictwin_platform_real_data.png",
                }
                else target.read_bytes()
            )
            == expected
        )
    # Existing scientific table bodies remain exact except the three explicitly amended tables.
    before_ids = re.findall(r"(?m)^\*Table ([A-F]?\d+[a-z]?)\.", baseline)
    after_ids = re.findall(r"(?m)^\*Table ([A-F]?\d+[a-z]?)\.", revised)
    checks["final_only_tables_7a_and_7b_added"] = (
        set(after_ids) == set(before_ids) | {"7a", "7b"} and len(after_ids) == len(before_ids) + 2
    )
    for number in before_ids:
        if number not in {"3a", "8", "9", "A1"}:
            checks[f"final_table_{number}_body_preserved"] = table_rows(
                revised, number
            ) == table_rows(baseline, number)
    for prefix, source, destination in [
        ("E1 varied waiting-room capacity", "3.1", "B"),
        ("The saved secondary summaries report", "3.1", "B"),
        ("Changing the off scoring mask", "3.1", "B"),
        ("Four ten-step forwarding probes", "2.7", "F"),
    ]:
        body = next(
            paragraph
            for paragraph in section(baseline, source).split("\n\n")
            if paragraph.startswith(prefix)
        )
        checks["final_verbatim_move_" + prefix.replace(" ", "_")] = revised.count(body) == appendix(
            revised, destination
        ).count(body) == 1 and body not in section(revised, source)
    g3 = (
        "A further 104 forwarded tasks had penalty-equal latency ambiguity but were already "
        "misses and remained misses under every nonnegative charge. "
        "Their latency ambiguity remains unresolved."
    )
    checks["final_G3_two_sentences_moved_together_verbatim_to_F"] = (
        g3 in section(baseline, "3.6")
        and revised.count(g3) == appendix(revised, "F").count(g3) == 1
        and g3 not in section(revised, "3.6")
    )
    references = revised.split("## References\n", 1)[1].split("## Appendix A.", 1)[0]
    original_references = baseline.split("## References\n", 1)[1].split("## Appendix A.", 1)[0]
    checks["final_references_1_to_46_exact_and_ref47_once"] = (
        references.split('<a id="ref-47">', 1)[0].strip() == original_references.strip()
        and references.count('<a id="ref-47"></a>') == references.count("[47] R. P. Putra") == 1
        and "DOI pending in the camera-ready copy" in references
    )
    checks["final_ref47_provenance_in_1_1_and_2_3"] = all(
        "[[47]](#ref-47)" in section(revised, number) for number in ("1.1", "2.3")
    )
    checks["final_sealing_and_Claude_attribution_scoped"] = (
        "Claude (Anthropic) proposed the three follow-up conditions and the three-trace study"
        in revised
        and "I designed the initial study and its evaluation experiments," in revised
        and (
            "The follow-up conditions were proposed as described in the Declaration; "
            "I authorised and reviewed them."
        )
        in section(revised, "3.7")
    )
    checks["final_stale_two_choice_and_global_actor_wording_absent"] = all(
        phrase not in revised
        for phrase in [
            "Two-choice spreading not evaluated",
            "the two-choice mode remains the first comparator to add",
            "The same archived one-hot-17 checkpoint is used throughout.",
            "One archived MAPPO checkpoint and one device-tier preset are fixed throughout;",
        ]
    )
    main_sha = ledger.get("study_source_sha", ledger["main_sha"])
    checks["final_S19_analysis_matches_owner_selected_source_object"] = git_bytes(
        root, main_sha, TRACE_PATH + "/ANALYSIS.json"
    ) == git_bytes(root, TRACE_SHA, TRACE_PATH + "/ANALYSIS.json")
    checks["final_sources_link_exact_analysis_commits"] = (
        f"/blob/{FOLLOWUP_SHA}/{FOLLOWUP_PATH}/ANALYSIS.json" in revised
        and f"/blob/{main_sha}/{TRACE_PATH}/ANALYSIS.json" in revised
    )
    changed = subprocess.check_output(  # noqa: S603 -- read-only change inventory
        ["/usr/bin/git", "diff", "--name-only", ledger["integration_baseline"]],
        cwd=root,
        text=True,
    ).splitlines()
    checks["final_tracked_changes_within_revision_package"] = all(
        name.startswith(PACKAGE + "/") for name in changed
    )
    checks.update(numerical_checks(root, revised))
    checks.update(run_count_checks(root, here, revised))
    return restored, checks


def artifact_checks(here: Path, revised: str) -> dict[str, bool]:
    """Check generated front matter and authentic Figure 7 bindings separately from source."""
    import fitz

    ledger = json.loads((here / LEDGER).read_text())
    capture = json.loads((here / CAPTURE_RECEIPT).read_text())
    adapter = json.loads((here / ADAPTER_RECEIPT).read_text())
    checks = {
        "final_capture_three_authentic_panels_no_new_research": capture["all_three_panels_captured"]
        is True
        and capture["source_commit"] == "17d6b21c7228910a911d66879a1c6e11ae445eb2"
        and capture["research_workloads_launched"] == 0
        and capture["browser_errors"] == []
        and capture["embed"] is True
        and capture["viewport_css"] == [1440, 3000]
        and capture["dpi"] == 300,
        "final_adapter_inventory_and_fingerprint": adapter["may_import_summaries"] is True
        and adapter["package_fingerprint"] == capture["package_fingerprint"]
        and adapter["engine_versions"] == ["v2_post_nrsus_fix"]
        and all(
            adapter["inventory"][key] == value
            for key, value in {
                "evaluation_rows": 300,
                "perstep_files": 60,
                "pertask_files": 6,
                "trace_files": 5,
                "training_csv_files": 66,
            }.items()
        ),
        "final_figure7_asset_and_external_evidence_caption": (
            "(assets/traffictwin_platform_real_data.pdf)" in revised
        )
        and all(
            phrase in revised
            for phrase in [
                "(a) An external evaluation package",
                "(b) That package's 300 evaluation runs",
                "(c) This dissertation's sealed eight-block contrasts",
                "not as results of this dissertation",
                "traffictwin integration tos",
            ]
        ),
    }
    defaults = {
        "traffictwin_platform_real_data.pdf": "assets/traffictwin_platform_real_data.pdf",
        "traffictwin_platform_real_data.png": "assets/traffictwin_platform_real_data.png",
        "TOS_ADAPTER_VALIDATION.json": ADAPTER_RECEIPT,
    }
    locations = defaults | ledger.get("capture_files", {})
    for filename, expected in capture["files"].items():
        path = here / (
            filename
            if filename.startswith(("assets/", "evidence/"))
            else locations.get(filename, "evidence/final_capture/" + filename)
        )
        checks["final_capture_file_" + filename] = (
            path.is_file() and digest(path.read_bytes()) == expected
        )
    tex = (here / "TrafficTwin_Dissertation.tex").read_text()
    pdf = fitz.open(review_pdf_path(here))
    cover = " ".join(pdf[0].get_text().split())
    checks["final_title_page_values_in_tex_and_pdf"] = all(
        value in tex and value in cover for key, value in OWNER.items() if key != "award"
    )
    checks["exemplar_expanded_award_on_cover"] = (
        "Master of Science in Artificial Intelligence" in cover
    )
    checks.update(exemplar_checks(here))
    checks["final_pdf_metadata_owner"] = pdf.metadata["author"] == OWNER["author"]
    pdf_text = " ".join(" ".join(page.get_text().split()) for page in pdf)
    checks["final_pdf_both_new_tables_present"] = (
        "Table 7a:" in pdf_text and "Table 7b:" in pdf_text
    )
    checks["final_standard_declaration_present"] = (
        "No portion of the work referred to in the dissertation has been submitted in support "
        "of an application for another degree or qualification of this or any other university "
        "or other institute of learning."
    ) in revised
    return checks


def main() -> None:
    here = Path(__file__).resolve().parents[1]
    revised = (here / "TrafficTwin_Dissertation.md").read_text()
    _, checks = restore_final_pass(here.parents[2], here, revised)
    checks.update(artifact_checks(here, revised))
    record = {
        "checks": checks,
        "passed": all(checks.values()),
        "scope": "Historical Markdown guards plus the hash-bound LaTeX exemplar overlay; review PDF is a local build only.",
        "review_pdf": str(review_pdf_path(here)),
    }
    (here / "evidence/FINAL_PASS_VALIDATION_2026-09-16.json").write_text(
        json.dumps(record, indent=2) + "\n"
    )
    print(json.dumps(record, indent=2))
    raise SystemExit(0 if record["passed"] else 1)


if __name__ == "__main__":
    main()
