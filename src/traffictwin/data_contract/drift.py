"""Deterministic schema-drift comparison against a frozen contract."""

from __future__ import annotations

import json

from traffictwin.data_contract.fingerprint import fingerprint_canonical
from traffictwin.data_contract.models import (
    FieldContract,
    FieldObservation,
    LogicalType,
    RightsAndRetentionContract,
    SchemaDriftFinding,
    SchemaDriftReport,
    SchemaDriftSeverity,
    SchemaObservation,
    SourceContractVersion,
    SourceDataContract,
)

# ---------------------------------------------------------------------------
# Type-compatibility matrix
# ---------------------------------------------------------------------------

_WIDENING: dict[LogicalType, set[LogicalType]] = {
    LogicalType.INTEGER: {LogicalType.FLOAT, LogicalType.DECIMAL},
    LogicalType.FLOAT: {LogicalType.DECIMAL},
    LogicalType.CATEGORICAL: {LogicalType.STRING},
}

_BLOCKED_TYPE_CHANGES: set[tuple[LogicalType, LogicalType]] = {
    (LogicalType.STRING, LogicalType.INTEGER),
    (LogicalType.STRING, LogicalType.FLOAT),
    (LogicalType.STRING, LogicalType.BOOLEAN),
    (LogicalType.STRING, LogicalType.DECIMAL),
    (LogicalType.STRING, LogicalType.TIMESTAMP),
    (LogicalType.INTEGER, LogicalType.STRING),
    (LogicalType.INTEGER, LogicalType.BOOLEAN),
    (LogicalType.INTEGER, LogicalType.TIMESTAMP),
    (LogicalType.FLOAT, LogicalType.STRING),
    (LogicalType.FLOAT, LogicalType.BOOLEAN),
    (LogicalType.FLOAT, LogicalType.TIMESTAMP),
    (LogicalType.DECIMAL, LogicalType.STRING),
    (LogicalType.DECIMAL, LogicalType.BOOLEAN),
    (LogicalType.DECIMAL, LogicalType.TIMESTAMP),
    (LogicalType.TIMESTAMP, LogicalType.STRING),
    (LogicalType.TIMESTAMP, LogicalType.INTEGER),
    (LogicalType.TIMESTAMP, LogicalType.FLOAT),
    (LogicalType.TIMESTAMP, LogicalType.BOOLEAN),
    (LogicalType.TIMESTAMP, LogicalType.DECIMAL),
    (LogicalType.BOOLEAN, LogicalType.INTEGER),
    (LogicalType.BOOLEAN, LogicalType.FLOAT),
    (LogicalType.BOOLEAN, LogicalType.DECIMAL),
    (LogicalType.BOOLEAN, LogicalType.TIMESTAMP),
    (LogicalType.CATEGORICAL, LogicalType.INTEGER),
    (LogicalType.CATEGORICAL, LogicalType.FLOAT),
    (LogicalType.CATEGORICAL, LogicalType.DECIMAL),
    (LogicalType.CATEGORICAL, LogicalType.BOOLEAN),
    (LogicalType.CATEGORICAL, LogicalType.TIMESTAMP),
}


def _is_widening(from_type: LogicalType, to_type: LogicalType) -> bool:
    return to_type in _WIDENING.get(from_type, set())


def _is_blocked_type_change(from_type: LogicalType, to_type: LogicalType) -> bool:
    if from_type == to_type:
        return False
    if (from_type, to_type) in _BLOCKED_TYPE_CHANGES:
        return True
    return from_type is LogicalType.TIMESTAMP and to_type is not LogicalType.TIMESTAMP


# ---------------------------------------------------------------------------
# Core comparison
# ---------------------------------------------------------------------------


