"""Render the completed capacity programme's cross-regime dissertation figure.

The input is a committed, hash-bound projection record. The generator performs only the
declared mean-of-paired-differences check and deterministic layout; it never opens a
campaign directory, registry, trace, or external repository.
"""

# ruff: noqa: E501

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "dissertation_appendices" / "figures" / "cross_regime"
SVG_NAME = "capacity_cross_regime_response.svg"
TEX_NAME = "capacity_cross_regime_response.tex"
PROVENANCE_NAME = "provenance.md"


class CrossRegimeFigureError(ValueError):
    """Raised when the projection record is incomplete or internally inconsistent."""


@dataclass(frozen=True, slots=True)
class RegimeRow:
    """One standard-squeeze row ready for deterministic rendering."""

    trace_id: str
    label: str
    max_slots: int
    seed_ids: tuple[int, ...]
    paired_differences_ms: tuple[float, ...]
    mean_difference_ms: float
    response_class: str


@dataclass(frozen=True, slots=True)
class DeepComparison:
    """One event-night deep-squeeze comparison."""

    variation_arm: str
    mean_difference_ms: float


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise CrossRegimeFigureError(f"{field} must be an object")
    return value


def _sequence(value: object, *, field: str) -> list[object]:
    if not isinstance(value, list) or not value:
        raise CrossRegimeFigureError(f"{field} must be a non-empty array")
    return value


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CrossRegimeFigureError(f"{field} must be non-empty text")
    return value


