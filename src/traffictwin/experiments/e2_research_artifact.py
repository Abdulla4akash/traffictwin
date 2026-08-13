# ruff: noqa: E501
"""Canonical portable E2 research artifact — Lane 03.

Provides wheel-portable built-in JSON via importlib.resources and a
standalone validator that first delegates to the Lane 02 strict loader
then enforces every pinned identity and result target. No fallback
schema, no private path, timestamp, secret, or mutation normalization.
"""

from __future__ import annotations

import json
import re
from importlib import resources

from traffictwin.experiments.e2_research_evidence import (
    E2ResearchEvidencePackage,
    load_e2_research_evidence_json,
)

_RESOURCE_PACKAGE = "traffictwin.resources.research"
_RESOURCE_NAME = "e2_resource_strategy_v1.json"

_PINNED_BASE_SHA = "bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6"
_PINNED_ACTOR_SHA = "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208"
_PINNED_TRACE_SHA = "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"
_PINNED_HEADS: dict[str, str] = {
    "e2b": "fe2ed4e9bd9043b19b96a5f179390db629b01ccb",
    "e2c": "1a08d6e148a1e8c430da39c3d575eda3f8ea5929",
    "e2d": "80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761",
}
_PINNED_MANIFESTS: dict[str, str] = {
    "e2b": "9383ec767dccf2f390b498e0c20283a74cd64fa521d6137fe23ce38d0022af91",
    "e2c": "fcaf2ee34b68ca4e4ef2e088d72ce2c5a410cf66ff9934a451fd8047204c480a",
    "e2d": "f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740",
}
_PINNED_REPLICATION_UNIT = "fleet_draw"
_PINNED_EVALUATOR_SEED = 0

# Pinned observation values: figure_id -> value
_PINNED_OBSERVATION_VALUES: dict[str, float] = {
    "fig1_e2b_offered_attainment_off": 0.683619229,
    "fig1_e2b_offered_attainment_jsq": 0.675681775,
    "fig1_e2b_offered_attainment_dla": 0.694939919,
    "fig1_e2b_offered_attainment_ingress_dla": 0.715773211,
    "fig2_e2c_dla_minus_ingress_seed1": -0.022097034972,
    "fig2_e2c_dla_minus_ingress_seed2": -0.020519134179,
    "fig2_e2c_dla_minus_ingress_seed3": -0.021447383092,
    "fig2_e2c_dla_minus_ingress_seed4": -0.020825491499,
    "fig3_e2d_per_task_minus_ingress_seed1": 0.004636732564,
    "fig3_e2d_per_task_minus_ingress_seed2": 0.005867285642,
    "fig3_e2d_per_task_minus_ingress_seed3": 0.005071796666,
    "fig3_e2d_per_task_minus_ingress_seed4": 0.005509919752,
}

_PINNED_PAIRED_DIFFERENCES: dict[str, list[float]] = {
    "e2c_dla_minus_ingress": [-0.022097034972, -0.020519134179, -0.021447383092, -0.020825491499],
    "e2d_per_task_minus_ingress": [0.004636732564, 0.005867285642, 0.005071796666, 0.005509919752],
    "e2d_per_task_minus_dla": [0.026733767536, 0.026386419821, 0.026519179758, 0.026335411251],
}

_PINNED_DECLARED_SUMMARIES: dict[str, dict[str, float | None]] = {
    "e2c_dla_minus_ingress": {
        "mean": -0.021222260935,
        "lower": -0.02233525407,
        "upper": -0.0201092678,
    },
    "e2d_per_task_minus_ingress": {
        "mean": 0.005271433656,
        "lower": 0.004422143925,
        "upper": 0.006120723387,
    },
    "e2d_per_task_minus_dla": {
        "mean": 0.026493694591,
        "lower": 0.026210763951,
        "upper": 0.026776625232,
    },
}

_PINNED_TASK_LIFECYCLE: dict[str, int] = {
    "offered": 13076234,
    "admitted": 10594205,
    "rejected_total": 2482029,
    "forwarded": 600885,
    "deadline_success": 9475948,
}

# Owner-required limitations — each phrase must appear verbatim (case-insensitive)
# in at least one limitation entry as explicit searchable wording. Do not rely
# on inference across an unrelated combined sentence.
_REQUIRED_LIMITATION_SUBSTRINGS: tuple[str, ...] = (
    "manchester incident hour",
    "four matched provisional fleet draws",
    "evaluator seed 0",
    "fixed 1x",
    "zero backhaul",
    "inherited deadline gate",
    "frozen vehicle actor",
    "does not observe current rsu load",
    "does not choose execution rsu",
    "e2b one-draw descriptive",
    "reuses already-observed e2c controls",
    "not independent held-out replication",
    "accounting records, not independent replicates",
    "no ordinary/free-flow control",
    "physical return is not independently instrumented",
)

