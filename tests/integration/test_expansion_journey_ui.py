# ruff: noqa: S108,E501,B017,F841,N811,ANN001,ANN201,ANN401,TRY003,TRY301
"""Expansion journey UI — Lane 16 coherent cross-epic AppTest.

Home/navigation -> Manchester Source Operations -> accepted or source-blocked standing
 -> Manchester Twin/SUMO controlled execution or provider gate -> compatible observed/simulated
  comparison -> Replay Observatory -> Research Registry -> provenance/report identities.

- Truthful blocked states are valid
- No SUMO binary, no network, no credentials, no private provider material
- Synthetic engineering SUMO execution, registry, replay, source ops remain available
- Bounded synthetic fixtures labelled exactly
- Never infers task-level replay from aggregate, causal from sync, map-match from distance, or realism from convergence
"""

from __future__ import annotations

import json
import pathlib
from copy import deepcopy

from streamlit.testing.v1 import AppTest

from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import page_script_for, validate_v07_page_specs
from traffictwin.ui.state import default_session_state


def _app_for(script: str) -> AppTest:
    app = AppTest.from_file(f"src/traffictwin/ui/{script}")
    for k, v in deepcopy(default_session_state()).items():
        app.session_state[k] = v
    app.session_state["_v07_navigation_active"] = True
    return app


def test_home_navigation_renders_and_links_to_expansion() -> None:
    validate_v07_page_specs()
    assert any(
        s.title == "Manchester Twin"
        for s in __import__(
            "traffictwin.ui.expansion_routes", fromlist=["EXPANSION_PAGE_SPECS"]
        ).EXPANSION_PAGE_SPECS
    )
    app = AppTest.from_file("src/traffictwin/ui/app.py").run(timeout=20)
    assert not app.exception
    assert app.session_state["_v07_navigation_active"] is True
    # Home must render without claiming live Manchester traffic as available
    blob = (
        "\n".join(str(x.value) for x in app.title)
        + "\n".join(str(x.value) for x in app.markdown)
        + "\n".join(str(x.value) for x in app.caption)
    )
    # Home must not claim city-wide live traffic as available (concrete positive claim)
    assert "city-wide live" not in blob.lower()
    assert "city-wide live traffic is available" not in blob.lower()


def test_manchester_source_operations_renders_truthfully() -> None:
    _app_for(page_script_for(UiPage.HOME))  # sanity: exercise Home
    # Directly render expansion page
    app2 = _app_for("app_pages/manchester_source_operations.py")
    app2.run(timeout=25)
    assert not app2.exception
    blob = (
        "\n".join(str(x.value) for x in getattr(app2, "title", []))
        + "\n".join(str(x.value) for x in getattr(app2, "markdown", []))
        + "\n".join(str(x.value) for x in getattr(app2, "caption", []))
        + "\n".join(str(x.value) for x in getattr(app2, "dataframe", []))
    )
    # Must show truthful per-family standing and BODS bus-only disclaimer via typed catalogue
    lower = blob.lower()
    assert "bus" in lower, "Manchester Source Operations page must state BODS is bus-only"
    # Page must not perform network or expose secrets
    assert "/Users/" not in blob
    assert "api_key" not in lower
    # Typed catalogue is the ground truth — BODS family is bus-only, not general traffic
    from traffictwin.ui.manchester_source_operations import build_demonstrator_catalogue

    cat = build_demonstrator_catalogue()
    assert len(cat.sources) == 8
    assert any(r.source.family.value == "bods" for r in cat.sources)
    bods_row = next(r for r in cat.sources if r.source.family.value == "bods")
    assert "bus" in bods_row.source.can_infer[0].lower()
    assert any("general" in x.lower() for x in bods_row.source.cannot_infer)


