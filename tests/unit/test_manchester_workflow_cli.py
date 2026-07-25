"""Evidence for the Manchester workflow CLI family.

The CLI is how the workflow becomes usable rather than library-only, so its job
is to render the honest state and never to soften it.
"""

from __future__ import annotations

import json
from pathlib import Path

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


class TestMatchPolicyCommand:
    def test_it_shows_the_owner_approved_candidate_policy(self) -> None:
        code, output = _invoke("integration", "manchester", "match", "policy")
        assert code == 0
        assert "policy_id: manchester-dft-map-match-owner-policy-1.1" in output
        assert "research_status: owner_approved_candidate" in output

    def test_it_never_claims_supervisor_approval_or_validation(self) -> None:
        _code, output = _invoke("integration", "manchester", "match", "policy")
        assert "supervisor_approved: false" in output
        assert "scientifically_validated: false" in output

    def test_it_states_that_automatic_acceptance_is_disabled(self) -> None:
        _code, output = _invoke("integration", "manchester", "match", "policy")
        assert "automatic_acceptance_enabled: false" in output

    def test_it_states_that_no_person_reviewed_any_row(self) -> None:
        _code, output = _invoke("integration", "manchester", "match", "policy")
        assert "owner_policy_accepted_candidate" in output
        assert "no analyst, human, or supervisor has reviewed any row" in output

    def test_it_records_what_the_override_may_and_may_not_relax(self) -> None:
        _code, output = _invoke("integration", "manchester", "match", "policy")
        assert "override_relaxes_only: wrong_road_type_family" in output
        assert "override_uses_fuzzy_names: false" in output


class TestObservationSnapshotsCommand:
    def test_an_absent_workspace_refuses_rather_than_reporting_empty(self, tmp_path: Path) -> None:
        # Reporting "0 snapshots" for an invalid workspace would look like a
        # workspace that simply has none.
        code, output = _invoke(
            "integration",
            "manchester",
            "observation",
            "snapshots",
            "--workspace",
            str(tmp_path / "absent"),
        )
        assert code == 1
        assert output.strip()

    def test_it_declares_that_no_request_was_made(self, tmp_path: Path) -> None:
        from traffictwin.release.compatibility import initialise_v07_workspace

        initialise_v07_workspace(tmp_path / "ws")
        code, output = _invoke(
            "integration",
            "manchester",
            "observation",
            "snapshots",
            "--workspace",
            str(tmp_path / "ws"),
        )
        assert code == 0
        assert "network_access_performed: false" in output

    def test_an_empty_workspace_says_so_explicitly(self, tmp_path: Path) -> None:
        from traffictwin.release.compatibility import initialise_v07_workspace

        initialise_v07_workspace(tmp_path / "ws")
        _code, output = _invoke(
            "integration",
            "manchester",
            "observation",
            "snapshots",
            "--workspace",
            str(tmp_path / "ws"),
        )
        assert "acquisition is operator-invoked" in output
