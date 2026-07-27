"""Route-pool diagnosis measurements for the predeclared demand rebuild (§2).

`docs/evaluation/demand_rebuild_predeclaration.md` §2 requires that, before any
variant runs, the alpha.7 pool is reproduced and *measured*: route-length and
edge-count distributions, expected free-flow residence time, counted-edge
multiplicity, and the fringe share. Those measurements are the hypothesis test,
and the predeclaration commits to publishing them regardless of what they show.

This module is that measurement layer, built ahead of signing so the diagnosis
step is execution-ready. **It runs on no real data.** Nothing here generates a
pool, samples demand, or launches a simulation, and it deliberately stops short
of any judgement:

* ``purpose`` is the literal ``measurements_only``;
* ``viability_verdict_included``, ``threshold_applied``, and ``variant_selected``
  are type-level ``False``.

The §4 viability thresholds are owner decision E3. They are not encoded here,
not defaulted here, and not compared against here — the library reports the
distributions and a person reads them against the contract they signed.

**Memory.** :func:`iter_route_pool` streams: it clears each route element and
the document root as it goes, so peak memory is bounded by a single route no
matter how large the file is. The summarisers hold one float per route per
measure (tens of thousands of floats for the recorded 43,200-route envelope),
which is the only quantity that grows with pool size.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from xml.etree.ElementTree import ParseError

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import iterparse
from pydantic import Field

from traffictwin.integration.manchester.models import ManchesterSnapshotModel
from traffictwin.metrics.statistics import percentile_linear

DEMAND_DIAGNOSIS_SCHEMA_VERSION: Literal["1.0"] = "1.0"
DEMAND_DIAGNOSIS_METHOD_VERSION: Literal["manchester-demand-diagnosis-1.0"] = (
    "manchester-demand-diagnosis-1.0"
)
#: This library measures. It does not decide, and the type says so.
DIAGNOSIS_PURPOSE: Literal["measurements_only"] = "measurements_only"

_METRES_PER_KM = 1000.0
#: Container elements that may carry the identity of an embedded route.
_ROUTE_CONTAINERS = frozenset({"vehicle", "trip", "flow", "person", "container"})


class DemandDiagnosisError(ValueError):
    """Raised when a route pool or edge mapping cannot be measured as given."""


@dataclass(frozen=True)
class EdgeAttributes:
    """Length, free-flow speed, and boundary membership for one network edge.

    ``free_flow_speed_mps`` must be positive: a zero or negative speed makes
    residence time undefined, and inventing a floor for it would fabricate the
    measurement this module exists to report.
    """

    length_m: float
    free_flow_speed_mps: float
    is_boundary: bool = False

    def __post_init__(self) -> None:
        if not self.length_m > 0:
            raise DemandDiagnosisError("edge length must be positive")
        if not self.free_flow_speed_mps > 0:
            raise DemandDiagnosisError("edge free-flow speed must be positive")

    @property
    def free_flow_traversal_s(self) -> float:
        """Return the seconds this edge takes to traverse at free flow."""

        return self.length_m / self.free_flow_speed_mps


@dataclass(frozen=True)
class PoolRoute:
    """One route in the pool: an identity and its ordered edge sequence."""

    route_id: str
    edge_ids: tuple[str, ...]


class DistributionSummary(ManchesterSnapshotModel):
    """A deterministic percentile summary of one measured quantity."""

    schema_version: Literal["1.0"] = "1.0"
    n: int = Field(ge=0)
    mean: float | None = None
    minimum: float | None = None
    p05: float | None = None
    p25: float | None = None
    p50: float | None = None
    p75: float | None = None
    p95: float | None = None
    maximum: float | None = None


class RoutePoolDiagnosis(ManchesterSnapshotModel):
    """The complete §2 measurement set for one route pool.

    Carries no verdict. Every field is an observation about the pool as
    supplied; the selection rule and the viability thresholds live in the
    signed predeclaration and are applied by a person, not by this artifact.
    """

    schema_version: Literal["1.0"] = DEMAND_DIAGNOSIS_SCHEMA_VERSION
    method_version: Literal["manchester-demand-diagnosis-1.0"] = DEMAND_DIAGNOSIS_METHOD_VERSION
    purpose: Literal["measurements_only"] = DIAGNOSIS_PURPOSE
    pool_label: str

    route_count: int = Field(ge=0)
    measured_route_count: int = Field(ge=0)
    routes_with_unknown_edges: int = Field(ge=0)
    unknown_edge_reference_count: int = Field(ge=0)

    route_length_km: DistributionSummary
    route_edge_count: DistributionSummary
    free_flow_residence_time_s: DistributionSummary

    counted_edge_count: int = Field(ge=0)
    counted_edge_multiplicity: DistributionSummary
    counted_edges_with_zero_coverage: int = Field(ge=0)

    fringe_denominator: int = Field(ge=0)
    fringe_entry_route_count: int = Field(ge=0)
    fringe_share: float | None = Field(default=None, ge=0, le=1)

    # Type-level refusals: this artifact cannot carry a decision.
    viability_verdict_included: Literal[False] = False
    threshold_applied: Literal[False] = False
    variant_selected: Literal[False] = False
    research_status: Literal["owner_approved_candidate"] = "owner_approved_candidate"


def iter_route_pool(path: str | Path) -> Iterator[PoolRoute]:
    """Stream every route in a SUMO route file without loading it.

    Both standalone ``<route id=... edges=.../>`` elements and routes embedded
    in a ``<vehicle>``/``<trip>``/``<flow>`` container are yielded. Each element
    and the document root are cleared as parsing advances, so a 1.28 GB pool
    costs the same peak memory as a one-route file.

    Parsing goes through ``defusedxml``'s hardened ``iterparse``, which rejects
    entity and external-reference attacks while staying streaming — the whole
    file is never held.
    """

    source = Path(path)
    if not source.is_file():
        raise DemandDiagnosisError(f"no route file exists at {source}")
    ordinal = 0
    container_id: str | None = None
    try:
        context = iterparse(source, events=("start", "end"))
        _, root = next(context)
        for event, element in context:
            tag = _local_name(element.tag)
            if event == "start":
                if tag in _ROUTE_CONTAINERS:
                    container_id = element.get("id")
                continue
            if tag in _ROUTE_CONTAINERS:
                container_id = None
                continue
            if tag != "route":
                continue
            edges = tuple((element.get("edges") or "").split())
            if not edges:
                raise DemandDiagnosisError(
                    f"route {element.get('id') or container_id or ordinal} declares no edges"
                )
            identity = element.get("id") or container_id or f"route-{ordinal}"
            ordinal += 1
            yield PoolRoute(route_id=identity, edge_ids=edges)
            element.clear()
            root.clear()
    except DefusedXmlException as exc:
        raise DemandDiagnosisError(f"route file uses a refused XML feature: {exc}") from exc
    except ParseError as exc:
        raise DemandDiagnosisError(f"route file is not parseable XML: {exc}") from exc
    except StopIteration as exc:  # pragma: no cover - empty file has no root event
        raise DemandDiagnosisError("route file contains no XML document") from exc


def diagnose_route_pool(
    routes: Iterable[PoolRoute],
    edges: Mapping[str, EdgeAttributes],
    counted_edge_ids: Iterable[str],
    *,
    pool_label: str,
) -> RoutePoolDiagnosis:
    """Measure one route pool against an edge mapping and the counted edges.

    A route referencing an edge the mapping does not carry cannot have a length
    or a residence time, so it is counted in ``routes_with_unknown_edges`` and
    left out of those two distributions rather than silently assigned a value.
    Its edge count still contributes, because that measurement needs no mapping.
    """

    counted = frozenset(counted_edge_ids)
    lengths_km: list[float] = []
    edge_counts: list[float] = []
    residence_s: list[float] = []
    multiplicity = dict.fromkeys(counted, 0)
    route_count = 0
    unmeasurable = 0
    unknown_references = 0
    fringe_denominator = 0
    fringe_entries = 0

    for route in routes:
        if not route.edge_ids:
            raise DemandDiagnosisError(f"route {route.route_id} declares no edges")
        route_count += 1
        edge_counts.append(float(len(route.edge_ids)))
        # Multiplicity counts each counted edge once per route that touches it,
        # so a route doubling back cannot inflate coverage.
        for edge_id in set(route.edge_ids) & counted:
            multiplicity[edge_id] += 1
        missing = [edge_id for edge_id in route.edge_ids if edge_id not in edges]
        if missing:
            unmeasurable += 1
            unknown_references += len(missing)
        else:
            attributes = [edges[edge_id] for edge_id in route.edge_ids]
            lengths_km.append(sum(item.length_m for item in attributes) / _METRES_PER_KM)
            residence_s.append(sum(item.free_flow_traversal_s for item in attributes))
        entry = edges.get(route.edge_ids[0])
        if entry is not None:
            fringe_denominator += 1
            if entry.is_boundary:
                fringe_entries += 1

    return RoutePoolDiagnosis(
        pool_label=pool_label,
        route_count=route_count,
        measured_route_count=len(lengths_km),
        routes_with_unknown_edges=unmeasurable,
        unknown_edge_reference_count=unknown_references,
        route_length_km=summarise(lengths_km),
        route_edge_count=summarise(edge_counts),
        free_flow_residence_time_s=summarise(residence_s),
        counted_edge_count=len(counted),
        counted_edge_multiplicity=summarise([float(value) for value in multiplicity.values()]),
        counted_edges_with_zero_coverage=sum(1 for value in multiplicity.values() if value == 0),
        fringe_denominator=fringe_denominator,
        fringe_entry_route_count=fringe_entries,
        fringe_share=(fringe_entries / fringe_denominator if fringe_denominator else None),
    )


def summarise(values: list[float]) -> DistributionSummary:
    """Return the deterministic percentile summary of one measured quantity."""

    if not values:
        return DistributionSummary(n=0)
    return DistributionSummary(
        n=len(values),
        mean=sum(values) / len(values),
        minimum=min(values),
        p05=percentile_linear(values, 0.05),
        p25=percentile_linear(values, 0.25),
        p50=percentile_linear(values, 0.50),
        p75=percentile_linear(values, 0.75),
        p95=percentile_linear(values, 0.95),
        maximum=max(values),
    )


def render_diagnosis_markdown(diagnosis: RoutePoolDiagnosis) -> str:
    """Render the §2 measurements as the publishable markdown record."""

    lines = [
        f"# Route-pool diagnosis — {diagnosis.pool_label}",
        "",
        f"**Purpose: `{diagnosis.purpose}`.** These are the predeclared §2 measurements of "
        "`docs/evaluation/demand_rebuild_predeclaration.md`, published regardless of what "
        "they show. This record carries no viability verdict, applies no threshold, and "
        "selects no variant — those are owner decisions against the signed contract.",
        "",
        f"- Method: `{diagnosis.method_version}` (schema {diagnosis.schema_version})",
        f"- Routes in pool: {diagnosis.route_count}",
        f"- Routes fully measurable against the edge mapping: {diagnosis.measured_route_count}",
        f"- Routes referencing unknown edges: {diagnosis.routes_with_unknown_edges} "
        f"({diagnosis.unknown_edge_reference_count} unknown edge references)",
        f"- Research status: `{diagnosis.research_status}`",
        "",
        "## Distributions",
        "",
        "| Measurement | n | mean | min | p05 | p25 | p50 | p75 | p95 | max |",
        "|---|---|---|---|---|---|---|---|---|---|",
        _distribution_row("Route length (km)", diagnosis.route_length_km),
        _distribution_row("Route edge count", diagnosis.route_edge_count),
        _distribution_row("Free-flow residence time (s)", diagnosis.free_flow_residence_time_s),
        _distribution_row("Counted-edge multiplicity", diagnosis.counted_edge_multiplicity),
        "",
        "## Counted-edge coverage",
        "",
        f"- Counted edges: {diagnosis.counted_edge_count}",
        f"- Counted edges no pool route traverses: {diagnosis.counted_edges_with_zero_coverage}",
        "",
        "## Fringe share",
        "",
        f"- Routes whose first edge is known: {diagnosis.fringe_denominator}",
        f"- Of those, entering from a subnetwork-boundary edge: "
        f"{diagnosis.fringe_entry_route_count}",
        f"- Fringe share: {_format(diagnosis.fringe_share)}",
        "",
        "## What this record does not do",
        "",
        "- It states no viability verdict and compares nothing against the §4 thresholds "
        "(owner decision E3).",
        "- It selects no variant; the §3 order and the first-viable rule stay with the "
        "signed predeclaration.",
        "- Reconstructed routes are never observed journeys.",
        "",
    ]
    return "\n".join(lines)


def _distribution_row(label: str, summary: DistributionSummary) -> str:
    cells = [
        _format(summary.mean),
        _format(summary.minimum),
        _format(summary.p05),
        _format(summary.p25),
        _format(summary.p50),
        _format(summary.p75),
        _format(summary.p95),
        _format(summary.maximum),
    ]
    return f"| {label} | {summary.n} | " + " | ".join(cells) + " |"


def _format(value: float | None) -> str:
    if value is None:
        return "unavailable"
    return f"{value:.4f}"


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