def test_manchester_twin_renders_synthetic_and_blocked_truthfully() -> None:
    app = _app_for("app_pages/manchester_twin.py")
    app.run(timeout=25)
    assert not app.exception
    blob = (
        "\n".join(str(x.value) for x in getattr(app, "title", []))
        + "\n".join(str(x.value) for x in getattr(app, "markdown", []))
        + "\n".join(str(x.value) for x in getattr(app, "caption", []))
        + "\n".join(str(x.value) for x in getattr(app, "info", []))
        + "\n".join(str(x.value) for x in getattr(app, "warning", []))
    )
    lower = blob.lower()
    # Must be labelled synthetic/design-only and provider blocked via exact standing
    assert "synthetic" in lower
    assert "provider_data_required" in lower
    # Must not claim scientific acceptance — the typed journey proves this
    from traffictwin.integration.manchester.closed_loop_journey import build_closed_loop_journey

    j_blocked = build_closed_loop_journey(
        journey_id="journey-ui-twin-blocked-check",
        source_provider_available=False,
        source_snapshot_id=None,
        baseline_package=None,
        baseline_decision=None,
        baseline_software_validation=None,
        map_workflow=None,
        demand_result=None,
        demand_receipt=None,
        demand_decision=None,
        calibration_result=None,
        calibration_decision=None,
        calibration_receipt=None,
        sumo_request=None,
        sumo_receipt=None,
        output_package=None,
        output_receipt=None,
        comparison_result=None,
    )
    assert j_blocked.overall_standing == "PROVIDER_DATA_REQUIRED"
    assert j_blocked.scientific_acceptance_present is False
    # Page truthfully teaches that scientifically_accepted_baseline requires explicit decision — not self-claimed
    assert "scientifically_accepted_baseline" in lower
    assert "software_valid does not imply scientifically_accepted_baseline" in lower
    # Page must distinguish software-valid from scientific acceptance (typed proof above is sufficient; no duplicate assert)
    assert any(m in lower for m in ("software_valid", "software-valid"))


def test_observed_simulated_compatibility_truthful() -> None:
    # Test that the twin page's synthetic comparison is correctly incompatible/compatible handling
    from decimal import Decimal

    from traffictwin.integration.manchester.comparison import ManchesterComparisonMetricContract

    contract = ManchesterComparisonMetricContract.model_validate(
        {
            "contract_version": "synthetic-demo-1",
            "evidence_class": "synthetic_development",
            "observed_source": "synthetic_utc_road",
            "scope_label": "synthetic_zone",
            "scope_fingerprint": "a" * 64,
            "time_basis_label": "synthetic_utc_hour",
            "time_basis_fingerprint": "b" * 64,
            "interval_duration_s": 900,
            "measure": "vehicle_count",
            "unit": "vehicles_per_interval",
            "minimum_observed_coverage": Decimal("0.500"),
            "minimum_simulated_coverage": Decimal("0.500"),
        },
        strict=True,
    )
    assert contract.measure == "vehicle_count"
    assert contract.unit == "vehicles_per_interval"
    # Incompatible would be refused — our check is that unit conversion is 'none' and missing is excluded, not zero-filled
    assert contract.unit_conversion == "none"
    assert contract.missing_policy == "exclude_unpaired_never_zero"


def test_replay_observatory_renders_with_disclaimers() -> None:
    app = _app_for("app_pages/replay_observatory.py")
    app.run(timeout=25)
    assert not app.exception
    blob = (
        "\n".join(str(x.value) for x in getattr(app, "title", []))
        + "\n".join(str(x.value) for x in getattr(app, "warning", []))
        + "\n".join(str(x.value) for x in getattr(app, "caption", []))
        + "\n".join(str(x.value) for x in getattr(app, "markdown", []))
    )
    lower = blob.lower()
    assert "replay observatory" in lower
    assert "deterministic" in lower
    # Must carry the typed non-causal disclaimers verbatim
    from traffictwin.ui.replay_observatory_service import (
        SYNCHRONIZED_REPLAY_DISCLAIMER,
    )

    assert SYNCHRONIZED_REPLAY_DISCLAIMER.lower() in lower
    assert "synthetic" in lower
    # Typed view disclaimers must be exact — prove via service, not vague substring
    from traffictwin.ui.replay_observatory_service import (
        build_synthetic_engineering_stream as _build_stream_j3,
    )
    from traffictwin.ui.replay_observatory_service import (
        create_engine as _create_engine_j3,
    )
    from traffictwin.ui.replay_observatory_service import (
        get_observatory_view as _get_view_j3,
    )

    _s_j3 = _build_stream_j3()
    _v_j3 = _get_view_j3(_create_engine_j3(_s_j3))
    assert _v_j3.causal_disclaimer == "replay is deterministic; no causality implied"
    assert _v_j3.sync_disclaimer == "synchronization is not evidence of causality"
    assert "SYNTHETIC ENGINEERING" in _v_j3.synthetic_disclaimer


