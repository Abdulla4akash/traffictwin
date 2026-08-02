"""Synthetic tests for preview-first aggregate-store activation."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

from traffictwin.platform.historical_store import (
    AdmissionStatus,
    AuthoritativeSourceRecord,
    CatalogueNamespace,
    CatalogueQuery,
    EvidenceRole,
    EvidenceStanding,
    PayloadClass,
)
from traffictwin.platform.historical_store_activation import (
    ActivationConfig,
    ActivationPreview,
    ActivationReceipt,
    ActivationRefusal,
    ActivationRefusalCode,
    AggregateImportKind,
    activate_store,
    catalogue_report,
    integrity_report,
    preview_activation,
)
from traffictwin.platform.historical_store_sqlite import LicenceAllowlistPolicy

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 2, 9, 30, tzinfo=UTC)
LICENCE = "synthetic-aggregate-test-v1"


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_private(path: Path, value: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    path.write_bytes(value)
    path.chmod(0o600)


def _activity_payload(*, timezone_note: str = "Europe/London synthetic fixture") -> bytes:
    return _json_bytes(
        {
            "record_type": "bods_session_activity_aggregate",
            "schema_version": "1.0",
            "design_reference": "docs/platform/bus_prediction_design.md",
            "session_kind": "scheduled",
            "label": "am_peak",
            "session_date_local": "2026-07-28",
            "utc_offset_seconds_applied": 3600,
            "timezone_note": timezone_note,
            "schedule_digest": "a" * 64,
            "snapshot_count": 2,
            "concurrency_source": "parser_live_vehicle",
            "per_snapshot_live_vehicle": [
                {
                    "snapshot_id": "snapshot-20260728t070000z",
                    "hour_utc": 7,
                    "hour_local": 8,
                    "live_vehicle": 12,
                },
                {
                    "snapshot_id": "snapshot-20260728t070105z",
                    "hour_utc": 7,
                    "hour_local": 8,
                    "live_vehicle": 13,
                },
            ],
            "progression_available": True,
            "progression_unavailable_reason": None,
            "hourly_progression": [
                {
                    "hour_utc": 7,
                    "hour_local": 8,
                    "segment_count": 4,
                    "speed_mps_median": 5.2,
                    "speed_mps_p90": 7.1,
                    "vehicles_contributing": 2,
                }
            ],
            "aggregates_only": True,
            "raw_identifiers_published": False,
            "bus_progression_only": True,
            "road_traffic_speed_available": False,
            "session_salt_discarded": True,
        }
    )


def _forecast_payload() -> bytes:
    return _json_bytes(
        {
            "schema_version": "1.0",
            "method_version": "bods-bus-forecast-1.0",
            "design_reference": "docs/platform/bus_prediction_design.md",
            "research_status": "owner_approved_candidate",
            "evidence": False,
            "generated_at_utc": "2026-08-02T09:00:00+00:00",
            "rules": {
                "min_snapshots_per_session": 10,
                "min_interval_support_dates": 5,
            },
            "targets": ["concurrency_median"],
            "sources": [],
            "fit_dates": [],
            "cells": [],
            "alpha_by_target": {"concurrency_median": None},
            "alpha_pair_counts": {"concurrency_median": 0},
        }
    )


def _standing(kind: AggregateImportKind) -> EvidenceStanding:
    if kind is AggregateImportKind.BUS_FORECAST_FIT:
        return EvidenceStanding(
            evidence_role=EvidenceRole.FORECAST,
            admission_status=AdmissionStatus.NOT_APPLICABLE,
            evidence=False,
        )
    return EvidenceStanding(
        evidence_role=EvidenceRole.DESCRIPTIVE,
        admission_status=AdmissionStatus.NOT_APPLICABLE,
        evidence=True,
    )


def _schema_contract(
    kind: AggregateImportKind,
) -> tuple[str, PayloadClass]:
    if kind is AggregateImportKind.BUS_FORECAST_FIT:
        return "bods.bus.forecast.fit", PayloadClass.MODEL_ARTIFACT
    return (
        "bods.session.activity.aggregate",
        PayloadClass.AGGREGATE_SESSION_MEASUREMENT,
    )


def _write_bundle(
    import_root: Path,
    *,
    name: str,
    kind: AggregateImportKind,
    payload: bytes | None = None,
    licence: str = LICENCE,
    source_standing: EvidenceStanding | None = None,
    expected_payload_digest: str | None = None,
    manifest_changes: dict[str, object] | None = None,
) -> tuple[Path, Path, Path]:
    actual_payload = payload or (
        _forecast_payload() if kind is AggregateImportKind.BUS_FORECAST_FIT else _activity_payload()
    )
    artifact = import_root / f"{name}.json"
    source_path = import_root / f"{name}.source.json"
    manifest_path = import_root / f"{name}.safe-aggregate-import.json"
    _write_private(artifact, actual_payload)
    schema_name, payload_class = _schema_contract(kind)
    payload_digest = _digest(actual_payload)
    source = AuthoritativeSourceRecord(
        source_record_id=f"source:{name}",
        record_digest=hashlib.sha256(f"authority:{name}".encode()).hexdigest(),
        payload_digest=payload_digest,
        schema_name=schema_name,
        schema_version=1,
        payload_class=payload_class,
        standing=source_standing or _standing(kind),
    )
    source_bytes = (source.canonical_json() + "\n").encode("utf-8")
    _write_private(source_path, source_bytes)
    manifest: dict[str, object] = {
        "record_type": "aggregate_store_import",
        "schema_version": "1.0",
        "import_kind": kind.value,
        "artifact_handle": artifact.name,
        "source_record_handle": source_path.name,
        "expected_artifact_digest": expected_payload_digest or payload_digest,
        "expected_source_file_digest": _digest(source_bytes),
        "dataset_id": f"dataset:{name}",
        "logical_source_id": f"logical:{name}",
        "created_at_utc": NOW.isoformat(),
        "licence_class": licence,
        "citations": [{"key": "source", "value": "synthetic aggregate authority"}],
        "exclusions": [],
        "refusal_count": 0,
        "aggregates_only": True,
        "contains_private_paths": False,
        "contains_credentials": False,
    }
    if manifest_changes:
        manifest.update(manifest_changes)
    _write_private(manifest_path, _json_bytes(manifest))
    return manifest_path, artifact, source_path


@pytest.fixture
def activation_workspace(tmp_path: Path) -> tuple[ActivationConfig, Path, Path]:
    owner = tmp_path / "owner-workspace"
    imports = owner / "safe-imports"
    owner.mkdir(mode=0o700)
    imports.mkdir(mode=0o700)
    owner.chmod(0o700)
    imports.chmod(0o700)
    config = ActivationConfig(
        workspace_id="synthetic-store",
        owner_workspace=owner,
        repository_root=REPOSITORY_ROOT,
        import_roots=(imports,),
        licence_policy=LicenceAllowlistPolicy(
            policy_version="synthetic-v1",
            allowed_classes=(LICENCE,),
        ),
    )
    return config, owner, imports


def _preview(config: ActivationConfig) -> ActivationPreview:
    result = preview_activation(config)
    assert isinstance(result, ActivationPreview), result
    return result


def _activate(config: ActivationConfig, preview: ActivationPreview) -> ActivationReceipt:
    result = activate_store(
        config,
        expected_preview_digest=preview.preview_digest,
        clock=lambda: NOW,
    )
    assert isinstance(result, ActivationReceipt), result
    return result


def test_preview_is_mutation_free_and_accepts_both_closed_adapters(
    activation_workspace: tuple[ActivationConfig, Path, Path],
) -> None:
    config, owner, imports = activation_workspace
    activity_paths = _write_bundle(
        imports,
        name="activity",
        kind=AggregateImportKind.BODS_SESSION_ACTIVITY_AGGREGATE,
    )
    forecast_paths = _write_bundle(
        imports,
        name="forecast",
        kind=AggregateImportKind.BUS_FORECAST_FIT,
    )
    before = {path: path.read_bytes() for path in (*activity_paths, *forecast_paths)}

    preview = _preview(config)

    assert preview.activatable is True
    assert preview.target_status == "absent"
    assert preview.manifests_discovered == 2
    assert preview.would_register == 2
    assert preview.would_refuse == 0
    assert preview.source_bytes_unchanged is True
    assert not (owner / "historical-store").exists()
    assert not tuple(owner.glob(".historical-store-activation-*"))
    assert {path: path.read_bytes() for path in before} == before
    assert str(owner) not in preview.model_dump_json()


def test_empty_import_set_is_a_typed_mutation_free_refusal(
    activation_workspace: tuple[ActivationConfig, Path, Path],
) -> None:
    config, owner, _ = activation_workspace

    preview = _preview(config)

    assert preview.activatable is False
    assert preview.manifests_discovered == 0
    assert preview.findings[0].refusal_code == ActivationRefusalCode.EMPTY_IMPORT_SET.value
    assert not (owner / "historical-store").exists()


def test_malformed_and_oversized_manifests_are_bounded_refusals(
    activation_workspace: tuple[ActivationConfig, Path, Path],
) -> None:
    config, _, imports = activation_workspace
    manifest = imports / "bad.safe-aggregate-import.json"
    _write_private(manifest, b"{")
    malformed = _preview(config)
    assert malformed.findings[0].refusal_code == ActivationRefusalCode.MANIFEST_INVALID.value

    _write_private(manifest, b"{" + b" " * 100)
    oversized = _preview(replace(config, max_manifest_bytes=32))
    assert oversized.findings[0].refusal_code == ActivationRefusalCode.INPUT_TOO_LARGE.value


def test_activation_is_atomic_backed_up_restored_queryable_and_idempotent(
    activation_workspace: tuple[ActivationConfig, Path, Path],
) -> None:
    config, owner, imports = activation_workspace
    source_paths = (
        *_write_bundle(
            imports,
            name="activity",
            kind=AggregateImportKind.BODS_SESSION_ACTIVITY_AGGREGATE,
        ),
        *_write_bundle(
            imports,
            name="forecast",
            kind=AggregateImportKind.BUS_FORECAST_FIT,
        ),
    )
    source_before = {path: path.read_bytes() for path in source_paths}
    preview = _preview(config)

    receipt = _activate(config, preview)

    assert receipt.datasets_registered == 2
    assert receipt.backup.payload_count == 2
    assert receipt.backup.manifest_verified is True
    assert receipt.restore_drill_verified is True
    assert receipt.atomic_publication is True
    assert (owner / "historical-store" / "activation.json").is_file()
    assert {path: path.read_bytes() for path in source_before} == source_before
    integrity = integrity_report(config)
    assert integrity.status == "ok"
    assert integrity.safe_to_use is True
    assert integrity.backup_restore_verified is True
    assert integrity.expected_dataset_count == 2
    assert integrity.reconciled_dataset_count == 2
    report = catalogue_report(
        config,
        CatalogueQuery(
            schema_name="bods.session.activity.aggregate",
            minimum_schema_version=1,
            maximum_schema_version=1,
            namespace=CatalogueNamespace.GENERAL,
        ),
    )
    assert not isinstance(report, ActivationRefusal)
    assert report.result_count == 1
    assert report.datasets[0].dataset_id == "dataset:activity"

    retry_preview = _preview(config)
    retry = _activate(config, retry_preview)
    assert retry.idempotent_retry is True
    assert retry.preview_digest == receipt.preview_digest
    assert retry.backup.backup_digest == receipt.backup.backup_digest


def test_confirmation_mismatch_never_creates_staging_or_target(
    activation_workspace: tuple[ActivationConfig, Path, Path],
) -> None:
    config, owner, imports = activation_workspace
    _write_bundle(
        imports,
        name="activity",
        kind=AggregateImportKind.BODS_SESSION_ACTIVITY_AGGREGATE,
    )
    _preview(config)

    result = activate_store(config, expected_preview_digest="f" * 64)

    assert isinstance(result, ActivationRefusal)
    assert result.code is ActivationRefusalCode.PREVIEW_DIGEST_MISMATCH
    assert not (owner / "historical-store").exists()
    assert not tuple(owner.glob(".historical-store-activation-*"))


def test_fault_before_publication_leaves_no_target_and_exact_retry_resumes(
    activation_workspace: tuple[ActivationConfig, Path, Path],
) -> None:
    config, owner, imports = activation_workspace
    _write_bundle(
        imports,
        name="activity",
        kind=AggregateImportKind.BODS_SESSION_ACTIVITY_AGGREGATE,
    )
    preview = _preview(config)

    def interrupt(stage: str) -> None:
        assert stage == "before_publication"
        raise RuntimeError("synthetic interruption")

    refused = activate_store(
        config,
        expected_preview_digest=preview.preview_digest,
        clock=lambda: NOW,
        fault_hook=interrupt,
    )
    assert isinstance(refused, ActivationRefusal)
    assert refused.code is ActivationRefusalCode.PUBLICATION_REFUSED
    assert not (owner / "historical-store").exists()
    assert len(tuple(owner.glob(".historical-store-activation-*"))) == 1

    resumed_preview = _preview(config)
    assert resumed_preview.activatable is True
    resumed = _activate(config, resumed_preview)
    assert resumed.datasets_registered == 1
    assert (owner / "historical-store").is_dir()


@pytest.mark.parametrize(
    ("change", "expected_code"),
    [
        (
            {"expected_artifact_digest": "0" * 64},
            ActivationRefusalCode.DIGEST_MISMATCH.value,
        ),
        (
            {"artifact_handle": "../outside.json"},
            ActivationRefusalCode.MANIFEST_INVALID.value,
        ),
    ],
)
def test_digest_and_traversal_refusals_are_path_free(
    activation_workspace: tuple[ActivationConfig, Path, Path],
    change: dict[str, object],
    expected_code: str,
) -> None:
    config, owner, imports = activation_workspace
    _write_bundle(
        imports,
        name="activity",
        kind=AggregateImportKind.BODS_SESSION_ACTIVITY_AGGREGATE,
        manifest_changes=change,
    )

    preview = _preview(config)

    assert preview.activatable is False
    assert preview.would_refuse == 1
    assert preview.findings[0].refusal_code == expected_code
    assert str(owner) not in preview.model_dump_json()


@pytest.mark.parametrize(
    ("change", "expected_code"),
    [
        (
            {"expected_source_file_digest": "0" * 64},
            ActivationRefusalCode.DIGEST_MISMATCH.value,
        ),
        (
            {"participant_data": "synthetic-fixture"},
            ActivationRefusalCode.PRIVATE_CONTENT_REFUSED.value,
        ),
        (
            {"credentials": "synthetic-fixture"},
            ActivationRefusalCode.PRIVATE_CONTENT_REFUSED.value,
        ),
    ],
)
def test_source_digest_participant_and_credential_metadata_fail_closed(
    activation_workspace: tuple[ActivationConfig, Path, Path],
    change: dict[str, object],
    expected_code: str,
) -> None:
    config, owner, imports = activation_workspace
    _write_bundle(
        imports,
        name="activity",
        kind=AggregateImportKind.BODS_SESSION_ACTIVITY_AGGREGATE,
        manifest_changes=change,
    )

    preview = _preview(config)

    assert preview.activatable is False
    assert preview.findings[0].refusal_code == expected_code
    assert str(owner) not in preview.model_dump_json()


def test_licence_and_private_payload_are_refused_by_existing_store_gate(
    activation_workspace: tuple[ActivationConfig, Path, Path],
) -> None:
    config, _, imports = activation_workspace
    _write_bundle(
        imports,
        name="licence",
        kind=AggregateImportKind.BODS_SESSION_ACTIVITY_AGGREGATE,
        licence="not-allowlisted",
    )
    licence_preview = _preview(config)
    assert licence_preview.activatable is False
    assert licence_preview.findings[0].refusal_code == "STORE_LICENCE_NOT_ALLOWLISTED"

    for path in imports.iterdir():
        path.unlink()
    _write_bundle(
        imports,
        name="private",
        kind=AggregateImportKind.BODS_SESSION_ACTIVITY_AGGREGATE,
        payload=_activity_payload(timezone_note="/Users/private/archive"),
    )
    private_preview = _preview(config)
    assert private_preview.activatable is False
    assert private_preview.findings[0].refusal_code == "STORE_PRIVATE_PATH_DETECTED"


def test_forecast_source_cannot_manufacture_standing(
    activation_workspace: tuple[ActivationConfig, Path, Path],
) -> None:
    config, _, imports = activation_workspace
    _write_bundle(
        imports,
        name="forecast",
        kind=AggregateImportKind.BUS_FORECAST_FIT,
        source_standing=EvidenceStanding(
            evidence_role=EvidenceRole.PROTOCOL_CONFIRMED,
            admission_status=AdmissionStatus.ADMITTED,
            evidence=True,
        ),
    )

    preview = _preview(config)

    assert preview.activatable is False
    assert preview.findings[0].refusal_code == ActivationRefusalCode.SOURCE_CONTRACT_MISMATCH.value


def test_unsafe_permissions_and_symlinks_fail_closed(
    activation_workspace: tuple[ActivationConfig, Path, Path],
    tmp_path: Path,
) -> None:
    config, _, imports = activation_workspace
    _, artifact, _ = _write_bundle(
        imports,
        name="activity",
        kind=AggregateImportKind.BODS_SESSION_ACTIVITY_AGGREGATE,
    )
    artifact.chmod(0o644)
    refused = preview_activation(config)
    assert isinstance(refused, ActivationRefusal)
    assert refused.code is ActivationRefusalCode.UNSAFE_PERMISSIONS

    artifact.chmod(0o600)
    outside = tmp_path / "outside.json"
    _write_private(outside, _activity_payload())
    artifact.unlink()
    artifact.symlink_to(outside)
    refused = preview_activation(config)
    assert isinstance(refused, ActivationRefusal)
    assert refused.code is ActivationRefusalCode.SYMLINK_FORBIDDEN


def test_duplicate_dataset_and_orphan_staging_are_visible_without_paths(
    activation_workspace: tuple[ActivationConfig, Path, Path],
) -> None:
    config, owner, imports = activation_workspace
    _write_bundle(
        imports,
        name="first",
        kind=AggregateImportKind.BODS_SESSION_ACTIVITY_AGGREGATE,
        manifest_changes={"dataset_id": "dataset:duplicate"},
    )
    _write_bundle(
        imports,
        name="second",
        kind=AggregateImportKind.BODS_SESSION_ACTIVITY_AGGREGATE,
        manifest_changes={"dataset_id": "dataset:duplicate"},
    )
    orphan = owner / ".historical-store-activation-deadbeefdeadbeef"
    orphan.mkdir(mode=0o700)

    preview = _preview(config)

    assert preview.activatable is False
    assert preview.would_refuse == 2
    assert all(
        finding.refusal_code == ActivationRefusalCode.DUPLICATE_DATASET.value
        for finding in preview.findings
    )
    assert len(preview.orphan_staging_handles) == 1
    assert "deadbeef" not in preview.model_dump_json()
    assert str(owner) not in preview.model_dump_json()


def test_corrupt_registered_payload_is_reported_and_never_deleted(
    activation_workspace: tuple[ActivationConfig, Path, Path],
) -> None:
    config, owner, imports = activation_workspace
    _write_bundle(
        imports,
        name="activity",
        kind=AggregateImportKind.BODS_SESSION_ACTIVITY_AGGREGATE,
    )
    _activate(config, _preview(config))
    payloads = tuple((owner / "historical-store" / "payloads" / "sha256").rglob("*.json"))
    assert len(payloads) == 1
    payloads[0].write_bytes(b"corrupt")

    report = integrity_report(config)

    assert report.safe_to_use is False
    assert report.status in {"corrupt", "refused"}
    assert report.refusal_code is ActivationRefusalCode.STORE_OPEN_REFUSED
    assert payloads[0].read_bytes() == b"corrupt"
    retry_preview = _preview(config)
    retry = activate_store(
        config,
        expected_preview_digest=retry_preview.preview_digest,
    )
    assert isinstance(retry, ActivationRefusal)
    assert retry.code is ActivationRefusalCode.TARGET_CORRUPT
    assert payloads[0].read_bytes() == b"corrupt"


@pytest.mark.parametrize("relative", ("catalogue.sqlite", "manifest.json"))
def test_corrupt_backup_is_reported_without_changing_the_live_catalogue(
    activation_workspace: tuple[ActivationConfig, Path, Path],
    relative: str,
) -> None:
    config, owner, imports = activation_workspace
    _write_bundle(
        imports,
        name="activity",
        kind=AggregateImportKind.BODS_SESSION_ACTIVITY_AGGREGATE,
    )
    receipt = _activate(config, _preview(config))
    backup_file = owner / "historical-store" / receipt.backup.backup_handle / relative
    backup_file.write_bytes(b"corrupt backup")

    report = integrity_report(config)

    assert report.status == "corrupt"
    assert report.safe_to_use is False
    assert report.backup_restore_verified is False
    assert report.refusal_code is ActivationRefusalCode.BACKUP_REFUSED
    assert report.recovery is not None and report.recovery.safe_to_open is True
    live = catalogue_report(
        config,
        CatalogueQuery(
            schema_name="bods.session.activity.aggregate",
            minimum_schema_version=1,
            maximum_schema_version=1,
            namespace=CatalogueNamespace.GENERAL,
        ),
    )
    assert not isinstance(live, ActivationRefusal)
    assert live.result_count == 1
    assert backup_file.read_bytes() == b"corrupt backup"


def test_symlinked_owner_workspace_is_refused_before_discovery(tmp_path: Path) -> None:
    real_owner = tmp_path / "real-owner"
    imports = real_owner / "safe-imports"
    real_owner.mkdir(mode=0o700)
    imports.mkdir(mode=0o700)
    linked_owner = tmp_path / "linked-owner"
    linked_owner.symlink_to(real_owner, target_is_directory=True)
    config = ActivationConfig(
        workspace_id="symlinked-store",
        owner_workspace=linked_owner,
        repository_root=REPOSITORY_ROOT,
        import_roots=(linked_owner / "safe-imports",),
        licence_policy=LicenceAllowlistPolicy(
            policy_version="synthetic-v1",
            allowed_classes=(LICENCE,),
        ),
    )

    refused = preview_activation(config)

    assert isinstance(refused, ActivationRefusal)
    assert refused.code is ActivationRefusalCode.SYMLINK_FORBIDDEN
    assert not (real_owner / "historical-store").exists()


def test_unmanaged_target_is_reported_and_never_overwritten(
    activation_workspace: tuple[ActivationConfig, Path, Path],
) -> None:
    config, owner, imports = activation_workspace
    _write_bundle(
        imports,
        name="activity",
        kind=AggregateImportKind.BODS_SESSION_ACTIVITY_AGGREGATE,
    )
    target = owner / "historical-store"
    target.mkdir(mode=0o700)
    sentinel = target / "unmanaged.json"
    _write_private(sentinel, b"unmanaged")

    preview = _preview(config)
    refused = activate_store(
        config,
        expected_preview_digest=preview.preview_digest,
    )

    assert preview.target_status == "corrupt"
    assert preview.activatable is False
    assert isinstance(refused, ActivationRefusal)
    assert refused.code is ActivationRefusalCode.PREVIEW_NOT_ACTIVATABLE
    assert sentinel.read_bytes() == b"unmanaged"


def test_symlinked_resume_stage_is_refused_without_touching_its_target(
    activation_workspace: tuple[ActivationConfig, Path, Path],
    tmp_path: Path,
) -> None:
    config, owner, imports = activation_workspace
    _write_bundle(
        imports,
        name="activity",
        kind=AggregateImportKind.BODS_SESSION_ACTIVITY_AGGREGATE,
    )
    preview = _preview(config)
    external = tmp_path / "external-stage-target"
    external.mkdir(mode=0o700)
    stage = owner / f".historical-store-activation-{preview.preview_digest[:16]}"
    stage.mkdir(mode=0o700)
    (stage / "historical-store").symlink_to(external, target_is_directory=True)

    refused = activate_store(
        config,
        expected_preview_digest=preview.preview_digest,
    )

    assert isinstance(refused, ActivationRefusal)
    assert refused.code is ActivationRefusalCode.SYMLINK_FORBIDDEN
    assert not tuple(external.iterdir())
    assert not (owner / "historical-store").exists()


@pytest.fixture
def cli_module() -> ModuleType:
    path = REPOSITORY_ROOT / "scripts" / "historical_store_activation.py"
    spec = importlib.util.spec_from_file_location("historical_store_activation_cli", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_local_config(path: Path, config: ActivationConfig) -> None:
    _write_private(
        path,
        _json_bytes(
            {
                "schema_version": "1.0",
                "workspace_id": config.workspace_id,
                "owner_workspace": str(config.owner_workspace),
                "repository_root": str(config.repository_root),
                "import_roots": [str(item) for item in config.import_roots],
                "licence_policy": config.licence_policy.model_dump(mode="json"),
            }
        ),
    )


def test_cli_preview_activate_catalogue_and_integrity_are_path_free(
    activation_workspace: tuple[ActivationConfig, Path, Path],
    cli_module: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config, owner, imports = activation_workspace
    _write_bundle(
        imports,
        name="activity",
        kind=AggregateImportKind.BODS_SESSION_ACTIVITY_AGGREGATE,
    )
    config_path = tmp_path / "activation-config.json"
    _write_local_config(config_path, config)
    main = cast(Callable[[Sequence[str] | None], int], cli_module.main)

    assert main(["preview", "--config", str(config_path)]) == 0
    preview_output = capsys.readouterr().out
    preview = json.loads(preview_output)
    assert str(tmp_path) not in preview_output

    assert (
        main(
            [
                "activate",
                "--config",
                str(config_path),
                "--expect-preview-digest",
                preview["preview_digest"],
            ]
        )
        == 0
    )
    assert str(owner) not in capsys.readouterr().out
    assert (
        main(
            [
                "catalogue",
                "--config",
                str(config_path),
                "--schema-name",
                "bods.session.activity.aggregate",
                "--minimum-version",
                "1",
                "--maximum-version",
                "1",
                "--namespace",
                "general",
            ]
        )
        == 0
    )
    catalogue_output = capsys.readouterr().out
    assert json.loads(catalogue_output)["result_count"] == 1
    assert str(owner) not in catalogue_output
    assert main(["integrity", "--config", str(config_path)]) == 0
    integrity_output = capsys.readouterr().out
    assert json.loads(integrity_output)["safe_to_use"] is True
    assert str(owner) not in integrity_output
