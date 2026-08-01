"""Experiment evidence matrix (post-v1 E-1): provenance and coverage, typed.

Implements ``docs/platform/experiment_evidence_matrix_design.md``: one typed
row per executed or proposed comparison, derived ONLY from a code-registered
extraction over committed records whose content digests are bound at build
time — hand-entered rows are structurally impossible. The matrix answers
"what has been run, on what, with which seeds, at what standing" and makes
gaps visible; it is a coverage index, never a meta-analysis, never an
admission authority, and it cannot change any row's standing.

The axes keep the project's hardest-won distinctions type-level:

- completion and admission are SEPARATE axes — the Sparse-64 bus/GPU returns
  completed 5/5 and remain ``non_admitted``, outside every admitted view;
- ``not_applicable`` / ``not_recorded`` / ``not_tested`` are distinct values,
  never interchangeable with zero;
- grouping requires a versioned compatibility rule and defaults to
  separation; mixed evidence roles refuse;
- the confirmed capacity comparison carries the exact five-seed sign-test
  floor (p = 0.0625) as a binding display note — it must never be summarised
  as conventionally significant.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

METHOD_VERSION: Literal["evidence-matrix-1.0"] = "evidence-matrix-1.0"
DESIGN_REFERENCE: Literal["docs/platform/experiment_evidence_matrix_design.md"] = (
    "docs/platform/experiment_evidence_matrix_design.md"
)
CITATION_REFERENCE = "docs/producer_citation_requirements.md"

NOT_APPLICABLE = "not_applicable"
NOT_RECORDED = "not_recorded"
NOT_TESTED = "not_tested"

RowStatus = Literal["proposed", "executed", "analysed", "admitted", "non_admitted", "refused"]
EvidenceRole = Literal[
    "protocol_confirmed", "post_hoc", "exploratory", "descriptive", "prediction", "diagnostic"
]

#: The exact five-held-out-seed limitation the design makes binding on display.
SIGN_TEST_FLOOR_NOTE = (
    "five paired held-out seeds impose an exact two-sided sign-test floor of "
    "p=0.0625; a unanimous direction is displayed only with that limitation and "
    "is never summarised as conventionally significant"
)

_PRIVATE_MARKERS = ("/Users/", "/home/", "\\Users\\")


class EvidenceMatrixError(RuntimeError):
    """Typed refusal; the matrix fails closed, never silently."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class MatrixModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


class SourceBinding(MatrixModel):
    """One committed record a row derives from, digest-bound at build."""

    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class EvidenceMatrixRow(MatrixModel):
    """One design-compatible comparison or explicitly declared single arm."""

    design_id: str
    design_fingerprint: str
    status: RowStatus
    evidence_role: EvidenceRole
    policy_ceiling: Literal["owner_approved_candidate"] = "owner_approved_candidate"
    trace_family: str
    locality: str
    actor_family: str
    fleet_preset: str
    capacity_arms: tuple[str, ...]
    demand_treatment: str
    tool_versions: str
    seed_set: tuple[int, ...] | Literal["not_recorded"]
    pairing_rule: str
    held_out_relationship: str
    execution_deviation: str | None
    primary_endpoint: str
    secondary_endpoints: tuple[str, ...]
    mechanism_diagnostics: tuple[str, ...]
    citation_bundle: str | None
    exclusion_reason: str | None
    significance_note: str | None
    sources: tuple[SourceBinding, ...] = Field(min_length=1)


@dataclass(frozen=True)
class RegisteredRow:
    """The code-registered extraction for one row: axes + source paths."""

    design_id: str
    design_fingerprint: str
    status: RowStatus
    evidence_role: EvidenceRole
    trace_family: str
    actor_family: str
    capacity_arms: tuple[str, ...]
    seed_set: tuple[int, ...] | Literal["not_recorded"]
    pairing_rule: str
    held_out_relationship: str
    primary_endpoint: str
    source_paths: tuple[str, ...]
    locality: str = "Etihad district, Manchester (inc trace family)"
    fleet_preset: str = "uk2030"
    demand_treatment: str = NOT_APPLICABLE
    tool_versions: str = "pinned evaluator v2_post_nrsus_fix; SUMO 1.27.1 toolchain"
    secondary_endpoints: tuple[str, ...] = ("task.latency.mean_ms", "task.offload.rate")
    mechanism_diagnostics: tuple[str, ...] = ()
    execution_deviation: str | None = None
    citation_bundle: str | None = CITATION_REFERENCE
    exclusion_reason: str | None = None
    significance_note: str | None = None


