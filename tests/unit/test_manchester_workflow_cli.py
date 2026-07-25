"""Evidence for the Manchester workflow CLI family.

The CLI is how the workflow becomes usable rather than library-only, so its job
is to render the honest state and never to soften it.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from traffictwin.cli import app

runner = CliRunner()


def _invoke(*args: str) -> tuple[int, str]:
    """Run a command, combining streams because refusals go to stderr."""

    result = runner.invoke(app, list(args))
    return result.exit_code, f"{result.stdout}{result.stderr or ''}"


class TestWorkflowStatusCommand:
    def test_it_reports_every_phase(self) -> None:
        code, output = _invoke("integration", "manchester", "workflow", "status")
        assert code == 0
        assert "stages: 13" in output

    def test_it_names_the_blocker_of_each_blocked_stage(self) -> None:
        code, output = _invoke(
            "integration", "manchester", "workflow", "status", "--show", "blocked"
        )
        assert code == 0
        assert "blocked_by:" in output
        assert "lifted_by: owner" in output

    def test_it_never_claims_review_or_approval(self) -> None:
        _code, output = _invoke("integration", "manchester", "workflow", "status")
        assert "analyst_reviewed: false" in output
        assert "supervisor_approved: false" in output
        assert "acceptance_basis: owner_policy_accepted_candidate" in output

    def test_it_keeps_the_capability_and_gates_honest(self) -> None:
        _code, output = _invoke("integration", "manchester", "workflow", "status")
        assert "capability_status: planned" in output
        assert "gate_d: foundation_only" in output
        assert "gate_e: foundation_only" in output

    def test_json_output_carries_the_same_refusals(self) -> None:
        code, output = _invoke(
            "integration", "manchester", "workflow", "status", "--format", "json"
        )
        assert code == 0
        payload = json.loads(output)
        assert payload["capability_status"] == "planned"
        assert payload["supervisor_approved"] is False
        assert payload["performs_network_access"] is False

    def test_an_unknown_show_selector_is_refused(self) -> None:
        code, output = _invoke(
            "integration", "manchester", "workflow", "status", "--show", "everything"
        )
        assert code == 2
        assert "--show must be one of" in output


class TestWorkflowDecisionsCommand:
    def test_it_lists_the_owner_only_decisions(self) -> None:
        code, output = _invoke("integration", "manchester", "workflow", "decisions")
        assert code == 0
        assert "open_owner_decisions: 4" in output
        assert "gridlock" in output
        assert "manual review" in output

    def test_json_output_is_a_plain_list(self) -> None:
        code, output = _invoke(
            "integration", "manchester", "workflow", "decisions", "--format", "json"
        )
        assert code == 0
        assert len(json.loads(output)["open_owner_decisions"]) == 4


class TestTheCliExposesNoUnsafeSurface:
    def test_no_command_accepts_an_executable_or_argument_vector(self) -> None:
        for command in ("status", "decisions"):
            _code, output = _invoke("integration", "manchester", "workflow", command, "--help")
            lowered = output.lower()
            for forbidden in ("--executable", "--argument", "--command", "--shell"):
                assert forbidden not in lowered
