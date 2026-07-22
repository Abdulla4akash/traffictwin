"""SQLite metadata registry for Phase 1 TrafficTwin objects."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

from traffictwin.annotations import (
    MAX_ANNOTATIONS_PER_PAGE,
    REGISTRY_VERIFIED_ANNOTATION_TARGETS,
    AnalystAnnotation,
    AnalystAnnotationHistory,
    AnalystAnnotationRequest,
    AnalystAnnotationTargetKind,
    AnalystArtifactReference,
    analyst_annotation_id,
    build_analyst_annotation,
)
from traffictwin.domain.enums import ExperimentStatus, RunStatus
from traffictwin.domain.experiment import Experiment, utc_now
from traffictwin.domain.run import Run
from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.storage.migrations import (
    CURRENT_REGISTRY_SCHEMA_VERSION,
    RegistryMigrationResult,
    migrate_registry,
)


class RegistryError(RuntimeError):
    """Base class for registry errors."""


class DuplicateIdentifierError(RegistryError):
    """Raised when a record identifier already exists."""


class RegistryNotFoundError(RegistryError):
    """Raised when a requested record cannot be found."""


class InvalidStatusTransitionError(RegistryError):
    """Raised when a lifecycle transition is not allowed."""


class RegistryConflictError(RegistryError):
    """Raised when an import conflicts with existing registry metadata."""


@dataclass(frozen=True)
class RegistrySummary:
    """Simple registry inspection result."""

    path: Path
    schema_version: int
    seed_count: int
    experiment_count: int
    run_count: int
    bundle_import_count: int
    metric_collection_count: int = 0
    evidence_pack_count: int = 0
    experiment_evidence_pack_count: int = 0
    experiment_protocol_count: int = 0
    protocol_slot_count: int = 0
    analyst_annotation_count: int = 0


@dataclass(frozen=True)
class BundleImportResult:
    """Result of registering a validated bundle."""

    bundle_id: str | None
    run_id: str | None
    created: bool
    idempotent: bool
    status: str
    message: str


@dataclass(frozen=True)
class BundleImportRecord:
    """Read-only persisted metadata for one registered bundle import."""

    bundle_id: str
    run_id: str
    source_reference: str
    fingerprint: str
    manifest_json: str
    validation_report_json: str
    imported_at: str


EXPERIMENT_TRANSITIONS: dict[ExperimentStatus, set[ExperimentStatus]] = {
    ExperimentStatus.PLANNED: {ExperimentStatus.RUNNING, ExperimentStatus.ARCHIVED},
    ExperimentStatus.RUNNING: {ExperimentStatus.COMPLETED, ExperimentStatus.FAILED},
    ExperimentStatus.COMPLETED: {ExperimentStatus.ARCHIVED},
    ExperimentStatus.FAILED: {ExperimentStatus.ARCHIVED},
    ExperimentStatus.ARCHIVED: set(),
}

RUN_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    RunStatus.REGISTERED: {
        RunStatus.EXPORTED,
        RunStatus.IMPORTED,
        RunStatus.VALIDATING,
        RunStatus.FAILED,
    },
    RunStatus.EXPORTED: {RunStatus.IMPORTED, RunStatus.FAILED},
    RunStatus.IMPORTED: {RunStatus.VALIDATING, RunStatus.FAILED},
    RunStatus.VALIDATING: {RunStatus.VALIDATED, RunStatus.FAILED},
    RunStatus.VALIDATED: {RunStatus.COMPLETED, RunStatus.FAILED},
    RunStatus.COMPLETED: set(),
    RunStatus.FAILED: set(),
}


class Registry:
    """SQLite-backed metadata registry."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def initialize(self) -> RegistryMigrationResult:
        """Create or atomically migrate the registry to the current schema."""

        return migrate_registry(self.path)

    def add_seed(self, seed: ScenarioSeed) -> None:
        """Register a scenario seed."""

        now = utc_now().isoformat()
        self._insert(
            table="seeds",
            id_column="seed_id",
            identifier=seed.seed_id,
            payload=seed.model_dump_json(),
            created_at=now,
            updated_at=now,
        )

    def get_seed(self, seed_id: str) -> ScenarioSeed:
        """Retrieve a scenario seed by ID."""

        payload = self._get_payload("seeds", "seed_id", seed_id)
        return ScenarioSeed.model_validate_json(payload)

    def list_seeds(self) -> list[ScenarioSeed]:
        """List registered scenario seeds in identifier order."""

        return [
            ScenarioSeed.model_validate_json(payload)
            for payload in self._list_payloads("seeds", "seed_id")
        ]

    def add_experiment(self, experiment: Experiment) -> None:
        """Register an experiment."""

        self._insert(
            table="experiments",
            id_column="experiment_id",
            identifier=experiment.experiment_id,
            payload=experiment.model_dump_json(),
            created_at=experiment.created_at.isoformat(),
            updated_at=experiment.updated_at.isoformat(),
            status=experiment.status.value,
        )

    def get_experiment(self, experiment_id: str) -> Experiment:
        """Retrieve an experiment by ID."""

        payload = self._get_payload("experiments", "experiment_id", experiment_id)
        return Experiment.model_validate_json(payload)

    def list_experiments(self) -> list[Experiment]:
        """List registered experiments in identifier order."""

        return [
            Experiment.model_validate_json(payload)
            for payload in self._list_payloads("experiments", "experiment_id")
        ]

    def update_experiment_status(
        self,
        experiment_id: str,
        new_status: ExperimentStatus,
    ) -> Experiment:
        """Update an experiment status if the transition is allowed."""

        current = self.get_experiment(experiment_id)
        self._ensure_transition(current.status, new_status, EXPERIMENT_TRANSITIONS)
        updated = current.model_copy(update={"status": new_status, "updated_at": utc_now()})
        self._update_status_payload(
            table="experiments",
            id_column="experiment_id",
            identifier=experiment_id,
            status=new_status.value,
            payload=updated.model_dump_json(),
            updated_at=updated.updated_at.isoformat(),
        )
        return updated

    def add_run(self, run: Run) -> None:
        """Register a run."""

        self._insert(
            table="runs",
            id_column="run_id",
            identifier=run.run_id,
            payload=run.model_dump_json(),
            created_at=run.created_at.isoformat(),
            updated_at=run.updated_at.isoformat(),
            status=run.status.value,
        )

    def get_run(self, run_id: str) -> Run:
        """Retrieve a run by ID."""

        payload = self._get_payload("runs", "run_id", run_id)
        return Run.model_validate_json(payload)

    def list_runs(self) -> list[Run]:
        """List registered runs in identifier order."""

        return [
            Run.model_validate_json(payload) for payload in self._list_payloads("runs", "run_id")
        ]

    def update_run_status(self, run_id: str, new_status: RunStatus) -> Run:
        """Update a run status if the transition is allowed."""

        current = self.get_run(run_id)
        self._ensure_transition(current.status, new_status, RUN_TRANSITIONS)
        updated = current.model_copy(update={"status": new_status, "updated_at": utc_now()})
        self._update_status_payload(
            table="runs",
            id_column="run_id",
            identifier=run_id,
            status=new_status.value,
            payload=updated.model_dump_json(),
            updated_at=updated.updated_at.isoformat(),
        )
        return updated

    def inspect(self) -> RegistrySummary:
        """Return record counts for the registry."""

        # All upgrades are delegated to the ordered transactional migration plan.
        self.initialize()
        with self._connect() as conn:
            return RegistrySummary(
                path=self.path,
                schema_version=CURRENT_REGISTRY_SCHEMA_VERSION,
                seed_count=self._count(conn, "seeds"),
                experiment_count=self._count(conn, "experiments"),
                run_count=self._count(conn, "runs"),
                bundle_import_count=self._count(conn, "bundle_imports"),
                metric_collection_count=self._count(conn, "metric_collections"),
                evidence_pack_count=self._count(conn, "evidence_packs"),
                experiment_evidence_pack_count=self._count(conn, "experiment_evidence_packs"),
                experiment_protocol_count=self._count(conn, "experiment_protocols"),
                protocol_slot_count=self._count(conn, "experiment_protocol_slots"),
                analyst_annotation_count=self._count(conn, "analyst_annotations"),
            )

    def append_analyst_annotation(
        self,
        request: AnalystAnnotationRequest,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> AnalystAnnotation:
        """Append one immutable analyst annotation and return its registry sequence."""

        self.initialize()
        created_at = clock() if clock is not None else utc_now()
        annotation_id = analyst_annotation_id(
            target=request.target,
            author_label=request.author_label,
            note=request.note,
            decision_label=request.decision_label,
            created_at=created_at,
        )
        try:
            with self._connect() as conn:
                self._ensure_annotation_target_exists(conn, request.target)
                cursor = conn.execute(
                    """
                    INSERT INTO analyst_annotations (
                        annotation_id,
                        target_kind,
                        target_id,
                        target_fingerprint,
                        author_label,
                        note,
                        decision_label,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        annotation_id,
                        request.target.kind.value,
                        request.target.artifact_id,
                        request.target.artifact_fingerprint,
                        request.author_label,
                        request.note,
                        request.decision_label.value,
                        created_at.isoformat(),
                    ),
                )
                sequence = cursor.lastrowid
        except sqlite3.IntegrityError as exc:
            raise DuplicateIdentifierError(
                f"analyst annotation already exists: {annotation_id}"
            ) from exc
        if sequence is None:
            raise RegistryError("analyst annotation sequence allocation failed")
        return build_analyst_annotation(
            request,
            sequence=sequence,
            created_at=created_at,
        )

    def get_analyst_annotation(self, annotation_id: str) -> AnalystAnnotation:
        """Retrieve one immutable analyst annotation by identifier."""

        self.initialize()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM analyst_annotations WHERE annotation_id = ?",
                (annotation_id,),
            ).fetchone()
        if row is None:
            raise RegistryNotFoundError(f"analyst annotation not found: {annotation_id}")
        return self._annotation_from_row(row)

    def list_analyst_annotations(
        self,
        *,
        target: AnalystArtifactReference | None = None,
        after_sequence: int = 0,
        limit: int = 100,
    ) -> AnalystAnnotationHistory:
        """Read one bounded ascending page from the append-only annotation stream."""

        if after_sequence < 0:
            raise ValueError("after_sequence must be non-negative")
        if not 1 <= limit <= MAX_ANNOTATIONS_PER_PAGE:
            raise ValueError(f"limit must be between 1 and {MAX_ANNOTATIONS_PER_PAGE}")
        self.initialize()
        parameters: list[object] = [after_sequence]
        where = "sequence > ?"
        if target is not None:
            where += " AND target_kind = ? AND target_id = ?"
            parameters.extend([target.kind.value, target.artifact_id])
            if target.artifact_fingerprint is None:
                where += " AND target_fingerprint IS NULL"
            else:
                where += " AND (target_fingerprint IS NULL OR target_fingerprint = ?)"
                parameters.append(target.artifact_fingerprint)
        parameters.append(limit + 1)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM analyst_annotations
                WHERE {where}
                ORDER BY sequence ASC
                LIMIT ?
                """,  # noqa: S608 - the clause is assembled only from fixed literals above.
                parameters,
            ).fetchall()
        has_more = len(rows) > limit
        selected = rows[:limit]
        return AnalystAnnotationHistory(
            target=target,
            after_sequence=after_sequence,
            limit=limit,
            annotations=[self._annotation_from_row(row) for row in selected],
            has_more=has_more,
        )

    def register_bundle_import(
        self,
        *,
        run: Run,
        bundle_id: str,
        source_reference: str,
        fingerprint: str,
        manifest_json: str,
        validation_report_json: str,
        import_status: str = "accepted",
    ) -> BundleImportResult:
        """Register a validated bundle idempotently."""

        self.initialize()
        now = utc_now().isoformat()
        with self._connect() as conn:
            existing_bundle = conn.execute(
                "SELECT bundle_id, run_id, fingerprint FROM bundle_imports WHERE bundle_id = ?",
                (bundle_id,),
            ).fetchone()
            if existing_bundle is not None:
                existing_fingerprint = cast(str, existing_bundle["fingerprint"])
                existing_run_id = cast(str, existing_bundle["run_id"])
                if existing_fingerprint == fingerprint and existing_run_id == run.run_id:
                    return BundleImportResult(
                        bundle_id=bundle_id,
                        run_id=run.run_id,
                        created=False,
                        idempotent=True,
                        status=import_status,
                        message="bundle already imported with identical fingerprint",
                    )
                msg = f"bundle_id already exists with different content: {bundle_id}"
                raise RegistryConflictError(msg)

            existing_run = conn.execute(
                "SELECT run_id FROM runs WHERE run_id = ?",
                (run.run_id,),
            ).fetchone()
            if existing_run is not None:
                msg = f"run_id already exists for a different bundle: {run.run_id}"
                raise RegistryConflictError(msg)

            conn.execute(
                """
                INSERT INTO runs (run_id, status, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.status.value,
                    run.model_dump_json(),
                    run.created_at.isoformat(),
                    run.updated_at.isoformat(),
                ),
            )
            conn.execute(
                """
                INSERT INTO bundle_imports (
                    bundle_id,
                    run_id,
                    source_reference,
                    fingerprint,
                    manifest_json,
                    validation_report_json,
                    imported_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bundle_id,
                    run.run_id,
                    source_reference,
                    fingerprint,
                    manifest_json,
                    validation_report_json,
                    now,
                ),
            )
        return BundleImportResult(
            bundle_id=bundle_id,
            run_id=run.run_id,
            created=True,
            idempotent=False,
            status=import_status,
            message="bundle imported",
        )

    def list_bundle_import_records(self) -> list[BundleImportRecord]:
        """List complete bundle-import records without changing registry state."""

        self.initialize()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT bundle_id, run_id, source_reference, fingerprint,
                       manifest_json, validation_report_json, imported_at
                FROM bundle_imports
                ORDER BY imported_at DESC, bundle_id
                """
            ).fetchall()
        return [
            BundleImportRecord(
                bundle_id=cast(str, row["bundle_id"]),
                run_id=cast(str, row["run_id"]),
                source_reference=cast(str, row["source_reference"]),
                fingerprint=cast(str, row["fingerprint"]),
                manifest_json=cast(str, row["manifest_json"]),
                validation_report_json=cast(str, row["validation_report_json"]),
                imported_at=cast(str, row["imported_at"]),
            )
            for row in rows
        ]

    def store_metric_collection(
        self,
        *,
        run_id: str,
        metric_version: str,
        source_fingerprint: str | None,
        payload_json: str,
    ) -> bool:
        """Store or refresh metric collection JSON for a run.

        Returns True when a new row is inserted and False when an existing row
        is refreshed.
        """

        self.initialize()
        now = utc_now().isoformat()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT run_id FROM metric_collections WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO metric_collections (
                        run_id,
                        metric_version,
                        source_fingerprint,
                        payload_json,
                        stored_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (run_id, metric_version, source_fingerprint, payload_json, now),
                )
                return True
            conn.execute(
                """
                UPDATE metric_collections
                SET metric_version = ?,
                    source_fingerprint = ?,
                    payload_json = ?,
                    stored_at = ?
                WHERE run_id = ?
                """,
                (metric_version, source_fingerprint, payload_json, now, run_id),
            )
            return False

    def get_metric_collection_json(self, run_id: str) -> str:
        """Retrieve metric collection JSON for a run."""

        self.initialize()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM metric_collections WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            msg = f"metric collection not found: {run_id}"
            raise RegistryNotFoundError(msg)
        return cast(str, row["payload_json"])

    def list_metric_collection_json(self) -> list[str]:
        """List stored metric collection JSON payloads."""

        self.initialize()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM metric_collections ORDER BY run_id"
            ).fetchall()
        return [cast(str, row["payload_json"]) for row in rows]

    def store_evidence_pack(
        self,
        *,
        pack_id: str,
        run_id: str,
        source_fingerprint: str | None,
        payload_json: str,
    ) -> bool:
        """Store or refresh an evidence pack JSON payload."""

        self.initialize()
        now = utc_now().isoformat()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT pack_id FROM evidence_packs WHERE pack_id = ?",
                (pack_id,),
            ).fetchone()
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO evidence_packs (
                        pack_id,
                        run_id,
                        source_fingerprint,
                        payload_json,
                        stored_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (pack_id, run_id, source_fingerprint, payload_json, now),
                )
                return True
            conn.execute(
                """
                UPDATE evidence_packs
                SET run_id = ?,
                    source_fingerprint = ?,
                    payload_json = ?,
                    stored_at = ?
                WHERE pack_id = ?
                """,
                (run_id, source_fingerprint, payload_json, now, pack_id),
            )
            return False

    def get_evidence_pack_json(self, pack_id: str) -> str:
        """Retrieve an evidence-pack JSON payload by pack identifier."""

        self.initialize()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM evidence_packs WHERE pack_id = ?",
                (pack_id,),
            ).fetchone()
        if row is None:
            msg = f"evidence pack not found: {pack_id}"
            raise RegistryNotFoundError(msg)
        return cast(str, row["payload_json"])

    def store_experiment_evidence_pack(
        self,
        *,
        pack_id: str,
        experiment_id: str,
        source_fingerprint: str | None,
        payload_json: str,
    ) -> bool:
        """Store or refresh one experiment-level EvidencePack JSON payload."""

        self.initialize()
        now = utc_now().isoformat()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT pack_id FROM experiment_evidence_packs WHERE pack_id = ?",
                (pack_id,),
            ).fetchone()
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO experiment_evidence_packs (
                        pack_id, experiment_id, source_fingerprint, payload_json, stored_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (pack_id, experiment_id, source_fingerprint, payload_json, now),
                )
                return True
            conn.execute(
                """
                UPDATE experiment_evidence_packs
                SET experiment_id = ?, source_fingerprint = ?, payload_json = ?, stored_at = ?
                WHERE pack_id = ?
                """,
                (experiment_id, source_fingerprint, payload_json, now, pack_id),
            )
            return False

    def get_experiment_evidence_pack_json(self, pack_id: str) -> str:
        """Retrieve experiment-level EvidencePack JSON by identifier."""

        self.initialize()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM experiment_evidence_packs WHERE pack_id = ?",
                (pack_id,),
            ).fetchone()
        if row is None:
            raise RegistryNotFoundError(f"experiment evidence pack not found: {pack_id}")
        return cast(str, row["payload_json"])

    def list_experiment_evidence_pack_json(self) -> list[str]:
        """List stored experiment-level EvidencePack JSON payloads."""

        self.initialize()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM experiment_evidence_packs ORDER BY pack_id"
            ).fetchall()
        return [cast(str, row["payload_json"]) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _annotation_from_row(row: sqlite3.Row) -> AnalystAnnotation:
        request = AnalystAnnotationRequest(
            target=AnalystArtifactReference(
                kind=cast(str, row["target_kind"]),
                artifact_id=cast(str, row["target_id"]),
                artifact_fingerprint=cast(str | None, row["target_fingerprint"]),
            ),
            author_label=cast(str, row["author_label"]),
            note=cast(str, row["note"]),
            decision_label=cast(str, row["decision_label"]),
        )
        return AnalystAnnotation(
            sequence=cast(int, row["sequence"]),
            annotation_id=cast(str, row["annotation_id"]),
            target=request.target,
            author_label=request.author_label,
            note=request.note,
            decision_label=request.decision_label,
            created_at=datetime.fromisoformat(cast(str, row["created_at"])),
        )

    @staticmethod
    def _ensure_annotation_target_exists(
        conn: sqlite3.Connection,
        target: AnalystArtifactReference,
    ) -> None:
        if target.kind not in REGISTRY_VERIFIED_ANNOTATION_TARGETS:
            return
        locations = {
            AnalystAnnotationTargetKind.EXPERIMENT: ("experiments", "experiment_id"),
            AnalystAnnotationTargetKind.RUN: ("runs", "run_id"),
            AnalystAnnotationTargetKind.BUNDLE_IMPORT: ("bundle_imports", "bundle_id"),
            AnalystAnnotationTargetKind.METRIC_COLLECTION: (
                "metric_collections",
                "run_id",
            ),
            AnalystAnnotationTargetKind.EVIDENCE_PACK: ("evidence_packs", "pack_id"),
            AnalystAnnotationTargetKind.EXPERIMENT_EVIDENCE_PACK: (
                "experiment_evidence_packs",
                "pack_id",
            ),
            AnalystAnnotationTargetKind.EXPERIMENT_PROTOCOL: (
                "experiment_protocols",
                "protocol_id",
            ),
        }
        table, identifier_column = locations[target.kind]
        row = conn.execute(
            f"SELECT 1 FROM {table} WHERE {identifier_column} = ?",  # noqa: S608
            (target.artifact_id,),
        ).fetchone()
        if row is None:
            raise RegistryNotFoundError(
                f"annotation target not found: {target.kind.value}:{target.artifact_id}"
            )

    def _insert(
        self,
        *,
        table: str,
        id_column: str,
        identifier: str,
        payload: str,
        created_at: str,
        updated_at: str,
        status: str | None = None,
    ) -> None:
        self.initialize()
        try:
            with self._connect() as conn:
                if status is None:
                    query = self._insert_query_without_status(table, id_column)
                    conn.execute(query, (identifier, payload, created_at, updated_at))
                else:
                    query = self._insert_query_with_status(table, id_column)
                    conn.execute(query, (identifier, status, payload, created_at, updated_at))
        except sqlite3.IntegrityError as exc:
            msg = f"{table} record already exists: {identifier}"
            raise DuplicateIdentifierError(msg) from exc

    def _get_payload(self, table: str, id_column: str, identifier: str) -> str:
        self.initialize()
        with self._connect() as conn:
            query = self._select_payload_query(table, id_column)
            row = conn.execute(
                query,
                (identifier,),
            ).fetchone()
        if row is None:
            msg = f"{table} record not found: {identifier}"
            raise RegistryNotFoundError(msg)
        return cast(str, row["payload"])

    def _list_payloads(self, table: str, id_column: str) -> list[str]:
        self.initialize()
        queries = {
            ("seeds", "seed_id"): "SELECT payload FROM seeds ORDER BY seed_id",
            ("experiments", "experiment_id"): (
                "SELECT payload FROM experiments ORDER BY experiment_id"
            ),
            ("runs", "run_id"): "SELECT payload FROM runs ORDER BY run_id",
        }
        with self._connect() as conn:
            rows = conn.execute(queries[(table, id_column)]).fetchall()
        return [cast(str, row["payload"]) for row in rows]

    def _update_status_payload(
        self,
        *,
        table: str,
        id_column: str,
        identifier: str,
        status: str,
        payload: str,
        updated_at: str,
    ) -> None:
        with self._connect() as conn:
            query = self._update_status_query(table, id_column)
            conn.execute(
                query,
                (status, payload, updated_at, identifier),
            )

    @staticmethod
    def _ensure_transition(
        current_status: ExperimentStatus | RunStatus,
        new_status: ExperimentStatus | RunStatus,
        allowed: dict[ExperimentStatus, set[ExperimentStatus]] | dict[RunStatus, set[RunStatus]],
    ) -> None:
        if current_status == new_status:
            return
        allowed_targets = allowed[current_status]  # type: ignore[index]
        if new_status not in allowed_targets:
            msg = f"invalid status transition: {current_status.value} -> {new_status.value}"
            raise InvalidStatusTransitionError(msg)

    @staticmethod
    def _count(conn: sqlite3.Connection, table: str) -> int:
        queries = {
            "seeds": "SELECT COUNT(*) AS count FROM seeds",
            "experiments": "SELECT COUNT(*) AS count FROM experiments",
            "runs": "SELECT COUNT(*) AS count FROM runs",
            "bundle_imports": "SELECT COUNT(*) AS count FROM bundle_imports",
            "metric_collections": "SELECT COUNT(*) AS count FROM metric_collections",
            "evidence_packs": "SELECT COUNT(*) AS count FROM evidence_packs",
            "experiment_evidence_packs": (
                "SELECT COUNT(*) AS count FROM experiment_evidence_packs"
            ),
            "experiment_protocols": "SELECT COUNT(*) AS count FROM experiment_protocols",
            "experiment_protocol_slots": (
                "SELECT COUNT(*) AS count FROM experiment_protocol_slots"
            ),
            "analyst_annotations": "SELECT COUNT(*) AS count FROM analyst_annotations",
        }
        row = conn.execute(queries[table]).fetchone()
        return cast(int, row["count"])

    @staticmethod
    def _insert_query_without_status(table: str, id_column: str) -> str:
        queries = {
            ("seeds", "seed_id"): """
                INSERT INTO seeds (seed_id, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            """,
        }
        return queries[(table, id_column)]

    @staticmethod
    def _insert_query_with_status(table: str, id_column: str) -> str:
        queries = {
            ("experiments", "experiment_id"): """
                INSERT INTO experiments (experiment_id, status, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """,
            ("runs", "run_id"): """
                INSERT INTO runs (run_id, status, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """,
        }
        return queries[(table, id_column)]

    @staticmethod
    def _select_payload_query(table: str, id_column: str) -> str:
        queries = {
            ("seeds", "seed_id"): "SELECT payload FROM seeds WHERE seed_id = ?",
            ("experiments", "experiment_id"): (
                "SELECT payload FROM experiments WHERE experiment_id = ?"
            ),
            ("runs", "run_id"): "SELECT payload FROM runs WHERE run_id = ?",
        }
        return queries[(table, id_column)]

    @staticmethod
    def _update_status_query(table: str, id_column: str) -> str:
        queries = {
            ("experiments", "experiment_id"): """
                UPDATE experiments
                SET status = ?, payload = ?, updated_at = ?
                WHERE experiment_id = ?
            """,
            ("runs", "run_id"): """
                UPDATE runs
                SET status = ?, payload = ?, updated_at = ?
                WHERE run_id = ?
            """,
        }
        return queries[(table, id_column)]