def compare_observation_to_contract(
    contract_version: SourceContractVersion,
    observation: SchemaObservation,
    *,
    candidate_contract: SourceDataContract | None = None,
) -> SchemaDriftReport:
    """Compare *observation* (or *candidate_contract*) against a frozen contract."""
    if not contract_version.is_frozen:
        raise ValueError("drift comparison requires a frozen contract version")

    contract = contract_version.contract
    findings: list[SchemaDriftFinding] = []

    # Source identity drift
    if candidate_contract is not None and candidate_contract.source_id != contract.source_id:
        findings.append(
            SchemaDriftFinding(
                field_name=None,
                severity=SchemaDriftSeverity.BLOCKED,
                code="SOURCE_IDENTITY_CHANGED",
                message=(
                    f"source_id changed from '{contract.source_id}' to "
                    f"'{candidate_contract.source_id}' without amendment"
                ),
                details={
                    "expected": contract.source_id,
                    "observed": candidate_contract.source_id,
                },
            )
        )

    # Rights drift (requires candidate contract)
    if candidate_contract is not None:
        findings.extend(_compare_rights(contract.rights, candidate_contract.rights))

    # Field-level drift – driven by contract vs observation, but if candidate
    # contract is present, field-set union is handled in compare_contracts
    # (which synthesizes observation). Here we handle observation-only path.
    contract_fields = contract.field_map()
    observed_map = observation.field_map()

    for field_name, fc in contract_fields.items():
        if fc.required and field_name not in observed_map:
            findings.append(
                SchemaDriftFinding(
                    field_name=field_name,
                    severity=SchemaDriftSeverity.BLOCKED,
                    code="REQUIRED_FIELD_REMOVED",
                    message=f"required field '{field_name}' is missing in candidate sample",
                    details={"expected": "required", "observed": "absent"},
                )
            )
        elif not fc.required and field_name not in observed_map:
            findings.append(
                SchemaDriftFinding(
                    field_name=field_name,
                    severity=SchemaDriftSeverity.COMPATIBLE,
                    code="OPTIONAL_FIELD_ABSENT",
                    message=f"optional field '{field_name}' absent – consistent with contract",
                    details={"expected": "optional", "observed": "absent"},
                )
            )

    for field_name, obs in observed_map.items():
        fc_opt = contract_fields.get(field_name)
        if fc_opt is None:
            findings.append(
                SchemaDriftFinding(
                    field_name=field_name,
                    severity=SchemaDriftSeverity.REVIEW_REQUIRED,
                    code="OPTIONAL_FIELD_ADDED",
                    message=f"field '{field_name}' present in candidate but not in frozen contract",
                    details={"expected": "absent", "observed": obs.observed_logical_type.value},
                )
            )
            continue

        fc = fc_opt
        type_finding = _classify_type_drift(fc, obs)
        if type_finding is not None:
            findings.append(type_finding)

        if obs.nullable and fc.required:
            findings.append(
                SchemaDriftFinding(
                    field_name=field_name,
                    severity=SchemaDriftSeverity.REVIEW_REQUIRED,
                    code="REQUIRED_FIELD_BECOMES_NULLABLE",
                    message=f"required field '{field_name}' has nulls in candidate sample",
                    details={
                        "expected": "non-nullable required",
                        "observed": f"nullable ({obs.null_count}/{obs.observed_count} nulls)",
                    },
                )
            )
        elif not obs.nullable:
            findings.append(
                SchemaDriftFinding(
                    field_name=field_name,
                    severity=SchemaDriftSeverity.COMPATIBLE,
                    code="NULLABILITY_COMPATIBLE",
                    message=f"field '{field_name}' nullability compatible",
                    details={
                        "expected": "non-nullable" if fc.required else "optional",
                        "observed": "non-nullable",
                    },
                )
            )

        # Unit drift
        if candidate_contract is not None:
            cand_fc = candidate_contract.field_map().get(field_name)
            if cand_fc is not None and (fc.unit is not None or cand_fc.unit is not None):
                unit_finding = _classify_unit_drift(fc, cand_fc, field_name)
                if unit_finding is not None:
                    findings.append(unit_finding)

        # Timestamp drift
        if candidate_contract is not None:
            cand_fc2 = candidate_contract.field_map().get(field_name)
            if cand_fc2 is not None and (
                fc.timestamp is not None or cand_fc2.timestamp is not None
            ):
                ts_finding = _classify_timestamp_drift(fc, cand_fc2, field_name)
                if ts_finding is not None:
                    findings.append(ts_finding)
        elif fc.logical_type is LogicalType.TIMESTAMP:
            ts_obs_finding = _classify_timestamp_observation_drift(fc, obs)
            if ts_obs_finding is not None:
                findings.append(ts_obs_finding)

    # Column reordering
    obs_order = [fo.field_name for fo in observation.field_observations]
    contract_order = [f.field_name for f in contract.fields]
    if set(obs_order) == set(contract_order) and obs_order != contract_order:
        findings.append(
            SchemaDriftFinding(
                field_name=None,
                severity=SchemaDriftSeverity.COMPATIBLE,
                code="COLUMN_REORDERING",
                message="column order differs but field set matches contract",
                details={"expected": ",".join(contract_order), "observed": ",".join(obs_order)},
            )
        )
    elif set(obs_order) == set(contract_order) and obs_order == contract_order:
        findings.append(
            SchemaDriftFinding(
                field_name=None,
                severity=SchemaDriftSeverity.COMPATIBLE,
                code="COLUMN_ORDER_COMPATIBLE",
                message="column order matches contract",
                details={"expected": ",".join(contract_order), "observed": ",".join(obs_order)},
            )
        )

    return _build_report(contract_version, observation, findings)


