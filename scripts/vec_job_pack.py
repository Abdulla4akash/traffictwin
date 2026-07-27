"""Operational command line over the CSF job-pack contract.

The Phase 56 library (:mod:`traffictwin.integration.vec_campaign.job_pack`) is
pure and has no entry point. This script is that entry point and nothing more:
it resolves a design, resolves the input manifest, calls the library, and prints
what the library said. Every refusal the library raises is passed through
verbatim rather than being reworded into something friendlier — a provenance
refusal that has been softened on its way to a terminal is a refusal somebody
will talk themselves past.

**There is still no executor.** No SSH, no network call, no scheduler, no
submission, no transfer. ``export`` writes a JSON file a person carries; ``verify``
reads a directory a person carried back.

**No clock.** ``--created-at-utc`` is a required argument because the library
takes the timestamp as an argument, so the same design and checkout always
produce the same pack bytes. A pack nobody can reproduce is a pack nobody can
check.

**Hashes are the audited pins; only sizes are measured.** The manifest a pack
carries must declare the pinned SHA-256 for every input — the library refuses any
other value — so this script never invents a hash and never launders a local file
into an identity. It reads two things off the supplied checkouts: each file's
size, and the checkout's HEAD commit, which must equal the audited commit for
that repository. ``--verify-input-hashes`` additionally re-hashes every declared
input before the pack is written; it is off by default because re-reading
multi-gigabyte traces is exactly the sustained I/O that must not run beside a
live campaign, and because the remote site is required to reproduce the pinned
hash regardless of what any local checkout contains.

**Exit codes are 0 and 1.** For ``verify``, only a ``verified`` import exits 0:
``partial`` and ``refused`` are both "do not read this yet", and a script that
exited 0 on a partial import would be the thing that lets a half-returned
campaign be read as a whole one.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Literal

from traffictwin.integration.vec_campaign.job_pack import (
    AUDITED_REPOSITORY_COMMITS,
    JobPackError,
    VecJobPack,
    VecJobPackImportStatus,
    VecJobPackImportVerification,
    VecJobPackInputRef,
    VecJobPackInputRole,
    build_job_pack,
    verify_job_pack_import,
)
from traffictwin.integration.vec_campaign.models import VecCampaignDesign
from traffictwin.integration.vec_runner.models import (
    PINNED_ACTORS,
    PINNED_EVALUATOR_FILES,
)

#: The two audited repositories, spelled the way the library's model spells them.
RepositoryName = Literal["vec_env", "tos-data"]

#: Repository each declared input role is checked out from.
TRACE_REPOSITORY: RepositoryName = "tos-data"
ACTOR_REPOSITORY: RepositoryName = "tos-data"
EVALUATOR_REPOSITORY: RepositoryName = "vec_env"

#: Filename the local runner writes for one cell's terminal evidence.
DEFAULT_RECEIPT_NAME = "execution_receipt.json"

GIT_TIMEOUT_SECONDS = 60
MAX_PACK_BYTES = 16 * 1024 * 1024
MAX_RECEIPT_BYTES = 8 * 1024 * 1024
HASH_CHUNK_BYTES = 1024 * 1024

#: Import statuses that mean "this is not yet safe to read downstream".
UNFAVOURABLE_STATUSES = (
    VecJobPackImportStatus.PARTIAL,
    VecJobPackImportStatus.REFUSED,
)


class JobPackCommandError(RuntimeError):
    """Raised when the command line cannot get as far as calling the library."""


def main(argv: list[str] | None = None) -> int:
    """Run one subcommand and report what the library decided."""

    parser = _build_parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "export":
            return _run_export(arguments)
        return _run_verify(arguments)
    except (JobPackCommandError, JobPackError) as error:
        # Library refusals reach the operator in the library's own words.
        print(f"error: {error}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vec_job_pack",
        description="Export an approved campaign design as a job pack, or verify what came back.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    export = subparsers.add_parser(
        "export",
        help="Write one approved design out as a fingerprinted job pack.",
        description=(
            "Export one already-approved campaign design as a job pack. Approval is the "
            "ADR-063 mechanism; this command neither grants nor re-opens it."
        ),
    )
    export.add_argument(
        "design_ref",
        help=(
            "MODULE:ATTRIBUTE naming the design, where MODULE is a dotted module or a "
            "path to a .py file and ATTRIBUTE is a VecCampaignDesign or a zero-argument "
            "factory for one, e.g. scripts/capacity_pilot_campaign.py:pilot_design"
        ),
    )
    export.add_argument("output_pack_json", type=Path, help="Path the pack JSON is written to.")
    export.add_argument("--pack-id", required=True, help="Identifier for this pack.")
    export.add_argument(
        "--created-at-utc",
        required=True,
        metavar="TIMESTAMP",
        help="Creation timestamp recorded in the pack. Supplied, never read from a clock.",
    )
    export.add_argument(
        "--tos-data-root",
        required=True,
        type=Path,
        help="Read-only path to the audited tos-data checkout (trace and actor sizes).",
    )
    export.add_argument(
        "--vec-env-root",
        required=True,
        type=Path,
        help="Read-only path to the audited vec_env checkout (evaluator source sizes).",
    )
    export.add_argument(
        "--verify-input-hashes",
        action="store_true",
        help=(
            "Re-hash every declared input and refuse on any mismatch. Off by default: it "
            "is sustained I/O that must not run beside a live campaign."
        ),
    )
    export.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing pack file instead of refusing.",
    )

    verify = subparsers.add_parser(
        "verify",
        help="Verify a returned receipt set against the pack that asked for it.",
        description=(
            "Verify returned results against their pack. A verified import is NOT a "
            "scientific admission: admission remains the local ADR-061 fresh-run path."
        ),
    )
    verify.add_argument("pack_json", type=Path, help="Path to the pack that was exported.")
    verify.add_argument(
        "results_dir",
        type=Path,
        help="Directory the returned results were unpacked into; searched recursively.",
    )
    verify.add_argument(
        "--receipt-name",
        default=DEFAULT_RECEIPT_NAME,
        help=f"Receipt filename to collect (default: {DEFAULT_RECEIPT_NAME}).",
    )
    verify.add_argument(
        "--returned-design-fingerprint",
        default=None,
        metavar="SHA256",
        help="Design fingerprint the remote site reported, when it reported one.",
    )
    verify.add_argument(
        "--report-json",
        type=Path,
        default=None,
        help="Optional path the full typed verification is written to.",
    )
    return parser


def _run_export(arguments: argparse.Namespace) -> int:
    output = Path(arguments.output_pack_json)
    if output.exists() and not arguments.overwrite:
        raise JobPackCommandError(f"{output} already exists; pass --overwrite to replace it")
    design = load_design(arguments.design_ref)
    roots = {
        "tos-data": Path(arguments.tos_data_root),
        "vec_env": Path(arguments.vec_env_root),
    }
    for repository, root in sorted(roots.items()):
        verify_checkout_commit(root, repository)
    inputs = resolve_manifest(
        design,
        roots=roots,
        verify_hashes=bool(arguments.verify_input_hashes),
    )
    pack = build_job_pack(
        design=design,
        pack_id=arguments.pack_id,
        created_at_utc=arguments.created_at_utc,
        inputs=inputs,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(pack.model_dump_json(indent=2) + "\n", encoding="utf-8")
    for line in render_export_summary(pack, output):
        print(line)
    return 0


def _run_verify(arguments: argparse.Namespace) -> int:
    pack = load_pack(Path(arguments.pack_json))
    receipts = collect_receipts(Path(arguments.results_dir), arguments.receipt_name)
    verification = verify_job_pack_import(
        pack,
        [payload for _, payload in receipts],
        returned_design_fingerprint=arguments.returned_design_fingerprint,
    )
    if arguments.report_json is not None:
        report = Path(arguments.report_json)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(verification.model_dump_json(indent=2) + "\n", encoding="utf-8")
    for line in render_verification_summary(verification, receipt_count=len(receipts)):
        print(line)
    return 1 if verification.status in UNFAVOURABLE_STATUSES else 0


def load_design(design_ref: str) -> VecCampaignDesign:
    """Resolve ``MODULE:ATTRIBUTE`` to an approved design without editing it."""

    module_ref, separator, attribute = design_ref.partition(":")
    if not separator or not module_ref.strip() or not attribute.strip():
        raise JobPackCommandError(
            "design reference must be MODULE:ATTRIBUTE, e.g. "
            "scripts/capacity_pilot_campaign.py:pilot_design"
        )
    module = _import_design_module(module_ref.strip())
    try:
        candidate = getattr(module, attribute.strip())
    except AttributeError as error:
        raise JobPackCommandError(
            f"{module_ref} defines no attribute named {attribute.strip()!r}"
        ) from error
    if callable(candidate):
        try:
            candidate = candidate()
        except ValueError as error:
            raise JobPackCommandError(
                f"{design_ref} did not produce a valid design: {error}"
            ) from error
    if not isinstance(candidate, VecCampaignDesign):
        raise JobPackCommandError(
            f"{design_ref} resolved to {type(candidate).__name__}, not a VecCampaignDesign"
        )
    return candidate


def _import_design_module(module_ref: str) -> ModuleType:
    """Import a dotted module, or a .py file that is not part of a package."""

    if not module_ref.endswith(".py"):
        try:
            return importlib.import_module(module_ref)
        except ImportError as error:
            raise JobPackCommandError(f"could not import module {module_ref}: {error}") from error
    path = Path(module_ref)
    if not path.is_file():
        raise JobPackCommandError(f"design module not found: {path}")
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise JobPackCommandError(f"{path} could not be loaded as a Python module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as error:  # noqa: BLE001 - any import-time failure is the operator's answer
        raise JobPackCommandError(f"{path} raised while being imported: {error}") from error
    return module


def verify_checkout_commit(root: Path, repository: str) -> str:
    """Refuse unless ``root`` is checked out at the audited commit for ``repository``.

    Read-only: ``git rev-parse HEAD`` opens no connection and fetches nothing.
    Re-pinning is an approval decision, so a checkout at any other commit is a
    refusal here rather than a pack that quietly names the wrong sources.
    """

    expected = AUDITED_REPOSITORY_COMMITS[repository]
    if not root.is_dir():
        raise JobPackCommandError(f"{repository} checkout not found: {root}")
    executable = shutil.which("git")
    if executable is None:
        raise JobPackCommandError("git is not on PATH, so no checkout commit can be read")
    try:
        completed = subprocess.run(  # noqa: S603 - fixed read-only argv, never a shell
            [executable, "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise JobPackCommandError(
            f"could not read the {repository} checkout commit: {error}"
        ) from error
    if completed.returncode != 0:
        detail = completed.stderr.strip().replace("\n", " ") or "git rev-parse failed"
        raise JobPackCommandError(
            f"{root} is not a readable git checkout of {repository}: {detail}"
        )
    head = completed.stdout.strip()
    if head != expected:
        raise JobPackCommandError(
            f"{repository} checkout {root} is at {head}, not the audited commit {expected}; "
            "re-pinning is an approval decision, not a pack argument"
        )
    return head


def resolve_manifest(
    design: VecCampaignDesign,
    *,
    roots: dict[str, Path],
    verify_hashes: bool = False,
) -> list[VecJobPackInputRef]:
    """Build the input manifest this design requires from the audited pins.

    Paths and hashes come from the pinned constants and the design's own reviewed
    trace identity; only ``size_bytes`` is measured. The library refuses a
    manifest that names anything else, which is the point: the manifest is not a
    place where a new input can be introduced.
    """

    if design.actor_id not in PINNED_ACTORS:
        raise JobPackCommandError(
            f"design actor {design.actor_id!r} is not a pinned checkpoint; "
            f"known: {', '.join(sorted(PINNED_ACTORS))}"
        )
    actor_path, actor_sha = PINNED_ACTORS[design.actor_id]
    declared: list[tuple[RepositoryName, str, str, VecJobPackInputRole]] = [
        (TRACE_REPOSITORY, design.trace_file, design.trace_sha256, VecJobPackInputRole.TRACE),
        (ACTOR_REPOSITORY, actor_path, actor_sha, VecJobPackInputRole.ACTOR),
    ]
    declared += [
        (EVALUATOR_REPOSITORY, path, sha, VecJobPackInputRole.EVALUATOR_SOURCE)
        for path, sha in sorted(PINNED_EVALUATOR_FILES.items())
    ]

    refs: list[VecJobPackInputRef] = []
    for repository, path, sha256, role in declared:
        root = roots.get(repository)
        if root is None:
            raise JobPackCommandError(f"no checkout root supplied for repository {repository}")
        resolved = root / path
        if not resolved.is_file():
            raise JobPackCommandError(
                f"declared {role.value} input is missing from the {repository} checkout: {resolved}"
            )
        if verify_hashes:
            measured = _sha256_file(resolved)
            if measured != sha256:
                raise JobPackCommandError(
                    f"{resolved} hashes to {measured}, not the audited {sha256}; "
                    "this checkout is not the audited source"
                )
        refs.append(
            VecJobPackInputRef(
                repository=repository,
                audited_commit=AUDITED_REPOSITORY_COMMITS[repository],
                path=path,
                sha256=sha256,
                size_bytes=resolved.stat().st_size,
                role=role,
            )
        )
    return refs


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def load_pack(path: Path) -> VecJobPack:
    """Read one exported pack, refusing anything that is not one."""

    if not path.is_file():
        raise JobPackCommandError(f"pack JSON not found: {path}")
    payload = path.read_bytes()
    if len(payload) > MAX_PACK_BYTES:
        raise JobPackCommandError(f"pack JSON exceeds {MAX_PACK_BYTES} bytes: {path}")
    try:
        return VecJobPack.model_validate_json(payload)
    except ValueError as error:
        raise JobPackCommandError(f"not a valid job pack: {error}") from error


def collect_receipts(results_dir: Path, receipt_name: str) -> list[tuple[Path, dict[str, Any]]]:
    """Collect returned receipts in deterministic path order.

    An unparseable file refuses the whole verification rather than being dropped:
    the library reports a receipt it cannot *model* as a finding, but a file that
    is not even JSON means the transfer itself is suspect, and silently verifying
    the rest of the set would hide that.
    """

    if not results_dir.is_dir():
        raise JobPackCommandError(f"returned-results directory not found: {results_dir}")
    paths = sorted(results_dir.rglob(receipt_name))
    if not paths:
        raise JobPackCommandError(
            f"no {receipt_name} files found under {results_dir}; "
            "pass --receipt-name if the remote site named them differently"
        )
    collected: list[tuple[Path, dict[str, Any]]] = []
    for path in paths:
        if path.stat().st_size > MAX_RECEIPT_BYTES:
            raise JobPackCommandError(f"receipt exceeds {MAX_RECEIPT_BYTES} bytes: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise JobPackCommandError(
                f"returned receipt is not readable JSON: {path}: {error}"
            ) from error
        if not isinstance(payload, dict):
            raise JobPackCommandError(
                f"returned receipt is not a JSON object: {path}: got {type(payload).__name__}"
            )
        collected.append((path, payload))
    return collected


def render_export_summary(pack: VecJobPack, output: Path) -> list[str]:
    """Render what was exported, including what the pack deliberately omits."""

    lines = [
        f"exported: {output}",
        f"  pack id            : {pack.pack_id}",
        f"  experiment         : {pack.design.experiment_id}",
        f"  design fingerprint : {pack.design_fingerprint}",
        f"  pack fingerprint   : {pack.fingerprint()}",
        f"  declared cells     : {len(pack.cells)}",
        f"  declared inputs    : {len(pack.inputs)}",
        f"  required outputs   : {', '.join(pack.required_output_names)}",
        "  audited commits    :",
    ]
    lines += [
        f"    {repository}: {commit}"
        for repository, commit in sorted(pack.audited_commits().items())
    ]
    lines += [
        "  carries no external repository bytes, no executor, and no credentials.",
        "  a person moves this pack; nothing here submits or transfers it.",
    ]
    return lines


def render_verification_summary(
    verification: VecJobPackImportVerification,
    *,
    receipt_count: int,
) -> list[str]:
    """Render the verification outcome, findings first when there are any."""

    lines = [
        f"status: {verification.status.value}",
        f"  pack id          : {verification.pack_id}",
        f"  experiment       : {verification.experiment_id}",
        f"  declared cells   : {verification.declared_cell_count}",
        f"  receipts read    : {receipt_count}",
        f"  fulfilled cells  : {verification.fulfilled_cell_count}",
    ]
    if verification.unfulfilled_run_ids:
        lines.append(f"  unfulfilled      : {', '.join(verification.unfulfilled_run_ids)}")
    if verification.findings:
        lines.append(f"  findings ({len(verification.findings)}):")
        lines += [f"    - {finding}" for finding in verification.findings]
    lines.append("  cells:")
    lines += [f"    {cell.run_id}: {cell.detail}" for cell in verification.cells]
    lines.append(
        "  a verified import is not a scientific admission; admission remains the local "
        "ADR-061 fresh-run path."
    )
    return lines


if __name__ == "__main__":
    sys.exit(main())
