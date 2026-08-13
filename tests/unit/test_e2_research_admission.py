"""Focused tests for Lane 04 — fail-closed source-bound admission."""

from __future__ import annotations

import copy
import json
from importlib import resources

import pytest
from pydantic import ValidationError

from traffictwin.evidence_admission.e2_research import (
    ADMISSION_MODE,
    EXPECTED_PACKAGE_FINGERPRINT,
    STANDING,
    E2ResearchAdmissionError,
    E2ResearchAdmissionReceipt,
    admit_e2_research,
    load_admitted_builtin_e2_research,
)
from traffictwin.experiments.e2_research_artifact import (
    builtin_e2_research_json,
    load_builtin_e2_research,
)
from traffictwin.experiments.e2_research_evidence import E2ResearchEvidencePackage


def _valid_pkg() -> E2ResearchEvidencePackage:
    return load_builtin_e2_research()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_admit_valid_package_returns_admitted_research_receipt() -> None:
    pkg = _valid_pkg()
    receipt = admit_e2_research(pkg)
    assert receipt.standing == "OWNER-AUTHORIZED PRODUCT ADMISSION"
    assert receipt.admission_mode == "ADMITTED_RESEARCH"
    assert receipt.standing == STANDING
    assert receipt.admission_mode == ADMISSION_MODE
    assert receipt.replication_unit == "fleet_draw"
    assert receipt.evaluator_seed == 0
    assert "SUPERVISOR APPROVED" not in str(receipt.standing)
    assert "RANDY CONFIRMED" not in str(receipt.standing)
    assert receipt.research_heads["e2b"] == "fe2ed4e9bd9043b19b96a5f179390db629b01ccb"
    assert (
        receipt.manifests["e2d"]
        == "f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740"
    )
    assert (
        receipt.actor_sha256 == "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208"
    )
    assert (
        receipt.trace_sha256 == "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"
    )
    assert receipt.package_fingerprint == EXPECTED_PACKAGE_FINGERPRINT
    assert receipt.package_fingerprint == pkg.fingerprint()
    assert receipt.receipt_fingerprint == receipt.computed_fingerprint()
    receipt.verify()
    dump = json.dumps(receipt.model_dump(mode="json"))
    assert "/Users/" not in dump
    assert "secret" not in dump.lower()
    for key in receipt.model_dump(mode="json"):
        assert key.lower() not in ("timestamp", "created_at", "scientific_timestamp")


def test_load_admitted_builtin_returns_tuple() -> None:
    pkg, receipt = load_admitted_builtin_e2_research()
    assert isinstance(pkg, E2ResearchEvidencePackage)
    assert receipt.standing == STANDING
    assert receipt.admission_mode == ADMISSION_MODE
    receipt.verify()
    receipt2 = admit_e2_research(pkg)
    assert receipt2.receipt_fingerprint == receipt.receipt_fingerprint
    assert receipt2.package_fingerprint == receipt.package_fingerprint
    assert receipt2.package_fingerprint == EXPECTED_PACKAGE_FINGERPRINT


def test_receipt_is_deterministic() -> None:
    pkg = _valid_pkg()
    r1 = admit_e2_research(pkg)
    r2 = admit_e2_research(copy.deepcopy(pkg))
    assert r1.receipt_fingerprint == r2.receipt_fingerprint
    assert r1.package_fingerprint == r2.package_fingerprint


def test_receipt_is_path_and_secret_free() -> None:
    pkg = _valid_pkg()
    receipt = admit_e2_research(pkg)
    text = json.dumps(receipt.model_dump(mode="json"))
    assert "/Users/" not in text
    assert "/home/" not in text
    assert "secret" not in text.lower()
    assert "credential" not in text.lower()


def test_receipt_has_no_timestamp_field() -> None:
    pkg = _valid_pkg()
    receipt = admit_e2_research(pkg)
    fields = set(receipt.model_fields.keys())
    for bad in ("timestamp", "created_at", "scientific_timestamp", "admitted_at", "generated_at"):
        assert bad not in fields
    dump = receipt.model_dump(mode="json")
    for bad in ("timestamp", "created_at"):
        assert bad not in dump


