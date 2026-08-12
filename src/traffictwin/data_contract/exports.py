"""Portable exports for contracts and drift reports.

- YAML/JSON exports exclude raw row values, paths, clocks, secrets.
- CSV exports apply spreadsheet formula-injection protection.
- Field names are schema identity: preserved verbatim on every surface, never
  collapsed to a shared placeholder. Secret-looking names are flagged in an
  explicit ``privacy_review`` column (``PRIVACY_REVIEW_REQUIRED``) so a human
  reviews them; raw values never enter portable exports at all.
- Deterministic canonical serialisation with sorted keys.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

import yaml

from traffictwin.data_contract.fingerprint import is_secret_field_name, sanitise_for_csv
from traffictwin.data_contract.models import (
    SchemaDriftReport,
    SchemaObservation,
    SourceContractVersion,
    SourceDataContract,
)


def contract_to_canonical_dict(contract: SourceDataContract) -> dict[str, Any]:
    """Return canonical dict for a contract (excludes runtime path/clock)."""
    data = contract.model_dump(mode="json")
    data["fields"] = sorted(data["fields"], key=lambda x: x["field_name"])
    return dict(sorted(data.items()))


def version_to_canonical_dict(version: SourceContractVersion) -> dict[str, Any]:
    """Return canonical dict for a version wrapper."""
    data = version.model_dump(mode="json")
    data["contract"]["fields"] = sorted(data["contract"]["fields"], key=lambda x: x["field_name"])
    return dict(sorted(data.items()))


def observation_to_canonical_dict(observation: SchemaObservation) -> dict[str, Any]:
    """Return canonical dict for an observation (already sorted)."""
    data = observation.model_dump(mode="json")
    data["field_observations"] = sorted(data["field_observations"], key=lambda x: x["field_name"])
    return dict(sorted(data.items()))


def drift_report_to_canonical_dict(report: SchemaDriftReport) -> dict[str, Any]:
    """Return canonical dict for a drift report."""
    data = report.model_dump(mode="json")
    data["findings"] = sorted(
        data["findings"],
        key=lambda x: (x["severity"], x["code"], str(x.get("field_name"))),
    )
    return dict(sorted(data.items()))


def export_contract_json(contract: SourceDataContract) -> str:
    """Export contract as deterministic JSON (no raw values, no paths)."""
    canonical = contract_to_canonical_dict(contract)
    return json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False, indent=2
    )


def export_contract_yaml(contract: SourceDataContract) -> str:
    """Export contract as deterministic YAML."""
    canonical = contract_to_canonical_dict(contract)
    return yaml.safe_dump(canonical, sort_keys=True, allow_unicode=True)


def export_version_json(version: SourceContractVersion) -> str:
    """Export version wrapper as deterministic JSON."""
    canonical = version_to_canonical_dict(version)
    return json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False, indent=2
    )


def export_version_yaml(version: SourceContractVersion) -> str:
    """Export version wrapper as deterministic YAML."""
    canonical = version_to_canonical_dict(version)
    return yaml.safe_dump(canonical, sort_keys=True, allow_unicode=True)


def export_observation_json(observation: SchemaObservation) -> str:
    """Export observation as deterministic JSON."""
    canonical = observation_to_canonical_dict(observation)
    return json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False, indent=2
    )


def export_drift_json(report: SchemaDriftReport) -> str:
    """Export drift report as deterministic JSON."""
    canonical = drift_report_to_canonical_dict(report)
    return json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False, indent=2
    )


def export_drift_yaml(report: SchemaDriftReport) -> str:
    """Export drift report as deterministic YAML."""
    canonical = drift_report_to_canonical_dict(report)
    return yaml.safe_dump(canonical, sort_keys=True, allow_unicode=True)


def export_drift_csv(report: SchemaDriftReport) -> str:
    """Export drift findings as CSV with formula-injection protection.

    Columns: field_name, severity, code, message, privacy_review
    Values that start with ``= + - @`` are prefixed with ``'``.

    Field names are schema identity and are preserved verbatim on every
    export surface: two distinct fields must never collapse to one
    identifier. Secret-looking field names are therefore flagged in the
    explicit ``privacy_review`` column (``PRIVACY_REVIEW_REQUIRED``)
    instead of being replaced by a shared redaction placeholder. Raw
    values remain excluded from portable exports entirely.
    """
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(["field_name", "severity", "code", "message", "privacy_review"])
    for finding in sorted(
        report.findings, key=lambda x: (x.severity.value, x.code, str(x.field_name))
    ):
        raw_name = finding.field_name or ""
        field_name = sanitise_for_csv(raw_name)
        severity = sanitise_for_csv(finding.severity.value)
        code = sanitise_for_csv(finding.code)
        message = sanitise_for_csv(finding.message)
        privacy = "PRIVACY_REVIEW_REQUIRED" if is_secret_field_name(raw_name) else ""
        writer.writerow([field_name, severity, code, message, privacy])
    return output.getvalue()


def export_observation_csv(observation: SchemaObservation) -> str:
    """Export observation field table as CSV with formula protection.

    Portable observation contains no raw row values – only structural counts and
    deterministic aggregate hashes for categorical domains.

    Field names are preserved verbatim (schema identity is never collapsed);
    secret-looking names are flagged in the explicit ``privacy_review`` column.
    """
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(
        [
            "field_name",
            "observed_logical_type",
            "nullable",
            "observed_count",
            "null_count",
            "timestamp_parse_state",
            "categorical_distinct_count",
            "categorical_aggregate_hash",
            "precision",
            "scale",
            "privacy_review",
        ]
    )
    for fo in sorted(observation.field_observations, key=lambda x: x.field_name):
        fname = sanitise_for_csv(fo.field_name)
        ltype = sanitise_for_csv(fo.observed_logical_type.value)
        nullable = str(fo.nullable)
        observed_count = str(fo.observed_count)
        null_count = str(fo.null_count)
        ts_state = sanitise_for_csv(fo.timestamp_parse_state or "")
        distinct_count = (
            str(fo.categorical_distinct_count) if fo.categorical_distinct_count is not None else ""
        )
        aggregate_hash = sanitise_for_csv(fo.categorical_aggregate_hash or "")
        precision = str(fo.precision) if fo.precision is not None else ""
        scale = str(fo.scale) if fo.scale is not None else ""
        privacy = "PRIVACY_REVIEW_REQUIRED" if is_secret_field_name(fo.field_name) else ""
        writer.writerow(
            [
                fname,
                ltype,
                nullable,
                observed_count,
                null_count,
                ts_state,
                distinct_count,
                aggregate_hash,
                precision,
                scale,
                privacy,
            ]
        )
    return output.getvalue()
