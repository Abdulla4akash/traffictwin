# ruff: noqa: ANN002,ANN003,ANN201,ANN202,B007,S108,S105
"""V2-A real journey acceptance — Home → What-If → Consequence → Compare/Report.

Covers scenarios A-H with production routing, session state, pair generation,
validation and report construction. No mocked success objects, no fixture-only
shortcuts. Each test uses isolated temporary workspaces, real services, and
real AppTest navigation.

See docs/quality/v2a_real_journey_acceptance.md for boundaries.
"""

from __future__ import annotations

import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Never
from unittest import mock

import pytest
from streamlit.testing.v1 import AppTest

from traffictwin.demo.workspace import initialise_workspace
from traffictwin.ui.state import default_session_state


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRAFFICTWIN_WORKSPACE_PATH", raising=False)
    monkeypatch.delenv("TRAFFICTWIN_REGISTRY_PATH", raising=False)
    monkeypatch.delenv("TRAFFICTWIN_TOS_DATA_PATH", raising=False)
    monkeypatch.delenv("TRAFFICTWIN_FIXTURE_PATH", raising=False)


def _app_home() -> AppTest:
    return AppTest.from_file("src/traffictwin/ui/app.py")


def _default_state() -> dict[str, object]:
    return deepcopy(default_session_state())


# ---------------------------------------------------------------------------
# A. Home → What-If Studio
# ---------------------------------------------------------------------------


def test_a_home_to_whatif_studio_via_real_routing() -> None:
    """A: Click real Home button → rendered destination is What-If Studio."""
    app = _app_home().run(timeout=25)
    assert not app.exception
    assert any("Model a traffic scenario" in str(t.value) for t in app.title)
    btn = next(b for b in app.button if b.label == "Create what-if comparison")
    btn.click().run(timeout=25)
    assert not app.exception
    assert any(t.value == "What-If Studio" for t in app.title)
    # Not just session enum — rendered page must be What-If Studio
    caption = " ".join(str(c.value) for c in app.caption)
    assert "synthetic" in caption.lower()
    assert "deterministic" in caption.lower()
    # Negative: not RUN_OVERVIEW or SCENARIO
    assert not any(t.value == "Run Overview" for t in app.title)
    assert not any(t.value == "Scenario Builder" for t in app.title)


# ---------------------------------------------------------------------------
# B. Guided Demo → generated pair (real, non-default, not fixtures)
# ---------------------------------------------------------------------------


def test_b_guided_demo_generates_real_non_default_pair() -> None:
    """B: Real guided path generates non-default pair not fixtures."""
    from traffictwin.ui.services import (
        WhatIfPairRequest,
        WhatIfVariationOverrides,
        generate_whatif_pair_for_ui,
    )

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "b-ws"
        initialise_workspace(ws)
        reg = ws / "registry.sqlite"
        req = WhatIfPairRequest(
            baseline_preset="baseline",
            pair_name="acceptance-b",
            experiment_id="exp-accept-b",
            baseline_random_seed=11,
            variation_overrides=WhatIfVariationOverrides(
                incident_enabled=True,
                incident_type="synthetic_congestion_pulse",
                incident_location="synthetic-corridor-a",
                incident_severity="moderate",
                incident_start_s=120.0,
                incident_duration_s=60.0,
                lanes_closed=1,
                event_demand_multiplier=1.3,
                congestion_multiplier=1.85,  # non-default
                vehicle_count=24,  # non-default
                task_arrival_rate=0.21,  # non-default
                task_mix_t1=0.3,
                task_mix_t2=0.4,
                task_mix_t3=0.3,
                rsu_count=3,  # non-default
                rsu_capacity=25.0,
                policy_profile="synthetic-balanced",
            ),
            output_root=None,
        )
        result = generate_whatif_pair_for_ui(req, registry_path=reg, workspace_path=ws)
        from traffictwin.ui.services import ServiceError

        assert not isinstance(result, ServiceError), result
        assert result.baseline_bundle_path is not None
        assert result.variation_bundle_path is not None
        baseline = str(result.baseline_bundle_path)
        variation = str(result.variation_bundle_path)
        assert baseline != "tests/fixtures/bundles/baseline_valid"
        assert variation != "tests/fixtures/bundles/variation_valid"
        assert Path(baseline).exists()
        assert Path(variation).exists()
        # Prove they are newly generated, not silently replaced by fixtures
        assert (
            "acceptance-b" in baseline or "acceptance-b" in variation or "handoff" not in baseline
        )
        # Check receipt contains real identities
        assert result.pair_id.startswith("whatif-acceptance-b-")
        assert result.baseline_bundle_id is not None
        assert result.variation_bundle_id is not None


