"""VEC outcome predictor (platform P-1 tier 1, decision from 30 July).

Implements ``docs/platform/outcome_predictor_design.md``: a three-regime
closed-form surrogate over the project's own admitted campaign cells that
predicts instantly inside the measured envelope and refuses, with a typed
first-class refusal, outside it. Every output is typed ``prediction`` and is
NEVER evidence — ``evidence: False`` and ``confirmatory: False`` are
type-level literals on the record.

The three regimes package the measured laws:

1. ``measured_inert`` — off-saturation traces above their measured onsets
   return the measured top-capacity descriptives: the paired capacity
   differences were measured *exactly zero*, so the honest model is a lookup
   that declares itself one.
2. ``near_onset`` — at/below the measured per-trace onsets the faint measured
   deltas are applied as corrections; onsets are per-trace lookups and are
   never interpolated across traces (the onset-scaling prediction was
   REFUTED 4/6 — that verdict is the reason this regime refuses to
   generalise).
3. ``saturated`` — the incident trace: the ceiling law ``p95-of-missed =
   K x capacity`` with ``K = 39,959 ms``; mean latency linear per actor;
   p50 pinned at 44.3 ms; offload rate constant per actor; attainment flat
   with the measured faint deep-squeeze rise.

Fit provenance is inherited, never re-decided: the fit accepts only analyses
of completed, admitted campaigns registered by experiment id and design
fingerprint, refuses GPU-track and non-admitted sources by name, records
every accepted source digest into the fit artifact, and — before either
fitting or loading — a self-test must reproduce the published constants
(K = 39,959, sample sigma 166, latency slopes 3,828.2 / 6,555.4 ms per
capacity unit, +6.09 pp crossover margin, p50 = 44.3 ms). Mismatch refuses.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from traffictwin.integration.vec_campaign.analysis import (
    VecArmDescriptives,
    VecCampaignAnalysis,
)

METHOD_VERSION: Literal["vec-outcome-predictor-1.0"] = "vec-outcome-predictor-1.0"
DESIGN_REFERENCE: Literal["docs/platform/outcome_predictor_design.md"] = (
    "docs/platform/outcome_predictor_design.md"
)

TRAINED_ACTOR = "ukfleettrain_mappo_model_c_17"
BASELINE_ACTOR = "baseline_model_c_17"
MEASURED_ACTORS = (TRAINED_ACTOR, BASELINE_ACTOR)
MEASURED_FLEET_PRESET: Literal["uk2030"] = "uk2030"

#: Measured concurrent-slot counts per admitted trace.
TRACE_SLOTS: dict[str, int] = {"we": 139, "wd_pm": 163, "ev": 175, "wd_am": 215, "inc": 2488}

#: The unmeasured density band; both endpoints are measured traces.
DENSITY_GAP_EXCLUSIVE = (215, 2488)

CAPACITY_ENVELOPE = (0.1, 2.5)

#: Measured per-trace onset capacities (sweep-completion record, 28 July).
TRACE_ONSETS: dict[str, float] = {"we": 0.25, "wd_pm": 0.25, "ev": 0.1, "wd_am": 0.1}

METRIC_DEADLINE = "deadline_attainment"
METRIC_LATENCY_MEAN = "latency_mean_ms"
METRIC_P50 = "latency_p50_ms"
METRIC_CEILING = "tail_ceiling_ms"
METRIC_OFFLOAD = "offload_rate"

_ANALYSIS_METRIC_MAP = {
    "tos.task.deadline_success.rate": METRIC_DEADLINE,
    "task.latency.mean_ms": METRIC_LATENCY_MEAN,
    "task.offload.rate": METRIC_OFFLOAD,
}

#: Two-sided 95% Student-t multipliers by degrees of freedom; the pooled
#: tables never exceed eleven seeds, so the fallback is never load-bearing.
_T95_BY_DF = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.160,
    14: 2.145,
}
_T95_FALLBACK = 2.101


@dataclass(frozen=True)
class PublishedConstant:
    """One published constant with the tolerance its rounding implies."""

    value: float
    tolerance: float


#: The published record values the self-test gate must reproduce; the sigma
#: is the SAMPLE estimator (ddof=1) — the estimator-choice lesson from the
#: ceiling-law verdict self-test (population gives 163.4 and must not pass).
PUBLISHED_CONSTANTS: dict[str, PublishedConstant] = {
    "k_ms_per_unit_capacity": PublishedConstant(39_959.0, 0.5),
    "k_sample_sigma": PublishedConstant(166.0, 0.5),
    "latency_slope_trained_ms_per_unit": PublishedConstant(3_828.2, 0.05),
    "latency_slope_baseline_ms_per_unit": PublishedConstant(6_555.4, 0.05),
    "crossover_margin_pp": PublishedConstant(6.09, 0.005),
    "p50_latency_ms": PublishedConstant(44.3, 0.05),
}


@dataclass(frozen=True)
class RegisteredExperiment:
    """One admitted campaign the fit may consume, pinned by design digest."""

    trace: str
    actor: str
    role: Literal["grid", "deep", "pilot", "confirmatory", "baseline_grid", "crossover_baseline"]
    design_fingerprint: str


#: The complete registry of admitted campaign analyses (~154 cells). An
#: analysis whose experiment id is absent here, or whose design fingerprint
#: differs, is refused — admission is inherited, not re-decided.
EXPERIMENT_REGISTRY: dict[str, RegisteredExperiment] = {
    "vec-capacity-squeeze-pilot": RegisteredExperiment(
        "inc",
        TRAINED_ACTOR,
        "pilot",
        "de474e038523e5e79e2d167364f312dc7c2ea273e610f2d26ec1cf253f41bb90",
    ),
    "vec-capacity-confirmatory": RegisteredExperiment(
        "inc",
        TRAINED_ACTOR,
        "confirmatory",
        "f289db31ce28b6361f91911485c36483b068fdee1ed73aa1d4ef0a8b57bc1754",
    ),
    "vec-capacity-deep-inc": RegisteredExperiment(
        "inc",
        TRAINED_ACTOR,
        "deep",
        "5331e5207ef2eae2dfde301522cc6ce76e3283419075e22ee79049226430e25e",
    ),
    "vec-crossover-inc-baseline": RegisteredExperiment(
        "inc",
        BASELINE_ACTOR,
        "crossover_baseline",
        "4784f5fc3055831091aca52def5497b3cd3f715de469a33fb023917bde108e11",
    ),
    "vec-capacity-grid-we": RegisteredExperiment(
        "we",
        TRAINED_ACTOR,
        "grid",
        "b4da3a5ba9b4dd100c3dd041b7bc7a19e35da2b4e8b673fa4733c0203a308312",
    ),
    "vec-capacity-grid-ev": RegisteredExperiment(
        "ev",
        TRAINED_ACTOR,
        "grid",
        "efa83a78c8518861cde62191c2a8c6975b5e616c6770f309496c955883a8245b",
    ),
    "vec-capacity-grid-wd-am": RegisteredExperiment(
        "wd_am",
        TRAINED_ACTOR,
        "grid",
        "2844fde2c38ec22664357865c528006a1cbad62f3ddb659fbd20a38c920f8df6",
    ),
    "vec-capacity-grid-wd-pm": RegisteredExperiment(
        "wd_pm",
        TRAINED_ACTOR,
        "grid",
        "635a2cbefd94b75773fcb608d71f4c0c8a2cbc3df447934980655fe75bdf8df5",
    ),
    "vec-capacity-deep-we": RegisteredExperiment(
        "we",
        TRAINED_ACTOR,
        "deep",
        "0759b31f4cae4afbb59027fec7ebc0e408b033391219d2c4fc85946648465605",
    ),
    "vec-capacity-deep-ev": RegisteredExperiment(
        "ev",
        TRAINED_ACTOR,
        "deep",
        "727745441c5e43c1cb95ea76b337716629cf528319b534e756bc9c140192109d",
    ),
    "vec-capacity-deep-wd-am": RegisteredExperiment(
        "wd_am",
        TRAINED_ACTOR,
        "deep",
        "1897f9f4a6a4e2a985a0b539cc199d85a6a0cb091ba628d7e70fe332c2d9222d",
    ),
    "vec-capacity-deep-wd-pm": RegisteredExperiment(
        "wd_pm",
        TRAINED_ACTOR,
        "deep",
        "1d1c6ce65a17db27a93dedd86648f8f89a0a031e220b7b9985d1cce71aa7febd",
    ),
    "vec-baseline-invariance-ev": RegisteredExperiment(
        "ev",
        BASELINE_ACTOR,
        "baseline_grid",
        "2f4e371b7769fde3cf7a6efe9d14e92fecb100cff9d971ec36fa23164ff1fd6a",
    ),
}

#: Path fragments that name the sources the fit refuses outright: the GPU
#: track and both Sparse-64 returns are non-admitted by their own records.
REFUSED_SOURCE_PATH_MARKERS = ("gpu-track", "gpu", "sparse64")

_REFUSAL_CODES = (
    "TRACE_NOT_MEASURED",
    "CAPACITY_OUT_OF_ENVELOPE",
    "FLEET_PRESET_NOT_MEASURED",
    "DENSITY_GAP",
    "ACTOR_NOT_MEASURED",
    "ACTOR_CAPACITY_NOT_MEASURED",
)

#: The mandatory producer/SUMO citation set (the permission's condition);
#: every published prediction card and the fit documentation carry it.
PRODUCER_CITATION_REFERENCE: Literal["docs/producer_citation_requirements.md"] = (
    "docs/producer_citation_requirements.md"
)
PRODUCER_CITATION_BUNDLE: dict[str, str] = {
    "environment_repository": "gitlab.cs.man.ac.uk/e62992rp/vec_env",
    "environment_pinned_commit": "068b4ea33e640f206ce6a7d04f3d6fae2ac831f4",
    "trace_data_repository": "gitlab.cs.man.ac.uk/e62992rp/tos-data",
    "trace_data_audited_commit": "f6c67acbed3360dba3a0d5c8d1fd557caa99ecff",
    "engine_version": "v2_post_nrsus_fix",
    "author": "Randy Prasetia Putra, University of Manchester",
    "requirements_record": "docs/producer_citation_requirements.md",
}

_STANDING_CAVEATS = (
    "prediction from a surrogate fit on admitted exploratory campaign analyses; "
    "never evidence, never confirmatory, never a physical journey claim",
    "one audited policy per actor, one reviewed trace per scenario, fleet preset "
    "uk2030 only; nothing here generalises to algorithm families",
)


class OutcomePredictorError(RuntimeError):
    """Typed refusal raised by the fit and load boundaries."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class PredictorModel(BaseModel):
    """Strict, frozen, finite base for predictor artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


class VecScenario(PredictorModel):
    """One scenario coordinate: ``(trace, capacity, actor)`` plus context."""

    trace: str
    capacity: float
    actor: str
    fleet_preset: str = MEASURED_FLEET_PRESET
    fleet_size: int | None = None


class SeedStat(PredictorModel):
    """Per-seed values for one measured point; the intervals' raw material."""

    seed_values: dict[str, float]
    mean: float
    minimum: float
    maximum: float

    @property
    def count(self) -> int:
        return len(self.seed_values)


