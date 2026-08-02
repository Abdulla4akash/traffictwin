#!/usr/bin/env python3
"""Preview, activate and inspect one external aggregate historical store.

The configuration file is private local input and must remain outside the
repository. Every emitted result is a strict path-free model.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from traffictwin.platform.historical_store import (
    AdmissionStatus,
    CatalogueNamespace,
    CatalogueQuery,
    EvidenceRole,
    PayloadClass,
    StoreModel,
)
from traffictwin.platform.historical_store_activation import (
    ActivationConfig,
    ActivationRefusal,
    ActivationRefusalCode,
    activate_store,
    catalogue_report,
    integrity_report,
    load_activation_config,
    preview_activation,
)


def _write_model(value: StoreModel, *, error: bool = False) -> None:
    stream = sys.stderr if error else sys.stdout
    stream.write(value.canonical_json() + "\n")


def _load(path: Path) -> ActivationConfig | None:
    result = load_activation_config(path)
    if isinstance(result, ActivationRefusal):
        _write_model(result, error=True)
        return None
    return result


def _query_refusal() -> ActivationRefusal:
    return ActivationRefusal(
        operation="catalogue",
        code=ActivationRefusalCode.QUERY_INVALID,
        message="catalogue query arguments failed strict validation",
        subject_id="historical-store",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    preview = commands.add_parser("preview", help="validate and dry-run selected imports")
    preview.add_argument("--config", required=True, type=Path)

    activate = commands.add_parser("activate", help="publish one exact confirmed preview")
    activate.add_argument("--config", required=True, type=Path)
    activate.add_argument("--expect-preview-digest", required=True)

    catalogue = commands.add_parser("catalogue", help="run one allowlisted catalogue query")
    catalogue.add_argument("--config", required=True, type=Path)
    catalogue.add_argument("--schema-name", required=True)
    catalogue.add_argument("--minimum-version", required=True, type=int)
    catalogue.add_argument("--maximum-version", required=True, type=int)
    catalogue.add_argument(
        "--namespace",
        required=True,
        choices=[item.value for item in CatalogueNamespace],
    )
    catalogue.add_argument(
        "--payload-class",
        choices=[item.value for item in PayloadClass],
    )
    catalogue.add_argument(
        "--evidence-role",
        choices=[item.value for item in EvidenceRole],
    )
    catalogue.add_argument(
        "--admission-status",
        choices=[item.value for item in AdmissionStatus],
    )

    integrity = commands.add_parser("integrity", help="reconcile marker, catalogue and payloads")
    integrity.add_argument("--config", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = _load(args.config)
    if config is None:
        return 2
    if args.command == "preview":
        preview = preview_activation(config)
        if isinstance(preview, ActivationRefusal):
            _write_model(preview, error=True)
            return 2
        _write_model(preview)
        return 0 if preview.activatable else 2
    if args.command == "activate":
        receipt = activate_store(
            config,
            expected_preview_digest=args.expect_preview_digest,
        )
        if isinstance(receipt, ActivationRefusal):
            _write_model(receipt, error=True)
            return 2
        _write_model(receipt)
        return 0
    if args.command == "integrity":
        report = integrity_report(config)
        _write_model(report)
        return 0 if report.safe_to_use else 2
    try:
        query = CatalogueQuery(
            schema_name=args.schema_name,
            minimum_schema_version=args.minimum_version,
            maximum_schema_version=args.maximum_version,
            namespace=CatalogueNamespace(args.namespace),
            payload_class=(
                None if args.payload_class is None else PayloadClass(args.payload_class)
            ),
            evidence_role=(
                None if args.evidence_role is None else EvidenceRole(args.evidence_role)
            ),
            admission_status=(
                None if args.admission_status is None else AdmissionStatus(args.admission_status)
            ),
        )
    except (ValidationError, ValueError):
        _write_model(_query_refusal(), error=True)
        return 2
    catalogue_output = catalogue_report(config, query)
    if isinstance(catalogue_output, ActivationRefusal):
        _write_model(catalogue_output, error=True)
        return 2
    _write_model(catalogue_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