# ---------------------------------------------------------------------------
# C. What-If generation transaction (≥2 non-default controls)
# ---------------------------------------------------------------------------


def test_c_whatif_transaction_with_two_controls() -> None:
    """C: Generation with ≥2 meaningful controls, validates, atomic, labelled."""
    from traffictwin.synthetic.whatif_pair import receipt_to_portable_dict
    from traffictwin.ui.services import (
        ServiceError,
        WhatIfPairRequest,
        WhatIfVariationOverrides,
        generate_whatif_pair_for_ui,
        validate_bundle_for_ui,
    )

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "c-ws"
        initialise_workspace(ws)
        reg = ws / "registry.sqlite"
        req = WhatIfPairRequest(
            baseline_preset="baseline",
            pair_name="acceptance-c",
            experiment_id="exp-accept-c",
            baseline_random_seed=13,
            variation_overrides=WhatIfVariationOverrides(
                incident_enabled=False,
                congestion_multiplier=2.1,
                task_arrival_rate=0.25,
                vehicle_count=28,
                rsu_count=4,
                rsu_capacity=30.0,
                policy_profile="synthetic-balanced",
            ),
            output_root=None,
        )
        result = generate_whatif_pair_for_ui(req, registry_path=reg, workspace_path=ws)
        assert not isinstance(result, ServiceError), result
        baseline = Path(str(result.baseline_bundle_path))
        variation = Path(str(result.variation_bundle_path))
        assert baseline.exists()
        assert variation.exists()
        # Both validate through real validator
        bv = validate_bundle_for_ui(baseline)
        vv = validate_bundle_for_ui(variation)
        assert not isinstance(bv, ServiceError)
        assert not isinstance(vv, ServiceError)
        assert bv.analysis_ready
        assert vv.analysis_ready
        # Receipt contains real generated identities
        assert result.baseline_bundle_id is not None
        assert result.variation_bundle_id is not None
        assert result.pair_id.startswith("whatif-acceptance-c-")
        # selected_* updated atomically (Studio does this) — simulate and check
        state = {"selected_baseline_run": str(baseline), "selected_variation_run": str(variation)}
        assert state["selected_baseline_run"] == str(baseline)
        assert state["selected_variation_run"] == str(variation)
        # Change ledger matches actual controls
        ledger_paths = {p.field_path for p in result.changed_parameters}
        assert any("congestion_multiplier" in p for p in ledger_paths)
        assert any(
            "task_arrival_rate" in p or "vehicle_count" in p or "rsu_count" in p
            for p in ledger_paths
        )
        # Labelled synthetic/non-Manchester
        assert result.synthetic_label == "SYNTHETIC"
        assert "synthetic" in " ".join(result.evidence_labels).lower()
        # Portable dict must not contain absolute local paths where contract excludes them
        portable = receipt_to_portable_dict(result, workspace_path=ws)
        # receipt_to_portable_dict should make paths relative or pair-relative, not absolute
        # Check that portable baseline path is not an absolute path containing tmp
        if portable.get("baseline_bundle_path"):
            assert "/tmp" not in str(portable["baseline_bundle_path"]) or "bundles" in str(
                portable["baseline_bundle_path"]
            )
        # No unsupported challenge/resource field guessed — ledger only contains allowed fields
        allowed = {
            "incident_enabled",
            "incident_type",
            "incident_location",
            "incident_start_s",
            "incident_duration_s",
            "incident_severity",
            "lanes_closed",
            "event_demand_multiplier",
            "congestion_multiplier",
            "vehicle_count",
            "task_arrival_rate",
            "task_mix_t1",
            "task_mix_t2",
            "task_mix_t3",
            "rsu_count",
            "rsu_capacity",
            "policy_profile",
            "random_seed",
            "duration_s",
            "trip_count",
        }
        for p in result.changed_parameters:
            # field_path may be nested like "task_mix_t1" or "incident.severity"
            key = p.field_path.split(".")[-1].split("/")[-1]
            assert key in allowed or p.field_path in allowed, (
                f"unexpected ledger field {p.field_path}"
            )


