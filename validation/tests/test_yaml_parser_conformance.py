"""Tests for the YAML parser conformance check (P-037)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

from validation.context import ApiContext, ValidationContext


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HELPER = _REPO_ROOT / "validation" / "scripts" / "check-yaml-parser-conformance.mjs"


def _make_context(api_name: str | None = None) -> ValidationContext:
    apis = ()
    if api_name is not None:
        apis = (
            ApiContext(
                api_name=api_name,
                target_api_version="0.1.0",
                target_api_status="alpha",
                target_api_maturity="initial",
                api_pattern="request-response",
                spec_file=f"code/API_definitions/{api_name}.yaml",
            ),
        )
    return ValidationContext(
        repository="TestRepo",
        branch_type="main",
        trigger_type="dispatch",
        profile="advisory",
        stage="enabled",
        target_release_type=None,
        commonalities_release=None,
        commonalities_version=None,
        icm_release=None,
        base_ref=None,
        is_release_review_pr=False,
        release_plan_changed=None,
        pr_number=None,
        apis=apis,
        workflow_run_url="",
        tooling_ref="",
    )


def _write_api_definition(tmp_path: Path, name: str, content: str) -> Path:
    api_dir = tmp_path / "code" / "API_definitions"
    api_dir.mkdir(parents=True, exist_ok=True)
    path = api_dir / f"{name}.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def _run_helper(tmp_path: Path, *paths: str) -> list[dict]:
    result = subprocess.run(
        ["node", str(_HELPER), *paths],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


_VALID_OPENAPI = """\
openapi: 3.0.3
info:
  title: Test API
  version: wip
paths: {}
"""

_FLOW_MAPPING_INDENTATION = """\
openapi: 3.0.3
info:
  title: Test API
  version: wip
paths: {}
components:
  schemas:
    Subscription:
      example:
        sinkCredential: {
          "credentialType": "ACCESSTOKEN",
          "accessToken": "xxx",
          "accessTokenExpiresUtc": "2024-02-17T16:23:45Z",
          "accessTokenType": "bearer"
        }
        protocol: HTTP
"""

_MULTILINE_SINGLE_QUOTED_SCALAR = """\
openapi: 3.0.3
info:
  title: Test API
  version: wip
paths: {}
components:
  schemas:
    Event:
      properties:
        mediaType:
          description: 'media-type that describes the event payload
          encoding, must be "application/json" for CAMARA APIs'