_TRAINED = "ukfleettrain_mappo (audited checkpoint model_c_17)"
_BASELINE = "baseline (audited checkpoint model_c_17 family)"
_DEADLINE = "tos.task.deadline_success.rate"
_CATALOGUE = "docs/evaluation/experiment_catalogue_20260730.md"
_REGISTER = "docs/experiments_and_findings_20260728.md"

#: Every row the matrix carries, bound to the committed records it derives
#: from. Adding a row means editing THIS table in a reviewed commit — there
#: is no other entrance, which is what forbids hand-entered rows.
REGISTERED_ROWS: tuple[RegisteredRow, ...] = (
    RegisteredRow(
        design_id="vec-capacity-squeeze-pilot",
        design_fingerprint="de474e038523e5e7",
        status="admitted",
        evidence_role="exploratory",
        trace_family="inc",
        actor_family=_TRAINED,
        capacity_arms=("cap-2.5", "cap-1.5", "cap-1.0", "cap-0.75"),
        seed_set=(0, 1, 2),
        pairing_rule="fleet_seed",
        held_out_relationship="pilot cohort; held-out {10-14} untouched",
        primary_endpoint=_DEADLINE,
        mechanism_diagnostics=("ceiling law", "bimodal offload partition", "failure Gini"),
        source_paths=(_CATALOGUE, "docs/evaluation/capacity_pilot_results_20260727.md"),
    ),
    RegisteredRow(
        design_id="vec-capacity-confirmatory",
        design_fingerprint="f289db31ce28b636",
        status="admitted",
        evidence_role="protocol_confirmed",
        trace_family="inc",
        actor_family=_TRAINED,
        capacity_arms=("cap-2.5", "cap-0.75"),
        seed_set=(10, 11, 12, 13, 14),
        pairing_rule="fleet_seed",
        held_out_relationship="held-out cohort {10-14}, SPENT by this study",
        primary_endpoint="task.latency.mean_ms (signed candidate b)",
        secondary_endpoints=(_DEADLINE, "task.offload.rate"),
        significance_note=SIGN_TEST_FLOOR_NOTE,
        source_paths=(_CATALOGUE, "docs/evaluation/capacity_confirmatory_results_20260728.md"),
    ),
    RegisteredRow(
        design_id="vec-capacity-grid-we",
        design_fingerprint="b4da3a5ba9b4dd10",
        status="admitted",
        evidence_role="exploratory",
        trace_family="we",
        actor_family=_TRAINED,
        capacity_arms=("cap-2.5", "cap-1.5", "cap-1.0", "cap-0.75"),
        seed_set=(50, 51, 52),
        pairing_rule="fleet_seed",
        held_out_relationship="fresh seeds; held-out untouched",
        primary_endpoint=_DEADLINE,
        source_paths=(_CATALOGUE, "docs/evaluation/capacity_grid_results_20260728.md"),
    ),
    RegisteredRow(
        design_id="vec-capacity-grid-ev",
        design_fingerprint="efa83a78c8518861",
        status="admitted",
        evidence_role="exploratory",
        trace_family="ev",
        actor_family=_TRAINED,
        capacity_arms=("cap-2.5", "cap-1.5", "cap-1.0", "cap-0.75"),
        seed_set=(50, 51, 52),
        pairing_rule="fleet_seed",
        held_out_relationship="fresh seeds; held-out untouched",
        primary_endpoint=_DEADLINE,
        source_paths=(_CATALOGUE, "docs/evaluation/capacity_grid_results_20260728.md"),
    ),
    RegisteredRow(
        design_id="vec-capacity-sweep-wd-am",
        design_fingerprint="2844fde2c38ec226",
        status="admitted",
        evidence_role="exploratory",
        trace_family="wd_am",
        actor_family=_TRAINED,
        capacity_arms=("cap-2.5", "cap-1.5", "cap-1.0", "cap-0.75"),
        seed_set=(50, 51, 52),
        pairing_rule="fleet_seed",
        held_out_relationship="fresh seeds; held-out untouched",
        primary_endpoint=_DEADLINE,
        source_paths=(_CATALOGUE, "docs/evaluation/capacity_sweep_completion_results_20260728.md"),
    ),
    RegisteredRow(
        design_id="vec-capacity-sweep-wd-pm",
        design_fingerprint="635a2cbefd94b757",
        status="admitted",
        evidence_role="exploratory",
        trace_family="wd_pm",
        actor_family=_TRAINED,
        capacity_arms=("cap-2.5", "cap-1.5", "cap-1.0", "cap-0.75"),
        seed_set=(50, 51, 52),
        pairing_rule="fleet_seed",
        held_out_relationship="fresh seeds; held-out untouched",
        primary_endpoint=_DEADLINE,
        source_paths=(_CATALOGUE, "docs/evaluation/capacity_sweep_completion_results_20260728.md"),
    ),
    RegisteredRow(
        design_id="vec-capacity-deep-ev",
        design_fingerprint="727745441c5e43c1",
        status="admitted",
        evidence_role="exploratory",
        trace_family="ev",
        actor_family=_TRAINED,
        capacity_arms=("cap-2.5", "cap-0.5", "cap-0.25", "cap-0.1"),
        seed_set=(50, 51, 52),
        pairing_rule="fleet_seed",
        held_out_relationship="fresh seeds; held-out untouched",
        primary_endpoint=_DEADLINE,
        mechanism_diagnostics=("onset location",),
        source_paths=(_CATALOGUE, "docs/evaluation/capacity_sweep_completion_results_20260728.md"),
    ),
    RegisteredRow(
        design_id="vec-capacity-deep-inc",
        design_fingerprint="5331e5207ef2eae2",
        status="admitted",
        evidence_role="protocol_confirmed",
        trace_family="inc",
        actor_family=_TRAINED,
        capacity_arms=("cap-2.5", "cap-0.5", "cap-0.25", "cap-0.1"),
        seed_set=(60, 61, 62),
        pairing_rule="fleet_seed",
        held_out_relationship="fresh seeds; pre-registered ceiling-law prediction test",
        primary_endpoint="p95-of-missed ceiling (predeclared, HELD 27/27)",
        mechanism_diagnostics=("ceiling law verdict", "sag trend"),
        source_paths=(_CATALOGUE, "docs/evaluation/ceiling_law_prediction_results_20260729.md"),
    ),
    RegisteredRow(
        design_id="vec-capacity-deep-we",
        design_fingerprint="0759b31f4cae4afb",
        status="analysed",
        evidence_role="post_hoc",
        trace_family="we",
        actor_family=_TRAINED,
        capacity_arms=("cap-2.5", "cap-0.5", "cap-0.25", "cap-0.1"),
        seed_set=(60, 61, 62),
        pairing_rule="fleet_seed",
        held_out_relationship="fresh seeds; onset-scaling prediction REFUTED 4/6",
        primary_endpoint="exact-identity onset check (predeclared)",
        source_paths=(_CATALOGUE, "docs/evaluation/onset_scaling_prediction_results_20260730.md"),
    ),
    RegisteredRow(
        design_id="vec-baseline-invariance-ev",
        design_fingerprint="2f4e371b7769fde3",
        status="admitted",
        evidence_role="exploratory",
        trace_family="ev",
        actor_family=_BASELINE,
        capacity_arms=("cap-2.5", "cap-1.5", "cap-1.0", "cap-0.75"),
        seed_set=(50, 51, 52),
        pairing_rule="fleet_seed",
        held_out_relationship="fresh seeds; B0 prediction HELD",
        primary_endpoint=_DEADLINE,
        source_paths=(_CATALOGUE, "docs/evaluation/baseline_invariance_results_20260728.md"),
    ),
    RegisteredRow(
        design_id="vec-crossover-inc-baseline",
        design_fingerprint="4784f5fc30558310",
        status="admitted",
        evidence_role="exploratory",
        trace_family="inc",
        actor_family=_BASELINE,
        capacity_arms=("cap-2.5", "cap-1.5", "cap-1.0", "cap-0.75"),
        seed_set=(0, 1, 2),
        pairing_rule="fleet_seed",
        held_out_relationship="fresh execution; NO crossover (+6.09 pp margin, all arms)",
        primary_endpoint=_DEADLINE,
        mechanism_diagnostics=("latency slope contrast (prediction 3 REFUTED)",),
        source_paths=(_CATALOGUE, "docs/evaluation/actor_crossover_results_20260730.md"),
    ),
    RegisteredRow(
        design_id="bbus-sparse64-homecoming",
        design_fingerprint=NOT_RECORDED,
        status="non_admitted",
        evidence_role="diagnostic",
        trace_family="derived bus (Sparse-64)",
        locality="Greater Manchester BODS-derived",
        actor_family="GPU-track training returns",
        capacity_arms=("cap-2.5", "cap-0.75"),
        seed_set="not_recorded",
        pairing_rule=NOT_APPLICABLE,
        held_out_relationship=NOT_APPLICABLE,
        execution_deviation=(
            "launchd relaunch repeated the fixed peak evaluation 147x and overwrote "
            "archives; peak-once rule failed (first return)"
        ),
        primary_endpoint="peak completion (diagnostic only)",
        secondary_endpoints=(),
        exclusion_reason="NON_ADMITTED by its own evidence record; outside the admitted VEC chain",
        source_paths=("docs/evaluation/bbus_sparse64_homecoming_results_20260730.md",),
        citation_bundle=None,
    ),
    RegisteredRow(
        design_id="bbus-sparse64-clean-rerun",
        design_fingerprint=NOT_RECORDED,
        status="non_admitted",
        evidence_role="diagnostic",
        trace_family="derived bus (Sparse-64)",
        locality="Greater Manchester BODS-derived",
        actor_family="GPU-track training returns",
        capacity_arms=("cap-2.5", "cap-0.75"),
        seed_set="not_recorded",
        pairing_rule=NOT_APPLICABLE,
        held_out_relationship=NOT_APPLICABLE,
        execution_deviation=(
            "one repeat evaluation: the terminal record was written after a fallible "
            "cleanup step a relaunch could interrupt (second return); 5/5 compute completed"
        ),
        primary_endpoint="peak completion (diagnostic only)",
        secondary_endpoints=(),
        exclusion_reason="NON_ADMITTED by its own evidence record; completion is not admission",
        source_paths=("docs/evaluation/bbus_sparse64_clean_rerun_results_20260730.md",),
        citation_bundle=None,
    ),
    RegisteredRow(
        design_id="vec-fleet-composition-prediction",
        design_fingerprint=NOT_RECORDED,
        status="proposed",
        evidence_role="prediction",
        trace_family="inc",
        actor_family=_TRAINED,
        capacity_arms=("cap-2.5",),
        seed_set="not_recorded",
        pairing_rule="fleet_seed (proposed)",
        held_out_relationship="fresh seeds proposed; owner launch decision pending",
        primary_endpoint=f"{_DEADLINE} (predicted 0.65±0.03 at tier-0 share 0.70)",
        exclusion_reason=None,
        source_paths=(_REGISTER,),
        significance_note="proposed only; evidence: false until executed and admitted",
    ),
)