class MetricPrediction(PredictorModel):
    """Point plus interval for one metric; the basis names its provenance."""

    metric: str
    point: float
    interval_low: float
    interval_high: float
    seed_support: int = Field(ge=0)
    interval_basis: str


class PredictionRecord(PredictorModel):
    """A typed prediction. ``evidence`` and ``confirmatory`` can never be True."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["vec-outcome-predictor-1.0"] = METHOD_VERSION
    design_reference: Literal["docs/platform/outcome_predictor_design.md"] = DESIGN_REFERENCE
    prediction: Literal[True] = True
    evidence: Literal[False] = False
    confirmatory: Literal[False] = False
    research_status: Literal["owner_approved_candidate"] = "owner_approved_candidate"
    scenario: VecScenario
    regime: Literal["measured_inert", "near_onset", "saturated"]
    metrics: tuple[MetricPrediction, ...]
    metrics_unavailable: dict[str, str]
    sources: tuple[str, ...]
    fit_digest: str
    caveats: tuple[str, ...]
    citation_reference: Literal["docs/producer_citation_requirements.md"] = (
        PRODUCER_CITATION_REFERENCE
    )


class PredictionRefusal(PredictorModel):
    """A typed refusal — a first-class output naming its gap and its cure."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["vec-outcome-predictor-1.0"] = METHOD_VERSION
    refusal: Literal[True] = True
    prediction: Literal[False] = False
    evidence: Literal[False] = False
    code: str
    detail: str
    closing_campaign: str
    fit_digest: str


class InertLookup(PredictorModel):
    """Regime-1 table: the measured top-capacity descriptives per trace/actor.

    ``measured_capacity_minimum``/``maximum`` bound this trace/actor pair's
    OWN measured envelope — the measured domain is not a Cartesian product,
    and a capacity below the pair's smallest admitted arm refuses rather
    than extrapolating (review-conformance, 1 August).
    """

    trace: str
    actor: str
    experiment_id: str
    arm_label: str
    metrics: dict[str, SeedStat]
    measured_capacity_minimum: float
    measured_capacity_maximum: float


class NearOnsetArm(PredictorModel):
    """Regime-2 table: one measured deep arm at/below its trace's onset."""

    trace: str
    actor: str
    experiment_id: str
    capacity: float
    metrics: dict[str, SeedStat]
    deltas_vs_top: dict[str, float]


class SaturatedArm(PredictorModel):
    """Regime-3 table: pooled admitted seed values at one inc capacity."""

    capacity: float
    metrics: dict[str, SeedStat]
    source_experiments: tuple[str, ...]


class SaturatedActorFit(PredictorModel):
    """Regime-3 per-actor model: the latency line plus the measured arms."""

    actor: str
    latency_slope_ms_per_unit: float
    latency_intercept_ms: float
    slope_source_experiment: str
    offload_rate_constant: float
    offload_rate_minimum: float
    offload_rate_maximum: float
    arms: tuple[SaturatedArm, ...]


