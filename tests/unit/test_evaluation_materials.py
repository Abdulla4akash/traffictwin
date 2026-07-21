from __future__ import annotations

import json
from pathlib import Path


def test_evaluation_kit_is_draft_and_schema_excludes_direct_identifiers() -> None:
    directory = Path("docs/evaluation")
    expected = {
        "README.md",
        "ethics_application_draft.md",
        "participant_task_script.md",
        "survey.md",
        "interview_guide.md",
        "consent_and_privacy.md",
        "anonymised_result_schema.json",
    }

    assert expected <= {path.name for path in directory.iterdir()}
    schema = json.loads((directory / "anonymised_result_schema.json").read_text(encoding="utf-8"))
    properties = set(schema["properties"])
    assert not properties & {"name", "email", "student_id", "staff_id", "ip_address"}
    assert schema["additionalProperties"] is False
    assert "not submitted and not approved" in (
        directory / "ethics_application_draft.md"
    ).read_text(encoding="utf-8")