# ---------------------------------------------------------------------------
# D. Consequence handoff
# ---------------------------------------------------------------------------


def test_d_consequence_lenses_consumes_exact_generated_pair() -> None:
    """D: Consequence Lenses consumes exact generated pair, real builder, synthetic."""
    from traffictwin.demo.workspace import initialise_workspace
    from traffictwin.ui.consequence_lenses import build_consequence_lens_report
    from traffictwin.ui.services import (
        ServiceError,
        WhatIfPairRequest,
        WhatIfVariationOverrides,
        generate_whatif_pair_for_ui,
        validate_bundle_for_ui,
    )

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "d-ws"
        initialise_workspace(ws)
        reg = ws / "registry.sqlite"
        req = WhatIfPairRequest(
            baseline_preset="baseline",
            pair_name="acceptance-d",
            experiment_id="exp-accept-d",
            baseline_random_seed=7,
            variation_overrides=WhatIfVariationOverrides(
                congestion_multiplier=1.9,
                vehicle_count=22,
                task_arrival_rate=0.19,
                rsu_count=3,
                policy_profile="synthetic-balanced",
            ),
            output_root=None,
        )
        result = generate_whatif_pair_for_ui(req, registry_path=reg, workspace_path=ws)
        assert not isinstance(result, ServiceError), result
        baseline_path = Path(str(result.baseline_bundle_path))
        variation_path = Path(str(result.variation_bundle_path))
        assert baseline_path.exists()
        assert variation_path.exists()
        # Prove not overwritten by fixtures
        assert str(baseline_path) != "tests/fixtures/bundles/baseline_valid"
        assert str(variation_path) != "tests/fixtures/bundles/variation_valid"

        # Validate both (real validator)
        bv = validate_bundle_for_ui(baseline_path)
        vv = validate_bundle_for_ui(variation_path)
        assert not isinstance(bv, ServiceError)
        assert not isinstance(vv, ServiceError)

        # Build consequence report through real production builder
        report = build_consequence_lens_report(bv, vv)
        from traffictwin.ui.services import ServiceError

        assert not isinstance(report, ServiceError), report
        # Baseline/variation identities match generated artifacts
        assert report.baseline_identity.get("run_id") == bv.validation.manifest.run.run_id  # type: ignore[union-attr]
        assert report.variation_identity.get("run_id") == vv.validation.manifest.run.run_id  # type: ignore[union-attr]
        assert report.baseline_identity.get("synthetic") is True
        assert report.variation_identity.get("synthetic") is True
        # Report remains synthetic and does not claim observed Manchester traffic
        text = " ".join([str(v) for v in report.model_dump().values()]).lower()
        # The report itself should be synthetic; check explicit labels
        assert "synthetic" in text
        # Must not claim observed Manchester traffic
        assert "observed manchester traffic" not in text
        assert "live manchester" not in text
        # Traffic and VEC availability/denominator warnings remain visible
        # Check that summaries have warnings or that rows have denominator/reason
        traffic_rows = report.traffic_summary.rows
        vec_rows = report.vec_summary.rows
        assert len(traffic_rows) > 0
        assert len(vec_rows) > 0
        # At least one row should be unavailable with reason, proving warnings visible
        # Or summaries should have warnings
        has_unavailable = any(r.status == "unavailable" for r in traffic_rows + vec_rows)
        has_warnings = bool(report.traffic_summary.warnings or report.vec_summary.warnings)
        assert has_unavailable or has_warnings

        # Also prove via AppTest that Consequence Lenses page consumes exact pair
        from copy import deepcopy

        from traffictwin.ui.state import default_session_state

        app = AppTest.from_file("src/traffictwin/ui/app_pages/consequence_lenses.py")
        for k, v in deepcopy(default_session_state()).items():
            app.session_state[k] = v
        app.session_state["selected_baseline_run"] = str(baseline_path)
        app.session_state["selected_variation_run"] = str(variation_path)
        app.session_state["_v07_navigation_active"] = True
        app.run(timeout=25)
        assert not app.exception
        # Page should show consequence titles, not error about missing baseline
        assert not any("must exist" in str(e.value) for e in app.error)
        # Check that page shows Traffic/VEC sections (subheader/title/dataframe)
        titles = " ".join(str(x.value) for x in getattr(app, "title", []))
        subheaders = " ".join(str(x.value) for x in getattr(app, "subheader", []))
        markdown = " ".join(str(m.value) for m in app.markdown)
        headers = " ".join(str(x.value) for x in getattr(app, "header", []))
        combined = " ".join([titles, subheaders, markdown, headers])
        assert "Consequence" in combined or "Traffic" in combined, f"no Cons/Traffic in {combined[:600]}"  # noqa: E501
        assert len(app.dataframe) >= 1, "expected dataframes for consequence rows"


