#!/usr/bin/env python3
"""Run the CAMARA validation orchestrator against a local API repository.

Validates the repository as a ``workflow_dispatch`` run of its checked-out
branch, using this tooling checkout and a settings override that enables
validation for any repository. The ruleset follows ``release-plan.yaml``
as in CI.

Usage:
    python3 validation/scripts/validate_local.py <repo-path> [--out <dir>]

Exit codes:
    0  pass or advisory
    1  fail (blocking findings)
    2  error (usage, orchestrator crash, or an engine that did not run)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Mapping

TOOLING_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOOLING_ROOT))

from validation.engines import node_tools  # noqa: E402
from validation.output.formatting import format_rule_label  # noqa: E402

CONFIG_OVERRIDE = Path(__file__).resolve().parent / "local-validation-settings.yaml"

NODE_TOOLS = ("spectral", "gplint", "redocly")

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ERROR = 2

_ORIGIN_RE = re.compile(r"[:/]([^/:]+/[^/]+?)(?:\.git)?/?$")


def _git(repo_path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def repo_name(repo_path: Path) -> str:
    """Return ``owner/repo`` from the ``origin`` remote, else ``local/<dir>``."""
    match = _ORIGIN_RE.search(_git(repo_path, "remote", "get-url", "origin"))
    if match:
        return match.group(1)
    return f"local/{repo_path.resolve().name}"


def missing_node_tools() -> list[str]:
    """Return the Node tools absent from the resolved ``node_modules/.bin``."""
    return [tool for tool in NODE_TOOLS if not (node_tools.bin_dir() / tool).exists()]


def build_env(
    repo_path: Path,
    output_dir: Path,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return the orchestrator environment for a dispatch-style local run."""
    env = dict(os.environ if base_env is None else base_env)
    name = repo_name(repo_path)
    env.update(
        {
            "PATH": os.pathsep.join(filter(None, [str(node_tools.bin_dir()), env.get("PATH")])),
            "NODE_PATH": str(node_tools.node_modules_dir()),
            "PYTHONPATH": str(TOOLING_ROOT),
            "VALIDATION_REPO_PATH": str(repo_path.resolve()),
            "VALIDATION_REPO_NAME": name,
            "VALIDATION_REPO_OWNER": name.split("/", 1)[0],
            "VALIDATION_REF_NAME": _git(repo_path, "symbolic-ref", "--short", "HEAD"),
            "VALIDATION_EVENT_NAME": "workflow_dispatch",
            "VALIDATION_TOOLING_PATH": str(TOOLING_ROOT),
            "VALIDATION_OUTPUT_DIR": str(output_dir),
            "VALIDATION_CONFIG_PATH": str(CONFIG_OVERRIDE),
        }
    )
    return env


def _read_summary(output_dir: Path) -> dict | None:
    path = output_dir / "diagnostics" / "summary.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def format_report(output_dir: Path) -> str:
    """Return the verdict, counts and per-file findings of a finished run."""
    diag = output_dir / "diagnostics"
    summary = _read_summary(output_dir)
    if summary is None:
        return f"no summary.json in {diag} (see the orchestrator log above)"

    counts = summary.get("counts", {})
    lines = [
        f"result: {summary.get('result')} - {summary.get('summary', '')}",
        "counts: " + " ".join(
            f"{key}={counts.get(key, 0)}" for key in ("errors", "warnings", "hints", "blocking")
        ),
    ]

    findings = json.loads((diag / "findings.json").read_text(encoding="utf-8"))
    by_file: dict[str, list[dict]] = {}
    for finding in findings:
        by_file.setdefault(finding.get("path") or "(no file)", []).append(finding)
    for path in sorted(by_file):
        lines += ["", path]
        for finding in sorted(by_file[path], key=lambda f: f.get("line") or 0):
            lines.append(
                f"  {finding.get('line') or 0}\t{finding.get('level', '')}"
                f"\t{format_rule_label(finding)}\t{finding.get('message', '')}"
            )

    lines += ["", f"diagnostics: {diag}"]
    return "\n".join(lines)


def exit_code(output_dir: Path, orchestrator_rc: int) -> int:
    """Map the orchestrator return code and verdict to the script's exit code."""
    summary = _read_summary(output_dir)
    if orchestrator_rc != 0 or summary is None:
        return EXIT_ERROR
    return {"fail": EXIT_FAIL, "error": EXIT_ERROR}.get(summary.get("result"), EXIT_PASS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run CAMARA validation against a local API repository."
    )
    parser.add_argument("repo_path", type=Path, help="local clone of the API repository")
    parser.add_argument(
        "--out", type=Path, help="output directory (default: a new temporary directory)"
    )
    args = parser.parse_args(argv)

    repo_path = args.repo_path.resolve()
    if not (repo_path / "code" / "API_definitions").is_dir():
        parser.error(f"not an API repository (no code/API_definitions): {repo_path}")
    missing = missing_node_tools()
    if missing:
        print(
            f"missing in {node_tools.bin_dir()}: {', '.join(missing)}\n"
            f"run `npm ci` in validation/ or set {node_tools.ENV_VAR} "
            "to an existing node_modules directory",
            file=sys.stderr,
        )
        return EXIT_ERROR
    output_dir = args.out or Path(tempfile.mkdtemp(prefix="camara-validation-"))

    env = build_env(repo_path, output_dir)
    print(
        f"validating {env['VALIDATION_REPO_NAME']} "
        f"(ref {env['VALIDATION_REF_NAME'] or '<detached>'}) with {TOOLING_ROOT}",
        file=sys.stderr,
    )
    rc = subprocess.run(
        [sys.executable, "-m", "validation.orchestrator"],
        cwd=TOOLING_ROOT,
        env=env,
    ).returncode

    print(format_report(output_dir))
    return exit_code(output_dir, rc)


if __name__ == "__main__":
    sys.exit(main())