class CeilingFit(PredictorModel):
    """The ceiling law with its sample spread and measured sag widening."""

    k_ms_per_unit_capacity: float
    k_sample_sigma: float
    pair_count: int = Field(ge=1)
    sag_widening_by_capacity: dict[str, float]


class P50Fit(PredictorModel):
    """The pinned p50 with the measured values that pin it."""

    pinned_ms: float
    pilot_arm_values_ms: dict[str, float]
    deep_cell_minimum_ms: float
    deep_cell_maximum_ms: float


class SelfTestCheck(PredictorModel):
    """One reproduced constant against its published value."""

    name: str
    computed: float
    published: float
    tolerance: float
    passed: bool


class SelfTestReport(PredictorModel):
    """The gate: all published constants reproduced from the fit sources."""

    checks: tuple[SelfTestCheck, ...]
    passed: bool


class FitSource(PredictorModel):
    """One accepted source, pinned by content digest."""

    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    kind: Literal[
        "campaign_analysis", "pilot_dynamics", "ceiling_law_verdict", "latency_tail_record"
    ]
    experiment_id: str | None = None
    design_fingerprint: str | None = None


class OutcomePredictorFit(PredictorModel):
    """The committed fit artifact; ``predict`` consumes nothing else."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["vec-outcome-predictor-1.0"] = METHOD_VERSION
    design_reference: Literal["docs/platform/outcome_predictor_design.md"] = DESIGN_REFERENCE
    research_status: Literal["owner_approved_candidate"] = "owner_approved_candidate"
    evidence: Literal[False] = False
    generated_at_utc: str
    sources: tuple[FitSource, ...]
    trace_slots: dict[str, int]
    trace_onsets: dict[str, float]
    capacity_envelope: tuple[float, float]
    fleet_preset: Literal["uk2030"] = MEASURED_FLEET_PRESET
    inert: tuple[InertLookup, ...]
    near_onset: tuple[NearOnsetArm, ...]
    saturated: dict[str, SaturatedActorFit]
    ceiling: CeilingFit
    p50: P50Fit
    self_test: SelfTestReport
    citation_reference: Literal["docs/producer_citation_requirements.md"] = (
        PRODUCER_CITATION_REFERENCE
    )
    citation_bundle: dict[str, str] = Field(default_factory=lambda: dict(PRODUCER_CITATION_BUNDLE))


@dataclass(frozen=True)
class LoadedFit:
    """A fit artifact that has passed the load-time self-test gate."""

    fit: OutcomePredictorFit
    digest: str


# --- source acceptance -------------------------------------------------------


def _refuse_named_sources(path: Path) -> None:
    lowered_parts = [part.lower() for part in path.parts]
    refused = any(part in ("gpu", "gpu-track") for part in lowered_parts) or any(
        "sparse64" in part for part in lowered_parts
    )
    if refused:
        raise OutcomePredictorError(
            "NON_ADMITTED_SOURCE_REFUSED",
            f"source path {path.name} is under a refused location: GPU-track and "
            "Sparse-64 outputs are non-admitted by their own records and never enter the fit",
        )


def _read_source_bytes(path: Path) -> bytes:
    _refuse_named_sources(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise OutcomePredictorError(
            "SOURCE_UNREADABLE", f"source {path.name} could not be read"
        ) from exc
    if b"NON_ADMITTED" in raw:
        raise OutcomePredictorError(
            "NON_ADMITTED_SOURCE_REFUSED",
            f"source {path.name} carries a NON_ADMITTED marker and never enters the fit",
        )
    return raw


def _accept_campaign_analysis(path: Path, raw: bytes) -> VecCampaignAnalysis:
    """Refuse by name, status, and pinned digest before structural validation."""

    payload = json.loads(raw.decode("utf-8"))
    status = str(payload.get("campaign_status"))
    experiment_id = str(payload.get("experiment_id"))
    if status != "completed":
        raise OutcomePredictorError(
            "CAMPAIGN_NOT_COMPLETED",
            f"{experiment_id} has campaign_status '{status}'; only completed admitted "
            "campaigns enter the fit",
        )
    registered = EXPERIMENT_REGISTRY.get(experiment_id)
    if registered is None:
        raise OutcomePredictorError(
            "SOURCE_NOT_REGISTERED",
            f"experiment '{experiment_id}' is not in the admitted registry; "
            "admission is inherited, not re-decided here",
        )
    fingerprint = str(payload.get("design_fingerprint"))
    if fingerprint != registered.design_fingerprint:
        raise OutcomePredictorError(
            "DESIGN_FINGERPRINT_MISMATCH",
            f"{experiment_id} carries design fingerprint {fingerprint[:12]}… but the "
            f"registry pins {registered.design_fingerprint[:12]}…",
        )
    try:
        return VecCampaignAnalysis.model_validate_json(raw)
    except ValidationError as exc:
        raise OutcomePredictorError(
            "SOURCE_INVALID", f"{path.name} is not a valid campaign analysis"
        ) from exc


# --- arithmetic helpers ------------------------------------------------------


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _sample_sigma(values: Sequence[float]) -> float:
    mean = _mean(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def _ols(points: Sequence[tuple[float, float]]) -> tuple[float, float]:
    """Slope and intercept of ordinary least squares over (x, y) points."""

    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    x_mean = _mean(xs)
    y_mean = _mean(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    slope = sum((x - x_mean) * (y - y_mean) for x, y in points) / denominator
    return slope, y_mean - slope * x_mean


def _seed_stat(seed_values: dict[str, float]) -> SeedStat:
    values = list(seed_values.values())
    return SeedStat(
        seed_values=dict(sorted(seed_values.items())),
        mean=_mean(values),
        minimum=min(values),
        maximum=max(values),
    )


def _descriptives_by_arm_metric(
    analysis: VecCampaignAnalysis,
) -> dict[tuple[str, str], VecArmDescriptives]:
    table: dict[tuple[str, str], VecArmDescriptives] = {}
    for row in [*analysis.primary_descriptives, *analysis.secondary_descriptives]:
        canonical = _ANALYSIS_METRIC_MAP.get(row.metric_key)
        if canonical is not None:
            table[(row.arm_label, canonical)] = row
    return table


def _arm_capacity(arm_label: str) -> float:
    match = re.fullmatch(r"cap-(\d+(?:\.\d+)?)", arm_label)
    if match is None:
        raise OutcomePredictorError(
            "SOURCE_INVALID", f"arm label '{arm_label}' does not encode a capacity"
        )
    return float(match.group(1))


# --- fit ---------------------------------------------------------------------

_TAIL_ROW_PATTERN = re.compile(r"^\|\s*cap-(\d+(?:\.\d+)?)\s*\|\s*([\d.,]+)\s*ms\s*\|")
_TAIL_RECORD_TITLE = "# Latency-Tail Analysis"


def _parse_latency_tail_record(path: Path, raw: bytes) -> dict[str, float]:
    text = raw.decode("utf-8")
    if _TAIL_RECORD_TITLE not in text:
        raise OutcomePredictorError(
            "SOURCE_INVALID", f"{path.name} is not the latency-tail analysis record"
        )
    p50_by_arm: dict[str, float] = {}
    for line in text.splitlines():
        match = _TAIL_ROW_PATTERN.match(line.strip())
        if match is not None:
            p50_by_arm[match.group(1)] = float(match.group(2).replace(",", ""))
    if sorted(p50_by_arm) != ["0.75", "1.0", "1.5", "2.5"]:
        raise OutcomePredictorError(
            "SOURCE_INVALID",
            f"{path.name} did not yield the four pilot arms' p50 values (got {sorted(p50_by_arm)})",
        )
    return p50_by_arm


def _classify_source(path: Path, raw: bytes) -> str:
    if path.suffix == ".md":
        return "latency_tail_record"
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OutcomePredictorError(
            "SOURCE_INVALID", f"{path.name} is neither JSON nor a markdown record"
        ) from exc
    if not isinstance(payload, dict):
        raise OutcomePredictorError("SOURCE_INVALID", f"{path.name} is not a JSON object")
    record_type = payload.get("record_type")
    if record_type == "ceiling_law_prediction_verdict":
        return "ceiling_law_verdict"
    if record_type == "capacity_pilot_dynamics_analysis":
        return "pilot_dynamics"
    if "experiment_id" in payload and "primary_descriptives" in payload:
        return "campaign_analysis"
    raise OutcomePredictorError("SOURCE_INVALID", f"{path.name} matches no accepted source kind")


def _self_test_report(computed: dict[str, float]) -> SelfTestReport:
    checks: list[SelfTestCheck] = []
    for name, constant in PUBLISHED_CONSTANTS.items():
        value = computed[name]
        passed = abs(value - constant.value) <= constant.tolerance
        checks.append(
            SelfTestCheck(
                name=name,
                computed=value,
                published=constant.value,
                tolerance=constant.tolerance,
                passed=passed,
            )
        )
    return SelfTestReport(checks=tuple(checks), passed=all(check.passed for check in checks))


def fit_outcome_predictor(
    analysis_paths: Sequence[Path],
    *,
    repo_root: Path,
    generated_at_utc: str,
) -> OutcomePredictorFit:
    """Fit the surrogate from admitted sources only; the self-test gates it.

    ``analysis_paths`` must include the thirteen registered campaign
    analyses, the pilot-dynamics artifact (K and its sample spread), the
    final ceiling-law verdict (sag widening and the deep p50 spread), and
    the committed latency-tail record (the pinned p50). Anything else in,
    a typed refusal out.
    """

    analyses: dict[str, tuple[VecCampaignAnalysis, FitSource]] = {}
    pilot_dynamics: dict[str, object] | None = None
    ceiling_verdict: dict[str, object] | None = None
    tail_p50: dict[str, float] | None = None
    sources: list[FitSource] = []

    for path in analysis_paths:
        raw = _read_source_bytes(path)
        digest = hashlib.sha256(raw).hexdigest()
        kind = _classify_source(path, raw)
        try:
            relative = str(path.resolve().relative_to(repo_root.resolve()))
        except ValueError:
            relative = str(path)
        if kind == "campaign_analysis":
            analysis = _accept_campaign_analysis(path, raw)
            source = FitSource(
                path=relative,
                sha256=digest,
                kind="campaign_analysis",
                experiment_id=analysis.experiment_id,
                design_fingerprint=analysis.design_fingerprint,
            )
            analyses[analysis.experiment_id] = (analysis, source)
        elif kind == "pilot_dynamics":
            pilot_dynamics = json.loads(raw.decode("utf-8"))
            source = FitSource(path=relative, sha256=digest, kind="pilot_dynamics")
        elif kind == "ceiling_law_verdict":
            ceiling_verdict = json.loads(raw.decode("utf-8"))
            source = FitSource(path=relative, sha256=digest, kind="ceiling_law_verdict")
        else:
            tail_p50 = _parse_latency_tail_record(path, raw)
            source = FitSource(path=relative, sha256=digest, kind="latency_tail_record")
        sources.append(source)

    missing = sorted(set(EXPERIMENT_REGISTRY) - set(analyses))
    if missing:
        raise OutcomePredictorError(
            "SOURCE_MISSING", f"registered campaign analyses absent from the fit: {missing}"
        )
    if pilot_dynamics is None or ceiling_verdict is None or tail_p50 is None:
        raise OutcomePredictorError(
            "SOURCE_MISSING",
            "the fit needs the pilot-dynamics artifact, the final ceiling-law verdict, "
            "and the latency-tail record beside the campaign analyses",
        )

    inert = _build_inert_lookups(analyses)
    near_onset = _build_near_onset_arms(analyses, inert)
    saturated = _build_saturated_fits(analyses)
    ceiling = _build_ceiling_fit(pilot_dynamics, ceiling_verdict)
    p50 = _build_p50_fit(tail_p50, ceiling_verdict)

    margin_pp = _crossover_margin_pp(analyses)
    computed = {
        "k_ms_per_unit_capacity": ceiling.k_ms_per_unit_capacity,
        "k_sample_sigma": ceiling.k_sample_sigma,
        "latency_slope_trained_ms_per_unit": saturated[TRAINED_ACTOR].latency_slope_ms_per_unit,
        "latency_slope_baseline_ms_per_unit": saturated[BASELINE_ACTOR].latency_slope_ms_per_unit,
        "crossover_margin_pp": margin_pp,
        "p50_latency_ms": p50.pinned_ms,
    }
    self_test = _self_test_report(computed)
    if not self_test.passed:
        failed = [check.name for check in self_test.checks if not check.passed]
        raise OutcomePredictorError(
            "FIT_SELF_TEST_FAILED",
            f"the fit does not reproduce the published constants ({failed}); "
            "refusing to produce a fit artifact",
        )

    return OutcomePredictorFit(
        generated_at_utc=generated_at_utc,
        sources=tuple(sources),
        trace_slots=dict(TRACE_SLOTS),
        trace_onsets=dict(TRACE_ONSETS),
        capacity_envelope=CAPACITY_ENVELOPE,
        inert=inert,
        near_onset=near_onset,
        saturated=saturated,
        ceiling=ceiling,
        p50=p50,
        self_test=self_test,
    )


def _top_arm_stats(
    analysis: VecCampaignAnalysis,
) -> tuple[str, dict[str, SeedStat]]:
    table = _descriptives_by_arm_metric(analysis)
    arm_labels = {arm for arm, _ in table}
    top_label = max(arm_labels, key=_arm_capacity)
    metrics = {
        metric: _seed_stat(dict(table[(top_label, metric)].seed_values))
        for arm, metric in table
        if arm == top_label
    }
    return top_label, metrics


def _build_inert_lookups(
    analyses: dict[str, tuple[VecCampaignAnalysis, FitSource]],
) -> tuple[InertLookup, ...]:
    lookups: list[InertLookup] = []
    for experiment_id, (analysis, _) in sorted(analyses.items()):
        registered = EXPERIMENT_REGISTRY[experiment_id]
        if registered.role not in ("grid", "baseline_grid"):
            continue
        top_label, metrics = _top_arm_stats(analysis)
        low, high = _measured_capacity_range(analyses, registered.trace, registered.actor)
        lookups.append(
            InertLookup(
                trace=registered.trace,
                actor=registered.actor,
                experiment_id=experiment_id,
                arm_label=top_label,
                metrics=metrics,
                measured_capacity_minimum=low,
                measured_capacity_maximum=high,
            )
        )
    return tuple(lookups)


def _measured_capacity_range(
    analyses: dict[str, tuple[VecCampaignAnalysis, FitSource]],
    trace: str,
    actor: str,
) -> tuple[float, float]:
    """The union of admitted arm capacities for one (trace, actor) pair."""

    capacities: list[float] = []
    for experiment_id, (analysis, _) in analyses.items():
        registered = EXPERIMENT_REGISTRY[experiment_id]
        if registered.trace != trace or registered.actor != actor:
            continue
        for row in [*analysis.primary_descriptives, *analysis.secondary_descriptives]:
            capacities.append(_arm_capacity(row.arm_label))
    return min(capacities), max(capacities)


def _build_near_onset_arms(
    analyses: dict[str, tuple[VecCampaignAnalysis, FitSource]],
    inert: tuple[InertLookup, ...],
) -> tuple[NearOnsetArm, ...]:
    inert_by_key = {(lookup.trace, lookup.actor): lookup for lookup in inert}
    arms: list[NearOnsetArm] = []
    for experiment_id, (analysis, _) in sorted(analyses.items()):
        registered = EXPERIMENT_REGISTRY[experiment_id]
        if registered.role != "deep" or registered.trace == "inc":
            continue
        onset = TRACE_ONSETS[registered.trace]
        table = _descriptives_by_arm_metric(analysis)
        top_by_metric = {
            metric: table[(arm, metric)]
            for arm, metric in table
            if math.isclose(_arm_capacity(arm), 2.5)
        }
        base = inert_by_key[(registered.trace, TRAINED_ACTOR)]
        for arm_label in sorted({arm for arm, _ in table}, key=_arm_capacity):
            capacity = _arm_capacity(arm_label)
            if capacity > onset or math.isclose(capacity, 2.5):
                continue
            metrics: dict[str, SeedStat] = {}
            deltas: dict[str, float] = {}
            for metric in base.metrics:
                row = table.get((arm_label, metric))
                top_row = top_by_metric.get(metric)
                if row is None or top_row is None:
                    continue
                metrics[metric] = _seed_stat(dict(row.seed_values))
                paired = [
                    row.seed_values[seed] - top_row.seed_values[seed]
                    for seed in row.seed_values
                    if seed in top_row.seed_values
                ]
                deltas[metric] = _mean(paired)
            arms.append(
                NearOnsetArm(
                    trace=registered.trace,
                    actor=TRAINED_ACTOR,
                    experiment_id=experiment_id,
                    capacity=capacity,
                    metrics=metrics,
                    deltas_vs_top=deltas,
                )
            )
    return tuple(arms)


def _build_saturated_fits(
    analyses: dict[str, tuple[VecCampaignAnalysis, FitSource]],
) -> dict[str, SaturatedActorFit]:
    slope_source = {
        TRAINED_ACTOR: "vec-capacity-squeeze-pilot",
        BASELINE_ACTOR: "vec-crossover-inc-baseline",
    }
    fits: dict[str, SaturatedActorFit] = {}
    for actor in MEASURED_ACTORS:
        pooled: dict[float, dict[str, dict[str, float]]] = {}
        pooled_sources: dict[float, set[str]] = {}
        offload_values: list[float] = []
        for experiment_id, (analysis, _) in sorted(analyses.items()):
            registered = EXPERIMENT_REGISTRY[experiment_id]
            if registered.trace != "inc" or registered.actor != actor:
                continue
            table = _descriptives_by_arm_metric(analysis)
            for (arm_label, metric), row in table.items():
                capacity = _arm_capacity(arm_label)
                bucket = pooled.setdefault(capacity, {}).setdefault(metric, {})
                bucket.update(row.seed_values)
                pooled_sources.setdefault(capacity, set()).add(experiment_id)
                if metric == METRIC_OFFLOAD:
                    offload_values.extend(row.seed_values.values())
        slope_analysis, _ = analyses[slope_source[actor]]
        slope_table = _descriptives_by_arm_metric(slope_analysis)
        level_means = sorted(
            (
                (_arm_capacity(arm), _mean(list(row.seed_values.values())))
                for (arm, metric), row in slope_table.items()
                if metric == METRIC_LATENCY_MEAN
            )
        )
        slope, intercept = _ols(level_means)
        arms = tuple(
            SaturatedArm(
                capacity=capacity,
                metrics={
                    metric: _seed_stat(seed_values)
                    for metric, seed_values in sorted(pooled[capacity].items())
                },
                source_experiments=tuple(sorted(pooled_sources[capacity])),
            )
            for capacity in sorted(pooled)
        )
        fits[actor] = SaturatedActorFit(
            actor=actor,
            latency_slope_ms_per_unit=slope,
            latency_intercept_ms=intercept,
            slope_source_experiment=slope_source[actor],
            offload_rate_constant=_mean(offload_values),
            offload_rate_minimum=min(offload_values),
            offload_rate_maximum=max(offload_values),
            arms=arms,
        )
    return fits


def _build_ceiling_fit(
    pilot_dynamics: dict[str, object],
    ceiling_verdict: dict[str, object],
) -> CeilingFit:
    cells = pilot_dynamics.get("cells")
    if not isinstance(cells, list):
        raise OutcomePredictorError("SOURCE_INVALID", "pilot dynamics artifact has no cells")
    ratios: list[float] = []
    for cell in cells:
        if not isinstance(cell, dict):
            raise OutcomePredictorError("SOURCE_INVALID", "pilot dynamics cell is not an object")
        label = str(cell["cell"])
        capacity = float(label.split("-fs")[0].removeprefix("cap-"))
        by_class = cell["deadline_slack_by_class"]
        if not isinstance(by_class, dict):
            raise OutcomePredictorError("SOURCE_INVALID", "cell has no per-class block")
        for block in by_class.values():
            ratios.append(float(block["missed_latency"]["p95"]) / capacity)
    verdict_block = ceiling_verdict.get("verdict_block")
    if not isinstance(verdict_block, dict):
        raise OutcomePredictorError("SOURCE_INVALID", "ceiling verdict has no verdict block")
    pairs = verdict_block.get("pairs")
    if not isinstance(pairs, list):
        raise OutcomePredictorError("SOURCE_INVALID", "ceiling verdict has no pairs")
    errors_by_class: dict[tuple[float, str], list[float]] = {}
    for pair in pairs:
        if not isinstance(pair, dict):
            raise OutcomePredictorError("SOURCE_INVALID", "ceiling verdict pair is not an object")
        key = (float(pair["capacity"]), str(pair["task_class"]))
        errors_by_class.setdefault(key, []).append(float(pair["relative_error"]))
    sag: dict[str, float] = {}
    for capacity in sorted({capacity for capacity, _ in errors_by_class}):
        per_class_means = [
            _mean(values) for (cap, _), values in errors_by_class.items() if cap == capacity
        ]
        # The design quotes the worst class's sag (+1.1 → +3.4%); widening by
        # the maximum across classes inherits the law's documented error
        # growth conservatively.
        sag[f"{capacity:g}"] = max(per_class_means)
    return CeilingFit(
        k_ms_per_unit_capacity=_mean(ratios),
        k_sample_sigma=_sample_sigma(ratios),
        pair_count=len(ratios),
        sag_widening_by_capacity=sag,
    )


def _build_p50_fit(
    tail_p50: dict[str, float],
    ceiling_verdict: dict[str, object],
) -> P50Fit:
    secondary = ceiling_verdict.get("secondary")
    if not isinstance(secondary, dict):
        raise OutcomePredictorError("SOURCE_INVALID", "ceiling verdict has no secondary block")
    deep_cells = secondary.get("prediction_3_p50_latency_ms_by_cell")
    if not isinstance(deep_cells, dict) or not deep_cells:
        raise OutcomePredictorError("SOURCE_INVALID", "ceiling verdict has no deep p50 values")
    deep_values = [float(value) for value in deep_cells.values()]
    return P50Fit(
        pinned_ms=_mean(list(tail_p50.values())),
        pilot_arm_values_ms=dict(sorted(tail_p50.items())),
        deep_cell_minimum_ms=min(deep_values),
        deep_cell_maximum_ms=max(deep_values),
    )


def _crossover_margin_pp(
    analyses: dict[str, tuple[VecCampaignAnalysis, FitSource]],
) -> float:
    trained_table = _descriptives_by_arm_metric(analyses["vec-capacity-squeeze-pilot"][0])
    baseline_table = _descriptives_by_arm_metric(analyses["vec-crossover-inc-baseline"][0])
    deltas: list[float] = []
    for (arm, metric), trained_row in sorted(trained_table.items()):
        if metric != METRIC_DEADLINE:
            continue
        baseline_row = baseline_table.get((arm, metric))
        if baseline_row is None:
            continue
        trained_mean = _mean(list(trained_row.seed_values.values()))
        baseline_mean = _mean(list(baseline_row.seed_values.values()))
        deltas.append(trained_mean - baseline_mean)
    return 100.0 * _mean(deltas)


# --- artifact IO -------------------------------------------------------------


def fit_to_json(fit: OutcomePredictorFit) -> str:
    return json.dumps(fit.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False)


def write_fit_artifact(fit: OutcomePredictorFit, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(fit_to_json(fit) + "\n", encoding="utf-8")


def load_outcome_predictor_fit(path: Path) -> LoadedFit:
    """Load a fit artifact; the self-test gate re-runs before it may predict."""

    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise OutcomePredictorError(
            "FIT_ARTIFACT_UNREADABLE", f"fit artifact {path.name} could not be read"
        ) from exc
    try:
        fit = OutcomePredictorFit.model_validate_json(raw)
    except ValidationError as exc:
        raise OutcomePredictorError(
            "FIT_ARTIFACT_INVALID", f"fit artifact {path.name} failed validation"
        ) from exc
    computed = {
        "k_ms_per_unit_capacity": fit.ceiling.k_ms_per_unit_capacity,
        "k_sample_sigma": fit.ceiling.k_sample_sigma,
        "latency_slope_trained_ms_per_unit": fit.saturated[TRAINED_ACTOR].latency_slope_ms_per_unit,
        "latency_slope_baseline_ms_per_unit": fit.saturated[
            BASELINE_ACTOR
        ].latency_slope_ms_per_unit,
        "crossover_margin_pp": _stored_margin(fit),
        "p50_latency_ms": fit.p50.pinned_ms,
    }
    report = _self_test_report(computed)
    if not report.passed or not fit.self_test.passed:
        failed = [check.name for check in report.checks if not check.passed]
        raise OutcomePredictorError(
            "FIT_SELF_TEST_FAILED",
            f"fit artifact {path.name} does not reproduce the published constants "
            f"({failed}); refusing to load",
        )
    return LoadedFit(fit=fit, digest=hashlib.sha256(raw).hexdigest())


def _stored_margin(fit: OutcomePredictorFit) -> float:
    """Recompute the crossover margin from the stored per-seed arm tables."""

    trained = {arm.capacity: arm for arm in fit.saturated[TRAINED_ACTOR].arms}
    baseline = {arm.capacity: arm for arm in fit.saturated[BASELINE_ACTOR].arms}
    deltas: list[float] = []
    for capacity in sorted(set(trained) & set(baseline)):
        trained_stat = trained[capacity].metrics.get(METRIC_DEADLINE)
        baseline_stat = baseline[capacity].metrics.get(METRIC_DEADLINE)
        if trained_stat is None or baseline_stat is None:
            continue
        # The margin is defined over the slope-source campaigns' seeds (the
        # crossover verdict's own frame): pilot seeds {0,1,2} against the
        # baseline campaign's seeds {0,1,2}.
        trained_values = [
            value for seed, value in trained_stat.seed_values.items() if seed in {"0", "1", "2"}
        ]
        baseline_values = [
            value for seed, value in baseline_stat.seed_values.items() if seed in {"0", "1", "2"}
        ]
        if not trained_values or not baseline_values:
            continue
        deltas.append(_mean(trained_values) - _mean(baseline_values))
    return 100.0 * _mean(deltas)


# --- prediction --------------------------------------------------------------


def _t95(count: int) -> float:
    return _T95_BY_DF.get(count - 1, _T95_FALLBACK)


def _interval_from_stat(stat: SeedStat) -> tuple[float, float]:
    """Seed min/max unioned with the 95% t-interval — the design's rule."""

    values = list(stat.seed_values.values())
    if len(values) < 2:
        return stat.minimum, stat.maximum
    half_width = _t95(len(values)) * _sample_sigma(values) / math.sqrt(len(values))
    return min(stat.minimum, stat.mean - half_width), max(stat.maximum, stat.mean + half_width)


