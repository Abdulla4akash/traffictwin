from __future__ import annotations

from pathlib import Path

import pytest
from tests.format_helpers import write_equivalent_bundle
from tests.helpers import FIXTURES
from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.ingestion.bundle import import_bundle
from traffictwin.storage.registry import RegistryConflictError


@pytest.mark.parametrize("representation", ["gzip", "parquet"])
def test_bundle_validate_cli_accepts_declared_tabular_format(
    tmp_path: Path,
    representation: str,
) -> None:
    bundle = write_equivalent_bundle(
        FIXTURES / "baseline_valid",
        tmp_path / representation,
        representation,
    )

    result = CliRunner().invoke(app, ["bundle", "validate", str(bundle)])

    assert result.exit_code == 0
    assert "status: accepted" in result.stdout
    assert "may_import: True" in result.stdout


def test_raw_format_identity_is_idempotent_only_for_exact_same_bundle(tmp_path: Path) -> None:
    gzip_bundle = write_equivalent_bundle(
        FIXTURES / "baseline_valid",
        tmp_path / "gzip",
        "gzip",
    )
    parquet_bundle = write_equivalent_bundle(
        FIXTURES / "baseline_valid",
        tmp_path / "parquet",
        "parquet",
    )
    registry = tmp_path / "registry.sqlite"

    first = import_bundle(gzip_bundle, registry)
    repeated = import_bundle(gzip_bundle, registry)

    assert first.created
    assert repeated.idempotent
    with pytest.raises(RegistryConflictError):
        import_bundle(parquet_bundle, registry)
