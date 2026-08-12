"""Service layer for Metric Contract Registry — validation, fingerprint, merge, CSV."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from traffictwin.experiments.resource_strategy import (
    EXPECTED_METRIC_CONTRACT,
    RESERVED_METRIC_KEYS,
    ResourceStrategyMetricDenominator,
)

from .models import (
    MetricContract,
    MetricContractCompatibility,
    MetricContractCompatibilityStatus,
    MetricContractDenominator,
    MetricContractFinding,
    MetricContractFindingSeverity,
    MetricContractRegistry,
    MetricContractRegistryReceipt,
    MetricContractStatus,
    MetricContractSupersession,
)

# ---------------------------------------------------------------------------
# Built-in contracts
# ---------------------------------------------------------------------------


def _built_in_contracts() -> list[MetricContract]:
    contracts: list[MetricContract] = []
    for key, (version, unit, denom) in EXPECTED_METRIC_CONTRACT.items():
        # Map ResourceStrategyMetricDenominator to MetricContractDenominator via value
        mc_denom = MetricContractDenominator(denom.value)
        contracts.append(
            MetricContract(
                metric_key=key,
                metric_version=version,
                unit=unit,
                denominator=mc_denom,
                description=f"Built-in metric {key} (authoritative)",
                higher_is_better=None,
                direction="neutral",
                time_window_applicable=False,
                contract_version="1.0",
            )
        )
    return contracts


def _built_in_map() -> dict[tuple[str, str], MetricContract]:
    return {(c.metric_key, c.metric_version): c for c in _built_in_contracts()}


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _check_built_in_override(
    contract: MetricContract,
) -> tuple[bool, bool]:
    """Return (is_built_in_key, is_conflicting).

    If metric_key exists in built-in set:
      - identical definition (version/unit/denom match built-in) -> not conflicting
      - otherwise -> conflicting
    """
    for builtin in _built_in_contracts():
        if builtin.metric_key == contract.metric_key:
            # Same key exists in built-in
            if (
                builtin.metric_version == contract.metric_version
                and builtin.unit == contract.unit
                and builtin.denominator == contract.denominator
            ):
                return True, False
            return True, True
    return False, False


def validate_registry(
    registry: MetricContractRegistry,
) -> MetricContractRegistryReceipt:
    findings: list[MetricContractFinding] = []
    built_in_conflicts: list[str] = []

    # Check each contract against built-in authority
    for contract in registry.contracts:
        is_builtin, is_conflicting = _check_built_in_override(contract)
        if is_builtin and is_conflicting:
            built_in_conflicts.append(contract.metric_key)
            findings.append(
                MetricContractFinding(
                    code="BUILT_IN_OVERRIDE_REJECTED",
                    severity=MetricContractFindingSeverity.ERROR,
                    message=(
                        f"Custom contract {contract.metric_key!r} version {contract.metric_version!r} "  # noqa: E501
                        "conflicts with authoritative built-in contract: same key but different "
                        f"unit {contract.unit!r} or denominator {contract.denominator.value!r} or version"  # noqa: E501
                    ),
                    metric_key=contract.metric_key,
                    metric_version=contract.metric_version,
                )
            )
        elif is_builtin and not is_conflicting:
            findings.append(
                MetricContractFinding(
                    code="BUILT_IN_REDUNDANT_REFERENCE",
                    severity=MetricContractFindingSeverity.INFO,
                    message=(
                        f"Contract {contract.metric_key!r} version {contract.metric_version!r} "
                        "is identical to authoritative built-in; accepted as redundant/reference"
                    ),
                    metric_key=contract.metric_key,
                    metric_version=contract.metric_version,
                )
            )

    status = MetricContractStatus.VALID
    if built_in_conflicts or any(
        f.severity == MetricContractFindingSeverity.ERROR for f in findings
    ):  # noqa: E501
        status = MetricContractStatus.REJECTED

    # Deduplicate identical contracts: receipt should reflect deduplicated count?
    deduped = registry.deduplicated_contracts()
    return MetricContractRegistryReceipt(
        registry_fingerprint=registry.fingerprint(),
        registry_version=registry.registry_version,
        contract_count=len(deduped),
        status=status,
        findings=findings,
        supersession_count=len(registry.supersession),
        built_in_conflicts=built_in_conflicts,
        is_deterministic=True,
    )


def fingerprint_registry(registry: MetricContractRegistry) -> str:
    return registry.fingerprint()


def registry_to_canonical_json(registry: MetricContractRegistry) -> str:
    return registry.canonical_json()


def registry_to_json(registry: MetricContractRegistry) -> str:
    return registry.to_json()


def registry_to_csv(registry: MetricContractRegistry) -> str:
    """Export registry contracts as deterministic CSV."""
    fieldnames = [
        "metric_key",
        "metric_version",
        "unit",
        "denominator",
        "description",
        "higher_is_better",
        "direction",
        "time_window_applicable",
        "minimum",
        "maximum",
        "allowed_statuses",
        "provenance",
        "citation",
        "contract_version",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for contract in registry.deduplicated_contracts():
        writer.writerow(
            {
                "metric_key": contract.metric_key,
                "metric_version": contract.metric_version,
                "unit": contract.unit,
                "denominator": contract.denominator.value,
                "description": contract.description,
                "higher_is_better": contract.higher_is_better,
                "direction": contract.direction.value if contract.direction else "",
                "time_window_applicable": contract.time_window_applicable,
                "minimum": repr(contract.minimum) if contract.minimum is not None else "",
                "maximum": repr(contract.maximum) if contract.maximum is not None else "",
                "allowed_statuses": ";".join(contract.allowed_statuses)
                if contract.allowed_statuses
                else "",
                "provenance": contract.provenance or "",
                "citation": contract.citation or "",
                "contract_version": contract.contract_version,
            }
        )
    return output.getvalue()


# ---------------------------------------------------------------------------
# Import / Export
# ---------------------------------------------------------------------------


def load_registry_from_dict(payload: dict[str, Any]) -> MetricContractRegistry:
    return MetricContractRegistry.model_validate(payload)


def load_registry_from_json(text: str) -> MetricContractRegistry:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("registry JSON must be an object")
    # Allow payload with extra 'fingerprint' field from to_json export; strip it
    data = dict(data)
    data.pop("fingerprint", None)
    return load_registry_from_dict(data)


def load_registry_from_file(path: str | Path) -> MetricContractRegistry:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    return load_registry_from_json(text)


def parse_registry_json(text: str) -> MetricContractRegistry:
    return load_registry_from_json(text)


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


def merge_registries(
    registries: list[MetricContractRegistry],
) -> tuple[MetricContractRegistry, MetricContractRegistryReceipt]:
    """Merge multiple registries deterministically.

    - Deterministic order: contracts sorted, supersession merged.
    - Unique key/version: duplicates must be identical or merge fails.
    - Built-in conflicts are reported via receipt findings.
    """
    if not registries:
        empty = MetricContractRegistry(registry_version="1.0", contracts=[], supersession=[])
        receipt = validate_registry(empty)
        return empty, receipt

    # Collect all contracts
    all_contracts: list[MetricContract] = []
    all_supersession: list[MetricContractSupersession] = []
    registry_version = registries[0].registry_version
    for reg in registries:
        all_contracts.extend(reg.contracts)
        all_supersession.extend(reg.supersession)
        # Use latest registry_version (lexicographically) deterministically
        if reg.registry_version > registry_version:
            registry_version = reg.registry_version

    # Deduplicate identical contracts: check conflicting duplicates
    seen: dict[tuple[str, str], MetricContract] = {}
    for contract in all_contracts:
        contract_key = (contract.metric_key, contract.metric_version)
        if contract_key in seen:
            if seen[contract_key].canonical_payload() != contract.canonical_payload():
                raise ValueError(
                    f"merge conflict: conflicting duplicate for {contract.metric_key!r} "
                    f"version {contract.metric_version!r}"
                )
            # identical duplicate -> redundant, ignore
            continue
        seen[contract_key] = contract

    # Supersession deduplication
    seen_succ: dict[tuple[str, str, str, str], MetricContractSupersession] = {}
    for sup in all_supersession:
        succ_key = (
            sup.predecessor_metric_key,
            sup.predecessor_metric_version,
            sup.successor_metric_key,
            sup.successor_metric_version,
        )
        if succ_key in seen_succ:
            if seen_succ[succ_key].reason != sup.reason:
                raise ValueError(f"merge conflict: supersession lineage conflict for {succ_key!r}")
            continue
        seen_succ[succ_key] = sup

    merged = MetricContractRegistry(
        registry_version=registry_version,
        contracts=list(seen.values()),
        supersession=list(seen_succ.values()),
    )
    receipt = validate_registry(merged)
    if receipt.status == MetricContractStatus.REJECTED:
        # Do not silently succeed; caller can inspect receipt
        pass
    return merged, receipt


# ---------------------------------------------------------------------------
# Resource Strategy integration helpers
# ---------------------------------------------------------------------------


def _denom_to_resource(denom: MetricContractDenominator) -> ResourceStrategyMetricDenominator:
    return ResourceStrategyMetricDenominator(denom.value)


def _denom_to_contract(denom: ResourceStrategyMetricDenominator) -> MetricContractDenominator:
    return MetricContractDenominator(denom.value)


def check_resource_strategy_compatibility(
    study_metric_key: str,
    study_metric_version: str,
    study_unit: str,
    study_denominator: ResourceStrategyMetricDenominator,
    *,
    registry: MetricContractRegistry | None,
    arm_contracts: dict[str, tuple[str, str, ResourceStrategyMetricDenominator]] | None = None,
) -> MetricContractCompatibility:
    """Check compatibility for a single metric across arms.

    - If metric is built-in (in EXPECTED_METRIC_CONTRACT), no registry needed: handled by
      built-in logic (but this helper is for custom metrics).
    - If registry is None and metric is custom -> UNAVAILABLE
    - If registry contains contract, verify every arm agrees on version/unit/denominator.

    ``arm_contracts`` maps arm_id -> (version, unit, denominator) for that metric.
    If None, implies all arms use the study-level contract (global). If provided,
    cross-arm consistency is checked explicitly (mutation target).
    """
    # Custom metric path
    if registry is None:
        return MetricContractCompatibility(
            metric_key=study_metric_key,
            metric_version=study_metric_version,
            status=MetricContractCompatibilityStatus.UNAVAILABLE,
            unit=study_unit,
            denominator=_denom_to_contract(study_denominator),
            finding="no registered compatibility contract; metric comparison not verified",
            arm_versions=[study_metric_version],
            arm_units=[study_unit],
            arm_denominators=[study_denominator.value],
        )

    # Lookup in registry by key/version
    contract = registry.get_contract(study_metric_key, study_metric_version)
    if contract is None:
        # Check if key exists with different version
        by_key = registry.find_by_key(study_metric_key)
        if by_key:
            versions = sorted({c.metric_version for c in by_key})
            return MetricContractCompatibility(
                metric_key=study_metric_key,
                metric_version=study_metric_version,
                status=MetricContractCompatibilityStatus.INCOMPATIBLE,
                unit=study_unit,
                denominator=_denom_to_contract(study_denominator),
                finding=(
                    f"incompatible: version {study_metric_version!r} != registered {versions!r}; "
                    "every arm must agree on metric version"
                ),
                arm_versions=[study_metric_version],
                arm_units=[study_unit],
                arm_denominators=[study_denominator.value],
            )
        return MetricContractCompatibility(
            metric_key=study_metric_key,
            metric_version=study_metric_version,
            status=MetricContractCompatibilityStatus.UNAVAILABLE,
            unit=study_unit,
            denominator=_denom_to_contract(study_denominator),
            finding="no registered compatibility contract; metric comparison not verified",
            arm_versions=[study_metric_version],
            arm_units=[study_unit],
            arm_denominators=[study_denominator.value],
        )

    # Registry contract exists — check study catalog matches registry
    mismatches: list[str] = []
    if contract.metric_version != study_metric_version:
        mismatches.append(
            f"version {study_metric_version!r} != registered {contract.metric_version!r}"
        )
    if contract.unit != study_unit:
        mismatches.append(f"unit {study_unit!r} != registered {contract.unit!r}")
    if contract.denominator.value != study_denominator.value:
        mismatches.append(
            f"denominator {study_denominator.value!r} != registered {contract.denominator.value!r}"
        )
    if mismatches:
        return MetricContractCompatibility(
            metric_key=study_metric_key,
            metric_version=study_metric_version,
            status=MetricContractCompatibilityStatus.INCOMPATIBLE,
            unit=study_unit,
            denominator=_denom_to_contract(study_denominator),
            finding="incompatible: " + "; ".join(mismatches),
            arm_versions=[study_metric_version],
            arm_units=[study_unit],
            arm_denominators=[study_denominator.value],
        )

    # Now cross-arm consistency check — every arm must agree on version/unit/denominator
    # This is the mutation target: removing this check should make incompatible arm appear comparable.  # noqa: E501
    if arm_contracts is not None:
        # Explicit per-arm overrides supplied (for testing arm mismatch)
        per_arm_versions = {v for v, _, _ in arm_contracts.values()}
        per_arm_units = {u for _, u, _ in arm_contracts.values()}
        per_arm_denoms = {
            d.value if hasattr(d, "value") else str(d) for _, _, d in arm_contracts.values()
        }
        if len(per_arm_versions) > 1 or len(per_arm_units) > 1 or len(per_arm_denoms) > 1:
            parts: list[str] = []
            if len(per_arm_versions) > 1:
                parts.append(f"versions {sorted(per_arm_versions)!r} differ across arms")
            if len(per_arm_units) > 1:
                parts.append(f"units {sorted(per_arm_units)!r} differ across arms")
            if len(per_arm_denoms) > 1:
                parts.append(f"denominators {sorted(per_arm_denoms)!r} differ across arms")
            return MetricContractCompatibility(
                metric_key=study_metric_key,
                metric_version=study_metric_version,
                status=MetricContractCompatibilityStatus.INCOMPATIBLE,
                unit=study_unit,
                denominator=_denom_to_contract(study_denominator),
                finding="incompatible: " + "; ".join(parts) + "; every arm must agree",
                arm_versions=sorted(per_arm_versions),
                arm_units=sorted(per_arm_units),
                arm_denominators=sorted(per_arm_denoms),
            )
        # Also check that arm contracts match registry
        for arm_id, (ver, unit, denom) in arm_contracts.items():
            if (
                ver != contract.metric_version
                or unit != contract.unit
                or denom.value != contract.denominator.value
            ):
                return MetricContractCompatibility(
                    metric_key=study_metric_key,
                    metric_version=study_metric_version,
                    status=MetricContractCompatibilityStatus.INCOMPATIBLE,
                    unit=study_unit,
                    denominator=_denom_to_contract(study_denominator),
                    finding=(
                        f"incompatible: arm {arm_id!r} contract "
                        f"({ver!r},{unit!r},{denom.value!r}) != registered "
                        f"({contract.metric_version!r},{contract.unit!r},{contract.denominator.value!r})"  # noqa: E501
                    ),
                    arm_versions=sorted(per_arm_versions),
                    arm_units=sorted(per_arm_units),
                    arm_denominators=sorted(per_arm_denoms),
                )

    # All checks passed -> compatible
    arm_versions_final = sorted(
        {arm_contracts[arm][0] for arm in arm_contracts}
        if arm_contracts
        else {study_metric_version}
    )
    arm_units_final = sorted(
        {arm_contracts[arm][1] for arm in arm_contracts} if arm_contracts else {study_unit}
    )
    arm_denoms_final = sorted(
        {arm_contracts[arm][2].value for arm in arm_contracts}
        if arm_contracts
        else {study_denominator.value}
    )
    return MetricContractCompatibility(
        metric_key=study_metric_key,
        metric_version=study_metric_version,
        status=MetricContractCompatibilityStatus.COMPATIBLE,
        unit=study_unit,
        denominator=_denom_to_contract(study_denominator),
        finding="compatible across matched cohort via registered contract",
        arm_versions=arm_versions_final,
        arm_units=arm_units_final,
        arm_denominators=arm_denoms_final,
    )


def is_built_in_metric(metric_key: str) -> bool:
    return metric_key in RESERVED_METRIC_KEYS or metric_key in EXPECTED_METRIC_CONTRACT


def build_built_in_registry() -> MetricContractRegistry:
    """Return a registry containing only built-in contracts (authoritative)."""
    return MetricContractRegistry(
        registry_version="1.0",
        contracts=_built_in_contracts(),
        supersession=[],
    )
