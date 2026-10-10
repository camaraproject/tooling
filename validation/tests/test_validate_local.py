"""Tests for the local validation runner (validation/scripts/validate_local.py)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

# validation/scripts/ is not a package — load the module directly.
_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _ROOT / "validation" / "scripts" / "validate_local.py"
_spec = importlib.util.spec_from_file_location("validate_local", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
validate_local = importlib.util.module_from_spec(_spec)
sys.modules["validate_local"] = validate_local
_spec.loader.exec_module(validate_local)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init_repo(path: Path, origin: str | None = None, branch: str = "main") -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", branch)
    if origin is not None:
        _git(path, "remote", "add", "origin", origin)
    return path


class TestRepoName:
    @pytest.mark.parametrize(
        "origin",
        [
            "https://github.com/camaraproject/ReleaseTest.git",
            "https://github.com/camaraproject/ReleaseTest",
            "git@github.com:camaraproject/ReleaseTest.git",
        ],
    )
    def test_owner_and_repo_from_origin(self, tmp_path, origin):
        repo = _init_repo(tmp_path / "clone", origin)

        assert validate_local.repo_name(repo) == "camaraproject/ReleaseTest"

    def test_local_fallback_without_origin(self, tmp_path):
        repo = _init_repo(tmp_path / "MyApi")

        assert validate_local.repo_name(repo) == "local/MyApi"


class TestBuildEnv:
    def test_dispatch_run_of_the_checked_out_branch(self, tmp_path):
        repo = _init_repo(tmp_path / "api", "https://github.com/camaraproject/ReleaseTest.git", "feature/x")
        out = tmp_path / "out"

        env = validate_local.build_env(repo, out, base_env={"PATH": "/usr/bin"})

        assert env["VALIDATION_REPO_PATH"] == str(repo.resolve())
        assert env["VALIDATION_REPO_NAME"] == "camaraproject/ReleaseTest"
        assert env["VALIDATION_REPO_OWNER"] == "camaraproject"
        assert env["VALIDATION_REF_NAME"] == "feature/x"
        assert env["VALIDATION_EVENT_NAME"] == "workflow_dispatch"
        assert env["VALIDATION_TOOLING_PATH"] == str(_ROOT)
        assert env["VALIDATION_OUTPUT_DIR"] == str(out)

    def test_node_tools_on_path(self, tmp_path, monkeypatch):
        install = tmp_path / "nm"
        (install / ".bin").mkdir(parents=True)
        monkeypatch.setenv("CAMARA_NODE_MODULES", str(install))
        repo = _init_repo(tmp_path / "api")

        env = validate_local.build_env(repo, tmp_path / "out", base_env={"PATH": "/usr/bin"})

        assert env["PATH"].split(":")[:2] == [str(install / ".bin"), "/usr/bin"]
        assert env["NODE_PATH"] == str(install)

    def test_config_override_passes_the_stage_gate(self, tmp_path):
        from validation.config.config_gate import resolve_stage_from_files

        repo = _init_repo(tmp_path / "api")
        env = validate_local.build_env(repo, tmp_path / "out", base_env={})

        result = resolve_stage_from_files(
            config_path=Path(env["VALIDATION_CONFIG_PATH"]),
            schema_path=_ROOT / "validation" / "schemas" / "validation-settings-schema.yaml",
            repo_full_name=env["VALIDATION_REPO_NAME"],
            repo_owner=env["VALIDATION_REPO_OWNER"],
            trigger_type=env["VALIDATION_EVENT_NAME"],
        )

        assert result.should_continue
        assert result.stage == "enabled"


def _write_diagnostics(out: Path, result: str, findings: list[dict]) -> Path:
    diag = out / "diagnostics"
    diag.mkdir(parents=True)
    summary = {
        "result": result,
        "summary": "1 error, 1 warning",
        "counts": {"errors": 1, "warnings": 1, "hints": 0, "total": 2, "blocking": 1},
    }
    (diag / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (diag / "findings.json").write_text(json.dumps(findings), encoding="utf-8")
    return diag


_FINDINGS = [
    {"rule_id": "S-011", "path": "code/API_definitions/b.yaml", "line": 40,
     "level": "warn", "message": "late"},
    {"engine_rule": "camara-x", "path": "code/API_definitions/a.yaml", "line": 7,
     "level": "error", "message": "first"},
    {"rule_id": "S-002", "path": "code/API_definitions/b.yaml", "line": 3,
     "level": "error", "message": "early"},
]


class TestReport:
    def test_findings_grouped_by_file_in_line_order(self, tmp_path):
        diag = _write_diagnostics(tmp_path, "fail", _FINDINGS)

        lines = validate_local.format_report(tmp_path).splitlines()

        assert lines[0] == "result: fail - 1 error, 1 warning"
        assert "errors=1 warnings=1 hints=0 blocking=1" in lines[1]
        body = [line for line in lines[2:] if line]
        assert body[:5] == [
            "code/API_definitions/a.yaml",
            "  7\terror\tcamara-x\tfirst",
            "code/API_definitions/b.yaml",
            "  3\terror\tS-002\tearly",
            "  40\twarn\tS-011\tlate",
        ]
        assert lines[-1] == f"diagnostics: {diag}"

    def test_missing_summary_is_reported(self, tmp_path):
        assert "no summary.json" in validate_local.format_report(tmp_path)


class TestExitCode:
    @pytest.mark.parametrize(
        ("result", "expected"),
        [("pass", 0), ("advisory", 0), ("fail", 1), ("error", 2)],
    )
    def test_maps_result(self, tmp_path, result, expected):
        _write_diagnostics(tmp_path, result, [])

        assert validate_local.exit_code(tmp_path, orchestrator_rc=0) == expected

    def test_orchestrator_crash_wins(self, tmp_path):
        _write_diagnostics(tmp_path, "pass", [])

        assert validate_local.exit_code(tmp_path, orchestrator_rc=2) == 2

    def test_missing_summary_is_an_error(self, tmp_path):
        assert validate_local.exit_code(tmp_path, orchestrator_rc=0) == 2


_MINIMAL_SPEC = """\
openapi: 3.0.3
info:
  title: Sample
  version: wip
  description: Sample API.
