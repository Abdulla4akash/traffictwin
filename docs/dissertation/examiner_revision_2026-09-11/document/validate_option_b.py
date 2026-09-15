"""Bind Option B preservation checks to the owner's exact Git baseline."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Callable
from pathlib import Path

BASELINE = "9b49efc34a482e5abaab804efcd857b368087c52"
PACKAGE = "docs/dissertation/examiner_revision_2026-09-11"
BASELINE_SHA256 = "1f9b0280010cb13e622678e71122296e7360f649e517496559c98303cd086ced"


def section(text: str, number: str) -> str:
    start = re.search(r"(?m)^### " + re.escape(number) + r" .*$", text)
    assert start, number
    end = re.search(r"(?m)^#{2,3} ", text[start.end() :])
    return text[start.start() : start.end() + end.start() if end else len(text)]


def appendix(text: str, letter: str) -> str:
    tail = text.split("## Appendix " + letter + ". ", 1)[1]
    return tail.split("\n## Appendix ", 1)[0]


def check_option_b(
    root: Path, here: Path, revised: str, table_parser: Callable[[str], dict[str, list[str]]]
) -> dict[str, bool]:
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
                "separate fixtures in Appendix D, Table D2.", "separate fixtures in Table 8.", 1
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
    changed = subprocess.check_output(  # noqa: S603 -- fixed read-only Git arguments
        ["/usr/bin/git", "diff", "--name-only", BASELINE], cwd=root, text=True
    ).splitlines()
    checks["option_b_tracked_changes_within_revision_package"] = all(
        name.startswith(PACKAGE + "/") for name in changed
    )
    return checks