def _refusal(code: str, detail: str, closing_campaign: str, digest: str) -> PredictionRefusal:
    return PredictionRefusal(
        code=code, detail=detail, closing_campaign=closing_campaign, fit_digest=digest
    )


def _validate_scenario(scenario: VecScenario, digest: str) -> PredictionRefusal | None:
    if scenario.trace not in TRACE_SLOTS:
        return _refusal(
            "TRACE_NOT_MEASURED",
            f"trace '{scenario.trace}' is not one of the five admitted traces "
            f"{sorted(TRACE_SLOTS)}",
            "audited admission of the trace via the reviewed-allowlist pattern "
            "(ADR-062/065/066), then a capacity campaign on it",
            digest,
        )
    low, high = CAPACITY_ENVELOPE
    if not (low <= scenario.capacity <= high):
        return _refusal(
            "CAPACITY_OUT_OF_ENVELOPE",
            f"capacity {scenario.capacity:g} is outside the tested envelope "
            f"[{low:g}, {high:g}]; extrapolating beyond it is exactly what the "
            "ceiling-law BOUNDED verdict warns against",
            "a capacity campaign extending the tested envelope at the requested level",
            digest,
        )
    if scenario.fleet_preset != MEASURED_FLEET_PRESET:
        return _refusal(
            "FLEET_PRESET_NOT_MEASURED",
            f"fleet preset '{scenario.fleet_preset}' has no measured cells; only "
            f"'{MEASURED_FLEET_PRESET}' was measured",
            "the predeclared fleet-composition campaign (3 cells, awaiting the "
            "owner's launch decision)",
            digest,
        )
    if scenario.fleet_size is not None and scenario.fleet_size != TRACE_SLOTS[scenario.trace]:
        gap_low, gap_high = DENSITY_GAP_EXCLUSIVE
        if gap_low < scenario.fleet_size < gap_high:
            return _refusal(
                "DENSITY_GAP",
                f"fleet size {scenario.fleet_size} falls in the unmeasured density band "
                f"({gap_low}, {gap_high}) — where the real observed bus fleet "
                "(~1,216 concurrent) lives",
                "an intermediate-density measuring campaign; no admitted trace "
                "carries a fleet size inside this band",
                digest,
            )
        return _refusal(
            "TRACE_NOT_MEASURED",
            f"no admitted trace carries fleet size {scenario.fleet_size}; measured "
            f"sizes are {dict(sorted(TRACE_SLOTS.items()))}",
            "audited admission of a trace at that density via the reviewed-allowlist "
            "pattern (ADR-062/065/066)",
            digest,
        )
    if scenario.actor not in MEASURED_ACTORS:
        return _refusal(
            "ACTOR_NOT_MEASURED",
            f"actor '{scenario.actor}' is not one of the two audited checkpoints "
            f"{list(MEASURED_ACTORS)}",
            "audited admission of the checkpoint, then a measuring campaign on the requested trace",
            digest,
        )
    return None


