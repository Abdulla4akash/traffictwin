"""Deterministic schema-drift comparison against a frozen contract."""

from __future__ import annotations

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

# Widening within numeric family is review_required; string is not a numeric widening.
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
    # Any narrowing? We'll treat narrowing as review_required, not blocked,
    # unless it is explicitly blocked (e.g., timestamp -> string)
    # Widening is compatible/review? For this workbench we map widening to review_required
    # to ensure user confirms semantics.
    # Only blocked if from_type is timestamp and to_type is not timestamp
    if from_type is LogicalType.TIMESTAMP and to_type is not LogicalType.TIMESTAMP:
        return True
    return False


# ---------------------------------------------------------------------------
# Core comparison
# ---------------------------------------------------------------------------


def compare_observation_to_contract(
    contract_version: SourceContractVersion,
    observation: SchemaObservation,
    *,
    candidate_contract: SourceDataContract | None = None,
) -> SchemaDriftReport:
    """Compare *observation* (or *candidate_contract*) against a frozen contract.

    If *candidate_contract* is provided, source/time/unit/rights drift is
    evaluated against its declared values; otherwise only observed structural
    facts are used for the comparison (observation path).

    The caller must ensure *contract_version.is_frozen* is True; a ValueError
    is raised otherwise to enforce immutability.
    """
    if not contract_version.is_frozen:
        raise ValueError("drift comparison requires a frozen contract version")

    contract = contract_version.contract
    # Source identity check uses candidate contract when available; observation
    # path compares source_label_redacted? We only have redacted label, so
    # observation-path source drift is limited.
    findings: list[SchemaDriftFinding] = []

    # -------------------------------------------------------------------
    # Source identity drift
    # -------------------------------------------------------------------
    if candidate_contract is not None:
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
                    details={
                        "expected": contract.source_id,
                        "observed": candidate_contract.source_id,
                    },
                )
            )

    # -------------------------------------------------------------------
    # Rights / publication class drift (requires candidate contract)
    # -------------------------------------------------------------------
    if candidate_contract is not None:
        rights_f = _compare_rights(contract.rights, candidate_contract.rights)
        findings.extend(rights_f)

    # -------------------------------------------------------------------
    # Field-level drift
    # -------------------------------------------------------------------
    contract_fields = contract.field_map()
    observed_map = observation.field_map()

    # Check for required field removed (blocked)
    for field_name, fc in contract_fields.items():
        if fc.required and field_name not in observed_map:
            # If candidate contract also missing required field, that's blocked
            # Observation path: missing required field in sample is blocked
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
            # Optional field absent is compatible (consistent with contract)
            findings.append(
                SchemaDriftFinding(
                    field_name=field_name,
                    severity=SchemaDriftSeverity.COMPATIBLE,
                    code="OPTIONAL_FIELD_ABSENT",
                    message=f"optional field '{field_name}' absent – consistent with contract",
                    details={"expected": "optional", "observed": "absent"},
                )
            )

    # For fields present in observation, classify drift
    for field_name, obs in observed_map.items():
        fc = contract_fields.get(field_name)
        if fc is None:
            # Extra field not in contract
            # Optional field added is review_required (spec). We treat any extra field as review_required  # noqa: E501
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

        # Field exists in both – compare type, nullability, unit, timestamp, domain, precision

        # Type drift
        type_finding = _classify_type_drift(fc, obs)
        if type_finding is not None:
            findings.append(type_finding)

        # Nullable drift: required field becomes nullable -> review_required
        # observed nullable True while contract required True is blocked? Spec says
        # "required field becomes nullable" is review_required. We'll follow that.
        if obs.nullable and fc.required:
            # If the contract says required, but sample has nulls, that's evidence of nullable data
            # Could be BLOCKED if nulls observed for required field? Spec classifies as review-required.  # noqa: E501
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
        elif obs.nullable and not fc.required:
            # Optional field nullable is compatible? But if contract says not nullable and observed nullable,  # noqa: E501
            # that's review. For now treat as review_required if field contract were non-nullable optional.  # noqa: E501
            # Our FieldContract does not have explicit nullable flag; required implies non-nullable.
            # So we already covered required case; optional nullable is expected? Skip.
            pass
        else:
            # Not nullable – check if type change already flags nullable; otherwise compatible for nullability  # noqa: E501
            if not obs.nullable:
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

        # Unit drift (requires candidate contract with unit info; observation path cannot infer unit reliably)  # noqa: E501
        if candidate_contract is not None:
            cand_fc = candidate_contract.field_map().get(field_name)
            if cand_fc is not None and (fc.unit is not None or cand_fc.unit is not None):
                unit_finding = _classify_unit_drift(fc, cand_fc, field_name)
                if unit_finding is not None:
                    findings.append(unit_finding)
        else:
            # Observation path: if observation logical type suggests unit-like inference, skip
            pass

        # Timestamp semantics drift
        if candidate_contract is not None:
            cand_fc2 = candidate_contract.field_map().get(field_name)
            if cand_fc2 is not None and (
                fc.timestamp is not None or cand_fc2.timestamp is not None
            ):  # noqa: E501
                ts_finding = _classify_timestamp_drift(fc, cand_fc2, field_name)
                if ts_finding is not None:
                    findings.append(ts_finding)
        else:
            # Observation path timestamp parse state vs contract
            if fc.logical_type is LogicalType.TIMESTAMP:
                ts_obs_finding = _classify_timestamp_observation_drift(fc, obs)
                if ts_obs_finding is not None:
                    findings.append(ts_obs_finding)

        # Categorical domain changes
        if fc.logical_type in {LogicalType.CATEGORICAL, LogicalType.STRING}:
            # Observation provides digest; compare to contract's expected domain if available?
            # For now, if observation has digest and it's different from previous? We cannot compare
            # without stored domain. Treat domain presence change as review_required.
            # If observation shows distinct count > contract expectation, flag review.
            # Since contract does not store domain digest, we emit review_required when digest present and logical type is categorical?  # noqa: E501
            # Instead, emit a compatible finding for domain when no explicit contract domain is stored.  # noqa: E501
            pass

        # Precision narrowing
        if (
            fc.logical_type in {LogicalType.FLOAT, LogicalType.DECIMAL}
            and obs.precision is not None
        ):
            # If observed precision/scale narrower than contract would expect, that's review_required  # noqa: E501
            # Contract does not store precision; we approximate: if scale decreases, review.
            # We'll emit review_required when precision suggests narrowing? Without baseline, skip or emit compatible.  # noqa: E501
            # Emit a review_required for precision narrows example: if scale is small vs previous? Not applicable.  # noqa: E501
            pass

        # Column reordering is handled at report level (not per-field). We'll emit a single compatible finding.  # noqa: E501

    # Overall column reordering / equivalent representation: if all required fields present and types compatible,  # noqa: E501
    # reordering is compatible. We detect that field order in observation differs from contract field order  # noqa: E501
    # but that is not a schema difference – we emit a compatible finding.
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

    # Compute overall severity: BLOCKED > REVIEW_REQUIRED > COMPATIBLE
    overall = SchemaDriftSeverity.COMPATIBLE
    for f in findings:
        if f.severity is SchemaDriftSeverity.BLOCKED:
            overall = SchemaDriftSeverity.BLOCKED
            break
        if f.severity is SchemaDriftSeverity.REVIEW_REQUIRED:
            overall = SchemaDriftSeverity.REVIEW_REQUIRED

    # Summary counts
    blocked = sum(1 for f in findings if f.severity is SchemaDriftSeverity.BLOCKED)
    review = sum(1 for f in findings if f.severity is SchemaDriftSeverity.REVIEW_REQUIRED)
    compatible = sum(1 for f in findings if f.severity is SchemaDriftSeverity.COMPATIBLE)
    summary = {
        "blocked": blocked,
        "review_required": review,
        "compatible": compatible,
        "total": len(findings),
    }

    # Deterministic fingerprint for report (excludes volatile fields; includes sorted findings)
    report_payload = {
        "schema_version": "1.0",
        "contract_fingerprint": contract_version.fingerprint,
        "candidate_fingerprint": observation.fingerprint,
        "contract_version": contract_version.version,
        "source_id": contract.source_id,
        "overall_severity": overall.value,
        "findings": sorted(
            [f.model_dump(mode="json") for f in findings],
            key=lambda x: (x.get("severity", ""), x.get("code", ""), str(x.get("field_name"))),
        ),
        "summary": summary,
    }
    fingerprint = fingerprint_canonical(report_payload)

    report = SchemaDriftReport(
        contract_fingerprint=contract_version.fingerprint,
        candidate_fingerprint=observation.fingerprint,
        contract_version=contract_version.version,
        source_id=contract.source_id,
        overall_severity=overall,
        findings=sorted(findings, key=lambda x: (x.severity.value, x.code, str(x.field_name))),
        summary=summary,
        fingerprint=fingerprint,
    )
    return report


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
            message=(
                f"field '{fc.field_name}' type widens from {expected.value} to {observed.value}"
            ),
            details={"expected": expected.value, "observed": observed.value},
        )
    # Narrowing or other change -> review_required
    return SchemaDriftFinding(
        field_name=fc.field_name,
        severity=SchemaDriftSeverity.REVIEW_REQUIRED,
        code="TYPE_NARROWING",
        message=(
            f"field '{fc.field_name}' type narrows or changes from {expected.value} to {observed.value}"  # noqa: E501
        ),
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
    # Any unit change is blocked if dimension changes; review if same dimension different unit?
    # Spec says "unit changed incompatibly" is blocked. We'll treat any unit change as blocked
    # when both are present and differ, because silent unit change is dangerous.
    if exp_u is not None and obs_u is not None and exp_u != obs_u:
        return SchemaDriftFinding(
            field_name=field_name,
            severity=SchemaDriftSeverity.BLOCKED,
            code="UNIT_CHANGED_INCOMPATIBLY",
            message=f"field '{field_name}' unit changed from '{exp_u}' to '{obs_u}'",
            details={"expected": exp_u, "observed": obs_u},
        )
    # One has unit, other doesn't -> review_required (could be blocked if required unit missing)
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
        return SchemaDriftFinding(
            field_name=field_name,
            severity=SchemaDriftSeverity.REVIEW_REQUIRED,
            code="TIMESTAMP_SEMANTICS_CHANGED",
            message=f"field '{field_name}' timestamp semantics presence changed",
            details={
                "expected": exp_ts.model_dump(mode="json") if exp_ts else "none",
                "observed": obs_ts.model_dump(mode="json") if obs_ts else "none",
            },
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
    # Compare contract timestamp semantics to observed parse state
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
    # If contract expects UTC but observation is naive, that's blocked per spec (timezone semantics changed)  # noqa: E501
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
    # Formatting change while semantics preserved -> review_required
    if ts.format_hint and parse_state == "parsed_naive":
        # Could be formatting change; flag review
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
    # Publication class weakening silently is blocked
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
    # Retention changes? Not blocked unless weakening privacy
    return findings


def compare_contracts(
    frozen_version: SourceContractVersion,
    candidate_contract: SourceDataContract,
    candidate_observation: SchemaObservation | None = None,
) -> SchemaDriftReport:
    """Compare a candidate authored contract to a frozen contract.

    If *candidate_observation* is provided, it is used for structural findings;
    otherwise structural findings are derived from the candidate contract's field
    list (logical types etc.).
    """
    if not frozen_version.is_frozen:
        raise ValueError("comparison requires frozen contract")
    # Synthesize an observation from the candidate contract if no observation provided
    if candidate_observation is None:
        # Build minimal observation from candidate fields (no raw values, deterministic)
        field_obs: list[FieldObservation] = []
        for fc in candidate_contract.fields:
            field_obs.append(
                FieldObservation(
                    field_name=fc.field_name,
                    observed_logical_type=fc.logical_type,
                    nullable=False,
                    observed_count=1,
                    null_count=0,
                    timestamp_parse_state="parsed_utc"
                    if fc.logical_type.value == "timestamp"
                    else "not_timestamp",
                    categorical_digest=None,
                    precision=None,
                    scale=None,
                )
            )
        # Fingerprint candidate observation deterministically
        from traffictwin.data_contract.fingerprint import fingerprint_canonical

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
    return compare_observation_to_contract(
        frozen_version, candidate_observation, candidate_contract=candidate_contract
    )