def test_standing_exact_string() -> None:
    assert STANDING == "OWNER-AUTHORIZED PRODUCT ADMISSION"
    pkg = _valid_pkg()
    receipt = admit_e2_research(pkg)
    assert receipt.standing == "OWNER-AUTHORIZED PRODUCT ADMISSION"
    assert "SUPERVISOR" not in receipt.standing
    assert "RANDY" not in receipt.standing


def test_builtin_json_deterministic_and_resource_accessible() -> None:
    a = builtin_e2_research_json()
    b = builtin_e2_research_json()
    assert a == b
    ref = resources.files("traffictwin.resources.research").joinpath("e2_resource_strategy_v1.json")
    text_via_resources = ref.read_text(encoding="utf-8")
    assert a == text_via_resources
    pkg = load_builtin_e2_research()
    assert pkg.fingerprint() == EXPECTED_PACKAGE_FINGERPRINT


def test_package_fingerprint_is_deterministic_and_hex() -> None:
    pkg = _valid_pkg()
    r1 = admit_e2_research(pkg)
    r2 = admit_e2_research(copy.deepcopy(pkg))
    assert r1.package_fingerprint == r2.package_fingerprint
    assert len(r1.package_fingerprint) == 64
    assert all(c in "0123456789abcdef" for c in r1.package_fingerprint)


def test_receipt_frozen_mutation_raises() -> None:
    pkg = _valid_pkg()
    receipt = admit_e2_research(pkg)
    with pytest.raises((ValidationError, ValueError, TypeError, AttributeError)):
        receipt.standing = "SUPERVISOR APPROVED"  # type: ignore[misc, assignment]


# ---------------------------------------------------------------------------
# Fail-closed — mutating any evidence identity or value
# ---------------------------------------------------------------------------


def _mutate_via_dict(mutator: object) -> None:
    # helper to mutate json dict and expect validation to fail
    data: dict[str, object] = json.loads(builtin_e2_research_json())
    assert callable(mutator)
    mutator(data)
    text = json.dumps(data)
    with pytest.raises((E2ResearchAdmissionError, ValueError, ValidationError)):
        # Try both artifact validation and admission
        from traffictwin.experiments.e2_research_artifact import validate_e2_research_artifact

        pkg = validate_e2_research_artifact(text)
        admit_e2_research(pkg)


def test_mutation_rejects_e2b_head() -> None:
    def mut(d: dict[str, object]) -> None:
        sd = d["source_identities"]
        assert isinstance(sd, dict)
        rh = sd["research_heads"]
        assert isinstance(rh, dict)
        rh["e2b"] = "0" * 40

    _mutate_via_dict(mut)


def test_mutation_rejects_e2c_head() -> None:
    def mut(d: dict[str, object]) -> None:
        sd = d["source_identities"]
        assert isinstance(sd, dict)
        rh = sd["research_heads"]
        assert isinstance(rh, dict)
        rh["e2c"] = "0" * 40

    _mutate_via_dict(mut)


def test_mutation_rejects_e2d_head() -> None:
    def mut(d: dict[str, object]) -> None:
        sd = d["source_identities"]
        assert isinstance(sd, dict)
        rh = sd["research_heads"]
        assert isinstance(rh, dict)
        rh["e2d"] = "0" * 40

    _mutate_via_dict(mut)


def test_mutation_rejects_e2b_manifest() -> None:
    def mut(d: dict[str, object]) -> None:
        sd = d["source_identities"]
        assert isinstance(sd, dict)
        mm = sd["manifest_sha256_by_study"]
        assert isinstance(mm, dict)
        mm["e2b"] = "0" * 64

    _mutate_via_dict(mut)


def test_mutation_rejects_e2c_manifest() -> None:
    def mut(d: dict[str, object]) -> None:
        sd = d["source_identities"]
        assert isinstance(sd, dict)
        mm = sd["manifest_sha256_by_study"]
        assert isinstance(mm, dict)
        mm["e2c"] = "0" * 64

    _mutate_via_dict(mut)


