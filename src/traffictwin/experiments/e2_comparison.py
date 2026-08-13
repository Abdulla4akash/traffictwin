"""Matched-draw uncertainty service for E2b / E2c / E2d.

Strict typed view built directly from the admitted
``E2ResearchEvidencePackage``.  No optional package, no ``Any``,
no guessed shapes, and no silent fallback to hard-coded constants.
Any inconsistent, missing, or drifted study, draw, mean, CI,
identity, seed, or replication value fails closed with an exception.

Values are read from the package's exact observations,
paired-difference sets, and declared summaries.
Means are deterministically reconciled to per-draw values using the
model's strict tolerance, but source-declared CIs and method are
preserved without substitution.  E2b remains one-draw descriptive with
no interval.  No p-values and no task-level N are produced.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.experiments.e2_research_evidence import (
    MEAN_RECONCILIATION_TOL,
    SD_RECONCILIATION_TOL,
    SE_RECONCILIATION_TOL,
    E2ResearchEvidencePackage,
)

# ---------------------------------------------------------------------------
# Committed constants — pinned to
# docs/closure/v08_alignment/improved_strategy_results.json
# ---------------------------------------------------------------------------

ACTOR_SHA256: str = "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208"
TRACE_SHA256: str = "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"

E2B_MANIFEST_SHA256: str = "9383ec767dccf2f390b498e0c20283a74cd64fa521d6137fe23ce38d0022af91"
E2B_CODE_COMMIT: str = "fe2ed4e9bd9043b19b96a5f179390db629b01ccb"
E2C_MANIFEST_SHA256: str = "fcaf2ee34b68ca4e4ef2e088d72ce2c5a410cf66ff9934a451fd8047204c480a"
E2C_CODE_COMMIT: str = "1a08d6e148a1e8c430da39c3d575eda3f8ea5929"
E2D_MANIFEST_SHA256: str = "f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740"
E2D_CODE_COMMIT: str = "80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761"

# E2b offered_task_deadline_attainment, one draw, fleet seed 0, evaluator 0
E2B_OFF: float = 0.683619229
E2B_JSQ: float = 0.675681775
E2B_INGRESS_DLA: float = 0.715773211
E2B_DLA: float = 0.694939919

# E2c dla - ingress_dla, fleet seeds 1-4, paired
E2C_PER_SEED: tuple[float, ...] = (
    -0.022097034972,
    -0.020519134179,
    -0.021447383092,
    -0.020825491499,
)
E2C_MEAN: float = -0.021222260935
E2C_SAMPLE_SD: float = 0.000699457605
E2C_STANDARD_ERROR: float = 0.000349728802
E2C_DF: Literal[3] = 3
E2C_METHOD: str = "two-sided Student-t 95% interval over fleet-draw differences"
E2C_CRITICAL: float = 3.182446305284263
E2C_LOWER: float = -0.02233525407
E2C_UPPER: float = -0.0201092678

# E2d per_task_dla - ingress_dla, fleet seeds 1-4, paired
E2D_PER_SEED: tuple[float, ...] = (
    0.004636732564,
    0.005867285642,
    0.005071796666,
    0.005509919752,
)
E2D_MEAN: float = 0.005271433656
E2D_SAMPLE_SD: float = 0.000533733895
E2D_STANDARD_ERROR: float = 0.000266866947
E2D_DF: Literal[3] = 3
E2D_METHOD: str = "two-sided Student-t 95% interval over fleet-draw differences"
E2D_CRITICAL: float = 3.182446305284263
E2D_LOWER: float = 0.004422143925
E2D_UPPER: float = 0.006120723387

# E2d per_task_dla - dla (inherited common-target), fleet seeds 1-4
E2D_VS_DLA_PER_SEED: tuple[float, ...] = (
    0.026733767536,
    0.026386419821,
    0.026519179758,
    0.026335411251,
)
E2D_VS_DLA_MEAN: float = 0.026493694591
E2D_VS_DLA_LOWER: float = 0.026210763951
E2D_VS_DLA_UPPER: float = 0.026776625232
E2D_VS_DLA_METHOD: str = "two-sided Student-t 95% interval over fleet-draw differences"

# Bound scope
SCENARIO: str = (
    "Manchester incident hour 2024-03-15 20:00-21:00 Europe/London, provisional uk2030 fleet"
)
EVALUATOR_SEED: Literal[0] = 0
REPLICATION_UNIT: Literal["fleet_draw"] = "fleet_draw"

# Strict declared tolerance for deterministic mean reconciliation
DECLARED_MEAN_TOLERANCE: float = MEAN_RECONCILIATION_TOL


def _deterministic_mean(values: tuple[float, ...] | list[float]) -> float:
    if not values:
        raise ValueError("cannot compute mean of empty values")
    return sum(values) / len(values)


def _check_mean_within_tolerance(
    per_seed: tuple[float, ...],
    declared_mean: float,
    tol: float = DECLARED_MEAN_TOLERANCE,
) -> None:
    calc = _deterministic_mean(per_seed)
    if abs(calc - declared_mean) > tol:
        raise ValueError(
            f"declared mean {declared_mean} drifts from per_seed mean {calc} "
            f"by {abs(calc - declared_mean)} > {tol}"
        )


def _check_sd_se_within_tolerance(
    per_seed: tuple[float, ...],
    declared_sd: float,
    declared_se: float,
) -> None:
    n = len(per_seed)
    mean = _deterministic_mean(per_seed)
    var = sum((x - mean) ** 2 for x in per_seed) / (n - 1) if n > 1 else 0.0
    expected_sd = math.sqrt(var)
    expected_se = expected_sd / math.sqrt(n) if n > 0 else 0.0
    if abs(declared_sd - expected_sd) > SD_RECONCILIATION_TOL:
        raise ValueError(
            f"sample_sd {declared_sd} drifts from expected {expected_sd} "
            f"by {abs(declared_sd - expected_sd)} > {SD_RECONCILIATION_TOL}"
        )
    if abs(declared_se - expected_se) > SE_RECONCILIATION_TOL:
        raise ValueError(
            f"standard_error {declared_se} drifts from expected {expected_se} "
            f"by {abs(declared_se - expected_se)} > {SE_RECONCILIATION_TOL}"
        )


# ---------------------------------------------------------------------------
# Typed view models — no p-values, no million-scale N
# ---------------------------------------------------------------------------


class E2bView(BaseModel):
    """One-draw descriptive comparison (E2b). No population inference."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    replication_unit: Literal["fleet_draw"] = REPLICATION_UNIT
    n: Literal[1] = 1
    fleet_seed: Literal[0] = 0
    evaluator_seed: Literal[0] = 0
    metric: Literal["offered_task_deadline_attainment"] = "offered_task_deadline_attainment"
    off: float = Field(description="strongest-link, no gate")
    jsq: float = Field(description="common-target JSQ, no gate")
    ingress_dla: float = Field(description="strongest-link + deadline gate")
    dla: float = Field(description="common-target DLA = JSQ placement + same gate")
    manifest_sha256: str = E2B_MANIFEST_SHA256
    code_commit: str = E2B_CODE_COMMIT
    actor_sha256: str = ACTOR_SHA256
    trace_sha256: str = TRACE_SHA256
    uncertainty: Literal["one_draw_descriptive_no_interval"] = "one_draw_descriptive_no_interval"
    interval: None = None
    standing: str = "RESEARCH-EVIDENCE FACT — one fleet draw, descriptive only"