def predict(scenario: VecScenario, loaded: LoadedFit) -> PredictionRecord | PredictionRefusal:
    """One scenario in, exactly one typed output out — prediction xor refusal."""

    fit = loaded.fit
    digest = loaded.digest
    refusal = _validate_scenario(scenario, digest)
    if refusal is not None:
        return refusal

    if scenario.trace == "inc":
        return _predict_saturated(scenario, fit, digest)

    lookup = next(
        (
            entry
            for entry in fit.inert
            if entry.trace == scenario.trace and entry.actor == scenario.actor
        ),
        None,
    )
    if lookup is None:
        return _refusal(
            "ACTOR_NOT_MEASURED",
            f"the pair (trace '{scenario.trace}', actor '{scenario.actor}') has no admitted cells",
            f"a baseline-actor grid leg on '{scenario.trace}' mirroring vec-baseline-invariance-ev",
            digest,
        )
    if scenario.capacity < lookup.measured_capacity_minimum:
        return _refusal(
            "ACTOR_CAPACITY_NOT_MEASURED",
            f"capacity {scenario.capacity:g} is below actor '{scenario.actor}''s "
            f"measured range [{lookup.measured_capacity_minimum:g}, "
            f"{lookup.measured_capacity_maximum:g}] on trace '{scenario.trace}' — "
            "inside the global envelope but outside this pair's admitted cells; "
            "the measured domain is not a Cartesian product",
            f"a deep capacity leg on '{scenario.trace}' for actor "
            f"'{scenario.actor}' extending its admitted arms",
            digest,
        )
    onset = fit.trace_onsets[scenario.trace]
    if scenario.capacity > onset:
        return _predict_inert(scenario, fit, lookup, digest)
    return _predict_near_onset(scenario, fit, lookup, onset, digest)


