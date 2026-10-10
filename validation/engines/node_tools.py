"""Locate the Node tool install (Spectral, Redocly) used by tests and local runs.

Resolution order for the ``node_modules`` directory:

1. ``CAMARA_NODE_MODULES`` environment variable
2. a ``spectral`` executable on ``PATH`` that sits in a ``node_modules/.bin`` directory
3. ``validation/node_modules`` in this repository
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

ENV_VAR = "CAMARA_NODE_MODULES"

_REPO_DEFAULT = Path(__file__).resolve().parent.parent / "node_modules"


def node_modules_dir() -> Path:
    """Return the ``node_modules`` directory to use."""
    configured = os.environ.get(ENV_VAR, "").strip()
    if configured:
        return Path(configured)

    on_path = shutil.which("spectral")
    if on_path:
        bin_dir = Path(on_path).parent
        if bin_dir.name == ".bin":
            return bin_dir.parent

    return _REPO_DEFAULT


def bin_dir() -> Path:
    """Return the ``.bin`` directory of the resolved install."""
    return node_modules_dir() / ".bin"


def spectral_bin() -> Path:
    """Return the path of the Spectral executable in the resolved install."""
    return bin_dir() / "spectral"


def spectral_env() -> dict[str, str]:
    """Return the minimal environment for running Spectral under ``node``."""
    return {
        "PATH": os.environ.get("PATH", ""),
        "NODE_PATH": str(node_modules_dir()),
        "HOME": os.environ.get("HOME", ""),
    }