def _build_report(
    contract_version: SourceContractVersion,
    observation: SchemaObservation,
    findings: list[SchemaDriftFinding],
) -> SchemaDriftReport:
    overall = SchemaDriftSeverity.COMPATIBLE
    for f in findings:
        if f.severity is SchemaDriftSeverity.BLOCKED:
            overall = SchemaDriftSeverity.BLOCKED
            break
        if f.severity is SchemaDriftSeverity.REVIEW_REQUIRED:
            overall = SchemaDriftSeverity.REVIEW_REQUIRED

    blocked = sum(1 for f in findings if f.severity is SchemaDriftSeverity.BLOCKED)
    review = sum(1 for f in findings if f.severity is SchemaDriftSeverity.REVIEW_REQUIRED)
    compatible = sum(1 for f in findings if f.severity is SchemaDriftSeverity.COMPATIBLE)
    summary = {
        "blocked": blocked,
        "review_required": review,
        "compatible": compatible,
        "total": len(findings),
    }

    report_payload = {
        "schema_version": "1.0",
        "contract_fingerprint": contract_version.fingerprint,
        "candidate_fingerprint": observation.fingerprint,
        "contract_version": contract_version.version,
        "source_id": contract_version.contract.source_id,
        "overall_severity": overall.value,
        "findings": sorted(
            [f.model_dump(mode="json") for f in findings],
            key=lambda x: (x.get("severity", ""), x.get("code", ""), str(x.get("field_name"))),
        ),
        "summary": summary,
    }
    fingerprint = fingerprint_canonical(report_payload)

    return SchemaDriftReport(
        contract_fingerprint=contract_version.fingerprint,
        candidate_fingerprint=observation.fingerprint,
        contract_version=contract_version.version,
        source_id=contract_version.contract.source_id,
        overall_severity=overall,
        findings=sorted(findings, key=lambda x: (x.severity.value, x.code, str(x.field_name))),
        summary=summary,
        fingerprint=fingerprint,
    )


def _classify_type_drift(fc: FieldContract, obs: FieldObservation) -> SchemaDriftFinding | None:
    expected = fc.logical_type
    observed = obs.observed_logical_type
    if expected == observed:
        return SchemaDriftFinding(
            field_name=fc.field_name,
            severity=SchemaDriftSeverity.COMPATIBLE,
            code="TYPE_COMPATIBLE",
            message=f"field '{fc.field_name}' type compatible ({expected.value} == {observed.value})",  # noqa: E501
            details={"expected": expected.value, "observed": observed.value},
        )
    if _is_blocked_type_change(expected, observed):
        return SchemaDriftFinding(
            field_name=fc.field_name,
            severity=SchemaDriftSeverity.BLOCKED,
            code="INCOMPATIBLE_LOGICAL_TYPE",
            message=(
                f"field '{fc.field_name}' logical type changed incompatibly "
                f"from {expected.value} to {observed.value}"
            ),
            details={"expected": expected.value, "observed": observed.value},
        )
    if _is_widening(expected, observed):
        return SchemaDriftFinding(
            field_name=fc.field_name,
            severity=SchemaDriftSeverity.REVIEW_REQUIRED,
            code="TYPE_WIDENING",
            message=f"field '{fc.field_name}' type widens from {expected.value} to {observed.value}",  # noqa: E501
            details={"expected": expected.value, "observed": observed.value},
        )
    return SchemaDriftFinding(
        field_name=fc.field_name,
        severity=SchemaDriftSeverity.REVIEW_REQUIRED,
        code="TYPE_NARROWING",
        message=f"field '{fc.field_name}' type narrows or changes from {expected.value} to {observed.value}",  # noqa: E501
        details={"expected": expected.value, "observed": observed.value},
    )


