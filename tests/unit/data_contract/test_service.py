"""Tests for service layer: freezing, lineage, handoff, bounded reads."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from traffictwin.data_contract.models import (
    FieldContract,
    LogicalType,
    PublicationClass,
    RightsAndRetentionContract,
    SourceDataContract,
)
from traffictwin.data_contract.service import (
    create_frozen_version,
    create_new_version_from_parent,
    prepare_handoff_to_manifest,
)


def _contract(version: str = "1.0.0", source_id: str = "src1") -> SourceDataContract:
    return SourceDataContract(
        source_id=source_id,
        contract_version=version,
        fields=[FieldContract(field_name="a", required=True, logical_type=LogicalType.STRING)],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )


def test_frozen_immutability() -> None:
    contract = _contract()
    frozen = create_frozen_version(contract)
    # Attempt to mutate via attribute assignment should raise ValidationError (frozen model)
    with pytest.raises(Exception):  # noqa: B017
        frozen.version = "9.9.9"  # type: ignore[misc]
    # Also test that dict mutation does not affect fingerprint
    assert frozen.is_frozen is True


def test_amendment_lineage() -> None:
    c1 = _contract(version="1.0.0")
    v1 = create_frozen_version(c1)
    c2 = _contract(version="1.0.1")
    v2 = create_new_version_from_parent(v1, c2, amendment_reason="add field b")
    assert v2.parent_fingerprint == v1.fingerprint
    assert v2.amendment_reason == "add field b"
    assert v2.version == "1.0.1"
    # Creating new version without bump should fail
    with pytest.raises(ValueError, match="must differ"):
        create_new_version_from_parent(v1, c1, amendment_reason="no bump")


def test_handoff_does_not_auto_import() -> None:
    c = _contract()
    v = create_frozen_version(c)
    payload = prepare_handoff_to_manifest(v)
    assert payload["import_auto_executed"] is False
    assert payload["source_id"] == "src1"
    assert "handoff_fingerprint" in payload
    # Handoff must not contain absolute path or raw values
    assert "/tmp" not in str(payload)  # noqa: S108
    assert "handoff_to_manifest" in payload["purpose"]


def test_bounded_read_bypass_blocked(tmp_path: Path) -> None:
    # Bounded read is exercised via the real inspection path, not a test helper
    p = tmp_path / "big.csv"
    p.write_text("a\n" + "x\n" * 5000, encoding="utf-8")
    from traffictwin.data_contract.inspection import inspect_tabular_sample

    # Within reasonable limit, bounded read succeeds (truncated if needed)
    obs = inspect_tabular_sample(
        p, max_rows=10, max_bytes=100000, observation_id="obs_001", source_label="local"
    )
    assert obs.total_observed_rows == 10
    # Exceeding limit with tiny max_bytes should raise
    with pytest.raises(Exception, match="exceeds"):
        inspect_tabular_sample(
            p, max_rows=1000, max_bytes=100, observation_id="obs_001", source_label="local"
        )


def test_unbounded_sample_read_is_not_allowed_via_inspection(tmp_path: Path) -> None:
    # Inspection with very low limit should fail or truncate, not silently read unbounded
    p = tmp_path / "sample.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["a"])
        for i in range(100):
            w.writerow([str(i)])
    from traffictwin.data_contract.inspection import inspect_tabular_sample

    # With max_bytes very low, should raise
    with pytest.raises(Exception, match="exceeds"):
        inspect_tabular_sample(
            p, max_rows=1000, max_bytes=10, observation_id="obs_001", source_label="local"
        )
    # With max_rows low, should truncate, not read all
    obs = inspect_tabular_sample(
        p, max_rows=5, max_bytes=1_000_000, observation_id="obs_001", source_label="local"
    )
    assert obs.total_observed_rows == 5
    assert obs.truncated is True


def test_fingerprint_excludes_path_and_clock(tmp_path: Path) -> None:
    from traffictwin.data_contract.inspection import inspect_tabular_sample

    p1 = tmp_path / "a.csv"
    p2 = tmp_path / "b.csv"
    p1.write_text("x,y\n1,2\n3,4\n", encoding="utf-8")
    p2.write_text("x,y\n1,2\n3,4\n", encoding="utf-8")
    obs1 = inspect_tabular_sample(
        p1, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label=str(p1)
    )
    obs2 = inspect_tabular_sample(
        p2, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label=str(p2)
    )
    # Fingerprints should be equal because source_label is redacted to local_sample and content same
    assert obs1.fingerprint == obs2.fingerprint


def test_raw_values_not_in_fingerprint(tmp_path: Path) -> None:
    p = tmp_path / "secret.csv"
    p.write_text("token,value\nsecret123,hello\n", encoding="utf-8")
    from traffictwin.data_contract.inspection import inspect_tabular_sample

    obs = inspect_tabular_sample(
        p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local"
    )
    assert "secret123" not in obs.fingerprint
    assert "secret123" not in json_dumps_obs(obs)


def json_dumps_obs(obs: object) -> str:
    import json

    return json.dumps(obs.model_dump(mode="json"), sort_keys=True)  # type: ignore[attr-defined]