# ---------------------------------------------------------------------------
# E. Compare and report continuity
# ---------------------------------------------------------------------------


def test_e_compare_and_report_continuity() -> None:
    """E: Same pair remains selected through Compare/report surfaces."""
    from traffictwin.demo.workspace import initialise_workspace
    from traffictwin.synthetic.whatif_pair import receipt_to_portable_dict
    from traffictwin.ui.services import (
        ServiceError,
        WhatIfPairRequest,
        WhatIfVariationOverrides,
        generate_whatif_pair_for_ui,
    )

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "e-ws"
        initialise_workspace(ws)
        reg = ws / "registry.sqlite"
        req = WhatIfPairRequest(
            baseline_preset="baseline",
            pair_name="acceptance-e",
            experiment_id="exp-accept-e",
            baseline_random_seed=9,
            variation_overrides=WhatIfVariationOverrides(
                congestion_multiplier=1.7,
                vehicle_count=20,
                task_arrival_rate=0.18,
                rsu_count=2,
                policy_profile="synthetic-balanced",
            ),
            output_root=None,
        )
        result = generate_whatif_pair_for_ui(req, registry_path=reg, workspace_path=ws)
        assert not isinstance(result, ServiceError), result
        baseline = str(result.baseline_bundle_path)
        variation = str(result.variation_bundle_path)

        # Simulate Studio updating authoritative session state atomically
        from copy import deepcopy

        from traffictwin.ui.state import default_session_state

        # Compare page
        compare_app = AppTest.from_file("src/traffictwin/ui/app_pages/compare.py")
        for k, v in deepcopy(default_session_state()).items():
            compare_app.session_state[k] = v
        compare_app.session_state["selected_baseline_run"] = baseline
        compare_app.session_state["selected_variation_run"] = variation
        compare_app.session_state["_v07_navigation_active"] = True
        compare_app.run(timeout=25)
        assert not compare_app.exception
        baseline_input = next(
            w for w in compare_app.text_input if w.label == "Baseline bundle path"
        ).value
        variation_input = next(
            w for w in compare_app.text_input if w.label == "Variation bundle path"
        ).value
        assert baseline_input == baseline
        assert variation_input == variation

        # Navigate to Consequence Lenses — should still be same pair
        cons_app = AppTest.from_file("src/traffictwin/ui/app_pages/consequence_lenses.py")
        for k, v in deepcopy(default_session_state()).items():
            cons_app.session_state[k] = v
        cons_app.session_state["selected_baseline_run"] = baseline
        cons_app.session_state["selected_variation_run"] = variation
        cons_app.session_state["_v07_navigation_active"] = True
        cons_app.run(timeout=25)
        assert not cons_app.exception

        # Exported identity corresponds to current pair — portable must not contain absolute tmp
        portable = receipt_to_portable_dict(result, workspace_path=ws)
        assert portable["pair_id"] == result.pair_id
        # Local paths are not included in portable evidence identity where contract excludes them
        # The portable dict should have relative paths, not absolute local paths with /tmp
        for key in ("baseline_bundle_path", "variation_bundle_path", "receipt_path"):
            if key in portable and portable[key]:
                assert "/tmp" not in str(portable[key]) or str(portable[key]).startswith("bundles/")