# Owner-required non-claims — each phrase must appear verbatim (case-insensitive)
# in at least one non_claim entry as explicit searchable wording.
_REQUIRED_NONCLAIM_SUBSTRINGS: tuple[str, ...] = (
    "kubernetes deployment",
    "cluster orchestration",
    "autonomous infrastructure control",
    "learned infrastructure placement",
    "learned rsu scheduler",
    "mappo choosing execution rsu",
    "mappo observing current rsu load",
    "manchester-wide",
    "population-wide",
    "physical rsu deployment",
    "physical result-return verification",
    "universal jsq superiority",
    "universal per_task_dla superiority",
    "free-flow validation",
    "independent held-out e2d replication",
    "task-level statistical replication",
    "zero-backhaul realism",
)

_TOL = 1e-12


def builtin_e2_research_json() -> str:
    """Return the exact built-in JSON text via importlib.resources."""
    ref = resources.files(_RESOURCE_PACKAGE).joinpath(_RESOURCE_NAME)
    return ref.read_text(encoding="utf-8")


def _require_close(actual: float, expected: float, name: str) -> None:
    if abs(float(actual) - float(expected)) > _TOL:
        raise ValueError(f"pinned value mismatch for {name}: expected {expected!r}, got {actual!r}")


def validate_e2_research_artifact(text: str) -> E2ResearchEvidencePackage:
    """Validate *text* as canonical E2 artifact and return typed package.

    First uses the Lane 02 schema/loader, then strictly verifies every
    pinned identity and result target. Rejects private paths, secrets,
    mutation of any pinned value, and malformed schema.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("artifact text must be non-empty string")
    if "/Users/" in text:
        raise ValueError("artifact contains forbidden absolute path '/Users/'")
    if re.search(r"[A-Z]:\\", text):
        raise ValueError("artifact contains forbidden Windows absolute path")
    # Early JSON parse for forbidden content check
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"artifact is not valid JSON: {exc}") from exc

    # First: strict Lane 02 schema validation
    pkg = load_e2_research_evidence_json(text)

    # Second: pinned identity verification
    if pkg.source_identities.base_sha != _PINNED_BASE_SHA:
        raise ValueError(
            f"pinned base_sha mismatch: expected {_PINNED_BASE_SHA!r}, got {pkg.source_identities.base_sha!r}"
        )
    if pkg.source_identities.actor.sha256 != _PINNED_ACTOR_SHA:
        raise ValueError(f"pinned actor sha mismatch: expected {_PINNED_ACTOR_SHA!r}")
    if pkg.source_identities.trace.sha256 != _PINNED_TRACE_SHA:
        raise ValueError(f"pinned trace sha mismatch: expected {_PINNED_TRACE_SHA!r}")
    for k, expected_head in _PINNED_HEADS.items():
        actual = getattr(pkg.source_identities.research_heads, k)
        if actual != expected_head:
            raise ValueError(
                f"pinned research head mismatch for {k}: expected {expected_head!r}, got {actual!r}"
            )
    for k, expected_manifest in _PINNED_MANIFESTS.items():
        actual = pkg.source_identities.manifest_sha256_by_study.get(k)
        if actual != expected_manifest:
            raise ValueError(
                f"pinned manifest mismatch for {k}: expected {expected_manifest!r}, got {actual!r}"
            )
    if pkg.replication_unit != _PINNED_REPLICATION_UNIT:
        raise ValueError(
            f"pinned replication_unit mismatch: expected {_PINNED_REPLICATION_UNIT!r}, got {pkg.replication_unit!r}"
        )
    if pkg.evaluator_seed != _PINNED_EVALUATOR_SEED:
        raise ValueError(
            f"pinned evaluator_seed mismatch: expected {_PINNED_EVALUATOR_SEED!r}, got {pkg.evaluator_seed!r}"
        )
    if pkg.source_identities.actor.observes_current_rsu_load is not False:
        raise ValueError("pinned actor observes_current_rsu_load must be false")
    if pkg.source_identities.actor.selects_execution_rsu is not False:
        raise ValueError("pinned actor selects_execution_rsu must be false")
    if pkg.source_identities.actor.training_seed != 100:
        raise ValueError("pinned actor training_seed must be 100")

    # Pinned observation values
    obs_by_id = {o.figure_id: o for o in pkg.observations}
    for fid, expected_val in _PINNED_OBSERVATION_VALUES.items():
        if fid not in obs_by_id:
            raise ValueError(f"missing pinned observation {fid!r}")
        _require_close(float(obs_by_id[fid].value), expected_val, f"observation {fid}")

    # Pinned paired differences
    pd_by_id = {pd.comparison_id: pd for pd in pkg.paired_differences}
    for cid, expected_list in _PINNED_PAIRED_DIFFERENCES.items():
        if cid not in pd_by_id:
            raise ValueError(f"missing pinned paired_difference {cid!r}")
        actual_list = pd_by_id[cid].per_seed_values
        if len(actual_list) != len(expected_list):
            raise ValueError(f"pinned paired_difference length mismatch for {cid}")
        for idx, (a, e) in enumerate(zip(actual_list, expected_list, strict=True)):
            _require_close(float(a), float(e), f"paired_difference {cid}[{idx}]")

    # Pinned declared summaries mean/CI
    ds_by_id = {ds.comparison_id: ds for ds in pkg.declared_summaries}
    for cid, expected_dict in _PINNED_DECLARED_SUMMARIES.items():
        if cid not in ds_by_id:
            raise ValueError(f"missing pinned declared_summary {cid!r}")
        ds = ds_by_id[cid]
        assert expected_dict["mean"] is not None
        assert expected_dict["lower"] is not None
        assert expected_dict["upper"] is not None
        _require_close(float(ds.mean), float(expected_dict["mean"]), f"declared_summary {cid} mean")
        _require_close(
            float(ds.lower), float(expected_dict["lower"]), f"declared_summary {cid} lower"
        )
        _require_close(
            float(ds.upper), float(expected_dict["upper"]), f"declared_summary {cid} upper"
        )

    # Pinned task lifecycle counts
    for field, expected_count in _PINNED_TASK_LIFECYCLE.items():
        actual = getattr(pkg.task_lifecycle, field)
        if actual != expected_count:
            raise ValueError(
                f"pinned task_lifecycle mismatch for {field}: expected {expected_count!r}, got {actual!r}"
            )

    # Six lifecycle-unavailable fields must remain null with faithful reasons
    for field in (
        "gate_rejected",
        "capacity_rejected",
        "started",
        "compute_completed",
        "returned",
        "dropped",
    ):
        if getattr(pkg.task_lifecycle, field) is not None:
            raise ValueError(f"lifecycle field {field} must be null (UNAVAILABLE)")
        reason = pkg.task_lifecycle.unavailable_reasons.get(field, "")
        if not reason or not reason.strip():
            raise ValueError(f"lifecycle reason for {field} must be non-empty")
        if "==" in reason and "admitted" in reason:
            raise ValueError(f"lifecycle reason for {field} must not claim equality with admitted")

    # Secondary absent SD/SE must remain null
    for ds in pkg.declared_summaries:
        if ds.comparison_id == "e2d_per_task_minus_dla" and (
            ds.sample_sd is not None or ds.standard_error is not None
        ):
            raise ValueError(
                "secondary e2d_per_task_minus_dla sample_sd/standard_error must be None"
            )

    # Provenance manifests must align
    provenance_manifests = {p.manifest_sha256 for p in pkg.provenance}
    for expected_manifest in _PINNED_MANIFESTS.values():
        if expected_manifest not in provenance_manifests:
            raise ValueError(f"provenance missing expected manifest {expected_manifest!r}")

    # Owner-required limitations — explicit searchable wording, per-item
    for phrase in _REQUIRED_LIMITATION_SUBSTRINGS:
        if not any(phrase in lim.lower() for lim in pkg.limitations):
            raise ValueError(f"required limitation phrase missing: {phrase!r}")

    # Owner-required non-claims — explicit searchable wording, per-item
    for phrase in _REQUIRED_NONCLAIM_SUBSTRINGS:
        if not any(phrase in nc.lower() for nc in pkg.non_claims):
            raise ValueError(f"required non_claim phrase missing: {phrase!r}")

    # Forbidden content deep scan on parsed structure (paranoia, loader already covers)
    dumped = json.dumps(raw, ensure_ascii=False)
    if "/Users/" in dumped or "/home/" in dumped:
        raise ValueError("artifact contains forbidden absolute path")

    return pkg


def load_builtin_e2_research() -> E2ResearchEvidencePackage:
    """Load and validate the built-in artifact via importlib.resources."""
    text = builtin_e2_research_json()
    return validate_e2_research_artifact(text)


__all__ = [
    "E2ResearchEvidencePackage",
    "builtin_e2_research_json",
    "validate_e2_research_artifact",
    "load_builtin_e2_research",
]
