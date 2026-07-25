"""Evidence for the read-only Manchester workflow status view.

The point of this view is that an unavailable stage stays visible. A reader who
scrolls past a missing stage has been misled as surely as one shown a wrong
number, so the model refuses a blocked stage that does not say why.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester import workflow_service
from traffictwin.integration.manchester.workflow_service import (
    OPEN_OWNER_DECISIONS,
    ManchesterWorkflowStatus,
    WorkflowStage,
    manchester_workflow_status,
)


class TestTheServiceIsReadOnlyAndOffline:
    def test_it_performs_no_network_or_subprocess_work(self) -> None:
        status = manchester_workflow_status()
        assert status.performs_network_access is False
        assert status.performs_subprocess_execution is False

    def test_the_module_imports_no_transport_or_subprocess(self) -> None:
        source = Path(workflow_service.__file__).read_text(encoding="utf-8")
        assert "import subprocess" not in source
        assert "import httpx" not in source

    def test_a_workspace_argument_does_not_cause_a_probe(self, tmp_path: Path) -> None:
        # Accepting a path must not mean touching it.
        assert manchester_workflow_status(tmp_path / "absent").stages


class TestUnavailableStatesStayVisible:
    def test_every_blocked_stage_states_its_blocker(self) -> None:
        for stage in manchester_workflow_status().blocked_stages:
            assert stage.blocker, f"{stage.key} is blocked without a stated reason"

    def test_a_blocked_stage_without_a_blocker_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="must state its blocker"):
            WorkflowStage(key="x", phase=7, title="X", state="blocked_on_missing_artifact")

    def test_a_decision_blocker_must_name_who_lifts_it(self) -> None:
        with pytest.raises(ValidationError, match="name who can lift it"):
            WorkflowStage(
                key="x",
                phase=7,
                title="X",
                state="blocked_on_owner_decision",
                blocker="something",
            )

    def test_an_available_stage_cannot_carry_a_blocker(self) -> None:
        with pytest.raises(ValidationError, match="cannot carry a blocker"):
            WorkflowStage(key="x", phase=1, title="X", state="available", blocker="something")

    def test_every_phase_from_one_to_thirteen_is_represented(self) -> None:
        # A phase that is simply absent reads as though it does not exist.
        phases = {stage.phase for stage in manchester_workflow_status().stages}
        assert phases == set(range(1, 14))


class TestOwnerDecisionsAreSurfaced:
    def test_a_decision_blocked_stage_requires_the_decision_listed(self) -> None:
        payload: dict[str, Any] = json.loads(manchester_workflow_status().canonical_json())
        payload["open_owner_decisions"] = []
        with pytest.raises(ValidationError, match="requires that decision to be listed"):
            ManchesterWorkflowStatus.model_validate_json(json.dumps(payload))

    def test_the_four_open_decisions_are_reported(self) -> None:
        assert len(OPEN_OWNER_DECISIONS) == 4
        assert manchester_workflow_status().open_owner_decisions == OPEN_OWNER_DECISIONS

    def test_the_gridlock_and_review_blockers_are_named(self) -> None:
        joined = " ".join(manchester_workflow_status().open_owner_decisions)
        assert "gridlock" in joined
        assert "manual review" in joined


class TestCapabilityTruthIsNotAdvanced:
    def test_the_capability_and_gates_stay_where_the_evidence_puts_them(self) -> None:
        status = manchester_workflow_status()
        assert status.capability_status == "planned"
        assert status.gate_d_state == "foundation_only"
        assert status.gate_e_state == "foundation_only"

    def test_no_row_is_described_as_reviewed_or_approved(self) -> None:
        status = manchester_workflow_status()
        assert status.acceptance_basis == "owner_policy_accepted_candidate"
        assert status.analyst_reviewed is False
        assert status.human_accepted is False
        assert status.supervisor_approved is False
        assert status.scientifically_validated is False

    def test_a_forged_supervisor_approval_is_refused(self) -> None:
        payload: dict[str, Any] = json.loads(manchester_workflow_status().canonical_json())
        payload["supervisor_approved"] = True
        with pytest.raises(ValidationError):
            ManchesterWorkflowStatus.model_validate_json(json.dumps(payload))

    def test_a_forged_analyst_review_is_refused(self) -> None:
        payload: dict[str, Any] = json.loads(manchester_workflow_status().canonical_json())
        payload["analyst_reviewed"] = True
        with pytest.raises(ValidationError):
            ManchesterWorkflowStatus.model_validate_json(json.dumps(payload))
