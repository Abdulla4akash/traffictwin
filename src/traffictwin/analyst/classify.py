"""Deterministic Analyst classification over existing rule outcomes.

The classifier introduces no thresholds. It maps the statuses that the
existing deterministic diagnostic rules (R0-R8, ruleset config owned) and
cross-rule policies already produced onto the bounded five-signal
vocabulary. Where the existing rules cannot support a distinction, the
answer is INSUFFICIENT_EVIDENCE, never a guess.

Side assignment restates each rule's own recorded hypothesis:
R1 (policy under-offloading) and R5 (training-to-validation drift) are
model/policy-side; R2 (infrastructure bottleneck) and R4 (load imbalance)
are infrastructure-side. R0 gates readiness. R3, R6, R7 and R8 are
material-problem candidates without a model-vs-infrastructure side.
"""

from __future__ import annotations

from traffictwin.analyst.models import (
    INFRASTRUCTURE_SIDE_RULE_IDS,
    MODEL_SIDE_RULE_IDS,
    AnalystClassification,
    AnalystEvidencePacket,
    AnalystRuleFact,
    AnalystSignal,
)

_TRIGGERED = "triggered"
_NOT_TRIGGERED = "not_triggered"
_CONFIDENCE_ORDER = {"low": 0, "moderate": 1, "high": 2}

_SIDE_RULE_IDS = (*INFRASTRUCTURE_SIDE_RULE_IDS, *MODEL_SIDE_RULE_IDS)


def _rules_by_id(packet: AnalystEvidencePacket) -> dict[str, AnalystRuleFact]:
    return {rule.rule_id: rule for rule in packet.diagnostics.subject_rules}


def _triggered(rules: dict[str, AnalystRuleFact], rule_ids: tuple[str, ...]) -> list[str]:
    return [
        rule_id for rule_id in rule_ids if rule_id in rules and rules[rule_id].status == _TRIGGERED
    ]


def _supporting_fact_lines(rules: dict[str, AnalystRuleFact], rule_ids: list[str]) -> list[str]:
    lines: list[str] = []
    for rule_id in sorted(rule_ids):
        rule = rules[rule_id]
        for finding in rule.findings:
            if finding.support == "supports":
                keys = ", ".join(finding.evidence_keys) or "no evidence key"
                lines.append(f"{finding.finding_id}: {finding.statement} [evidence: {keys}]")
    return lines


def _missing_lines(rules: dict[str, AnalystRuleFact], rule_ids: list[str]) -> list[str]:
    lines: list[str] = []
    for rule_id in sorted(rule_ids):
        rule = rules[rule_id]
        for item in rule.missing_evidence:
            lines.append(f"{rule.rule_id}: missing evidence — {item}")
    return lines


def _unevaluable_side_rules(rules: dict[str, AnalystRuleFact]) -> list[str]:
    return [
        rule_id
        for rule_id in _SIDE_RULE_IDS
        if rule_id not in rules or rules[rule_id].status not in (_TRIGGERED, _NOT_TRIGGERED)
    ]


def _combined_confidence(rules: dict[str, AnalystRuleFact], rule_ids: list[str]) -> tuple[str, str]:
    """The weakest categorical confidence among the contributing rules."""

    categories = [
        rules[rule_id].confidence
        for rule_id in rule_ids
        if rules[rule_id].confidence in _CONFIDENCE_ORDER
    ]
    if not categories:
        return (
            "unavailable",
            "No contributing triggered rule carries a confidence category.",
        )
    weakest = min(categories, key=lambda item: _CONFIDENCE_ORDER[item])
    return (
        weakest,
        "The weakest categorical confidence among the contributing "
        f"deterministic rules ({', '.join(sorted(rule_ids))}).",
    )


def _next_investigation(rules: dict[str, AnalystRuleFact], rule_ids: list[str]) -> str | None:
    for rule_id in sorted(rule_ids):
        for item in rules[rule_id].recommendations:
            return (
                f"{item.action} — {item.rationale} (conditional; prerequisite: {item.prerequisite})"
            )
    return None


