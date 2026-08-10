"""Typed CLI sub-application for the Evidence Admission Inbox.

Registered during Fable integration via docs/quality/v4_registration/*_cli.json.
This module does not wire itself into the shared CLI.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated

import typer

from traffictwin.evidence_admission.models import (
    CompatibilityStanding,
    EvidenceMode,
    EvidenceReviewState,
    RightsPrivacyStanding,
    ValidationStanding,
)
from traffictwin.evidence_admission.service import (
    EvidenceAdmissionError,
    admitted_attachment_to_json,
    build_receipt,
    case_to_json,
    get_global_service,
    ledger_to_json,
    receipt_to_json,
    review_summary_to_csv,
)

app = typer.Typer(
    help=(
        "Evidence Admission Inbox — human review queue between validation "
        "and preregistration admission. Validation is not admission."
    ),
    no_args_is_help=True,
)


@app.command("list")
def list_cases(
    state: Annotated[
        str | None,
        typer.Option(
            help="Filter by review state (pending, needs_information, admitted, "
            "rejected, withdrawn)"
        ),
    ] = None,
) -> None:
    """List cases currently in the in-memory inbox (empty until populated)."""
    service = get_global_service()
    if state is None:
        cases = service.list_cases()
    else:
        try:
            wanted = EvidenceReviewState(state)
        except ValueError as err:
            typer.echo(f"unknown state {state!r}", err=True)
            raise typer.Exit(2) from err
        cases = service.cases_by_state(wanted)
    if not cases:
        typer.echo(
            "No cases in this state. The inbox is empty until evidence "
            "candidates are enqueued in this process."
        )
        return
    for case in sorted(cases, key=lambda c: c.case_id):
        cell = case.expected_preregistration_cell_id
        metric = case.observed_metric_key
        state_val = case.current_state.value
        typer.echo(f"{case.case_id}  {state_val}  cell={cell}  metric={metric}")


@app.command("show")
def show_case(
    case_id: Annotated[str, typer.Argument(help="Case ID to display")],
) -> None:
    """Show one case with its findings and ledger status (thin service output)."""
    service = get_global_service()
    try:
        case = service.get_case(case_id)
        ledger = service.get_ledger(case_id)
    except EvidenceAdmissionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(case_to_json(case))
    typer.echo("---ledger---")
    typer.echo(ledger_to_json(ledger))


@app.command("create-demo")
def create_demo(
    case_id: Annotated[str, typer.Argument(help="New case ID")],
    cell_id: Annotated[str, typer.Argument(help="Preregistration cell ID")],
    metric_key: Annotated[str, typer.Argument(help="Observed metric key")] = "task.completion.rate",
    metric_version: Annotated[str, typer.Argument(help="Metric version")] = "1.0",
    unit: Annotated[str, typer.Argument(help="Unit")] = "ratio",
) -> None:
    """Create a demo pending case in the in-memory inbox (manual only)."""
    service = get_global_service()
    demo_artifact = hashlib_hex(f"demo-artifact:{case_id}")
    demo_contract = hashlib_hex(f"demo-contract:{case_id}")
    try:
        case = service.create_case(
            case_id=case_id,
            candidate_artifact_fingerprint=demo_artifact,
            expected_preregistration_cell_id=cell_id,
            observed_metric_key=metric_key,
            observed_metric_version=metric_version,
            observed_metric_unit=unit,
            evidence_mode=EvidenceMode.IMPORTED_EVIDENCE,
            source_contract_result_fingerprint=demo_contract,
            rights_privacy_standing=RightsPrivacyStanding.ALLOWED,
            validation_standing=ValidationStanding.VALIDATED,
            compatibility_standing=CompatibilityStanding.COMPATIBLE,
            findings=[],
            created_at=datetime.now(UTC),
        )
    except EvidenceAdmissionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(case_to_json(case))


@app.command("decide")
def decide(
    case_id: Annotated[str, typer.Argument(help="Case ID")],
    decision: Annotated[
        str,
        typer.Argument(
            help="Target state: needs_information, admitted, rejected, pending, withdrawn"
        ),
    ],
    reason: Annotated[str, typer.Option(help="Human reason for the decision")] = "reviewed",
    reviewer: Annotated[
        str, typer.Option(help="Reviewer label or pseudonymous ID")
    ] = "reviewer-demo",
    requested_field: Annotated[
        list[str] | None,
        typer.Option(help="Requested information field (repeatable)"),
    ] = None,
) -> None:
    """Append one human decision to the hash-chained ledger (refuses invalid)."""
    service = get_global_service()
    try:
        target = EvidenceReviewState(decision)
    except ValueError as err:
        typer.echo(f"unknown decision {decision!r}", err=True)
        raise typer.Exit(2) from err
    try:
        ledger = service.get_ledger(case_id)
        decision_id = f"dec-{case_id}-{len(ledger.decisions) + 1}"
    except EvidenceAdmissionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    try:
        entry = service.append_decision(
            case_id=case_id,
            decision_id=decision_id,
            decision=target,
            reason=reason,
            reviewer_label=reviewer,
            decision_timestamp=datetime.now(UTC),
            requested_information_fields=list(requested_field or []),
        )
    except EvidenceAdmissionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(
        json.dumps(
            entry.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
    )


@app.command("export")
def export_attachment(
    case_id: Annotated[str, typer.Argument(help="Admitted case ID to export")],
) -> None:
    """Export admitted EvidenceAttachment for one admitted case (fail closed)."""
    service = get_global_service()
    try:
        exp = service.export_admitted_attachment(case_id)
    except EvidenceAdmissionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(admitted_attachment_to_json(exp))


@app.command("ledger")
def ledger_json(
    case_id: Annotated[str, typer.Argument(help="Case ID")],
) -> None:
    """Emit deterministic ledger JSON for one case (no private paths)."""
    service = get_global_service()
    try:
        ledger = service.get_ledger(case_id)
    except EvidenceAdmissionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(ledger_to_json(ledger))


@app.command("summary-csv")
def summary_csv() -> None:
    """Emit deterministic review-summary CSV for all cases in this process."""
    service = get_global_service()
    typer.echo(review_summary_to_csv(service))


@app.command("receipt")
def receipt(
    case_id: Annotated[str, typer.Argument(help="Case ID")],
    decision_id: Annotated[str, typer.Argument(help="Decision ID")],
) -> None:
    """Emit portable receipt for one ledger decision (no credential data)."""
    service = get_global_service()
    try:
        case = service.get_case(case_id)
        ledger = service.get_ledger(case_id)
        decision = next(d for d in ledger.decisions if d.decision_id == decision_id)
    except (EvidenceAdmissionError, StopIteration) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    rec = build_receipt(case=case, ledger=ledger, decision=decision)
    typer.echo(receipt_to_json(rec))


def hashlib_hex(seed: str) -> str:
    import hashlib

    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    app()
