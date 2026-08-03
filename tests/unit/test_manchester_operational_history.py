from __future__ import annotations

import json
import stat
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.integration.manchester.operational_history import (
    GENESIS_CHAIN_SHA256,
    OPERATIONAL_DAY_DIRECTORY,
    OPERATIONAL_JOURNAL_RELATIVE_PATH,
    ManchesterAggregateRetentionPolicy,
    ManchesterOperationalAppendReceipt,
    ManchesterOperationalAttemptRecord,
    ManchesterOperationalCadenceExpectation,
    ManchesterOperationalDayAggregate,
    ManchesterOperationalDayPublicationReceipt,
    ManchesterOperationalHistoryError,
    OperationalSource,
    OperationalTerminalStatus,
    append_operational_attempt,
    build_operational_attempt_record,
    build_operational_day_store_candidate,
    compact_operational_utc_day,
    load_operational_journal,
    operational_day_store_schema,
    project_operational_day_to_london,
    proposed_aggregate_retention_policy,
    publish_operational_utc_day,
)
from traffictwin.platform.historical_store import (
    AdmissionStatus,
    AuthoritativeSourceRecord,
    EvidenceRole,
    EvidenceStanding,
    InMemoryHistoricalStore,
    PayloadClass,
    StoreReceipt,
)
from traffictwin.release.durable_workspace import (
    create_durable_v07_workspace,
    preview_durable_v07_workspace,
)

DAY = date(2026, 8, 2)
START = datetime(2026, 8, 2, tzinfo=UTC)
LICENCE = "private-academic-aggregate-test"


def _workspace(tmp_path: Path) -> Path:
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    parent.chmod(0o700)
    target = parent / "workspace-v0.7"
    plan = preview_durable_v07_workspace(target)
    create_durable_v07_workspace(
        target,
        expected_plan_fingerprint=plan.confirmation_fingerprint(),
        clock=lambda: START,
    )
    return target


def _policy() -> ManchesterAggregateRetentionPolicy:
    return ManchesterAggregateRetentionPolicy(
        decision_status="owner_approved",
        owner_decision_id="decision-0123456789abcdef",
        decided_at_utc=START,
    )


def _expectations() -> tuple[ManchesterOperationalCadenceExpectation, ...]:
    return (
        ManchesterOperationalCadenceExpectation(
            source="bods",
            configuration_status="enabled",
            interval_seconds=60,
            expected_automatic_attempts=1440,
        ),
        ManchesterOperationalCadenceExpectation(
            source="national_highways",
            configuration_status="enabled",
            interval_seconds=300,
            expected_automatic_attempts=288,
        ),
    )


def _record(
    *,
    source: OperationalSource = "bods",
    terminal: datetime = START + timedelta(minutes=1),
    prior: str = GENESIS_CHAIN_SHA256,
    receipt: str = "1" * 64,
    status: OperationalTerminalStatus = "succeeded",
    failure: str | None = None,
    source_end: datetime | None = None,
) -> ManchesterOperationalAttemptRecord:
    return build_operational_attempt_record(
        source=source,
        source_contract_version="contract-v1",
        trigger="automatic",
        attempted_at_utc=terminal - timedelta(seconds=2),
        terminal_at_utc=terminal,
        terminal_status=status,
        failure_code=failure,
        request_scope_fingerprint="a" * 64,
        accepted_count=4 if status == "succeeded" else 0,
        excluded_count=1,
        stale_count=1 if status == "succeeded" else 0,
        source_time_start_utc=None if source_end is None else source_end - timedelta(seconds=3),
        source_time_end_utc=source_end,
        terminal_receipt_fingerprint=receipt,
        prior_chain_sha256=prior,
    )


def _append(
    workspace: Path, record: ManchesterOperationalAttemptRecord
) -> ManchesterOperationalAppendReceipt:
    policy = _policy()
    return append_operational_attempt(
        workspace,
        record,
        policy=policy,
        expected_policy_fingerprint=policy.fingerprint(),
        authority_validator=lambda candidate: candidate == policy,
    )


