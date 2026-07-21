"""Regression tests for discriminator-aware unused-component rule S-211."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_RULESET = _REPO_ROOT / "linting" / "config" / ".spectral-r4.yaml"
_RULESETS = [
    _REPO_ROOT / "linting" / "config" / ".spectral.yaml",
    _REPO_ROOT / "linting" / "config" / ".spectral-r3.4.yaml",
    _RULESET,
]
_NODE_MODULES = _REPO_ROOT / "validation" / "node_modules"
_RULE = "camara-discriminator-aware-unused-component"


def _run_spectral(spec: str, ruleset: Path = _RULESET) -> list[dict]:
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as file:
        file.write(spec)
        file.flush()
        spec_path = Path(file.name)

    env = {
        "PATH": os.environ.get("PATH", ""),
        "NODE_PATH": str(_NODE_MODULES),
        "HOME": os.environ.get("HOME", ""),
    }
    try:
        result = subprocess.run(
            [
                "node",
                str(_NODE_MODULES / ".bin" / "spectral"),
                "lint",
                str(spec_path),
                "-r",
                str(ruleset),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
    finally:
        spec_path.unlink(missing_ok=True)

    assert result.stdout.strip(), result.stderr
    return json.loads(result.stdout)


def _unused_component_paths(findings: list[dict]) -> list[list[str]]:
    return [finding["path"] for finding in findings if finding["code"] == _RULE]


_SPEC = """\
openapi: 3.0.3
info:
  title: Unused Component Test
  version: wip
paths:
  /events:
    get:
      operationId: getEvents
      responses:
        "200":
          $ref: "#/components/responses/EventResponse"
components:
  responses:
    EventResponse:
      description: OK
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/BaseEvent"
    UnusedResponse:
      description: Not referenced
  schemas:
    BaseEvent:
      type: object
      required:
        - eventType
      properties:
        eventType:
          type: string
      discriminator:
        propertyName: eventType
        mapping:
          started: "#/components/schemas/StartedEvent"
    StartedEvent:
      allOf:
        - $ref: "#/components/schemas/BaseEvent"
        - type: object
          properties:
            startedAt:
              type: string
    UnusedEvent:
      type: object
"""

_COMPONENTS_ONLY_SPEC = """\
components:
  schemas:
    SharedEvent:
      type: object
  responses:
    SharedResponse:
      description: OK
"""


@pytest.mark.parametrize("ruleset", _RULESETS, ids=lambda path: path.name)
def test_discriminator_mapping_counts_as_schema_reference(ruleset: Path):
    paths = _unused_component_paths(_run_spectral(_SPEC, ruleset))

    assert ["components", "schemas", "StartedEvent"] not in paths
    assert ["components", "schemas", "UnusedEvent"] in paths


def test_regular_refs_still_count_and_other_component_types_are_checked():
    paths = _unused_component_paths(_run_spectral(_SPEC))

    assert ["components", "responses", "EventResponse"] not in paths
    assert ["components", "responses", "UnusedResponse"] in paths


@pytest.mark.parametrize("ruleset", _RULESETS, ids=lambda path: path.name)
def test_components_only_documents_are_not_checked(ruleset: Path):
    paths = _unused_component_paths(_run_spectral(_COMPONENTS_ONLY_SPEC, ruleset))

    assert paths == []


def test_plain_schema_name_mapping_counts_as_reference():
    spec = _SPEC.replace(
        'started: "#/components/schemas/StartedEvent"',
        "started: StartedEvent",
    )

    paths = _unused_component_paths(_run_spectral(spec))

    assert ["components", "schemas", "StartedEvent"] not in paths


def test_external_mapping_does_not_mark_same_named_local_schema_as_used():
    spec = _SPEC.replace(
        'started: "#/components/schemas/StartedEvent"',
        'started: "./events.yaml#/components/schemas/StartedEvent"',
    )

    paths = _unused_component_paths(_run_spectral(spec))

    assert ["components", "schemas", "StartedEvent"] in paths


def test_unused_component_findings_are_warnings():
    findings = [
        finding for finding in _run_spectral(_SPEC) if finding["code"] == _RULE
    ]

    assert findings
    assert {finding["severity"] for finding in findings} == {1}