def classify_packet(packet: AnalystEvidencePacket) -> AnalystClassification:
    """Assign the bounded signal, citing the exact rule basis."""

    rules = _rules_by_id(packet)
    diagnostics = packet.diagnostics
    fingerprint = packet.fingerprint()

    def build(
        signal: AnalystSignal,
        statement: str,
        *,
        rule_basis: list[str],
        supported: list[str],
        not_supported: list[str],
        confidence: tuple[str, str],
        next_investigation: str | None,
    ) -> AnalystClassification:
        return AnalystClassification(
            signal=signal,
            statement=statement,
            rule_basis=tuple(rule_basis),
            supported_facts=tuple(supported),
            not_supported=tuple(not_supported),
            confidence=confidence[0],
            confidence_basis=confidence[1],
            next_investigation=next_investigation,
            packet_fingerprint=fingerprint,
        )

    unevaluable = _unevaluable_side_rules(rules)
    baseline_note = (
        [
            "Baseline context: triggered rules "
            f"{', '.join(diagnostics.baseline_triggered_rule_ids)} on the baseline run."
        ]
        if diagnostics.baseline_triggered_rule_ids
        else []
    )
    unevaluable_notes = [
        f"{rule_id}: this check could not evaluate on the selected evidence."
        for rule_id in unevaluable
    ]

    # Gate: readiness and R0 come first.
    r0 = rules.get("R0")
    if diagnostics.subject_readiness == "invalid" or (r0 is not None and r0.status == _TRIGGERED):
        basis = ["R0"] if r0 is not None and r0.status == _TRIGGERED else []
        return build(
            AnalystSignal.INSUFFICIENT_EVIDENCE,
            "The evidence readiness gate refused diagnosis: the selected "
            "evidence is insufficient or inconsistent, so no model-vs-"
            "infrastructure interpretation is supported.",
            rule_basis=[f"{rule_id}:{rules[rule_id].status}" for rule_id in basis]
            or [f"readiness:{diagnostics.subject_readiness}"],
            supported=_supporting_fact_lines(rules, basis),
            not_supported=_missing_lines(rules, basis) + unevaluable_notes,
            confidence=("unavailable", "The readiness gate refused diagnosis."),
            next_investigation=(
                "Resolve the missing or inconsistent evidence named above, "
                "then re-run the deterministic diagnostics."
            ),
        )

    infra = _triggered(rules, INFRASTRUCTURE_SIDE_RULE_IDS)
    model = _triggered(rules, MODEL_SIDE_RULE_IDS)
    conflict = any(fact.relation_type == "conflict" for fact in diagnostics.cross_rule)

    if (infra and model) or conflict:
        contributing = infra + model
        return build(
            AnalystSignal.MIXED_SIGNAL,
            "Both model-side and infrastructure-side candidates are "
            "supported by the deterministic rules; the current evidence "
            "does not choose between them.",
            rule_basis=[f"{rule_id}:triggered" for rule_id in sorted(contributing)]
            + (["XR:conflict"] if conflict else []),
            supported=_supporting_fact_lines(rules, contributing),
            not_supported=_missing_lines(rules, contributing) + unevaluable_notes + baseline_note,
            confidence=_combined_confidence(rules, contributing),
            next_investigation=(
                "Run the existing follow-up comparisons for each candidate "
                "before choosing one hypothesis; the current report retains "
                "both candidates with no winner."
            ),
        )

    if infra:
        titles = "; ".join(rules[rule_id].title for rule_id in sorted(infra))
        return build(
            AnalystSignal.INFRASTRUCTURE_SIDE_SIGNAL,
            "Within the selected evidence, the strongest supported signal "
            f"is infrastructure-side ({titles}). The available model-side "
            "checks did not trigger, so the evidence does not establish a "
            "policy failure.",
            rule_basis=[f"{rule_id}:triggered" for rule_id in sorted(infra)],
            supported=_supporting_fact_lines(rules, infra),
            not_supported=_missing_lines(rules, infra) + unevaluable_notes + baseline_note,
            confidence=_combined_confidence(rules, infra),
            next_investigation=_next_investigation(rules, infra),
        )

    if model:
        titles = "; ".join(rules[rule_id].title for rule_id in sorted(model))
        return build(
            AnalystSignal.MODEL_SIDE_SIGNAL,
            "Within the selected evidence, the strongest supported signal "
            f"is model/policy-side ({titles}). The available infrastructure-"
            "side checks did not trigger, so the evidence does not establish "
            "an infrastructure constraint.",
            rule_basis=[f"{rule_id}:triggered" for rule_id in sorted(model)],
            supported=_supporting_fact_lines(rules, model),
            not_supported=_missing_lines(rules, model) + unevaluable_notes + baseline_note,
            confidence=_combined_confidence(rules, model),
            next_investigation=_next_investigation(rules, model),
        )

    other_triggered = [
        rule.rule_id for rule in diagnostics.subject_rules if rule.status == _TRIGGERED
    ]
    if other_triggered:
        titles = "; ".join(rules[rule_id].title for rule_id in sorted(other_triggered))
        return build(
            AnalystSignal.INSUFFICIENT_EVIDENCE,
            f"A material problem candidate is present ({titles}), but the "
            "current evidence cannot distinguish a model-side from an "
            "infrastructure-side explanation: neither side's rules "
            "triggered.",
            rule_basis=[f"{rule_id}:triggered" for rule_id in sorted(other_triggered)],
            supported=_supporting_fact_lines(rules, other_triggered),
            not_supported=_missing_lines(rules, other_triggered) + unevaluable_notes,
            confidence=_combined_confidence(rules, other_triggered),
            next_investigation=_next_investigation(rules, other_triggered)
            or (
                "Acquire the missing evidence named above before attributing "
                "this outcome to the model or the infrastructure."
            ),
        )

    primary_pair_evaluated = all(
        rule_id in rules and rules[rule_id].status == _NOT_TRIGGERED for rule_id in ("R1", "R2")
    )
    if primary_pair_evaluated:
        return build(
            AnalystSignal.NO_MATERIAL_PROBLEM_DETECTED,
            "No deterministic diagnostic rule triggered on the selected "
            f"evidence under ruleset {diagnostics.subject_ruleset_version}. "
            "This does not prove the absence of problems outside the "
            "evaluated rules' scope.",
            rule_basis=[
                f"{rule.rule_id}:{rule.status}"
                for rule in diagnostics.subject_rules
                if rule.rule_id in _SIDE_RULE_IDS
            ],
            supported=[],
            not_supported=unevaluable_notes,
            confidence=(
                "unavailable",
                "No triggered rule contributes a confidence category; the "
                "signal reports an absence, not a finding.",
            ),
            next_investigation=None,
        )

    return build(
        AnalystSignal.INSUFFICIENT_EVIDENCE,
        "The rules needed to distinguish a model-side from an "
        "infrastructure-side explanation could not evaluate on the "
        "selected evidence.",
        rule_basis=[f"{rule_id}:unevaluable" for rule_id in unevaluable],
        supported=[],
        not_supported=unevaluable_notes,
        confidence=("unavailable", "The distinguishing checks could not evaluate."),
        next_investigation=(
            "Provide the evidence the unevaluable checks require, then "
            "re-run the deterministic diagnostics."
        ),
    )
