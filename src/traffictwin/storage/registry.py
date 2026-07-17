"""SQLite metadata registry for Phase 1 TrafficTwin objects."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar, cast

from pydantic import BaseModel

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


@dataclass(frozen=True)
class RegistrySummary:
    """Simple registry inspection result."""

    path: Path
    seed_count: int
    experiment_count: int
    run_count: int


ModelT = TypeVar("ModelT", bound=BaseModel)

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
            )

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
