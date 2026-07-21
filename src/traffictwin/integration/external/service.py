"""Discovery, selection, and inspection services for external-source adapters."""

from __future__ import annotations

from pathlib import Path

from traffictwin.integration.external.adapters import (
    SumoExternalSourceAdapter,
    TosExternalSourceAdapter,
)
from traffictwin.integration.external.models import (
    ConversionLevel,
    DiscoveryReportStatus,
    DiscoveryStatus,
    ExternalDiscoveryReport,
    ExternalSourceCatalogue,
    ExternalSourceInspection,
)
from traffictwin.integration.external.protocol import ExternalSourceAdapter


class ExternalSourceError(ValueError):
    """Raised when discovery cannot safely and unambiguously select an adapter."""


def external_source_adapters() -> tuple[ExternalSourceAdapter, ...]:
    """Return the closed, deterministic v1 reference-adapter registry."""

    adapters: tuple[ExternalSourceAdapter, ...] = (
        SumoExternalSourceAdapter(),
        TosExternalSourceAdapter(),
    )
    return tuple(sorted(adapters, key=lambda item: item.adapter_id))


def external_source_catalogue() -> ExternalSourceCatalogue:
    """Return the shared interface policy plus both reference contracts."""

    return ExternalSourceCatalogue(
        protocol_methods=["discover", "contract", "validate", "inspect"],
        selection_policy=[
            "Discovery uses exact safe relative markers and performs no deep parsing.",
            "Zero matches remain unknown; TrafficTwin does not guess from extensions or names.",
            "Multiple matches are ambiguous until the caller explicitly selects an adapter.",
            "A symlinked source root or marker blocks selection before source validation.",
            "The v1 registry is closed to the two evidenced reference adapters.",
        ],
        validation_policy=[
            "The selected adapter calls its existing source-specific read-only validator.",
            "The portable summary retains the source report type, validator version, findings, "
            "fingerprint, import decision, and exact produced-record counts.",
            "A portable accepted state applies only to the adapter's declared import boundary.",
            "Validation never launches a simulator, repairs a source, or mutates a registry.",
        ],
        semantics_policy=[
            "Every field meaning carries confirmed, inferred, unknown, or unsupported status.",
            "Units, identity scope, joins, coverage, and canonical targets are never inferred.",
            "Unknown and unsupported evidence remains visible instead of becoming zero.",
            "Implementing this protocol does not make different source families equivalent.",
        ],
        conversion_level_semantics={
            ConversionLevel.NONE.value: "No typed TrafficTwin output is produced.",
            ConversionLevel.SOURCE_SPECIFIC.value: (
                "Typed inspection output is retained only in source-native semantics."
            ),
            ConversionLevel.AGGREGATE_SUMMARY.value: (
                "Producer aggregate summaries may enter source-labelled artifacts; no canonical "
                "row conversion is implied."
            ),
            ConversionLevel.PARTIAL_CANONICAL.value: (
                "Only explicitly listed compatible fields enter listed canonical records; all "
                "other evidence stays source-specific or unavailable."
            ),
            ConversionLevel.CANONICAL_BUNDLE.value: (
                "An adapter satisfies a complete declared canonical-bundle contract; this level "
                "is not claimed by either v1 external reference adapter."
            ),
        },
        adapters=[adapter.contract() for adapter in external_source_adapters()],
        exclusions=[
            "dynamic plugin discovery or uploaded adapter code",
            "automatic source conversion or manifest inference",
            "direct or asynchronous simulator launch",
            "registry mutation, package repair, or source rewriting",
            "cross-source metric compatibility or scientific equivalence",
            "licence, permission, unit, identity, join, or producer-version inference",
        ],
        limitations=[
            "v1 contains only the evidenced public SUMO and private TOS reference adapters.",
            "Generic TrafficTwin run bundles retain their existing first-party validation path.",
            "A new source requires a reviewed adapter, contract, fixtures, and acceptance "
            "evidence.",
        ],
    )


def discover_external_sources(
    source: str | Path,
    *,
    adapters: tuple[ExternalSourceAdapter, ...] | None = None,
) -> ExternalDiscoveryReport:
    """Apply every registered adapter's shallow, non-mutating discovery rules."""

    path = Path(source)
    selected = adapters or external_source_adapters()
    results = sorted(
        (adapter.discover(path) for adapter in selected),
        key=lambda item: item.adapter_id,
    )
    candidates = sorted(
        result.adapter_id for result in results if result.status is DiscoveryStatus.MATCHED
    )
    if any(result.status is DiscoveryStatus.BLOCKED for result in results):
        status = DiscoveryReportStatus.BLOCKED
    elif len(candidates) == 1:
        status = DiscoveryReportStatus.ONE_MATCH
    elif len(candidates) > 1:
        status = DiscoveryReportStatus.AMBIGUOUS
    else:
        status = DiscoveryReportStatus.NO_MATCH
    return ExternalDiscoveryReport(
        source_label=_source_label(path),
        status=status,
        results=results,
        candidate_adapter_ids=candidates,
    )


def inspect_external_source(
    source: str | Path,
    *,
    adapter_id: str | None = None,
    deep: bool = False,
) -> ExternalSourceInspection:
    """Select one evidenced adapter and return a portable read-only inspection."""

    path = Path(source)
    adapters = external_source_adapters()
    by_id = {adapter.adapter_id: adapter for adapter in adapters}
    discovery = discover_external_sources(path, adapters=adapters)
    if discovery.status is DiscoveryReportStatus.BLOCKED:
        raise ExternalSourceError("external-source discovery was blocked by an unsafe source")
    if adapter_id is None:
        if discovery.status is DiscoveryReportStatus.NO_MATCH:
            raise ExternalSourceError(
                "no registered external-source adapter matched the required markers"
            )
        if discovery.status is DiscoveryReportStatus.AMBIGUOUS:
            raise ExternalSourceError(
                "multiple external-source adapters matched; select one explicitly"
            )
        selected_id = discovery.candidate_adapter_ids[0]
    else:
        selected_id = adapter_id
        if selected_id not in by_id:
            supported = ", ".join(sorted(by_id))
            raise ExternalSourceError(
                f"unknown external-source adapter {selected_id!r}; supported: {supported}"
            )
    selected = by_id[selected_id]
    selected_discovery = next(
        result for result in discovery.results if result.adapter_id == selected_id
    )
    if selected_discovery.status is not DiscoveryStatus.MATCHED:
        raise ExternalSourceError(
            f"adapter {selected_id!r} did not safely match its required source markers"
        )
    contract = selected.contract()
    validation, provenance = selected.inspect(path, deep=deep)
    return ExternalSourceInspection(
        source_label=_source_label(path),
        adapter_id=selected.adapter_id,
        adapter_version=selected.adapter_version,
        contract_fingerprint=contract.fingerprint(),
        discovery=selected_discovery,
        validation=validation,
        observed_provenance=provenance,
        conversion=contract.conversion,
        blockers=contract.blockers,
        interpretation_limits=contract.interpretation_limits,
    )


def _source_label(path: Path) -> str:
    label = path.name.strip()
    return label if label and label not in {".", ".."} else "<source>"
