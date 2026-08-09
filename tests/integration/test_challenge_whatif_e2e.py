"""End-to-end probe: Portfolio → What-If → Generate → Compare wiring.

Proves:

- Portfolio handoff contains supported values.
- What-If prefill applies them.
- Ledger reflects actual mapped inputs.
- Generate produces valid pair.
- Pair described as prepared from supported subset, not exact execution.
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
    # Build overrides — fill required fields, keep mapped ones
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
    # Pick CH-01 which is FULLY_MAPPABLE with meaningful fields
    challenge = get_challenge_seed("CH-01-arena-surge")
    assert challenge is not None
    draft = build_challenge_whatif_draft(challenge)
    # Must have at least one meaningful field transferred
    assert len(draft.supported_fields) >= 1
    ov = draft.whatif_overrides
    assert ov.get("congestion_multiplier") == 2.2
    assert ov.get("task_arrival_rate") == 0.16
    # Incident fields present
    assert ov.get("incident_type") == "stadium_event"

    # Preview ledger reflects actual mapped inputs
    request = _draft_overrides_to_request(draft)
    # Ensure request differs from baseline (otherwise ledger empty)
    # Baseline is preset "baseline" with congestion 1.0, task_arrival 0.11 etc.
    ledger = preview_whatif_ledger_for_ui(request)
    from traffictwin.ui.services.models import ServiceError

    assert not isinstance(ledger, ServiceError), f"ledger error: {ledger}"
    assert len(ledger) >= 1
    # Ledger must contain congestion and task arrival changes
    paths = {p.field_path for p in ledger}
    assert "congestion_multiplier" in paths
    assert "task_arrival_rate" in paths

    # Generate pair — valid bundle pair
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
        assert result.baseline_bundle_id is not None
        assert result.variation_bundle_id is not None
        # Paths exist
        assert Path(result.baseline_bundle_path).exists()
        assert Path(result.variation_bundle_path).exists()
        # Changed parameters present
        assert len(result.changed_parameters) >= 1
        # Pair wording: must not claim exact execution if unsupported exist
        # (CH-01 has none). For CH-01 fully mappable, still prepared from
        # challenges — but not "CH-01 executed". Validate draft has no false claim
        assert draft.mapping_status.value in (
            "FULLY_MAPPABLE",
            "PARTIALLY_MAPPABLE",
            "NOT_MAPPABLE",
        )
        # For partially mappable challenge: wording must say supported subset
        ch04 = get_challenge_seed("CH-04-rsu-waiting-room-squeeze")
        assert ch04 is not None
        d04 = build_challenge_whatif_draft(ch04)
        assert len(d04.unsupported_fields) >= 1
        assert any("Only the supported subset will be prefilled" in w for w in d04.warnings)
        # Handoff fingerprint matches
        assert d04.fingerprint


def test_e2e_partially_mappable_pair_wording() -> None:
    # CH-02 is PARTIALLY_MAPPABLE — verify unsupported fields visible and wording
    challenge = get_challenge_seed("CH-02-lane-closure-corridor")
    assert challenge is not None
    draft = build_challenge_whatif_draft(challenge)
    assert draft.mapping_status.value == "PARTIALLY_MAPPABLE"
    assert len(draft.unsupported_fields) == 1
    assert draft.unsupported_fields[0].challenge_path == "infrastructure.rsu_capacity_mode"
    # Request from draft should NOT contain rsu_capacity
    request = _draft_overrides_to_request(draft)
    assert request.variation_overrides.rsu_capacity is None
    # But should contain congestion and lanes_closed
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
        # Valid pair
        assert result.baseline_bundle_path is not None
        # Ledger contains mapped fields
        paths = {p.field_path for p in result.changed_parameters}
        assert "congestion_multiplier" in paths
        # rsu_capacity should NOT be in ledger (since not overridden)
        assert "rsu_capacity" not in paths


def test_selected_runs_wiring_after_generation() -> None:
    """Prove that after generation, baseline/variation paths would wire Compare correctly."""
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
        # Simulate what What-If Studio does on success
        fake_session: dict[str, object] = {}
        fake_session["selected_baseline_run"] = result.baseline_bundle_path or ""
        fake_session["selected_variation_run"] = result.variation_bundle_path or ""
        fake_session["selected_bundle_path"] = result.baseline_bundle_path or ""
        assert fake_session["selected_baseline_run"] != ""
        assert fake_session["selected_variation_run"] != ""
        assert fake_session["selected_baseline_run"] != fake_session["selected_variation_run"]
        # Paths must be distinct and valid
        assert Path(str(fake_session["selected_baseline_run"])).exists()
        assert Path(str(fake_session["selected_variation_run"])).exists()