def _classify_unit_drift(
    expected: FieldContract, observed: FieldContract | None, field_name: str
) -> SchemaDriftFinding | None:
    if observed is None:
        return None
    exp_u = expected.unit.canonical_key() if expected.unit else None
    obs_u = observed.unit.canonical_key() if observed.unit else None
    if exp_u == obs_u:
        return SchemaDriftFinding(
            field_name=field_name,
            severity=SchemaDriftSeverity.COMPATIBLE,
            code="UNIT_COMPATIBLE",
            message=f"field '{field_name}' unit compatible ({exp_u or 'none'})",
            details={"expected": exp_u or "none", "observed": obs_u or "none"},
        )
    if exp_u is not None and obs_u is not None and exp_u != obs_u:
        return SchemaDriftFinding(
            field_name=field_name,
            severity=SchemaDriftSeverity.BLOCKED,
            code="UNIT_CHANGED_INCOMPATIBLY",
            message=f"field '{field_name}' unit changed from '{exp_u}' to '{obs_u}'",
            details={"expected": exp_u, "observed": obs_u},
        )
    if (exp_u is None) != (obs_u is None):
        return SchemaDriftFinding(
            field_name=field_name,
            severity=SchemaDriftSeverity.REVIEW_REQUIRED,
            code="UNIT_PRESENCE_CHANGED",
            message=f"field '{field_name}' unit presence changed",
            details={"expected": exp_u or "none", "observed": obs_u or "none"},
        )
    return None


def _classify_timestamp_drift(
    expected: FieldContract, observed: FieldContract | None, field_name: str
) -> SchemaDriftFinding | None:
    if observed is None:
        return None
    exp_ts = expected.timestamp
    obs_ts = observed.timestamp
    if exp_ts is None and obs_ts is None:
        return SchemaDriftFinding(
            field_name=field_name,
            severity=SchemaDriftSeverity.COMPATIBLE,
            code="TIMESTAMP_SEMANTICS_COMPATIBLE",
            message=f"field '{field_name}' timestamp semantics compatible (none)",
            details={"expected": "none", "observed": "none"},
        )
    if exp_ts is None or obs_ts is None:
        # Canonicalise timestamp contracts to JSON strings for details (avoid dict in str-only)
        exp_json = json.dumps(exp_ts.model_dump(mode="json"), sort_keys=True) if exp_ts else "none"
        obs_json = json.dumps(obs_ts.model_dump(mode="json"), sort_keys=True) if obs_ts else "none"
        return SchemaDriftFinding(
            field_name=field_name,
            severity=SchemaDriftSeverity.REVIEW_REQUIRED,
            code="TIMESTAMP_SEMANTICS_CHANGED",
            message=f"field '{field_name}' timestamp semantics presence changed",
            details={"expected": exp_json, "observed": obs_json},
        )
    if exp_ts.time_basis != obs_ts.time_basis:
        return SchemaDriftFinding(
            field_name=field_name,
            severity=SchemaDriftSeverity.BLOCKED,
            code="TIME_BASIS_CHANGED",
            message=(
                f"field '{field_name}' time_basis changed from {exp_ts.time_basis.value} "
                f"to {obs_ts.time_basis.value}"
            ),
            details={"expected": exp_ts.time_basis.value, "observed": obs_ts.time_basis.value},
        )
    if exp_ts.timezone != obs_ts.timezone:
        return SchemaDriftFinding(
            field_name=field_name,
            severity=SchemaDriftSeverity.BLOCKED,
            code="TIMEZONE_SEMANTICS_CHANGED",
            message=(
                f"field '{field_name}' timezone semantics changed from {exp_ts.timezone.value} "
                f"to {obs_ts.timezone.value}"
            ),
            details={"expected": exp_ts.timezone.value, "observed": obs_ts.timezone.value},
        )
    if exp_ts.requires_timezone != obs_ts.requires_timezone:
        return SchemaDriftFinding(
            field_name=field_name,
            severity=SchemaDriftSeverity.BLOCKED,
            code="TIMESTAMP_TZ_REQUIREMENT_CHANGED",
            message=f"field '{field_name}' timestamp timezone requirement changed",
            details={
                "expected": str(exp_ts.requires_timezone),
                "observed": str(obs_ts.requires_timezone),
            },
        )
    if (exp_ts.format_hint or "") != (obs_ts.format_hint or ""):
        return SchemaDriftFinding(
            field_name=field_name,
            severity=SchemaDriftSeverity.REVIEW_REQUIRED,
            code="TIMESTAMP_FORMATTING_CHANGED",
            message=f"field '{field_name}' timestamp formatting changed while semantics preserved",
            details={
                "expected": exp_ts.format_hint or "none",
                "observed": obs_ts.format_hint or "none",
            },
        )
    return SchemaDriftFinding(
        field_name=field_name,
        severity=SchemaDriftSeverity.COMPATIBLE,
        code="TIMESTAMP_SEMANTICS_COMPATIBLE",
        message=f"field '{field_name}' timestamp semantics compatible",
        details={"expected": exp_ts.time_basis.value, "observed": obs_ts.time_basis.value},
    )