servers:
  - url: "{apiRoot}/sample/vwip"
    variables:
      apiRoot:
        default: http://localhost:9091
paths: {}
"""


class TestMain:
    def test_rejects_a_directory_without_api_definitions(self, tmp_path, capsys):
        with pytest.raises(SystemExit):
            validate_local.main([str(tmp_path)])

        assert "code/API_definitions" in capsys.readouterr().err

    def test_stops_when_the_node_install_is_incomplete(self, tmp_path, monkeypatch, capsys):
        install = tmp_path / "nm"
        (install / ".bin").mkdir(parents=True)
        (install / ".bin" / "spectral").write_text("", encoding="utf-8")
        monkeypatch.setenv("CAMARA_NODE_MODULES", str(install))
        repo = _init_repo(tmp_path / "SampleApi")
        (repo / "code" / "API_definitions").mkdir(parents=True)

        rc = validate_local.main([str(repo), "--out", str(tmp_path / "out")])

        err = capsys.readouterr().err
        assert rc == validate_local.EXIT_ERROR
        assert "gplint, redocly" in err
        assert "CAMARA_NODE_MODULES" in err
        assert not (tmp_path / "out" / "diagnostics").exists()

    def test_runs_the_orchestrator_and_prints_the_report(self, tmp_path, capsys):
        repo = _init_repo(tmp_path / "SampleApi", "https://github.com/camaraproject/SampleApi.git")
        api_dir = repo / "code" / "API_definitions"
        api_dir.mkdir(parents=True)
        (api_dir / "sample.yaml").write_text(_MINIMAL_SPEC, encoding="utf-8")
        out = tmp_path / "out"

        rc = validate_local.main([str(repo), "--out", str(out)])

        report = capsys.readouterr().out
        assert (out / "diagnostics" / "summary.json").is_file()
        assert rc in (validate_local.EXIT_PASS, validate_local.EXIT_FAIL)
        assert report.startswith("result: ")
        assert "code/API_definitions/sample.yaml" in report
