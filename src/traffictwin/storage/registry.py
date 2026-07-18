"""SQLite metadata registry for Phase 1 TrafficTwin objects."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from traffictwin.domain.enums import ExperimentStatus, RunStatus
from traffictwin.domain.experiment import Experiment, utc_now
from traffictwin.domain.run import Run
from traffictwin.domain.scenario import ScenarioSeed


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
    seed_count: int
    experiment_count: int
    run_count: int
    bundle_import_count: int
    metric_collection_count: int = 0
    evidence_pack_count: int = 0


@dataclass(frozen=True)
class BundleImportResult:
    """Result of registering a validated bundle."""

    bundle_id: str | None
    run_id: str | None
    created: bool
    idempotent: bool
    status: str
    message: str


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

    def initialize(self) -> None:
        """Create registry tables if they do not already exist."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS seeds (
                    seed_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS experiments (
                    experiment_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS bundle_imports (
                    bundle_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    source_reference TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    validation_report_json TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    UNIQUE(run_id),
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                );

                CREATE TABLE IF NOT EXISTS metric_collections (
                    run_id TEXT PRIMARY KEY,
                    metric_version TEXT NOT NULL,
                    source_fingerprint TEXT,
                    payload_json TEXT NOT NULL,
                    stored_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                );

                CREATE TABLE IF NOT EXISTS evidence_packs (
                    pack_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    source_fingerprint TEXT,
                    payload_json TEXT NOT NULL,
                    stored_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                );
                """
            )

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

        with self._connect() as conn:
            return RegistrySummary(
                path=self.path,
                seed_count=self._count(conn, "seeds"),
                experiment_count=self._count(conn, "experiments"),
                run_count=self._count(conn, "runs"),
                bundle_import_count=self._count(conn, "bundle_imports"),
                metric_collection_count=self._count(conn, "metric_collections"),
                evidence_pack_count=self._count(conn, "evidence_packs"),
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

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

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
