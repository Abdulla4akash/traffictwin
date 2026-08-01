"""Read-only services for the platform dashboard pages (P-3, Phase 145).

The page-independent halves of the Data Inventory, Forecasts, and What-If
Composer screens. Everything here is an allowlisted schema reader: it loads
only the named artifact kinds the dashboard design enumerates, computes no
new measurement, performs no acquisition, opens no raw quarantine byte, and
writes nothing anywhere.

Redaction is a service-boundary rule, not page politeness: no absolute or
private path, credential, salt, or raw identifier leaves this module —
display names are workspace-relative, and a screen function that would emit
an absolute path raises instead.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from traffictwin.platform.bus_prediction import (
    BuildRules,
    BusPredictionError,
    LoadedAggregate,
    load_activity_aggregates,
    readiness_report,
)

#: The committed schedule the freshness view reconciles against.
SCHEDULE_RELATIVE_PATH = Path("docs") / "platform" / "bods_schedule.json"
#: The committed outcome-predictor fit artifact the composer consumes.
FIT_ARTIFACT_RELATIVE_PATH = Path("docs") / "platform" / "outcome_predictor_fit.json"
#: Committed publication-safe records of private GPU diagnostic archives.
PRESERVATION_RECORDS_RELATIVE_DIR = Path("docs") / "integration" / "evidence"

_SCHEDULED_RELATIVE = Path("manchester") / "scheduled"
_AGGREGATES_RELATIVE = Path("manchester") / "aggregates"
_PRIVATE_MARKERS = ("/Users/", "/home/", "\\Users\\")

_GPU_STANDING = (
    "private diagnostic archive; its metrics never enter forecasts, prediction "
    "comparisons, or evidence headlines"
)


class PlatformServiceError(RuntimeError):
    """Typed service refusal; the dashboard fails closed, never silently."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _display_safe(text: str) -> str:
    """Refuse rather than emit an absolute/private path to a page."""

    for marker in _PRIVATE_MARKERS:
        if marker in text:
            raise PlatformServiceError(
                "PRIVATE_PATH_REFUSED",
                "a display value contained a private absolute path and was refused "
                "at the service boundary",
            )
    return text


@dataclass(frozen=True)
class InventoryRow:
    """One dataset row: everything the design's inventory table shows."""

    dataset: str
    source: str
    acquisition_mode: str
    count_label: str
    last_updated: str
    digest_prefix: str
    freshness: str
    standing: str
    deviation: str | None = None


@dataclass(frozen=True)
class FreshnessGap:
    """One reconciled schedule gap: a recorded skip or an inferred absence."""

    session_date: str
    window: str
    kind: str  # "recorded_skip" | "inferred_absence"
    detail: str


@dataclass(frozen=True)
class PlatformInventory:
    rows: tuple[InventoryRow, ...]
    gaps: tuple[FreshnessGap, ...]
    retention_note: str | None
    workspace_note: str
    unreadable_artifacts: int = 0