def test_mutation_rejects_e2d_manifest() -> None:
    def mut(d: dict[str, object]) -> None:
        sd = d["source_identities"]
        assert isinstance(sd, dict)
        mm = sd["manifest_sha256_by_study"]
        assert isinstance(mm, dict)
        mm["e2d"] = "0" * 64

    _mutate_via_dict(mut)


def test_mutation_rejects_actor_hash() -> None:
    def mut(d: dict[str, object]) -> None:
        sd = d["source_identities"]
        assert isinstance(sd, dict)
        actor = sd["actor"]
        assert isinstance(actor, dict)
        actor["sha256"] = "0" * 64

    _mutate_via_dict(mut)


def test_mutation_rejects_trace_hash() -> None:
    def mut(d: dict[str, object]) -> None:
        sd = d["source_identities"]
        assert isinstance(sd, dict)
        trace = sd["trace"]
        assert isinstance(trace, dict)
        trace["sha256"] = "f" * 64

    _mutate_via_dict(mut)


def test_mutation_rejects_replication_unit() -> None:
    def mut(d: dict[str, object]) -> None:
        d["replication_unit"] = "task"

    _mutate_via_dict(mut)


def test_mutation_rejects_evaluator_seed() -> None:
    def mut(d: dict[str, object]) -> None:
        d["evaluator_seed"] = 1

    _mutate_via_dict(mut)


def test_mutation_rejects_e2b_off() -> None:
    def mut(d: dict[str, object]) -> None:
        obs_any = d.get("observations")
        assert isinstance(obs_any, list)
        for obs_any_item in obs_any:
            assert isinstance(obs_any_item, dict)
            obs: dict[str, object] = obs_any_item
            if obs.get("figure_id") == "fig1_e2b_offered_attainment_off":
                obs["value"] = 0.0

    _mutate_via_dict(mut)


def test_mutation_rejects_e2b_jsq() -> None:
    def mut(d: dict[str, object]) -> None:
        obs_any = d.get("observations")
        assert isinstance(obs_any, list)
        for obs_any_item in obs_any:
            assert isinstance(obs_any_item, dict)
            obs: dict[str, object] = obs_any_item
            if obs.get("figure_id") == "fig1_e2b_offered_attainment_jsq":
                obs["value"] = 0.0

    _mutate_via_dict(mut)


def test_mutation_rejects_e2b_ingress() -> None:
    def mut(d: dict[str, object]) -> None:
        obs_any = d.get("observations")
        assert isinstance(obs_any, list)
        for obs_any_item in obs_any:
            assert isinstance(obs_any_item, dict)
            obs: dict[str, object] = obs_any_item
            if obs.get("figure_id") == "fig1_e2b_offered_attainment_ingress_dla":
                obs["value"] = 0.0

    _mutate_via_dict(mut)


def test_mutation_rejects_e2b_dla() -> None:
    def mut(d: dict[str, object]) -> None:
        obs_any = d.get("observations")
        assert isinstance(obs_any, list)
        for obs_any_item in obs_any:
            assert isinstance(obs_any_item, dict)
            obs: dict[str, object] = obs_any_item
            if obs.get("figure_id") == "fig1_e2b_offered_attainment_dla":
                obs["value"] = 0.0

    _mutate_via_dict(mut)


def test_mutation_rejects_e2c_per_seed() -> None:
    def mut(d: dict[str, object]) -> None:
        pd_list = d.get("paired_differences")
        assert isinstance(pd_list, list)
        for pd in pd_list:
            assert isinstance(pd, dict)
            if pd.get("comparison_id") == "e2c_dla_minus_ingress":
                vals = pd.get("per_seed_values")
                assert isinstance(vals, list)
                vals[0] = 0.0

    _mutate_via_dict(mut)


def test_mutation_rejects_e2c_mean() -> None:
    def mut(d: dict[str, object]) -> None:
        ds_list = d.get("declared_summaries")
        assert isinstance(ds_list, list)
        for ds in ds_list:
            assert isinstance(ds, dict)
            if ds.get("comparison_id") == "e2c_dla_minus_ingress":
                ds["mean"] = 0.0

    _mutate_via_dict(mut)