class E2cView(BaseModel):
    """Four matched fleet draws: common-target DLA minus ingress_dla."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    replication_unit: Literal["fleet_draw"] = REPLICATION_UNIT
    n_fleet_draws: Literal[4] = 4
    fleet_seeds: tuple[int, int, int, int] = (1, 2, 3, 4)
    seed0_excluded: bool = True
    evaluator_seed: Literal[0] = 0
    estimand: Literal["dla_minus_ingress_dla offered_task_deadline_attainment"] = (
        "dla_minus_ingress_dla offered_task_deadline_attainment"
    )
    per_seed_values: tuple[float, float, float, float] = Field(
        default=E2C_PER_SEED  # type: ignore[assignment]
    )
    mean: float = E2C_MEAN
    sample_sd: float = E2C_SAMPLE_SD
    standard_error: float = E2C_STANDARD_ERROR
    degrees_of_freedom: Literal[3] = E2C_DF
    method: str = E2C_METHOD
    critical_value: float = E2C_CRITICAL
    lower: float = E2C_LOWER
    upper: float = E2C_UPPER
    includes_zero: bool = False
    decision: str = "evidence_of_directional_difference_within_bounded_four_draw_replication"
    manifest_sha256: str = E2C_MANIFEST_SHA256
    code_commit: str = E2C_CODE_COMMIT
    actor_sha256: str = ACTOR_SHA256
    trace_sha256: str = TRACE_SHA256
    all_negative: bool = True
    standing: str = (
        "RESEARCH-EVIDENCE FACT — interval excludes zero within bounded draws; "
        "does not support population or equivalence claims"
    )


class E2dView(BaseModel):
    """Four matched fleet draws: per_task_dla minus ingress_dla."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    replication_unit: Literal["fleet_draw"] = REPLICATION_UNIT
    n_fleet_draws: Literal[4] = 4
    fleet_seeds: tuple[int, int, int, int] = (1, 2, 3, 4)
    seed0_excluded: bool = True
    evaluator_seed: Literal[0] = 0
    estimand: Literal["per_task_dla_minus_ingress_dla offered_task_deadline_attainment"] = (
        "per_task_dla_minus_ingress_dla offered_task_deadline_attainment"
    )
    per_seed_values: tuple[float, float, float, float] = Field(
        default=E2D_PER_SEED  # type: ignore[assignment]
    )
    mean: float = E2D_MEAN
    sample_sd: float = E2D_SAMPLE_SD
    standard_error: float = E2D_STANDARD_ERROR
    degrees_of_freedom: Literal[3] = E2D_DF
    method: str = E2D_METHOD
    critical_value: float = E2D_CRITICAL
    lower: float = E2D_LOWER
    upper: float = E2D_UPPER
    includes_zero: bool = False
    decision: str = "directional_advantage_for_per_task_placement_within_bounded_draws"
    manifest_sha256: str = E2D_MANIFEST_SHA256
    code_commit: str = E2D_CODE_COMMIT
    actor_sha256: str = ACTOR_SHA256
    trace_sha256: str = TRACE_SHA256
    all_positive: bool = True
    standing: str = (
        "RESEARCH-EVIDENCE FACT — construct-validity comparison; not universal superiority"
    )