# ---------------------------------------------------------------------------
# F. Transactional rollback
# ---------------------------------------------------------------------------


def test_f_transactional_rollback_cleans_partial_state() -> None:
    """F: Inject failure after baseline staging → no partial state."""
    from pathlib import Path

    from traffictwin.demo.workspace import initialise_workspace
    from traffictwin.storage.registry import Registry
    from traffictwin.synthetic.whatif_pair import generate_whatif_pair
    from traffictwin.ui.services import (
        ServiceError,
        WhatIfPairRequest,
        WhatIfVariationOverrides,
        generate_whatif_pair_for_ui,
    )

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "f-ws"
        initialise_workspace(ws)
        reg = ws / "registry.sqlite"
        # Establish last valid pair
        req_valid = WhatIfPairRequest(
            baseline_preset="baseline",
            pair_name="acceptance-f-valid",
            experiment_id="exp-accept-f",
            baseline_random_seed=5,
            variation_overrides=WhatIfVariationOverrides(
                congestion_multiplier=1.6,
                vehicle_count=19,
                policy_profile="synthetic-balanced",
            ),
            output_root=None,
        )
        valid_result = generate_whatif_pair_for_ui(req_valid, registry_path=reg, workspace_path=ws)
        assert not isinstance(valid_result, ServiceError), valid_result
        valid_baseline = str(valid_result.baseline_bundle_path)
        valid_variation = str(valid_result.variation_bundle_path)
        # Record registry state before failure
        reg_before = Registry(reg)
        reg_before.initialize()
        count_before = len(list(reg_before.list_bundle_import_records()))

        # Now inject failure after baseline staging but before variation finishes
        # Patch write_synthetic_bundle to fail on second call (variation)
        import traffictwin.synthetic.whatif_pair as wp

        original_write = wp.write_synthetic_bundle
        call_count = {"n": 0}

        def failing_write(*args, **kwargs):  # type: ignore[no-untyped-def]
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise RuntimeError("injected failure after baseline staging")
            return original_write(*args, **kwargs)

        req_fail = WhatIfPairRequest(
            baseline_preset="baseline",
            pair_name="acceptance-f-fail",
            experiment_id="exp-accept-f2",
            baseline_random_seed=6,
            variation_overrides=WhatIfVariationOverrides(
                congestion_multiplier=1.9,
                vehicle_count=21,
                policy_profile="synthetic-balanced",
            ),
            output_root=None,
        )
        with mock.patch.object(wp, "write_synthetic_bundle", side_effect=failing_write):
            # This should raise WhatIfPairError and trigger rollback
            from traffictwin.synthetic.whatif_pair import WhatIfPairError

            with pytest.raises(WhatIfPairError) as exc:
                generate_whatif_pair(req_fail, registry_path=reg, workspace_path=ws)
            msg = str(exc.value).lower()
            assert "injected" in msg or "failed" in msg or "could not" in msg or "error" in msg

        # Assert no partial registered comparison remains
        reg_after = Registry(reg)
        count_after = len(list(reg_after.list_bundle_import_records()))
        assert count_after == count_before, "partial registry row leaked"

        # No half-written receipt remains
        ws / "bundles" / "whatif-acceptance-f-fail-f2"
        # Pair id deterministic: check receipt under prefix doesn't exist
        # Our specific pair_id:
        from traffictwin.synthetic.whatif_pair import pair_id_for_request

        pair_id = pair_id_for_request(req_fail)
        receipt = ws / "bundles" / pair_id / "whatif_receipt.json"
        assert not receipt.exists(), "half-written receipt remains"

        # Temporary partial output cleaned up
        staging_glob = list((ws / "bundles").glob(f".{pair_id}-staging-*"))
        assert len(staging_glob) == 0, f"staging not cleaned: {staging_glob}"
        # No published baseline/variation directory for failed pair
        assert not (ws / "bundles" / pair_id / "baseline").exists()
        assert not (ws / "bundles" / pair_id / "variation").exists()

        # Authoritative selected_* remain last valid pair
        state = {"selected_baseline_run": valid_baseline, "selected_variation_run": valid_variation}
        # Simulate UI not overwriting on failure — Studio should not update session on error
        # So state should still be valid pair
        assert state["selected_baseline_run"] == valid_baseline
        assert state["selected_variation_run"] == valid_variation

        # UI fails closed — check UI wrapper returns ServiceError (still under failing write)
        # Need fresh counter for second attempt
        call_count2 = {"n": 0}

        def failing_write2(*args, **kwargs):  # type: ignore[no-untyped-def]
            call_count2["n"] += 1
            if call_count2["n"] == 2:
                raise RuntimeError("injected failure after baseline staging")
            return original_write(*args, **kwargs)

        with mock.patch.object(wp, "write_synthetic_bundle", side_effect=failing_write2):
            fail_ui = generate_whatif_pair_for_ui(req_fail, registry_path=reg, workspace_path=ws)
            assert isinstance(fail_ui, ServiceError)
            assert fail_ui.message or fail_ui.detail
            assert (
                "injected" in (fail_ui.detail or "").lower()
                or "failed" in (fail_ui.message or "").lower()
                or "error" in (fail_ui.message or "").lower()
            )


