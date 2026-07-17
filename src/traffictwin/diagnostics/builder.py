"""Diagnostic report construction helpers."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from traffictwin.diagnostics.report import DiagnosticReport
from traffictwin.evidence.pack import EvidencePack
from traffictwin.rules.config import RuleSetConfig
from traffictwin.rules.engine import evaluate_rules


def build_diagnostic_report(
    evidence_pack: EvidencePack,
    rule_config: RuleSetConfig | None = None,
    *,
    clock: Callable[[], datetime],
) -> DiagnosticReport:
    """Build a deterministic diagnostic report from an EvidencePack."""

    return evaluate_rules(evidence_pack, rule_config, clock=clock)