def _classify_timestamp_observation_drift(
    fc: FieldContract, obs: FieldObservation
) -> SchemaDriftFinding | None:
    ts = fc.timestamp
    if ts is None:
        return None
    parse_state = obs.timestamp_parse_state or "not_timestamp"
    if parse_state in {"parse_failed", "parse_ambiguous"}:
        return SchemaDriftFinding(
            field_name=fc.field_name,
            severity=SchemaDriftSeverity.BLOCKED,
            code="TIMESTAMP_PARSE_FAILED",
            message=f"field '{fc.field_name}' timestamp failed to parse in candidate",
            details={"expected": ts.time_basis.value, "observed": parse_state},
        )
    if ts.timezone is not None and ts.timezone.value == "UTC" and parse_state == "parsed_naive":
        return SchemaDriftFinding(
            field_name=fc.field_name,
            severity=SchemaDriftSeverity.BLOCKED,
            code="TIMEZONE_SEMANTICS_CHANGED",
            message=f"field '{fc.field_name}' timezone semantics changed (UTC expected, naive observed)",  # noqa: E501
            details={"expected": ts.timezone.value, "observed": parse_state},
        )
    if parse_state == "not_timestamp" and fc.logical_type.value == "timestamp":
        return SchemaDriftFinding(
            field_name=fc.field_name,
            severity=SchemaDriftSeverity.BLOCKED,
            code="INCOMPATIBLE_LOGICAL_TYPE",
            message=f"field '{fc.field_name}' expected timestamp but observation is not timestamp",
            details={"expected": "timestamp", "observed": parse_state},
        )
    if ts.format_hint and parse_state == "parsed_naive":
        return SchemaDriftFinding(
            field_name=fc.field_name,
            severity=SchemaDriftSeverity.REVIEW_REQUIRED,
            code="TIMESTAMP_FORMATTING_CHANGED",
            message=f"field '{fc.field_name}' timestamp formatting may differ while semantics preserved",  # noqa: E501
            details={"expected": ts.format_hint, "observed": parse_state},
        )
    return None


