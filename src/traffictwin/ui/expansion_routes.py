"""Expansion V1 additive route registry — Lane 16.

Dependency-gated composition that makes the four promoted lanes inspectable
without duplicating models or patching upstream lane source.

Composition reuses the public contracts from lanes 1-14:
- Manchester Twin (Lane 06 closed-loop journey)
- Manchester Source Operations (Lane 14 typed catalogue)
- Replay Observatory (Lane 12 deterministic engine)
- Research Registry (Lane 09 typed registry)

Navigation is additive via V07AdditivePageSpec, preserving the counted
34-page normative inventory and the existing Platform group.

Resource Strategy Explorer (Compare & test) is deliberately untouched;
navigation overlap is recorded honestly in the closure packet.

No network, no subprocess, no secret handling.
"""

from __future__ import annotations

from pathlib import Path

from traffictwin.ui.navigation_v07 import V07AdditivePageSpec

# Four promoted surfaces — scripts already exist and are read-only here.
MANCHESTER_TWIN_EXPANSION_SPEC = V07AdditivePageSpec(
    title="Manchester Twin",
    group="Source evidence",
    script="app_pages/manchester_twin.py",
    url_path="manchester-twin",
    icon=":material/cycle:",
)

MANCHESTER_SOURCE_OPERATIONS_EXPANSION_SPEC = V07AdditivePageSpec(
    title="Manchester Source Operations",
    group="Source evidence",
    script="app_pages/manchester_source_operations.py",
    url_path="manchester-source-operations",
    icon=":material/database:",
)

REPLAY_OBSERVATORY_EXPANSION_SPEC = V07AdditivePageSpec(
    title="Replay Observatory",
    group="Source evidence",
    script="app_pages/replay_observatory.py",
    url_path="replay-observatory",
    icon=":material/replay:",
)

RESEARCH_REGISTRY_EXPANSION_SPEC = V07AdditivePageSpec(
    title="Research Registry",
    group="Evidence & reports",
    script="app_pages/research_registry.py",
    url_path="research-registry",
    icon=":material/science:",
)

EXPANSION_PAGE_SPECS: tuple[V07AdditivePageSpec, ...] = (
    MANCHESTER_TWIN_EXPANSION_SPEC,
    MANCHESTER_SOURCE_OPERATIONS_EXPANSION_SPEC,
    REPLAY_OBSERVATORY_EXPANSION_SPEC,
    RESEARCH_REGISTRY_EXPANSION_SPEC,
)

# Coherent grouping rationale (kept in code so validator can exercise it):
# - Manchester Twin + Manchester Source Operations + Replay Observatory share
#   "Source evidence" because they are all source/observation-derived realities
#   (twin journey stages, source standing, deterministic replay).
# - Research Registry sits in "Evidence & reports" because it is admitted
#   research evidence, not source telemetry.
EXPANSION_GROUPING: dict[str, tuple[str, ...]] = {
    "Source evidence": (
        "Manchester Twin",
        "Manchester Source Operations",
        "Replay Observatory",
    ),
    "Evidence & reports": ("Research Registry",),
}

# Overlap honesty — must be echoed in closure material.
NAVIGATION_OVERLAP_NOTE = (
    "Resource Strategy Explorer remains normative in Compare & test; "
    "Research Registry is additive in Evidence & reports. "
    "Both concern research but are separate: the Explorer is traffic/VEC "
    "deterministic scheduling (admitted or synthetic study JSON), the Registry "
    "is the typed future-generic E2 study family. Neither duplicates the other. "
    "Manchester Operations (Overview, additive) vs Manchester Source Operations "
    "(Source evidence, expansion) — the former is live Manchester Operations; "
    "the latter is the typed source-operations catalogue (secret-free, offline). "
    "TOS Replay (Source evidence, normative) vs Replay Observatory (Source evidence, "
    "expansion) — the former is generic replay, the latter is the deterministic "
    "Replay Observatory over immutable event streams."
)


def validate_expansion_routes(base: object | None = None) -> None:
    """Lightweight structural validation for expansion specs.

    Checks route uniqueness within expansion and against the file system.
    Delegates full cross-inventory collision checks to navigation_v07.validate.
    """
    seen_paths = set()
    seen_scripts = set()
    for spec in EXPANSION_PAGE_SPECS:
        if spec.url_path in seen_paths:
            raise ValueError(f"duplicate expansion url_path: {spec.url_path}")
        if spec.script in seen_scripts:
            raise ValueError(f"duplicate expansion script: {spec.script}")
        seen_paths.add(spec.url_path)
        seen_scripts.add(spec.script)
        if "/" in spec.url_path or "\\" in spec.url_path or ".." in spec.url_path:
            raise ValueError(f"unsafe url_path: {spec.url_path}")
        if spec.group not in (
            "Source evidence",
            "Evidence & reports",
            "Overview",
            "Platform",
        ):
            raise ValueError(f"expansion group must be a registered navigation group: {spec.group}")

    # File existence check (allow base override for tests)
    root = (
        Path(__file__).parent
        if base is None
        else Path(base)
        if isinstance(base, Path)
        else Path(str(base))
    )  # noqa: SIM108
    missing = [s.script for s in EXPANSION_PAGE_SPECS if not (root / s.script).is_file()]
    if missing:
        raise ValueError(f"expansion page scripts missing: {sorted(missing)}")


def expansion_titles() -> tuple[str, ...]:
    return tuple(s.title for s in EXPANSION_PAGE_SPECS)


def expansion_url_paths() -> tuple[str, ...]:
    return tuple(s.url_path for s in EXPANSION_PAGE_SPECS)


def expansion_scripts() -> tuple[str, ...]:
    return tuple(s.script for s in EXPANSION_PAGE_SPECS)
