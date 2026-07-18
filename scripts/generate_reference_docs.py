"""Generate documentation-safe reference artifacts from TrafficTwin code."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from traffictwin.canonical.records import (
    IncidentRecord,
    InfrastructureRecord,
    TaskRecord,
    TrafficObservationRecord,
    TripRecord,
    VehicleStateRecord,
)
from traffictwin.config.capabilities import CapabilityManifest
from traffictwin.domain.experiment import Experiment
from traffictwin.domain.run import Run
from traffictwin.domain.scenario import ScenarioSeed, SeedDocument
from traffictwin.evidence.pack import EvidencePack
from traffictwin.ingestion.manifest import BundleManifest, FileDeclaration
from traffictwin.integration.tos.analysis import tos_analysis_catalogue
from traffictwin.integration.tos.analysis_models import (
    TosCampaignComparisonReport,
    TosEvaluationMatrix,
    TosGeneralisationMatrix,
    TosReproducibilityAudit,
    TosRsuRunSummary,
    TosTaskOutcomeSummary,
    TosTraceSummary,
    TosTrainingRun,
)
from traffictwin.integration.tos.contract import TosSourceContract, tos_source_contract
from traffictwin.integration.tos.metrics import tos_metric_catalogue
from traffictwin.integration.tos.models import (
    TosEvaluationRun,
    TosReplayFrame,
    TosTaskSample,
    TosValidationReport,
)
from traffictwin.integration.tos.readiness import TosIntegrationReadinessReport
from traffictwin.integration.tos.supervisor import TosSupervisorPackManifest
from traffictwin.metrics.catalogue import metric_catalogue
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import MetricCollection
from traffictwin.provenance.models import (
    ProvenanceEdge,
    ProvenanceNode,
    ProvenanceTrace,
    SourceRowPreview,
)
from traffictwin.release.deployment import SyntheticStaticSiteManifest
from traffictwin.rules.catalogue import rule_catalogue
from traffictwin.rules.config import RuleSetConfig
from traffictwin.validation.codes import ValidationCode
from traffictwin.validation.report import ValidationReport

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "reference" / "generated"


MODEL_TYPES: dict[str, type[BaseModel]] = {
    "ScenarioSeed": ScenarioSeed,
    "SeedDocument": SeedDocument,
    "Experiment": Experiment,
    "Run": Run,
    "CapabilityManifest": CapabilityManifest,
    "BundleManifest": BundleManifest,
    "FileDeclaration": FileDeclaration,
    "TaskRecord": TaskRecord,
    "InfrastructureRecord": InfrastructureRecord,
    "VehicleStateRecord": VehicleStateRecord,
    "TrafficObservationRecord": TrafficObservationRecord,
    "TripRecord": TripRecord,
    "IncidentRecord": IncidentRecord,
    "ValidationReport": ValidationReport,
    "MetricEngineConfig": MetricEngineConfig,
    "MetricCollection": MetricCollection,
    "EvidencePack": EvidencePack,
    "ProvenanceNode": ProvenanceNode,
    "ProvenanceEdge": ProvenanceEdge,
    "ProvenanceTrace": ProvenanceTrace,
    "SourceRowPreview": SourceRowPreview,
    "TosEvaluationRun": TosEvaluationRun,
    "TosReplayFrame": TosReplayFrame,
    "TosTaskSample": TosTaskSample,
    "TosValidationReport": TosValidationReport,
    "TosSourceContract": TosSourceContract,
    "TosEvaluationMatrix": TosEvaluationMatrix,
    "TosCampaignComparisonReport": TosCampaignComparisonReport,
    "TosGeneralisationMatrix": TosGeneralisationMatrix,
    "TosTrainingRun": TosTrainingRun,
    "TosTraceSummary": TosTraceSummary,
    "TosRsuRunSummary": TosRsuRunSummary,
    "TosTaskOutcomeSummary": TosTaskOutcomeSummary,
    "TosReproducibilityAudit": TosReproducibilityAudit,
    "TosIntegrationReadinessReport": TosIntegrationReadinessReport,
    "TosSupervisorPackManifest": TosSupervisorPackManifest,
    "SyntheticStaticSiteManifest": SyntheticStaticSiteManifest,
    "RuleSetConfig": RuleSetConfig,
}

CLI_COMMANDS = [
    [],
    ["validate-seed"],
    ["normalise-seed"],
    ["capabilities"],
    ["synthetic"],
    ["synthetic", "presets"],
    ["synthetic", "generate-preset"],
    ["synthetic", "experiment-generate-preset"],
    ["synthetic", "verify"],
    ["demo"],
    ["demo", "initialise"],
    ["demo", "reset"],
    ["demo", "status"],
    ["demo", "launch"],
    ["compare"],
    ["registry"],
    ["registry", "init"],
    ["registry", "inspect"],
    ["bundle"],
    ["bundle", "validate"],
    ["bundle", "inspect"],
    ["bundle", "import"],
    ["bundle", "report"],
    ["metrics"],
    ["metrics", "compute"],
    ["metrics", "report"],
    ["evidence"],
    ["evidence", "build"],
    ["report"],
    ["report", "run"],
    ["report", "compare"],
    ["report", "diagnostics"],
    ["report", "full"],
    ["release"],
    ["release", "status"],
    ["release", "stage-demo-site"],
    ["experiment"],
    ["experiment", "summarise"],
    ["diagnose"],
    ["diagnose", "bundle"],
    ["diagnose", "evidence"],
    ["diagnose", "report"],
    ["diagnose", "evaluate"],
    ["provenance"],
    ["provenance", "metric"],
    ["provenance", "rule"],
    ["provenance", "run"],
    ["provenance", "source"],
    ["provenance", "export"],
    ["integration"],
    ["integration", "tos"],
    ["integration", "tos", "inspect"],
    ["integration", "tos", "contract"],
    ["integration", "tos", "validate"],
    ["integration", "tos", "runs"],
    ["integration", "tos", "import"],
    ["integration", "tos", "metrics"],
    ["integration", "tos", "replay"],
    ["integration", "tos", "rsu-series"],
    ["integration", "tos", "task-sample"],
    ["integration", "tos", "diagnose"],
    ["integration", "tos", "provenance"],
    ["integration", "tos", "matrix"],
    ["integration", "tos", "compare-campaigns"],
    ["integration", "tos", "generalisation"],
    ["integration", "tos", "training-runs"],
    ["integration", "tos", "training"],
    ["integration", "tos", "trace-summary"],
    ["integration", "tos", "rsu-summary"],
    ["integration", "tos", "task-summary"],
    ["integration", "tos", "audit"],
    ["integration", "tos", "report"],
    ["integration", "tos", "atlas"],
    ["integration", "tos", "results-pack"],
    ["integration", "tos", "readiness"],
    ["integration", "tos", "supervisor-pack"],
    ["integration", "tos", "stage-public-atlas"],
]


def main() -> None:
    """Write generated reference JSON files."""

    OUTPUT.mkdir(parents=True, exist_ok=True)
    _write_json("pydantic_schemas.json", _schemas())
    _write_json("metric_catalogue.json", _metric_catalogue())
    _write_json("validation_codes.json", _validation_codes())
    _write_json("rule_catalogue.json", _rule_catalogue())
    _write_json("cli_help.json", _cli_help())
    _write_json("tos_source_contract.json", tos_source_contract().model_dump(mode="json"))
    _write_json(
        "tos_analysis_catalogue.json",
        {
            "_meta": _metadata("traffictwin.integration.tos.analysis.tos_analysis_catalogue"),
            "measures": [item.model_dump(mode="json") for item in tos_analysis_catalogue()],
        },
    )


def _metadata(kind: str) -> dict[str, str]:
    return {
        "generated": "true",
        "source": kind,
        "note": "Generated by scripts/generate_reference_docs.py. Do not hand-edit.",
    }


def _schemas() -> dict[str, Any]:
    return {
        "_meta": _metadata("pydantic model_json_schema"),
        "schemas": {name: model.model_json_schema() for name, model in sorted(MODEL_TYPES.items())},
    }


def _metric_catalogue() -> dict[str, Any]:
    catalogue = {**metric_catalogue(), **tos_metric_catalogue()}
    return {
        "_meta": _metadata(
            "traffictwin.metrics.catalogue.metric_catalogue and "
            "traffictwin.integration.tos.metrics.tos_metric_catalogue"
        ),
        "metrics": {
            key: definition.model_dump(mode="json") for key, definition in sorted(catalogue.items())
        },
    }


def _validation_codes() -> dict[str, Any]:
    return {
        "_meta": _metadata("traffictwin.validation.codes.ValidationCode"),
        "codes": [code.value for code in ValidationCode],
    }


def _rule_catalogue() -> dict[str, Any]:
    return {
        "_meta": _metadata("traffictwin.rules.catalogue.rule_catalogue"),
        "rules": {
            key: definition.model_dump(mode="json") for key, definition in rule_catalogue().items()
        },
    }


def _cli_help() -> dict[str, Any]:
    executable = _traffictwin_executable()
    env = {
        **os.environ,
        "COLUMNS": "100",
        "NO_COLOR": "1",
        "TERM": "dumb",
    }
    entries: list[dict[str, Any]] = []
    for command in CLI_COMMANDS:
        args = [executable, *command, "--help"]
        completed = subprocess.run(  # noqa: S603 - fixed local CLI help commands only.
            args,
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        entries.append(
            {
                "command": " ".join(["traffictwin", *command]),
                "args": command,
                "exit_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )
    return {
        "_meta": _metadata("traffictwin Typer --help output"),
        "commands": entries,
    }


def _traffictwin_executable() -> str:
    local_script = Path(sys.executable).parent / "traffictwin"
    if local_script.exists():
        return str(local_script)
    found = shutil.which("traffictwin")
    if found is not None:
        return found
    msg = "traffictwin console script not found; run `python -m pip install -e .` first"
    raise RuntimeError(msg)


def _write_json(name: str, payload: dict[str, Any]) -> None:
    path = OUTPUT / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n")


if __name__ == "__main__":
    main()