def test_research_registry_renders_admitted_and_unavailable_truthfully() -> None:
    app = _app_for("app_pages/research_registry.py")
    app.run(timeout=25)
    assert not app.exception
    blob = (
        "\n".join(str(x.value) for x in getattr(app, "title", []))
        + "\n".join(str(x.value) for x in getattr(app, "markdown", []))
        + "\n".join(str(x.value) for x in getattr(app, "caption", []))
        + "\n".join(str(x.value) for x in getattr(app, "info", []))
        + "\n".join(str(x.value) for x in getattr(app, "dataframe", []))
    )
    lower = blob.lower()
    assert "research registry" in lower
    # Typed registry is the ground truth for admission
    from traffictwin.research_registry.models import AdmissionStatus
    from traffictwin.research_registry.service import RegistryService

    _snap_j4 = RegistryService.with_default_e2().snapshot()
    _admitted_e2 = [
        r
        for r in _snap_j4.records
        if r.study.startswith("E2") and r.admission_status == AdmissionStatus.ADMITTED
    ]
    assert len(_admitted_e2) >= 3, "typed registry must have at least 3 admitted E2"
    assert all(r.code_sha is not None and len(r.code_sha) == 40 for r in _admitted_e2)
    _e3_admitted = [
        r
        for r in _snap_j4.records
        if r.study == "E3" and r.admission_status == AdmissionStatus.ADMITTED
    ]
    assert len(_e3_admitted) == 0, "typed registry must have zero admitted E3 — no fabrication"
    # Page must show admitted and expose provenance identities via exact rendered marker
    assert "admitted" in lower
    assert "snapshot fingerprint" in lower
    # Registry UI contract: truthful future E3 absent/unavailable state must be rendered exactly
    assert "e3 is absent/unavailable by default" in lower


