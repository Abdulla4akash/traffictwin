"""Typed bridge from ChallengeSeed parameters to What-If Studio controls.

This module is a SUPPORTED-SUBSET PREFILL BRIDGE only.
It does NOT make ScenarioSeed executable and does NOT invent numeric
inverses for abstract modes.

Only fields with a defensible semantic equivalence to an existing
``WhatIfVariationOverrides`` control are mapped. All other challenge
parameters are reported as unsupported and surfaced explicitly to the user.

Mapping provenance
------------------
ScenarioSeed → SyntheticScenarioConfig conversion is authoritative in
``traffictwin.synthetic.generator._seed``:

* demand.multiplier             ↔ congestion_multiplier (max 0.1 clamp)
* workload.birth_rate_multiplier ↔ task_arrival_rate   (×0.10, max 0.1 clamp)
* workload.class_mix            ↔ task_class_mix        (direct enum map)
* traffic.* incident fields     ↔ IncidentSpec fields
* infrastructure.rsu_count      ↔ rsu_count            (direct)
* evaluation.random_seed        ↔ random_seed           (direct)
* fleet.count                   ↔ vehicle_count         (direct, no tier mix)

What-If variation controls are authoritative in
``traffictwin.synthetic.whatif_pair.WhatIfVariationOverrides`` and
``build_whatif_configs``. Only those controls are reachable.

Fields intentionally marked UNSUPPORTED:

* fleet.tier_mix — generator derives tier_mix from vehicle_tier_mix threshold
  (>=0.6 low → weak else mixed); there is no authoritative reverse mapping
  from the ScenarioSeed FleetTierMix enum to What-If controls.
* infrastructure.rsu_capacity_mode — abstract REDUCED/STANDARD/EXPANDED has
  no authoritative numeric rsu_capacity inverse; must not be guessed.
* workload.ordering — What-If has no ordering control; generator hardcodes
  ordering=MIXED.
* traffic.duration_min, traffic.event_demand_multiplier etc that are incident-
  specific are mapped only when an IncidentSpec mapping exists; otherwise
  unsupported.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.synthetic.whatif_pair import WhatIfVariationOverrides
from traffictwin.ui.portfolio_explorer import ChallengeSeedDefinition, get_challenge_seed
from traffictwin.ui.whatif_controls import is_value_representable

# ---------------------------------------------------------------------------
# typed contracts
# ---------------------------------------------------------------------------


class ChallengeWhatIfMappingStatus(StrEnum):
    """Bridge outcome for one challenge."""

    FULLY_MAPPABLE = "FULLY_MAPPABLE"
    PARTIALLY_MAPPABLE = "PARTIALLY_MAPPABLE"
    NOT_MAPPABLE = "NOT_MAPPABLE"


class ChallengeWhatIfMappedField(BaseModel):
    """One successfully mapped challenge parameter."""

    model_config = ConfigDict(extra="forbid")

    challenge_path: str = Field(min_length=1)
    challenge_value: Any
    whatif_field: str = Field(min_length=1)
    mapped_value: Any
    rationale: str = Field(min_length=1)


class ChallengeWhatIfUnsupportedField(BaseModel):
    """One challenge parameter not representable in What-If controls."""

    model_config = ConfigDict(extra="forbid")

    challenge_path: str = Field(min_length=1)
    challenge_value: Any
    reason: str = Field(min_length=1)


class ChallengeWhatIfDraft(BaseModel):
    """Publication-safe handoff payload for Portfolio → What-If."""

    model_config = ConfigDict(extra="forbid")

    challenge_id: str = Field(min_length=1)
    challenge_title: str = Field(min_length=1)
    mapping_status: ChallengeWhatIfMappingStatus
    supported_fields: list[ChallengeWhatIfMappedField] = Field(default_factory=list)
    unsupported_fields: list[ChallengeWhatIfUnsupportedField] = Field(default_factory=list)
    whatif_overrides: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    fingerprint: str = Field(min_length=1)
    evidence_standing: str = "synthetic demonstration only"
    source_status: str = Field(default="REPRESENTABLE_ONLY")


# Session handoff key — declared in DEFAULT_SESSION_STATE downstream
PENDING_WHATIF_CHALLENGE_DRAFT_KEY = "pending_whatif_challenge_draft"

# ---------------------------------------------------------------------------
# mapping registry
# ---------------------------------------------------------------------------

# Each mapper: (challenge_path) -> (whatif_field, convert_fn, rationale)
# convert_fn: (challenge_value) -> (mapped_value) or raises ValueError
_MapperFn = Callable[[Any], Any]


def _as_congestion_multiplier(value: Any) -> float:  # noqa: ANN401
    if not isinstance(value, (int, float)):
        raise ValueError(f"demand.multiplier must be numeric, got {type(value).__name__}")
    fv = float(value)
    if fv <= 0:
        raise ValueError(f"demand.multiplier must be > 0, got {fv}")
    if fv > 10:
        raise ValueError(f"demand.multiplier implausibly large: {fv}")
    return fv


def _as_birth_rate_multiplier(value: Any) -> float:  # noqa: ANN401
    if not isinstance(value, (int, float)):
        raise ValueError(
            f"workload.birth_rate_multiplier must be numeric, got {type(value).__name__}"
        )
    fv = float(value)
    if fv <= 0:
        raise ValueError(f"workload.birth_rate_multiplier must be > 0, got {fv}")
    if fv > 10:
        raise ValueError(f"workload.birth_rate_multiplier implausibly large: {fv}")
    # What-If task_arrival_rate = birth_rate_multiplier * 0.10
    return round(fv * 0.10, 6)


def _as_rsu_count(value: Any) -> int:  # noqa: ANN401
    if not isinstance(value, int):
        # bool is subclass of int — reject
        if isinstance(value, bool):
            raise ValueError("infrastructure.rsu_count must be int")
        raise ValueError(f"infrastructure.rsu_count must be int, got {type(value).__name__}")
    if value < 1:
        raise ValueError(f"infrastructure.rsu_count must be >= 1, got {value}")
    if value > 100:
        raise ValueError(f"infrastructure.rsu_count implausibly large: {value}")
    return value


def _as_fleet_count(value: Any) -> int:  # noqa: ANN401
    if not isinstance(value, int):
        if isinstance(value, bool):
            raise ValueError("fleet.count must be int")
        raise ValueError(f"fleet.count must be int, got {type(value).__name__}")
    if value < 1:
        raise ValueError(f"fleet.count must be >= 1, got {value}")
    if value > 500:
        raise ValueError(f"fleet.count implausibly large: {value}")
    return value


def _as_random_seed(value: Any) -> int:  # noqa: ANN401
    if not isinstance(value, int):
        if isinstance(value, bool):
            raise ValueError("evaluation.random_seed must be int")
        raise ValueError(f"evaluation.random_seed must be int, got {type(value).__name__}")
    if value < 0:
        raise ValueError(f"evaluation.random_seed must be >= 0, got {value}")
    return value


def _as_traffic_event_type(value: Any) -> str:  # noqa: ANN401
    if not isinstance(value, str) or not value.strip():
        raise ValueError("traffic.event_type must be non-empty string")
    return value.strip()


def _as_traffic_location(value: Any) -> str:  # noqa: ANN401
    if not isinstance(value, str) or not value.strip():
        raise ValueError("traffic.location must be non-empty string")
    return value.strip()


def _as_lanes_closed(value: Any) -> int:  # noqa: ANN401
    if not isinstance(value, int):
        if isinstance(value, bool):
            raise ValueError("traffic.lanes_closed must be int")
        raise ValueError(f"traffic.lanes_closed must be int, got {type(value).__name__}")
    if value < 0:
        raise ValueError(f"traffic.lanes_closed must be >= 0, got {value}")
    if value > 20:
        raise ValueError(f"traffic.lanes_closed implausibly large: {value}")
    return value


def _as_duration_min(value: Any) -> float:  # noqa: ANN401
    if not isinstance(value, (int, float)):
        raise ValueError(f"traffic.duration_min must be numeric, got {type(value).__name__}")
    fv = float(value)
    if fv <= 0:
        raise ValueError(f"traffic.duration_min must be > 0, got {fv}")
    if fv > 1440:
        raise ValueError(f"traffic.duration_min implausibly large: {fv}")
    # What-If incident_duration_s = duration_min * 60
    return round(fv * 60.0, 3)


def _as_event_demand_multiplier(value: Any) -> float:  # noqa: ANN401
    if not isinstance(value, (int, float)):
        raise ValueError(
            f"traffic.event_demand_multiplier must be numeric, got {type(value).__name__}"
        )
    fv = float(value)
    if fv <= 0:
        raise ValueError(f"traffic.event_demand_multiplier must be > 0, got {fv}")
    if fv > 10:
        raise ValueError(f"traffic.event_demand_multiplier implausibly large: {fv}")
    return fv


def _as_class_mix(value: Any) -> dict[str, float]:  # noqa: ANN401
    # value is dict like {"T1": 0.6, ...} or {TaskClass.T1: 0.6}
    if not isinstance(value, dict):
        raise ValueError(f"workload.class_mix must be dict, got {type(value).__name__}")
    # Extract T1/T2/T3 shares
    t1 = value.get("T1", value.get("t1"))
    # Also handle TaskClass enum keys serialized as "T1"
    if t1 is None:
        for k, v in value.items():
            ks = str(getattr(k, "value", k))
            if ks == "T1":
                t1 = v
                break
    t2 = value.get("T2", value.get("t2"))
    if t2 is None:
        for k, v in value.items():
            ks = str(getattr(k, "value", k))
            if ks == "T2":
                t2 = v
                break
    t3 = value.get("T3", value.get("t3"))
    if t3 is None:
        for k, v in value.items():
            ks = str(getattr(k, "value", k))
            if ks == "T3":
                t3 = v
                break
    if t1 is None or t2 is None or t3 is None:
        raise ValueError("workload.class_mix must contain T1, T2, T3 shares")
    for label, val in [("T1", t1), ("T2", t2), ("T3", t3)]:
        if not isinstance(val, (int, float)):
            raise ValueError(f"workload.class_mix[{label}] must be numeric")
        fv = float(val)
        if fv < 0 or fv > 1:
            raise ValueError(f"workload.class_mix[{label}] must be in [0,1], got {fv}")
    total = float(t1) + float(t2) + float(t3)
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"workload.class_mix shares must sum to 1.0, got {total:.6f}")
    return {"T1": float(t1), "T2": float(t2), "T3": float(t3)}


# Registry: challenge_path -> (whatif_field, mapper, rationale)
# Only defensible semantic equivalences established from generator code.
CHALLENGE_TO_WHATIF_MAPPERS: dict[str, tuple[str, _MapperFn, str]] = {
    "demand.multiplier": (
        "congestion_multiplier",
        _as_congestion_multiplier,
        "demand.multiplier ↔ SyntheticScenarioConfig.congestion_multiplier "
        "(generator: demand.multiplier = max(0.1, congestion_multiplier))",
    ),
    "workload.birth_rate_multiplier": (
        "task_arrival_rate",
        _as_birth_rate_multiplier,
        "workload.birth_rate_multiplier ↔ SyntheticScenarioConfig.task_arrival_rate "
        "(generator: birth_rate_multiplier = max(0.1, task_arrival_rate/0.10))",
    ),
    "infrastructure.rsu_count": (
        "rsu_count",
        _as_rsu_count,
        "infrastructure.rsu_count ↔ SyntheticScenarioConfig.rsu_count (direct)",
    ),
    "fleet.count": (
        "vehicle_count",
        _as_fleet_count,
        "fleet.count ↔ SyntheticScenarioConfig.vehicle_count (direct)",
    ),
    "evaluation.random_seed": (
        "random_seed",
        _as_random_seed,
        "evaluation.random_seed ↔ SyntheticScenarioConfig.random_seed (direct)",
    ),
    "traffic.event_type": (
        "incident_type",
        _as_traffic_event_type,
        "traffic.event_type ↔ IncidentSpec.incident_type "
        "(generator: traffic.event_type = first_incident.incident_type)",
    ),
    "traffic.location": (
        "incident_location",
        _as_traffic_location,
        "traffic.location ↔ IncidentSpec.location "
        "(generator: traffic.location = first_incident.location)",
    ),
    "traffic.lanes_closed": (
        "lanes_closed",
        _as_lanes_closed,
        "traffic.lanes_closed ↔ IncidentSpec.lanes_closed (direct)",
    ),
    "traffic.duration_min": (
        "incident_duration_s",
        _as_duration_min,
        "traffic.duration_min ↔ IncidentSpec.duration_s "
        "(generator: duration_min = duration_s/60, What-If: incident_duration_s)",
    ),
    "traffic.event_demand_multiplier": (
        "event_demand_multiplier",
        _as_event_demand_multiplier,
        "traffic.event_demand_multiplier ↔ IncidentSpec.demand_multiplier "
        "(generator: event_demand_multiplier = first_incident.demand_multiplier)",
    ),
}

# Challenge paths that are explicitly unsupported with a reason
# (no invented numeric inverse, no silent drop)
_UNSUPPORTED_REASONS: dict[str, str] = {
    "infrastructure.rsu_capacity_mode": (
        "UNSUPPORTED BY CURRENT WHAT-IF CONTROLS — abstract rsu_capacity_mode "
        "(REDUCED/STANDARD/EXPANDED) has no scientifically authoritative numeric "
        "rsu_capacity inverse; TrafficTwin does not invent a mapping."
    ),
    "fleet.tier_mix": (
        "UNSUPPORTED BY CURRENT WHAT-IF CONTROLS — fleet.tier_mix (WEAK/MIXED/"
        "HIGH_COMPUTE) has no direct What-If control; generator derives tier_mix "
        "from vehicle_tier_mix threshold, not a reversible What-If field."
    ),
    "workload.ordering": (
        "UNSUPPORTED BY CURRENT WHAT-IF CONTROLS — workload.ordering "
        "(EASY_FIRST/MIXED/HARD_FIRST) has no What-If Studio control; "
        "generator hardcodes ordering=MIXED."
    ),
}

# Generic unsupported reason for unknown paths
_GENERIC_UNSUPPORTED_REASON = (
    "UNSUPPORTED BY CURRENT WHAT-IF CONTROLS — no defensible semantic equivalence "
    "to an existing What-If Studio control has been established for this field."
)


def _fingerprint_draft(
    challenge_id: str,
    supported: list[ChallengeWhatIfMappedField],
    unsupported: list[ChallengeWhatIfUnsupportedField],
    overrides: dict[str, Any],
    source_status: str,
) -> str:
    payload = {
        "challenge_id": challenge_id,
        "source_status": source_status,
        "supported": sorted(
            [(f.challenge_path, f.whatif_field, f.mapped_value) for f in supported],
            key=lambda x: x[0],
        ),
        "unsupported": sorted(
            [(f.challenge_path, str(f.challenge_value)) for f in unsupported],
            key=lambda x: x[0],
        ),
        "overrides": {k: overrides[k] for k in sorted(overrides)},
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _build_overrides_dict(
    mapped_fields: list[ChallengeWhatIfMappedField],
) -> dict[str, Any]:
    """Merge mapped fields into a WhatIfVariationOverrides-compatible dict.

    Handles class_mix expansion into three separate fields and incident
    enablement inference.
    """
    overrides: dict[str, Any] = {}
    has_incident_field = False
    for field in mapped_fields:
        if field.challenge_path == "workload.class_mix":
            # mapped_value is dict {"T1":..., "T2":..., "T3":...}
            cm = field.mapped_value
            if isinstance(cm, dict):
                overrides["task_mix_t1"] = cm.get("T1")
                overrides["task_mix_t2"] = cm.get("T2")
                overrides["task_mix_t3"] = cm.get("T3")
            continue
        # Regular single-field mapping
        overrides[field.whatif_field] = field.mapped_value
        if field.whatif_field in (
            "incident_type",
            "incident_location",
            "incident_duration_s",
            "lanes_closed",
            "event_demand_multiplier",
        ):
            has_incident_field = True
    # If any incident field was mapped, ensure incident_enabled is set
    if has_incident_field:
        overrides["incident_enabled"] = True
    return overrides


def build_challenge_whatif_draft(
    challenge: ChallengeSeedDefinition,
) -> ChallengeWhatIfDraft:
    """Build a deterministic bridge draft for one challenge.

    Pure function: does not touch session state, does not mutate inputs.
    """
    # Defensive deep copy of overrides to avoid mutation
    overrides_in = dict(challenge.parameter_overrides)

    supported: list[ChallengeWhatIfMappedField] = []
    unsupported: list[ChallengeWhatIfUnsupportedField] = []

    for path, value in overrides_in.items():
        # Special handling for workload.class_mix dict
        if path == "workload.class_mix":
            try:
                mapped = _as_class_mix(value)
                # Validate each share against control spec
                t1_ok, t1_reason = is_value_representable("task_mix_t1", mapped["T1"])
                t2_ok, t2_reason = is_value_representable("task_mix_t2", mapped["T2"])
                t3_ok, t3_reason = is_value_representable("task_mix_t3", mapped["T3"])
                if not (t1_ok and t2_ok and t3_ok):
                    reasons: list[str] = []
                    if not t1_ok:
                        reasons.append(str(t1_reason))
                    if not t2_ok:
                        reasons.append(str(t2_reason))
                    if not t3_ok:
                        reasons.append(str(t3_reason))
                    unsupported.append(
                        ChallengeWhatIfUnsupportedField(
                            challenge_path=path,
                            challenge_value=value,
                            reason=(
                                "UNSUPPORTED BY CURRENT WHAT-IF CONTROLS — "
                                + "; ".join(reasons)
                                + f" — mapped {mapped} from {path}"
                            ),
                        )
                    )
                else:
                    supported.append(
                        ChallengeWhatIfMappedField(
                            challenge_path=path,
                            challenge_value=value,
                            whatif_field="task_mix_t1/task_mix_t2/task_mix_t3",
                            mapped_value=mapped,
                            rationale=(
                                "workload.class_mix ↔ SyntheticScenarioConfig.task_class_mix "
                                "(generator: class_mix = {TaskClass: share} ↔ "
                                "task_class_mix dict; What-If: task_mix_t1/t2/t3)"
                            ),
                        )
                    )
            except (ValueError, TypeError) as exc:
                unsupported.append(
                    ChallengeWhatIfUnsupportedField(
                        challenge_path=path,
                        challenge_value=value,
                        reason=f"workload.class_mix conversion failed: {exc}",
                    )
                )
            continue

        # Check registry
        mapper_entry = CHALLENGE_TO_WHATIF_MAPPERS.get(path)
        if mapper_entry is not None:
            whatif_field, fn, rationale = mapper_entry
            try:
                mapped_value = fn(value)
                # Range / representability check against shared control spec (fail closed)
                ok, reason = is_value_representable(whatif_field, mapped_value)
                if not ok:
                    unsupported.append(
                        ChallengeWhatIfUnsupportedField(
                            challenge_path=path,
                            challenge_value=value,
                            reason=(
                                f"UNSUPPORTED BY CURRENT WHAT-IF CONTROLS — "
                                f"{reason} — mapped {whatif_field}={mapped_value} from "
                                f"{path}={value!r}"
                            ),
                        )
                    )
                else:
                    supported.append(
                        ChallengeWhatIfMappedField(
                            challenge_path=path,
                            challenge_value=value,
                            whatif_field=whatif_field,
                            mapped_value=mapped_value,
                            rationale=rationale,
                        )
                    )
            except (ValueError, TypeError) as exc:
                unsupported.append(
                    ChallengeWhatIfUnsupportedField(
                        challenge_path=path,
                        challenge_value=value,
                        reason=f"{_GENERIC_UNSUPPORTED_REASON} Conversion failed: {exc}",
                    )
                )
            continue

        # Explicit unsupported
        if path in _UNSUPPORTED_REASONS:
            unsupported.append(
                ChallengeWhatIfUnsupportedField(
                    challenge_path=path,
                    challenge_value=value,
                    reason=_UNSUPPORTED_REASONS[path],
                )
            )
            continue

        # Unknown path — never ignored
        unsupported.append(
            ChallengeWhatIfUnsupportedField(
                challenge_path=path,
                challenge_value=value,
                reason=f"{_GENERIC_UNSUPPORTED_REASON} (unknown challenge path: {path})",
            )
        )

    # Validate resulting overrides against WhatIfVariationOverrides schema
    # by constructing a temporary instance (fail closed)
    overrides_dict = _build_overrides_dict(supported)
    warnings: list[str] = []
    if overrides_dict:
        try:
            WhatIfVariationOverrides.model_validate(overrides_dict)
        except Exception as exc:
            # If validation fails, mark affected fields as unsupported
            # This is defensive — our mappers should produce valid values
            warnings.append(f"Override validation warning: {exc}")

    # Determine mapping status
    total = len(supported) + len(unsupported)
    if total == 0:
        mapping_status = ChallengeWhatIfMappingStatus.NOT_MAPPABLE
        warnings.append("Challenge has no parameter overrides to map.")
    elif len(supported) == 0:
        mapping_status = ChallengeWhatIfMappingStatus.NOT_MAPPABLE
    elif len(unsupported) == 0:
        mapping_status = ChallengeWhatIfMappingStatus.FULLY_MAPPABLE
    else:
        mapping_status = ChallengeWhatIfMappingStatus.PARTIALLY_MAPPABLE

    if mapping_status == ChallengeWhatIfMappingStatus.PARTIALLY_MAPPABLE:
        warnings.append(
            "Only the supported subset will be prefilled. "
            "The generated What-If pair must not be interpreted as exact "
            "execution of the original challenge."
        )
    elif mapping_status == ChallengeWhatIfMappingStatus.NOT_MAPPABLE and total > 0:
        warnings.append(
            "No challenge fields are representable with current What-If controls. "
            "The challenge remains REPRESENTABLE_ONLY."
        )

    fingerprint = _fingerprint_draft(
        challenge.challenge_id,
        supported,
        unsupported,
        overrides_dict,
        challenge.status.value,
    )

    # Sort for deterministic output
    supported_sorted = sorted(supported, key=lambda f: f.challenge_path)
    unsupported_sorted = sorted(unsupported, key=lambda f: f.challenge_path)

    return ChallengeWhatIfDraft(
        challenge_id=challenge.challenge_id,
        challenge_title=challenge.title,
        mapping_status=mapping_status,
        supported_fields=supported_sorted,
        unsupported_fields=unsupported_sorted,
        whatif_overrides=overrides_dict,
        warnings=warnings,
        fingerprint=fingerprint,
        evidence_standing=challenge.evidence_standing,
        source_status=challenge.status.value,
    )


def build_draft_for_challenge_id(challenge_id: str) -> ChallengeWhatIfDraft | None:
    """Convenience: build draft from challenge library by ID."""
    challenge = get_challenge_seed(challenge_id)
    if challenge is None:
        return None
    return build_challenge_whatif_draft(challenge)


def draft_to_handoff_dict(draft: ChallengeWhatIfDraft) -> dict[str, Any]:
    """Convert draft to JSON-safe session handoff dict (no paths/secrets)."""
    return draft.model_dump(mode="json")


def draft_from_handoff_dict(data: dict[str, Any]) -> ChallengeWhatIfDraft:
    """Rehydrate draft from handoff dict."""
    return ChallengeWhatIfDraft.model_validate(data)


def is_valid_handoff_dict(data: Any) -> bool:  # noqa: ANN401
    """Return True if data looks like a valid handoff payload."""
    if not isinstance(data, dict):
        return False
    required = {"challenge_id", "mapping_status", "whatif_overrides", "fingerprint"}
    return required.issubset(data.keys())