def _compare_rights(
    expected: RightsAndRetentionContract, observed: RightsAndRetentionContract
) -> list[SchemaDriftFinding]:
    findings: list[SchemaDriftFinding] = []
    # Publication class
    if expected.is_weakening(observed):
        findings.append(
            SchemaDriftFinding(
                field_name=None,
                severity=SchemaDriftSeverity.BLOCKED,
                code="PRIVACY_CLASSIFICATION_WEAKENED",
                message=(
                    f"publication class weakened from {expected.publication_class.value} "
                    f"to {observed.publication_class.value} without amendment"
                ),
                details={
                    "expected": expected.publication_class.value,
                    "observed": observed.publication_class.value,
                },
            )
        )
    elif expected.publication_class != observed.publication_class:
        findings.append(
            SchemaDriftFinding(
                field_name=None,
                severity=SchemaDriftSeverity.REVIEW_REQUIRED,
                code="PUBLICATION_CLASS_CHANGED",
                message=(
                    f"publication class changed from {expected.publication_class.value} "
                    f"to {observed.publication_class.value}"
                ),
                details={
                    "expected": expected.publication_class.value,
                    "observed": observed.publication_class.value,
                },
            )
        )
    else:
        findings.append(
            SchemaDriftFinding(
                field_name=None,
                severity=SchemaDriftSeverity.COMPATIBLE,
                code="PUBLICATION_CLASS_COMPATIBLE",
                message="publication class compatible",
                details={
                    "expected": expected.publication_class.value,
                    "observed": observed.publication_class.value,
                },
            )
        )

    # Personal data classification
    if expected.contains_personal_data != observed.contains_personal_data:
        findings.append(
            SchemaDriftFinding(
                field_name=None,
                severity=SchemaDriftSeverity.BLOCKED,
                code="PERSONAL_DATA_CLASSIFICATION_CHANGED",
                message=(
                    f"personal-data flag changed from {expected.contains_personal_data} "
                    f"to {observed.contains_personal_data}"
                ),
                details={
                    "expected": str(expected.contains_personal_data),
                    "observed": str(observed.contains_personal_data),
                },
            )
        )
    else:
        findings.append(
            SchemaDriftFinding(
                field_name=None,
                severity=SchemaDriftSeverity.COMPATIBLE,
                code="PERSONAL_DATA_CLASSIFICATION_COMPATIBLE",
                message="personal-data classification compatible",
                details={
                    "expected": str(expected.contains_personal_data),
                    "observed": str(observed.contains_personal_data),
                },
            )
        )

    # Retention
    if expected.retention_days is not None or observed.retention_days is not None:
        exp_ret = expected.retention_days
        obs_ret = observed.retention_days
        if exp_ret is not None and obs_ret is not None:
            if obs_ret > exp_ret:
                findings.append(
                    SchemaDriftFinding(
                        field_name=None,
                        severity=SchemaDriftSeverity.BLOCKED,
                        code="RETENTION_PERIOD_INCREASED",
                        message=f"retention increased from {exp_ret} to {obs_ret} days",
                        details={"expected": str(exp_ret), "observed": str(obs_ret)},
                    )
                )
            elif obs_ret < exp_ret:
                findings.append(
                    SchemaDriftFinding(
                        field_name=None,
                        severity=SchemaDriftSeverity.REVIEW_REQUIRED,
                        code="RETENTION_PERIOD_DECREASED",
                        message=f"retention decreased from {exp_ret} to {obs_ret} days",
                        details={"expected": str(exp_ret), "observed": str(obs_ret)},
                    )
                )
            else:
                findings.append(
                    SchemaDriftFinding(
                        field_name=None,
                        severity=SchemaDriftSeverity.COMPATIBLE,
                        code="RETENTION_PERIOD_COMPATIBLE",
                        message="retention period compatible",
                        details={"expected": str(exp_ret), "observed": str(obs_ret)},
                    )
                )
        elif exp_ret is None and obs_ret is not None:
            findings.append(
                SchemaDriftFinding(
                    field_name=None,
                    severity=SchemaDriftSeverity.REVIEW_REQUIRED,
                    code="RETENTION_PERIOD_ADDED",
                    message=f"retention {obs_ret} days added where none declared",
                    details={"expected": "none", "observed": str(obs_ret)},
                )
            )
        elif exp_ret is not None and obs_ret is None:
            findings.append(
                SchemaDriftFinding(
                    field_name=None,
                    severity=SchemaDriftSeverity.REVIEW_REQUIRED,
                    code="RETENTION_PERIOD_REMOVED",
                    message="retention removed",
                    details={"expected": str(exp_ret), "observed": "none"},
                )
            )

    return findings


