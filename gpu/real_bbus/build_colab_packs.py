"""Build two separately bound private B-BUS Colab ZIPs."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gpu.real_bbus.checkpoint_source import write_checkpointed_trainer
from gpu.real_bbus.prepare_source import sha256_file, stage_source
from gpu.real_bbus.run_campaign import verify_pack

METHOD_VERSION = "bbus-private-colab-pack-1.2"
DEFAULT_TRACE_ROOT = "data/bbus-successors-20260728"
DEFAULT_SOURCE_ROOT = "../external/vec_env"
DEFAULT_OUTPUT_ROOT = "data/bbus-colab-packs-checkpointed-20260729"
APPROVAL_PATH = "docs/integration/evidence/bbus_dual_successor_owner_approval_20260728.json"
APPROVAL_SHA256 = "e165619566249c9b7f6cb2a531e486cfda3e61e306ab6b2d6821577432dd3764"

ARM_BINDINGS: dict[str, dict[str, Any]] = {
    "corridor": {
        "experiment_id": "B-BUS-CORRIDOR-DAWN-PEAK-20260728",
        "protocol_path": "docs/evaluation/bbus_corridor_dawn_peak_protocol_20260728.md",
        "protocol_sha256": ("cd2e93f926d19a1c8b55d3962a674353be70b8d4fff0f69d80417e666238cde7"),
        "vec06_compatible": True,
        "coverage_statement": "exact_full_coverage_both_sessions",
        "traces": {
            "dawn": {
                "source": "corridor/dawn-20260728/trace.npz",
                "sha256": "d92cfb0c5144cc646e1ed30bec76484af3b38d1ce9e94e1b714e86d4098af4a4",
                "T": 3422,
                "maxN": 67,
                "vehicle_seconds": 161654,
                "rsu_count": 12,
                "window": "dawn-20260728",
            },
            "peak": {
                "source": "corridor/peak-20260728/trace.npz",
                "sha256": "5ed9b123531f55c70c5209e1799f9c55bbb479ba57045b20ed996b9cbfcf4d02",
                "T": 3384,
                "maxN": 98,
                "vehicle_seconds": 281265,
                "rsu_count": 12,
                "window": "peak-20260728",
            },
        },
    },
    "sparse64": {
        "experiment_id": "B-BUS-SPARSE64-DAWN-PEAK-20260728",
        "protocol_path": "docs/evaluation/bbus_sparse64_dawn_peak_protocol_20260728.md",
        "protocol_sha256": ("f366f3ba886287150eefcf64268e38df4e2a488372ed738dbbc712573c221efa"),
        "vec06_compatible": False,
        "coverage_statement": "dawn_designed_64_sites__incomplete_coverage",
        "traces": {
            "dawn": {
                "source": "sparse64/dawn-20260728/trace.npz",
                "sha256": "c08a69da7b29bee50a3f110c27d1947774c20e491982075bc8e154c84434b15b",
                "T": 3422,
                "maxN": 827,
                "vehicle_seconds": 2174120,
                "rsu_count": 64,
                "window": "dawn-20260728",
                "exact_coverage_share": 0.45014074660092357,
            },
            "peak": {
                "source": "sparse64/peak-20260728/trace.npz",
                "sha256": "9125b32c9b869cb6d09d9c1d595e44558468fcff797a6b5d2e3e3e6ea8dc284f",
                "T": 3384,
                "maxN": 1000,
                "vehicle_seconds": 3170599,
                "rsu_count": 64,
                "window": "peak-20260728",
                "exact_coverage_share": 0.4599600895603638,
            },
        },
    },
}

REQUIREMENTS = """jax[cuda12]==0.7.2
jaxlib==0.7.2
numpy==2.0.2
flax==0.11.2
optax==0.2.8
chex==0.1.92
distrax==0.1.9
gymnax==0.0.9
brax==0.14.2
mujoco==3.10.0
mujoco-mjx==3.10.0
jaxopt==0.8.5
glfw==2.10.2
trimesh==4.12.2
"""

# JaxMARL 0.0.4 declares its historical JAX 0.4 dependency family even though the
# pack runs the separately staged producer source on the frozen JAX 0.7 stack.
# Install only its distribution metadata so pip does not replace the frozen stack.
NO_DEPS_REQUIREMENTS = "jaxmarl==0.0.4\n"


def build_packs(
    *, repo: Path, trace_root: Path, source_root: Path, output_root: Path
) -> dict[str, Any]:
    root = repo.resolve()
    traces = _resolve(root, trace_root)
    source = _resolve(root, source_root)
    output = _new_private_output(root, output_root)
    if sha256_file(root / APPROVAL_PATH) != APPROVAL_SHA256:
        raise ValueError("dual-successor owner approval receipt changed identity")
    harness = root / "gpu/real_bbus/run_campaign.py"
    packs: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="bbus-colab-pack-") as temporary:
        work = Path(temporary)
        for arm, design in ARM_BINDINGS.items():
            pack_name = f"bbus_{arm}_colab"
            pack = work / pack_name
            pack.mkdir()
            stage_source(source, pack / "source")
            checkpoint_execution = write_checkpointed_trainer(
                pack / "source/jaxmarl/scripts/train_mappo_vec.py",
                pack / "source/jaxmarl/scripts/train_mappo_vec_checkpointed.py",
            )
            (pack / "runner").mkdir()
            shutil.copyfile(harness, pack / "runner/run_campaign.py")
            (pack / "inputs").mkdir()
            for role in ("dawn", "peak"):
                expected = design["traces"][role]
                source_trace = traces / expected["source"]
                if sha256_file(source_trace) != expected["sha256"]:
                    raise ValueError(f"{arm} {role} trace changed identity")
                shutil.copyfile(source_trace, pack / f"inputs/{role}_trace.npz")
            (pack / "evidence").mkdir()
            approval_name = Path(APPROVAL_PATH).name
            protocol_name = Path(design["protocol_path"]).name
            shutil.copyfile(root / APPROVAL_PATH, pack / "evidence" / approval_name)
            shutil.copyfile(root / design["protocol_path"], pack / "evidence" / protocol_name)
            (pack / "requirements-colab.txt").write_text(REQUIREMENTS, encoding="utf-8")
            (pack / "requirements-colab-no-deps.txt").write_text(
                NO_DEPS_REQUIREMENTS, encoding="utf-8"
            )
            (pack / "RUN.txt").write_text(
                "1. Use a Colab GPU runtime.\n"
                "2. Install requirements-colab.txt exactly.\n"
                "3. Install requirements-colab-no-deps.txt with --no-deps.\n"
                f"4. python runner/run_campaign.py --pack-root . "
                f"--output-root /content/bbus_{arm}_results --max-workers 5\n"
                "5. Mirror the atomic *.checkpoint.zip files off-runtime while it runs.\n"
                "6. Download the resulting sibling ZIP; do not publish it.\n",
                encoding="utf-8",
            )
            file_inventory = {
                path.relative_to(pack).as_posix(): sha256_file(path)
                for path in sorted(pack.rglob("*"))
                if path.is_file()
            }
            binding = {
                "schema_version": "1.0",
                "method_version": METHOD_VERSION,
                "date": "2026-07-29",
                "arm": arm,
                "experiment_id": design["experiment_id"],
                "protocol_path": f"evidence/{protocol_name}",
                "protocol_sha256": design["protocol_sha256"],
                "approval_path": f"evidence/{approval_name}",
                "approval_sha256": APPROVAL_SHA256,
                "traces": {
                    role: {
                        key: value
                        for key, value in design["traces"][role].items()
                        if key != "source"
                    }
                    for role in ("dawn", "peak")
                },
                "infrastructure": {
                    "vec06_compatible": design["vec06_compatible"],
                    "coverage_statement": design["coverage_statement"],
                },
                "train_role": "dawn",
                "held_out_role": "peak",
                "peak_used_for_training_or_selection": False,
                "raw_bods_material_included": False,
                "raw_identifiers_included": False,
                "session_tokens_included": False,
                "producer_data_included": False,
                "producer_code_permission_basis": (
                    "docs/integration/randy_code_permission_20260728.md"
                ),
                "files": file_inventory,
                "checkpoint_execution": checkpoint_execution,
                "scientific_evidence": False,
                "actor_admission_eligible": False,
            }
            binding_path = pack / "campaign_binding.json"
            binding_path.write_text(
                json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            verify_pack(pack)
            archive = output / f"traffictwin_bbus_{arm}_checkpointed_colab_20260729.zip"
            _deterministic_zip(pack, archive)
            with tempfile.TemporaryDirectory(prefix=f"verify-{arm}-") as verification:
                with zipfile.ZipFile(archive) as zipped:
                    if zipped.testzip() is not None:
                        raise ValueError(f"{arm} pack failed ZIP CRC verification")
                    zipped.extractall(verification)
                verify_pack(Path(verification) / pack_name)
            packs.append(
                {
                    "arm": arm,
                    "experiment_id": design["experiment_id"],
                    "filename": archive.name,
                    "bytes": archive.stat().st_size,
                    "sha256": sha256_file(archive),
                    "binding_sha256": sha256_file(binding_path),
                    "zip_integrity_test_passed": True,
                    "extracted_pack_verification_passed": True,
                }
            )
    manifest = {
        "schema_version": "1.0",
        "method_version": METHOD_VERSION,
        "date": "2026-07-29",
        "packs": packs,
        "separate_campaigns": True,
        "raw_bods_material_included": False,
        "raw_identifiers_included": False,
        "session_tokens_included": False,
        "producer_data_included": False,
        "private_owner_colab_only": True,
        "public_hosting_authorised": False,
        "scientific_evidence": False,
        "actor_admission_eligible": False,
    }
    manifest_path = output / "pack_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "output": str(output),
        "manifest_sha256": sha256_file(manifest_path),
        "pack_count": len(packs),
        "colab_ready": True,
    }


def _resolve(repo: Path, requested: Path) -> Path:
    path = requested.expanduser()
    resolved = (repo / path).resolve() if not path.is_absolute() else path.resolve()
    if not resolved.exists():
        raise ValueError(f"required path does not exist: {requested}")
    return resolved


def _new_private_output(repo: Path, requested: Path) -> Path:
    output = requested.expanduser()
    output = (repo / output).resolve() if not output.is_absolute() else output.resolve()
    data = (repo / "data").resolve()
    if output == data or not output.is_relative_to(data):
        raise ValueError("pack output must be a named child of private data")
    if output.exists():
        raise ValueError("pack output is new-only and never overwritten")
    output.mkdir(parents=True)
    return output


def _deterministic_zip(root: Path, archive: Path) -> None:
    if archive.exists():
        raise ValueError("pack archive already exists and is never overwritten")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative = Path(root.name) / path.relative_to(root)
            info = zipfile.ZipInfo(relative.as_posix(), date_time=(2026, 7, 29, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            out.writestr(info, path.read_bytes())


def _repository_root() -> Path:
    source = Path(__file__).resolve()
    for parent in source.parents:
        if (parent / "AGENTS.md").is_file():
            return parent
    raise ValueError("repository root could not be resolved")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-root", type=Path, default=Path(DEFAULT_TRACE_ROOT))
    parser.add_argument("--source-root", type=Path, default=Path(DEFAULT_SOURCE_ROOT))
    parser.add_argument("--output-root", type=Path, default=Path(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args(argv)
    result = build_packs(
        repo=_repository_root(),
        trace_root=args.trace_root,
        source_root=args.source_root,
        output_root=args.output_root,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
