"""Offline re-verification of one already-executed VEC campaign.

An examiner should not have to trust the campaign service's own summary of what
it did. This module re-derives that summary from the artifacts left on disk and
reports every place the two disagree. It re-runs the checks the service made at
execution time, against the files as they exist now:

* the **design fingerprint** the receipt recorded is recomputed from the design
  the caller supplies, so a receipt cannot be paired with a different matrix;
* every **cell** is re-derived from the design grid and matched to the receipt,
  and each executed cell's `execution_receipt.json` is re-read and its request
  fingerprint, terminal status, and own fingerprint re-compared;
* every **published output file** named by an execution receipt is re-hashed on
  disk and compared to the hash the receipt published;
* every **admitted cell** is looked up in the registry under the identity the
  admission policy derives from its receipt (``vec:fresh:<receipt[:16]>``),
  together with the metric collection stored under that same identity;
* the **approval block** is checked for presence and its predeclaration digest
  is re-hashed against the document on disk.

**It only reads.** There is no repair path, no reconciliation, no "fix" flag,
and no write of any kind — not to the campaign directory, not to the registry,
not to the predeclaration. A verifier that could repair its subject would be
able to manufacture the agreement it claims to have found, so the two type-level
literals ``repairs_performed`` and ``writes_performed`` are fixed ``False`` and
the registry is reached only through the public read methods of
:class:`~traffictwin.storage.registry.Registry`.

One honest caveat about "read-only". The public :class:`Registry` read methods
apply their own idempotent schema migration when they open a database, so
pointing this verifier at a registry can create or update that registry's schema
tables exactly as any other reader would. No run, metric collection, experiment,
annotation, bundle record, or evidence pack is ever inserted, updated, or
deleted by this module, and no campaign artifact is touched at all.

**A PASS is a consistency statement, not a scientific one.** It says the
artifacts agree with each other and with the design they claim to implement. It
says nothing about whether the design was a good one, whether the numbers mean
what someone hopes they mean, or whether any result is accepted, reproduced, or
approved. A campaign that halted on failure verifies cleanly when its receipt
faithfully records the halt.

**Absent evidence is a finding, never a pass.** A missing cell directory, an
unreadable receipt, a registry that cannot be opened, or a predeclaration that
is not on disk each produce a finding; none of them is silently skipped, and
none is treated as agreement. The one exception is deliberate and explicit: when
the caller passes no registry path the registry checks are recorded as *not
run*, and the report says so rather than implying they passed.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import Field

from traffictwin.integration.vec_campaign.models import (
    VecCampaignCell,
    VecCampaignCellState,
    VecCampaignDesign,
    VecCampaignModel,
    VecCampaignReceipt,
)
from traffictwin.integration.vec_fresh_admission.models import VecPairingSeedSource
from traffictwin.integration.vec_runner.models import VecExecutionReceipt, VecTerminalStatus
from traffictwin.storage.registry import Registry, RegistryError

VEC_CAMPAIGN_VERIFY_METHOD_VERSION: Literal["vec-campaign-verification-1.0"] = (
    "vec-campaign-verification-1.0"
)

#: The campaign service writes one of these per executed cell directory.
CELL_RECEIPT_FILE = "execution_receipt.json"

#: The campaign service writes this at the campaign root.
CAMPAIGN_RECEIPT_FILE = "campaign_receipt.json"

_HASH_CHUNK_BYTES = 1024 * 1024

#: Refuse implausibly large JSON rather than loading it into memory.
MAX_RECEIPT_BYTES = 64 * 1024 * 1024

#: States whose cell directory is expected to hold a completed execution receipt.
_EXECUTED_STATES = frozenset(
    {
        VecCampaignCellState.ADMITTED,
        VecCampaignCellState.REUSED,
        VecCampaignCellState.ADMISSION_REFUSED,
    }
)

#: States that must carry registry admission evidence.
_ADMITTED_STATES = frozenset({VecCampaignCellState.ADMITTED, VecCampaignCellState.REUSED})

STANDING_VERIFICATION_LIMITATIONS = (
    "Consistency verification only: a PASS states that the recorded artifacts agree "
    "with each other and with the supplied design, and is not a scientific finding, "
    "an accepted result, a reproduction, or supervisor approval.",
    "Read-only by construction: nothing is written, repaired, reconciled, or "
    "re-executed, and the registry is consulted through public read methods only.",
    "The design is supplied by the caller. Verification proves the artifacts match "
    "that design; it cannot prove the supplied design is the one a person approved.",
    "Re-hashing proves the published bytes are unchanged since the receipt was "
    "written. It does not re-run the evaluator and establishes no numerical "
    "reproduction of any result.",
    "A campaign that failed or halted verifies cleanly when its receipt records the "
    "failure faithfully; PASS is never a statement that the campaign succeeded.",
)


class CampaignVerificationError(RuntimeError):
    """Raised when verification cannot be performed at all.

    Distinct from a verification *failure*: a failure is a finding about the
    campaign, whereas this means the check itself could not be carried out —
    an unreadable campaign receipt, a design module that will not import.
    """


class VerificationCheck(StrEnum):
    """The named check groups a report can run."""

    DESIGN_FINGERPRINT = "design_fingerprint"
    CELL_GRID = "cell_grid"
    CELL_RECEIPTS = "cell_receipts"
    OUTPUT_HASHES = "output_hashes"
    REGISTRY_ADMISSION = "registry_admission"
    APPROVAL = "approval"


class VerificationSeverity(StrEnum):
    """How a finding bears on the PASS/FAIL summary."""

    #: Contradicts the recorded evidence; forces FAIL.
    FAILURE = "failure"
    #: Evidence is absent or could not be reached; reported, never a silent pass.
    WARNING = "warning"


class VerificationFinding(VecCampaignModel):
    """One disagreement between the recorded evidence and the artifacts."""

    check: VerificationCheck
    severity: VerificationSeverity
    code: str = Field(min_length=1, max_length=100)
    subject: str = Field(min_length=1, max_length=400)
    detail: str = Field(min_length=1, max_length=2_000)
    expected: str | None = Field(default=None, max_length=400)
    observed: str | None = Field(default=None, max_length=400)


class CampaignVerificationReport(VecCampaignModel):
    """Complete typed outcome of one offline verification pass."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["vec-campaign-verification-1.0"] = VEC_CAMPAIGN_VERIFY_METHOD_VERSION
    campaign_directory: str
    experiment_id: str
    phase: str
    campaign_status: str
    design_fingerprint_expected: str = Field(pattern=r"^[0-9a-f]{64}$")
    design_fingerprint_recorded: str = Field(pattern=r"^[0-9a-f]{64}$")
    checks_run: list[VerificationCheck]
    checks_not_run: list[VerificationCheck] = Field(default_factory=list)
    planned_cell_count: int = Field(ge=0)
    cells_examined: int = Field(ge=0)
    executed_cells_examined: int = Field(ge=0)
    admitted_cells_examined: int = Field(ge=0)
    output_files_hashed: int = Field(ge=0)
    output_bytes_hashed: int = Field(ge=0)
    findings: list[VerificationFinding] = Field(default_factory=list)
    passed: bool
    repairs_performed: Literal[False] = False
    writes_performed: Literal[False] = False
    limitations: list[str] = Field(min_length=1, max_length=16)

    def failures(self) -> list[VerificationFinding]:
        """Return only the findings that force a FAIL."""

        return [f for f in self.findings if f.severity is VerificationSeverity.FAILURE]

    def warnings(self) -> list[VerificationFinding]:
        """Return only the findings that report unreachable or absent evidence."""

        return [f for f in self.findings if f.severity is VerificationSeverity.WARNING]


