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


class TestObservationAcquireIsOperatorInvoked:
    def test_it_refuses_without_confirmation(self, tmp_path: Path) -> None:
        # Acquisition performs a real request; it must never be a side effect.
        code, output = _invoke(
            "integration",
            "manchester",
            "observation",
            "acquire",
            "--workspace",
            str(tmp_path),
            "--dataset",
            "raw_counts",
        )
        assert code == 2
        assert "--confirm" in output

    def test_it_refuses_an_unknown_dataset(self, tmp_path: Path) -> None:
        code, output = _invoke(
            "integration",
            "manchester",
            "observation",
            "acquire",
            "--workspace",
            str(tmp_path),
            "--dataset",
            "everything",
        )
        assert code == 2
        assert "count_points or raw_counts" in output

    def test_an_unknown_dataset_is_refused_before_confirmation_matters(
        self, tmp_path: Path
    ) -> None:
        # The dataset check must not be reachable only after --confirm, or a
        # typo plus a confirm would still reach the provider.
        code, _output = _invoke(
            "integration",
            "manchester",
            "observation",
            "acquire",
            "--workspace",
            str(tmp_path),
            "--dataset",
            "everything",
            "--confirm",
        )
        assert code == 2


class TestRunPreflight:
    def test_it_reports_the_frozen_step_and_fcd_period(self) -> None:
        code, output = _invoke("integration", "manchester", "run", "preflight")
        assert code == 0
        assert "step_length_s: 1" in output
        assert "fcd_period_s: 1" in output

    def test_it_warns_that_the_current_demand_gridlocks(self) -> None:
        _code, output = _invoke("integration", "manchester", "run", "preflight")
        assert "gridlocks" in output

    def test_json_output_is_machine_readable(self) -> None:
        code, output = _invoke("integration", "manchester", "run", "preflight", "--format", "json")
        assert code == 0
        assert "sumo_available" in json.loads(output)


class TestTheReviewQueueCannotBeCleared:
    def test_no_accept_or_reject_option_exists(self) -> None:
        # Policy 1.1 requires a person for every unaccepted row. A command that
        # could clear the queue would let an agent stand in for one.
        _code, output = _invoke("integration", "manchester", "match", "review", "--help")
        lowered = output.lower()
        for forbidden in ("--accept", "--reject", "--approve", "--bulk", "--auto"):
            assert forbidden not in lowered

    def test_the_candidates_command_offers_no_acceptance_either(self) -> None:
        _code, output = _invoke("integration", "manchester", "match", "candidates", "--help")
        lowered = output.lower()
        for forbidden in ("--accept", "--approve", "--auto"):
            assert forbidden not in lowered


class TestEvidenceExportIsPermissionSafe:
    def test_it_exports_only_aggregate_records(self, tmp_path: Path) -> None:
        code, output = _invoke(
            "integration",
            "manchester",
            "evidence",
            "export",
            "--destination",
            str(tmp_path / "out"),
        )
        assert code == 0
        assert "raw_artifacts_included: false" in output
        exported = list((tmp_path / "out").glob("*"))
        assert exported, "at least one aggregate record should export"
        assert all(item.suffix == ".json" for item in exported)

    def test_no_raw_or_large_artifact_is_exported(self, tmp_path: Path) -> None:
        _invoke(
            "integration",
            "manchester",
            "evidence",
            "export",
            "--destination",
            str(tmp_path / "out"),
        )
        for item in (tmp_path / "out").glob("*"):
            assert not item.name.endswith((".rou.xml", ".net.xml", ".osm.xml", ".osm.pbf"))

    def test_nothing_exported_carries_a_private_path(self, tmp_path: Path) -> None:
        _invoke(
            "integration",
            "manchester",
            "evidence",
            "export",
            "--destination",
            str(tmp_path / "out"),
        )
        for item in (tmp_path / "out").glob("*.json"):
            text = item.read_text(encoding="utf-8")
            assert "/Users/" not in text
            assert "/private/" not in text


class TestEvidenceLineage:
    def test_it_reports_the_comparison_contract_as_unregistered(self, tmp_path: Path) -> None:
        from traffictwin.release.compatibility import initialise_v07_workspace

        initialise_v07_workspace(tmp_path / "ws")
        code, output = _invoke(
            "integration",
            "manchester",
            "evidence",
            "lineage",
            "--workspace",
            str(tmp_path / "ws"),
        )
        assert code == 0
        assert "registered: false" in output

    def test_an_unbound_chain_says_so_rather_than_looking_short(self, tmp_path: Path) -> None:
        from traffictwin.release.compatibility import initialise_v07_workspace

        initialise_v07_workspace(tmp_path / "ws")
        _code, output = _invoke(
            "integration",
            "manchester",
            "evidence",
            "lineage",
            "--workspace",
            str(tmp_path / "ws"),
        )
        assert "the chain starts unbound" in output

    def test_it_makes_no_request(self, tmp_path: Path) -> None:
        from traffictwin.release.compatibility import initialise_v07_workspace

        initialise_v07_workspace(tmp_path / "ws")
        _code, output = _invoke(
            "integration",
            "manchester",
            "evidence",
            "lineage",
            "--workspace",
            str(tmp_path / "ws"),
        )
        assert "network_access_performed: false" in output


class TestDemandBuildLabelsItsProduct:
    def test_help_states_it_is_a_count_target_not_a_simulation(self) -> None:
        _code, output = _invoke("integration", "manchester", "demand", "build", "--help")
        assert "count target" in output.lower() or "route sampling is a separate" in output.lower()

    def test_no_option_runs_a_simulation(self) -> None:
        _code, output = _invoke("integration", "manchester", "demand", "build", "--help")
        lowered = output.lower()
        for forbidden in ("--simulate", "--run-sumo", "--sample"):
            assert forbidden not in lowered