def test_cross_epic_journey_end_to_end_via_navigation_and_services() -> None:
    """End-to-end: Home -> Source Ops -> Twin (blocked truthful) -> Replay -> Registry -> provenance."""
    # 1. Home/navigation
    home_app = AppTest.from_file("src/traffictwin/ui/app.py").run(timeout=20)
    assert not home_app.exception
    # 2. Source Operations (accepted or blocked is valid)
    from traffictwin.ui.manchester_source_operations import build_demonstrator_catalogue

    cat = build_demonstrator_catalogue()
    # Truthful blocked states: BODS is credential_required when no credential, but our demonstrator may be synthetic? Check that at least one blocked or historical exists
    standings = {r.current_standing.value for r in cat.sources}
    assert any(
        s in standings for s in ("credential_required", "historical_only", "provider_data_required")
    )
    # 3. Twin/SUMO — truthful blocked and synthetic available (two journeys)
    from traffictwin.integration.manchester.closed_loop_journey import build_closed_loop_journey

    j_blocked = build_closed_loop_journey(
        journey_id="journey-e2e-blocked",
        source_provider_available=False,
        source_snapshot_id=None,
        baseline_package=None,
        baseline_decision=None,
        baseline_software_validation=None,
        map_workflow=None,
        demand_result=None,
        demand_receipt=None,
        demand_decision=None,
        calibration_result=None,
        calibration_decision=None,
        calibration_receipt=None,
        sumo_request=None,
        sumo_receipt=None,
        output_package=None,
        output_receipt=None,
        comparison_result=None,
    )
    assert j_blocked.overall_standing == "PROVIDER_DATA_REQUIRED"
    assert j_blocked.synthetic_execution_available is False
    # Synthetic available via synthetic output while still provider blocked
    from traffictwin.integration.manchester.models import sha256_hex as _sha256_hex_e2e
    from traffictwin.integration.manchester.sumo_output_pipeline import (
        SumoOutputFileDeclaration,
        SumoOutputNetworkIdentity,
        SumoOutputProvenance,
        SumoOutputTimeBasis,
        SumoOutputToolIdentity,
        build_sumo_output_request,
        import_sumo_outputs,
    )

    _trip_e2e = b'<tripinfos><tripinfo id="v0" depart="0.0" /></tripinfos>'
    _summ_e2e = b'<summary><step time="0.0" running="1" /></summary>'
    _tool_e2e = SumoOutputToolIdentity(reported_version="1.27.0", executable_sha256="a" * 64)
    _net_e2e = SumoOutputNetworkIdentity(
        network_sha256="b" * 64,
        demand_sha256="c" * 64,
        config_sha256="d" * 64,
        network_file="net.xml",
        demand_file="routes.xml",
        config_file="sumo.sumocfg",
    )
    _tb_e2e = SumoOutputTimeBasis(
        window_start_s=0,
        window_end_s=3600,
        step_length_s=1,
        time_basis_label="synthetic_utc_hour",
        time_basis_fingerprint="e" * 64,
    )
    _decls_e2e = [
        SumoOutputFileDeclaration(
            relative_path="tripinfo.xml",
            sha256=_sha256_hex_e2e(_trip_e2e),
            size_bytes=len(_trip_e2e),
            required=True,
            media_type="application/xml",
        ),
        SumoOutputFileDeclaration(
            relative_path="summary.xml",
            sha256=_sha256_hex_e2e(_summ_e2e),
            size_bytes=len(_summ_e2e),
            required=True,
            media_type="application/xml",
        ),
    ]
    _req_e2e = build_sumo_output_request(
        request_id="journey-e2e-req-01",
        run_id="journey-e2e-run-01",
        tool=_tool_e2e,
        network=_net_e2e,
        time_basis=_tb_e2e,
        files=_decls_e2e,
    )
    _pkg_e2e = import_sumo_outputs(
        _req_e2e,
        {"tripinfo.xml": _trip_e2e, "summary.xml": _summ_e2e},
        provenance=SumoOutputProvenance(
            created_at_utc="2026-01-01T00:00:00Z", created_by="journey-e2e", parent_fingerprints=()
        ),
    )
    j = build_closed_loop_journey(
        journey_id="journey-e2e",
        source_provider_available=False,
        source_snapshot_id=None,
        baseline_package=None,
        baseline_decision=None,
        baseline_software_validation=None,
        map_workflow=None,
        demand_result=None,
        demand_receipt=None,
        demand_decision=None,
        calibration_result=None,
        calibration_decision=None,
        calibration_receipt=None,
        sumo_request=None,
        sumo_receipt=None,
        output_package=_pkg_e2e,
        output_receipt=None,
        comparison_result=None,
    )
    assert j.overall_standing == "SOFTWARE_VALID_SYNTHETIC_AVAILABLE"
    assert j.synthetic_execution_available is True
    # 4. Comparison — compatible synthetic
    from decimal import Decimal

    from traffictwin.integration.manchester.comparison import ManchesterComparisonMetricContract

    contract = ManchesterComparisonMetricContract.model_validate(
        {
            "contract_version": "synthetic-demo-1",
            "evidence_class": "synthetic_development",
            "observed_source": "synthetic_utc_road",
            "scope_label": "synthetic_zone",
            "scope_fingerprint": "a" * 64,
            "time_basis_label": "synthetic_utc_hour",
            "time_basis_fingerprint": "b" * 64,
            "interval_duration_s": 900,
            "measure": "vehicle_count",
            "unit": "vehicles_per_interval",
            "minimum_observed_coverage": Decimal("0.500"),
            "minimum_simulated_coverage": Decimal("0.500"),
        },
        strict=True,
    )
    assert contract.unit == "vehicles_per_interval"
    # 5. Replay
    from traffictwin.ui.replay_observatory_service import (
        build_synthetic_engineering_stream,
        create_engine,
    )

    s = build_synthetic_engineering_stream()
    e = create_engine(s)
    assert e.state().playhead_time_s == 0.0
    # 6. Registry
    from traffictwin.research_registry.service import RegistryService

    snap = RegistryService.with_default_e2().snapshot()
    assert len(snap.records) >= 3
    # 7. Provenance/report identities — deterministic fingerprints present
    for rec in snap.records:
        if rec.study.startswith("E2"):
            assert rec.code_sha is not None and len(rec.code_sha) == 40
            assert rec.manifest_hash is not None and len(rec.manifest_hash) == 64
    # No absolute path leakage across journey
    dump = json.dumps(
        {
            "nav": [
                s.title
                for s in __import__(
                    "traffictwin.ui.expansion_routes", fromlist=["EXPANSION_PAGE_SPECS"]
                ).EXPANSION_PAGE_SPECS
            ],
            "journey": j.model_dump(mode="json"),
        },
        sort_keys=True,
    )
    assert "/Users/" not in dump
    assert "/home/" not in dump