def load_design_from_module(module_path: str | Path, attribute: str) -> VecCampaignDesign:
    """Import a campaign design from a repository script's constructor.

    The design lives beside the campaign script that ran it, so verification
    reads it from there rather than duplicating the matrix. The module is
    *imported*, which executes its top level: pass only a trusted repository
    script, never an artifact that arrived with the campaign directory being
    verified.
    """

    path = Path(module_path)
    if path.is_symlink() or not path.is_file():
        raise CampaignVerificationError(f"design module is missing or unsafe: {module_path}")
    spec = importlib.util.spec_from_file_location(f"_tt_campaign_design_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise CampaignVerificationError(f"design module cannot be imported: {module_path}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get(spec.name)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - any import error is a usage error here
        raise CampaignVerificationError(f"design module failed to import: {exc}") from exc
    finally:
        if previous is None:
            sys.modules.pop(spec.name, None)
        else:
            sys.modules[spec.name] = previous
    constructor = getattr(module, attribute, None)
    if constructor is None:
        raise CampaignVerificationError(
            f"design module {module_path} exposes no attribute {attribute!r}"
        )
    design = constructor() if callable(constructor) else constructor
    if not isinstance(design, VecCampaignDesign):
        raise CampaignVerificationError(
            f"{module_path}:{attribute} produced {type(design).__name__}, not a VecCampaignDesign"
        )
    return design


def load_campaign_receipt(campaign_directory: str | Path) -> VecCampaignReceipt:
    """Read and validate the campaign receipt at a campaign directory root."""

    path = Path(campaign_directory) / CAMPAIGN_RECEIPT_FILE
    return VecCampaignReceipt.model_validate_json(_read_json_text(path, "campaign receipt"))


def verify_campaign(
    design: VecCampaignDesign,
    campaign_directory: str | Path,
    *,
    registry_path: str | Path | None = None,
    predeclaration_root: str | Path = Path(),
    hash_outputs: bool = True,
) -> CampaignVerificationReport:
    """Re-verify one executed campaign against its design and artifacts.

    ``registry_path`` may be omitted, in which case the registry checks are
    recorded in ``checks_not_run`` rather than reported as passed. Set
    ``hash_outputs`` to ``False`` to skip re-hashing published payloads when
    only the receipt-level structure is in question; the skip is likewise
    recorded rather than implied.
    """

    root = Path(campaign_directory)
    receipt = load_campaign_receipt(root)
    findings: list[VerificationFinding] = []

    findings.extend(_check_design_fingerprint(design, receipt))
    findings.extend(_check_approval(design, receipt, Path(predeclaration_root)))
    grid_findings, matched = _check_cell_grid(design, receipt)
    findings.extend(grid_findings)

    executed = 0
    admitted = 0
    files_hashed = 0
    bytes_hashed = 0
    registry = _open_registry(registry_path) if registry_path is not None else None
    if registry_path is not None and registry is None:
        findings.append(
            VerificationFinding(
                check=VerificationCheck.REGISTRY_ADMISSION,
                severity=VerificationSeverity.WARNING,
                code="REGISTRY_UNREADABLE",
                subject=str(registry_path),
                detail=(
                    "the registry could not be opened, so admission evidence was not "
                    "checked for any cell"
                ),
            )
        )

    for cell in receipt.cells:
        cell_dir = root / cell.output_directory_name
        execution_receipt: VecExecutionReceipt | None = None
        if cell.state in _EXECUTED_STATES:
            executed += 1
            execution_receipt, receipt_findings = _load_cell_receipt(cell, cell_dir)
            findings.extend(receipt_findings)
            if execution_receipt is not None:
                findings.extend(_check_cell_receipt(cell, execution_receipt))
                if hash_outputs:
                    hash_findings, hashed, byte_total = _check_output_hashes(
                        cell, cell_dir, execution_receipt
                    )
                    findings.extend(hash_findings)
                    files_hashed += hashed
                    bytes_hashed += byte_total
        if cell.state in _ADMITTED_STATES:
            admitted += 1
            if registry is not None:
                findings.extend(_check_registry_admission(design, cell, registry))

    if registry is not None:
        findings.extend(_check_registry_experiment(design, registry))

    checks_run = [
        VerificationCheck.DESIGN_FINGERPRINT,
        VerificationCheck.CELL_GRID,
        VerificationCheck.CELL_RECEIPTS,
        VerificationCheck.APPROVAL,
    ]
    checks_not_run: list[VerificationCheck] = []
    (checks_run if hash_outputs else checks_not_run).append(VerificationCheck.OUTPUT_HASHES)
    (checks_run if registry is not None else checks_not_run).append(
        VerificationCheck.REGISTRY_ADMISSION
    )

    return CampaignVerificationReport(
        campaign_directory=str(root),
        experiment_id=receipt.experiment_id,
        phase=str(receipt.phase),
        campaign_status=str(receipt.status),
        design_fingerprint_expected=design.fingerprint(),
        design_fingerprint_recorded=receipt.design_fingerprint,
        checks_run=sorted(checks_run),
        checks_not_run=sorted(checks_not_run),
        planned_cell_count=receipt.planned_cell_count,
        cells_examined=len(matched),
        executed_cells_examined=executed,
        admitted_cells_examined=admitted,
        output_files_hashed=files_hashed,
        output_bytes_hashed=bytes_hashed,
        findings=findings,
        passed=not any(f.severity is VerificationSeverity.FAILURE for f in findings),
        limitations=list(STANDING_VERIFICATION_LIMITATIONS),
    )


def render_verification_markdown(report: CampaignVerificationReport) -> str:
    """Render one verification report as a deterministic markdown exhibit."""

    verdict = "PASS" if report.passed else "FAIL"
    lines = [
        f"# Campaign verification — {report.experiment_id} ({verdict})",
        "",
        f"- Campaign directory: `{report.campaign_directory}`",
        f"- Campaign phase: {report.phase}",
        f"- Recorded campaign status: {report.campaign_status}",
        f"- Design fingerprint (recomputed): `{report.design_fingerprint_expected}`",
        f"- Design fingerprint (recorded): `{report.design_fingerprint_recorded}`",
        f"- Method version: {report.method_version}",
        "",
        "## Coverage",
        "",
        f"- Planned cells: {report.planned_cell_count}",
        f"- Cells matched to the design grid: {report.cells_examined}",
        f"- Executed cells re-read: {report.executed_cells_examined}",
        f"- Admitted cells checked against the registry: {report.admitted_cells_examined}",
        (
            f"- Output files re-hashed: {report.output_files_hashed} "
            f"({report.output_bytes_hashed} bytes)"
        ),
        f"- Checks run: {', '.join(str(check) for check in report.checks_run) or 'none'}",
        f"- Checks not run: {', '.join(str(check) for check in report.checks_not_run) or 'none'}",
        "",
        "## Findings",
        "",
    ]
    if not report.findings:
        lines.append("No finding: every recorded artifact agreed with the supplied design.")
    else:
        lines.extend(
            [
                "| Severity | Check | Code | Subject | Expected | Observed | Detail |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for finding in report.findings:
            lines.append(
                f"| {finding.severity} | {finding.check} | {finding.code} "
                f"| {finding.subject} | {finding.expected or '—'} "
                f"| {finding.observed or '—'} | {finding.detail} |"
            )
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in report.limitations)
    lines.append("")
    return "\n".join(lines)


def _check_design_fingerprint(
    design: VecCampaignDesign, receipt: VecCampaignReceipt
) -> list[VerificationFinding]:
    findings: list[VerificationFinding] = []
    expected = design.fingerprint()
    if expected != receipt.design_fingerprint:
        findings.append(
            VerificationFinding(
                check=VerificationCheck.DESIGN_FINGERPRINT,
                severity=VerificationSeverity.FAILURE,
                code="DESIGN_FINGERPRINT_MISMATCH",
                subject="campaign_receipt.json",
                detail=(
                    "the receipt was written by a different design than the one supplied; "
                    "the two cannot be read as one experiment"
                ),
                expected=expected,
                observed=receipt.design_fingerprint,
            )
        )
    if design.experiment_id != receipt.experiment_id:
        findings.append(
            VerificationFinding(
                check=VerificationCheck.DESIGN_FINGERPRINT,
                severity=VerificationSeverity.FAILURE,
                code="EXPERIMENT_ID_MISMATCH",
                subject="campaign_receipt.json",
                detail="the receipt records a different experiment identifier than the design",
                expected=design.experiment_id,
                observed=receipt.experiment_id,
            )
        )
    if design.phase is not receipt.phase:
        findings.append(
            VerificationFinding(
                check=VerificationCheck.DESIGN_FINGERPRINT,
                severity=VerificationSeverity.FAILURE,
                code="PHASE_MISMATCH",
                subject="campaign_receipt.json",
                detail="the receipt records a different seed cohort than the design declares",
                expected=str(design.phase),
                observed=str(receipt.phase),
            )
        )
    return findings


def _check_approval(
    design: VecCampaignDesign, receipt: VecCampaignReceipt, predeclaration_root: Path
) -> list[VerificationFinding]:
    findings: list[VerificationFinding] = []
    approval = receipt.approval
    if approval != design.approval:
        findings.append(
            VerificationFinding(
                check=VerificationCheck.APPROVAL,
                severity=VerificationSeverity.FAILURE,
                code="APPROVAL_BLOCK_MISMATCH",
                subject="campaign_receipt.json",
                detail=(
                    "the approval recorded in the receipt differs from the approval the "
                    "supplied design carries"
                ),
                expected=design.approval.predeclaration_sha256,
                observed=approval.predeclaration_sha256,
            )
        )
    candidate = Path(approval.predeclaration_path)
    path = candidate if candidate.is_absolute() else predeclaration_root / candidate
    if path.is_symlink() or not path.is_file():
        findings.append(
            VerificationFinding(
                check=VerificationCheck.APPROVAL,
                severity=VerificationSeverity.WARNING,
                code="PREDECLARATION_MISSING",
                subject=approval.predeclaration_path,
                detail=(
                    "the approved predeclaration is not present at the recorded path, so its "
                    "digest could not be re-checked against the file on disk"
                ),
                expected=approval.predeclaration_sha256,
            )
        )
        return findings
    digest = _file_sha256(path)
    if digest != approval.predeclaration_sha256:
        findings.append(
            VerificationFinding(
                check=VerificationCheck.APPROVAL,
                severity=VerificationSeverity.FAILURE,
                code="PREDECLARATION_DIGEST_MISMATCH",
                subject=approval.predeclaration_path,
                detail=(
                    "the predeclaration on disk no longer hashes to the digest that was "
                    "approved; the document changed after approval"
                ),
                expected=approval.predeclaration_sha256,
                observed=digest,
            )
        )
    if not receipt.predeclaration_verified_unchanged:
        findings.append(
            VerificationFinding(
                check=VerificationCheck.APPROVAL,
                severity=VerificationSeverity.WARNING,
                code="PREDECLARATION_NOT_VERIFIED_AT_RUN",
                subject="campaign_receipt.json",
                detail=(
                    "the campaign itself did not record the predeclaration as verified "
                    "unchanged when it ran"
                ),
            )
        )
    return findings


def _check_cell_grid(
    design: VecCampaignDesign, receipt: VecCampaignReceipt
) -> tuple[list[VerificationFinding], dict[tuple[str, int], VecCampaignCell]]:
    findings: list[VerificationFinding] = []
    recorded: dict[tuple[str, int], VecCampaignCell] = {}
    for cell in receipt.cells:
        key = (cell.arm_label, cell.fleet_seed)
        if key in recorded:
            findings.append(
                VerificationFinding(
                    check=VerificationCheck.CELL_GRID,
                    severity=VerificationSeverity.FAILURE,
                    code="DUPLICATE_CELL",
                    subject=f"{cell.arm_label}/fs{cell.fleet_seed}",
                    detail="the receipt records more than one outcome for the same design cell",
                )
            )
            continue
        recorded[key] = cell

    expected_keys: set[tuple[str, int]] = set()
    for arm in design.arms():
        for seed in design.fleet_seeds:
            key = (arm.label, seed)
            expected_keys.add(key)
            declared = recorded.get(key)
            if declared is None:
                findings.append(
                    VerificationFinding(
                        check=VerificationCheck.CELL_GRID,
                        severity=VerificationSeverity.FAILURE,
                        code="CELL_MISSING_FROM_RECEIPT",
                        subject=f"{arm.label}/fs{seed}",
                        detail="the design declares this cell but the receipt records no outcome",
                    )
                )
                continue
            expected_run_id = design.cell_run_id(arm.label, seed)
            if declared.run_id != expected_run_id:
                findings.append(
                    VerificationFinding(
                        check=VerificationCheck.CELL_GRID,
                        severity=VerificationSeverity.FAILURE,
                        code="CELL_RUN_ID_MISMATCH",
                        subject=f"{arm.label}/fs{seed}",
                        detail="the recorded run id is not the one the design composes",
                        expected=expected_run_id,
                        observed=declared.run_id,
                    )
                )
            expected_fingerprint = design.cell_request(arm, seed).fingerprint()
            if declared.request_fingerprint != expected_fingerprint:
                findings.append(
                    VerificationFinding(
                        check=VerificationCheck.CELL_GRID,
                        severity=VerificationSeverity.FAILURE,
                        code="CELL_REQUEST_FINGERPRINT_MISMATCH",
                        subject=f"{arm.label}/fs{seed}",
                        detail=(
                            "the recorded request fingerprint is not the one the design's "
                            "controls produce for this cell"
                        ),
                        expected=expected_fingerprint,
                        observed=declared.request_fingerprint,
                    )
                )

    for key in sorted(set(recorded) - expected_keys):
        findings.append(
            VerificationFinding(
                check=VerificationCheck.CELL_GRID,
                severity=VerificationSeverity.FAILURE,
                code="CELL_NOT_IN_DESIGN",
                subject=f"{key[0]}/fs{key[1]}",
                detail="the receipt records a cell the supplied design does not declare",
            )
        )
    return findings, recorded


def _load_cell_receipt(
    cell: VecCampaignCell, cell_dir: Path
) -> tuple[VecExecutionReceipt | None, list[VerificationFinding]]:
    path = cell_dir / CELL_RECEIPT_FILE
    if not cell_dir.is_dir():
        return None, [
            VerificationFinding(
                check=VerificationCheck.CELL_RECEIPTS,
                severity=VerificationSeverity.WARNING,
                code="CELL_DIRECTORY_MISSING",
                subject=cell.output_directory_name,
                detail=(
                    "the receipt records an executed cell but its output directory is not "
                    "present, so nothing about it could be re-checked"
                ),
            )
        ]
    if path.is_symlink() or not path.is_file():
        return None, [
            VerificationFinding(
                check=VerificationCheck.CELL_RECEIPTS,
                severity=VerificationSeverity.WARNING,
                code="CELL_RECEIPT_MISSING",
                subject=f"{cell.output_directory_name}/{CELL_RECEIPT_FILE}",
                detail="the executed cell has no readable execution receipt on disk",
            )
        ]
    try:
        text = _read_json_text(path, "execution receipt")
        execution_receipt = VecExecutionReceipt.model_validate_json(text)
    except (CampaignVerificationError, ValueError) as exc:
        return None, [
            VerificationFinding(
                check=VerificationCheck.CELL_RECEIPTS,
                severity=VerificationSeverity.FAILURE,
                code="CELL_RECEIPT_INVALID",
                subject=f"{cell.output_directory_name}/{CELL_RECEIPT_FILE}",
                detail=f"the execution receipt is not a valid VEC-07 receipt: {exc}"[:2_000],
            )
        ]
    return execution_receipt, []


def _check_cell_receipt(
    cell: VecCampaignCell, execution_receipt: VecExecutionReceipt
) -> list[VerificationFinding]:
    findings: list[VerificationFinding] = []
    subject = f"{cell.output_directory_name}/{CELL_RECEIPT_FILE}"
    if execution_receipt.request_fingerprint != cell.request_fingerprint:
        findings.append(
            VerificationFinding(
                check=VerificationCheck.CELL_RECEIPTS,
                severity=VerificationSeverity.FAILURE,
                code="RECEIPT_REQUEST_FINGERPRINT_MISMATCH",
                subject=subject,
                detail=(
                    "the execution receipt in this directory was produced by a different "
                    "request than the campaign cell claims"
                ),
                expected=cell.request_fingerprint,
                observed=execution_receipt.request_fingerprint,
            )
        )
    if execution_receipt.request.run_id != cell.run_id:
        findings.append(
            VerificationFinding(
                check=VerificationCheck.CELL_RECEIPTS,
                severity=VerificationSeverity.FAILURE,
                code="RECEIPT_RUN_ID_MISMATCH",
                subject=subject,
                detail="the execution receipt names a different run than the campaign cell",
                expected=cell.run_id,
                observed=execution_receipt.request.run_id,
            )
        )
    if execution_receipt.status is not VecTerminalStatus.COMPLETED:
        severity = (
            VerificationSeverity.FAILURE
            if cell.state in _ADMITTED_STATES
            else VerificationSeverity.WARNING
        )
        findings.append(
            VerificationFinding(
                check=VerificationCheck.CELL_RECEIPTS,
                severity=severity,
                code="RECEIPT_STATUS_NOT_COMPLETED",
                subject=subject,
                detail=(
                    "the campaign cell records an admitted outcome but its execution "
                    "receipt did not complete"
                    if cell.state in _ADMITTED_STATES
                    else "the execution receipt in this directory did not complete"
                ),
                expected=str(VecTerminalStatus.COMPLETED),
                observed=str(execution_receipt.status),
            )
        )
    recomputed = execution_receipt.fingerprint()
    if cell.receipt_fingerprint is None:
        findings.append(
            VerificationFinding(
                check=VerificationCheck.CELL_RECEIPTS,
                severity=VerificationSeverity.WARNING,
                code="CELL_RECEIPT_FINGERPRINT_ABSENT",
                subject=subject,
                detail=(
                    "an execution receipt is present on disk but the campaign cell recorded "
                    "no receipt fingerprint to compare it against"
                ),
                observed=recomputed,
            )
        )
    elif cell.receipt_fingerprint != recomputed:
        findings.append(
            VerificationFinding(
                check=VerificationCheck.CELL_RECEIPTS,
                severity=VerificationSeverity.FAILURE,
                code="CELL_RECEIPT_FINGERPRINT_MISMATCH",
                subject=subject,
                detail=(
                    "the execution receipt on disk does not hash to the fingerprint the "
                    "campaign recorded for this cell"
                ),
                expected=cell.receipt_fingerprint,
                observed=recomputed,
            )
        )
    return findings


def _check_output_hashes(
    cell: VecCampaignCell, cell_dir: Path, execution_receipt: VecExecutionReceipt
) -> tuple[list[VerificationFinding], int, int]:
    findings: list[VerificationFinding] = []
    hashed = 0
    total_bytes = 0
    for item in execution_receipt.outputs:
        path = cell_dir / item.path
        subject = f"{cell.output_directory_name}/{item.path}"
        if path.is_symlink() or not path.is_file():
            findings.append(
                VerificationFinding(
                    check=VerificationCheck.OUTPUT_HASHES,
                    severity=VerificationSeverity.WARNING,
                    code="OUTPUT_FILE_MISSING",
                    subject=subject,
                    detail="the receipt publishes this output but it is not on disk",
                    expected=item.sha256,
                )
            )
            continue
        size = path.stat().st_size
        if size != item.size_bytes:
            findings.append(
                VerificationFinding(
                    check=VerificationCheck.OUTPUT_HASHES,
                    severity=VerificationSeverity.FAILURE,
                    code="OUTPUT_FILE_SIZE_MISMATCH",
                    subject=subject,
                    detail="the published output has a different size than the receipt records",
                    expected=str(item.size_bytes),
                    observed=str(size),
                )
            )
        digest = _file_sha256(path)
        hashed += 1
        total_bytes += size
        if digest != item.sha256:
            findings.append(
                VerificationFinding(
                    check=VerificationCheck.OUTPUT_HASHES,
                    severity=VerificationSeverity.FAILURE,
                    code="OUTPUT_FILE_HASH_MISMATCH",
                    subject=subject,
                    detail=(
                        "the published output no longer hashes to the value the receipt "
                        "recorded; the bytes changed after execution"
                    ),
                    expected=item.sha256,
                    observed=digest,
                )
            )
    return findings, hashed, total_bytes


def _check_registry_admission(
    design: VecCampaignDesign, cell: VecCampaignCell, registry: Registry
) -> list[VerificationFinding]:
    findings: list[VerificationFinding] = []
    subject = f"{cell.output_directory_name} ({cell.run_id})"
    if cell.receipt_fingerprint is None or cell.registry_run_id is None:
        findings.append(
            VerificationFinding(
                check=VerificationCheck.REGISTRY_ADMISSION,
                severity=VerificationSeverity.FAILURE,
                code="ADMISSION_EVIDENCE_ABSENT",
                subject=subject,
                detail="an admitted cell records no receipt fingerprint or registry run id",
            )
        )
        return findings

    expected_run_id = f"vec:fresh:{cell.receipt_fingerprint[:16]}"
    if cell.registry_run_id != expected_run_id:
        findings.append(
            VerificationFinding(
                check=VerificationCheck.REGISTRY_ADMISSION,
                severity=VerificationSeverity.FAILURE,
                code="REGISTRY_RUN_ID_NOT_RECEIPT_DERIVED",
                subject=subject,
                detail=(
                    "the registry identity is not the one the admission policy derives from "
                    "this cell's receipt fingerprint"
                ),
                expected=expected_run_id,
                observed=cell.registry_run_id,
            )
        )

    try:
        run = registry.get_run(cell.registry_run_id)
    except RegistryError:
        findings.append(
            VerificationFinding(
                check=VerificationCheck.REGISTRY_ADMISSION,
                severity=VerificationSeverity.FAILURE,
                code="REGISTRY_RUN_MISSING",
                subject=subject,
                detail="the admitted cell has no run under its recorded identity in the registry",
                expected=cell.registry_run_id,
            )
        )
    else:
        if run.experiment_id != design.experiment_id:
            findings.append(
                VerificationFinding(
                    check=VerificationCheck.REGISTRY_ADMISSION,
                    severity=VerificationSeverity.FAILURE,
                    code="REGISTRY_RUN_EXPERIMENT_MISMATCH",
                    subject=subject,
                    detail="the registry run is attached to a different experiment",
                    expected=design.experiment_id,
                    observed=str(run.experiment_id),
                )
            )
        if run.seed_id != cell.arm_label:
            findings.append(
                VerificationFinding(
                    check=VerificationCheck.REGISTRY_ADMISSION,
                    severity=VerificationSeverity.FAILURE,
                    code="REGISTRY_RUN_ARM_MISMATCH",
                    subject=subject,
                    detail="the registry run records a different arm than the campaign cell",
                    expected=cell.arm_label,
                    observed=run.seed_id,
                )
            )
        expected_seed = _expected_pairing_seed(design, cell)
        if run.random_seed != expected_seed:
            findings.append(
                VerificationFinding(
                    check=VerificationCheck.REGISTRY_ADMISSION,
                    severity=VerificationSeverity.FAILURE,
                    code="REGISTRY_RUN_PAIRING_SEED_MISMATCH",
                    subject=subject,
                    detail=(
                        "the registry run's pairing seed is not the one the design's declared "
                        "pairing seed source gives this cell"
                    ),
                    expected=str(expected_seed),
                    observed=str(run.random_seed),
                )
            )

    try:
        registry.get_metric_collection_json(cell.registry_run_id)
    except RegistryError:
        findings.append(
            VerificationFinding(
                check=VerificationCheck.REGISTRY_ADMISSION,
                severity=VerificationSeverity.FAILURE,
                code="METRIC_COLLECTION_MISSING",
                subject=subject,
                detail=(
                    "the admitted cell has no metric collection stored under its registry "
                    "identity, so the admission produced no study-visible metrics"
                ),
                expected=cell.registry_run_id,
            )
        )
    return findings


def _check_registry_experiment(
    design: VecCampaignDesign, registry: Registry
) -> list[VerificationFinding]:
    try:
        experiment = registry.get_experiment(design.experiment_id)
    except RegistryError:
        return [
            VerificationFinding(
                check=VerificationCheck.REGISTRY_ADMISSION,
                severity=VerificationSeverity.FAILURE,
                code="REGISTRY_EXPERIMENT_MISSING",
                subject=design.experiment_id,
                detail="the declared experiment plan is not registered in this registry",
            )
        ]
    findings: list[VerificationFinding] = []
    expected_arms = sorted(arm.label for arm in design.variation_arms)
    if sorted(experiment.variation_seed_ids) != expected_arms:
        findings.append(
            VerificationFinding(
                check=VerificationCheck.REGISTRY_ADMISSION,
                severity=VerificationSeverity.FAILURE,
                code="REGISTRY_EXPERIMENT_ARMS_MISMATCH",
                subject=design.experiment_id,
                detail="the registered plan declares different variation arms than the design",
                expected=", ".join(expected_arms),
                observed=", ".join(sorted(experiment.variation_seed_ids)),
            )
        )
    if sorted(experiment.common_random_seed_set) != sorted(design.fleet_seeds):
        findings.append(
            VerificationFinding(
                check=VerificationCheck.REGISTRY_ADMISSION,
                severity=VerificationSeverity.FAILURE,
                code="REGISTRY_EXPERIMENT_SEEDS_MISMATCH",
                subject=design.experiment_id,
                detail="the registered plan declares a different common seed set than the design",
                expected=str(sorted(design.fleet_seeds)),
                observed=str(sorted(experiment.common_random_seed_set)),
            )
        )
    return findings


def _expected_pairing_seed(design: VecCampaignDesign, cell: VecCampaignCell) -> int:
    if design.pairing_seed_source is VecPairingSeedSource.FLEET_SEED:
        return cell.fleet_seed
    return design.evaluator_seed


def _open_registry(registry_path: str | Path) -> Registry | None:
    path = Path(registry_path)
    if path.is_symlink() or not path.is_file():
        return None
    registry = Registry(path)
    try:
        registry.inspect()
    except (RegistryError, OSError):
        return None
    return registry


def _read_json_text(path: Path, label: str) -> str:
    if path.is_symlink() or not path.is_file():
        raise CampaignVerificationError(f"{label} is missing or unsafe: {path}")
    size = path.stat().st_size
    if size > MAX_RECEIPT_BYTES:
        raise CampaignVerificationError(f"{label} is implausibly large ({size} bytes): {path}")
    text = path.read_text(encoding="utf-8")
    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        raise CampaignVerificationError(f"{label} is not valid JSON: {path}") from exc
    return text


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(_HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()