class E2dVsCommonTargetView(BaseModel):
    """Secondary: per_task_dla minus inherited common-target DLA, same four draws."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    replication_unit: Literal["fleet_draw"] = REPLICATION_UNIT
    n_fleet_draws: Literal[4] = 4
    fleet_seeds: tuple[int, int, int, int] = (1, 2, 3, 4)
    estimand: Literal["per_task_dla_minus_dla offered_task_deadline_attainment"] = (
        "per_task_dla_minus_dla offered_task_deadline_attainment"
    )
    mean: float = E2D_VS_DLA_MEAN
    lower: float = E2D_VS_DLA_LOWER
    upper: float = E2D_VS_DLA_UPPER
    method: str = E2D_VS_DLA_METHOD
    degrees_of_freedom: Literal[3] = 3
    critical_value: float = E2D_CRITICAL
    includes_zero: bool = False
    standing: str = "RESEARCH-EVIDENCE FACT — secondary within same bounded draws"


class DirectionReversalSummary(BaseModel):
    """Bounded direction statement — the core reversal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    statement: str = (
        "Within four matched incident-hour fleet draws (seeds 1-4), changing dispatch "
        "granularity from one common target per substep to sequential per-task "
        "least-busy feasible placement reversed the observed deadline-performance "
        "direction. Never claim universal superiority."
    )
    e2c_direction: Literal["negative"] = "negative"
    e2d_direction: Literal["positive"] = "positive"
    reversed: bool = True
    bounded_to: str = SCENARIO
    replication_unit: Literal["fleet_draw"] = REPLICATION_UNIT


