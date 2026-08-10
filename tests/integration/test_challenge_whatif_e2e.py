"""End-to-end probe: Portfolio → What-If → Generate → Compare wiring.

Proves handoff, ledger, generation, session wiring; real form paths are
tested in UI suite. This keeps service-level E2E for direct generation (valid
for bridge service) separate from AppTest form E2E.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from traffictwin.synthetic.whatif_pair import WhatIfPairRequest, WhatIfVariationOverrides
from traffictwin.ui.challenge_whatif_bridge import build_challenge_whatif_draft
from traffictwin.ui.portfolio_explorer import get_challenge_seed
from traffictwin.ui.services.whatif_pair import (
    generate_whatif_pair_for_ui,
    preview_whatif_ledger_for_ui,
)


def _draft_overrides_to_request(draft: object) -> WhatIfPairRequest:
    ov = draft.whatif_overrides  # type: ignore[attr-defined]
    overrides = WhatIfVariationOverrides(
        incident_enabled=ov.get("incident_enabled"),
        incident_type=ov.get("incident_type"),
        incident_location=ov.get("incident_location"),
        incident_start_s=ov.get("incident_start_s"),
        incident_duration_s=ov.get("incident_duration_s"),
        lanes_closed=ov.get("lanes_closed"),
        event_demand_multiplier=ov.get("event_demand_multiplier"),
        congestion_multiplier=ov.get("congestion_multiplier"),
        vehicle_count=ov.get("vehicle_count"),
        task_arrival_rate=ov.get("task_arrival_rate"),
        task_mix_t1=ov.get("task_mix_t1"),
        task_mix_t2=ov.get("task_mix_t2"),
        task_mix_t3=ov.get("task_mix_t3"),
        rsu_count=ov.get("rsu_count"),
        rsu_capacity=ov.get("rsu_capacity"),
        random_seed=ov.get("random_seed"),
    )
    return WhatIfPairRequest(
        baseline_preset="baseline",
        pair_name=f"e2e-{draft.challenge_id.lower()}",  # type: ignore[attr-defined]
        experiment_id="exp-whatif-e2e",
        baseline_random_seed=ov.get("random_seed", 7)
        if isinstance(ov.get("random_seed"), int)
        else 7,
        variation_overrides=overrides,
    )


def test_e2e_portfolio_to_whatif_to_pair() -> None:
    challenge = get_challenge_seed("CH-01-arena-surge")
    assert challenge is not None
    draft = build_challenge_whatif_draft(challenge)
    assert len(draft.supported_fields) >= 1
    ov = draft.whatif_overrides
    assert ov.get("congestion_multiplier") == 2.2
    assert ov.get("task_arrival_rate") == 0.16
    assert ov.get("incident_type") == "stadium_event"

    request = _draft_overrides_to_request(draft)
    ledger = preview_whatif_ledger_for_ui(request)
    from traffictwin.ui.services.models import ServiceError

    assert not isinstance(ledger, ServiceError), f"ledger error: {ledger}"
    assert len(ledger) >= 1
    paths = {p.field_path for p in ledger}
    assert "congestion_multiplier" in paths
    assert "task_arrival_rate" in paths

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        workspace = tmp_path / "ws"
        registry = workspace / "registry.sqlite"
        workspace.mkdir(parents=True, exist_ok=True)
        result = generate_whatif_pair_for_ui(
            request, registry_path=registry, workspace_path=workspace
        )
        assert not isinstance(result, ServiceError), f"generate error: {result}"
        assert result.status in ("ok", "already_exists")
        assert result.baseline_bundle_path is not None
        assert result.variation_bundle_path is not None
        assert Path(result.baseline_bundle_path).exists()
        assert Path(result.variation_bundle_path).exists()
        assert len(result.changed_parameters) >= 1
        assert draft.mapping_status.value in (
            "FULLY_MAPPABLE",
            "PARTIALLY_MAPPABLE",
            "NOT_MAPPABLE",
        )
        ch04 = get_challenge_seed("CH-04-rsu-waiting-room-squeeze")
        assert ch04 is not None
        d04 = build_challenge_whatif_draft(ch04)
        assert len(d04.unsupported_fields) >= 1
        assert any("Only the supported subset will be prefilled" in w for w in d04.warnings)
        assert d04.fingerprint


def test_e2e_partially_mappable_pair_wording() -> None:
    challenge = get_challenge_seed("CH-02-lane-closure-corridor")
    assert challenge is not None
    draft = build_challenge_whatif_draft(challenge)
    assert draft.mapping_status.value == "PARTIALLY_MAPPABLE"
    assert len(draft.unsupported_fields) == 1
    assert draft.unsupported_fields[0].challenge_path == "infrastructure.rsu_capacity_mode"
    request = _draft_overrides_to_request(draft)
    assert request.variation_overrides.rsu_capacity is None
    assert request.variation_overrides.congestion_multiplier == 1.1
    assert request.variation_overrides.lanes_closed == 2

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        workspace = tmp_path / "ws"
        registry = workspace / "registry.sqlite"
        workspace.mkdir(parents=True, exist_ok=True)
        result = generate_whatif_pair_for_ui(
            request, registry_path=registry, workspace_path=workspace
        )
        from traffictwin.ui.services.models import ServiceError

        assert not isinstance(result, ServiceError)
        assert result.baseline_bundle_path is not None
        paths = {p.field_path for p in result.changed_parameters}
        assert "congestion_multiplier" in paths
        assert "rsu_capacity" not in paths


def test_selected_runs_wiring_after_generation() -> None:
    challenge = get_challenge_seed("CH-07-scaling-strategy")
    assert challenge is not None
    draft = build_challenge_whatif_draft(challenge)
    request = _draft_overrides_to_request(draft)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        workspace = tmp_path / "ws"
        registry = workspace / "registry.sqlite"
        workspace.mkdir(parents=True, exist_ok=True)
        result = generate_whatif_pair_for_ui(
            request, registry_path=registry, workspace_path=workspace
        )
        from traffictwin.ui.services.models import ServiceError

        assert not isinstance(result, ServiceError)
        fake_session: dict[str, object] = {}
        fake_session["selected_baseline_run"] = result.baseline_bundle_path or ""
        fake_session["selected_variation_run"] = result.variation_bundle_path or ""
        fake_session["selected_bundle_path"] = result.baseline_bundle_path or ""
        assert fake_session["selected_baseline_run"] != ""
        assert fake_session["selected_variation_run"] != ""
        assert fake_session["selected_baseline_run"] != fake_session["selected_variation_run"]
        assert Path(str(fake_session["selected_baseline_run"])).exists()
        assert Path(str(fake_session["selected_variation_run"])).exists()
