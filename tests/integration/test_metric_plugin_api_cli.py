from __future__ import annotations

import json

from typer.testing import CliRunner

from traffictwin.cli import app


def test_metric_plugin_api_cli_exposes_machine_readable_trust_boundary() -> None:
    result = CliRunner().invoke(app, ["metrics", "plugin-api", "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "1.0"
    assert payload["registration_mode"] == "explicit_trusted_in_process"
    assert payload["determinism_verification_runs"] == 2
    assert payload["execution_failure_policy"] == "isolate_as_unavailable"
    assert payload["uploaded_code_execution"] is False
    assert payload["sandboxed_execution"] is False
    assert payload["supported_tables"] == [
        "tasks",
        "infrastructure",
        "vehicles",
        "traffic",
        "trips",
        "incidents",
    ]

    text = CliRunner().invoke(app, ["metrics", "plugin-api", "--format", "text"])
    assert text.exit_code == 0
    assert "registration_mode: explicit_trusted_in_process" in text.stdout
    assert "dynamic_file_import: false" in text.stdout
