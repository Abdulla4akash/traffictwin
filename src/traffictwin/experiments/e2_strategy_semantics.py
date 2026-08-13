"""Strategy semantics service for E2 product campaign (Lane 05).

Strict deterministic typed descriptions for off, jsq, ingress_dla, dla and
per_task_dla.  Covers radio ingress, execution placement, admission,
forwarding, actor/infrastructure authority, learned/deterministic status,
evidence level and limitations.

Truth anchors are docs/closure/v08_alignment/strategy_matrix.json and
improved_dynamic_strategy_contract.json at base 6e3fd0d385c20c7262e096f2d7da4995a7d9c21b.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

StrategyId = Literal["off", "jsq", "ingress_dla", "dla", "per_task_dla"]

_ALLOWED_IDS: Final[tuple[StrategyId, ...]] = (
    "off",
    "jsq",
    "ingress_dla",
    "dla",
    "per_task_dla",
)


# ---------------------------------------------------------------------------
# Validation helpers — hard reject prohibited claims (mutation guards).
# ---------------------------------------------------------------------------


def _contains_affirming(text: str, phrase: str) -> bool:
    """Return True if *phrase* appears affirmatively (not negated by not/no/never)."""
    lower = text.lower()
    needle = phrase.lower()
    start = 0
    while True:
        idx = lower.find(needle, start)
        if idx == -1:
            return False
        # Check up to 20 chars before phrase for negation tokens.
        prefix = lower[max(0, idx - 24) : idx]
        # If prefix contains a negation that scopes over the phrase, treat as disclaimed.
        # Negation tokens include "not ", "no ", "never", "without", "is not ", "are not "
        has_negation = any(
            token in prefix
            for token in ("not ", "no ", "never", "without", "is not", "are not", "isn't", "isnt")
        )
        # Also check for "not canonical" style where phrase itself is preceded by "not "
        # e.g. "not canonical per-task jsq" -> phrase "canonical per-task jsq" with negation
        if has_negation:
            # This occurrence is negated — skip it.
            start = idx + len(needle)
            continue
        return True


def _validate_text_fields(sem: E2StrategySemantics) -> None:
    # Collect all string fields to scan (checked per-field to avoid cross-field
    # negation bleed where trailing "not learned" in one field would mask a
    # forbidden phrase at the start of the next field).
    texts: list[str] = [
        sem.human_label,
        sem.radio_ingress,
        sem.execution_placement,
        sem.admission,
        sem.forwarding,
        sem.actor_authority,
        sem.infrastructure_authority,
        sem.evidence_level,
        sem.limitations,
    ]

    # Helper to check per-field to avoid cross-field negation bleed.
    def _any_field_has(phrase: str) -> bool:
        return any(_contains_affirming(t, phrase) for t in texts)

    # 1. Common-target DLA must not be called canonical per-task JSQ (affirmative).
    if sem.strategy_id == "dla":
        for phrase in (
            "canonical per-task jsq",
            "canonical jsq",
        ):
            if _any_field_has(phrase):
                raise ValueError(
                    f"strategy {sem.strategy_id}: forbidden affirmative phrase '{phrase}' — "
                    "common-target DLA is not canonical per-task JSQ"
                )
        if _any_field_has("canonical"):
            raise ValueError(
                f"strategy {sem.strategy_id}: forbidden affirmative 'canonical' — "
                "common-target DLA must not be called canonical"
            )

    # 2. Must not credit MAPPO/actor with execution-RSU selection or current load observation.
    for phrase in (
        "mappo selects execution",
        "mappo selects rsu",
        "actor selects execution",
        "actor selects rsu",
        "mappo observes current load",
        "mappo observes rsu load",
        "actor observes current load",
        "observes current rsu load",
        "observes current load",
    ):
        if _any_field_has(phrase):
            raise ValueError(
                f"strategy {sem.strategy_id}: forbidden actor-RSU credit '{phrase}' — "
                "MAPPO is frozen Local/V2I/V2V and does not observe load or select execution RSU"
            )
    if _any_field_has("mappo selects"):
        raise ValueError(
            f"strategy {sem.strategy_id}: forbidden 'mappo selects' — "
            "actor does not select execution RSU"
        )

    # 3. Deterministic placement must not be called learned.
    if sem.is_deterministic and sem.is_learned:
        raise ValueError(
            f"strategy {sem.strategy_id}: deterministic placement must not be marked learned "
            "(is_learned must be False when is_deterministic is True)"
        )
    for phrase in (
        "deterministic placement is learned",
        "placement is learned",
        "learned placement",
        "learned scheduler",
        "learned jsq",
    ):
        if _any_field_has(phrase):
            raise ValueError(
                f"strategy {sem.strategy_id}: forbidden 'learned placement' — "
                "placement is deterministic infrastructure-side, not learned"
            )

    # 4. Must not describe Kubernetes deployment / cluster orchestration as real deployment.
    for phrase in (
        "kubernetes deployment",
        "kubernetes cluster",
        "cluster orchestration",
    ):
        if _any_field_has(phrase):
            raise ValueError(
                f"strategy {sem.strategy_id}: forbidden affirmative '{phrase}' — "
                "placement is Kubernetes-inspired deterministic scheduling, not actual "
                "Kubernetes deployment or cluster orchestration"
            )


def _validate_semantics(sem: E2StrategySemantics) -> None:
    if sem.strategy_id not in _ALLOWED_IDS:
        raise ValueError(f"unknown strategy_id {sem.strategy_id!r}")
    if not sem.human_label or len(sem.human_label.strip()) < 5:
        raise ValueError(f"strategy {sem.strategy_id}: human_label must be substantive")
    if not sem.radio_ingress or len(sem.radio_ingress.strip()) < 10:
        raise ValueError(f"strategy {sem.strategy_id}: radio_ingress must be substantive")
    if not sem.execution_placement or len(sem.execution_placement.strip()) < 10:
        raise ValueError(f"strategy {sem.strategy_id}: execution_placement must be substantive")
    if not sem.admission or len(sem.admission.strip()) < 10:
        raise ValueError(f"strategy {sem.strategy_id}: admission must be substantive")
    if not sem.forwarding or len(sem.forwarding.strip()) < 10:
        raise ValueError(f"strategy {sem.strategy_id}: forwarding must be substantive")
    if not sem.actor_authority or len(sem.actor_authority.strip()) < 10:
        raise ValueError(f"strategy {sem.strategy_id}: actor_authority must be substantive")
    if not sem.infrastructure_authority or len(sem.infrastructure_authority.strip()) < 10:
        raise ValueError(
            f"strategy {sem.strategy_id}: infrastructure_authority must be substantive"
        )
    if sem.is_learned not in (True, False):
        raise ValueError(f"strategy {sem.strategy_id}: is_learned must be bool")
    if sem.is_deterministic not in (True, False):
        raise ValueError(f"strategy {sem.strategy_id}: is_deterministic must be bool")
    # All E2 placements are deterministic infrastructure; none are learned.
    if sem.is_learned is True:
        raise ValueError(
            f"strategy {sem.strategy_id}: is_learned must be False (no learned placement)"
        )
    if sem.is_deterministic is not True:
        raise ValueError(f"strategy {sem.strategy_id}: is_deterministic must be True")
    if not sem.evidence_level or len(sem.evidence_level.strip()) < 10:
        raise ValueError(f"strategy {sem.strategy_id}: evidence_level must be substantive")
    if not sem.limitations or len(sem.limitations.strip()) < 10:
        raise ValueError(f"strategy {sem.strategy_id}: limitations must be substantive")

    _validate_text_fields(sem)


# ---------------------------------------------------------------------------
# Typed semantics dataclass.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class E2StrategySemantics:
    """Deterministic typed description for one E2 strategy."""

    strategy_id: StrategyId
    human_label: str
    radio_ingress: str
    execution_placement: str
    admission: str
    forwarding: str
    actor_authority: str
    infrastructure_authority: str
    is_learned: bool
    is_deterministic: bool
    evidence_level: str
    limitations: str

    def __post_init__(self) -> None:
        _validate_semantics(self)


# ---------------------------------------------------------------------------
# Canonical strategy instances — strict, deterministic, truth-bound.
# ---------------------------------------------------------------------------

_OFF = E2StrategySemantics(
    strategy_id="off",
    human_label=(
        "Strongest-link / LB-off (deterministic strongest radio link, "
        "no infrastructure load balancing)"
    ),
    radio_ingress=(
        "Strongest-link ingress: vehicle selects a V2I RSU by best radio link "
        "(best_rsu_idx from compute_per_vehicle_links). Infrastructure performs no alternative "
        "ingress decision; ingress quality is used only to determine eligibility."
    ),
    execution_placement=(
        "Off / strongest-link execution: selected_execution_rsu equals task ingress RSU "
        "(best_rsu_idx). No JSQ, no least-busy, no load-aware selection. Execution equals ingress "
        "when admitted; no forwarding. Deterministic identity function on ingress."
    ),
    admission=(
        "Admission is per-RSU waiting-room ceiling at 2.5x (6220 tasks/RSU for padded width 2488) "
        "with evaluator flag --rsu-cap-per-veh 2.5, --rsu-cap-mode reject, sequential substeps "
        "and 3 reconciliation iterations. No deadline-aware gate beyond cap, local MQD, V2V MQD "
        "and "
        "V2I unavailable (code 7). Rejected tasks retain selected target, execution -1, not "
        "enqueued. "
        "Cap is waiting-room ceiling, not compute power (SOURCE-DERIVED FACT via S-035, S-007)."
    ),
    forwarding=(
        "Forwarding never occurs: forwarded_admitted_task_count is 0, share 0.0, forwarding "
        "latency "
        "0.0 ms, ingress-to-execution matrix is diagonal. Backhaul is 0 ms by design "
        "(--rsu-backhaul-ms 0.0) "
        "representing ideal fibre; zero cost is a controlled simulator condition, not a deployment "
        "claim. "
        "Deterministic because execution equals ingress."
    ),
    actor_authority=(
        "Vehicle actor authority: frozen MAPPO (mappo_modelc_17dim, 17-dim observation, actions "
        "Local/V2I/V2V, checkpoint sha256 "
        "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208, "
        "training seed 100, frozen). Actor emits Local/V2I/V2V intent only and does not select an "
        "execution RSU. Actor has no current RSU load or capacity observation (no explicit "
        "awareness; RSUs "
        "do not broadcast load due to staleness). Placement is not actor-controlled."
    ),
    infrastructure_authority=(
        "Infrastructure authority: placement is deterministic infrastructure-side RSU management, "
        "degenerate identity on ingress for off. Admission authority (cap) is infrastructure. "
        "No learned scheduler; optionally described as Kubernetes-inspired deterministic "
        "scheduling, "
        "but no actual cluster deployment is evidenced or claimed."
    ),
    is_learned=False,
    is_deterministic=True,
    evidence_level=(
        "RESEARCH-EVIDENCE FACT: single fleet draw seed 0, offered 13076234, manifest "
        "53bcd2e26b913b64ce0c4546da7c01cb7f9290382a036a20ce9fd28229ed02a8, comparison "
        "67d626ca4e6b60afb6beb5c9d4c8cc2bf7b15c72922eba633194848439fe3d52, validation "
        "30f6d117402e91decf8581b2b42030c0f9795881dd5eaef1a380bbf6408f0d38, head "
        "fe2ed4e9bd9043b19b96a5f179390db629b01ccb, vec_env "
        "e11f4445a9cc939a79d4f419c6f48b43ce110664. "
        "No population inference; descriptive only."
    ),
    limitations=(
        "Bounded to one Manchester incident hour 2024-03-15 20:00-21:00 Europe/London (3600 "
        "steps), "
        "provisional uk2030 fleet, evaluator seed 0, waiting-room cap 2.5x/6220, fixed 1x service "
        "(--rsu-service-mult 1.0, --k8s-scale off), zero backhaul, frozen actor that does not "
        "observe "
        "RSU load nor choose execution RSU. Deadline success is simulated outcome, not confirmed "
        "physical "
        "return. No ordinary-traffic control, no stale-state sweep, no learning, no physical "
        "deployment. "
        "EXTERNAL DECISION REQUIRED for broader generalisation."
    ),
)

_JSQ = E2StrategySemantics(
    strategy_id="jsq",
    human_label="Evidenced JSQ without deadline gate (least-busy placement, admission is cap only)",
    radio_ingress=(
        "Strongest-link ingress: per-vehicle best_rsu_idx from compute_per_vehicle_links "
        "determines "
        "ingress RSU and radio eligibility. Ingress quality does not filter the placement argmin; "
        "it is "
        "checked post-selection for eligibility. Same radio as off."
    ),
    execution_placement=(
        "JSQ least-busy placement without gate: per substep compute jnp.argmin(rsu_busy_ms) over "
        "all 10 RSUs "
        "(remaining service work in ms, drained at most 1000 ms per simulated second, remainder "
        "carried). "
        "Not task-count shortest-queue and not canonical queue-length JSQ; labelled least-busy / "
        "shortest-workload. One common target per Model-C task substep is selected at substep "
        "entry and "
        "broadcast to eligible V2I candidates in that substep. Reachability, ingress quality and "
        "capacity "
        "do not filter the argmin. Tie resolves to lowest RSU index deterministically. This "
        "evidenced JSQ is "
        "common-target per substep, not sequential per-task placement (contrast with per_task_dla)."
    ),
    admission=(
        "Admission is same waiting-room ceiling 2.5x/6220 with sequential reject semantics as off. "
        "No "
        "backlog-vs-deadline gate; outcome code 3 count is 0 for jsq. E2 seed 0 recorded 355207 "
        "cap rejections "
        "(vs 834120 for off), reflecting that load spreading reduces cap pressure. Local MQD "
        "34124, V2V MQD "
        "545879, V2I unavailable 138 remain. Cap size remains provisional (50/20) not an approved "
        "physical size."
    ),
    forwarding=(
        "Forwarding when selected execution RSU differs from ingress and task is admitted. At seed "
        "0, "
        "forwarded 2067204 of 2297044 admitted V2I (share 0.899940968). Execution imbalance "
        "diagnostic "
        "(max share minus min share) at seed 0: off 0.098660108 to jsq 0.000457980 (more "
        "balanced). "
        "Total forwarding latency 0.0 ms due to zero backhaul design; zero cost is controlled "
        "idealisation, "
        "not 'forwarding is free'. Deterministic given snapshot and tie rule."
    ),
    actor_authority=(
        "Frozen MAPPO actor (same checkpoint "
        "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208) "
        "emits Local/V2I/V2V intent only; actor does not select an execution RSU and does not "
        "observe current "
        "RSU load or capacity (IMPLEMENTATION-VERIFIED FACT via vec_env vec_jax). Actions remain "
        "byte-identical to off across matched arms; no new PRNG split."
    ),
    infrastructure_authority=(
        "Infrastructure authority: placement authority selects execution RSU after vehicle chooses "
        "V2I, "
        "using deterministic least-busy argmin. Admission authority remains cap/MQD/unavailable. "
        "Placement and admission are separated; this mode is placement-only. Infrastructure "
        "placement is "
        "deterministic, not learned; optionally termed Kubernetes-inspired deterministic "
        "scheduling, but no "
        "actual managed-cluster deployment or orchestration is tested."
    ),
    is_learned=False,
    is_deterministic=True,
    evidence_level=(
        "IMPLEMENTATION-VERIFIED FACT + RESEARCH-EVIDENCE FACT: one draw seed 0, "
        "placement recomputes argmin from live sequential backlog at substep entry. Observed "
        "offered "
        "attainment 0.675681775, admitted 0.727737086, offered 13076234, admitted 12140886. "
        "Validation 30f6d117402e91decf8581b2b42030c0f9795881dd5eaef1a380bbf6408f0d38. No "
        "population inference."
    ),
    limitations=(
        "One fleet draw seed 0, one trace/hour/cap/service/backhaul/actor. Zero backhaul "
        "idealisation and frozen "
        "actor without RSU load observation. Evaluator deadline outcome is not physical return. "
        "Cannot claim "
        "universal JSQ superiority or harm; zero-backhaul and lack of staleness limit "
        "generalisation. "
        "EXTERNAL DECISION REQUIRED for stale-state and backhaul sweeps."
    ),
)

_INGRESS_DLA = E2StrategySemantics(
    strategy_id="ingress_dla",
    human_label=(
        "Ingress DLA — strongest-link execution plus deadline-aware "
        "admission (placement fixed, admission is DLA gate)"
    ),
    radio_ingress=(
        "Strongest-link ingress: best_rsu_idx per vehicle from compute_per_vehicle_links. Radio "
        "linkage is "
        "identical to off; ingress quality determines eligibility for the subsequent gate check."
    ),
    execution_placement=(
        "Strongest-link execution only: selected_execution_rsu equals best_rsu_idx (ingress) for "
        "every "
        "V2I attempt. No argmin, no load metric, no forwarding. Deterministic strongest-link "
        "execution; "
        "placement authority is degenerate (identity) but admission uses the deadline gate."
    ),
    admission=(
        "Deadline-aware admission (DLA gate) at ingress RSU: strict backlog-only rule "
        "effective_busy_ms[selected_rsu] < TASK_DEADLINE_MS[task_type] evaluated against live "
        "per-RSU backlog "
        "with candidate service, recomputed each substep against current sequential state and "
        "three-iteration "
        "fixed-point reconciliation (seq_offsets). Gate excludes own compute, radio and return "
        "transfer, and "
        "forwarding latency; it is backlog-only feasibility, not confirmed physical result return. "
        "Gate-before-cap "
        "outcome precedence. At seed 0, gate rejected 2071344 tasks (retained ingress, execution "
        "-1, not enqueued, "
        "not forwarded); v2i cap 0 at seed 0. Cap remains 2.5x/6220. Inherited caveat: off vs "
        "ingress_dla contrast "
        "retains one eligibility-timing difference (off step-entry coarse saturation vs live "
        "backlog per substep; "
        "off recorded 138 unavailable ~1.1e-5). Admission cost: fewer admitted tasks (10424749 vs "
        "off 11661973 "
        "at seed 0) but higher conditional admitted success."
    ),
    forwarding=(
        "Never forwarded: selected execution equals ingress, so forwarded count 0, share 0.0, "
        "latency 0.0 ms, "
        "admitted execution lies on ingress diagonal. Rejected tasks never forwarded. "
        "Deterministic and without "
        "new randomness; inherits existing gate logic."
    ),
    actor_authority=(
        "Frozen MAPPO actor does not select an execution RSU and does not observe current RSU "
        "load. "
        "Actor emits V2I intent; infrastructure deterministic placement (here degenerate) and gate "
        "decide admission. "
        "No learned RSU selection."
    ),
    infrastructure_authority=(
        "Infrastructure authority: admission authority is the DLA gate at the ingress RSU "
        "(deadline-aware). "
        "Placement authority is degenerate (ingress). Deterministic gate logic; not learned; "
        "optionally described as "
        "Kubernetes-inspired deterministic admission, but no actual managed-cluster deployment or "
        "orchestration is claimed."
    ),
    is_learned=False,
    is_deterministic=True,
    evidence_level=(
        "IMPLEMENTATION-VERIFIED FACT + RESEARCH-EVIDENCE FACT: E2b single-draw factorial seed 0, "
        "manifest 9383ec767dccf2f390b498e0c20283a74cd64fa521d6137fe23ce38d0022af91, comparison "
        "8d35e55e2952d71b1c04479b310d1f5b48da7cf7bc2e171a1ca6359c9fa98aaf, head "
        "fe2ed4e9bd9043b19b96a5f179390db629b01ccb, plus E2c replication seeds 1-4 manifest "
        "fcaf2ee34b68ca4e4ef2e088d72ce2c5a410cf66ff9934a451fd8047204c480a. Offers gate-only "
        "contrast."
    ),
    limitations=(
        "Descriptive until E2c (one pilot seed plus four new draws). Same Manchester incident hour "
        "trace "
        "2024-03-15 20:00-21:00, 3600 steps, provisional uk2030 fleet, cap 6220, 1x service, zero "
        "backhaul, "
        "frozen actor without RSU load observation. Off contrast inherits eligibility-timing "
        "caveat. Gate is "
        "backlog-only, not predicted earliest-completion. No staging of physical deployment. "
        "EXTERNAL DECISION REQUIRED for cap/trace breadth and whether backlog-only gate satisfies "
        "TT-REQ-008."
    ),
)

_DLA = E2StrategySemantics(
    strategy_id="dla",
    human_label=(
        "Common-target DLA — JSQ placement (common-target per substep) "
        "plus deadline-aware admission"
    ),
    radio_ingress=(
        "Strongest-link ingress: best_rsu_idx per vehicle determines ingress radio RSU. Ingress "
        "quality, "
        "reachability and capacity do not filter the placement argmin; post-selection eligibility "
        "checks "
        "positive ingress-link quality and selected target below cap at substep entry."
    ),
    execution_placement=(
        "Common-target batch placement: one jnp.argmin(rsu_busy_ms) over all 10 RSUs per Model-C "
        "task substep "
        "(one common target per substep); that single RSU is the selected execution target for "
        "every eligible "
        "V2I candidate in that substep (inherited evaluator behavior, per substep batch). "
        "Sequentially, target "
        "is recomputed at substep entry from backlogs updated by prior substeps after "
        "three-iteration "
        "reconciliation, but not recomputed after each candidate's reservation within the same "
        "substep. Tie to "
        "lowest RSU index deterministically. This is common-target-per-substep least-busy "
        "placement; it is not "
        "sequential per-task placement and must not be described as canonical sequential per-task "
        "JSQ. The later "
        "per_task_dla recomputes after each candidate's reservation (see that entry). State is "
        "shortest "
        "remaining service workload in rsu_busy_ms, not task-count queue length."
    ),
    admission=(
        "Deadline-aware admission at the selected common target: strict backlog-only gate "
        "effective_busy_ms[selected_rsu] < TASK_DEADLINE_MS[task_type] with three-iteration "
        "fixed-point "
        "reconciliation, evaluated per candidate at that selected target. Outcome code 3 for gate "
        "rejection; "
        "rejected tasks retain selected target, execution -1, not enqueued. At seed 0, gate "
        "rejected 2373522; "
        "cap rejected 0. Gate-before-cap precedence. Gate is backlog-only feasibility, not "
        "confirmed return."
    ),
    forwarding=(
        "Forwarding when common selected target differs from ingress and gate passes. At seed 0: "
        "forwarded "
        "232729 of 278729 admitted V2I (share 0.834965145); E2c seeds 1-4 forwarded ~234k-242k "
        "share "
        "~0.848-0.857. Latency 0.0 ms due to zero backhaul design. Execution distribution is "
        "concentrated: at "
        "seed 0 counts [66743, 66899, 66772, 52223, 26092, 0,0,0,0,0] leaving 5 RSUs idle; "
        "imbalance range "
        "~0.240 vs ingress ~0.060. Zero cost is idealisation; nonzero backhaul would add "
        "per-forwarded delay."
    ),
    actor_authority=(
        "Frozen MAPPO actor (same checkpoint) does not select an execution RSU and does not "
        "observe current "
        "RSU load or capacity. Actor emits offload intent; infrastructure deterministic "
        "common-target placement "
        "selects execution RSU downstream. Placement is deterministic, not learned."
    ),
    infrastructure_authority=(
        "Infrastructure authority jointly holds placement (common-target JSQ) and admission (DLA "
        "gate at that "
        "chosen RSU). Deterministic downstream placement; not learned. Optionally termed "
        "Kubernetes-inspired "
        "deterministic scheduling, but no actual managed-cluster deployment or orchestration is "
        "evidenced."
    ),
    is_learned=False,
    is_deterministic=True,
    evidence_level=(
        "IMPLEMENTATION-VERIFIED FACT + RESEARCH-EVIDENCE FACT + INFERENCE boundary: E2 seed 0 "
        "pilot plus "
        "E2c four-draw replication (seeds 1-4) holding gate fixed. Manifest "
        "fcaf2ee34b68ca4e4ef2e088d72ce2c5a410cf66ff9934a451fd8047204c480a, comparison "
        "b0bc17ef097e8a8ca3639482bbf5ae05ef249c1221836cc6591207e87b511970, head "
        "1a08d6e148a1e8c430da39c3d575eda3f8ea5929. Directional dla minus ingress_dla mean "
        "-0.021222261 "
        "95% CI [-0.022335, -0.020109], all four negative. Not population or task-level "
        "significance."
    ),
    limitations=(
        "Four provisional fleet draws plus one pilot seed; one Manchester incident trace/hour, cap "
        "6220, fixed "
        "1x service, zero backhaul, frozen actor without RSU load observation. Backlog is total "
        "remaining service ms, "
        "not predicted earliest completion. Common-target batch convention limits claims to that "
        "construction, not general "
        "JSQ. No scaling/P2C/learning. EXTERNAL DECISION REQUIRED for trace breadth and staleness."
    ),
)

_PER_TASK_DLA = E2StrategySemantics(
    strategy_id="per_task_dla",
    human_label=(
        "per_task_dla — per-task recomputed least-busy placement plus deadline-aware admission"
    ),
    radio_ingress=(
        "Strongest-link ingress: best_rsu_idx per vehicle (same radio as other arms). Ingress "
        "quality is "
        "checked post-selection for eligibility before the gate; radio attachment does not change "
        "with per-task "
        "target recomputation."
    ),
    execution_placement=(
        "Per-task sequential least-busy placement: for each admitted V2I candidate in ascending "
        "padded "
        "vehicle-slot order within each Model-C task substep, recompute argmin(effective_busy_ms) "
        "over all 10 "
        "RSUs from live backlog that includes service just reserved for prior admitted candidates "
        "in the same "
        "substep. Selection metric is shortest remaining service workload in rsu_busy_ms "
        "(milliseconds), not queue "
        "length; not canonical queue-length JSQ. Tie to lowest RSU index deterministically "
        "(jnp.argmin). "
        "Service reservation quantity is exact selected RSU service work derived from split index "
        "1 of the existing "
        "five-way process_agent subkey split, divided by service multiplier (1.0 locked). No new "
        "RNG draw. "
        "Contrast to common-target: common-target computes once per substep and reuses; per-task "
        "recomputes after "
        "each reservation so batch concentration is reduced. Deterministic sequential per-task "
        "placement under the "
        "declared deadline rule with immediate reservation/load update after each assignment."
    ),
    admission=(
        "Same deadline-aware gate as dla/ingress_dla at the per-task selected target: "
        "effective_busy_ms[selected_rsu] < TASK_DEADLINE_MS[task_type], strict backlog-only, "
        "excludes own compute, "
        "radio/return transfer and forwarding latency. Live in-batch cap with gate-before-cap "
        "precedence and "
        "three-iteration causal reconciliation from identical live rb/rl (idempotent). Rejected "
        "(unavailable, "
        "gate_rejected, cap_rejected) leaves temporary effective vectors unchanged; admitted adds "
        "one load unit and "
        "exact service work immediately visible to next candidate."
    ),
    forwarding=(
        "Forwarding when per-task selected target differs from ingress and gate passes. At E2d "
        "seeds 1-4, "
        "forwarded ~600k tasks, share 0.899-0.900 of admitted V2I (~667k admitted V2I), higher "
        "count than "
        "common-target dla (~234-241k) because per-task admits more. Ingress-to-execution matrix "
        "shows greater "
        "off-diagonal spread. Latent forwarding latency 0.0 ms due to zero backhaul design; real "
        "backhaul would "
        "scale with ~600k forwards per hour. Execution across 10 RSUs near-uniform (counts "
        "~66.3k-67.3k, share range "
        "~0.0007-0.0014; mean difference vs dla about -0.238), not concentrated to a subset."
    ),
    actor_authority=(
        "Frozen MAPPO actor (17-dim, same checkpoint "
        "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208) "
        "emits Local/V2I/V2V intent only; infrastructure deterministic per-task placement selects "
        "execution RSU "
        "downstream. Actor does not observe current RSU load or capacity and does not select an "
        "execution RSU. "
        "Placement is downstream deterministic, not learned."
    ),
    infrastructure_authority=(
        "Infrastructure authority: placement authority recomputes per task deterministically; "
        "admission authority "
        "is the same DLA gate applied per task at its own selected target. This per-task "
        "recomputation directly "
        "tests construct validity of E2c common-target deficit. Deterministic, not learned; "
        "optionally termed "
        "Kubernetes-inspired deterministic scheduling, but no actual managed-cluster deployment or "
        "orchestration "
        "is evidenced. S-035 requested investigation (A) maps to deterministic load balancing "
        "without retraining."
    ),
    is_learned=False,
    is_deterministic=True,
    evidence_level=(
        "IMPLEMENTATION-VERIFIED FACT + RESEARCH-EVIDENCE FACT: E2d four-draw bounded study (seeds "
        "1-4), "
        "manifest f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740, comparison "
        "1655ae76d3c9a6aac77d66b53555a35d608394427f86f0f19828fa5fb148afd0, mechanism "
        "4975ab8792242a56c241d6513e7e49bcdfa5117ab462bcb6b9bb3c5d2a5e5410, head "
        "80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761, vec_env "
        "2f63706f46319433a2ba3af1df97afd0e56a95d1 "
        "helper a6e047265dd09365c0d4029afa76f8cb7caa444883e2f549a4254e3d0b53472a. Primary per_task "
        "minus ingress "
        "mean +0.005271433656 CI [+0.004422, +0.006120]; secondary per_task minus dla mean "
        "+0.026493694591. "
        "Bounded directional advantage within four draws only; not universal, not held-out "
        "replication."
    ),
    limitations=(
        "Four fleet seeds, evaluator seed 0, one Manchester incident hour 2024-03-15 20:00-21:00 "
        "(3600 steps), "
        "cap 6220 (2.5x), 1x service, zero backhaul, provisional uk2030 fleet, frozen actor "
        "without RSU load "
        "observation, backlog-only gate, evaluator deadline not physical return. No "
        "ordinary-traffic control, no "
        "deployment, no scaling/P2C/learning. E2d is construct-validity robustness, not general "
        "controller "
        "superiority. Reuses prior E2c controls, not independent held-out replication; tasks are "
        "accounting records, "
        "not replicates. EXTERNAL DECISION REQUIRED for trace/cap breadth and backhaul realism."
    ),
)

_ALL: Final[tuple[E2StrategySemantics, ...]] = (_OFF, _JSQ, _INGRESS_DLA, _DLA, _PER_TASK_DLA)


def e2_strategy_semantics() -> tuple[E2StrategySemantics, ...]:
    """Return the five canonical E2 strategy semantics in declared order.

    Returns a tuple of ``E2StrategySemantics`` for off, jsq, ingress_dla, dla,
    per_task_dla.  Instances are frozen and validated; callers must not mutate
    string fields to affirm prohibited claims (canonical per-task JSQ for dla,
    MAPPO execution-RSU credit, learned deterministic placement, or managed-cluster
    deployment).  Validation is strict and deterministic.
    """
    # Return a new tuple of the validated frozen instances (deterministic order).
    return _ALL


__all__ = ["E2StrategySemantics", "e2_strategy_semantics", "StrategyId"]