def _read_json(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _sha_prefix(path: Path) -> str:
    import hashlib

    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    except OSError:
        return "unreadable"


def load_platform_inventory(
    workspace_path: Path | None,
    repo_root: Path,
    *,
    today: date,
) -> PlatformInventory:
    """Build the honest inventory over the allowlisted artifact kinds."""

    rows: list[InventoryRow] = []
    gaps: list[FreshnessGap] = []
    unreadable = 0
    retention_note: str | None = None

    if workspace_path is None or not workspace_path.is_dir():
        workspace_note = (
            "No workspace is configured or present; the inventory below lists only "
            "committed repository records. Absence is shown as absence."
        )
    else:
        workspace_note = "Reading allowlisted records from the configured workspace."
        scheduled_root = workspace_path / _SCHEDULED_RELATIVE
        if scheduled_root.is_dir():
            for marker_path in sorted(scheduled_root.glob("*/*/completed.json")):
                marker = _read_json(marker_path)
                if marker is None:
                    unreadable += 1
                    continue
                label = str(marker.get("label", marker_path.parent.name))
                session_date = str(marker.get("session_date", ""))
                accepted = marker.get("snapshots_accepted", "?")
                refused = marker.get("snapshots_refused", 0)
                deviation = (
                    f"{refused} refusal(s) ledgered"
                    if isinstance(refused, int) and refused
                    else None
                )
                rows.append(
                    InventoryRow(
                        dataset=_display_safe(f"scheduled session {session_date}/{label}"),
                        source="BODS SIRI-VM (GM box)",
                        acquisition_mode="scheduled",
                        count_label=f"{accepted} accepted snapshot(s)",
                        last_updated=str(marker.get("finished_at_utc", "")),
                        digest_prefix=_sha_prefix(marker_path),
                        freshness="captured",
                        standing="aggregate-only session record; owner_approved_candidate",
                        deviation=deviation,
                    )
                )
            for skip_path in sorted(scheduled_root.glob("*/*/skipped.json")):
                skip = _read_json(skip_path)
                if skip is None:
                    unreadable += 1
                    continue
                gaps.append(
                    FreshnessGap(
                        session_date=str(skip.get("session_date", "")),
                        window=str(skip.get("label", skip_path.parent.name)),
                        kind="recorded_skip",
                        detail=str(skip.get("reason", "skipped")),
                    )
                )
            retention = _read_json(scheduled_root / "retention_report.json")
            if retention is not None:
                count = retention.get("eligible_snapshot_count", 0)
                retention_note = (
                    f"{count} scheduled snapshot(s) are prune-eligible; deletion is "
                    "owner-confirmed and never automatic, so owner action is pending. "
                    "Nothing has been deleted."
                )
        for aggregate_path in sorted(
            [
                *scheduled_root.glob("*/*/activity_aggregate.json"),
                *(workspace_path / _AGGREGATES_RELATIVE).glob("*.json"),
            ]
            if scheduled_root.is_dir() or (workspace_path / _AGGREGATES_RELATIVE).is_dir()
            else []
        ):
            payload = _read_json(aggregate_path)
            if payload is None or payload.get("record_type") != "bods_session_activity_aggregate":
                continue
            rows.append(
                InventoryRow(
                    dataset=_display_safe(
                        f"activity aggregate {payload.get('session_date_local', '')}/"
                        f"{payload.get('label', '')}"
                    ),
                    source="BODS SIRI-VM (GM box)",
                    acquisition_mode=str(payload.get("session_kind", "unknown")),
                    count_label=f"{payload.get('snapshot_count', '?')} snapshot(s)",
                    last_updated=str(payload.get("session_date_local", "")),
                    digest_prefix=_sha_prefix(aggregate_path),
                    freshness="captured",
                    standing="aggregate-only; salts discarded; raw identifiers never published",
                    deviation=(
                        None
                        if payload.get("progression_available")
                        else "no progression rows (cadence-era or no linked movement)"
                    ),
                )
            )
        _reconcile_schedule_gaps(workspace_path, repo_root, today, gaps)

    preservation_dir = repo_root / PRESERVATION_RECORDS_RELATIVE_DIR
    if preservation_dir.is_dir():
        for record_path in sorted(preservation_dir.glob("*preservation*.json")):
            record = _read_json(record_path)
            if record is None:
                unreadable += 1
                continue
            raw_text = record_path.read_text(encoding="utf-8", errors="replace")
            status = "NON_ADMITTED" if "NON_ADMITTED" in raw_text else "private diagnostic"
            rows.append(
                InventoryRow(
                    dataset=_display_safe(str(record.get("record", record_path.stem))),
                    source="GPU-track archive (committed preservation record only)",
                    acquisition_mode="archive",
                    count_label="publication-safe record",
                    last_updated=str(record.get("recorded_at_utc", "")),
                    digest_prefix=_sha_prefix(record_path),
                    freshness="archived",
                    standing=f"{status} — {_GPU_STANDING}",
                    deviation="execution-deviated" if "deviat" in raw_text.lower() else None,
                )
            )

    return PlatformInventory(
        rows=tuple(rows),
        gaps=tuple(gaps),
        retention_note=retention_note,
        workspace_note=workspace_note,
        unreadable_artifacts=unreadable,
    )


def _reconcile_schedule_gaps(
    workspace_path: Path,
    repo_root: Path,
    today: date,
    gaps: list[FreshnessGap],
) -> None:
    """Infer older missing windows as absences, never as recorded skips."""

    schedule = _read_json(repo_root / SCHEDULE_RELATIVE_PATH)
    if schedule is None:
        return
    sessions = schedule.get("sessions")
    if not isinstance(sessions, list):
        return
    scheduled_root = workspace_path / _SCHEDULED_RELATIVE
    for offset in (1, 2):
        day = today - timedelta(days=offset)
        for window in sessions:
            if not isinstance(window, dict):
                continue
            label = str(window.get("label", ""))
            directory = scheduled_root / day.isoformat() / label
            if (directory / "completed.json").exists() or (directory / "skipped.json").exists():
                continue
            gaps.append(
                FreshnessGap(
                    session_date=day.isoformat(),
                    window=label,
                    kind="inferred_absence",
                    detail=(
                        "no completion or skip record exists; inferred as an absence "
                        "(supervisor not running or machine asleep), not a recorded skip"
                    ),
                )
            )


# --- forecasts ---------------------------------------------------------------


@dataclass(frozen=True)
class ForecastContext:
    """Everything the Forecasts page renders, honest about its own gaps."""

    aggregates: tuple[LoadedAggregate, ...] = ()
    readiness: dict[str, object] = field(default_factory=dict)
    load_refusal: str | None = None
    source_count: int = 0


def load_forecast_context(workspace_path: Path | None) -> ForecastContext:
    """Load whatever eligible aggregates exist; absence is the normal state."""

    if workspace_path is None or not workspace_path.is_dir():
        return ForecastContext(
            load_refusal=("no workspace is configured or present; no aggregate sources exist yet")
        )
    candidates: list[Path] = []
    scheduled_root = workspace_path / _SCHEDULED_RELATIVE
    if scheduled_root.is_dir():
        candidates.extend(sorted(scheduled_root.glob("*/*/activity_aggregate.json")))
    aggregates_dir = workspace_path / _AGGREGATES_RELATIVE
    if aggregates_dir.is_dir():
        candidates.extend(sorted(aggregates_dir.glob("*.json")))
    if not candidates:
        return ForecastContext(
            load_refusal=(
                "no activity aggregates exist in this workspace yet; scheduled "
                "sessions write them at capture time and the owner script builds "
                "them post-hoc for attended sessions"
            )
        )
    try:
        loaded = load_activity_aggregates(candidates)
    except BusPredictionError as error:
        return ForecastContext(load_refusal=str(error))
    rules = BuildRules()
    return ForecastContext(
        aggregates=loaded,
        readiness=readiness_report(loaded, rules),
        source_count=len(loaded),
    )