def test_mutation_rejects_e2c_ci_lower() -> None:
    def mut(d: dict[str, object]) -> None:
        ds_list = d.get("declared_summaries")
        assert isinstance(ds_list, list)
        for ds in ds_list:
            assert isinstance(ds, dict)
            if ds.get("comparison_id") == "e2c_dla_minus_ingress":
                ds["lower"] = 0.0

    _mutate_via_dict(mut)


def test_mutation_rejects_e2c_ci_upper() -> None:
    def mut(d: dict[str, object]) -> None:
        ds_list = d.get("declared_summaries")
        assert isinstance(ds_list, list)
        for ds in ds_list:
            assert isinstance(ds, dict)
            if ds.get("comparison_id") == "e2c_dla_minus_ingress":
                ds["upper"] = 0.0

    _mutate_via_dict(mut)


def test_mutation_rejects_e2d_per_seed() -> None:
    def mut(d: dict[str, object]) -> None:
        pd_list = d.get("paired_differences")
        assert isinstance(pd_list, list)
        for pd in pd_list:
            assert isinstance(pd, dict)
            if pd.get("comparison_id") == "e2d_per_task_minus_ingress":
                vals = pd.get("per_seed_values")
                assert isinstance(vals, list)
                vals[0] = 0.0

    _mutate_via_dict(mut)


def test_mutation_rejects_e2d_mean() -> None:
    def mut(d: dict[str, object]) -> None:
        ds_list = d.get("declared_summaries")
        assert isinstance(ds_list, list)
        for ds in ds_list:
            assert isinstance(ds, dict)
            if ds.get("comparison_id") == "e2d_per_task_minus_ingress":
                ds["mean"] = 0.0

    _mutate_via_dict(mut)


def test_mutation_rejects_e2d_ci_lower() -> None:
    def mut(d: dict[str, object]) -> None:
        ds_list = d.get("declared_summaries")
        assert isinstance(ds_list, list)
        for ds in ds_list:
            assert isinstance(ds, dict)
            if ds.get("comparison_id") == "e2d_per_task_minus_ingress":
                ds["lower"] = 0.0

    _mutate_via_dict(mut)


def test_mutation_rejects_e2d_ci_upper() -> None:
    def mut(d: dict[str, object]) -> None:
        ds_list = d.get("declared_summaries")
        assert isinstance(ds_list, list)
        for ds in ds_list:
            assert isinstance(ds, dict)
            if ds.get("comparison_id") == "e2d_per_task_minus_ingress":
                ds["upper"] = 0.0

    _mutate_via_dict(mut)


def test_mutation_rejects_vs_common_mean() -> None:
    def mut(d: dict[str, object]) -> None:
        ds_list = d.get("declared_summaries")
        assert isinstance(ds_list, list)
        for ds in ds_list:
            assert isinstance(ds, dict)
            if ds.get("comparison_id") == "e2d_per_task_minus_dla":
                ds["mean"] = 0.0

    _mutate_via_dict(mut)


def test_mutation_rejects_vs_common_ci_lower() -> None:
    def mut(d: dict[str, object]) -> None:
        ds_list = d.get("declared_summaries")
        assert isinstance(ds_list, list)
        for ds in ds_list:
            assert isinstance(ds, dict)
            if ds.get("comparison_id") == "e2d_per_task_minus_dla":
                ds["lower"] = 0.0

    _mutate_via_dict(mut)


def test_mutation_rejects_vs_common_ci_upper() -> None:
    def mut(d: dict[str, object]) -> None:
        ds_list = d.get("declared_summaries")
        assert isinstance(ds_list, list)
        for ds in ds_list:
            assert isinstance(ds, dict)
            if ds.get("comparison_id") == "e2d_per_task_minus_dla":
                ds["upper"] = 0.0

    _mutate_via_dict(mut)