"""


class TestYamlParserConformanceHelper:
    def test_valid_yaml_has_no_findings(self, tmp_path: Path):
        _write_api_definition(tmp_path, "sample-service", _VALID_OPENAPI)

        findings = _run_helper(
            tmp_path,
            "code/API_definitions/sample-service.yaml",
        )

        assert findings == []

    def test_flow_mapping_indentation_shape_is_reported(self, tmp_path: Path):
        _write_api_definition(
            tmp_path,
            "sample-service-subscriptions",
            _FLOW_MAPPING_INDENTATION,
        )

        findings = _run_helper(
            tmp_path,
            "code/API_definitions/sample-service-subscriptions.yaml",
        )

        assert len(findings) == 1
        finding = findings[0]
        assert finding["path"] == "code/API_definitions/sample-service-subscriptions.yaml"
        assert finding["line"] > 1
        assert finding["column"] > 0
        assert "deficient indentation" in finding["reason"]

    def test_multiline_quoted_scalar_shape_is_reported(self, tmp_path: Path):
        _write_api_definition(
            tmp_path,
            "sample-implicit-events",
            _MULTILINE_SINGLE_QUOTED_SCALAR,
        )

        findings = _run_helper(
            tmp_path,
            "code/API_definitions/sample-implicit-events.yaml",
        )

        assert len(findings) == 1
        assert findings[0]["path"] == "code/API_definitions/sample-implicit-events.yaml"
        assert "deficient indentation" in findings[0]["reason"]

    def test_multiple_files_emit_one_finding_per_invalid_file(self, tmp_path: Path):
        _write_api_definition(tmp_path, "sample-service", _VALID_OPENAPI)
        _write_api_definition(
            tmp_path,
            "sample-service-subscriptions",
            _FLOW_MAPPING_INDENTATION,
        )
        _write_api_definition(
            tmp_path,
            "sample-implicit-events",
            _MULTILINE_SINGLE_QUOTED_SCALAR,
        )

        findings = _run_helper(
            tmp_path,
            "code/API_definitions/sample-service.yaml",
            "code/API_definitions/sample-service-subscriptions.yaml",
            "code/API_definitions/sample-implicit-events.yaml",
        )

        assert {
            finding["path"] for finding in findings
        } == {
            "code/API_definitions/sample-service-subscriptions.yaml",
            "code/API_definitions/sample-implicit-events.yaml",
        }


class TestCheckYamlParserConformance:
    def test_no_api_context_returns_no_findings(self, tmp_path: Path, monkeypatch):
        from validation.engines.python_checks import yaml_parser_conformance_checks

        run = Mock()
        monkeypatch.setattr(yaml_parser_conformance_checks.subprocess, "run", run)

        findings = yaml_parser_conformance_checks.check_yaml_parser_conformance(
            tmp_path,
            _make_context(),
        )

        assert findings == []
        run.assert_not_called()

    def test_missing_spec_file_returns_no_findings(self, tmp_path: Path, monkeypatch):
        from validation.engines.python_checks import yaml_parser_conformance_checks

        run = Mock()
        monkeypatch.setattr(yaml_parser_conformance_checks.subprocess, "run", run)

        findings = yaml_parser_conformance_checks.check_yaml_parser_conformance(
            tmp_path,
            _make_context("sample-service"),
        )

        assert findings == []
        run.assert_not_called()

    def test_valid_helper_result_returns_no_findings(self, tmp_path: Path, monkeypatch):
        from validation.engines.python_checks import yaml_parser_conformance_checks

        _write_api_definition(tmp_path, "sample-service", _VALID_OPENAPI)
        monkeypatch.setattr(
            yaml_parser_conformance_checks.subprocess,
            "run",
            Mock(return_value=subprocess.CompletedProcess([], 0, stdout="[]", stderr="")),
        )

        findings = yaml_parser_conformance_checks.check_yaml_parser_conformance(
            tmp_path,
            _make_context("sample-service"),
        )

        assert findings == []

    def test_parser_error_is_converted_to_warning(self, tmp_path: Path, monkeypatch):
        from validation.engines.python_checks import yaml_parser_conformance_checks

        _write_api_definition(
            tmp_path,
            "sample-service-subscriptions",
            _FLOW_MAPPING_INDENTATION,
        )
        helper_output = [
            {
                "path": "code/API_definitions/sample-service-subscriptions.yaml",
                "line": 15,
                "column": 9,
                "reason": "deficient indentation",
                "message": "YAML parser rejected the document",
            }
        ]
        monkeypatch.setattr(
            yaml_parser_conformance_checks.subprocess,
            "run",
            Mock(
                return_value=subprocess.CompletedProcess(
                    [],
                    0,
                    stdout=json.dumps(helper_output),
                    stderr="",
                )
            ),
        )

        findings = yaml_parser_conformance_checks.check_yaml_parser_conformance(
            tmp_path,
            _make_context("sample-service-subscriptions"),
        )

        assert len(findings) == 1
        assert findings[0]["engine"] == "python"
        assert findings[0]["engine_rule"] == "check-yaml-parser-conformance"
        assert findings[0]["level"] == "warn"
        assert findings[0]["path"] == "code/API_definitions/sample-service-subscriptions.yaml"
        assert findings[0]["line"] == 15
        assert findings[0]["column"] == 9
        assert findings[0]["api_name"] == "sample-service-subscriptions"
        assert "deficient indentation" in findings[0]["message"]

    def test_helper_failure_is_visible_as_error(self, tmp_path: Path, monkeypatch):
        from validation.engines.python_checks import yaml_parser_conformance_checks

        _write_api_definition(tmp_path, "sample-service", _VALID_OPENAPI)
        monkeypatch.setattr(
            yaml_parser_conformance_checks.subprocess,
            "run",
            Mock(
                return_value=subprocess.CompletedProcess(
                    [],
                    1,
                    stdout="",
                    stderr="helper exploded",
                )
            ),
        )

        findings = yaml_parser_conformance_checks.check_yaml_parser_conformance(
            tmp_path,
            _make_context("sample-service"),
        )

        assert len(findings) == 1
        assert findings[0]["engine_rule"] == "yaml-parser-conformance-execution-error"
        assert findings[0]["level"] == "error"
        assert "helper failed" in findings[0]["message"]
