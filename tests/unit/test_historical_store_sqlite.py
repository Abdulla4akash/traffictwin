"""Synthetic persistence tests for the aggregate historical store."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.platform.historical_store import (
    AdmissionStatus,
    AuthoritativeSourceRecord,
    CatalogueNamespace,
    CatalogueQuery,
    CitationEntry,
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
from traffictwin.platform.historical_store_sqlite import (
    BackupReceipt,
    LicenceAllowlistPolicy,
    PersistentRefusalCode,
    PersistentStoreRefusal,
    SQLiteHistoricalStore,
    SQLiteStoreConfig,
)

NOW = datetime(2026, 8, 1, 20, 30, tzinfo=UTC)
LICENCE = "synthetic-test-only"


def _json_bytes(value: Mapping[str, object]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _schema() -> DatasetSchemaContract:
    return DatasetSchemaContract(
        schema_name="synthetic.activity",
        schema_version=1,
        payload_class=PayloadClass.AGGREGATE_SESSION_MEASUREMENT,
        required_top_level_keys=(
            "record_type",
            "schema_version",
            "aggregates_only",
            "support_dates",
            "concurrency_median",
        ),
        allowed_top_level_keys=(
            "record_type",
            "schema_version",
            "aggregates_only",
            "support_dates",
            "concurrency_median",
        ),
        required_literals=(
            SchemaLiteral(field="record_type", value="synthetic_activity_aggregate"),
            SchemaLiteral(field="schema_version", value=1),
            SchemaLiteral(field="aggregates_only", value=True),
        ),
    )


def _standing() -> EvidenceStanding:
    return EvidenceStanding(
        evidence_role=EvidenceRole.PROTOCOL_CONFIRMED,
        admission_status=AdmissionStatus.ADMITTED,
        evidence=True,
    )


def _source() -> AuthoritativeSourceRecord:
    return AuthoritativeSourceRecord(
        source_record_id="source:synthetic",
        record_digest="a" * 64,
        payload_digest="b" * 64,
        schema_name="synthetic.source",
        schema_version=1,
        payload_class=PayloadClass.SAFE_ANALYSIS_SUMMARY,
        standing=_standing(),
    )


def _candidate(*, licence: str = LICENCE) -> DatasetRegistrationCandidate:
    schema = _schema()
    source = _source()
    payload = _json_bytes(
        {
            "record_type": "synthetic_activity_aggregate",
            "schema_version": 1,
            "aggregates_only": True,
            "support_dates": 5,
            "concurrency_median": 12.0,
        }
    )
    digest = hashlib.sha256(payload).hexdigest()
    record = HistoricalDatasetRecord(
        dataset_id="dataset:synthetic-activity",
        logical_source_id="logical:synthetic-activity",
        payload_class=schema.payload_class,
        schema_name=schema.schema_name,
        schema_version=schema.schema_version,
        schema_digest=schema.fingerprint(),
        payload_digest=digest,
        payload_handle=f"sha256:{digest}",
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
        standing=_standing(),
        citation_bundle=(CitationEntry(key="source", value="synthetic fixture"),),
        licence_class=licence,
        namespace=CatalogueNamespace.ADMITTED_VEC,
    )
    return DatasetRegistrationCandidate(record=record, payload=payload)


def _feature() -> FeatureDefinition:
    return FeatureDefinition(
        feature_name="bus.concurrency.median",
        definition_version=1,
        value_type="float",
        units="vehicles",
        null_semantics="missing",
        aggregation_grain="local service date",
        transformation_id="synthetic:median",
        implementation_digest="c" * 64,
        required_inputs=(
            FeatureInputRequirement(
                schema_name=_schema().schema_name,
                minimum_schema_version=1,
                maximum_schema_version=1,
                minimum_support=(SupportCount(name="support_dates", value=2),),
            ),
        ),
        leakage_boundary="whole local service dates stay on one side of a split",
        evidence_restriction=EvidenceRestriction.ADMITTED_ONLY,
        namespace=CatalogueNamespace.ADMITTED_VEC,
    )


def _snapshot_candidate(
    dataset: HistoricalDatasetRecord,
    feature: FeatureDefinition,
) -> FeatureSnapshotCandidate:
    payload = _json_bytes({"aggregates_only": True, "values": [12.0]})
    request = FeatureMaterialisationRequest(
        snapshot_id="snapshot:synthetic-concurrency",
        feature_name=feature.feature_name,
        feature_version=feature.definition_version,
        definition_digest=feature.definition_digest,
        dataset_bindings=(
            DatasetDigestBinding(
                dataset_id=dataset.dataset_id,
                expected_record_digest=dataset.fingerprint(),
                expected_payload_digest=dataset.payload_digest,
            ),
        ),
        values_digest=hashlib.sha256(payload).hexdigest(),
        row_count=1,
        coverage=(SupportCount(name="support_dates", value=5),),
        exclusions=("none",),
        created_at_utc=NOW,
        namespace=CatalogueNamespace.ADMITTED_VEC,
    )
    return FeatureSnapshotCandidate(request=request, values_payload=payload)


def _config(tmp_path: Path, *, inside_repository: bool = False) -> SQLiteStoreConfig:
    repository = tmp_path / "repository"
    repository.mkdir(parents=True, exist_ok=True)
    workspace = repository / "runtime" if inside_repository else tmp_path / "owner-workspace"
    return SQLiteStoreConfig(owner_workspace=workspace, repository_root=repository)


def _licence_policy(
    *, version: str = "synthetic-v1", allowed: tuple[str, ...] = (LICENCE,)
) -> LicenceAllowlistPolicy:
    return LicenceAllowlistPolicy(policy_version=version, allowed_classes=allowed)


def _open(
    config: SQLiteStoreConfig,
    *,
    licence_policy: LicenceAllowlistPolicy | None = None,
    schemas: tuple[DatasetSchemaContract, ...] | None = None,
    sources: tuple[AuthoritativeSourceRecord, ...] | None = None,
    fault_hook: Callable[[str, str], None] | None = None,
) -> SQLiteHistoricalStore:
    result = SQLiteHistoricalStore.open(
        config=config,
        schemas=schemas or (_schema(),),
        authoritative_sources=sources or (_source(),),
        licence_policy=licence_policy or _licence_policy(),
        fault_hook=fault_hook,
    )
    assert isinstance(result, SQLiteHistoricalStore)
    return result


def _query() -> CatalogueQuery:
    return CatalogueQuery(
        schema_name=_schema().schema_name,
        minimum_schema_version=1,
        maximum_schema_version=1,
        namespace=CatalogueNamespace.ADMITTED_VEC,
    )


def test_defaults_create_only_the_external_local_workspace(tmp_path: Path) -> None:
    config = _config(tmp_path)
    store = _open(config)
    root = config.owner_workspace / "historical-store"

    assert store.policy.catalogue_engine == "sqlite"
    assert store.policy.retention == "owner_confirmed_digest_only"
    assert store.policy.automatic_deletion is False
    assert store.policy.runtime_catalogue_committed is False
    assert store.policy.network_service is False
    assert (root / "catalogue.sqlite").is_file()
    assert (root / "payloads" / "sha256").is_dir()
    assert (root / "staging").is_dir()
    assert (root / "backups").is_dir()
    assert str(config.owner_workspace) not in repr(config)
    assert store.recovery_report().safe_to_open is True
    store.close()

    refused = SQLiteHistoricalStore.open(
        config=_config(tmp_path / "inside", inside_repository=True),
        schemas=(_schema(),),
        authoritative_sources=(_source(),),
        licence_policy=_licence_policy(),
    )
    assert isinstance(refused, PersistentStoreRefusal)
    assert refused.code is PersistentRefusalCode.WORKSPACE_INSIDE_REPOSITORY
    assert str(tmp_path) not in refused.model_dump_json()


def test_records_snapshots_and_provenance_replay_exactly_after_restart(tmp_path: Path) -> None:
    config = _config(tmp_path)
    candidate = _candidate()
    feature = _feature()
    snapshot_candidate = _snapshot_candidate(candidate.record, feature)
    store = _open(config)

    dataset_receipt = store.register_dataset(candidate)
    feature_receipt = store.register_feature(feature)
    snapshot = store.materialise_snapshot(snapshot_candidate)
    assert isinstance(dataset_receipt, StoreReceipt)
    assert isinstance(feature_receipt, FeatureReceipt)
    assert isinstance(snapshot, FeatureSnapshot)
    assert store.query_catalogue(_query()) == (candidate.record,)
    store.close()

    reopened = _open(config)
    loaded = reopened.get_dataset(candidate.record.dataset_id, candidate.record.payload_digest)
    assert loaded == candidate.record
    assert loaded.canonical_json() == candidate.record.canonical_json()
    assert reopened.query_catalogue(_query()) == (candidate.record,)
    walk = reopened.provenance_walk(snapshot.snapshot_id)
    assert isinstance(walk, ProvenanceWalk)
    assert walk.snapshot == snapshot
    assert walk.feature_definition == feature
    assert walk.datasets == (candidate.record,)
    assert walk.authoritative_sources == (_source(),)

    dataset_retry = reopened.register_dataset(candidate)
    feature_retry = reopened.register_feature(feature)
    snapshot_retry = reopened.materialise_snapshot(snapshot_candidate)
    assert isinstance(dataset_retry, StoreReceipt) and dataset_retry.idempotent_retry is True
    assert isinstance(feature_retry, FeatureReceipt) and feature_retry.idempotent_retry is True
    assert snapshot_retry == snapshot
    assert str(config.owner_workspace) not in dataset_retry.model_dump_json()
    reopened.close()


def test_all_write_operations_roll_back_and_retry_after_injected_failure(tmp_path: Path) -> None:
    failures = {"register_dataset", "register_feature", "materialise_snapshot"}

    def fail_once(stage: str, operation: str) -> None:
        assert stage == "before_catalogue_commit"
        if operation in failures:
            failures.remove(operation)
            raise RuntimeError("synthetic failure before commit")

    config = _config(tmp_path)
    candidate = _candidate()
    feature = _feature()
    snapshot_candidate = _snapshot_candidate(candidate.record, feature)
    store = _open(config, fault_hook=fail_once)

    failed_dataset = store.register_dataset(candidate)
    assert isinstance(failed_dataset, PersistentStoreRefusal)
    assert store.query_catalogue(_query()) == ()
    assert (
        tuple((config.owner_workspace / "historical-store/payloads/sha256").glob("*/*.json")) == ()
    )
    assert isinstance(store.register_dataset(candidate), StoreReceipt)

    failed_feature = store.register_feature(feature)
    assert isinstance(failed_feature, PersistentStoreRefusal)
    assert isinstance(store.register_feature(feature), FeatureReceipt)

    payload_count = len(
        tuple((config.owner_workspace / "historical-store/payloads/sha256").glob("*/*.json"))
    )
    failed_snapshot = store.materialise_snapshot(snapshot_candidate)
    assert isinstance(failed_snapshot, PersistentStoreRefusal)
    assert (
        len(tuple((config.owner_workspace / "historical-store/payloads/sha256").glob("*/*.json")))
        == payload_count
    )
    assert isinstance(store.materialise_snapshot(snapshot_candidate), FeatureSnapshot)
    assert failures == set()
    store.close()

    reopened = _open(config)
    assert reopened.query_catalogue(_query()) == (candidate.record,)
    assert isinstance(
        reopened.provenance_walk(snapshot_candidate.request.snapshot_id), ProvenanceWalk
    )
    reopened.close()


def test_bound_contract_and_fail_closed_licence_policy_refuse_mismatch(tmp_path: Path) -> None:
    config = _config(tmp_path)
    store = _open(config)
    not_allowlisted = store.register_dataset(_candidate(licence="unreviewed"))
    assert isinstance(not_allowlisted, StoreRefusal)
    assert not_allowlisted.code is RefusalCode.LICENCE_NOT_ALLOWLISTED
    store.close()

    policy_mismatch = SQLiteHistoricalStore.open(
        config=config,
        schemas=(_schema(),),
        authoritative_sources=(_source(),),
        licence_policy=_licence_policy(version="synthetic-v2"),
    )
    assert isinstance(policy_mismatch, PersistentStoreRefusal)
    assert policy_mismatch.code is PersistentRefusalCode.POLICY_MISMATCH

    changed_schema = _schema().model_copy(update={"schema_version": 2})
    contract_mismatch = SQLiteHistoricalStore.open(
        config=config,
        schemas=(changed_schema,),
        authoritative_sources=(_source(),),
        licence_policy=_licence_policy(),
    )
    assert isinstance(contract_mismatch, PersistentStoreRefusal)
    assert contract_mismatch.code is PersistentRefusalCode.CONTRACT_MISMATCH


def test_recovery_reports_orphans_without_deleting_them(tmp_path: Path) -> None:
    config = _config(tmp_path)
    store = _open(config)
    candidate = _candidate()
    assert isinstance(store.register_dataset(candidate), StoreReceipt)
    store.close()

    orphan_payload = _json_bytes({"aggregates_only": True, "orphan": "synthetic"})
    orphan_digest = hashlib.sha256(orphan_payload).hexdigest()
    orphan_path = (
        config.owner_workspace
        / "historical-store"
        / "payloads"
        / "sha256"
        / orphan_digest[:2]
        / f"{orphan_digest}.json"
    )
    orphan_path.parent.mkdir(parents=True)
    orphan_path.write_bytes(orphan_payload)

    reopened = _open(config)
    report = reopened.recovery_report()
    assert report.orphan_payload_digests == (orphan_digest,)
    assert report.automatic_deletion_performed is False
    assert orphan_path.exists()
    reopened.close()


def test_missing_and_corrupt_registered_payloads_refuse_open_safely(tmp_path: Path) -> None:
    config = _config(tmp_path)
    candidate = _candidate()
    store = _open(config)
    assert isinstance(store.register_dataset(candidate), StoreReceipt)
    store.close()
    payload_path = (
        config.owner_workspace
        / "historical-store"
        / "payloads"
        / "sha256"
        / candidate.record.payload_digest[:2]
        / f"{candidate.record.payload_digest}.json"
    )
    original = payload_path.read_bytes()
    payload_path.unlink()

    missing = SQLiteHistoricalStore.open(
        config=config,
        schemas=(_schema(),),
        authoritative_sources=(_source(),),
        licence_policy=_licence_policy(),
    )
    assert isinstance(missing, PersistentStoreRefusal)
    assert missing.code is PersistentRefusalCode.PAYLOAD_MISSING
    assert str(config.owner_workspace) not in missing.model_dump_json()

    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_bytes(b"synthetic-corruption")
    corrupt = SQLiteHistoricalStore.open(
        config=config,
        schemas=(_schema(),),
        authoritative_sources=(_source(),),
        licence_policy=_licence_policy(),
    )
    assert isinstance(corrupt, PersistentStoreRefusal)
    assert corrupt.code is PersistentRefusalCode.PAYLOAD_CORRUPT
    payload_path.write_bytes(original)


def test_verified_backups_are_explicit_safe_and_never_pruned(tmp_path: Path) -> None:
    config = _config(tmp_path)
    store = _open(config)
    assert isinstance(store.register_dataset(_candidate()), StoreReceipt)

    invalid = store.create_verified_backup("Not Safe")
    assert isinstance(invalid, PersistentStoreRefusal)
    assert invalid.code is PersistentRefusalCode.BACKUP_LABEL_INVALID

    receipt = store.create_verified_backup("pre-migration")
    assert isinstance(receipt, BackupReceipt)
    assert receipt.catalogue_integrity_verified is True
    assert receipt.manifest_verified is True
    assert receipt.payload_count == 1
    assert receipt.automatic_deletion is False
    backup_path = config.owner_workspace / "historical-store" / receipt.backup_handle
    assert backup_path.is_dir()
    manifest_bytes = (backup_path / "manifest.json").read_bytes()
    assert hashlib.sha256(manifest_bytes).hexdigest() == receipt.backup_digest
    manifest = json.loads(manifest_bytes)
    assert manifest["catalogue_digest"] == receipt.catalogue_digest
    backup_catalogue = backup_path / "catalogue.sqlite"
    assert hashlib.sha256(backup_catalogue.read_bytes()).hexdigest() == receipt.catalogue_digest
    candidate = _candidate()
    backup_payload = (
        backup_path
        / "payloads"
        / "sha256"
        / candidate.record.payload_digest[:2]
        / f"{candidate.record.payload_digest}.json"
    )
    assert backup_payload.read_bytes() == candidate.payload
    backup_connection = sqlite3.connect(backup_catalogue)
    try:
        assert backup_connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        backup_connection.close()

    retry = store.create_verified_backup("pre-migration")
    assert isinstance(retry, BackupReceipt)
    assert retry.idempotent_retry is True
    assert backup_path.exists()
    store.close()


def test_future_sqlite_schema_version_is_never_rewritten(tmp_path: Path) -> None:
    config = _config(tmp_path)
    store = _open(config)
    store.close()
    catalogue = config.owner_workspace / "historical-store" / "catalogue.sqlite"
    connection = sqlite3.connect(catalogue)
    try:
        connection.execute("PRAGMA user_version = 99")
    finally:
        connection.close()

    refused = SQLiteHistoricalStore.open(
        config=config,
        schemas=(_schema(),),
        authoritative_sources=(_source(),),
        licence_policy=_licence_policy(),
    )

    assert isinstance(refused, PersistentStoreRefusal)
    assert refused.code is PersistentRefusalCode.CONTRACT_MISMATCH
    verification = sqlite3.connect(catalogue)
    try:
        assert verification.execute("PRAGMA user_version").fetchone()[0] == 99
    finally:
        verification.close()


def test_two_local_instances_refresh_before_reads_and_writes(tmp_path: Path) -> None:
    config = _config(tmp_path)
    first = _open(config)
    second = _open(config)
    candidate = _candidate()
    feature = _feature()

    assert isinstance(first.register_dataset(candidate), StoreReceipt)
    assert second.query_catalogue(_query()) == (candidate.record,)
    assert isinstance(second.register_feature(feature), FeatureReceipt)
    snapshot = first.materialise_snapshot(_snapshot_candidate(candidate.record, feature))
    assert isinstance(snapshot, FeatureSnapshot)
    first.close()
    second.close()


def test_migration_dry_run_does_not_persist_payload_or_catalogue_rows(tmp_path: Path) -> None:
    config = _config(tmp_path)
    store = _open(config)
    root = config.owner_workspace / "historical-store"

    report = store.dry_run_migration((_candidate(),))

    assert report.would_register == 1
    assert report.store_unchanged is True
    assert store.query_catalogue(_query()) == ()
    assert tuple((root / "payloads" / "sha256").glob("*/*.json")) == ()
    connection = sqlite3.connect(root / "catalogue.sqlite")
    try:
        assert connection.execute("SELECT COUNT(*) FROM datasets").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 0
    finally:
        connection.close()
    store.close()