def test_mutation_changes_package_fingerprint() -> None:
    pkg = _valid_pkg()
    original_fp = pkg.fingerprint()
    data_any: dict[str, object] = json.loads(builtin_e2_research_json())
    data = data_any
    # mutate tiny
    obs_list_any = data.get("observations")
    assert isinstance(obs_list_any, list)
    for obs_any in obs_list_any:
        assert isinstance(obs_any, dict)
        obs: dict[str, object] = obs_any
        if obs.get("figure_id") == "fig1_e2b_offered_attainment_off":
            val = obs.get("value")
            assert isinstance(val, (int, float))
            obs["value"] = float(val) + 0.0001
            break
    text = json.dumps(data)
    with pytest.raises((E2ResearchAdmissionError, ValueError, ValidationError)):
        from traffictwin.experiments.e2_research_artifact import validate_e2_research_artifact

        mutated_pkg = validate_e2_research_artifact(text)
        # fingerprint must differ if validation somehow passed
        assert mutated_pkg.fingerprint() != original_fp
        admit_e2_research(mutated_pkg)


def test_swapped_head_binding_fails() -> None:
    pkg = _valid_pkg()
    e2b_head = pkg.source_identities.research_heads.e2b
    e2c_head = pkg.source_identities.research_heads.e2c
    new_heads = pkg.source_identities.research_heads.model_copy(
        update={"e2b": e2c_head, "e2c": e2b_head}
    )
    new_id = pkg.source_identities.model_copy(update={"research_heads": new_heads})
    swapped = pkg.model_copy(update={"source_identities": new_id})
    with pytest.raises((E2ResearchAdmissionError, ValueError, ValidationError)):
        admit_e2_research(swapped)


def test_swapped_manifest_binding_fails() -> None:
    pkg = _valid_pkg()
    mans = pkg.source_identities.manifest_sha256_by_study
    e2b_m = mans["e2b"]
    e2c_m = mans["e2c"]
    new_mans = dict(mans)
    new_mans["e2b"] = e2c_m
    new_mans["e2c"] = e2b_m
    new_id = pkg.source_identities.model_copy(update={"manifest_sha256_by_study": new_mans})
    swapped = pkg.model_copy(update={"source_identities": new_id})
    with pytest.raises((E2ResearchAdmissionError, ValueError, ValidationError)):
        admit_e2_research(swapped)


def test_path_injection_fails() -> None:
    data = json.loads(builtin_e2_research_json())
    lim = data.get("limitations")
    assert isinstance(lim, list)
    data["limitations"] = list(lim) + ["/Users/evil path"]
    text = json.dumps(data)
    with pytest.raises((E2ResearchAdmissionError, ValueError, ValidationError)):
        from traffictwin.experiments.e2_research_artifact import validate_e2_research_artifact

        pkg = validate_e2_research_artifact(text)
        admit_e2_research(pkg)


def test_secret_injection_fails() -> None:
    data = json.loads(builtin_e2_research_json())
    lim2 = data.get("limitations")
    assert isinstance(lim2, list)
    data["limitations"] = list(lim2) + ["api_key: secret123"]
    text = json.dumps(data)
    with pytest.raises((E2ResearchAdmissionError, ValueError, ValidationError)):
        from traffictwin.experiments.e2_research_artifact import validate_e2_research_artifact

        pkg = validate_e2_research_artifact(text)
        admit_e2_research(pkg)


def test_wrong_type_fails() -> None:
    with pytest.raises((E2ResearchAdmissionError, ValueError, TypeError, ValidationError)):
        admit_e2_research(None)  # type: ignore[arg-type]
    with pytest.raises((E2ResearchAdmissionError, ValueError, TypeError)):
        admit_e2_research({})  # type: ignore[arg-type]
    with pytest.raises((E2ResearchAdmissionError, ValueError, TypeError)):
        admit_e2_research("not a package")  # type: ignore[arg-type]


def test_missing_builtin_resource_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    import traffictwin.evidence_admission.e2_research as mod

    def fake_load() -> E2ResearchEvidencePackage:
        raise FileNotFoundError("missing resource")

    monkeypatch.setattr(mod, "load_builtin_e2_research", fake_load)
    with pytest.raises(E2ResearchAdmissionError):
        load_admitted_builtin_e2_research()