_OFF_SATURATION_UNAVAILABLE = {
    METRIC_P50: (
        "p50 latency was measured only on the saturated inc trace "
        "(the latency-tail analysis is inc-only)"
    ),
    METRIC_CEILING: (
        "the tail ceiling was measured only on the saturated inc trace "
        "(the ceiling law is an RSU-queue property of the collapse hour)"
    ),
}


def _metric_predictions_from_lookup(
    lookup: InertLookup, *, delta_by_metric: dict[str, float] | None, basis: str
) -> tuple[MetricPrediction, ...]:
    predictions: list[MetricPrediction] = []
    for metric in (METRIC_DEADLINE, METRIC_LATENCY_MEAN, METRIC_OFFLOAD):
        stat = lookup.metrics.get(metric)
        if stat is None:
            continue
        delta = (delta_by_metric or {}).get(metric, 0.0)
        interval_low, interval_high = _interval_from_stat(stat)
        predictions.append(
            MetricPrediction(
                metric=metric,
                point=stat.mean + delta,
                interval_low=interval_low + delta,
                interval_high=interval_high + delta,
                seed_support=stat.count,
                interval_basis=basis,
            )
        )
    return tuple(predictions)


def _predict_inert(
    scenario: VecScenario, fit: OutcomePredictorFit, lookup: InertLookup, digest: str
) -> PredictionRecord:
    seed_count = len(next(iter(lookup.metrics.values())).seed_values)
    basis = (
        f"seed min/max ∪ 95% t-interval over {seed_count} seeds at "
        f"{lookup.arm_label} ({lookup.experiment_id}); paired capacity "
        "differences measured exactly zero above the onset"
    )
    return PredictionRecord(
        scenario=scenario,
        regime="measured_inert",
        metrics=_metric_predictions_from_lookup(lookup, delta_by_metric=None, basis=basis),
        metrics_unavailable=dict(_OFF_SATURATION_UNAVAILABLE),
        sources=(lookup.experiment_id,),
        fit_digest=digest,
        caveats=(
            *_STANDING_CAVEATS,
            f"capacity is measured inert on '{scenario.trace}' above onset "
            f"{fit.trace_onsets[scenario.trace]:g}: this is an honest lookup of the "
            "measured top-capacity descriptives and declares itself one",
        ),
    )


