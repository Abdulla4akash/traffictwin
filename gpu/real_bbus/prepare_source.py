"""Stage the exact permitted producer code for a private B-BUS Colab pack.

The external producer clone is read-only. Only a new disposable copy is made,
and the sole source change restores the JAX tree-map alias removed after the
producer code was written. The operation and model are otherwise unchanged.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

METHOD_VERSION = "bbus-producer-source-stage-1.0"

BASE_SOURCE_SHA256 = {
    "jaxmarl/env/__init__.py": "1ade2d2774b1249d182484cc95195a8c08bf1528de132c13adc1dc09ba198bea",
    "jaxmarl/env/vec_jax.py": "4eed6b61f157b9a1ba203d0095acdecb0741f2da8d7fc4f411b6ee16a0bdd4f9",
    "jaxmarl/env/vec_jaxmarl.py": (
        "aa7a0d8f373605b2d3f3c700760c7e2c578ffebab4eea0530e9f42de95dd0734"
    ),
    "jaxmarl/scripts/train_mappo_vec.py": (
        "b36079f495e663353398453357b2c42c54431769dcb6d208b259a592df53de12"
    ),
    "eval/eval_sumo_stage1_mc.py": (
        "f6515f6c88522c3df2109f2671220ef8da43f43bf981799464be9c3b65ddc639"
    ),
}
PATCHED_TRAIN_SHA256 = "d19453529babb1c1691fdc9da5188aa0e3e233e3dcf6a65ac84ada2ef25355e1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _patch_train_text(source: str) -> str:
    old = "    import jax\n    import jax.numpy as jnp\n"
    new = (
        "    import jax\n"
        "    # Compatibility only: JaxMARL 0.0.4 calls the alias removed in JAX 0.6.\n"
        '    if not hasattr(jax, "tree_map"):\n'
        "        jax.tree_map = jax.tree_util.tree_map\n"
        "    import jax.numpy as jnp\n"
    )
    if source.count(old) != 1:
        raise ValueError("producer trainer layout changed before the compatibility patch")
    patched = source.replace(old, new, 1)
    compile(patched, "train_mappo_vec.py", "exec")
    return patched


def stage_source(source_root: Path, destination: Path) -> dict[str, object]:
    """Copy the allowlisted producer files and apply the one compatibility patch."""

    source = source_root.resolve()
    target = destination.resolve()
    if target.exists():
        raise ValueError("the disposable producer-code destination must be new")
    actual = {relative: sha256_file(source / relative) for relative in BASE_SOURCE_SHA256}
    if actual != BASE_SOURCE_SHA256:
        raise ValueError(f"producer source bytes differ from the permitted inputs: {actual}")
    for relative in BASE_SOURCE_SHA256:
        output = target / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, output)
    trainer = target / "jaxmarl/scripts/train_mappo_vec.py"
    trainer.write_text(_patch_train_text(trainer.read_text(encoding="utf-8")), encoding="utf-8")
    if sha256_file(trainer) != PATCHED_TRAIN_SHA256:
        raise ValueError("compatibility-patched producer trainer has an unexpected identity")
    staged = {relative: sha256_file(target / relative) for relative in BASE_SOURCE_SHA256}
    record = {
        "method_version": METHOD_VERSION,
        "base_source_sha256": BASE_SOURCE_SHA256,
        "staged_source_sha256": staged,
        "patched_train_sha256": PATCHED_TRAIN_SHA256,
        "patch_scope": "restore_removed_jax_tree_map_alias_only",
        "producer_clone_modified": False,
        "producer_data_included": False,
        "disposable_copy_only": True,
    }
    record_path = target / "bbus_source_transformation.json"
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record