def _number(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CrossRegimeFigureError(f"{field} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise CrossRegimeFigureError(f"{field} must be finite")
    return number


def _validated_mean(differences: tuple[float, ...], recorded: object, *, field: str) -> float:
    mean = math.fsum(differences) / len(differences)
    recorded_mean = _number(recorded, field=field)
    if not math.isclose(mean, recorded_mean, rel_tol=0.0, abs_tol=1e-9):
        raise CrossRegimeFigureError(
            f"{field} does not equal the mean of its paired per-seed differences"
        )
    return recorded_mean


def load_projection(
    path: Path,
) -> tuple[dict[str, object], tuple[RegimeRow, ...], tuple[DeepComparison, ...]]:
    """Load and validate the complete cross-regime projection."""

    if not path.is_file():
        raise FileNotFoundError(f"projection JSON not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CrossRegimeFigureError("projection file is not valid JSON") from exc
    record = _mapping(payload, field="projection")
    if record.get("schema_version") != "1.0":
        raise CrossRegimeFigureError("unsupported projection schema_version")
    if record.get("projection_id") != "vec-cross-regime-capacity-response-20260728":
        raise CrossRegimeFigureError("unexpected projection_id")

    rows: list[RegimeRow] = []
    raw_rows = _sequence(record.get("standard_squeeze_regimes"), field="standard_squeeze_regimes")
    for index, item in enumerate(raw_rows):
        row = _mapping(item, field=f"standard_squeeze_regimes[{index}]")
        differences = tuple(
            _number(value, field=f"standard_squeeze_regimes[{index}].paired_latency_differences_ms")
            for value in _sequence(
                row.get("paired_latency_differences_ms"),
                field=f"standard_squeeze_regimes[{index}].paired_latency_differences_ms",
            )
        )
        seed_ids = tuple(
            int(_number(value, field=f"standard_squeeze_regimes[{index}].seed_ids"))
            for value in _sequence(
                row.get("seed_ids"), field=f"standard_squeeze_regimes[{index}].seed_ids"
            )
        )
        if len(seed_ids) != len(differences):
            raise CrossRegimeFigureError(f"standard_squeeze_regimes[{index}] seed count differs")
        mean = _validated_mean(
            differences,
            row.get("mean_paired_latency_difference_ms"),
            field=f"standard_squeeze_regimes[{index}].mean_paired_latency_difference_ms",
        )
        response_class = _text(
            row.get("response_class"),
            field=f"standard_squeeze_regimes[{index}].response_class",
        )
        exact_zero = all(value == 0.0 for value in differences)
        expected_class = "exactly_inert" if exact_zero else "outcome_sensitive"
        if response_class != expected_class:
            raise CrossRegimeFigureError(
                f"standard_squeeze_regimes[{index}] response_class contradicts its values"
            )
        max_slots = int(
            _number(
                row.get("max_vehicle_slots"),
                field=f"standard_squeeze_regimes[{index}].max_vehicle_slots",
            )
        )
        if max_slots < 1:
            raise CrossRegimeFigureError("max_vehicle_slots must be positive")
        rows.append(
            RegimeRow(
                trace_id=_text(
                    row.get("trace_id"), field=f"standard_squeeze_regimes[{index}].trace_id"
                ),
                label=_text(
                    row.get("display_label"),
                    field=f"standard_squeeze_regimes[{index}].display_label",
                ),
                max_slots=max_slots,
                seed_ids=seed_ids,
                paired_differences_ms=differences,
                mean_difference_ms=mean,
                response_class=response_class,
            )
        )
    rows.sort(key=lambda item: item.max_slots)
    if len(rows) != 5 or len({item.trace_id for item in rows}) != 5:
        raise CrossRegimeFigureError("the projection must contain five distinct regimes")

    deep = _mapping(record.get("event_night_deep_squeeze"), field="event_night_deep_squeeze")
    deep_rows: list[DeepComparison] = []
    for index, item in enumerate(
        _sequence(deep.get("comparisons"), field="event_night_deep_squeeze.comparisons")
    ):
        comparison = _mapping(item, field=f"event_night_deep_squeeze.comparisons[{index}]")
        differences = tuple(
            _number(
                value,
                field=(
                    f"event_night_deep_squeeze.comparisons[{index}].paired_latency_differences_ms"
                ),
            )
            for value in _sequence(
                comparison.get("paired_latency_differences_ms"),
                field=(
                    f"event_night_deep_squeeze.comparisons[{index}].paired_latency_differences_ms"
                ),
            )
        )
        mean = _validated_mean(
            differences,
            comparison.get("mean_paired_latency_difference_ms"),
            field=(
                f"event_night_deep_squeeze.comparisons[{index}].mean_paired_latency_difference_ms"
            ),
        )
        deep_rows.append(
            DeepComparison(
                variation_arm=_text(
                    comparison.get("variation_arm"),
                    field=f"event_night_deep_squeeze.comparisons[{index}].variation_arm",
                ),
                mean_difference_ms=mean,
            )
        )
    if [item.variation_arm for item in deep_rows] != ["cap-0.5", "cap-0.25", "cap-0.1"]:
        raise CrossRegimeFigureError("deep-squeeze comparisons must keep frozen arm order")
    return record, tuple(rows), tuple(deep_rows)


def _density_x(max_slots: int) -> float:
    left, right = 285.0, 585.0
    low, high = math.log10(100.0), math.log10(3000.0)
    return left + (math.log10(max_slots) - low) / (high - low) * (right - left)


def _response_x(value: float) -> float:
    left, right = 735.0, 1130.0
    minimum = -7000.0
    bounded = max(minimum, min(0.0, value))
    return left + (bounded - minimum) / -minimum * (right - left)


def render_svg(rows: tuple[RegimeRow, ...], deep_rows: tuple[DeepComparison, ...]) -> str:
    """Return one deterministic, accessible, print-oriented SVG."""

    palette = {
        "ink": "#17324d",
        "text": "#243444",
        "muted": "#526473",
        "grid": "#d9e2e8",
        "inert": "#0b7285",
        "active": "#c24156",
        "band": "#f1f5f7",
    }
    row_y = [185, 250, 315, 380, 445]
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="680" viewBox="0 0 1200 680" role="img" aria-labelledby="title desc">',
        '  <title id="title">Cross-regime capacity response in the Etihad event district</title>',
        '  <desc id="desc">Five trace regimes ordered by maximum vehicle-slot width. Four normal regimes show exactly zero mean paired latency change under the standard capacity squeeze; only the 2488-slot collapse hour responds. A separate magnifier records the much smaller event-night deep-squeeze onset.</desc>',
        f'  <text x="40" y="42" font-family="Helvetica,Arial,sans-serif" font-size="25" font-weight="700" fill="{palette["ink"]}">Cross-regime capacity response</text>',
        f'  <text x="40" y="70" font-family="Helvetica,Arial,sans-serif" font-size="14" fill="{palette["muted"]}">Etihad/Co-op Live event district · standard squeeze cap-2.5 → cap-0.75 · mean of three paired fleet seeds</text>',
        f'  <text x="285" y="112" font-family="Helvetica,Arial,sans-serif" font-size="15" font-weight="700" fill="{palette["ink"]}">A. Maximum trace width (maxN, log scale)</text>',
        f'  <text x="735" y="112" font-family="Helvetica,Arial,sans-serif" font-size="15" font-weight="700" fill="{palette["ink"]}">B. Mean paired latency change (ms)</text>',
    ]
    for tick in (100, 250, 500, 1000, 2500):
        x = _density_x(tick)
        lines.extend(
            [
                f'  <line x1="{x:.2f}" y1="142" x2="{x:.2f}" y2="470" stroke="{palette["grid"]}" stroke-width="1"/>',
                f'  <text x="{x:.2f}" y="492" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="11" fill="{palette["muted"]}">{tick:,}</text>',
            ]
        )
    for tick in (-7000, -3500, 0):
        x = _response_x(float(tick))
        lines.extend(
            [
                f'  <line x1="{x:.2f}" y1="142" x2="{x:.2f}" y2="470" stroke="{palette["grid"]}" stroke-width="1"/>',
                f'  <text x="{x:.2f}" y="492" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="11" fill="{palette["muted"]}">{tick:,}</text>',
            ]
        )
    for row, y in zip(rows, row_y, strict=True):
        label = html.escape(f"{row.label} ({row.trace_id})")
        density_x = _density_x(row.max_slots)
        response_x = _response_x(row.mean_difference_ms)
        active = row.response_class == "outcome_sensitive"
        marker_fill = palette["active"] if active else "none"
        marker_stroke = palette["active"] if active else palette["inert"]
        lines.extend(
            [
                f'  <line x1="40" y1="{y + 24}" x2="1130" y2="{y + 24}" stroke="{palette["grid"]}" stroke-width="1"/>',
                f'  <text x="40" y="{y + 5}" font-family="Helvetica,Arial,sans-serif" font-size="14" fill="{palette["text"]}">{label}</text>',
                f'  <circle cx="{density_x:.2f}" cy="{y}" r="7" fill="{marker_fill}" stroke="{marker_stroke}" stroke-width="3"/>',
                f'  <text x="{density_x + 13:.2f}" y="{y + 5}" font-family="Helvetica,Arial,sans-serif" font-size="12" fill="{palette["text"]}">{row.max_slots:,}</text>',
            ]
        )
        if active:
            width = 1130.0 - response_x
            lines.extend(
                [
                    f'  <rect x="{response_x:.2f}" y="{y - 10}" width="{width:.2f}" height="20" fill="{palette["active"]}" rx="2"/>',
                    f'  <text x="{response_x + 8:.2f}" y="{y + 5}" font-family="Helvetica,Arial,sans-serif" font-size="12" font-weight="700" fill="#ffffff">−6,715.239</text>',
                ]
            )
        else:
            lines.extend(
                [
                    f'  <circle cx="1130" cy="{y}" r="5" fill="{palette["inert"]}"/>',
                    f'  <text x="1117" y="{y + 5}" text-anchor="end" font-family="Helvetica,Arial,sans-serif" font-size="12" fill="{palette["text"]}">0.000 (exact)</text>',
                ]
            )
    lines.extend(
        [
            f'  <text x="735" y="520" font-family="Helvetica,Arial,sans-serif" font-size="12" fill="{palette["muted"]}">Negative = lower mean task latency under squeeze.</text>',
            f'  <rect x="40" y="545" width="1090" height="92" rx="4" fill="{palette["band"]}"/>',
            f'  <text x="60" y="574" font-family="Helvetica,Arial,sans-serif" font-size="14" font-weight="700" fill="{palette["ink"]}">Event-night deep-squeeze magnifier (175 slots)</text>',
        ]
    )
    deep_text = " · ".join(
        f"{item.variation_arm}: {item.mean_difference_ms:.3f} ms" for item in deep_rows
    )
    lines.extend(
        [
            f'  <text x="60" y="601" font-family="Helvetica,Arial,sans-serif" font-size="13" fill="{palette["text"]}">{html.escape(deep_text)}</text>',
            f'  <text x="60" y="624" font-family="Helvetica,Arial,sans-serif" font-size="12" fill="{palette["muted"]}">First non-zero latency response appears at cap-0.1 (−0.024 ms); offloading decisions remain invariant. This brackets a mechanism, not a universal slot threshold.</text>',
            "</svg>",
        ]
    )
    return "\n".join(lines) + "\n"


def _latex_escape(value: str) -> str:
    return value.replace("_", r"\_").replace("%", r"\%")


def render_tex(rows: tuple[RegimeRow, ...], deep_rows: tuple[DeepComparison, ...]) -> str:
    """Render the exact companion table as a LaTeX fragment."""

    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Exploratory, owner\_approved\_candidate, descriptive non-causal cross-regime capacity response in the Etihad/Co-op Live event district. Negative differences mean lower latency under squeeze.}",
        r"\label{tab:capacity-cross-regime-response}",
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Regime & maxN & Seeds & Contrast & Mean paired $\Delta$ latency (ms) \\",
        r"\midrule",
    ]
    for row in rows:
        seeds = ",".join(str(seed) for seed in row.seed_ids)
        lines.append(
            f"{_latex_escape(row.label)} ({_latex_escape(row.trace_id)}) & "
            f"{row.max_slots} & {_latex_escape(seeds)} & 0.75--2.5 & "
            f"{row.mean_difference_ms:.9f} \\\\"
        )
    lines.extend([r"\midrule", r"Event-night deep squeeze & 175 & 50,51,52 & --- & --- \\"])
    for item in deep_rows:
        arm = _latex_escape(item.variation_arm.removeprefix("cap-"))
        lines.append(
            rf"\quad variation cap-{arm} & & & {arm}--2.5 & "
            rf"{item.mean_difference_ms:.9f} \\"
        )
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
            "",
        ]
    )
    return "\n".join(lines)


