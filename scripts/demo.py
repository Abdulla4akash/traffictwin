"""Small wrapper for the TrafficTwin standalone demo workspace."""

from __future__ import annotations

from pathlib import Path

from traffictwin.demo.workspace import initialise_workspace


def main() -> None:
    """Initialise .demo and print the supported launch command."""

    workspace = Path(".demo")
    result = initialise_workspace(workspace, force=False)
    print(f"initialised: {result.path}")
    print(f"registry: {result.registry_path}")
    print("launch with: traffictwin demo launch .demo")


if __name__ == "__main__":
    main()