class EvidenceMatrix(MatrixModel):
    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["evidence-matrix-1.0"] = METHOD_VERSION
    design_reference: Literal["docs/platform/experiment_evidence_matrix_design.md"] = (
        DESIGN_REFERENCE
    )
    research_status: Literal["owner_approved_candidate"] = "owner_approved_candidate"
    evidence: Literal[False] = False
    rows: tuple[EvidenceMatrixRow, ...]
    build_digest: str


class CompatibilityRule(MatrixModel):
    """A versioned statement that a grouping is legitimate; default is separation."""

    rule_id: str
    version: str
    allows_roles: tuple[EvidenceRole, ...]
    allows_statuses: tuple[RowStatus, ...]
    rationale: str


class MatrixSelection(MatrixModel):
    row_ids: tuple[str, ...]
    rows: tuple[EvidenceMatrixRow, ...]
    build_digest: str
    includes_non_admitted: bool


class CoverageSummary(MatrixModel):
    row_count: int
    row_ids: tuple[str, ...]
    build_digest: str
    unique_traces: tuple[str, ...]
    unique_actor_families: tuple[str, ...]
    unique_capacity_arms: tuple[str, ...]
    unique_seeds: tuple[int, ...]
    statuses: dict[str, int]
    evidence_roles: dict[str, int]
    significance_notes: tuple[str, ...]


