"""V2-S1 what-if pair service tests — deterministic, transactional, idempotent."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.storage.registry import Registry
from traffictwin.synthetic.whatif_pair import (
    WhatIfPairRequest,
    WhatIfVariationOverrides,
    build_whatif_configs,
    compute_changed_ledger,
    generate_whatif_pair,
    pair_id_for_request,
    request_fingerprint,
    sanitise_pair_name,
)


def _tmp_workspace(tmp_path: Path) -> tuple[Path, Path]:
    ws = tmp_path / "ws"
    ws.mkdir()
    reg = ws / "registry.sqlite"
    return ws, reg


def test_deterministic_fingerprint_and_pair_id() -> None:
    req = WhatIfPairRequest(
        baseline_preset="baseline",
        pair_name="congestion-pulse",
        experiment_id="exp-demo",
        variation_overrides=WhatIfVariationOverrides(congestion_multiplier=1.5),
    )
    fp1 = request_fingerprint(req)
    fp2 = request_fingerprint(req)
    assert fp1 == fp2
    assert len(fp1) == 64
    pid1 = pair_id_for_request(req)
    pid2 = pair_id_for_request(req)
    assert pid1 == pid2
    assert pid1.startswith("whatif-congestion-pulse-")
    # different content gives different fingerprint
    req2 = WhatIfPairRequest(
        baseline_preset="baseline",
        pair_name="congestion-pulse",
        experiment_id="exp-demo",
        variation_overrides=WhatIfVariationOverrides(congestion_multiplier=2.0),
    )
    assert request_fingerprint(req2) != fp1
    assert pair_id_for_request(req2) != pid1


def test_baseline_and_variation_ids() -> None:
    req = WhatIfPairRequest(
        baseline_preset="baseline",
        pair_name="my-pair",
        experiment_id="exp-whatif",
        variation_overrides=WhatIfVariationOverrides(vehicle_count=30),
    )
    baseline, variation = build_whatif_configs(req)
    pid = pair_id_for_request(req)
    assert baseline.scenario_id == f"{pid}-baseline"
    assert variation.scenario_id == f"{pid}-variation"
    assert baseline.experiment_id == "exp-whatif"
    assert variation.experiment_id == "exp-whatif"
    assert variation.baseline_seed_id == f"seed-{baseline.scenario_id}"
    assert baseline.scenario_id != variation.scenario_id


def test_changed_ledger_contains_every_change() -> None:
    req = WhatIfPairRequest(
        baseline_preset="baseline",
        pair_name="ledger-test",
        experiment_id="exp-demo",
        variation_overrides=WhatIfVariationOverrides(
            congestion_multiplier=2.0,
            vehicle_count=30,
            rsu_capacity=22.0,
            policy_profile="synthetic-always-local",
        ),
    )
    b, v = build_whatif_configs(req)
    ledger = compute_changed_ledger(b, v)
    paths = {p.field_path for p in ledger}
    assert "congestion_multiplier" in paths
    assert "vehicle_count" in paths
    assert "rsu_capacity" in paths
    assert "policy_behavior" in paths
    # ordering is lexical
    assert paths == set(sorted(paths))
    assert [p.field_path for p in ledger] == sorted([p.field_path for p in ledger])


def test_unchanged_fields_absent_from_ledger() -> None:
    req = WhatIfPairRequest(
        baseline_preset="baseline",
        pair_name="unchanged-test",
        experiment_id="exp-demo",
        variation_overrides=WhatIfVariationOverrides(congestion_multiplier=2.0),
    )
    b, v = build_whatif_configs(req)
    ledger = compute_changed_ledger(b, v)
    paths = {p.field_path for p in ledger}
    # only congestion should be changed
    assert "congestion_multiplier" in paths
    assert "vehicle_count" not in paths
    assert "rsu_count" not in paths
    # rsu_capacity not changed
    assert "rsu_capacity" not in paths


def test_identical_baseline_variation_refuses(tmp_path: Path) -> None:
    ws, reg = _tmp_workspace(tmp_path)
    req = WhatIfPairRequest(
        baseline_preset="baseline", pair_name="identical", experiment_id="exp-demo"
    )
    from traffictwin.synthetic.whatif_pair import WhatIfPairError

    with pytest.raises(WhatIfPairError) as exc:
        generate_whatif_pair(req, registry_path=reg, workspace_path=ws)
    assert exc.value.code == "identical_pair"
    # no partial
    pid = pair_id_for_request(req)
    assert not (ws / "bundles" / pid).exists()
    assert not reg.exists() or Registry(reg).inspect().run_count == 0


def test_both_bundles_validate_and_comparable(tmp_path: Path) -> None:
    ws, reg = _tmp_workspace(tmp_path)
    req = WhatIfPairRequest(
        baseline_preset="baseline",
        pair_name="comparable-test",
        experiment_id="exp-comparable",
        variation_overrides=WhatIfVariationOverrides(
            congestion_multiplier=1.6, incident_enabled=True
        ),
    )
    receipt = generate_whatif_pair(req, registry_path=reg, workspace_path=ws)
    assert receipt.status == "ok"
    assert receipt.baseline_bundle_path is not None
    assert receipt.variation_bundle_path is not None
    b = validate_bundle(Path(receipt.baseline_bundle_path))
    v = validate_bundle(Path(receipt.variation_bundle_path))
    assert b.report.may_import
    assert v.report.may_import
    assert b.manifest is not None and v.manifest is not None
    assert b.manifest.run.experiment_id == v.manifest.run.experiment_id == "exp-comparable"
    assert b.manifest.environment.name == "synthetic"
    assert v.manifest.environment.name == "synthetic"
    # comparable via compare service
    from traffictwin.ui.services import compare_runs_for_ui, validate_bundle_for_ui

    b_a = validate_bundle_for_ui(Path(receipt.baseline_bundle_path))
    v_a = validate_bundle_for_ui(Path(receipt.variation_bundle_path))
    report = compare_runs_for_ui(b_a, v_a)
    assert not hasattr(report, "message")
    assert report.baseline_context.get("experiment_id") == "exp-comparable"


def test_exact_retry_is_idempotent(tmp_path: Path) -> None:
    ws, reg = _tmp_workspace(tmp_path)
    req = WhatIfPairRequest(
        baseline_preset="baseline",
        pair_name="idempotent-test",
        experiment_id="exp-idem",
        variation_overrides=WhatIfVariationOverrides(congestion_multiplier=1.7),
    )
    r1 = generate_whatif_pair(req, registry_path=reg, workspace_path=ws)
    assert r1.status == "ok"
    r2 = generate_whatif_pair(req, registry_path=reg, workspace_path=ws)
    assert r2.status == "already_exists"
    assert r2.pair_id == r1.pair_id
    assert r2.request_fingerprint == r1.request_fingerprint
    # registry still 2 runs, not 4
    assert Registry(reg).inspect().run_count == 2
    assert r1.baseline_bundle_path is not None
    assert r1.variation_bundle_path is not None
    assert Path(r1.baseline_bundle_path).exists()
    assert Path(r1.variation_bundle_path).exists()


def test_changed_content_collision_refuses(tmp_path: Path) -> None:
    ws, reg = _tmp_workspace(tmp_path)
    req1 = WhatIfPairRequest(
        baseline_preset="baseline",
        pair_name="collision-test",
        experiment_id="exp-demo",
        variation_overrides=WhatIfVariationOverrides(congestion_multiplier=1.5),
    )
    r1 = generate_whatif_pair(req1, registry_path=reg, workspace_path=ws)
    assert r1.status == "ok"
    # Manually tamper: create same pair_id dir with different fingerprint
    pid = pair_id_for_request(req1)
    receipt_path = ws / "bundles" / pid / "whatif_receipt.json"
    data = json.loads(receipt_path.read_text())
    data["pair_fingerprint"] = "0" * 64
    receipt_path.write_text(json.dumps(data))
    # Now try to re-create same request -> should detect corrupt and refuse (not treat as success)
    from traffictwin.synthetic.whatif_pair import WhatIfPairError

    with pytest.raises(WhatIfPairError) as exc:
        generate_whatif_pair(req1, registry_path=reg, workspace_path=ws)
    assert exc.value.code in {"corrupt_existing_pair", "pair_id_collision"}


def test_unsafe_output_path_refused(tmp_path: Path) -> None:
    ws, reg = _tmp_workspace(tmp_path)
    req = WhatIfPairRequest(
        baseline_preset="baseline",
        pair_name="unsafe-test",
        experiment_id="exp-demo",
        variation_overrides=WhatIfVariationOverrides(congestion_multiplier=1.5),
        output_root=Path("/"),
    )
    from traffictwin.synthetic.whatif_pair import WhatIfPairError

    with pytest.raises(WhatIfPairError) as exc:
        generate_whatif_pair(req, registry_path=reg, workspace_path=ws)
    assert exc.value.code == "unsafe_path"


def test_existing_unrelated_nonempty_destination_refused(tmp_path: Path) -> None:
    ws, reg = _tmp_workspace(tmp_path)
    req = WhatIfPairRequest(
        baseline_preset="baseline",
        pair_name="unrelated-test",
        experiment_id="exp-demo",
        variation_overrides=WhatIfVariationOverrides(congestion_multiplier=1.6),
    )
    pid = pair_id_for_request(req)
    dest = ws / "bundles" / pid
    dest.mkdir(parents=True)
    (dest / "random.txt").write_text("unrelated")
    from traffictwin.synthetic.whatif_pair import WhatIfPairError

    with pytest.raises(WhatIfPairError) as exc:
        generate_whatif_pair(req, registry_path=reg, workspace_path=ws)
    assert exc.value.code == "destination_exists"
    # unrelated data preserved
    assert (dest / "random.txt").exists()


def test_baseline_generation_failure_rolls_back(tmp_path: Path) -> None:
    ws, reg = _tmp_workspace(tmp_path)
    req = WhatIfPairRequest(
        baseline_preset="baseline",
        pair_name="rollback-baseline",
        experiment_id="exp-demo",
        variation_overrides=WhatIfVariationOverrides(congestion_multiplier=2.0),
    )
    from traffictwin.synthetic import whatif_pair as m

    orig = m.write_synthetic_bundle

    def fail_baseline(cfg: Any, dest: Path, overwrite: bool = False) -> Path:
        if "baseline" in str(dest):
            raise RuntimeError("baseline fail")
        return orig(cfg, dest, overwrite=overwrite)

    with patch.object(m, "write_synthetic_bundle", side_effect=fail_baseline):
        from traffictwin.synthetic.whatif_pair import WhatIfPairError

        with pytest.raises(WhatIfPairError) as exc:
            generate_whatif_pair(req, registry_path=reg, workspace_path=ws)
        assert exc.value.code == "baseline_generation_failed"
    pid = pair_id_for_request(req)
    assert not (ws / "bundles" / pid).exists()
    # no partial staging
    assert not any((ws / "bundles").glob(".*-staging-*")) if (ws / "bundles").exists() else True
    assert not reg.exists() or Registry(reg).inspect().run_count == 0


def test_variation_generation_failure_rolls_back(tmp_path: Path) -> None:
    ws, reg = _tmp_workspace(tmp_path)
    req = WhatIfPairRequest(
        baseline_preset="baseline",
        pair_name="rollback-variation",
        experiment_id="exp-demo",
        variation_overrides=WhatIfVariationOverrides(congestion_multiplier=2.0),
    )
    from traffictwin.synthetic import whatif_pair as m

    orig = m.write_synthetic_bundle

    def fail_variation(cfg: Any, dest: Path, overwrite: bool = False) -> Path:
        # distinguish via scenario_id suffix
        if hasattr(cfg, "scenario_id") and str(getattr(cfg, "scenario_id")).endswith("-variation"):
            raise RuntimeError("variation fail")
        return orig(cfg, dest, overwrite=overwrite)

    with patch.object(m, "write_synthetic_bundle", side_effect=fail_variation):
        from traffictwin.synthetic.whatif_pair import WhatIfPairError

        with pytest.raises(WhatIfPairError) as exc:
            generate_whatif_pair(req, registry_path=reg, workspace_path=ws)
        assert exc.value.code == "variation_generation_failed"
    pid = pair_id_for_request(req)
    assert not (ws / "bundles" / pid).exists()
    assert not reg.exists() or Registry(reg).inspect().run_count == 0


def test_validation_failure_rolls_back(tmp_path: Path) -> None:
    ws, reg = _tmp_workspace(tmp_path)
    req = WhatIfPairRequest(
        baseline_preset="baseline",
        pair_name="rollback-validation",
        experiment_id="exp-demo",
        variation_overrides=WhatIfVariationOverrides(congestion_multiplier=1.9),
    )
    from traffictwin.synthetic import whatif_pair as m
    from traffictwin.ingestion.bundle import validate_bundle as orig_v

    def mock_validate(p: Path) -> object:
        res = orig_v(p)
        if "variation" in str(p) and res.manifest is not None:
            from traffictwin.validation.findings import Severity, ValidationFinding
            from traffictwin.validation.codes import ValidationCode

            res.report.add(
                ValidationFinding(
                    code=ValidationCode.FILE_UNREADABLE,
                    severity=Severity.FATAL,
                    message="forced failure",
                    may_continue=False,
                )
            )
            res.report.finalise()
            return type(res)(
                source=res.source,
                fingerprint=res.fingerprint,
                manifest=None,
                seed=None,
                canonical=res.canonical,
                evidence=res.evidence,
                insufficient_evidence=res.insufficient_evidence,
                report=res.report,
            )
        return res

    with patch.object(m, "validate_bundle", side_effect=mock_validate):
        from traffictwin.synthetic.whatif_pair import WhatIfPairError

        with pytest.raises(WhatIfPairError) as exc:
            generate_whatif_pair(req, registry_path=reg, workspace_path=ws)
        assert exc.value.code == "variation_validation_failed"
    pid = pair_id_for_request(req)
    assert not (ws / "bundles" / pid).exists()
    assert not any((ws / "bundles").glob(".*-staging-*")) if (ws / "bundles").exists() else True


def test_registration_failure_rolls_back(tmp_path: Path) -> None:
    ws, reg = _tmp_workspace(tmp_path)
    req = WhatIfPairRequest(
        baseline_preset="baseline",
        pair_name="rollback-registry",
        experiment_id="exp-demo",
        variation_overrides=WhatIfVariationOverrides(congestion_multiplier=2.1),
    )
    from traffictwin.synthetic import whatif_pair as m

    orig_import = m.import_validated_bundle

    def fail_second(result: Any, registry_path: Path) -> Any:
        # result is BundleValidationResult
        if getattr(getattr(result, "manifest", None), "run", None) and "variation" in getattr(
            result.manifest.run, "seed_id", ""
        ):
            raise m.RegistryConflictError("simulated")
        return orig_import(result, registry_path)

    with patch.object(m, "import_validated_bundle", side_effect=fail_second):
        from traffictwin.synthetic.whatif_pair import WhatIfPairError

        with pytest.raises(WhatIfPairError) as exc:
            generate_whatif_pair(req, registry_path=reg, workspace_path=ws)
        assert exc.value.code == "registration_failed"
    pid = pair_id_for_request(req)
    assert not (ws / "bundles" / pid).exists()
    assert Registry(reg).inspect().run_count == 0


def test_no_partial_pair_remains_on_failure(tmp_path: Path) -> None:
    ws, reg = _tmp_workspace(tmp_path)
    req = WhatIfPairRequest(
        baseline_preset="baseline",
        pair_name="no-partial",
        experiment_id="exp-demo",
        variation_overrides=WhatIfVariationOverrides(congestion_multiplier=2.2),
    )
    from traffictwin.synthetic import whatif_pair as m

    orig = m.write_synthetic_bundle

    def fail(cfg: Any, dest: Path, overwrite: bool = False) -> Path:
        if hasattr(cfg, "scenario_id") and str(getattr(cfg, "scenario_id")).endswith("-variation"):
            raise RuntimeError("fail")
        return orig(cfg, dest, overwrite=overwrite)

    with patch.object(m, "write_synthetic_bundle", side_effect=fail):
        from traffictwin.synthetic.whatif_pair import WhatIfPairError

        with pytest.raises(WhatIfPairError):
            generate_whatif_pair(req, registry_path=reg, workspace_path=ws)
    pid = pair_id_for_request(req)
    # neither baseline nor variation directory should exist
    assert not (ws / "bundles" / pid / "baseline").exists()
    assert not (ws / "bundles" / pid / "variation").exists()


def test_no_partial_registry_state_remains(tmp_path: Path) -> None:
    ws, reg = _tmp_workspace(tmp_path)
    req = WhatIfPairRequest(
        baseline_preset="baseline",
        pair_name="no-registry-partial",
        experiment_id="exp-demo",
        variation_overrides=WhatIfVariationOverrides(congestion_multiplier=2.3),
    )
    from traffictwin.synthetic import whatif_pair as m

    orig_import = m.import_validated_bundle

    def fail(result: Any, registry_path: Path) -> Any:
        if getattr(getattr(result, "manifest", None), "run", None) and getattr(
            result.manifest.run, "seed_id", ""
        ).endswith("-variation"):
            raise RuntimeError("variation registry fail")
        return orig_import(result, registry_path)

    with patch.object(m, "import_validated_bundle", side_effect=fail):
        from traffictwin.synthetic.whatif_pair import WhatIfPairError

        with pytest.raises(WhatIfPairError):
            generate_whatif_pair(req, registry_path=reg, workspace_path=ws)
    assert Registry(reg).inspect().run_count == 0
    assert Registry(reg).inspect().bundle_import_count == 0


def test_synthetic_provenance_preserved(tmp_path: Path) -> None:
    ws, reg = _tmp_workspace(tmp_path)
    req = WhatIfPairRequest(
        baseline_preset="baseline",
        pair_name="provenance-test",
        experiment_id="exp-demo",
        variation_overrides=WhatIfVariationOverrides(
            congestion_multiplier=1.4, incident_enabled=True
        ),
    )
    receipt = generate_whatif_pair(req, registry_path=reg, workspace_path=ws)
    assert receipt.baseline_bundle_path is not None
    assert receipt.variation_bundle_path is not None
    b = validate_bundle(Path(receipt.baseline_bundle_path))
    v = validate_bundle(Path(receipt.variation_bundle_path))
    assert b.manifest is not None and v.manifest is not None
    assert b.manifest.environment.name == "synthetic"
    assert v.manifest.environment.name == "synthetic"
    assert b.manifest.provenance.producer == "TrafficTwin standalone synthetic generator"
    assert receipt.synthetic_label == "SYNTHETIC"
    assert "SYNTHETIC" in receipt.evidence_labels
    assert receipt.receipt_path is not None
    # receipt must not contain absolute private path
    receipt_data = json.loads(
        (ws / "bundles" / receipt.pair_id / "whatif_receipt.json").read_text()
    )
    assert not receipt_data["baseline_bundle_path"].startswith("/")
    assert not receipt_data["variation_bundle_path"].startswith("/")


def test_no_network_provider_sumo_vec_dependency(tmp_path: Path) -> None:
    # Verify the module does not import network/provider/sumo/vec
    import traffictwin.synthetic.whatif_pair as mod
    import pathlib

    source = pathlib.Path(mod.__file__).read_text()
    # should not import httpx, sumolib, vec, provider
    assert "import httpx" not in source
    assert "sumolib" not in source
    assert "vec_env" not in source
    # also ensure deterministic: fingerprint stable
    req = WhatIfPairRequest(
        baseline_preset="baseline", pair_name="no-net", experiment_id="exp-demo"
    )
    fp = request_fingerprint(req)
    assert len(fp) == 64
    # ensure sanitise works
    assert sanitise_pair_name(" My Pair _Test 123 ") == "my-pair-test-123"


def test_pair_receipt_has_no_absolute_private_path(tmp_path: Path) -> None:
    ws, reg = _tmp_workspace(tmp_path)
    req = WhatIfPairRequest(
        baseline_preset="baseline",
        pair_name="private-path-test",
        experiment_id="exp-demo",
        variation_overrides=WhatIfVariationOverrides(congestion_multiplier=1.3),
    )
    receipt = generate_whatif_pair(req, registry_path=reg, workspace_path=ws)
    # receipt JSON on disk must not contain absolute private path
    data = json.loads((ws / "bundles" / receipt.pair_id / "whatif_receipt.json").read_text())
    assert not data["baseline_bundle_path"].startswith(str(ws))
    assert not data["variation_bundle_path"].startswith("/")
    # also check receipt's baseline_bundle_path (UI path) is absolute for UI but receipt_path is relative
    assert receipt.receipt_path is not None
    assert not receipt.receipt_path.startswith("/")
    # but the receipt's baseline_bundle_path for UI is absolute (session needs it), but publication-safe receipt is relative
    assert receipt.baseline_bundle_path is not None
    assert Path(receipt.baseline_bundle_path).is_absolute()
