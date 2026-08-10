"""Tests for strict contract models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from traffictwin.data_contract.models import (
    FieldContract,
    LogicalType,
    PublicationClass,
    RightsAndRetentionContract,
    SourceContractVersion,
    SourceDataContract,
    TimeBasis,
    TimestampContract,
    TimezoneSemantics,
    UnitContract,
)


def _minimal_contract() -> SourceDataContract:
    return SourceDataContract(
        source_id="test_source",
        contract_version="1.0.0",
        fields=[
            FieldContract(
                field_name="timestamp",
                required=True,
                logical_type=LogicalType.TIMESTAMP,
                timestamp=TimestampContract(
                    time_basis=TimeBasis.ISO8601, timezone=TimezoneSemantics.UTC
                ),
            ),
            FieldContract(field_name="vehicle_id", required=True, logical_type=LogicalType.STRING),
            FieldContract(
                field_name="speed",
                required=False,
                logical_type=LogicalType.FLOAT,
                unit=UnitContract(unit="mps", dimension="speed"),
            ),
        ],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )


def test_field_contract_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        FieldContract.model_validate(
            {"field_name": "x", "required": True, "logical_type": "string", "unknown": "bad"}
        )


def test_timestamp_required_for_timestamp_type() -> None:
    with pytest.raises(ValidationError, match="timestamp contract required"):
        FieldContract(field_name="ts", required=True, logical_type=LogicalType.TIMESTAMP)


def test_timestamp_forbidden_for_non_timestamp() -> None:
    with pytest.raises(ValidationError, match="only allowed for timestamp"):
        FieldContract(
            field_name="x",
            required=True,
            logical_type=LogicalType.STRING,
            timestamp=TimestampContract(
                time_basis=TimeBasis.ISO8601, timezone=TimezoneSemantics.UTC
            ),
        )


def test_contract_version_must_be_semver() -> None:
    with pytest.raises(ValidationError, match="semantic version"):
        SourceDataContract(
            source_id="src",
            contract_version="v1",
            fields=[FieldContract(field_name="a", required=True, logical_type=LogicalType.STRING)],
        )


def test_contract_duplicate_fields_forbidden() -> None:
    with pytest.raises(ValidationError, match="unique field_name"):
        SourceDataContract(
            source_id="src",
            contract_version="1.0.0",
            fields=[
                FieldContract(field_name="a", required=True, logical_type=LogicalType.STRING),
                FieldContract(field_name="a", required=True, logical_type=LogicalType.STRING),
            ],
        )


def test_source_contract_version_frozen_immutability() -> None:
    contract = _minimal_contract()
    from traffictwin.data_contract.service import create_frozen_version

    version = create_frozen_version(contract)
    assert version.is_frozen is True
    with pytest.raises(ValidationError):
        version.version = "9.9.9"  # type: ignore[misc]


def test_amendment_requires_parent() -> None:
    contract = _minimal_contract()
    with pytest.raises(ValidationError, match="requires parent_fingerprint"):
        SourceContractVersion(
            version="1.0.0",
            contract=contract,
            parent_fingerprint=None,
            amendment_reason="reason",
            fingerprint="a" * 64,
            is_frozen=True,
        )


def test_rights_weakening_detection() -> None:
    private = RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE)
    open_pub = RightsAndRetentionContract(publication_class=PublicationClass.OPEN)
    assert private.is_weakening(open_pub) is True
    assert open_pub.is_weakening(private) is False
    assert private.is_weakening(private) is False