def test_proposed_policy_cannot_mutate_and_empty_status_is_path_free(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    record = _record()
    policy = proposed_aggregate_retention_policy()

    with pytest.raises(ManchesterOperationalHistoryError, match="RETENTION_POLICY_UNAPPROVED"):
        append_operational_attempt(
            workspace,
            record,
            policy=policy,
            expected_policy_fingerprint=policy.fingerprint(),
            authority_validator=lambda _: True,
        )

    journal = load_operational_journal(workspace)
    assert journal.records == ()
    assert journal.report.tail_chain_sha256 == GENESIS_CHAIN_SHA256
    assert journal.report.network_request_performed is False
    assert str(workspace) not in journal.report.model_dump_json()
    assert not (workspace / OPERATIONAL_JOURNAL_RELATIVE_PATH).exists()


def test_append_verifies_chain_permissions_retry_and_safe_failure(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    first = _record(source_end=START + timedelta(minutes=2))
    first_receipt = _append(workspace, first)
    second = _record(
        source="national_highways",
        terminal=START + timedelta(minutes=6),
        prior=first.fingerprint(),
        receipt="2" * 64,
        status="failed",
        failure="provider-secret-detail",
    )
    second_receipt = _append(workspace, second)
    retry = _append(workspace, second)

    journal = load_operational_journal(workspace)
    target = workspace / OPERATIONAL_JOURNAL_RELATIVE_PATH
    assert first_receipt.idempotent_retry is False
    assert second_receipt.idempotent_retry is False
    assert retry.idempotent_retry is True
    assert journal.report.record_count == 2
    assert journal.report.tail_chain_sha256 == second.fingerprint()
    assert journal.records[0].source_clock_skew_count == 1
    assert journal.records[1].failure_code == "UNCLASSIFIED_SAFE_FAILURE"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    serialized = target.read_text(encoding="utf-8")
    assert "provider-secret-detail" not in serialized
    assert str(workspace) not in serialized
    assert "vehicle_id" not in serialized


def test_chain_receipt_and_fault_refusals_are_atomic(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    first = _record()
    policy = _policy()

    def stop(stage: str) -> None:
        if stage == "before_journal_publication":
            raise RuntimeError("injected stop")

    with pytest.raises(RuntimeError, match="injected stop"):
        append_operational_attempt(
            workspace,
            first,
            policy=policy,
            expected_policy_fingerprint=policy.fingerprint(),
            authority_validator=lambda _: True,
            fault_hook=stop,
        )
    assert load_operational_journal(workspace).records == ()

    _append(workspace, first)
    bad_chain = _record(receipt="3" * 64, prior="f" * 64)
    with pytest.raises(ManchesterOperationalHistoryError, match="APPEND_CHAIN_MISMATCH"):
        _append(workspace, bad_chain)
    conflict = first.model_copy(update={"accepted_count": 3})
    with pytest.raises(ManchesterOperationalHistoryError, match="RECEIPT_CONFLICT"):
        _append(workspace, conflict)
    assert load_operational_journal(workspace).records == (first,)


def test_partial_and_divergent_journals_fail_closed(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    first = _record()
    _append(workspace, first)
    target = workspace / OPERATIONAL_JOURNAL_RELATIVE_PATH
    original = target.read_bytes()

    target.write_bytes(original[:-1])
    target.chmod(0o600)
    with pytest.raises(ManchesterOperationalHistoryError, match="JOURNAL_PARTIAL"):
        load_operational_journal(workspace)

    target.write_bytes(original)
    target.chmod(0o600)
    dumped = json.loads(original)
    dumped["prior_chain_sha256"] = "f" * 64
    target.write_text(json.dumps(dumped, sort_keys=True, separators=(",", ":")) + "\n")
    target.chmod(0o600)
    with pytest.raises(ManchesterOperationalHistoryError, match="CHAIN_DIVERGED"):
        load_operational_journal(workspace)


def test_compaction_is_utc_complete_reconciled_and_reorder_safe() -> None:
    first = _record(source_end=START + timedelta(minutes=2))
    second = _record(
        source="national_highways",
        terminal=START + timedelta(hours=1, minutes=5),
        prior=first.fingerprint(),
        receipt="2" * 64,
    )

    day = compact_operational_utc_day((first, second), DAY, _expectations())

    assert len(day.utc_hours) == 48
    assert day.journal_record_count == 2
    assert day.source_aggregates[0].attempts == 1
    assert day.source_aggregates[0].missing_cadence_attempts == 1439
    assert day.source_aggregates[1].missing_cadence_attempts == 287
    assert day.source_aggregates[0].source_clock_skew_count == 1
    assert day == compact_operational_utc_day((first, second), DAY, _expectations())
    with pytest.raises(ManchesterOperationalHistoryError, match="SEQUENCE_REORDERED"):
        compact_operational_utc_day((second, first), DAY, _expectations())
    with pytest.raises(ManchesterOperationalHistoryError, match="DUPLICATE_RECEIPT"):
        compact_operational_utc_day((first, first), DAY, _expectations())


def test_london_projection_retains_fallback_offset_and_fold() -> None:
    fallback_day = compact_operational_utc_day((), date(2026, 10, 25), _expectations())
    projection = project_operational_day_to_london(fallback_day)
    repeated = [
        item
        for item in projection
        if item.source == "bods"
        and item.london_local_date == date(2026, 10, 25)
        and item.london_hour == 1
    ]

    assert [(item.utc_offset_minutes, item.fold) for item in repeated] == [(60, 0), (0, 1)]


def test_immutable_day_requires_delay_and_blocks_late_append(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    first = _record()
    _append(workspace, first)
    journal = load_operational_journal(workspace)
    day = compact_operational_utc_day(journal.records, DAY, _expectations())
    policy = _policy()

    def publish(
        candidate: ManchesterOperationalDayAggregate,
    ) -> ManchesterOperationalDayPublicationReceipt:
        return publish_operational_utc_day(
            workspace,
            candidate,
            policy=policy,
            expected_policy_fingerprint=policy.fingerprint(),
            authority_validator=lambda _: True,
            clock=lambda: day.day_end_utc + timedelta(hours=24),
        )

    with pytest.raises(ManchesterOperationalHistoryError, match="COMPACTION_DELAY_ACTIVE"):
        publish_operational_utc_day(
            workspace,
            day,
            policy=policy,
            expected_policy_fingerprint=policy.fingerprint(),
            authority_validator=lambda _: True,
            clock=lambda: day.day_end_utc + timedelta(hours=23),
        )
    first_receipt = publish(day)
    retry = publish(day)
    target = workspace / OPERATIONAL_DAY_DIRECTORY / "2026-08-02.json"
    assert first_receipt.idempotent_retry is False
    assert retry.idempotent_retry is True
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    late = _record(
        terminal=START + timedelta(hours=12),
        prior=first.fingerprint(),
        receipt="4" * 64,
    )
    with pytest.raises(ManchesterOperationalHistoryError, match="DAY_ALREADY_COMPACTED"):
        _append(workspace, late)


def test_closed_day_adapter_registers_only_safe_descriptive_source() -> None:
    first = _record()
    day = compact_operational_utc_day((first,), DAY, _expectations())
    standing = EvidenceStanding(
        evidence_role=EvidenceRole.DESCRIPTIVE,
        admission_status=AdmissionStatus.NOT_APPLICABLE,
        evidence=False,
    )
    source = AuthoritativeSourceRecord(
        source_record_id="source:manchester-operational-journal",
        record_digest="d" * 64,
        payload_digest=day.journal_tail_record_sha256,
        schema_name="manchester.operational.journal",
        schema_version=1,
        payload_class=PayloadClass.SAFE_ANALYSIS_SUMMARY,
        standing=standing,
        sparse64=False,
        metadata_only=False,
    )
    schema = operational_day_store_schema()
    candidate = build_operational_day_store_candidate(day, source, licence_class=LICENCE)
    store = InMemoryHistoricalStore(
        schemas=(schema,),
        authoritative_sources=(source,),
        licence_allowlist=frozenset({LICENCE}),
    )

    receipt = store.register_dataset(candidate)

    assert isinstance(receipt, StoreReceipt)
    assert candidate.record.payload_class is PayloadClass.SAFE_ANALYSIS_SUMMARY
    assert candidate.record.standing == standing
    incompatible = source.model_copy(update={"schema_name": "generic.json"})
    with pytest.raises(ManchesterOperationalHistoryError, match="SOURCE_CONTRACT_MISMATCH"):
        build_operational_day_store_candidate(day, incompatible, licence_class=LICENCE)


def test_read_only_cli_status_and_day_preview_are_path_free(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    runner = CliRunner()

    status = runner.invoke(
        app,
        ["release", "v07-operational-history-status", str(workspace), "--format", "json"],
    )
    preview = runner.invoke(
        app,
        [
            "release",
            "v07-operational-day-preview",
            str(workspace),
            "2026-08-02",
            "--bods-status",
            "enabled",
            "--bods-interval",
            "60",
            "--bods-expected",
            "1440",
            "--format",
            "json",
        ],
    )

    assert status.exit_code == 0, status.output
    assert json.loads(status.output)["record_count"] == 0
    assert preview.exit_code == 0, preview.output
    payload = json.loads(preview.output)
    assert payload["journal_record_count"] == 0
    assert len(payload["utc_hours"]) == 48
    assert str(workspace) not in status.output + preview.output
    assert not (workspace / OPERATIONAL_JOURNAL_RELATIVE_PATH).exists()
