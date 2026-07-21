"""Manual, import-first tracking for externally executed protocol slots."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.experiments.protocol import ExperimentProtocol
from traffictwin.storage.migrations import migrate_registry


class ProtocolSlotStatus(StrEnum):
    """Manual lifecycle for one planned external run slot."""

    PLANNED = "planned"
    RECEIVED = "received"
    VALIDATED = "validated"
    MATCHED = "matched"
    REJECTED = "rejected"
    COMPLETE = "complete"


SLOT_TRANSITIONS: dict[ProtocolSlotStatus, set[ProtocolSlotStatus]] = {
    ProtocolSlotStatus.PLANNED: {ProtocolSlotStatus.RECEIVED, ProtocolSlotStatus.REJECTED},
    ProtocolSlotStatus.RECEIVED: {
        ProtocolSlotStatus.VALIDATED,
        ProtocolSlotStatus.REJECTED,
    },
    ProtocolSlotStatus.VALIDATED: {
        ProtocolSlotStatus.MATCHED,
        ProtocolSlotStatus.REJECTED,
    },
    ProtocolSlotStatus.MATCHED: {
        ProtocolSlotStatus.COMPLETE,
        ProtocolSlotStatus.REJECTED,
    },
    ProtocolSlotStatus.REJECTED: set(),
    ProtocolSlotStatus.COMPLETE: set(),
}


class ProtocolSlotRecord(BaseModel):
    """Persisted manual status for one protocol slot."""

    model_config = ConfigDict(extra="forbid")

    protocol_id: str
    experiment_id: str
    slot_id: str
    sequence: int = Field(ge=1)
    status: ProtocolSlotStatus
    expected_run_id: str
    expected_bundle_id: str
    observed_run_id: str | None = None
    observed_bundle_id: str | None = None
    note: str | None = None
    updated_at: datetime


class ProtocolTrackingSummary(BaseModel):
    """Counts for one tracked protocol."""

    model_config = ConfigDict(extra="forbid")

    protocol_id: str
    experiment_id: str
    input_fingerprint: str
    total_slots: int
    counts_by_status: dict[str, int]


class ProtocolTrackingError(RuntimeError):
    """Base tracking error."""


class ProtocolTrackingConflictError(ProtocolTrackingError):
    """Raised when stored protocol identity conflicts with a new document."""


class ProtocolTrackingNotFoundError(ProtocolTrackingError):
    """Raised when a protocol or slot is absent."""


class InvalidProtocolSlotTransitionError(ProtocolTrackingError):
    """Raised when a slot lifecycle transition is invalid."""


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


class ProtocolTracker:
    """SQLite-backed manual protocol tracker sharing the registry database."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        """Migrate the shared registry before protocol tracking access."""

        migrate_registry(self.path)

    def register_protocol(
        self,
        protocol: ExperimentProtocol,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> bool:
        """Register every planned slot atomically; return False when already identical."""

        self.initialize()
        now = clock().isoformat()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT input_fingerprint FROM experiment_protocols WHERE protocol_id = ?",
                (protocol.protocol_id,),
            ).fetchone()
            if existing is not None:
                if cast(str, existing["input_fingerprint"]) == protocol.input_fingerprint:
                    return False
                raise ProtocolTrackingConflictError(
                    f"protocol_id exists with different content: {protocol.protocol_id}"
                )
            conn.execute(
                """
                INSERT INTO experiment_protocols (
                    protocol_id, experiment_id, input_fingerprint, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    protocol.protocol_id,
                    protocol.experiment.experiment_id,
                    protocol.input_fingerprint,
                    protocol.to_json(),
                    now,
                ),
            )
            conn.executemany(
                """
                INSERT INTO experiment_protocol_slots (
                    protocol_id, experiment_id, slot_id, sequence, status,
                    expected_run_id, expected_bundle_id, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        protocol.protocol_id,
                        protocol.experiment.experiment_id,
                        slot.slot_id,
                        slot.sequence,
                        ProtocolSlotStatus.PLANNED.value,
                        slot.expected_run_id,
                        slot.expected_bundle_id,
                        now,
                    )
                    for slot in protocol.slots
                ],
            )
        return True

    def list_protocol_ids(self) -> list[str]:
        """List tracked protocol identifiers."""

        self.initialize()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT protocol_id FROM experiment_protocols ORDER BY protocol_id"
            ).fetchall()
        return [cast(str, row["protocol_id"]) for row in rows]

    def list_slots(self, protocol_id: str) -> list[ProtocolSlotRecord]:
        """List tracked slots in protocol sequence order."""

        self.initialize()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM experiment_protocol_slots
                WHERE protocol_id = ? ORDER BY sequence
                """,
                (protocol_id,),
            ).fetchall()
        if not rows and protocol_id not in self.list_protocol_ids():
            raise ProtocolTrackingNotFoundError(f"tracked protocol not found: {protocol_id}")
        return [_record(row) for row in rows]

    def update_slot(
        self,
        protocol_id: str,
        slot_id: str,
        new_status: ProtocolSlotStatus,
        *,
        observed_run_id: str | None = None,
        observed_bundle_id: str | None = None,
        note: str | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> ProtocolSlotRecord:
        """Apply one explicit lifecycle transition."""

        self.initialize()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM experiment_protocol_slots
                WHERE protocol_id = ? AND slot_id = ?
                """,
                (protocol_id, slot_id),
            ).fetchone()
            if row is None:
                raise ProtocolTrackingNotFoundError(
                    f"tracked protocol slot not found: {protocol_id}/{slot_id}"
                )
            current = _record(row)
            if (
                new_status is not current.status
                and new_status not in SLOT_TRANSITIONS[current.status]
            ):
                raise InvalidProtocolSlotTransitionError(
                    "invalid protocol slot transition: "
                    f"{current.status.value} -> {new_status.value}"
                )
            updated_at = clock()
            conn.execute(
                """
                UPDATE experiment_protocol_slots
                SET status = ?, observed_run_id = ?, observed_bundle_id = ?,
                    note = ?, updated_at = ?
                WHERE protocol_id = ? AND slot_id = ?
                """,
                (
                    new_status.value,
                    observed_run_id if observed_run_id is not None else current.observed_run_id,
                    observed_bundle_id
                    if observed_bundle_id is not None
                    else current.observed_bundle_id,
                    note if note is not None else current.note,
                    updated_at.isoformat(),
                    protocol_id,
                    slot_id,
                ),
            )
        return current.model_copy(
            update={
                "status": new_status,
                "observed_run_id": observed_run_id or current.observed_run_id,
                "observed_bundle_id": observed_bundle_id or current.observed_bundle_id,
                "note": note if note is not None else current.note,
                "updated_at": updated_at,
            }
        )

    def summary(self, protocol_id: str) -> ProtocolTrackingSummary:
        """Return deterministic status counts."""

        self.initialize()
        with self._connect() as conn:
            protocol = conn.execute(
                """
                SELECT experiment_id, input_fingerprint FROM experiment_protocols
                WHERE protocol_id = ?
                """,
                (protocol_id,),
            ).fetchone()
            if protocol is None:
                raise ProtocolTrackingNotFoundError(f"tracked protocol not found: {protocol_id}")
            rows = conn.execute(
                """
                SELECT status, COUNT(*) AS count FROM experiment_protocol_slots
                WHERE protocol_id = ? GROUP BY status ORDER BY status
                """,
                (protocol_id,),
            ).fetchall()
        counts = {status.value: 0 for status in ProtocolSlotStatus}
        counts.update({cast(str, row["status"]): int(row["count"]) for row in rows})
        return ProtocolTrackingSummary(
            protocol_id=protocol_id,
            experiment_id=cast(str, protocol["experiment_id"]),
            input_fingerprint=cast(str, protocol["input_fingerprint"]),
            total_slots=sum(counts.values()),
            counts_by_status=counts,
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn


def _record(row: sqlite3.Row) -> ProtocolSlotRecord:
    return ProtocolSlotRecord(
        protocol_id=cast(str, row["protocol_id"]),
        experiment_id=cast(str, row["experiment_id"]),
        slot_id=cast(str, row["slot_id"]),
        sequence=int(row["sequence"]),
        status=ProtocolSlotStatus(cast(str, row["status"])),
        expected_run_id=cast(str, row["expected_run_id"]),
        expected_bundle_id=cast(str, row["expected_bundle_id"]),
        observed_run_id=cast(str | None, row["observed_run_id"]),
        observed_bundle_id=cast(str | None, row["observed_bundle_id"]),
        note=cast(str | None, row["note"]),
        updated_at=datetime.fromisoformat(cast(str, row["updated_at"])),
    )