class E2ResearchComparisonView(BaseModel):
    """Typed bundle for E2b/E2c/E2d matched-draw uncertainty service."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    e2b: E2bView
    e2c: E2cView
    e2d: E2dView
    e2d_vs_common_target: E2dVsCommonTargetView
    direction_reversal: DirectionReversalSummary
    per_task_vs_common_target_summary: str = (
        "Per-task sequential least-busy placement (per_task_dla) vs "
        "inherited common-target DLA: mean +0.026493694591, "
        "95% CI [0.026210763951, 0.026776625232] over same four fleet draws "
        "(seeds 1-4, df=3, Student-t). Common-target DLA was negative vs "
        "ingress_dla (-0.02122); per_task was positive (+0.00527), "
        "so per_task exceeded common-target by ~0.02649 within bounded draws."
    )
    replication_note: str = (
        "Replication unit is fleet_draw (fleet_seed); individual tasks are "
        "never statistical replications. Tasks are accounting records."
    )
    limitations: str = (
        "Bounded to one Manchester incident hour (2024-03-15 20:00-21:00), "
        "one provisional uk2030 fleet, evaluator_seed 0, fixed 1x compute service, "
        "zero backhaul latency, 2.5x waiting-room cap (6220 tasks/RSU), "
        "frozen 17-dim MAPPO actor that does not observe RSU load and does not "
        "select execution RSU, inherited deadline gate."
    )


# ---------------------------------------------------------------------------
# Strict builder — consumes E2ResearchEvidencePackage directly, fails closed
# ---------------------------------------------------------------------------

E2C_COMPARISON_ID: str = "e2c_dla_minus_ingress"
E2D_COMPARISON_ID: str = "e2d_per_task_minus_ingress"
E2D_VS_DLA_COMPARISON_ID: str = "e2d_per_task_minus_dla"


def _require_fleet_draw_sets(package: E2ResearchEvidencePackage) -> None:
    by_study = {fds.study: fds for fds in package.fleet_draw_sets}
    for study, expected in [("e2b", [0]), ("e2c", [1, 2, 3, 4]), ("e2d", [1, 2, 3, 4])]:
        fds = by_study.get(study)
        if fds is None:
            raise ValueError(f"missing fleet_draw_set for study {study}")
        if sorted(fds.fleet_seeds) != expected:
            raise ValueError(f"fleet_draw_set {study} must be {expected}, got {fds.fleet_seeds}")
        if fds.replication_unit != REPLICATION_UNIT:
            raise ValueError(
                f"fleet_draw_set {study} replication_unit must be {REPLICATION_UNIT}, "
                f"got {fds.replication_unit!r}"
            )
        if fds.evaluator_seed != EVALUATOR_SEED:
            raise ValueError(
                f"fleet_draw_set {study} evaluator_seed must be {EVALUATOR_SEED}, "
                f"got {fds.evaluator_seed}"
            )


def _extract_e2b_values(package: E2ResearchEvidencePackage) -> dict[str, float]:
    # Map arm -> value for E2b only (fleet_seed 0, evidence_id e2b_factorial)
    e2b_obs = [
        o
        for o in package.observations
        if o.evidence_id == "e2b_factorial_comparison"
        and o.fleet_seed == 0
        and o.evaluator_seed == EVALUATOR_SEED
        and o.replication_unit == REPLICATION_UNIT
    ]
    if len(e2b_obs) != 4:
        raise ValueError(f"E2b must have exactly 4 observations, got {len(e2b_obs)}")
    by_arm: dict[str, float] = {}
    for obs in e2b_obs:
        if obs.standing != "RESEARCH-EVIDENCE FACT":
            raise ValueError(f"E2b observation {obs.figure_id} has wrong standing {obs.standing!r}")
        if obs.manifest_sha256 != E2B_MANIFEST_SHA256:
            raise ValueError(
                f"E2b observation {obs.figure_id} manifest {obs.manifest_sha256!r} "
                f"must be {E2B_MANIFEST_SHA256!r}"
            )
        if obs.code_commit != E2B_CODE_COMMIT:
            raise ValueError(
                f"E2b observation {obs.figure_id} code_commit {obs.code_commit!r} "
                f"must be {E2B_CODE_COMMIT!r}"
            )
        if obs.metric != "offered_task_deadline_attainment":
            raise ValueError("E2b observation metric must be offered_task_deadline_attainment")
        if obs.arm not in {"off", "jsq", "dla", "ingress_dla"}:
            raise ValueError(f"unexpected E2b arm {obs.arm!r}")
        if obs.arm in by_arm:
            raise ValueError(f"duplicate E2b arm {obs.arm!r}")
        by_arm[obs.arm] = obs.value
    for arm in ("off", "jsq", "dla", "ingress_dla"):
        if arm not in by_arm:
            raise ValueError(f"missing E2b arm {arm!r}")
    # Fail closed if any E2b value drifts beyond tolerance from committed truth
    for arm, expected in [
        ("off", E2B_OFF),
        ("jsq", E2B_JSQ),
        ("ingress_dla", E2B_INGRESS_DLA),
        ("dla", E2B_DLA),
    ]:
        actual = by_arm[arm]
        if abs(actual - expected) > DECLARED_MEAN_TOLERANCE:
            raise ValueError(
                f"E2b arm {arm} value {actual} drifts from committed {expected} "
                f"by {abs(actual - expected)} > {DECLARED_MEAN_TOLERANCE}"
            )
    return by_arm


def _get_paired_difference(
    package: E2ResearchEvidencePackage, comparison_id: str
) -> tuple[tuple[float, ...], tuple[int, ...]]:
    pd = next((p for p in package.paired_differences if p.comparison_id == comparison_id), None)
    if pd is None:
        raise ValueError(f"missing paired_difference for {comparison_id!r}")
    if pd.replication_unit != REPLICATION_UNIT:
        raise ValueError(
            f"paired_difference {comparison_id!r} replication_unit must be {REPLICATION_UNIT}, "
            f"got {pd.replication_unit!r}"
        )
    if sorted(pd.fleet_seeds) != [1, 2, 3, 4]:
        raise ValueError(
            f"paired_difference {comparison_id!r} fleet_seeds must be [1,2,3,4], got {pd.fleet_seeds}"  # noqa: E501
        )
    if len(pd.per_seed_values) != 4:
        raise ValueError(f"paired_difference {comparison_id!r} must have 4 per_seed_values")
    # Check committed per_seed values within tolerance
    expected_map: dict[str, tuple[float, ...]] = {
        E2C_COMPARISON_ID: E2C_PER_SEED,
        E2D_COMPARISON_ID: E2D_PER_SEED,
        E2D_VS_DLA_COMPARISON_ID: E2D_VS_DLA_PER_SEED,
    }
    expected = expected_map.get(comparison_id)
    if expected is not None:
        for actual, exp in zip(pd.per_seed_values, expected, strict=True):
            if abs(actual - exp) > DECLARED_MEAN_TOLERANCE:
                raise ValueError(
                    f"paired_difference {comparison_id!r} per_seed value {actual} "
                    f"drifts from committed {exp} by {abs(actual - exp)} > {DECLARED_MEAN_TOLERANCE}"  # noqa: E501
                )
        # Sign check with committed direction
        if comparison_id == E2C_COMPARISON_ID:
            if not all(v < 0 for v in pd.per_seed_values):
                raise ValueError(
                    f"{comparison_id!r} per_seed_values must all be negative (sign reversal)"
                )
        else:
            if not all(v > 0 for v in pd.per_seed_values):
                raise ValueError(
                    f"{comparison_id!r} per_seed_values must all be positive (sign reversal)"
                )
    return tuple(pd.per_seed_values), tuple(pd.fleet_seeds)


def _get_declared_summary(
    package: E2ResearchEvidencePackage, comparison_id: str
) -> tuple[float, float, float, str, int, bool, str]:
    ds = next((d for d in package.declared_summaries if d.comparison_id == comparison_id), None)
    if ds is None:
        raise ValueError(f"missing declared_summary for {comparison_id!r}")
    # Method must be the declared Student-t method; do not substitute CI method
    expected_method = "two-sided Student-t 95% interval over fleet-draw differences"
    if ds.method != expected_method:
        raise ValueError(
            f"declared_summary {comparison_id!r} method must be {expected_method!r}, got {ds.method!r}"  # noqa: E501
        )
    if ds.degrees_of_freedom != 3:
        raise ValueError(
            f"declared_summary {comparison_id!r} df must be 3, got {ds.degrees_of_freedom}"
        )
    # CI ordering and inclusion already validated by model; re-check for fail-closed drift
    if not (ds.lower < ds.upper):
        raise ValueError(f"declared_summary {comparison_id!r} CI ordering violated")
    if not (ds.lower <= ds.mean <= ds.upper):
        raise ValueError(f"declared_summary {comparison_id!r} mean outside CI")
    # For secondary, sd/se must remain None
    if comparison_id == E2D_VS_DLA_COMPARISON_ID:
        if ds.sample_sd is not None or ds.standard_error is not None:
            raise ValueError(
                f"declared_summary {comparison_id!r} sd/se must be None/UNAVAILABLE, "
                f"got sd={ds.sample_sd!r} se={ds.standard_error!r}"
            )
    else:
        if ds.sample_sd is None or ds.standard_error is None:
            raise ValueError(f"declared_summary {comparison_id!r} missing sd/se")
        # Reconcile sd/se within tolerance against per_seed
    # Return tuple for builder
    decision = ds.decision
    return ds.mean, ds.lower, ds.upper, ds.method, ds.degrees_of_freedom, ds.includes_zero, decision


def build_e2_comparison_view(package: E2ResearchEvidencePackage) -> E2ResearchComparisonView:
    """Build the exact typed view for E2b/E2c/E2d.

    The package's exact observations, paired-difference sets, and declared
    summaries are used.  Means are deterministically reconciled to per-draw
    values within the model's strict tolerance (1e-12); declared Student-t
    intervals and method are preserved without substitution.  Any
    inconsistent, missing, or drifted study, draw, mean, CI, identity, seed,
    or replication value raises.
    """
    if not isinstance(package, E2ResearchEvidencePackage):
        raise TypeError(f"package must be E2ResearchEvidencePackage, got {type(package).__name__}")

    # Top-level replication / evaluator checks
    if package.replication_unit != REPLICATION_UNIT:
        raise ValueError(
            f"package replication_unit must be {REPLICATION_UNIT!r}, got {package.replication_unit!r}"  # noqa: E501
        )
    if package.evaluator_seed != EVALUATOR_SEED:
        raise ValueError(
            f"package evaluator_seed must be {EVALUATOR_SEED}, got {package.evaluator_seed}"
        )

    # Identity checks — fail closed on any wrong hash
    si = package.source_identities
    if si.actor.sha256 != ACTOR_SHA256:
        raise ValueError(f"actor sha256 mismatch: {si.actor.sha256!r}")
    if si.trace.sha256 != TRACE_SHA256:
        raise ValueError(f"trace sha256 mismatch: {si.trace.sha256!r}")
    expected_heads = {
        "e2b": E2B_CODE_COMMIT,
        "e2c": E2C_CODE_COMMIT,
        "e2d": E2D_CODE_COMMIT,
    }
    for k, exp in expected_heads.items():
        actual = getattr(si.research_heads, k)
        if actual != exp:
            raise ValueError(f"research head {k} must be {exp!r}, got {actual!r}")
    for study, exp in [
        ("e2b", E2B_MANIFEST_SHA256),
        ("e2c", E2C_MANIFEST_SHA256),
        ("e2d", E2D_MANIFEST_SHA256),
    ]:
        actual = si.manifest_sha256_by_study.get(study)
        if actual != exp:
            raise ValueError(f"manifest for {study} must be {exp!r}, got {actual!r}")

    _require_fleet_draw_sets(package)

    # E2b exact observations
    e2b_by_arm = _extract_e2b_values(package)

    # Paired differences and declared summaries — strict linkage
    e2c_per_seed, e2c_seeds = _get_paired_difference(package, E2C_COMPARISON_ID)
    e2d_per_seed, e2d_seeds = _get_paired_difference(package, E2D_COMPARISON_ID)
    vs_per_seed, vs_seeds = _get_paired_difference(package, E2D_VS_DLA_COMPARISON_ID)

    e2c_mean, e2c_lower, e2c_upper, e2c_method, e2c_df, e2c_includes_zero, e2c_decision = (
        _get_declared_summary(package, E2C_COMPARISON_ID)
    )
    e2d_mean, e2d_lower, e2d_upper, e2d_method, e2d_df, e2d_includes_zero, e2d_decision = (
        _get_declared_summary(package, E2D_COMPARISON_ID)
    )
    vs_mean, vs_lower, vs_upper, vs_method, vs_df, vs_includes_zero, vs_decision = (
        _get_declared_summary(package, E2D_VS_DLA_COMPARISON_ID)
    )

    # Deterministic mean reconciliation — strict, fail closed
    _check_mean_within_tolerance(e2c_per_seed, e2c_mean)
    _check_mean_within_tolerance(e2d_per_seed, e2d_mean)
    _check_mean_within_tolerance(vs_per_seed, vs_mean)

    # For primary comparisons, also reconcile sd/se
    # Fetch declared sd/se directly from package to preserve source values
    e2c_ds = next(d for d in package.declared_summaries if d.comparison_id == E2C_COMPARISON_ID)
    e2d_ds = next(d for d in package.declared_summaries if d.comparison_id == E2D_COMPARISON_ID)
    if e2c_ds.sample_sd is None or e2c_ds.standard_error is None:
        raise ValueError("E2c declared sd/se must be present")
    if e2d_ds.sample_sd is None or e2d_ds.standard_error is None:
        raise ValueError("E2d declared sd/se must be present")
    _check_sd_se_within_tolerance(e2c_per_seed, e2c_ds.sample_sd, e2c_ds.standard_error)
    _check_sd_se_within_tolerance(e2d_per_seed, e2d_ds.sample_sd, e2d_ds.standard_error)

    # Committed mean/CI must not drift beyond tolerance from declared package values
    # (already reconciled) and also must match hard-committed truth within tolerance.
    # This kills mutants that shift both per_seed and mean consistently.
    for actual, expected, label in [
        (e2c_mean, E2C_MEAN, "E2c mean"),
        (e2c_lower, E2C_LOWER, "E2c lower"),
        (e2c_upper, E2C_UPPER, "E2c upper"),
        (e2d_mean, E2D_MEAN, "E2d mean"),
        (e2d_lower, E2D_LOWER, "E2d lower"),
        (e2d_upper, E2D_UPPER, "E2d upper"),
        (vs_mean, E2D_VS_DLA_MEAN, "secondary mean"),
        (vs_lower, E2D_VS_DLA_LOWER, "secondary lower"),
        (vs_upper, E2D_VS_DLA_UPPER, "secondary upper"),
    ]:
        if abs(actual - expected) > DECLARED_MEAN_TOLERANCE:
            raise ValueError(
                f"{label} {actual} drifts from committed {expected} "
                f"by {abs(actual - expected)} > {DECLARED_MEAN_TOLERANCE}"
            )

    # Direction reversal must hold: E2c negative, E2d positive
    if not (e2c_mean < 0 and all(v < 0 for v in e2c_per_seed)):
        raise ValueError("E2c direction must be negative")
    if not (e2d_mean > 0 and all(v > 0 for v in e2d_per_seed)):
        raise ValueError("E2d direction must be positive")
    if not (vs_mean > 0 and all(v > 0 for v in vs_per_seed)):
        raise ValueError("secondary direction must be positive")

    # Build views from package exact values (preserve declared CIs/method)
    e2b = E2bView(
        off=e2b_by_arm["off"],
        jsq=e2b_by_arm["jsq"],
        ingress_dla=e2b_by_arm["ingress_dla"],
        dla=e2b_by_arm["dla"],
    )
    e2c = E2cView(
        per_seed_values=e2c_per_seed,
        mean=e2c_mean,
        sample_sd=e2c_ds.sample_sd,
        standard_error=e2c_ds.standard_error,
        lower=e2c_lower,
        upper=e2c_upper,
        method=e2c_method,
        includes_zero=e2c_includes_zero,
        decision=e2c_decision,
    )
    e2d = E2dView(
        per_seed_values=e2d_per_seed,
        mean=e2d_mean,
        sample_sd=e2d_ds.sample_sd,
        standard_error=e2d_ds.standard_error,
        lower=e2d_lower,
        upper=e2d_upper,
        method=e2d_method,
        includes_zero=e2d_includes_zero,
        decision=e2d_decision,
    )
    e2d_vs = E2dVsCommonTargetView(
        mean=vs_mean,
        lower=vs_lower,
        upper=vs_upper,
        method=vs_method,
        includes_zero=vs_includes_zero,
    )

    direction = DirectionReversalSummary()

    return E2ResearchComparisonView(
        e2b=e2b,
        e2c=e2c,
        e2d=e2d,
        e2d_vs_common_target=e2d_vs,
        direction_reversal=direction,
    )


__all__ = [
    "ACTOR_SHA256",
    "DECLARED_MEAN_TOLERANCE",
    "DirectionReversalSummary",
    "E2B_CODE_COMMIT",
    "E2B_DLA",
    "E2B_INGRESS_DLA",
    "E2B_JSQ",
    "E2B_MANIFEST_SHA256",
    "E2B_OFF",
    "E2C_CODE_COMMIT",
    "E2C_CRITICAL",
    "E2C_DF",
    "E2C_LOWER",
    "E2C_MANIFEST_SHA256",
    "E2C_MEAN",
    "E2C_METHOD",
    "E2C_PER_SEED",
    "E2C_SAMPLE_SD",
    "E2C_STANDARD_ERROR",
    "E2C_UPPER",
    "E2D_CODE_COMMIT",
    "E2D_CRITICAL",
    "E2D_DF",
    "E2D_LOWER",
    "E2D_MANIFEST_SHA256",
    "E2D_MEAN",
    "E2D_METHOD",
    "E2D_PER_SEED",
    "E2D_SAMPLE_SD",
    "E2D_STANDARD_ERROR",
    "E2D_UPPER",
    "E2D_VS_DLA_LOWER",
    "E2D_VS_DLA_MEAN",
    "E2D_VS_DLA_PER_SEED",
    "E2D_VS_DLA_UPPER",
    "E2ResearchComparisonView",
    "E2bView",
    "E2cView",
    "E2dView",
    "E2dVsCommonTargetView",
    "TRACE_SHA256",
    "build_e2_comparison_view",
]