def compare_contracts(
    frozen_version: SourceContractVersion,
    candidate_contract: SourceDataContract,
    candidate_observation: SchemaObservation | None = None,
) -> SchemaDriftReport:
    """Compare a candidate authored contract to a frozen contract.

    Field-set comparison is driven by union of frozen and candidate field names,
    not solely by observation, so removal of a required field is not hidden
    by an observed column.
    """
    if not frozen_version.is_frozen:
        raise ValueError("comparison requires frozen contract")
    contract = frozen_version.contract
    findings: list[SchemaDriftFinding] = []

    # Source identity + rights (always, even when observation present)
    if candidate_contract.source_id != contract.source_id:
        findings.append(
            SchemaDriftFinding(
                field_name=None,
                severity=SchemaDriftSeverity.BLOCKED,
                code="SOURCE_IDENTITY_CHANGED",
                message=(
                    f"source_id changed from '{contract.source_id}' to "
                    f"'{candidate_contract.source_id}' without amendment"
                ),
                details={"expected": contract.source_id, "observed": candidate_contract.source_id},
            )
        )
    findings.extend(_compare_rights(contract.rights, candidate_contract.rights))

    # Field-set union driven comparison
    frozen_map = contract.field_map()
    candidate_map = candidate_contract.field_map()
    frozen_names = set(frozen_map.keys())
    candidate_names = set(candidate_map.keys())

    for name in sorted(frozen_names - candidate_names):
        fc = frozen_map[name]
        if fc.required:
            findings.append(
                SchemaDriftFinding(
                    field_name=name,
                    severity=SchemaDriftSeverity.BLOCKED,
                    code="REQUIRED_FIELD_REMOVED",
                    message=f"required field '{name}' removed in candidate contract",
                    details={"expected": "required", "observed": "absent"},
                )
            )
        else:
            findings.append(
                SchemaDriftFinding(
                    field_name=name,
                    severity=SchemaDriftSeverity.REVIEW_REQUIRED,
                    code="OPTIONAL_FIELD_REMOVED",
                    message=f"optional field '{name}' removed in candidate contract",
                    details={"expected": "optional", "observed": "absent"},
                )
            )

    for name in sorted(candidate_names - frozen_names):
        findings.append(
            SchemaDriftFinding(
                field_name=name,
                severity=SchemaDriftSeverity.REVIEW_REQUIRED,
                code="OPTIONAL_FIELD_ADDED",
                message=f"field '{name}' present in candidate but not in frozen contract",
                details={"expected": "absent", "observed": candidate_map[name].logical_type.value},
            )
        )

    for name in sorted(frozen_names & candidate_names):
        fc = frozen_map[name]
        cc = candidate_map[name]
        # Type drift via observation-like classification but using contract types directly
        if fc.logical_type != cc.logical_type:
            if _is_blocked_type_change(fc.logical_type, cc.logical_type):
                findings.append(
                    SchemaDriftFinding(
                        field_name=name,
                        severity=SchemaDriftSeverity.BLOCKED,
                        code="INCOMPATIBLE_LOGICAL_TYPE",
                        message=(
                            f"field '{name}' logical type changed incompatibly "
                            f"from {fc.logical_type.value} to {cc.logical_type.value}"
                        ),
                        details={
                            "expected": fc.logical_type.value,
                            "observed": cc.logical_type.value,
                        },
                    )
                )
            elif _is_widening(fc.logical_type, cc.logical_type):
                findings.append(
                    SchemaDriftFinding(
                        field_name=name,
                        severity=SchemaDriftSeverity.REVIEW_REQUIRED,
                        code="TYPE_WIDENING",
                        message=f"field '{name}' type widens from {fc.logical_type.value} to {cc.logical_type.value}",  # noqa: E501
                        details={
                            "expected": fc.logical_type.value,
                            "observed": cc.logical_type.value,
                        },
                    )
                )
            else:
                findings.append(
                    SchemaDriftFinding(
                        field_name=name,
                        severity=SchemaDriftSeverity.REVIEW_REQUIRED,
                        code="TYPE_NARROWING",
                        message=f"field '{name}' type narrows from {fc.logical_type.value} to {cc.logical_type.value}",  # noqa: E501
                        details={
                            "expected": fc.logical_type.value,
                            "observed": cc.logical_type.value,
                        },
                    )
                )
        else:
            findings.append(
                SchemaDriftFinding(
                    field_name=name,
                    severity=SchemaDriftSeverity.COMPATIBLE,
                    code="TYPE_COMPATIBLE",
                    message=f"field '{name}' type compatible ({fc.logical_type.value})",
                    details={"expected": fc.logical_type.value, "observed": cc.logical_type.value},
                )
            )
        # Nullability (required flag) change
        if fc.required and not cc.required:
            findings.append(
                SchemaDriftFinding(
                    field_name=name,
                    severity=SchemaDriftSeverity.REVIEW_REQUIRED,
                    code="REQUIRED_FIELD_BECOMES_OPTIONAL",
                    message=f"field '{name}' changed from required to optional",
                    details={"expected": "required", "observed": "optional"},
                )
            )
        # Unit
        if (fc.unit is not None or cc.unit is not None) and fc.unit != cc.unit:
            exp_u = fc.unit.canonical_key() if fc.unit else None
            obs_u = cc.unit.canonical_key() if cc.unit else None
            if exp_u == obs_u:
                findings.append(
                    SchemaDriftFinding(
                        field_name=name,
                        severity=SchemaDriftSeverity.COMPATIBLE,
                        code="UNIT_COMPATIBLE",
                        message=f"field '{name}' unit compatible",
                        details={"expected": exp_u or "none", "observed": obs_u or "none"},
                    )
                )
            elif exp_u is not None and obs_u is not None and exp_u != obs_u:
                findings.append(
                    SchemaDriftFinding(
                        field_name=name,
                        severity=SchemaDriftSeverity.BLOCKED,
                        code="UNIT_CHANGED_INCOMPATIBLY",
                        message=f"field '{name}' unit changed from '{exp_u}' to '{obs_u}'",
                        details={"expected": exp_u, "observed": obs_u},
                    )
                )
            else:
                findings.append(
                    SchemaDriftFinding(
                        field_name=name,
                        severity=SchemaDriftSeverity.REVIEW_REQUIRED,
                        code="UNIT_PRESENCE_CHANGED",
                        message=f"field '{name}' unit presence changed",
                        details={"expected": exp_u or "none", "observed": obs_u or "none"},
                    )
                )
        # Timestamp
        if fc.timestamp is not None or cc.timestamp is not None:
            ts_f = _classify_timestamp_drift(fc, cc, name)
            if ts_f:
                findings.append(ts_f)

    # Also synthesize an observation from candidate if none provided, for column-order etc.
    if candidate_observation is None:
        field_obs: list[FieldObservation] = []
        for fc in candidate_contract.fields:
            field_obs.append(
                FieldObservation(
                    field_name=fc.field_name,
                    observed_logical_type=fc.logical_type,
                    nullable=False,
                    observed_count=1,
                    null_count=0,
                    timestamp_parse_state="parsed_with_tz"
                    if fc.logical_type == LogicalType.TIMESTAMP
                    else "not_timestamp",
                    categorical_distinct_count=None,
                    categorical_aggregate_hash=None,
                    precision=None,
                    scale=None,
                )
            )

        payload = {
            "schema_version": "1.0",
            "source_label_redacted": "candidate_contract",
            "total_observed_rows": 0,
            "truncated": False,
            "field_observations": [fo.model_dump(mode="json") for fo in field_obs],
        }
        fp = fingerprint_canonical(payload)
        candidate_observation = SchemaObservation(
            observation_id="candidate_contract_obs",
            source_label_redacted="candidate_contract",
            total_observed_rows=0,
            field_observations=field_obs,
            truncated=False,
            fingerprint=fp,
        )

    # Add column-order finding based on observation vs contract order
    contract_order = [f.field_name for f in contract.fields]
    # For contract-vs-contract we compare candidate order vs frozen order
    cand_order = [f.field_name for f in candidate_contract.fields]
    if set(cand_order) == set(contract_order) and cand_order != contract_order:
        findings.append(
            SchemaDriftFinding(
                field_name=None,
                severity=SchemaDriftSeverity.COMPATIBLE,
                code="COLUMN_REORDERING",
                message="column order differs but field set matches contract",
                details={"expected": ",".join(contract_order), "observed": ",".join(cand_order)},
            )
        )
    elif set(cand_order) == set(contract_order):
        findings.append(
            SchemaDriftFinding(
                field_name=None,
                severity=SchemaDriftSeverity.COMPATIBLE,
                code="COLUMN_ORDER_COMPATIBLE",
                message="column order matches contract",
                details={"expected": ",".join(contract_order), "observed": ",".join(cand_order)},
            )
        )

    # Build report using candidate observation fingerprint for candidate_fingerprint
    # but findings already include contract-level checks
    # We reuse _build_report logic but with candidate_observation
    overall = SchemaDriftSeverity.COMPATIBLE
    for f in findings:
        if f.severity is SchemaDriftSeverity.BLOCKED:
            overall = SchemaDriftSeverity.BLOCKED
            break
        if f.severity is SchemaDriftSeverity.REVIEW_REQUIRED:
            overall = SchemaDriftSeverity.REVIEW_REQUIRED

    blocked = sum(1 for f in findings if f.severity is SchemaDriftSeverity.BLOCKED)
    review = sum(1 for f in findings if f.severity is SchemaDriftSeverity.REVIEW_REQUIRED)
    compatible = sum(1 for f in findings if f.severity is SchemaDriftSeverity.COMPATIBLE)
    summary = {
        "blocked": blocked,
        "review_required": review,
        "compatible": compatible,
        "total": len(findings),
    }

    report_payload = {
        "schema_version": "1.0",
        "contract_fingerprint": frozen_version.fingerprint,
        "candidate_fingerprint": candidate_observation.fingerprint,
        "contract_version": frozen_version.version,
        "source_id": contract.source_id,
        "overall_severity": overall.value,
        "findings": sorted(
            [f.model_dump(mode="json") for f in findings],
            key=lambda x: (x.get("severity", ""), x.get("code", ""), str(x.get("field_name"))),
        ),
        "summary": summary,
    }
    fingerprint = fingerprint_canonical(report_payload)

    return SchemaDriftReport(
        contract_fingerprint=frozen_version.fingerprint,
        candidate_fingerprint=candidate_observation.fingerprint,
        contract_version=frozen_version.version,
        source_id=contract.source_id,
        overall_severity=overall,
        findings=sorted(findings, key=lambda x: (x.severity.value, x.code, str(x.field_name))),
        summary=summary,
        fingerprint=fingerprint,
    )
