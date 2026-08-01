"""Contract and adversarial tests for the aggregate historical store."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from traffictwin.platform.historical_store import (
    AdmissionStatus,
    AuthoritativeSourceRecord,
    CatalogueNamespace,
    CatalogueQuery,
    CitationEntry,
    ContentScope,
    DatasetDigestBinding,
    DatasetRegistrationCandidate,
    DatasetSchemaContract,
    EvidenceRestriction,
    EvidenceRole,
    EvidenceStanding,
    FeatureDefinition,
    FeatureInputRequirement,
    FeatureMaterialisationRequest,
    FeatureReceipt,
    FeatureSnapshot,
    FeatureSnapshotCandidate,
    HistoricalDatasetRecord,
    InMemoryHistoricalStore,
    MigrationDryRunReport,
    PayloadClass,
    ProvenanceWalk,
    RefusalCode,
    SchemaLiteral,
    SourceBinding,
    SourceKind,
    StoreReceipt,
    StoreRefusal,
    SupportCount,
)

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
LICENCE = "synthetic-test-only"


def _payload_bytes(value: Mapping[str, object]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _activity_payload(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "record_type": "synthetic_activity_aggregate",
        "schema_version": 1,
        "session_date_local": "2026-07-28",
        "timezone": "Europe/London",
        "aggregates_only": True,
        "concurrency_median": 12.0,
        "support_dates": 5,
    }
    payload.update(updates)
    return payload


def _activity_schema(version: int = 1) -> DatasetSchemaContract:
    return DatasetSchemaContract(
        schema_name="synthetic.activity",
        schema_version=version,
        payload_class=PayloadClass.AGGREGATE_SESSION_MEASUREMENT,
        required_top_level_keys=(
            "record_type",
            "schema_version",
            "session_date_local",
            "timezone",
            "aggregates_only",
            "concurrency_median",
            "support_dates",
        ),
        allowed_top_level_keys=(
            "record_type",
            "schema_version",
            "session_date_local",
            "timezone",
            "aggregates_only",
            "concurrency_median",
            "support_dates",
        ),
        required_literals=(
            SchemaLiteral(field="record_type", value="synthetic_activity_aggregate"),
            SchemaLiteral(field="schema_version", value=version),
            SchemaLiteral(field="aggregates_only", value=True),
        ),
    )


def _admitted_standing() -> EvidenceStanding:
    return EvidenceStanding(
        evidence_role=EvidenceRole.PROTOCOL_CONFIRMED,
        admission_status=AdmissionStatus.ADMITTED,
        evidence=True,
    )


def _source(
    *,
    source_id: str = "source:synthetic-activity",
    standing: EvidenceStanding | None = None,
    sparse64: bool = False,
    metadata_only: bool = False,
) -> AuthoritativeSourceRecord:
    return AuthoritativeSourceRecord(
        source_record_id=source_id,
        record_digest="a" * 64,
        payload_digest="b" * 64,
        schema_name="synthetic.source",
        schema_version=1,
        payload_class=PayloadClass.SAFE_ANALYSIS_SUMMARY,
        standing=standing or _admitted_standing(),
        sparse64=sparse64,
        metadata_only=metadata_only,
    )


def _record(
    schema: DatasetSchemaContract,
    source: AuthoritativeSourceRecord,
    payload: bytes,
    *,
    dataset_id: str = "dataset:activity-20260728",
    schema_digest: str | None = None,
    declared_payload_digest: str | None = None,
    standing: EvidenceStanding | None = None,
    citation_value: str = "synthetic fixture",
    namespace: CatalogueNamespace = CatalogueNamespace.ADMITTED_VEC,
    sparse64: bool = False,
    content_scope: ContentScope = ContentScope.AGGREGATE_PAYLOAD,
) -> HistoricalDatasetRecord:
    payload_digest = declared_payload_digest or hashlib.sha256(payload).hexdigest()
    return HistoricalDatasetRecord(
        dataset_id=dataset_id,
        logical_source_id="logical:synthetic-activity",
        payload_class=schema.payload_class,
        schema_name=schema.schema_name,
        schema_version=schema.schema_version,
        schema_digest=schema_digest or schema.fingerprint(),
        payload_digest=payload_digest,
        payload_handle=f"sha256:{payload_digest}",
        source_bindings=(
            SourceBinding(
                source_kind=SourceKind.AUTHORITATIVE_RECORD,
                source_id=source.source_record_id,
                expected_record_digest=source.record_digest,
                expected_payload_digest=source.payload_digest,
            ),
        ),
        created_at_utc=NOW,
        local_service_dates=("2026-07-28",),
        timezone="Europe/London",
        support=(SupportCount(name="support_dates", value=5),),
        exclusions=("none",),
        standing=standing or _admitted_standing(),
        citation_bundle=(CitationEntry(key="source", value=citation_value),),
        licence_class=LICENCE,
        namespace=namespace,
        content_scope=content_scope,
        sparse64=sparse64,
    )


def _candidate(
    schema: DatasetSchemaContract,
    source: AuthoritativeSourceRecord,
    payload_value: Mapping[str, object] | None = None,
    *,
    dataset_id: str = "dataset:activity-20260728",
    schema_digest: str | None = None,
    declared_payload_digest: str | None = None,
    standing: EvidenceStanding | None = None,
    citation_value: str = "synthetic fixture",
    namespace: CatalogueNamespace = CatalogueNamespace.ADMITTED_VEC,
    sparse64: bool = False,
    content_scope: ContentScope = ContentScope.AGGREGATE_PAYLOAD,
) -> DatasetRegistrationCandidate:
    payload = _payload_bytes(payload_value or _activity_payload())
    return DatasetRegistrationCandidate(
        record=_record(
            schema,
            source,
            payload,
            dataset_id=dataset_id,
            schema_digest=schema_digest,
            declared_payload_digest=declared_payload_digest,
            standing=standing,
            citation_value=citation_value,
            namespace=namespace,
            sparse64=sparse64,
            content_scope=content_scope,
        ),
        payload=payload,
    )


def _store(
    *,
    schemas: tuple[DatasetSchemaContract, ...] | None = None,
    sources: tuple[AuthoritativeSourceRecord, ...] | None = None,
    before_commit: Callable[[str], None] | None = None,
) -> InMemoryHistoricalStore:
    return InMemoryHistoricalStore(
        schemas=schemas or (_activity_schema(),),
        authoritative_sources=sources or (_source(),),
        licence_allowlist=frozenset({LICENCE}),
        before_commit=before_commit,
    )


def _feature(
    schema: DatasetSchemaContract,
    *,
    version: int = 1,
    units: str = "vehicles",
    namespace: CatalogueNamespace = CatalogueNamespace.ADMITTED_VEC,
    restriction: EvidenceRestriction = EvidenceRestriction.ADMITTED_ONLY,
) -> FeatureDefinition:
    return FeatureDefinition(
        feature_name="bus.concurrency.median",
        definition_version=version,
        supersedes_version=None if version == 1 else version - 1,
        value_type="float",
        units=units,
        null_semantics="missing",
        aggregation_grain="local service date and local hour",
        transformation_id="synthetic:concurrency-median",
        implementation_digest="c" * 64,
        required_inputs=(
            FeatureInputRequirement(
                schema_name=schema.schema_name,
                minimum_schema_version=schema.schema_version,
                maximum_schema_version=schema.schema_version,
                minimum_support=(SupportCount(name="support_dates", value=2),),
            ),
        ),
        leakage_boundary="whole local service dates stay on one side of a split",
        evidence_restriction=restriction,
        namespace=namespace,
    )


def _snapshot_candidate(
    record: HistoricalDatasetRecord,
    definition: FeatureDefinition,
    *,
    snapshot_id: str = "snapshot:bus-concurrency-v1",
    values: Mapping[str, object] | None = None,
) -> FeatureSnapshotCandidate:
    payload = _payload_bytes(values or {"values": [12.0], "aggregates_only": True})
    request = FeatureMaterialisationRequest(
        snapshot_id=snapshot_id,
        feature_name=definition.feature_name,
        feature_version=definition.definition_version,
        definition_digest=definition.definition_digest,
        dataset_bindings=(
            DatasetDigestBinding(
                dataset_id=record.dataset_id,
                expected_record_digest=record.fingerprint(),
                expected_payload_digest=record.payload_digest,
            ),
        ),
        values_digest=hashlib.sha256(payload).hexdigest(),
        row_count=1,
        coverage=(SupportCount(name="support_dates", value=5),),
        exclusions=("none",),
        created_at_utc=NOW,
        namespace=definition.namespace,
    )
    return FeatureSnapshotCandidate(request=request, values_payload=payload)


def test_register_dataset_is_digest_pinned_idempotent_and_query_safe() -> None:
    schema = _activity_schema()
    source = _source()
    store = _store(schemas=(schema,), sources=(source,))
    candidate = _candidate(schema, source)

    first = store.register_dataset(candidate)
    assert isinstance(first, StoreReceipt)
    assert first.idempotent_retry is False
    state_after_first = store.state_digest()

    retry = store.register_dataset(candidate)
    assert isinstance(retry, StoreReceipt)
    assert retry.idempotent_retry is True
    assert retry.state_digest == state_after_first == store.state_digest()

    loaded = store.get_dataset(candidate.record.dataset_id, candidate.record.payload_digest)
    assert loaded == candidate.record
    assert loaded.canonical_json() == candidate.record.canonical_json()
    selection = store.query_catalogue(
        CatalogueQuery(
            schema_name=schema.schema_name,
            minimum_schema_version=1,
            maximum_schema_version=1,
            namespace=CatalogueNamespace.ADMITTED_VEC,
        )
    )
    assert selection == (candidate.record,)
    assert selection[0].payload_handle.startswith("sha256:")
    assert "/Users/" not in selection[0].model_dump_json()


def test_digest_schema_source_and_licence_refusals_are_atomic() -> None:
    schema = _activity_schema()
    source = _source()
    cases = (
        _candidate(schema, source, declared_payload_digest="f" * 64),
        _candidate(schema, source, schema_digest="e" * 64),
        _candidate(
            schema,
            source,
            payload_value=_activity_payload(unexpected="field"),
        ),
        DatasetRegistrationCandidate(
            record=_candidate(schema, source).record.model_copy(
                update={"licence_class": "unreviewed-licence"}
            ),
            payload=_candidate(schema, source).payload,
        ),
        DatasetRegistrationCandidate(
            record=_candidate(schema, source).record.model_copy(
                update={
                    "source_bindings": (
                        SourceBinding(
                            source_kind=SourceKind.AUTHORITATIVE_RECORD,
                            source_id=source.source_record_id,
                            expected_record_digest="d" * 64,
                            expected_payload_digest=source.payload_digest,
                        ),
                    )
                }
            ),
            payload=_candidate(schema, source).payload,
        ),
    )
    expected = (
        RefusalCode.DIGEST_MISMATCH,
        RefusalCode.SCHEMA_DIGEST_MISMATCH,
        RefusalCode.SCHEMA_UNSUPPORTED,
        RefusalCode.LICENCE_NOT_ALLOWLISTED,
        RefusalCode.DIGEST_MISMATCH,
    )
    for candidate, code in zip(cases, expected, strict=True):
        store = _store(schemas=(schema,), sources=(source,))
        before = store.state_digest()
        result = store.register_dataset(candidate)
        assert isinstance(result, StoreRefusal)
        assert result.code is code
        assert result.state_digest_before == result.state_digest_after == before
        assert store.state_digest() == before


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (
            _activity_payload(workspace="/Users/example/private/store"),
            RefusalCode.PRIVATE_PATH_DETECTED,
        ),
        (
            _activity_payload(workspace="/opt/aggregate-store"),
            RefusalCode.PRIVATE_PATH_DETECTED,
        ),
        (
            _activity_payload(note="stored at /opt/aggregate-store"),
            RefusalCode.PRIVATE_PATH_DETECTED,
        ),
        (_activity_payload(api_key="synthetic-secret-marker"), RefusalCode.SECRET_DETECTED),
        (
            _activity_payload(
                access_token="synthetic-secret-marker"  # noqa: S106 - adversarial fixture
            ),
            RefusalCode.SECRET_DETECTED,
        ),
        (
            _activity_payload(VehicleRef="synthetic-identifier"),
            RefusalCode.IDENTIFIER_FIELD_FORBIDDEN,
        ),
        (
            _activity_payload(participant_id="synthetic-person"),
            RefusalCode.PARTICIPANT_DATA_FORBIDDEN,
        ),
        (_activity_payload(raw_payload="synthetic-wire-marker"), RefusalCode.RAW_SOURCE_FORBIDDEN),
    ],
)
def test_private_secret_identifier_participant_and_raw_fields_refuse(
    payload: dict[str, object],
    code: RefusalCode,
) -> None:
    schema = _activity_schema()
    source = _source()
    store = _store(schemas=(schema,), sources=(source,))
    candidate = _candidate(schema, source, payload_value=payload)
    before = store.state_digest()

    result = store.register_dataset(candidate)

    assert isinstance(result, StoreRefusal)
    assert result.code is code
    assert store.state_digest() == before


def test_compressed_and_xml_source_bytes_are_never_ingested() -> None:
    schema = _activity_schema()
    source = _source()
    store = _store(schemas=(schema,), sources=(source,))
    for payload in (b"\x1f\x8bsynthetic", b"<synthetic-feed />"):
        digest = hashlib.sha256(payload).hexdigest()
        candidate = DatasetRegistrationCandidate(
            record=_record(schema, source, payload, declared_payload_digest=digest),
            payload=payload,
        )
        result = store.register_dataset(candidate)
        assert isinstance(result, StoreRefusal)
        assert result.code is RefusalCode.RAW_SOURCE_FORBIDDEN


def test_private_path_in_typed_metadata_refuses_without_echoing_it() -> None:
    schema = _activity_schema()
    source = _source()
    store = _store(schemas=(schema,), sources=(source,))
    candidate = _candidate(
        schema,
        source,
        citation_value="/Users/example/private/permission.txt",
    )

    result = store.register_dataset(candidate)

    assert isinstance(result, StoreRefusal)
    assert result.code is RefusalCode.PRIVATE_PATH_DETECTED
    assert "/Users/" not in result.model_dump_json()


def test_evidence_standing_never_strengthens_or_clears_deviation() -> None:
    schema = _activity_schema()
    weak = EvidenceStanding(
        evidence_role=EvidenceRole.EXECUTION_DEVIATED,
        admission_status=AdmissionStatus.NON_ADMITTED,
        evidence=False,
        execution_deviation=True,
    )
    source = _source(standing=weak)
    store = _store(schemas=(schema,), sources=(source,))
    candidate = _candidate(schema, source, standing=_admitted_standing())

    result = store.register_dataset(candidate)

    assert isinstance(result, StoreRefusal)
    assert result.code is RefusalCode.STANDING_ESCALATION
    assert (
        store.query_catalogue(
            CatalogueQuery(
                schema_name=schema.schema_name,
                minimum_schema_version=1,
                maximum_schema_version=1,
                namespace=CatalogueNamespace.ADMITTED_VEC,
            )
        )
        == ()
    )


def test_predictions_forecasts_and_non_admitted_models_are_type_level_false() -> None:
    for role in (
        EvidenceRole.PREDICTION,
        EvidenceRole.FORECAST,
        EvidenceRole.DRAFT,
        EvidenceRole.NON_ADMITTED_DIAGNOSTIC,
    ):
        with pytest.raises(ValidationError, match="evidence=false"):
            EvidenceStanding(
                evidence_role=role,
                admission_status=AdmissionStatus.NOT_APPLICABLE,
                evidence=True,
            )


def test_feature_definitions_are_monotonic_immutable_and_idempotent() -> None:
    schema = _activity_schema()
    store = _store(schemas=(schema,))
    version_1 = _feature(schema)

    first = store.register_feature(version_1)
    retry = store.register_feature(version_1)
    assert isinstance(first, FeatureReceipt)
    assert first.idempotent_retry is False
    assert isinstance(retry, FeatureReceipt)
    assert retry.idempotent_retry is True

    gap = store.register_feature(_feature(schema, version=3))
    assert isinstance(gap, StoreRefusal)
    assert gap.code is RefusalCode.FEATURE_VERSION_GAP

    version_2 = _feature(schema, version=2)
    assert isinstance(store.register_feature(version_2), FeatureReceipt)
    conflict = store.register_feature(_feature(schema, version=2, units="count"))
    assert isinstance(conflict, StoreRefusal)
    assert conflict.code is RefusalCode.LOGICAL_ID_CONFLICT


def test_snapshot_is_immutable_idempotent_and_has_complete_provenance() -> None:
    schema = _activity_schema()
    source = _source()
    store = _store(schemas=(schema,), sources=(source,))
    dataset = _candidate(schema, source)
    assert isinstance(store.register_dataset(dataset), StoreReceipt)
    definition = _feature(schema)
    assert isinstance(store.register_feature(definition), FeatureReceipt)
    candidate = _snapshot_candidate(dataset.record, definition)

    snapshot = store.materialise_snapshot(candidate)
    assert isinstance(snapshot, FeatureSnapshot)
    assert snapshot.standing == dataset.record.standing
    state_after_first = store.state_digest()
    retry = store.materialise_snapshot(candidate)
    assert retry == snapshot
    assert retry.canonical_json() == snapshot.canonical_json()
    assert store.state_digest() == state_after_first

    walk = store.provenance_walk(snapshot.snapshot_id)
    assert isinstance(walk, ProvenanceWalk)
    assert walk.complete is True
    assert walk.feature_definition == definition
    assert walk.datasets == (dataset.record,)
    assert walk.authoritative_sources == (source,)

    tampered = snapshot.model_dump()
    tampered["snapshot_digest"] = "f" * 64
    with pytest.raises(ValidationError, match="snapshot digest"):
        FeatureSnapshot.model_validate(tampered)

    before_conflict = store.state_digest()
    conflict = store.materialise_snapshot(
        _snapshot_candidate(
            dataset.record,
            definition,
            values={"values": [13.0], "aggregates_only": True},
        )
    )
    assert isinstance(conflict, StoreRefusal)
    assert conflict.code is RefusalCode.SNAPSHOT_CONFLICT
    assert store.state_digest() == before_conflict

    non_aggregate = store.materialise_snapshot(
        _snapshot_candidate(dataset.record, definition, values={"values": [12.0]})
    )
    assert isinstance(non_aggregate, StoreRefusal)
    assert non_aggregate.code is RefusalCode.SCHEMA_UNSUPPORTED
    assert store.state_digest() == before_conflict


def test_feature_refusal_for_missing_support_and_private_values_is_atomic() -> None:
    schema = _activity_schema()
    source = _source()
    store = _store(schemas=(schema,), sources=(source,))
    payload = _payload_bytes(_activity_payload())
    low_support = DatasetRegistrationCandidate(
        record=_record(schema, source, payload).model_copy(
            update={"support": (SupportCount(name="support_dates", value=1),)}
        ),
        payload=payload,
    )
    assert isinstance(store.register_dataset(low_support), StoreReceipt)
    definition = _feature(schema)
    assert isinstance(store.register_feature(definition), FeatureReceipt)
    before = store.state_digest()

    incompatible = store.materialise_snapshot(_snapshot_candidate(low_support.record, definition))
    assert isinstance(incompatible, StoreRefusal)
    assert incompatible.code is RefusalCode.FEATURE_INCOMPATIBLE
    assert store.state_digest() == before

    private_values = store.materialise_snapshot(
        _snapshot_candidate(
            low_support.record,
            definition,
            snapshot_id="snapshot:private-values",
            values={"workspace": "/Users/example/private"},
        )
    )
    assert isinstance(private_values, StoreRefusal)
    assert private_values.code is RefusalCode.PRIVATE_PATH_DETECTED
    assert store.state_digest() == before

    private_metadata_request = _snapshot_candidate(
        low_support.record,
        definition,
        snapshot_id="snapshot:private-metadata",
    ).request.model_copy(update={"exclusions": ("/opt/private-exclusion",)})
    private_metadata = store.materialise_snapshot(
        FeatureSnapshotCandidate(
            request=private_metadata_request,
            values_payload=_payload_bytes({"values": [12.0], "aggregates_only": True}),
        )
    )
    assert isinstance(private_metadata, StoreRefusal)
    assert private_metadata.code is RefusalCode.PRIVATE_PATH_DETECTED
    assert store.state_digest() == before


def test_copy_on_write_commit_recovers_after_injected_crash() -> None:
    calls = 0

    def fail_once(operation: str) -> None:
        nonlocal calls
        assert operation == "register_dataset"
        calls += 1
        if calls == 1:
            raise RuntimeError("synthetic crash before commit")

    schema = _activity_schema()
    source = _source()
    store = _store(schemas=(schema,), sources=(source,), before_commit=fail_once)
    candidate = _candidate(schema, source)
    before = store.state_digest()

    failed = store.register_dataset(candidate)
    assert isinstance(failed, StoreRefusal)
    assert failed.code is RefusalCode.PARTIAL_COMMIT
    assert store.state_digest() == before

    recovered = store.register_dataset(candidate)
    assert isinstance(recovered, StoreReceipt)
    assert recovered.idempotent_retry is False
    assert store.get_dataset(candidate.record.dataset_id, candidate.record.payload_digest) == (
        candidate.record
    )


def test_feature_and_snapshot_commits_recover_after_injected_crashes() -> None:
    fail_once = {"register_feature", "materialise_snapshot"}

    def inject(operation: str) -> None:
        if operation in fail_once:
            fail_once.remove(operation)
            raise RuntimeError("synthetic crash before commit")

    schema = _activity_schema()
    source = _source()
    store = _store(schemas=(schema,), sources=(source,), before_commit=inject)
    dataset = _candidate(schema, source)
    assert isinstance(store.register_dataset(dataset), StoreReceipt)
    definition = _feature(schema)

    before_feature = store.state_digest()
    failed_feature = store.register_feature(definition)
    assert isinstance(failed_feature, StoreRefusal)
    assert failed_feature.code is RefusalCode.PARTIAL_COMMIT
    assert store.state_digest() == before_feature
    assert isinstance(store.register_feature(definition), FeatureReceipt)

    snapshot_candidate = _snapshot_candidate(dataset.record, definition)
    before_snapshot = store.state_digest()
    failed_snapshot = store.materialise_snapshot(snapshot_candidate)
    assert isinstance(failed_snapshot, StoreRefusal)
    assert failed_snapshot.code is RefusalCode.PARTIAL_COMMIT
    assert store.state_digest() == before_snapshot
    recovered_snapshot = store.materialise_snapshot(snapshot_candidate)
    assert isinstance(recovered_snapshot, FeatureSnapshot)
    assert recovered_snapshot.snapshot_id == snapshot_candidate.request.snapshot_id


def _sparse_schema() -> DatasetSchemaContract:
    return DatasetSchemaContract(
        schema_name="sparse64.metadata",
        schema_version=1,
        payload_class=PayloadClass.SAFE_ANALYSIS_SUMMARY,
        required_top_level_keys=(
            "record_type",
            "status",
            "execution_deviation",
            "results_included",
        ),
        allowed_top_level_keys=(
            "record_type",
            "status",
            "execution_deviation",
            "results_included",
        ),
        required_literals=(
            SchemaLiteral(field="record_type", value="sparse64_safe_metadata"),
            SchemaLiteral(field="status", value="NON_ADMITTED"),
            SchemaLiteral(field="execution_deviation", value=True),
            SchemaLiteral(field="results_included", value=False),
        ),
        sparse64_metadata_compatible=True,
    )


def test_sparse64_is_metadata_only_non_admitted_and_namespace_segregated() -> None:
    schema = _sparse_schema()
    standing = EvidenceStanding(
        evidence_role=EvidenceRole.EXECUTION_DEVIATED,
        admission_status=AdmissionStatus.NON_ADMITTED,
        evidence=False,
        execution_deviation=True,
    )
    source = _source(
        source_id="source:sparse64-homecoming",
        standing=standing,
        sparse64=True,
        metadata_only=True,
    )
    store = _store(schemas=(schema,), sources=(source,))
    payload = _payload_bytes(
        {
            "record_type": "sparse64_safe_metadata",
            "status": "NON_ADMITTED",
            "execution_deviation": True,
            "results_included": False,
        }
    )

    promoted = DatasetRegistrationCandidate(
        record=_record(
            schema,
            source,
            payload,
            dataset_id="dataset:sparse64-promoted",
            standing=_admitted_standing(),
            namespace=CatalogueNamespace.ADMITTED_VEC,
        ),
        payload=payload,
    )
    refused = store.register_dataset(promoted)
    assert isinstance(refused, StoreRefusal)
    assert refused.code in {
        RefusalCode.NON_ADMITTED_PROMOTION,
        RefusalCode.STANDING_ESCALATION,
    }

    segregated = DatasetRegistrationCandidate(
        record=_record(
            schema,
            source,
            payload,
            dataset_id="dataset:sparse64-metadata",
            standing=standing,
            namespace=CatalogueNamespace.NON_ADMITTED_SPARSE64,
            sparse64=True,
            content_scope=ContentScope.METADATA_ONLY,
        ),
        payload=payload,
    )
    assert isinstance(store.register_dataset(segregated), StoreReceipt)
    admitted_view = store.query_catalogue(
        CatalogueQuery(
            schema_name=schema.schema_name,
            minimum_schema_version=1,
            maximum_schema_version=1,
            namespace=CatalogueNamespace.ADMITTED_VEC,
        )
    )
    non_admitted_view = store.query_catalogue(
        CatalogueQuery(
            schema_name=schema.schema_name,
            minimum_schema_version=1,
            maximum_schema_version=1,
            namespace=CatalogueNamespace.NON_ADMITTED_SPARSE64,
        )
    )
    assert admitted_view == ()
    assert non_admitted_view == (segregated.record,)


def test_migration_dry_run_changes_neither_sources_store_nor_payload_bytes() -> None:
    schema = _activity_schema()
    source = _source()
    store = _store(schemas=(schema,), sources=(source,))
    good = _candidate(schema, source)
    bad = _candidate(
        schema,
        source,
        dataset_id="dataset:bad-digest",
        declared_payload_digest="f" * 64,
    )
    good_before = bytes(good.payload)
    bad_before = bytes(bad.payload)
    store_before = store.state_digest()

    report = store.dry_run_migration((good, bad))

    assert isinstance(report, MigrationDryRunReport)
    assert (report.would_register, report.would_reuse, report.would_refuse) == (1, 0, 1)
    assert report.findings[1].refusal_code is RefusalCode.DIGEST_MISMATCH
    assert good.payload == good_before
    assert bad.payload == bad_before
    assert store.state_digest() == store_before
    assert (
        store.query_catalogue(
            CatalogueQuery(
                schema_name=schema.schema_name,
                minimum_schema_version=1,
                maximum_schema_version=1,
                namespace=CatalogueNamespace.ADMITTED_VEC,
            )
        )
        == ()
    )

    assert isinstance(store.register_dataset(good), StoreReceipt)
    reuse_report = store.dry_run_migration((good,))
    assert reuse_report.would_reuse == 1
    assert reuse_report.store_unchanged is True


def test_schema_evolution_requires_explicit_query_range_and_keeps_missing_support() -> None:
    schema_v1 = _activity_schema(1)
    schema_v2 = _activity_schema(2)
    source = _source()
    store = _store(schemas=(schema_v1, schema_v2), sources=(source,))
    first = _candidate(schema_v1, source, dataset_id="dataset:activity-v1")
    second = _candidate(
        schema_v2,
        source,
        payload_value=_activity_payload(schema_version=2),
        dataset_id="dataset:activity-v2",
    )
    assert isinstance(store.register_dataset(first), StoreReceipt)
    assert isinstance(store.register_dataset(second), StoreReceipt)

    v1_only = store.query_catalogue(
        CatalogueQuery(
            schema_name=schema_v1.schema_name,
            minimum_schema_version=1,
            maximum_schema_version=1,
            namespace=CatalogueNamespace.ADMITTED_VEC,
        )
    )
    both = store.query_catalogue(
        CatalogueQuery(
            schema_name=schema_v1.schema_name,
            minimum_schema_version=1,
            maximum_schema_version=2,
            namespace=CatalogueNamespace.ADMITTED_VEC,
        )
    )
    assert v1_only == (first.record,)
    assert both == (first.record, second.record)
    assert first.record.support_value("unobserved_support") is None

    with pytest.raises(ValidationError, match="precedes"):
        CatalogueQuery(
            schema_name=schema_v1.schema_name,
            minimum_schema_version=2,
            maximum_schema_version=1,
            namespace=CatalogueNamespace.ADMITTED_VEC,
        )


def test_local_service_dates_require_timezone_and_producer_citations_are_complete() -> None:
    schema = _activity_schema()
    source = _source()
    candidate = _candidate(schema, source)
    dumped = candidate.record.model_dump()
    dumped["timezone"] = None
    with pytest.raises(ValidationError, match="timezone"):
        HistoricalDatasetRecord.model_validate(dumped)

    producer_dump = candidate.record.model_dump()
    producer_dump["producer_derived"] = True
    with pytest.raises(ValidationError, match="citation"):
        HistoricalDatasetRecord.model_validate(producer_dump)


def test_store_requires_explicit_nonempty_licence_allowlist() -> None:
    with pytest.raises(ValueError, match="allowlist"):
        InMemoryHistoricalStore(
            schemas=(_activity_schema(),),
            authoritative_sources=(_source(),),
            licence_allowlist=frozenset(),
        )


def test_blank_licence_metadata_has_a_typed_atomic_refusal() -> None:
    schema = _activity_schema()
    source = _source()
    store = _store(schemas=(schema,), sources=(source,))
    candidate = _candidate(schema, source)
    blank_record = candidate.record.model_copy(update={"licence_class": " "})
    before = store.state_digest()

    result = store.register_dataset(
        DatasetRegistrationCandidate(record=blank_record, payload=candidate.payload)
    )

    assert isinstance(result, StoreRefusal)
    assert result.code is RefusalCode.LICENCE_METADATA_MISSING
    assert result.state_digest_before == result.state_digest_after == before
    assert store.state_digest() == before
