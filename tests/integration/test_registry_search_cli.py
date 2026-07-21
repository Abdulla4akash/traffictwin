from __future__ import annotations

import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.domain.run import Run
from traffictwin.storage.registry import Registry


def _registry_with_run(path: Path) -> None:
    registry = Registry(path)
    registry.initialize()
    registry.register_bundle_import(
        run=Run(
            run_id="run-cli-search",
            seed_id="seed-cli-search",
            algorithm="round-robin",
            random_seed=19,
        ),
        bundle_id="bundle-cli-search",
        source_reference="/Users/operator/private/bundle",
        fingerprint="c" * 64,
        manifest_json="{}",
        validation_report_json=json.dumps(
            {
                "findings": [
                    {
                        "code": "CLI_QUEUE_WARNING",
                        "message": "Queue evidence requires review.",
                    }
                ]
            }
        ),
    )


def test_registry_search_cli_returns_ranked_json_without_mutation(tmp_path: Path) -> None:
    registry = tmp_path / "registry.sqlite"
    _registry_with_run(registry)
    before = hashlib.sha256(registry.read_bytes()).hexdigest()

    result = CliRunner().invoke(
        app,
        [
            "registry",
            "search",
            "run cli search",
            "--registry",
            str(registry),
            "--category",
            "run",
            "--format",
            "json",
        ],
    )
    after = hashlib.sha256(registry.read_bytes()).hexdigest()

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["capability_id"] == "REP-05"
    assert payload["selected_categories"] == ["run"]
    assert payload["returned_count"] == 1
    assert payload["hits"][0]["reference"] == "run:run-cli-search"
    assert before == after


def test_registry_search_cli_contract_text_and_invalid_query(tmp_path: Path) -> None:
    registry = tmp_path / "registry.sqlite"
    _registry_with_run(registry)

    contract = CliRunner().invoke(app, ["registry", "search-contract"])
    invalid = CliRunner().invoke(
        app,
        ["registry", "search", "--registry", str(registry), "--", "---"],
    )

    assert contract.exit_code == 0, contract.output
    assert "contract_version: registry-search-v1" in contract.output
    assert "maximum_candidate_documents: 20000" in contract.output
    assert invalid.exit_code == 1
    assert "alphanumeric" in invalid.output
