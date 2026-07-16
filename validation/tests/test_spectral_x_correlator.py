"""Regression tests for x-correlator documentation rules S-039 and S-040."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_RULESET = _REPO_ROOT / "linting" / "config" / ".spectral-r4.yaml"
_NODE_MODULES = _REPO_ROOT / "validation" / "node_modules"
_REQUEST_RULE = "camara-x-correlator-request-parameter"
_RESPONSE_RULE = "camara-x-correlator-response-header"


def _run_spectral(files: dict[str, str], entrypoint: str = "api.yaml") -> list[dict]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for name, content in files.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        env = {
            "PATH": os.environ.get("PATH", ""),
            "NODE_PATH": str(_NODE_MODULES),
            "HOME": os.environ.get("HOME", ""),
        }
        result = subprocess.run(
            [
                "node",
                str(_NODE_MODULES / ".bin" / "spectral"),
                "lint",
                str(root / entrypoint),
                "-r",
                str(_RULESET),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        assert result.stdout.strip(), result.stderr
        return json.loads(result.stdout)


def _for_rule(findings: list[dict], rule: str) -> list[dict]:
    return [finding for finding in findings if finding["code"] == rule]


_SPEC = """\
openapi: 3.0.3
info:
  title: Correlator Test
  version: wip
paths:
  /widgets:
    get:
      operationId: getWidgets
      parameters:
        - name: x-correlator
          in: header
          schema:
            type: string
      responses:
        "200":
          description: OK
          headers:
            x-correlator:
              schema:
                type: string
"""


def test_documented_request_and_response_pass():
    findings = _run_spectral({"api.yaml": _SPEC})
    assert _for_rule(findings, _REQUEST_RULE) == []
    assert _for_rule(findings, _RESPONSE_RULE) == []


def test_path_level_request_parameter_applies_to_operation():
    spec = _SPEC.replace(
        "    get:\n      operationId: getWidgets\n      parameters:\n",
        "    parameters:\n      - name: x-correlator\n        in: header\n        schema:\n          type: string\n    get:\n      operationId: getWidgets\n      parameters:\n",
    ).replace(
        "        - name: x-correlator\n          in: header\n          schema:\n            type: string\n",
        "        - name: limit\n          in: query\n          schema:\n            type: integer\n",
    )
    findings = _run_spectral({"api.yaml": spec})
    assert _for_rule(findings, _REQUEST_RULE) == []


def test_missing_request_parameter_reports_operation_path():
    spec = _SPEC.replace("        - name: x-correlator", "        - name: traceparent")
    findings = _for_rule(_run_spectral({"api.yaml": spec}), _REQUEST_RULE)
    assert len(findings) == 1
    assert findings[0]["path"] == ["paths", "/widgets", "get", "parameters"]


def test_each_response_without_header_is_reported():
    spec = _SPEC.replace(
        "          headers:\n            x-correlator:\n              schema:\n                type: string\n",
        "",
    ) + """\
        "400":
          description: Bad request
          headers: {}
"""
    findings = _for_rule(_run_spectral({"api.yaml": spec}), _RESPONSE_RULE)
    assert len(findings) == 2
    assert any("200" in finding["path"] for finding in findings)
    assert any("400" in finding["path"] for finding in findings)


def test_component_references_are_resolved():
    spec = """\
openapi: 3.0.3
info:
  title: Correlator Test
  version: wip
paths:
  /widgets:
    get:
      operationId: getWidgets
      parameters:
        - $ref: "#/components/parameters/XCorrelator"
      responses:
        "200":
          $ref: "#/components/responses/CorrelatedResponse"
components:
  parameters:
    XCorrelator:
      name: x-correlator
      in: header
      schema:
        type: string
  responses:
    CorrelatedResponse:
      description: OK
      headers:
        x-correlator:
          schema:
            type: string
"""
    findings = _run_spectral({"api.yaml": spec})
    assert _for_rule(findings, _REQUEST_RULE) == []
    assert _for_rule(findings, _RESPONSE_RULE) == []


def test_external_references_are_resolved():
    spec = """\
openapi: 3.0.3
info:
  title: Correlator Test
  version: wip
paths:
  /widgets:
    get:
      operationId: getWidgets
      parameters:
        - $ref: "./common.yaml#/components/parameters/XCorrelator"
      responses:
        "200":
          $ref: "./common.yaml#/components/responses/CorrelatedResponse"
"""
    common = """\
openapi: 3.0.3
info:
  title: Common
  version: wip
paths: {}
components:
  parameters:
    XCorrelator:
      name: x-correlator
      in: header
      schema:
        type: string
  responses:
    CorrelatedResponse:
      description: OK
      headers:
        x-correlator:
          schema:
            type: string
"""
    findings = _run_spectral({"api.yaml": spec, "common.yaml": common})
    assert _for_rule(findings, _REQUEST_RULE) == []
    assert _for_rule(findings, _RESPONSE_RULE) == []


def test_callback_operation_is_in_scope():
    spec = _SPEC.replace(
        "      responses:\n",
        "      callbacks:\n"
        "        onEvent:\n"
        "          '{$request.body#/sink}':\n"
        "            post:\n"
        "              operationId: onEvent\n"
        "              responses:\n"
        "                '204':\n"
        "                  description: Accepted\n"
        "      responses:\n",
        1,
    )
    findings = _run_spectral({"api.yaml": spec})
    request_findings = _for_rule(findings, _REQUEST_RULE)
    response_findings = _for_rule(findings, _RESPONSE_RULE)
    assert len(request_findings) == 1
    assert "callbacks" in request_findings[0]["path"]
    assert len(response_findings) == 1
    assert "callbacks" in response_findings[0]["path"]
