"""Deterministic one-click what-if baseline/variation pair orchestration (V2-S1).

This module is the single pair-orchestration service for V2-S1.  It reuses:

* existing synthetic configuration types (:mod:`traffictwin.synthetic.config`)
* existing preset catalogue (:mod:`traffictwin.synthetic.scenarios`)
* deterministic local generator (:mod:`traffictwin.synthetic.bundles`)
* ordinary bundle validation and import (:mod:`traffictwin.ingestion.bundle`)
* existing registry types (:mod:`traffictwin.storage.registry`)

The page ``What-If Studio`` is a thin Streamlit wrapper over this service.
No network, provider, SUMO or VEC dependency exists.

Guarantees (V2-S1 § Transaction and Rollback, Idempotency):

* Build deterministic baseline and variation configs.
* Stage outside final locations.
* Generate both, validate both through the ordinary validation path.
* Confirm pair compatibility / expected identities.
* Publish both only when all checks pass.
* Register both using existing registry services.
* Set session state only after publication/registration (UI responsibility).
* On any failure: no partial bundle, no partial registry, staging removed,
  unrelated data preserved, typed user-readable failure returned,
  no broad destructive overwrite.

Evidence wording is synthetic/deterministic/local and explicitly not
Manchester, not live, not SUMO/VEC.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from traffictwin.domain.enums import TaskClass
from traffictwin.ingestion.bundle import (
    import_validated_bundle as import_validated_bundle,
    validate_bundle as validate_bundle,
)
from traffictwin.storage.registry import Registry, RegistryConflictError as RegistryConflictError
from traffictwin.synthetic.bundles import write_synthetic_bundle as write_synthetic_bundle
from traffictwin.synthetic.config import (
    IncidentSpec,
    SyntheticPolicyProfile,
    SyntheticScenarioConfig,
)
from traffictwin.synthetic.scenarios import preset_config

# ---------------------------------------------------------------------------
# typed contracts
# ---------------------------------------------------------------------------

_ALLOWED_VARIATION_FIELDS = frozenset(
    {
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
)

_PAIR_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class WhatIfChangedParameter(BaseModel):
    """One changed field between baseline and variation."""

    model_config = ConfigDict(extra="forbid")

    field_path: str = Field(min_length=1)
    baseline_value: Any
    variation_value: Any
    unit: str | None = None
    semantic_label: str | None = None


class WhatIfVariationOverrides(BaseModel):
    """Closed intervention set for V2-S1.

    Every field is optional; ``None`` means unchanged from baseline.
    """

    model_config = ConfigDict(extra="forbid")

    incident_enabled: bool | None = None
    incident_type: str | None = None
    incident_location: str | None = None
    incident_start_s: float | None = None
    incident_duration_s: float | None = None
    incident_severity: str | None = None
    lanes_closed: int | None = None
    event_demand_multiplier: float | None = None
    congestion_multiplier: float | None = None
    vehicle_count: int | None = None
    task_arrival_rate: float | None = None
    task_mix_t1: float | None = None
    task_mix_t2: float | None = None
    task_mix_t3: float | None = None
    rsu_count: int | None = None
    rsu_capacity: float | None = None
    policy_profile: str | None = None
    random_seed: int | None = None
    duration_s: float | None = None
    trip_count: int | None = None


class WhatIfPairRequest(BaseModel):
    """Typed request for a baseline/variation pair."""

    model_config = ConfigDict(extra="forbid")

    baseline_preset: str = Field(min_length=1)
    pair_name: str = Field(
        min_length=1, description="sanitised human name, e.g. 'congestion-pulse'"
    )
    experiment_id: str = Field(default="exp-whatif-demo", min_length=1)
    baseline_random_seed: int = Field(default=7, ge=0)
    variation_overrides: WhatIfVariationOverrides = Field(default_factory=WhatIfVariationOverrides)
    # workspace/output target: exactly one should be supplied
    output_root: Path | None = None

    @field_validator("pair_name")
    @classmethod
    def validate_pair_name(cls, value: str) -> str:
        sanitised = sanitise_pair_name(value)
        if not _PAIR_NAME_RE.match(sanitised):
            raise ValueError(
                "pair_name must be lowercase alphanumeric and hyphens, e.g. 'congestion-pulse'"
            )
        return sanitised

    @field_validator("baseline_preset")
    @classmethod
    def validate_preset(cls, value: str) -> str:
        # defer strict preset existence to service; keep minimal
        if not value.strip():
            raise ValueError("baseline_preset must not be empty")
        return value.strip()


class WhatIfPairReceipt(BaseModel):
    """Result returned to UI after attempting pair generation."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "already_exists"]
    pair_id: str
    request_fingerprint: str
    pair_fingerprint: str
    experiment_id: str
    baseline_scenario_id: str
    variation_scenario_id: str
    baseline_bundle_id: str | None = None
    variation_bundle_id: str | None = None
    baseline_run_id: str | None = None
    variation_run_id: str | None = None
    baseline_bundle_path: str | None = None
    variation_bundle_path: str | None = None
    changed_parameters: list[WhatIfChangedParameter] = Field(default_factory=list)
    validation_standing: str = "unknown"
    synthetic_label: str = "SYNTHETIC"
    evidence_labels: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    message: str | None = None
    receipt_path: str | None = None


