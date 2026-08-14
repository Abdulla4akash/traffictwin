# ruff: noqa: E501, ANN401
"""Strategy semantics service for E3 product campaign — Lane 10 (no-inference).

Strict deterministic typed descriptions for ingress_dla, per_task_dla, p2c_dla
placements and fixed_1x, static_overprovisioned, reactive, proactive scalings,
plus staleness handling. Covers radio ingress, execution placement, admission,
forwarding, actor/infrastructure authority, learned/deterministic status,
evidence level and limitations. Queue capacity is waiting-room slots,
compute capacity is service units, resource cost is resource_unit_seconds not
money. Truth anchor is the frozen E3 contract at
docs/evaluation/e3/e3_dynamic_resource_v2_contract_v2.json (base
211a6662151ccad43187f8a2ce3f75a57515408d) with no results available.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from traffictwin.experiments.e3_research_evidence import (
    E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED,
    LANE_09,
    NO_E3_RESEARCH_RESULTS_AVAILABLE,
    NOT_EXECUTED,
)

PlacementId = Literal["ingress_dla", "per_task_dla", "p2c_dla"]
ScalingId = Literal["fixed_1x", "static_overprovisioned", "reactive", "proactive"]

_ALLOWED_PLACEMENTS: Final[tuple[PlacementId, ...]] = ("ingress_dla", "per_task_dla", "p2c_dla")
_ALLOWED_SCALINGS: Final[tuple[ScalingId, ...]] = (
    "fixed_1x",
    "static_overprovisioned",
    "reactive",
    "proactive",
)
_ALLOWED_STATE_AGES: Final[tuple[int, ...]] = (0, 1000, 3000)

_HOLD_NOTE: Final[str] = (
    f"Evidence state {NOT_EXECUTED}, result {NO_E3_RESEARCH_RESULTS_AVAILABLE}, "
    f"{E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED}, {LANE_09}, research_workloads_launched = 0. "
    "No E3 research results exist; this service describes typed semantics for the staged designs "
    "without empirical claims."
)


def _contains_affirming(text: str, phrase: str) -> bool:
    lower = text.lower()
    needle = phrase.lower()
    start = 0
    while True:
        idx = lower.find(needle, start)
        if idx == -1:
            return False
        prefix = lower[max(0, idx - 24) : idx]
        has_negation = any(
            token in prefix
            for token in ("not ", "no ", "never", "without", "is not", "are not", "isn't", "isnt")
        )
        if has_negation:
            start = idx + len(needle)
            continue
        return True


def _validate_text_fields(sem: E3StrategySemantics) -> None:
    texts: list[str] = [
        sem.human_label,
        sem.radio_ingress,
        sem.execution_placement,
        sem.admission,
        sem.forwarding,
        sem.actor_authority,
        sem.infrastructure_authority,
        sem.scaling_semantics,
        sem.staleness_semantics,
        sem.queue_capacity_note,
        sem.compute_capacity_note,
        sem.resource_cost_note,
        sem.evidence_level,
        sem.limitations,
    ]

    def _any_has(phrase: str) -> bool:
        return any(_contains_affirming(t, phrase) for t in texts)

    # No actor selects execution RSU
    for phrase in (
        "actor selects execution",
        "actor selects rsu",
        "actor_selects_rsu",
        "mappo selects execution",
        "actor selects",
    ):
        if _any_has(phrase):
            raise ValueError(
                f"strategy {sem.placement_id}/{sem.scaling_id}: forbidden actor selects execution claim"
            )
    # No Kubernetes actual deployment
    for phrase in (
        "kubernetes deployment",
        "kubernetes cluster",
        "cluster orchestration",
        "actual kubernetes",
    ):
        if _any_has(phrase):
            raise ValueError(
                f"strategy {sem.placement_id}/{sem.scaling_id}: forbidden kubernetes claim"
            )
    # No learned placement when deterministic
    if sem.is_deterministic and sem.is_learned:
        raise ValueError(
            f"strategy {sem.placement_id}/{sem.scaling_id}: deterministic must not be learned"
        )
    for phrase in ("learned placement", "learned scheduler", "learned jsq"):
        if _any_has(phrase):
            raise ValueError(
                f"strategy {sem.placement_id}/{sem.scaling_id}: forbidden learned placement"
            )
    # Queue vs compute conflation
    for phrase in ("queue ceiling is compute", "queue_ceiling_is_compute", "queue ceiling is"):
        if _any_has(phrase):
            raise ValueError(
                f"strategy {sem.placement_id}/{sem.scaling_id}: forbidden queue/compute conflation"
            )
    # Monetary cost language
    for phrase in ("cost dollars", "cost_currency", "monetary cost", "cost billing", "dollars"):
        if _any_has(phrase):
            raise ValueError(
                f"strategy {sem.placement_id}/{sem.scaling_id}: forbidden monetary cost language"
            )
    # Tasks-as-N or Manchester-wide inference
    for phrase in (
        "task as n",
        "tasks as n",
        "tasks_as_n",
        "manchester-wide",
        "population-wide",
        "universal superiority",
    ):
        if _any_has(phrase):
            raise ValueError(
                f"strategy {sem.placement_id}/{sem.scaling_id}: forbidden inference claim"
            )
    # Supervisor approval
    for phrase in ("supervisor approved", "randy confirmed"):
        if _any_has(phrase):
            raise ValueError(
                f"strategy {sem.placement_id}/{sem.scaling_id}: forbidden supervisor approval claim"
            )


def _validate_semantics(sem: E3StrategySemantics) -> None:
    if sem.placement_id not in _ALLOWED_PLACEMENTS:
        raise ValueError(f"unknown placement {sem.placement_id!r}")
    if sem.scaling_id not in _ALLOWED_SCALINGS:
        raise ValueError(f"unknown scaling {sem.scaling_id!r}")
    if sem.state_age_ms not in _ALLOWED_STATE_AGES:
        raise ValueError(f"state_age_ms {sem.state_age_ms!r} not in {list(_ALLOWED_STATE_AGES)}")
    for field_name in (
        "human_label",
        "radio_ingress",
        "execution_placement",
        "admission",
        "forwarding",
        "actor_authority",
        "infrastructure_authority",
        "scaling_semantics",
        "staleness_semantics",
        "queue_capacity_note",
        "compute_capacity_note",
        "resource_cost_note",
        "evidence_level",
        "limitations",
    ):
        val = getattr(sem, field_name)
        if not isinstance(val, str) or len(val.strip()) < 10:
            raise ValueError(
                f"strategy {sem.placement_id}/{sem.scaling_id}: {field_name} must be substantive"
            )
    if sem.is_learned not in (True, False) or sem.is_deterministic not in (True, False):
        raise ValueError("is_learned/is_deterministic must be bool")
    if sem.is_learned is True:
        raise ValueError("is_learned must be False, placement/scaling are deterministic")
    if sem.is_deterministic is not True:
        raise ValueError("is_deterministic must be True")
    if sem.state_age_ms not in (0, 1000, 3000):
        raise ValueError("state_age_ms must be typed int milliseconds 0/1000/3000")
    if "resource_unit_seconds" not in sem.resource_cost_note.lower():
        raise ValueError("resource_cost_note must mention resource_unit_seconds")
    if (
        "queue" not in sem.queue_capacity_note.lower()
        and "waiting" not in sem.queue_capacity_note.lower()
    ):
        raise ValueError("queue_capacity_note must mention queue/waiting-room")
    if "compute" not in sem.compute_capacity_note.lower():
        raise ValueError("compute_capacity_note must mention compute")
    # evidence_level must mention NOT_EXECUTED and NO_E3...
    if (
        NOT_EXECUTED not in sem.evidence_level
        and NO_E3_RESEARCH_RESULTS_AVAILABLE not in sem.evidence_level
    ):
        raise ValueError("evidence_level must mention hold state")
    _validate_text_fields(sem)


@dataclass(frozen=True)
class E3StrategySemantics:
    """Deterministic typed description for one E3 placement x scaling x state_age arm."""

    placement_id: PlacementId
    scaling_id: ScalingId
    state_age_ms: int
    human_label: str
    radio_ingress: str
    execution_placement: str
    admission: str
    forwarding: str
    actor_authority: str
    infrastructure_authority: str
    scaling_semantics: str
    staleness_semantics: str
    queue_capacity_note: str
    compute_capacity_note: str
    resource_cost_note: str
    is_learned: bool
    is_deterministic: bool
    evidence_level: str
    limitations: str

    def __post_init__(self) -> None:
        _validate_semantics(self)


# ---------------------------------------------------------------------------
# Canonical instances — 14 arms x 3 placements? We provide examples for the
# core factor combinations, not empirical results. The service enumerates the
# dormant design without claiming outcomes.
# ---------------------------------------------------------------------------

_INGRESS_FIXED_0 = E3StrategySemantics(
    placement_id="ingress_dla",
    scaling_id="fixed_1x",
    state_age_ms=0,
    human_label="ingress_dla with fixed_1x at state_age 0 ms — strongest-link execution plus deadline gate, 1 compute unit",
    radio_ingress="Strongest-link ingress: best_rsu_idx per vehicle determines ingress RSU; radio viability is current, not stale.",
    execution_placement="Strongest-link execution only: selected execution equals ingress RSU, no p2c or per-task recomputation. Deterministic.",
    admission="Deadline-aware gate at ingress: effective_busy_ms[selected] < TASK_DEADLINE_MS, strict backlog-only, stale view plus same-tick reservation overlay where applicable. Execution is -1 for rejected.",
    forwarding="Never forwarded when placement equals ingress; forwarded is 0 when this arm runs, null with reason before execution. Zero backhaul idealisation remains.",
    actor_authority="Frozen MAPPO actor does not observe RSU load and does not select execution RSU. Actor emits Local/V2I/V2V intent only.",
    infrastructure_authority="Infrastructure placement is degenerate (ingress) and admission is deadline gate; deterministic, not learned, not Kubernetes deployment.",
    scaling_semantics="fixed_1x: 1 active compute unit per RSU, drain = min(backlog, 1000) per tick, latency = work_ahead + own_service. No scaling actions.",
    staleness_semantics="state_age_ms 0: decision backlog is fresh immutable view plus overlay; no staleness delay, true state not mutated by stale view.",
    queue_capacity_note="Queue capacity is waiting-room tasks per RSU (6220 ceiling at 2.5x), strictly separate from compute service capacity.",
    compute_capacity_note="Compute capacity is active units 1..3 per RSU, each drains 1000 work_ms per second; not queue slots.",
    resource_cost_note="Resource cost is resource_unit_seconds = sum over RSU sum over interval active_units * interval_seconds, normalized usage not money, never dollars.",
    is_learned=False,
    is_deterministic=True,
    evidence_level="IMPLEMENTATION-VERIFIED FACT + " + _HOLD_NOTE + " No empirical offering.",
    limitations="Bounded to staged design E3a; no E3 results. Tasks are accounting records, not replicates; no Manchester-wide inference; no universal superiority.",
)

_PER_TASK_FIXED_0 = E3StrategySemantics(
    placement_id="per_task_dla",
    scaling_id="fixed_1x",
    state_age_ms=0,
    human_label="per_task_dla with fixed_1x at state_age 0 ms — per-task least-busy plus deadline gate, 1 unit",
    radio_ingress="Strongest-link ingress per vehicle; ingress radio checked post-placement eligibility; current viability not stale.",
    execution_placement="Per-task sequential least-busy: recompute argmin(effective_busy_ms) over 10 RSUs per V2I candidate in deterministic padded-slot order, with immediate reservation overlay. Tie to lowest RSU id.",
    admission="Same deadline gate at per-task selected target; backlog-only, gate-before-cap precedence, rejected work never reserved; -1 execution for rejected.",
    forwarding="Forwarding when per-task target differs from ingress and gate passes; before execution this count is null with reason, not zero.",
    actor_authority="Frozen MAPPO actor does not observe RSU load nor select execution RSU; infrastructure selects target deterministically.",
    infrastructure_authority="Infrastructure placement recomputes per task; admission is DLA gate; deterministic scheduling, not learned, not actual Kubernetes.",
    scaling_semantics="fixed_1x: 1 compute unit, no scaling receipts, per-RSU capacity 1000 work_ms per tick.",
    staleness_semantics="state_age_ms 0: fresh view; stale snapshot not delayed; true backlog unchanged by observed view.",
    queue_capacity_note="Queue capacity (waiting-room ceiling) uses current true occupancy plus same-tick reservations; not compute capacity.",
    compute_capacity_note="Compute capacity 1..3 units per RSU defines drain per tick; queue slots do not define drain.",
    resource_cost_note="Cost is resource_unit_seconds per RSU per tick = active_units * 1, summed; no monetary billing.",
    is_learned=False,
    is_deterministic=True,
    evidence_level="IMPLEMENTATION-VERIFIED FACT + " + _HOLD_NOTE,
    limitations="One Manchester incident hour, provisional uk2030 fleet, 3600-step cells not yet run. Hold blocks inference.",
)

_P2C_FIXED_0 = E3StrategySemantics(
    placement_id="p2c_dla",
    scaling_id="fixed_1x",
    state_age_ms=0,
    human_label="p2c_dla with fixed_1x at state_age 0 ms — power-of-two-choices feasibility-first plus gate, 1 unit",
    radio_ingress="Strongest-link ingress per vehicle; candidate feasibility determines the p2c pair eligibility before hash mapping.",
    execution_placement="P2C feasibility-first: two candidate hashes via SplitMix64 over (evaluator_seed, fleet_seed, outer_tick, task_slot, ordinal) mapped to distinct feasible RSUs without replacement, choose lower effective_busy_ms. Inspect only pair, not all RSUs. Uniformity not claimed; modulo bias noted.",
    admission="Deadline gate at p2c-chosen RSU; same strict backlog rule, gate-before-cap, -1 execution for rejected, rejected never drains.",
    forwarding="Forwarding when p2c target differs from ingress; null with reason before execution; latency estimate is backlog/u.",
    actor_authority="Frozen actor does not observe load and does not choose p2c pair; infrastructure p2c mapper chooses deterministically.",
    infrastructure_authority="Infrastructure p2c placement is deterministic pseudo-random mapper, not learned, not Kubernetes.",
    scaling_semantics="fixed_1x: 1 active unit per RSU; no scale actions; resource time even when idle.",
    staleness_semantics="state_age_ms 0 fresh; p2c uses current or delayed immutable backlog view but never mutates true state.",
    queue_capacity_note="Queue ceiling counts tasks waiting; distinct from compute units; strain does not change drain.",
    compute_capacity_note="Compute units 1..3 set drain capacity per tick; queue fullness does not equal compute.",
    resource_cost_note="Resource cost resource_unit_seconds stays required for diagnostic deadline per cost; zero cost not fabricated.",
    is_learned=False,
    is_deterministic=True,
    evidence_level="IMPLEMENTATION-VERIFIED FACT + " + _HOLD_NOTE,
    limitations="P2C pair mapping uses SplitMix64 modulo, not proven uniform; H1 remains hypothesis. No empirical coverage under staleness.",
)

_PER_TASK_REACTIVE_0 = E3StrategySemantics(
    placement_id="per_task_dla",
    scaling_id="reactive",
    state_age_ms=0,
    human_label="per_task_dla with reactive at state_age 0 ms — per-task placement plus workload-reactive scaling",
    radio_ingress="Same ingress as per_task_dla; scaling does not change radio.",
    execution_placement="Same per-task least-busy recomputation per candidate.",
    admission="Same deadline gate; scaling applied before tick decision, not retroactively repriced.",
    forwarding="Same forwarding semantics as per_task_dla; scaling may change backlog but not radio.",
    actor_authority="Frozen actor does not observe load nor select scaling; scaling loop is infrastructure rule.",
    infrastructure_authority="Reactive scaling is deterministic threshold rule on service_workload_ms (raw backlog), not learned; gap hysteresis 600 ms, cooldown 5000 ms, actuation 2000 ms, one level per action, max 1 pending.",
    scaling_semantics="Reactive: scale_up inclusive at >=800 ms, scale_down inclusive at <=200 ms, stable in between, per-RSU, no prediction, threshold_gap 600 ms is hysteresis.",
    staleness_semantics="state_age_ms 0 for decision staleness; reactive signal uses raw backlog independent of capacity.",
    queue_capacity_note="Queue ceiling still task-count based, not compute; scaling does not change ceiling.",
    compute_capacity_note="Compute scales 1..3 units; drain scales with active units; queue occupancy not denominator for utilization.",
    resource_cost_note="Resource cost resource_unit_seconds increases with scaled units even when idle; no dollars.",
    is_learned=False,
    is_deterministic=True,
    evidence_level="IMPLEMENTATION-VERIFIED FACT + " + _HOLD_NOTE,
    limitations="Reactive thresholds are gap-hysteresis baseline, not optimal tuning; no results to infer.",
)

_PER_TASK_PROACTIVE_0 = E3StrategySemantics(
    placement_id="per_task_dla",
    scaling_id="proactive",
    state_age_ms=0,
    human_label="per_task_dla with proactive at state_age 0 ms — per-task placement plus transparent proactive forecast",
    radio_ingress="Same ingress; no change.",
    execution_placement="Same per-task placement.",
    admission="Same gate; scaling decisions use only samples at or before observation time, no future leakage.",
    forwarding="Same as per_task_dla.",
    actor_authority="Frozen actor never observes load; proactive forecast is infrastructure, not actor.",
    infrastructure_authority="Proactive is transparent baseline forecasting mean(trend) with window 4 arrivals, not ML optimal; formulas: recent_mean minus older_mean as trend, forecast max(0, mean+2*trend). Deterministic.",
    scaling_semantics="Proactive: horizon 2000 ms, window 4, interval 1000 ms, warm-up 4 observations, thresholds 800/200 ms inclusive, same bounds and delays as reactive.",
    staleness_semantics="state_age_ms 0; observation uses arrival_work_ms raw, not capacity-normalized.",
    queue_capacity_note="Queue task slots separate; proactive does not change queue size.",
    compute_capacity_note="Compute units 1..3; scaling before latency and drain; backlog invariant baseline.",
    resource_cost_note="Cost is resource_unit_seconds; extra units add cost even with no tasks; non-monetary.",
    is_learned=False,
    is_deterministic=True,
    evidence_level="IMPLEMENTATION-VERIFIED FACT + " + _HOLD_NOTE,
    limitations="Proactive is transparent baseline not claimed optimal; negative or null results acceptable.",
)

_PER_TASK_STATIC_0 = E3StrategySemantics(
    placement_id="per_task_dla",
    scaling_id="static_overprovisioned",
    state_age_ms=0,
    human_label="per_task_dla with static_overprovisioned at state_age 0 ms — per-task placement plus 3x compute",
    radio_ingress="Same ingress.",
    execution_placement="Same per-task placement.",
    admission="Same gate; more capacity may admit more but gate still strict backlog check.",
    forwarding="Same forwarding as per_task_dla; target differs from ingress when selected differs, otherwise not forwarded.",
    actor_authority="Frozen actor does not select compute scale.",
    infrastructure_authority="Static_overprovisioned is 3 active units per RSU from tick 0, rsu_service_mult 3.0, not queue.",
    scaling_semantics="Static: 3 units constant, drain = min(backlog, 3000) per tick, latency = raw/backlog/u. No scale actions.",
    staleness_semantics="state_age 0 fresh; scaling not dependent on staleness.",
    queue_capacity_note="Queue ceiling stays current occupancy plus overlay; not multiplied by compute.",
    compute_capacity_note="Compute is 3 units fixed; queue slots are not multiplied.",
    resource_cost_note="Resource cost resource_unit_seconds = 3 * 3600 * 10 = 108000 baseline if fully run; still not dollars.",
    is_learned=False,
    is_deterministic=True,
    evidence_level="IMPLEMENTATION-VERIFIED FACT + " + _HOLD_NOTE,
    limitations="Static 3x is reference overprovision, not claimed efficient; cost trade-off family awaits data.",
)

# Stale variants — demonstrate typed staleness handling without claiming results
_PER_TASK_FIXED_1000 = E3StrategySemantics(
    placement_id="per_task_dla",
    scaling_id="fixed_1x",
    state_age_ms=1000,
    human_label="per_task_dla fixed_1x at state_age 1000 ms — delayed view 1 s",
    radio_ingress="Same ingress.",
    execution_placement="Per-task placement uses delayed immutable backlog view aged 1000 ms plus same-tick overlay.",
    admission="Gate uses observed delayed backlog; true latency and success use true state, not stale estimate.",
    forwarding="Same forwarding as per_task_dla at 1s staleness; null before execution.",
    actor_authority="Frozen actor still does not observe load.",
    infrastructure_authority="Staleness is view parameter only; does not mutate true execution.",
    scaling_semantics="fixed_1x 1 unit; no scaling.",
    staleness_semantics="state_age_ms 1000 typed int milliseconds: immutable delayed view 1000 ms, no future leakage, pessimistic rejected still not executed, optimistic admitted may miss per true latency.",
    queue_capacity_note="Queue safety uses current true occupancy, not stale snapshot.",
    compute_capacity_note="Compute drain uses true active units, not stale.",
    resource_cost_note="Cost resource_unit_seconds unchanged by view age.",
    is_learned=False,
    is_deterministic=True,
    evidence_level="IMPLEMENTATION-VERIFIED FACT + " + _HOLD_NOTE,
    limitations="Staleness 1000 ms contrast not yet executed; E3c dormant.",
)

_PER_TASK_FIXED_3000 = E3StrategySemantics(
    placement_id="per_task_dla",
    scaling_id="fixed_1x",
    state_age_ms=3000,
    human_label="per_task_dla fixed_1x at state_age 3000 ms — delayed view 3 s",
    radio_ingress="Same ingress as fresh; radio viability current not stale.",
    execution_placement="Per-task placement uses 3000 ms delayed immutable backlog view plus same-tick overlay.",
    admission="Gate uses 3000 ms delayed backlog; true execution not delayed.",
    forwarding="Same forwarding as per_task_dla at 3s staleness; null before execution.",
    actor_authority="Frozen actor does not observe load.",
    infrastructure_authority="Delayed view does not change true backlog or occupancy; staleness is view parameter only.",
    scaling_semantics="fixed_1x: 1 active unit per RSU, no scaling actions, drain 1000 per tick.",
    staleness_semantics="state_age_ms 3000 typed int ms; maximal staleness in design.",
    queue_capacity_note="Queue safety uses current true occupancy, not stale snapshot view age.",
    compute_capacity_note="Compute drain uses true active units 1..3, not stale view.",
    resource_cost_note="Resource cost resource_unit_seconds unchanged by view age; not money.",
    is_learned=False,
    is_deterministic=True,
    evidence_level="IMPLEMENTATION-VERIFIED FACT + " + _HOLD_NOTE,
    limitations="Awaiting E3c staleness sensitivity.",
)

_ALL: Final[tuple[E3StrategySemantics, ...]] = (
    _INGRESS_FIXED_0,
    _PER_TASK_FIXED_0,
    _P2C_FIXED_0,
    _PER_TASK_REACTIVE_0,
    _PER_TASK_PROACTIVE_0,
    _PER_TASK_STATIC_0,
    _PER_TASK_FIXED_1000,
    _PER_TASK_FIXED_3000,
)


def e3_strategy_semantics() -> tuple[E3StrategySemantics, ...]:
    """Return the canonical typed E3 strategy semantics (deterministic frozen tuples)."""
    return _ALL


def e3_semantics_for(
    placement: PlacementId, scaling: ScalingId, state_age_ms: int
) -> E3StrategySemantics:
    """Lookup semantics for an exact placement/scaling/state_age triple or raise."""
    if state_age_ms not in _ALLOWED_STATE_AGES:
        raise ValueError(
            f"state_age_ms must be in {list(_ALLOWED_STATE_AGES)}, got {state_age_ms!r}"
        )
    for sem in _ALL:
        if (
            sem.placement_id == placement
            and sem.scaling_id == scaling
            and sem.state_age_ms == state_age_ms
        ):
            return sem
    raise KeyError(f"no semantics for {placement}/{scaling}/{state_age_ms}")


__all__ = [
    "E3StrategySemantics",
    "PlacementId",
    "ScalingId",
    "e3_strategy_semantics",
    "e3_semantics_for",
]
