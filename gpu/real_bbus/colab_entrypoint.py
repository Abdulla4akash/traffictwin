# ruff: noqa: S603
"""Install the frozen B-BUS stack and run the uploaded checkpointed pack."""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def main() -> int:
    content = Path("/content")
    archives = sorted(content.glob("traffictwin_bbus_*_checkpointed_colab_*.zip"))
    if len(archives) != 1:
        raise ValueError(f"expected exactly one checkpointed B-BUS pack, found {archives}")
    archive = archives[0]
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() is not None:
            raise ValueError("uploaded B-BUS pack failed CRC verification")
        roots = {Path(name).parts[0] for name in zipped.namelist() if name}
        if len(roots) != 1:
            raise ValueError("B-BUS pack has an ambiguous root")
        pack_root = content / next(iter(roots))
        if pack_root.exists():
            raise ValueError(f"pack extraction root already exists: {pack_root}")
        zipped.extractall(content)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-r",
            str(pack_root / "requirements-colab.txt"),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-deps",
            "-r",
            str(pack_root / "requirements-colab-no-deps.txt"),
        ],
        check=True,
    )
    equivalence_script = content / "verify_checkpoint_equivalence.py"
    if equivalence_script.is_file():
        completed = subprocess.run(
            [
                sys.executable,
                str(equivalence_script),
                "--pack-root",
                str(pack_root),
                "--output-root",
                str(content / "bbus_checkpoint_equivalence"),
            ],
            check=False,
        )
        return completed.returncode
    arm = pack_root.name.removeprefix("bbus_").removesuffix("_colab")
    output = content / f"bbus_{arm}_results"
    checkpoint_bootstrap = sorted(content.glob("model-seed-*.checkpoint.zip*"))
    if checkpoint_bootstrap:
        output.mkdir(parents=True, exist_ok=True)
        for checkpoint_file in checkpoint_bootstrap:
            shutil.move(str(checkpoint_file), output / checkpoint_file.name)
    completed = subprocess.run(
        [
            sys.executable,
            str(pack_root / "runner/run_campaign.py"),
            "--pack-root",
            str(pack_root),
            "--output-root",
            str(output),
            "--max-workers",
            "5",
        ],
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