def _predict_near_onset(
    scenario: VecScenario,
    fit: OutcomePredictorFit,
    lookup: InertLookup,
    onset: float,
    digest: str,
) -> PredictionRecord:
    candidates = [arm for arm in fit.near_onset if arm.trace == scenario.trace]
    sources: tuple[str, ...] = (lookup.experiment_id,)
    delta_by_metric: dict[str, float] = {}
    caveat = (
        f"at/below the measured onset {onset:g} on '{scenario.trace}' with no measured "
        "deep arm; the onset itself is the measured fact"
    )
    if candidates:
        nearest = min(candidates, key=lambda arm: abs(arm.capacity - scenario.capacity))
        delta_by_metric = dict(nearest.deltas_vs_top)
        sources = (lookup.experiment_id, nearest.experiment_id)
        caveat = (
            f"correction from the measured cap-{nearest.capacity:g} arm of "
            f"{nearest.experiment_id} (trained actor); onsets are per-trace lookups — "
            "the onset-scaling prediction was REFUTED, so nothing here interpolates "
            "across traces"
        )
    basis = "seed min/max ∪ 95% t-interval at the top arm, shifted by the measured near-onset delta"
    return PredictionRecord(
        scenario=scenario,
        regime="near_onset",
        metrics=_metric_predictions_from_lookup(
            lookup, delta_by_metric=delta_by_metric, basis=basis
        ),
        metrics_unavailable=dict(_OFF_SATURATION_UNAVAILABLE),
        sources=sources,
        fit_digest=digest,
        caveats=(*_STANDING_CAVEATS, caveat),
    )