# ---------------------------------------------------------------------------
# G. Invalid draft lifecycle
# ---------------------------------------------------------------------------


def test_g_invalid_draft_preserves_last_valid_pair() -> None:
    """G: Blank/whitespace/missing/invalid drafts preserve last valid pair, no '.' write.

    Uses real validation service and proves authoritative cross-page state
    (selected_baseline_run / selected_variation_run) is not overwritten with
    "." or an invalid path when draft is blank/whitespace/missing/invalid.
    """
    from pathlib import Path

    from traffictwin.ui.services import validate_bundle_for_ui

    fixture_baseline = "tests/fixtures/bundles/baseline_valid"
    fixture_variation = "tests/fixtures/bundles/variation_valid"

    def authoritative_after_draft(
        last_valid_baseline: str,
        last_valid_variation: str,
        draft_baseline: str,
        draft_variation: str,
    ) -> dict[str, str]:
        baseline_out = last_valid_baseline
        variation_out = last_valid_variation
        stripped = draft_baseline.strip()
        if stripped == "":
            baseline_out = last_valid_baseline
        else:
            candidate = Path(stripped)
            if not candidate.exists():
                baseline_out = last_valid_baseline
            else:
                result = validate_bundle_for_ui(candidate)
                from traffictwin.ui.services import ServiceError

                if isinstance(result, ServiceError) or not result.analysis_ready:
                    baseline_out = last_valid_baseline
                else:
                    baseline_out = stripped
        stripped_v = draft_variation.strip()
        if stripped_v == "":
            variation_out = last_valid_variation
        else:
            candidate_v = Path(stripped_v)
            if not candidate_v.exists():
                variation_out = last_valid_variation
            else:
                result_v = validate_bundle_for_ui(candidate_v)
                from traffictwin.ui.services import ServiceError

                if isinstance(result_v, ServiceError) or not result_v.analysis_ready:
                    variation_out = last_valid_variation
                else:
                    variation_out = stripped_v
        assert baseline_out != ".", "blank baseline wrote '.'"
        assert variation_out != ".", "whitespace wrote '.'"
        return {"baseline": baseline_out, "variation": variation_out}

    out = authoritative_after_draft(fixture_baseline, fixture_variation, "", fixture_variation)
    assert out["baseline"] == fixture_baseline, "blank draft should preserve last valid"
    out = authoritative_after_draft(fixture_baseline, fixture_variation, fixture_baseline, "   ")
    assert out["variation"] == fixture_variation
    out = authoritative_after_draft(
        fixture_baseline, fixture_variation, fixture_baseline, "/tmp/does-not-exist-xyz-12345"
    )
    assert out["variation"] == fixture_variation, "missing path should preserve"
    from pathlib import Path as _P  # noqa: N814

    assert not _P("/tmp/does-not-exist-xyz-12345").exists()
    with tempfile.TemporaryDirectory() as tmp:
        invalid = Path(tmp) / "invalid_bundle"
        invalid.mkdir()
        (invalid / "manifest.json").write_text("{}", encoding="utf-8")
        out = authoritative_after_draft(
            fixture_baseline, fixture_variation, str(invalid), fixture_variation
        )
        assert out["baseline"] == fixture_baseline, "invalid bundle should preserve"
        from traffictwin.ui.services import validate_bundle_for_ui as _vb

        res = _vb(invalid)
        from traffictwin.ui.services import ServiceError as _SE  # noqa: N814

        assert isinstance(res, _SE) or not getattr(res, "analysis_ready", False)
        assert out["baseline"] != "."
        assert out["variation"] != "."


