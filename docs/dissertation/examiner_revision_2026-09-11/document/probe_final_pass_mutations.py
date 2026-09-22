"""Require a wrong Table 7a value and a restored deleted sentence to be rejected."""

from __future__ import annotations

import json
from pathlib import Path

from validate_final_pass import DELETIONS, numerical_checks, table_rows


def main() -> None:
    here = Path(__file__).resolve().parents[1]
    root = here.parents[2]
    text = (here / "TrafficTwin_Dissertation.md").read_text()
    baseline = numerical_checks(root, text)
    if not all(baseline.values()):
        raise SystemExit("Unmodified manuscript fails numerical/deletion checks")
    value = table_rows(text, "7a")[0][2]
    table_start = text.index("*Table 7a.")
    value_start = text.index("| " + value + " |", table_start) + 2
    mutated = text[:value_start] + "+9.999" + text[value_start + len(value) :]
    wrong_table = numerical_checks(root, mutated)
    resurrected = numerical_checks(root, text + "\n\n" + DELETIONS["G.4"] + "\n")
    checks = {
        "wrong_table_7a_value_rejected_by_direct_analysis_check": not wrong_table[
            "final_table_7a_seven_rows_match_pinned_all_ten_intervals"
        ],
        "restored_G4_sentence_rejected_by_absence_check": not resurrected[
            "final_deleted_G.4_absent"
        ],
    }
    record = {
        "passed": all(checks.values()),
        "checks": checks,
        "mutations_written_to_manuscript": False,
    }
    (here / "evidence/FINAL_PASS_MUTATION_CHECK_2026-09-16.json").write_text(
        json.dumps(record, indent=2) + "\n"
    )
    print(json.dumps(record, indent=2))
    raise SystemExit(0 if record["passed"] else 1)


if __name__ == "__main__":
    main()