def build_evidence_matrix(repo_root: Path) -> EvidenceMatrix:
    """Bind every registered row to its committed sources, digests included."""

    rows: list[EvidenceMatrixRow] = []
    seen_ids: set[str] = set()
    digest_material: list[str] = []
    for registered in REGISTERED_ROWS:
        if registered.design_id in seen_ids:
            raise EvidenceMatrixError(
                "DESIGN_ID_COLLISION", f"design id '{registered.design_id}' appears twice"
            )
        seen_ids.add(registered.design_id)
        bindings: list[SourceBinding] = []
        for source_path in registered.source_paths:
            for marker in _PRIVATE_MARKERS:
                if marker in source_path:
                    raise EvidenceMatrixError(
                        "PRIVATE_CONTENT_DETECTED",
                        f"row '{registered.design_id}' names a private path",
                    )
            absolute = repo_root / source_path
            if not absolute.is_file():
                raise EvidenceMatrixError(
                    "SOURCE_RECORD_MISSING",
                    f"row '{registered.design_id}' derives from missing record '{source_path}'",
                )
            digest = hashlib.sha256(absolute.read_bytes()).hexdigest()
            bindings.append(SourceBinding(path=source_path, sha256=digest))
            digest_material.append(f"{registered.design_id}:{source_path}:{digest}")
        if (
            registered.citation_bundle is None
            and registered.status in ("admitted", "analysed")
            and not registered.design_id.startswith("bbus-")
        ):
            raise EvidenceMatrixError(
                "CITATION_BUNDLE_MISSING",
                f"admitted row '{registered.design_id}' carries no citation bundle",
            )
        rows.append(
            EvidenceMatrixRow(
                design_id=registered.design_id,
                design_fingerprint=registered.design_fingerprint,
                status=registered.status,
                evidence_role=registered.evidence_role,
                trace_family=registered.trace_family,
                locality=registered.locality,
                actor_family=registered.actor_family,
                fleet_preset=registered.fleet_preset,
                capacity_arms=registered.capacity_arms,
                demand_treatment=registered.demand_treatment,
                tool_versions=registered.tool_versions,
                seed_set=registered.seed_set,
                pairing_rule=registered.pairing_rule,
                held_out_relationship=registered.held_out_relationship,
                execution_deviation=registered.execution_deviation,
                primary_endpoint=registered.primary_endpoint,
                secondary_endpoints=registered.secondary_endpoints,
                mechanism_diagnostics=registered.mechanism_diagnostics,
                citation_bundle=registered.citation_bundle,
                exclusion_reason=registered.exclusion_reason,
                significance_note=registered.significance_note,
                sources=tuple(bindings),
            )
        )
    build_digest = hashlib.sha256("\n".join(sorted(digest_material)).encode()).hexdigest()
    return EvidenceMatrix(rows=tuple(rows), build_digest=build_digest)