class WhatIfPairError(RuntimeError):
    """Typed failure that maps to a user-readable refusal."""

    def __init__(self, code: str, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------------------
# helpers: sanitise, fingerprint, pair id, path safety
# ---------------------------------------------------------------------------


def sanitise_pair_name(name: str) -> str:
    """Sanitise a human pair name to lowercase hyphen form."""

    raw = name.strip().lower()
    # replace underscores/spaces with hyphens
    raw = re.sub(r"[\s_]+", "-", raw)
    # keep only alphanumeric and hyphen
    raw = re.sub(r"[^a-z0-9-]", "-", raw)
    raw = re.sub(r"-+", "-", raw).strip("-")
    if not raw:
        return "whatif"
    return raw


def request_fingerprint(request: WhatIfPairRequest) -> str:
    """Deterministic SHA-256 over canonical request JSON (stable ordering)."""

    payload = {
        "baseline_preset": request.baseline_preset,
        "pair_name": sanitise_pair_name(request.pair_name),
        "experiment_id": request.experiment_id,
        "baseline_random_seed": request.baseline_random_seed,
        "variation_overrides": request.variation_overrides.model_dump(
            mode="json", exclude_none=True
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def pair_id_for_request(request: WhatIfPairRequest) -> str:
    """Stable pair identifier: whatif-<sanitised>-<short-digest>."""

    fp = request_fingerprint(request)
    short = fp[:8]
    name = sanitise_pair_name(request.pair_name)
    return f"whatif-{name}-{short}"


def _validated_pair_root(output_root: Path, pair_id: str) -> Path:
    raw = Path(output_root).expanduser()
    if raw.is_symlink():
        raise WhatIfPairError("unsafe_path", f"output root must not be a symlink: {raw}")
    resolved = raw.resolve(strict=False)
    if not str(resolved).strip():
        raise WhatIfPairError("invalid_path", "output root must not be empty")
    protected = (Path.cwd().resolve(), Path.home().resolve())
    for item in protected:
        if resolved == item or item.is_relative_to(resolved):
            raise WhatIfPairError(
                "unsafe_path",
                "output root must not be current, home, root, or ancestor",
            )
    return resolved / pair_id


def _is_safe_containment(candidate: Path, root: Path) -> bool:
    try:
        return candidate.resolve(strict=False).is_relative_to(root.resolve(strict=False))
    except (OSError, ValueError, RuntimeError):
        return False


# ---------------------------------------------------------------------------
# config building
# ---------------------------------------------------------------------------


def build_whatif_configs(
    request: WhatIfPairRequest,
) -> tuple[SyntheticScenarioConfig, SyntheticScenarioConfig]:
    """Build deterministic baseline and variation configs from a request."""

    pair_id = pair_id_for_request(request)
    baseline_scenario_id = f"{pair_id}-baseline"
    variation_scenario_id = f"{pair_id}-variation"

    # baseline from preset — keep original name for clean variation naming
    try:
        preset_baseline = preset_config(
            request.baseline_preset, random_seed=request.baseline_random_seed
        )
    except ValueError as exc:
        raise WhatIfPairError("invalid_preset", str(exc)) from exc

    preset_name = preset_baseline.name
    baseline = preset_baseline.model_copy(
        update={
            "scenario_id": baseline_scenario_id,
            "name": f"{preset_name} — what-if baseline",
            "experiment_id": request.experiment_id,
            "baseline_seed_id": None,
        }
    )

    # variation copies baseline then applies overrides
    overrides = request.variation_overrides
    variation = baseline.model_copy(deep=True)
    variation = variation.model_copy(
        update={
            "scenario_id": variation_scenario_id,
            "name": f"{preset_name} — what-if variation",
            "baseline_seed_id": f"seed-{baseline_scenario_id}",
            "experiment_id": request.experiment_id,
        }
    )

    # scalar overrides
    if overrides.random_seed is not None:
        variation = variation.model_copy(update={"random_seed": overrides.random_seed})
    if overrides.congestion_multiplier is not None:
        variation = variation.model_copy(
            update={"congestion_multiplier": overrides.congestion_multiplier}
        )
    if overrides.vehicle_count is not None:
        variation = variation.model_copy(update={"vehicle_count": overrides.vehicle_count})
    if overrides.task_arrival_rate is not None:
        variation = variation.model_copy(update={"task_arrival_rate": overrides.task_arrival_rate})
    if overrides.rsu_count is not None:
        variation = variation.model_copy(update={"rsu_count": overrides.rsu_count})
    if overrides.rsu_capacity is not None:
        variation = variation.model_copy(update={"rsu_capacity": overrides.rsu_capacity})
    if overrides.duration_s is not None:
        variation = variation.model_copy(update={"duration_s": overrides.duration_s})
    if overrides.trip_count is not None:
        variation = variation.model_copy(update={"trip_count": overrides.trip_count})
    if overrides.policy_profile is not None:
        try:
            profile = SyntheticPolicyProfile(overrides.policy_profile)
        except ValueError as exc:
            raise WhatIfPairError(
                "invalid_policy", f"unknown policy_profile: {overrides.policy_profile}"
            ) from exc
        variation = variation.model_copy(update={"policy_behavior": profile})

    # task mix
    if (
        overrides.task_mix_t1 is not None
        or overrides.task_mix_t2 is not None
        or overrides.task_mix_t3 is not None
    ):
        t1 = (
            overrides.task_mix_t1
            if overrides.task_mix_t1 is not None
            else float(baseline.task_class_mix[TaskClass.T1])
        )
        t2 = (
            overrides.task_mix_t2
            if overrides.task_mix_t2 is not None
            else float(baseline.task_class_mix[TaskClass.T2])
        )
        t3 = (
            overrides.task_mix_t3
            if overrides.task_mix_t3 is not None
            else float(baseline.task_class_mix[TaskClass.T3])
        )
        total = t1 + t2 + t3
        if abs(total - 1.0) > 1e-6:
            raise WhatIfPairError("invalid_task_mix", f"task mix must sum to 1.0; got {total:.6f}")
        variation = variation.model_copy(
            update={"task_class_mix": {TaskClass.T1: t1, TaskClass.T2: t2, TaskClass.T3: t3}}
        )

    # incident handling — single authoritative flow
    if overrides.incident_enabled is not None:
        if overrides.incident_enabled and not variation.incident_schedule:
            variation = variation.model_copy(
                update={
                    "incident_schedule": [
                        IncidentSpec(
                            timestamp_s=overrides.incident_start_s
                            if overrides.incident_start_s is not None
                            else 60.0,
                            incident_type=overrides.incident_type or "synthetic_incident",
                            location=overrides.incident_location or "synthetic-corridor-a",
                            severity=overrides.incident_severity or "moderate",
                            duration_s=overrides.incident_duration_s
                            if overrides.incident_duration_s is not None
                            else 60.0,
                            lanes_closed=overrides.lanes_closed,
                            demand_multiplier=overrides.event_demand_multiplier
                            if overrides.event_demand_multiplier is not None
                            else 1.0,
                        )
                    ]
                }
            )
        elif not overrides.incident_enabled and variation.incident_schedule:
            variation = variation.model_copy(update={"incident_schedule": []})
    # if incident present, apply any field overrides
    if variation.incident_schedule:
        incident = variation.incident_schedule[0]
        patch: dict[str, Any] = {}
        if overrides.incident_type is not None:
            patch["incident_type"] = overrides.incident_type
        if overrides.incident_location is not None:
            patch["location"] = overrides.incident_location
        if overrides.incident_severity is not None:
            patch["severity"] = overrides.incident_severity
        if overrides.incident_start_s is not None:
            patch["timestamp_s"] = overrides.incident_start_s
        if overrides.incident_duration_s is not None:
            patch["duration_s"] = overrides.incident_duration_s
        if overrides.lanes_closed is not None:
            patch["lanes_closed"] = overrides.lanes_closed
        if overrides.event_demand_multiplier is not None:
            patch["demand_multiplier"] = overrides.event_demand_multiplier
        if patch:
            variation = variation.model_copy(
                update={"incident_schedule": [incident.model_copy(update=patch)]}
            )

    return baseline, variation


def compute_changed_ledger(
    baseline: SyntheticScenarioConfig,
    variation: SyntheticScenarioConfig,
) -> list[WhatIfChangedParameter]:
    """Deterministic changed-parameter ledger: canonical field paths, ordered, no unchanged rows."""

    ledger: list[WhatIfChangedParameter] = []

    # helper to add
    def add(
        path: str, b: object, v: object, unit: str | None = None, label: str | None = None
    ) -> None:
        if b != v:
            ledger.append(
                WhatIfChangedParameter(
                    field_path=path,
                    baseline_value=_serialise_value(b),
                    variation_value=_serialise_value(v),
                    unit=unit,
                    semantic_label=label,
                )
            )

    # incident
    b_has = bool(baseline.incident_schedule)
    v_has = bool(variation.incident_schedule)
    if b_has != v_has:
        add("incident_schedule.enabled", b_has, v_has, label="incident enabled")
    if b_has and v_has:
        b_inc = baseline.incident_schedule[0]
        v_inc = variation.incident_schedule[0]
        add("incident_schedule[0].incident_type", b_inc.incident_type, v_inc.incident_type)
        add("incident_schedule[0].location", b_inc.location, v_inc.location)
        add("incident_schedule[0].severity", b_inc.severity, v_inc.severity)
        add("incident_schedule[0].timestamp_s", b_inc.timestamp_s, v_inc.timestamp_s, unit="s")
        add("incident_schedule[0].duration_s", b_inc.duration_s, v_inc.duration_s, unit="s")
        add("incident_schedule[0].lanes_closed", b_inc.lanes_closed, v_inc.lanes_closed)
        add(
            "incident_schedule[0].demand_multiplier",
            b_inc.demand_multiplier,
            v_inc.demand_multiplier,
            label="event demand multiplier",
        )
    elif b_has and not v_has:
        # removal counts as change already captured via enabled, but also show removal details?
        pass
    elif not b_has and v_has:
        v_inc = variation.incident_schedule[0]
        # show added fields as change from None
        add("incident_schedule[0].incident_type", None, v_inc.incident_type)
        add("incident_schedule[0].location", None, v_inc.location)
        add("incident_schedule[0].timestamp_s", None, v_inc.timestamp_s, unit="s")
        add("incident_schedule[0].duration_s", None, v_inc.duration_s, unit="s")
        add("incident_schedule[0].lanes_closed", None, v_inc.lanes_closed)
        add("incident_schedule[0].demand_multiplier", None, v_inc.demand_multiplier)

    add(
        "congestion_multiplier",
        baseline.congestion_multiplier,
        variation.congestion_multiplier,
        label="congestion/demand multiplier",
    )
    add("vehicle_count", baseline.vehicle_count, variation.vehicle_count)
    add(
        "task_arrival_rate",
        baseline.task_arrival_rate,
        variation.task_arrival_rate,
        unit="rate",
        label="task arrival rate",
    )
    add(
        "task_class_mix.T1",
        float(baseline.task_class_mix[TaskClass.T1]),
        float(variation.task_class_mix[TaskClass.T1]),
        label="T1 share",
    )
    add(
        "task_class_mix.T2",
        float(baseline.task_class_mix[TaskClass.T2]),
        float(variation.task_class_mix[TaskClass.T2]),
        label="T2 share",
    )
    add(
        "task_class_mix.T3",
        float(baseline.task_class_mix[TaskClass.T3]),
        float(variation.task_class_mix[TaskClass.T3]),
        label="T3 share",
    )
    add("rsu_count", baseline.rsu_count, variation.rsu_count)
    add("rsu_capacity", baseline.rsu_capacity, variation.rsu_capacity)
    add(
        "policy_behavior",
        baseline.policy_behavior.value,
        variation.policy_behavior.value,
        label="synthetic policy profile",
    )
    add("random_seed", baseline.random_seed, variation.random_seed, label="reproducibility seed")
    add("duration_s", baseline.duration_s, variation.duration_s, unit="s")
    add("trip_count", baseline.trip_count, variation.trip_count)

    # stable lexical ordering by field_path
    ledger.sort(key=lambda x: x.field_path)
    return ledger


def _serialise_value(value: object) -> object:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


# ---------------------------------------------------------------------------
# receipt helpers
# ---------------------------------------------------------------------------

EVIDENCE_LABELS = [
    "SYNTHETIC",
    "DETERMINISTIC",
    "LOCAL",
    "NOT_MANCHESTER_OBSERVATION",
    "NOT_LIVE_TRAFFIC_FORECAST",
    "NOT_SUMO_EXECUTION",
    "NOT_VEC_EXECUTION",
    "NOT_RESEARCH_ADMISSION",
]

STUDIO_EVIDENCE_SENTENCE = (
    "This studio generates a deterministic synthetic baseline and intervention "
    "through TrafficTwin's local generator. It does not run SUMO, VEC, a provider feed "
    "or an admitted research campaign."
)


def _receipt_relative_paths(
    pair_root: Path, baseline_path: Path, variation_path: Path
) -> tuple[str, str]:
    # Return relative POSIX paths for receipt (no absolute private path)
    try:
        rel_base = baseline_path.relative_to(pair_root.parent).as_posix()
    except ValueError:
        rel_base = baseline_path.name + "/baseline"
    try:
        rel_var = variation_path.relative_to(pair_root.parent).as_posix()
    except ValueError:
        rel_var = variation_path.name + "/variation"
    return rel_base, rel_var


# ---------------------------------------------------------------------------
# main orchestration
# ---------------------------------------------------------------------------


def generate_whatif_pair(
    request: WhatIfPairRequest,
    *,
    registry_path: Path,
    workspace_path: Path | None = None,
) -> WhatIfPairReceipt:
    """Generate, validate, publish and register a what-if baseline/variation pair atomically.

    Returns a :class:`WhatIfPairReceipt` with status ``ok`` or ``already_exists``
    on success.  On failure raises :class:`WhatIfPairError` with a user-readable
    message.  No partial publication or registry mutation remains on failure.

    Parameters
    ----------
    request:
        Typed request describing baseline preset and variation overrides.
    registry_path:
        Registry file (e.g. ``workspace/registry.sqlite``).
    workspace_path:
        When provided and ``request.output_root`` is ``None``, pair is published
        under ``workspace_path / "bundles" / pair_id``.
    """

    # -------------------------------------------------
    # 1. build deterministic baseline/variation and ledger
    # -------------------------------------------------
    pair_id = pair_id_for_request(request)
    req_fp = request_fingerprint(request)
    # pair fingerprint is same as request fingerprint (deterministic)
    pair_fp = req_fp

    baseline_cfg, variation_cfg = build_whatif_configs(request)
    ledger = compute_changed_ledger(baseline_cfg, variation_cfg)

    if not ledger:
        raise WhatIfPairError(
            "identical_pair",
            "Baseline and variation are identical — no meaningful field changed. "
            "Change at least one intervention parameter before generating.",
            detail="ledger is empty",
        )

    # resolve output root
    if request.output_root is not None:
        pair_root = _validated_pair_root(request.output_root, pair_id)
    elif workspace_path is not None:
        pair_root = _validated_pair_root(workspace_path / "bundles", pair_id)
    else:
        # fallback to cwd-relative bundles (still validated)
        pair_root = _validated_pair_root(Path.cwd() / "bundles", pair_id)

    baseline_final = pair_root / "baseline"
    variation_final = pair_root / "variation"
    receipt_path = pair_root / "whatif_receipt.json"

    # -------------------------------------------------
    # 2. idempotency / collision checks before work
    # -------------------------------------------------
    if pair_root.exists():
        if not pair_root.is_dir():
            raise WhatIfPairError(
                "destination_exists", f"pair destination is not a directory: {pair_root}"
            )
        # existing receipt?
        if receipt_path.is_file():
            try:
                existing = json.loads(receipt_path.read_text(encoding="utf-8"))
                existing_fp = existing.get("pair_fingerprint") or existing.get(
                    "request_fingerprint"
                )
                if existing_fp == pair_fp:
                    # verify both bundles still exist and validate
                    if baseline_final.is_dir() and variation_final.is_dir():
                        try:
                            b_val = validate_bundle(baseline_final)
                            v_val = validate_bundle(variation_final)
                            if b_val.report.may_import and v_val.report.may_import:
                                reg = Registry(registry_path)
                                reg.initialize()
                                records = {r.bundle_id: r for r in reg.list_bundle_import_records()}
                                b_bid = b_val.manifest.bundle.bundle_id if b_val.manifest else None
                                v_bid = v_val.manifest.bundle.bundle_id if v_val.manifest else None
                                b_in = (
                                    b_bid in records
                                    and records[b_bid].fingerprint == b_val.fingerprint
                                )
                                v_in = (
                                    v_bid in records
                                    and records[v_bid].fingerprint == v_val.fingerprint
                                )
                                if b_in and v_in:
                                    return WhatIfPairReceipt(
                                        status="already_exists",
                                        pair_id=pair_id,
                                        request_fingerprint=req_fp,
                                        pair_fingerprint=pair_fp,
                                        experiment_id=request.experiment_id,
                                        baseline_scenario_id=baseline_cfg.scenario_id,
                                        variation_scenario_id=variation_cfg.scenario_id,
                                        baseline_bundle_id=b_bid,
                                        variation_bundle_id=v_bid,
                                        baseline_run_id=b_val.manifest.run.run_id
                                        if b_val.manifest
                                        else None,
                                        variation_run_id=v_val.manifest.run.run_id
                                        if v_val.manifest
                                        else None,
                                        baseline_bundle_path=str(baseline_final),
                                        variation_bundle_path=str(variation_final),
                                        changed_parameters=ledger,
                                        validation_standing="accepted",
                                        synthetic_label="SYNTHETIC",
                                        evidence_labels=EVIDENCE_LABELS,
                                        warnings=[],
                                        message="Pair exists with same fingerprint; verified.",
                                        receipt_path=str(
                                            receipt_path.relative_to(pair_root.parent)
                                            if _is_safe_containment(receipt_path, pair_root.parent)
                                            else receipt_path.name
                                        ),
                                    )
                                # valid artifacts but missing registration -> re-register (F-5)
                                if b_val.manifest and v_val.manifest:
                                    try:
                                        if not b_in:
                                            import_validated_bundle(b_val, registry_path)
                                        if not v_in:
                                            import_validated_bundle(v_val, registry_path)
                                        return WhatIfPairReceipt(
                                            status="already_exists",
                                            pair_id=pair_id,
                                            request_fingerprint=req_fp,
                                            pair_fingerprint=pair_fp,
                                            experiment_id=request.experiment_id,
                                            baseline_scenario_id=baseline_cfg.scenario_id,
                                            variation_scenario_id=variation_cfg.scenario_id,
                                            baseline_bundle_id=b_bid,
                                            variation_bundle_id=v_bid,
                                            baseline_run_id=b_val.manifest.run.run_id
                                            if b_val.manifest
                                            else None,
                                            variation_run_id=v_val.manifest.run.run_id
                                            if v_val.manifest
                                            else None,
                                            baseline_bundle_path=str(baseline_final),
                                            variation_bundle_path=str(variation_final),
                                            changed_parameters=ledger,
                                            validation_standing="accepted",
                                            synthetic_label="SYNTHETIC",
                                            evidence_labels=EVIDENCE_LABELS,
                                            warnings=[],
                                            message=(
                                                "Pair re-registered into fresh registry; verified."
                                            ),
                                            receipt_path=str(
                                                receipt_path.relative_to(pair_root.parent)
                                                if _is_safe_containment(
                                                    receipt_path, pair_root.parent
                                                )
                                                else receipt_path.name
                                            ),
                                        )
                                    except WhatIfPairError:
                                        raise
                                    except Exception as exc:
                                        raise WhatIfPairError(
                                            "corrupt_existing_pair",
                                            f"Re-registration failed: {exc}",
                                        ) from exc
                        except WhatIfPairError:
                            raise
                        except Exception:  # noqa: S110
                            pass  # not idempotent, fall through
                    # fingerprint matches but artifacts corrupt -> do not treat as success
                    raise WhatIfPairError(
                        "corrupt_existing_pair",
                        "Pair exists but is incomplete or corrupt; remove it before retry.",
                        detail=str(receipt_path),
                    )
                else:
                    raise WhatIfPairError(
                        "pair_id_collision",
                        "Pair exists with different content; change pair name or variation.",
                        detail=f"existing fingerprint {existing_fp!r} != requested {pair_fp!r}",
                    )
            except WhatIfPairError:
                raise
            except Exception as exc:
                raise WhatIfPairError(
                    "corrupt_existing_pair", f"Existing pair is corrupt: {exc}"
                ) from exc
        # no receipt but directory non-empty -> unrelated or partial
        if any(pair_root.iterdir()):
            raise WhatIfPairError(
                "destination_exists",
                f"Pair destination exists and is not empty: {pair_root}. Choose another name.",
            )

    # ensure parent is safe to write under
    pair_root.parent.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------
    # 3. stage outside final location
    # -------------------------------------------------
    staging_root: Path | None = None
    baseline_staging: Path | None = None
    variation_staging: Path | None = None
    published_baseline = False
    published_variation = False
    baseline_created = False
    variation_created = False
    baseline_import_result = None
    variation_import_result = None

    try:
        staging_parent = pair_root.parent
        staging_root = Path(
            tempfile.mkdtemp(prefix=f".{pair_id}-staging-", dir=str(staging_parent))
        )
        baseline_staging = staging_root / "baseline"
        variation_staging = staging_root / "variation"

        # 3a. generate both (uses transactional bundle writer internally)
        try:
            write_synthetic_bundle(baseline_cfg, baseline_staging, overwrite=False)
        except Exception as exc:
            raise WhatIfPairError(
                "baseline_generation_failed", f"Baseline generation failed: {exc}"
            ) from exc

        try:
            write_synthetic_bundle(variation_cfg, variation_staging, overwrite=False)
        except Exception as exc:
            raise WhatIfPairError(
                "variation_generation_failed", f"Variation generation failed: {exc}"
            ) from exc

        # 3b. validate both through ordinary path
        baseline_validation = validate_bundle(baseline_staging)
        if baseline_validation.manifest is None or not baseline_validation.report.may_import:
            detail = "; ".join(f.message for f in baseline_validation.report.findings) or "unknown"
            raise WhatIfPairError(
                "baseline_validation_failed", f"Baseline bundle is not valid: {detail}"
            )

        variation_validation = validate_bundle(variation_staging)
        if variation_validation.manifest is None or not variation_validation.report.may_import:
            detail = "; ".join(f.message for f in variation_validation.report.findings) or "unknown"
            raise WhatIfPairError(
                "variation_validation_failed", f"Variation bundle is not valid: {detail}"
            )

        # 3c. pair compatibility
        # experiment_id must match (already enforced via config)
        if (
            baseline_validation.manifest.run.experiment_id
            != variation_validation.manifest.run.experiment_id
        ):
            raise WhatIfPairError(
                "incompatible_pair",
                "Baseline and variation must belong to the same experiment identity",
            )
        # scenario ids must be distinct and match expected
        if baseline_cfg.scenario_id == variation_cfg.scenario_id:
            raise WhatIfPairError(
                "incompatible_pair", "Baseline and variation scenario IDs must be distinct"
            )
        if variation_cfg.baseline_seed_id != f"seed-{baseline_cfg.scenario_id}":
            raise WhatIfPairError(
                "incompatible_pair", "Variation must link to baseline via baseline_seed_id"
            )
        # provenance synthetic check
        if (
            baseline_validation.manifest.environment.name != "synthetic"
            or variation_validation.manifest.environment.name != "synthetic"
        ):
            raise WhatIfPairError("invalid_provenance", "Both bundles must be synthetic")

        # compare deterministic: ensure both use same metric version etc. (no further check)

        # -------------------------------------------------
        # 4. publish both only when all checks pass
        # -------------------------------------------------
        # atomic publish of each bundle directory (staging -> final) via replace
        pair_root.mkdir(parents=True, exist_ok=True)

        # publish baseline
        if baseline_final.exists():
            raise WhatIfPairError(
                "destination_exists", f"Baseline destination already exists: {baseline_final}"
            )
        try:
            baseline_staging.replace(baseline_final)
            published_baseline = True
        except Exception as exc:
            raise WhatIfPairError(
                "publish_failed", f"Could not publish baseline bundle: {exc}"
            ) from exc

        # publish variation
        if variation_final.exists():
            # rollback baseline publish
            raise WhatIfPairError(
                "destination_exists", f"Variation destination already exists: {variation_final}"
            )
        try:
            variation_staging.replace(variation_final)
            published_variation = True
        except Exception as exc:
            raise WhatIfPairError(
                "publish_failed", f"Could not publish variation bundle: {exc}"
            ) from exc

        # -------------------------------------------------
        # 5. register both using existing registry services
        # -------------------------------------------------
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        Registry(registry_path).initialize()

        # check existing bundle_id collision before importing
        reg = Registry(registry_path)
        existing_records = {r.bundle_id: r for r in reg.list_bundle_import_records()}
        b_bundle_id = baseline_validation.manifest.bundle.bundle_id
        v_bundle_id = variation_validation.manifest.bundle.bundle_id
        b_run_id = baseline_validation.manifest.run.run_id
        v_run_id = variation_validation.manifest.run.run_id

        # pre-check collisions
        for bid, fp, run_id in (
            (b_bundle_id, baseline_validation.fingerprint, b_run_id),
            (v_bundle_id, variation_validation.fingerprint, v_run_id),
        ):
            if bid in existing_records and existing_records[bid].fingerprint != fp:
                raise WhatIfPairError(
                    "registry_collision",
                    f"Registry already contains bundle_id {bid!r} with different content.",
                )
            # also check run_id collision
            from traffictwin.storage.registry import RegistryNotFoundError

            try:
                reg.get_run(run_id)
                if bid not in existing_records:
                    raise WhatIfPairError(
                        "registry_collision",
                        f"Registry already contains run_id {run_id!r} for a different bundle",
                    )
            except RegistryNotFoundError:
                pass

        # import baseline
        try:
            baseline_import_result = import_validated_bundle(baseline_validation, registry_path)
            if not (baseline_import_result.created or baseline_import_result.idempotent):
                raise WhatIfPairError(
                    "registration_failed",
                    f"Baseline registration failed: {baseline_import_result.message}",
                )
            baseline_created = baseline_import_result.created
        except RegistryConflictError as exc:
            raise WhatIfPairError(
                "registration_failed", f"Baseline registration conflict: {exc}"
            ) from exc
        except WhatIfPairError:
            raise
        except Exception as exc:
            raise WhatIfPairError(
                "registration_failed", f"Baseline registration failed: {exc}"
            ) from exc

        # import variation
        try:
            variation_import_result = import_validated_bundle(variation_validation, registry_path)
            if not (variation_import_result.created or variation_import_result.idempotent):
                raise WhatIfPairError(
                    "registration_failed",
                    f"Variation registration failed: {variation_import_result.message}",
                )
            variation_created = variation_import_result.created
        except RegistryConflictError as exc:
            raise WhatIfPairError(
                "registration_failed", f"Variation registration conflict: {exc}"
            ) from exc
        except WhatIfPairError:
            raise
        except Exception as exc:
            raise WhatIfPairError(
                "registration_failed", f"Variation registration failed: {exc}"
            ) from exc

        # -------------------------------------------------
        # 6. write receipt (no absolute private path)
        # -------------------------------------------------
        rel_baseline, rel_variation = _receipt_relative_paths(
            pair_root, baseline_final, variation_final
        )
        receipt_payload = {
            "pair_id": pair_id,
            "request_fingerprint": req_fp,
            "pair_fingerprint": pair_fp,
            "experiment_id": request.experiment_id,
            "baseline_scenario_id": baseline_cfg.scenario_id,
            "variation_scenario_id": variation_cfg.scenario_id,
            "baseline_bundle_id": b_bundle_id,
            "variation_bundle_id": v_bundle_id,
            "baseline_run_id": b_run_id,
            "variation_run_id": v_run_id,
            "baseline_bundle_path": rel_baseline,
            "variation_bundle_path": rel_variation,
            "changed_parameters": [p.model_dump(mode="json") for p in ledger],
            "validation_standing": "accepted",
            "synthetic_label": "SYNTHETIC",
            "evidence_labels": EVIDENCE_LABELS,
            "warnings": [],
            "pair_name": sanitise_pair_name(request.pair_name),
            "baseline_preset": request.baseline_preset,
        }
        receipt_path.write_text(
            json.dumps(receipt_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        return WhatIfPairReceipt(
            status="ok",
            pair_id=pair_id,
            request_fingerprint=req_fp,
            pair_fingerprint=pair_fp,
            experiment_id=request.experiment_id,
            baseline_scenario_id=baseline_cfg.scenario_id,
            variation_scenario_id=variation_cfg.scenario_id,
            baseline_bundle_id=b_bundle_id,
            variation_bundle_id=v_bundle_id,
            baseline_run_id=b_run_id,
            variation_run_id=v_run_id,
            baseline_bundle_path=str(baseline_final),
            variation_bundle_path=str(variation_final),
            changed_parameters=ledger,
            validation_standing="accepted",
            synthetic_label="SYNTHETIC",
            evidence_labels=EVIDENCE_LABELS,
            warnings=[],
            message="Pair generated, validated, published and registered.",
            receipt_path=str(
                receipt_path.relative_to(pair_root.parent)
                if _is_safe_containment(receipt_path, pair_root.parent)
                else receipt_path.name
            ),
        )

    except WhatIfPairError:
        # rollback published bundles and registry if needed, then re-raise
        # F-4: only rollback rows we created (not idempotent)
        _rollback_on_failure(
            pair_root=pair_root,
            baseline_final=baseline_final if published_baseline else None,
            variation_final=variation_final if published_variation else None,
            registry_path=registry_path,
            baseline_created=baseline_created,
            variation_created=variation_created,
            baseline_bundle_id=b_bundle_id if "b_bundle_id" in locals() else None,
            variation_bundle_id=v_bundle_id if "v_bundle_id" in locals() else None,
            baseline_run_id=b_run_id if "b_run_id" in locals() else None,
            variation_run_id=v_run_id if "v_run_id" in locals() else None,
        )
        # also clean up receipt if partially written
        try:
            if receipt_path.is_file():
                receipt_path.unlink()
            # if pair_root now empty, remove it
            if pair_root.exists() and pair_root.is_dir() and not any(pair_root.iterdir()):
                pair_root.rmdir()
        except Exception:  # noqa: S110
            pass
        raise
    except Exception as exc:
        # unexpected failure - also rollback
        _rollback_on_failure(
            pair_root=pair_root,
            baseline_final=baseline_final if published_baseline else None,
            variation_final=variation_final if published_variation else None,
            registry_path=registry_path,
            baseline_created=baseline_created,
            variation_created=variation_created,
            baseline_bundle_id=b_bundle_id if "b_bundle_id" in locals() else None,
            variation_bundle_id=v_bundle_id if "v_bundle_id" in locals() else None,
            baseline_run_id=b_run_id if "b_run_id" in locals() else None,
            variation_run_id=v_run_id if "v_run_id" in locals() else None,
        )
        try:
            if receipt_path.is_file():
                receipt_path.unlink()
            if pair_root.exists() and pair_root.is_dir() and not any(pair_root.iterdir()):
                pair_root.rmdir()
        except Exception:  # noqa: S110
            pass
        raise WhatIfPairError("unexpected_error", f"Pair generation failed: {exc}") from exc
    finally:
        # always remove staging root
        if staging_root is not None and staging_root.exists():
            shutil.rmtree(staging_root, ignore_errors=True)


def _rollback_on_failure(
    *,
    pair_root: Path,
    baseline_final: Path | None,
    variation_final: Path | None,
    registry_path: Path,
    baseline_created: bool,
    variation_created: bool,
    baseline_bundle_id: str | None,
    variation_bundle_id: str | None,
    baseline_run_id: str | None,
    variation_run_id: str | None,
) -> None:
    # remove published directories if this failure was after publish
    for p in (baseline_final, variation_final):
        if p is not None and p.exists():
            shutil.rmtree(p, ignore_errors=True)
    # attempt to remove empty pair_root
    try:
        if pair_root.exists() and pair_root.is_dir() and not any(pair_root.iterdir()):
            pair_root.rmdir()
    except Exception:  # noqa: S110
        pass
    # registry rollback: delete only rows we created (F-4: idempotent rows preserved)
    try:
        import sqlite3

        if not registry_path.exists():
            return
        conn = sqlite3.connect(str(registry_path))
        try:
            if baseline_created and baseline_bundle_id:
                conn.execute(
                    "DELETE FROM bundle_imports WHERE bundle_id = ?", (baseline_bundle_id,)
                )
                if baseline_run_id:
                    conn.execute("DELETE FROM runs WHERE run_id = ?", (baseline_run_id,))
                conn.commit()
            if variation_created and variation_bundle_id:
                conn.execute(
                    "DELETE FROM bundle_imports WHERE bundle_id = ?", (variation_bundle_id,)
                )
                if variation_run_id:
                    conn.execute("DELETE FROM runs WHERE run_id = ?", (variation_run_id,))
                conn.commit()
        finally:
            conn.close()
    except Exception:  # noqa: S110
        pass


# ---------------------------------------------------------------------------
# yaml download helper for UI
# ---------------------------------------------------------------------------


def whatif_ledger_to_yaml(ledger: list[WhatIfChangedParameter]) -> str:
    """Return deterministic YAML for a changed-parameter ledger."""

    return yaml.safe_dump(
        [item.model_dump(mode="json") for item in ledger],
        sort_keys=False,
        allow_unicode=False,
    )
