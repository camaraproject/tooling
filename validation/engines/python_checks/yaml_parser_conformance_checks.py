"""YAML parser conformance check.

Runs an explicit ``js-yaml@5`` parser probe for the current API definition file
and reports parser failures as advisory Validation findings.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import List

from validation.context import ValidationContext

from ._types import make_finding

_ENGINE_RULE = "check-yaml-parser-conformance"
_EXECUTION_ERROR_RULE = "yaml-parser-conformance-execution-error"
_VALIDATION_ROOT = Path(__file__).resolve().parents[2]
_HELPER = _VALIDATION_ROOT / "scripts" / "check-yaml-parser-conformance.mjs"
_TIMEOUT_SECONDS = 60


def check_yaml_parser_conformance(
    repo_path: Path, context: ValidationContext
) -> List[dict]:
    """Check the current API definition with the pinned strict YAML parser.

    API-scoped check — the adapter calls this once per API context. Missing
    files are left to the existing release-plan/API-file checks.
    """
    if not context.apis:
        return []

    api = context.apis[0]
    spec_file = api.spec_file or f"code/API_definitions/{api.api_name}.yaml"
    if not spec_file:
        return []

    if not (repo_path / spec_file).is_file():
        return []

    helper_result = _run_helper(repo_path, spec_file)
    if isinstance(helper_result, dict):
        return [helper_result]

    findings: List[dict] = []
    for item in helper_result:
        reason = str(item.get("reason") or "YAML parser error")
        path = str(item.get("path") or spec_file)
        findings.append(
            make_finding(
                engine_rule=_ENGINE_RULE,
                level="warn",
                message=f"OpenAPI YAML fails parser conformance: {reason}",
                path=path,
                line=_positive_int(item.get("line"), 1),
                api_name=api.api_name,
                column=_positive_int(item.get("column"), 1),
            )
        )
    return findings


def _run_helper(repo_path: Path, spec_file: str) -> list[dict] | dict:
    try:
        result = subprocess.run(
            ["node", str(_HELPER), spec_file],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        return _helper_error(f"YAML parser conformance helper could not run: {exc}")

    if result.returncode != 0:
        stderr = result.stderr.strip() or "no stderr"
        return _helper_error(
            f"YAML parser conformance helper failed: {stderr}"
        )

    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        return _helper_error(
            f"YAML parser conformance helper returned invalid JSON: {exc}"
        )

    if not isinstance(payload, list):
        return _helper_error(
            "YAML parser conformance helper returned non-list JSON"
        )

    return [item for item in payload if isinstance(item, dict)]


def _helper_error(message: str) -> dict:
    return make_finding(
        engine_rule=_EXECUTION_ERROR_RULE,
        level="error",
        message=message,
        path="",
        line=1,
        api_name=None,
    )


def _positive_int(value: object, default: int) -> int:
    return value if isinstance(value, int) and value > 0 else default