def filter_rows(
    matrix: EvidenceMatrix,
    *,
    trace_family: str | None = None,
    actor_family: str | None = None,
    status: RowStatus | None = None,
    evidence_role: EvidenceRole | None = None,
    include_non_admitted: bool = False,
) -> MatrixSelection:
    """Select rows without ever altering their standing.

    Non-admitted rows are excluded by default and join a selection only on
    the explicit flag — and never by asking for ``status='admitted'``.
    """

    if status == "admitted" and include_non_admitted:
        raise EvidenceMatrixError(
            "NON_ADMITTED_PROMOTION",
            "a selection cannot request admitted standing and include non-admitted "
            "rows at once; completion is not admission",
        )
    selected: list[EvidenceMatrixRow] = []
    for row in matrix.rows:
        if row.status == "non_admitted" and not include_non_admitted:
            continue
        if trace_family is not None and row.trace_family != trace_family:
            continue
        if actor_family is not None and row.actor_family != actor_family:
            continue
        if status is not None and row.status != status:
            continue
        if evidence_role is not None and row.evidence_role != evidence_role:
            continue
        selected.append(row)
    return MatrixSelection(
        row_ids=tuple(row.design_id for row in selected),
        rows=tuple(selected),
        build_digest=matrix.build_digest,
        includes_non_admitted=include_non_admitted,
    )