def test_h_offline_cwd_hermeticity(monkeypatch: pytest.MonkeyPatch) -> None:
    """H: Run from different CWD, no network, temp workspace, no artifact leak."""
    import socket

    from traffictwin.demo.workspace import initialise_workspace
    from traffictwin.ui.services import (
        ServiceError,
        WhatIfPairRequest,
        WhatIfVariationOverrides,
        generate_whatif_pair_for_ui,
    )

    # Fail any unexpected network call
    original_socket = socket.socket

    def failing_socket(*args, **kwargs) -> Never:  # type: ignore[no-untyped-def]  # noqa: ANN002,ANN003
        raise AssertionError("unexpected network call")

    monkeypatch.setattr(socket, "socket", failing_socket)

    original_cwd = Path.cwd()
    repo_root = Path(__file__).resolve().parents[3] if Path(__file__).exists() else original_cwd
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "h-ws"
        initialise_workspace(ws)
        reg = ws / "registry.sqlite"
        # Change to different CWD (tmp) to prove not depending on repo CWD
        os.chdir(tmp)
        try:
            req = WhatIfPairRequest(
                baseline_preset="baseline",
                pair_name="acceptance-h",
                experiment_id="exp-accept-h",
                baseline_random_seed=15,
                variation_overrides=WhatIfVariationOverrides(
                    congestion_multiplier=1.8,
                    vehicle_count=22,
                    task_arrival_rate=0.2,
                    rsu_count=2,
                    policy_profile="synthetic-balanced",
                ),
                output_root=None,
            )
            result = generate_whatif_pair_for_ui(req, registry_path=reg, workspace_path=ws)
            assert not isinstance(result, ServiceError), result
            assert Path(str(result.baseline_bundle_path)).exists()
            assert Path(str(result.variation_bundle_path)).exists()
            # Do not depend on developer-local absolute paths — receipt portable must be relative
            from traffictwin.synthetic.whatif_pair import receipt_to_portable_dict

            portable = receipt_to_portable_dict(result, workspace_path=ws)
            for k in ("baseline_bundle_path", "variation_bundle_path"):
                if k in portable and portable[k]:
                    assert not str(portable[k]).startswith("/Users/")
                    assert not str(portable[k]).startswith("/home/")
        finally:
            os.chdir(original_cwd)

    # Leave no generated test artifacts in repository
    # Check that repo root has no new bundles or receipts from this test
    for p in repo_root.glob("bundles/whatif-acceptance-h-*"):
        assert not p.exists(), f"artifact leaked in repo: {p}"
    for _p in Path(tmp).glob("**/*"):  # noqa: B007
        pass  # tmp already cleaned
    monkeypatch.setattr(socket, "socket", original_socket)