def _sag_fraction(fit: OutcomePredictorFit, capacity: float) -> float:
    if capacity >= 0.75:
        return 0.0
    sag = fit.ceiling.sag_widening_by_capacity
    if not sag:
        return 0.0
    nearest = min(sag, key=lambda key: abs(float(key) - capacity))
    return sag[nearest]


def _predict_saturated(
    scenario: VecScenario, fit: OutcomePredictorFit, digest: str
) -> PredictionRecord | PredictionRefusal:
    actor_fit = fit.saturated.get(scenario.actor)
    if actor_fit is None:
        return _refusal(
            "ACTOR_NOT_MEASURED",
            f"actor '{scenario.actor}' has no admitted inc cells",
            "a measuring campaign on inc for the checkpoint",
            digest,
        )
    capacity = scenario.capacity
    arms_by_capacity = {arm.capacity: arm for arm in actor_fit.arms}
    smallest_arm = min(arms_by_capacity)
    if capacity < smallest_arm:
        # Review-conformance (1 August): inside the global envelope but below
        # this actor's smallest admitted inc arm — refuse, never line-extrapolate.
        return _refusal(
            "ACTOR_CAPACITY_NOT_MEASURED",
            f"capacity {capacity:g} is below actor '{scenario.actor}''s measured "
            f"inc range [{smallest_arm:g}, {max(arms_by_capacity):g}] — inside the "
            "global envelope but outside this pair's admitted cells; the measured "
            "domain is not a Cartesian product",
            f"a deep-inc capacity leg for actor '{scenario.actor}' mirroring vec-capacity-deep-inc",
            digest,
        )
    nearest_capacity = min(arms_by_capacity, key=lambda value: abs(value - capacity))
    nearest = arms_by_capacity[nearest_capacity]
    exact = math.isclose(nearest_capacity, capacity, rel_tol=0.0, abs_tol=1e-9)
    sag = _sag_fraction(fit, capacity)
    metrics: list[MetricPrediction] = []
    unavailable: dict[str, str] = {}
    caveats: list[str] = [*_STANDING_CAVEATS]

    deadline_stat = nearest.metrics.get(METRIC_DEADLINE)
    if deadline_stat is not None:
        low, high = _interval_from_stat(deadline_stat)
        metrics.append(
            MetricPrediction(
                metric=METRIC_DEADLINE,
                point=deadline_stat.mean,
                interval_low=low,
                interval_high=high,
                seed_support=deadline_stat.count,
                interval_basis=(
                    f"seed min/max ∪ 95% t-interval at the nearest measured arm "
                    f"cap-{nearest_capacity:g} ({', '.join(nearest.source_experiments)}); "
                    "attainment is flat with the measured faint deep-squeeze rise"
                ),
            )
        )
    else:
        unavailable[METRIC_DEADLINE] = (
            "no admitted deadline descriptives at the nearest measured arm"
        )

    latency_stat = nearest.metrics.get(METRIC_LATENCY_MEAN)
    if latency_stat is not None:
        if exact:
            point = latency_stat.mean
            low, high = _interval_from_stat(latency_stat)
        else:
            point = actor_fit.latency_intercept_ms + actor_fit.latency_slope_ms_per_unit * capacity
            near_low, near_high = _interval_from_stat(latency_stat)
            half_width = (near_high - near_low) / 2.0
            widened = half_width * (1.0 + sag)
            low, high = point - widened, point + widened
        metrics.append(
            MetricPrediction(
                metric=METRIC_LATENCY_MEAN,
                point=point,
                interval_low=low,
                interval_high=high,
                seed_support=latency_stat.count,
                interval_basis=(
                    "measured arm lookup"
                    if exact
                    else (
                        f"OLS line ({actor_fit.slope_source_experiment}: slope "
                        f"{actor_fit.latency_slope_ms_per_unit:.1f} ms/unit) with the "
                        f"nearest arm's seed spread"
                        + (f", widened {sag:+.2%} by the measured sag" if sag else "")
                    )
                ),
            )
        )

    offload_seeds = {
        seed
        for arm in actor_fit.arms
        if METRIC_OFFLOAD in arm.metrics
        for seed in arm.metrics[METRIC_OFFLOAD].seed_values
    }
    metrics.append(
        MetricPrediction(
            metric=METRIC_OFFLOAD,
            point=actor_fit.offload_rate_constant,
            interval_low=actor_fit.offload_rate_minimum,
            interval_high=actor_fit.offload_rate_maximum,
            seed_support=len(offload_seeds),
            interval_basis=(
                "constant per actor (the offload partition is bit-identical across "
                "capacities); interval = min/max over all admitted arms and seeds"
            ),
        )
    )

    if scenario.actor == TRAINED_ACTOR:
        ceiling_point = fit.ceiling.k_ms_per_unit_capacity * capacity
        ceiling_half = 2.0 * fit.ceiling.k_sample_sigma * capacity
        ceiling_half *= 1.0 + sag
        metrics.append(
            MetricPrediction(
                metric=METRIC_CEILING,
                point=ceiling_point,
                interval_low=ceiling_point - ceiling_half,
                interval_high=ceiling_point + ceiling_half,
                seed_support=fit.ceiling.pair_count,
                interval_basis=(
                    f"ceiling law K x capacity (K = "
                    f"{fit.ceiling.k_ms_per_unit_capacity:.1f} ms/unit, ±2 sample sigma "
                    f"over {fit.ceiling.pair_count} cell-class pairs)"
                    + (f", widened {sag:+.2%} by the measured sag" if sag else "")
                ),
            )
        )
        if capacity >= 0.75:
            p50_low = min(fit.p50.pilot_arm_values_ms.values())
            p50_high = max(fit.p50.pilot_arm_values_ms.values())
            p50_basis = "pinned; identical at every measured pilot arm"
        else:
            p50_low = min(fit.p50.pinned_ms, fit.p50.deep_cell_minimum_ms)
            p50_high = fit.p50.deep_cell_maximum_ms
            p50_basis = (
                "pinned at the pilot value; interval widened to the measured deep-arm "
                "spread (the ceiling verdict recorded a partial p50 miss at one seed)"
            )
        metrics.append(
            MetricPrediction(
                metric=METRIC_P50,
                point=fit.p50.pinned_ms,
                interval_low=p50_low,
                interval_high=p50_high,
                seed_support=len(fit.p50.pilot_arm_values_ms),
                interval_basis=p50_basis,
            )
        )
    else:
        unavailable[METRIC_CEILING] = (
            "the ceiling law was measured on the trained actor's admitted cells only; "
            "a baseline deep-inc leg would close this"
        )
        unavailable[METRIC_P50] = (
            "p50 latency was measured on the trained actor's admitted cells only; "
            "a baseline latency-tail analysis would close this"
        )
    return PredictionRecord(
        scenario=scenario,
        regime="saturated",
        metrics=tuple(metrics),
        metrics_unavailable=unavailable,
        sources=tuple(
            sorted({source for arm in actor_fit.arms for source in arm.source_experiments})
        ),
        fit_digest=digest,
        caveats=tuple(caveats),
    )