def render_provenance(
    projection_path: Path,
    payload: dict[str, object],
    svg_path: Path,
    tex_path: Path,
) -> str:
    """Bind the published files to the projection and upstream analysis identities."""

    lines = [
        "# Cross-regime capacity-response figure provenance",
        "",
        "Status: **exploratory, owner_approved_candidate, descriptive non-causal**. This is",
        "not supervisor approval, external validation, a causal claim, or a universal",
        "capacity threshold.",
        "",
        "## Projection source",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Projection record | `{projection_path.name}` |",
        f"| Projection SHA-256 | `{_sha256(projection_path)}` |",
        f"| Projection ID | `{payload['projection_id']}` |",
        f"| Trace-audit SHA-256 | `{payload['trace_audit_source']['sha256']}` |",
        "| Metric | `task.latency.mean_ms` |",
        "| Standard contrast | `cap-0.75` minus `cap-2.5` |",
        "| Pairing unit | fleet seed within campaign |",
        "",
        "## Campaign-analysis bindings",
        "",
        "| Experiment | Analysis SHA-256 | Design fingerprint |",
        "|---|---|---|",
    ]
    for row in payload["standard_squeeze_regimes"]:
        lines.append(
            f"| `{row['experiment_id']}` | `{row['campaign_analysis_sha256']}` | "
            f"`{row['design_fingerprint']}` |"
        )
    deep = payload["event_night_deep_squeeze"]
    lines.append(
        f"| `{deep['experiment_id']}` | `{deep['campaign_analysis_sha256']}` | "
        f"`{deep['design_fingerprint']}` |"
    )
    lines.extend(
        [
            "",
            "The campaign-analysis paths are private, gitignored workspace paths. Their exact",
            "hashes and the complete numeric projection are preserved in the committed JSON;",
            "the generator never opens those paths.",
            "",
            "## Published files",
            "",
            "| File | SHA-256 | Bytes |",
            "|---|---|---|",
            f"| `{svg_path.name}` | `{_sha256(svg_path)}` | {svg_path.stat().st_size} |",
            f"| `{tex_path.name}` | `{_sha256(tex_path)}` | {tex_path.stat().st_size} |",
            "",
            "## Derivation and reading boundary",
            "",
            "- Each plotted response is the arithmetic mean of the three recorded paired",
            "  per-seed differences, variation minus baseline. No cross-regime pooling or",
            "  inferential test is performed.",
            "- `maxN` is the audited trace-array width, not the number of vehicles active at",
            "  every second. The aligned panels show an association with saturation; they do",
            "  not identify a universal threshold.",
            "- The four normal regimes are exactly invariant under the standard squeeze in",
            "  every recorded metric. The 2,488-slot collapse hour has a −6,715.239 ms mean",
            "  paired latency response. The separately magnified event-night response first",
            "  becomes non-zero at cap-0.1 (−0.024 ms).",
            "- All traces cover the Etihad/Co-op Live event district, not Manchester city-wide.",
            "- The policy's offloading decisions remain invariant; decision invariance and",
            "  outcome sensitivity are separate observations.",
            "",
            "## Regenerating",
            "",
            "```bash",
            "uv run python scripts/generate_cross_regime_capacity_figure.py \\",
            "  docs/integration/evidence/vec_cross_regime_capacity_projection_20260728.json \\",
            "  --overwrite",
            "```",
            "",
            "Unchanged input rewrites byte-identical SVG, TeX, and provenance files.",
            "",
        ]
    )
    return "\n".join(lines)


def generate_cross_regime_figure(
    projection_path: Path,
    output_dir: Path,
    *,
    overwrite: bool = False,
) -> tuple[Path, Path, Path]:
    """Validate the projection and publish deterministic SVG, TeX, and provenance."""

    payload, rows, deep_rows = load_projection(projection_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    svg_path = output_dir / SVG_NAME
    tex_path = output_dir / TEX_NAME
    provenance_path = output_dir / PROVENANCE_NAME
    targets = (svg_path, tex_path, provenance_path)
    existing = [path for path in targets if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(f"output exists: {existing[0]}")
    svg_path.write_text(render_svg(rows, deep_rows), encoding="utf-8")
    tex_path.write_text(render_tex(rows, deep_rows), encoding="utf-8")
    provenance_path.write_text(
        render_provenance(projection_path, payload, svg_path, tex_path),
        encoding="utf-8",
    )
    return targets


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("projection", type=Path, help="Committed cross-regime projection JSON")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        outputs = generate_cross_regime_figure(
            args.projection,
            args.output_dir,
            overwrite=args.overwrite,
        )
    except (CrossRegimeFigureError, FileExistsError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