def test_admission_spec_missing_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    pkg = _valid_pkg()
    import traffictwin.evidence_admission.e2_research as mod

    def fake_files(pkg: str) -> object:
        class FakeRef:
            def joinpath(self, _name: str) -> FakeRef:
                return self

            def read_text(self, encoding: str = "utf-8") -> str:
                raise FileNotFoundError("spec missing")

        return FakeRef()

    monkeypatch.setattr(mod.resources, "files", fake_files)  # type: ignore[attr-defined]
    with pytest.raises(E2ResearchAdmissionError):
        admit_e2_research(pkg)


# ---------------------------------------------------------------------------
# Receipt tampering — mutating any receipt field fails closed
# ---------------------------------------------------------------------------


def test_receipt_field_mutation_fails_verify() -> None:
    pkg = _valid_pkg()
    receipt = admit_e2_research(pkg)
    tampered_dict = receipt.model_dump(mode="json")
    tampered_dict["standing"] = "SUPERVISOR APPROVED"
    with pytest.raises((ValidationError, ValueError, E2ResearchAdmissionError)):
        E2ResearchAdmissionReceipt.model_validate(tampered_dict)


def test_receipt_fingerprint_tamper_fails() -> None:
    pkg = _valid_pkg()
    receipt = admit_e2_research(pkg)
    tampered = receipt.model_dump(mode="json")
    tampered["receipt_fingerprint"] = "0" * 64
    with pytest.raises((ValidationError, ValueError, E2ResearchAdmissionError)):
        r = E2ResearchAdmissionReceipt.model_validate(tampered)
        r.verify()


def test_receipt_replication_unit_mutation_fails() -> None:
    pkg = _valid_pkg()
    receipt = admit_e2_research(pkg)
    d = receipt.model_dump(mode="json")
    d["replication_unit"] = "random_seed"
    with pytest.raises((ValidationError, ValueError, E2ResearchAdmissionError)):
        E2ResearchAdmissionReceipt.model_validate(d)


def test_receipt_evaluator_seed_mutation_fails() -> None:
    pkg = _valid_pkg()
    receipt = admit_e2_research(pkg)
    d = receipt.model_dump(mode="json")
    d["evaluator_seed"] = 1
    with pytest.raises((ValidationError, ValueError, E2ResearchAdmissionError)):
        E2ResearchAdmissionReceipt.model_validate(d)


def test_receipt_head_mutation_fails() -> None:
    pkg = _valid_pkg()
    receipt = admit_e2_research(pkg)
    d = receipt.model_dump(mode="json")
    heads_any = d.get("research_heads")
    assert isinstance(heads_any, dict)
    heads_any["e2b"] = "0" * 40
    with pytest.raises((ValidationError, ValueError, E2ResearchAdmissionError)):
        r = E2ResearchAdmissionReceipt.model_validate(d)
        r.verify()


def test_receipt_manifest_mutation_fails() -> None:
    pkg = _valid_pkg()
    receipt = admit_e2_research(pkg)
    d = receipt.model_dump(mode="json")
    mans_any = d.get("manifests")
    assert isinstance(mans_any, dict)
    mans_any["e2c"] = "0" * 64
    with pytest.raises((ValidationError, ValueError, E2ResearchAdmissionError)):
        r = E2ResearchAdmissionReceipt.model_validate(d)
        r.verify()


def test_receipt_package_fingerprint_mutation_fails() -> None:
    pkg = _valid_pkg()
    receipt = admit_e2_research(pkg)
    d = receipt.model_dump(mode="json")
    d["package_fingerprint"] = "0" * 64
    with pytest.raises((ValidationError, ValueError, E2ResearchAdmissionError)):
        r = E2ResearchAdmissionReceipt.model_validate(d)
        r.verify()