def group_rows(
    selection: MatrixSelection, rule: CompatibilityRule | None = None
) -> tuple[EvidenceMatrixRow, ...]:
    """Group only under a versioned compatibility rule; default is separation."""

    roles = {row.evidence_role for row in selection.rows}
    statuses = {row.status for row in selection.rows}
    if rule is None:
        if len(roles) > 1:
            raise EvidenceMatrixError(
                "EVIDENCE_ROLE_MIXED",
                f"the selection mixes evidence roles {sorted(roles)} and no "
                "compatibility rule was given; default behaviour is separation",
            )
        if len(statuses) > 1:
            raise EvidenceMatrixError(
                "INCOMPATIBLE_GROUPING",
                f"the selection mixes statuses {sorted(statuses)} and no "
                "compatibility rule was given",
            )
        return selection.rows
    missing_roles = roles - set(rule.allows_roles)
    missing_statuses = statuses - set(rule.allows_statuses)
    if missing_roles or missing_statuses:
        raise EvidenceMatrixError(
            "INCOMPATIBLE_GROUPING",
            f"rule '{rule.rule_id}@{rule.version}' does not license roles "
            f"{sorted(missing_roles)} / statuses {sorted(missing_statuses)}",
        )
    return selection.rows


def summarise_coverage(selection: MatrixSelection) -> CoverageSummary:
    """Deterministic counts only — never a pooled effect estimate."""

    seeds: set[int] = set()
    for row in selection.rows:
        if isinstance(row.seed_set, tuple):
            seeds.update(row.seed_set)
    statuses: dict[str, int] = {}
    roles: dict[str, int] = {}
    for row in selection.rows:
        statuses[row.status] = statuses.get(row.status, 0) + 1
        roles[row.evidence_role] = roles.get(row.evidence_role, 0) + 1
    return CoverageSummary(
        row_count=len(selection.rows),
        row_ids=selection.row_ids,
        build_digest=selection.build_digest,
        unique_traces=tuple(sorted({row.trace_family for row in selection.rows})),
        unique_actor_families=tuple(sorted({row.actor_family for row in selection.rows})),
        unique_capacity_arms=tuple(
            sorted({arm for row in selection.rows for arm in row.capacity_arms})
        ),
        unique_seeds=tuple(sorted(seeds)),
        statuses=statuses,
        evidence_roles=roles,
        significance_notes=tuple(
            sorted({row.significance_note for row in selection.rows if row.significance_note})
        ),
    )


def explain_cell(matrix: EvidenceMatrix, *, trace_family: str, actor_family: str) -> str:
    """Why a cell is empty or thin — not run, non-admitted, or covered."""

    covered = [
        row
        for row in matrix.rows
        if row.trace_family == trace_family and row.actor_family == actor_family
    ]
    if not covered:
        return (
            f"({trace_family} x {actor_family}): {NOT_TESTED} — no registered row "
            "covers this cell; absence of a row is a coverage gap, not a zero"
        )
    admitted = [row for row in covered if row.status == "admitted"]
    non_admitted = [row for row in covered if row.status == "non_admitted"]
    parts = [f"({trace_family} x {actor_family}): {len(covered)} row(s)"]
    if admitted:
        parts.append(f"{len(admitted)} admitted ({', '.join(row.design_id for row in admitted)})")
    if non_admitted:
        parts.append(
            f"{len(non_admitted)} non-admitted, excluded from admitted views "
            f"({', '.join(row.design_id for row in non_admitted)})"
        )
    proposed = [row for row in covered if row.status == "proposed"]
    if proposed:
        parts.append(f"{len(proposed)} proposed (evidence: false until admitted)")
    return "; ".join(parts)


def matrix_to_json(matrix: EvidenceMatrix) -> str:
    return json.dumps(matrix.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False)


def registered_row_ids() -> tuple[str, ...]:
    return tuple(row.design_id for row in REGISTERED_ROWS)
