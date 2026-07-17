"""YAML loading and dumping for versioned scenario seeds."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import ValidationError

from traffictwin.domain.scenario import SUPPORTED_SEED_SCHEMA_VERSION, ScenarioSeed, SeedDocument


class SeedIOError(ValueError):
    """Raised when a seed YAML document cannot be loaded or validated."""


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        msg = f"could not read seed file {path}: {exc}"
        raise SeedIOError(msg) from exc
    except yaml.YAMLError as exc:
        msg = f"could not parse seed YAML {path}: {exc}"
        raise SeedIOError(msg) from exc

    if not isinstance(raw, dict):
        msg = f"seed YAML {path} must contain a mapping at the top level"
        raise SeedIOError(msg)
    return cast(dict[str, Any], raw)


def _normalise_raw_seed_document(raw: dict[str, Any]) -> dict[str, Any]:
    schema_version = raw.get("schema_version")
    seed = raw.get("seed")
    if isinstance(seed, dict) and "schema_version" not in seed:
        raw = dict(raw)
        raw["seed"] = dict(seed)
        raw["seed"]["schema_version"] = schema_version
    return raw


def load_seed_document(path: str | Path) -> SeedDocument:
    """Load and validate a seed YAML document."""

    seed_path = Path(path)
    raw = _normalise_raw_seed_document(_load_yaml_mapping(seed_path))
    try:
        return SeedDocument.model_validate(raw)
    except ValidationError as exc:
        msg = f"invalid seed YAML {seed_path}: {exc}"
        raise SeedIOError(msg) from exc


def load_seed(path: str | Path) -> ScenarioSeed:
    """Load and validate a scenario seed from YAML."""

    return load_seed_document(path).seed


def seed_document_to_dict(document: SeedDocument) -> dict[str, Any]:
    """Convert a seed document to the canonical YAML dictionary."""

    return {
        "schema_version": document.schema_version,
        "seed": document.seed.model_dump(
            mode="json",
            by_alias=True,
            exclude={"schema_version"},
            exclude_none=False,
        ),
    }


def dump_seed_document(document: SeedDocument) -> str:
    """Serialise a seed document to deterministic YAML."""

    return yaml.safe_dump(
        seed_document_to_dict(document),
        sort_keys=False,
        allow_unicode=False,
    )


def dump_seed(seed: ScenarioSeed) -> str:
    """Serialise a scenario seed to deterministic YAML."""

    document = SeedDocument(schema_version=SUPPORTED_SEED_SCHEMA_VERSION, seed=seed)
    return dump_seed_document(document)


def write_seed(seed: ScenarioSeed, path: str | Path) -> None:
    """Write a scenario seed to YAML."""

    Path(path).write_text(dump_seed(seed), encoding="utf-8")


def normalise_seed_file(source: str | Path, destination: str | Path) -> SeedDocument:
    """Load, validate, and write a deterministic YAML representation."""

    document = load_seed_document(source)
    Path(destination).write_text(dump_seed_document(document), encoding="utf-8")
    return document