def test_admission_mode_only_on_exact_match() -> None:
    pkg = _valid_pkg()
    receipt = admit_e2_research(pkg)
    assert receipt.admission_mode == "ADMITTED_RESEARCH"
    data_any2: dict[str, object] = json.loads(builtin_e2_research_json())
    data2b: dict[str, object] = data_any2
    obs_list_any2 = data2b.get("observations")
    assert isinstance(obs_list_any2, list)
    for obs_any2 in obs_list_any2:
        assert isinstance(obs_any2, dict)
        obs2: dict[str, object] = obs_any2
        if obs2.get("figure_id") == "fig1_e2b_offered_attainment_off":
            val2 = obs2.get("value")
            assert isinstance(val2, (int, float))
            obs2["value"] = float(val2) + 1.0
            break
    data = data2b
    text = json.dumps(data)
    with pytest.raises((E2ResearchAdmissionError, ValueError, ValidationError)):
        from traffictwin.experiments.e2_research_artifact import validate_e2_research_artifact

        bad_pkg = validate_e2_research_artifact(text)
        bad_receipt = admit_e2_research(bad_pkg)
        assert bad_receipt.admission_mode == "ADMITTED_RESEARCH"


def test_json_spec_is_path_free_and_valid() -> None:
    p = resources.files("traffictwin.evidence_admission").joinpath("e2_research_admission_v1.json")
    text2 = p.read_text(encoding="utf-8")
    data2: dict[str, object] = json.loads(text2)
    data = data2
    assert data.get("standing") == "OWNER-AUTHORIZED PRODUCT ADMISSION"
    assert data.get("admission_mode") == "ADMITTED_RESEARCH"
    assert "/Users/" not in text2
    cleaned = text2.lower().replace("secret_free", "")
    assert "secret" not in cleaned
    exp_any = data.get("expected")
    assert isinstance(exp_any, dict)
    exp: dict[str, object] = exp_any
    heads_any = exp.get("research_heads")
    assert isinstance(heads_any, dict)
    assert heads_any.get("e2b") == "fe2ed4e9bd9043b19b96a5f179390db629b01ccb"
    mans_any = exp.get("manifests")
    assert isinstance(mans_any, dict)
    assert mans_any.get("e2d") == "f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740"
    assert exp.get("package_fingerprint") == EXPECTED_PACKAGE_FINGERPRINT


def test_admission_spec_missing_package_fingerprint_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pkg = _valid_pkg()
    import traffictwin.evidence_admission.e2_research as mod

    p = resources.files("traffictwin.evidence_admission").joinpath("e2_research_admission_v1.json")
    base: dict[str, object] = json.loads(p.read_text(encoding="utf-8"))
    expected_any = base.get("expected")
    assert isinstance(expected_any, dict)
    expected: dict[str, object] = dict(expected_any)
    expected.pop("package_fingerprint", None)
    mutated = dict(base)
    mutated["expected"] = expected
    mutated_text = json.dumps(mutated)

    def fake_files(pkg_name: str) -> object:
        class FakeRef:
            def joinpath(self, _name: str) -> FakeRef:
                return self

            def read_text(self, encoding: str = "utf-8") -> str:
                return mutated_text

        return FakeRef()

    monkeypatch.setattr(mod.resources, "files", fake_files)  # type: ignore[attr-defined]
    with pytest.raises(E2ResearchAdmissionError):
        admit_e2_research(pkg)
    with pytest.raises(E2ResearchAdmissionError):
        load_admitted_builtin_e2_research()


def test_admission_spec_non_string_package_fingerprint_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pkg = _valid_pkg()
    import traffictwin.evidence_admission.e2_research as mod

    p = resources.files("traffictwin.evidence_admission").joinpath("e2_research_admission_v1.json")
    base2: dict[str, object] = json.loads(p.read_text(encoding="utf-8"))
    expected_any2 = base2.get("expected")
    assert isinstance(expected_any2, dict)
    expected2: dict[str, object] = dict(expected_any2)
    expected2["package_fingerprint"] = 123456
    mutated2 = dict(base2)
    mutated2["expected"] = expected2
    mutated_text2 = json.dumps(mutated2)

    def fake_files2(pkg_name: str) -> object:
        class FakeRef:
            def joinpath(self, _name: str) -> FakeRef:
                return self

            def read_text(self, encoding: str = "utf-8") -> str:
                return mutated_text2

        return FakeRef()

    monkeypatch.setattr(mod.resources, "files", fake_files2)  # type: ignore[attr-defined]
    with pytest.raises(E2ResearchAdmissionError):
        admit_e2_research(pkg)
