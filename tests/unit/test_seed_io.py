from __future__ import annotations

from pathlib import Path

import pytest

from traffictwin.config.seed_io import SeedIOError, dump_seed, load_seed, load_seed_document


def test_seed_yaml_round_trip() -> None:
    source = Path("examples/seeds/arena_gridlock.yaml")
    seed = load_seed(source)
    dumped = dump_seed(seed)

    assert "schema_version: '1.0'" in dumped or 'schema_version: "1.0"' in dumped
    assert "s1-arena-gridlock-x2" in dumped

    tmp = Path("tests/fixtures/seeds/.round_trip.tmp.yaml")
    try:
        tmp.write_text(dumped, encoding="utf-8")
        reloaded = load_seed(tmp)
    finally:
        if tmp.exists():
            tmp.unlink()

    assert reloaded == seed


def test_load_seed_document_injects_top_level_schema_version() -> None:
    document = load_seed_document("examples/seeds/arena_gridlock.yaml")

    assert document.schema_version == "1.0"
    assert document.seed.schema_version == "1.0"


def test_invalid_schema_version_fixture_rejected() -> None:
    with pytest.raises(SeedIOError, match="invalid seed YAML"):
        load_seed("tests/fixtures/seeds/invalid_schema_version.yaml")


def test_invalid_class_mix_fixture_rejected() -> None:
    with pytest.raises(SeedIOError, match="class_mix shares must sum"):
        load_seed("tests/fixtures/seeds/invalid_class_mix.yaml")