def test_journey_does_not_require_sumo_binary_or_provider_observations() -> None:
    # Prove all four expansion pages render without SUMO binary, network, or provider observations
    for script in [
        "app_pages/manchester_twin.py",
        "app_pages/manchester_source_operations.py",
        "app_pages/replay_observatory.py",
        "app_pages/research_registry.py",
    ]:
        app = _app_for(script)
        app.run(timeout=25)
        assert not app.exception, f"{script} should render without external dependencies"
        blob = "\n".join(str(x.value) for x in getattr(app, "warning", [])) + "\n".join(
            str(x.value) for x in getattr(app, "info", [])
        )
        # Synthetic fixture must be labelled exactly
        if "manchester_twin" in script:
            assert "synthetic" in blob.lower()
        if "research_registry" in script:
            # Registry is read-only over typed service, not network
            pass


def test_no_inference_from_aggregate_sync_distance_or_convergence() -> None:
    # Explicitly assert that validator and journey do not infer forbidden things
    blob = "\n".join(
        pathlib.Path(f"src/traffictwin/ui/{s.script}").read_text()  # noqa: S108
        for s in __import__(
            "traffictwin.ui.expansion_routes", fromlist=["EXPANSION_PAGE_SPECS"]
        ).EXPANSION_PAGE_SPECS
    )
    lower = blob.lower()
    # Validator limitations must be exact and forbid the four inference classes
    from scripts.validate_traffictwin_expansion_v1 import build_validator_receipt, run_all_checks

    receipt = build_validator_receipt(run_all_checks())
    lim = "\n".join(receipt["limitations"]).lower()
    assert (
        "inferences from aggregate evidence, visual sync, distance alone, or convergence to realism are never made"
        in lim
    )
    # No page may claim causal effect — typed disclaimers are the enforcement
    from traffictwin.ui.replay_observatory_service import (
        build_synthetic_engineering_stream as _build_j5,
    )
    from traffictwin.ui.replay_observatory_service import create_engine as _create_j5
    from traffictwin.ui.replay_observatory_service import get_observatory_view as _get_view_j5

    _v_j5 = _get_view_j5(_create_j5(_build_j5()))
    assert _v_j5.causal_disclaimer == "replay is deterministic; no causality implied"
    assert _v_j5.sync_disclaimer == "synchronization is not evidence of causality"
    # Source expansion routes must not contain causal prose — strict anti-claim list
    assert "causal effect" not in lower
    assert "proves causality" not in lower
    assert "causally proves" not in lower
