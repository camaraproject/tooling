"""Unit tests for validation.output.diagnostics."""

from __future__ import annotations

import json
from pathlib import Path

from validation.context import ValidationContext
from validation.output.diagnostics import write_diagnostics
from validation.postfilter.engine import PostFilterResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context() -> ValidationContext:
    return ValidationContext(
        repository="TestRepo",
        branch_type="main",
        trigger_type="pr",
        profile="standard",
        stage="enabled",
        target_release_type=None,
        commonalities_release=None,
        commonalities_version=None,
        icm_release=None,
        base_ref=None,
        is_release_review_pr=False,
        release_plan_changed=None,
        pr_number=None,
        apis=(),
        workflow_run_url="https://example.com/run/1",
        tooling_ref="abc1234",
    )


def _make_finding(
    level: str = "warn",
    message: str = "Something is wrong",
) -> dict:
    return {
        "engine": "spectral",
        "engine_rule": "some-rule",
        "level": level,
        "message": message,
        "path": "spec.yaml",
        "line": 10,
        "api_name": "quality-on-demand",
        "blocks": False,
    }


def _make_result(
    findings: list[dict] | None = None,
    result: str = "pass",
) -> PostFilterResult:
    return PostFilterResult(
        findings=findings or [],
        result=result,
        summary="Passed: no findings",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWriteDiagnostics:
    def test_creates_expected_files(self, tmp_path: Path):
        out = tmp_path / "output"
        paths = write_diagnostics(_make_result(), _make_context(), out)
        names = {p.name for p in paths}
        assert names == {
            "findings.json",
            "context.json",
            "summary.json",
            "findings.tsv",
        }

    def test_findings_json_content(self, tmp_path: Path):
        findings = [_make_finding(level="error"), _make_finding(level="warn")]
        out = tmp_path / "output"
        write_diagnostics(_make_result(findings), _make_context(), out)
        data = json.loads((out / "findings.json").read_text())
        assert len(data) == 2
        assert data[0]["level"] == "error"
        assert data[1]["level"] == "warn"

    def test_context_json_parseable(self, tmp_path: Path):
        out = tmp_path / "output"
        write_diagnostics(_make_result(), _make_context(), out)
        data = json.loads((out / "context.json").read_text())
        assert data["repository"] == "TestRepo"
        assert data["profile"] == "standard"

    def test_summary_json_content(self, tmp_path: Path):
        findings = [
            _make_finding(level="error"),
            _make_finding(level="warn"),
        ]
        out = tmp_path / "output"
        write_diagnostics(
            _make_result(findings, result="fail"),
            _make_context(),
            out,
        )
        data = json.loads((out / "summary.json").read_text())
        assert data["result"] == "fail"
        assert data["counts"]["errors"] == 1
        assert data["counts"]["warnings"] == 1
        assert data["counts"]["total"] == 2

    def test_engine_reports_written_when_provided(self, tmp_path: Path):
        out = tmp_path / "output"
        reports = {"spectral": {"raw": "data"}}
        paths = write_diagnostics(
            _make_result(), _make_context(), out, engine_reports=reports
        )
        names = {p.name for p in paths}
        assert "engine-reports.json" in names
        data = json.loads((out / "engine-reports.json").read_text())
        assert data["spectral"]["raw"] == "data"

    def test_engine_reports_omitted_when_none(self, tmp_path: Path):
        out = tmp_path / "output"
        paths = write_diagnostics(_make_result(), _make_context(), out)
        assert not (out / "engine-reports.json").exists()
        assert len(paths) == 4

    def test_empty_findings(self, tmp_path: Path):
        out = tmp_path / "output"
        write_diagnostics(_make_result([]), _make_context(), out)
        data = json.loads((out / "findings.json").read_text())
        assert data == []

    def test_creates_output_dir(self, tmp_path: Path):
        out = tmp_path / "nested" / "deep" / "output"
        assert not out.exists()
        write_diagnostics(_make_result(), _make_context(), out)
        assert out.exists()
        assert (out / "findings.json").exists()

    def test_returns_written_paths(self, tmp_path: Path):
        out = tmp_path / "output"
        paths = write_diagnostics(_make_result(), _make_context(), out)
        assert all(isinstance(p, Path) for p in paths)
        assert all(p.exists() for p in paths)


class TestFindingsTsv:
    def test_header_row(self, tmp_path: Path):
        out = tmp_path / "output"
        write_diagnostics(_make_result(), _make_context(), out)
        text = (out / "findings.tsv").read_text(encoding="utf-8")
        first_line = text.splitlines()[0]
        assert first_line == (
            "rule\tfile\tline\tlevel\tmessage\tsuggestion\tdocumentation_url"
        )

    def test_row_per_finding(self, tmp_path: Path):
        findings = [
            _make_finding(level="error"),
            _make_finding(level="warn"),
            _make_finding(level="hint"),
        ]
        out = tmp_path / "output"
        write_diagnostics(_make_result(findings), _make_context(), out)
        text = (out / "findings.tsv").read_text(encoding="utf-8")
        # Header + 3 rows + trailing newline → 4 non-empty lines
        rows = [line for line in text.splitlines() if line.strip()]
        assert len(rows) == 4

    def test_field_values_present(self, tmp_path: Path):
        findings = [
            {
                "engine": "spectral",
                "engine_rule": "camara-x",
                "rule_id": "S-042",
                "level": "error",
                "message": "Bad path",
                "path": "spec.yaml",
                "line": 47,
                "api_name": None,
                "blocks": True,
                "suggestion": "Use kebab-case",
            }
        ]
        out = tmp_path / "output"
        write_diagnostics(_make_result(findings), _make_context(), out)
        text = (out / "findings.tsv").read_text(encoding="utf-8")
        # Row carries each column value, tab-separated
        assert "S-042\tspec.yaml\t47\terror\tBad path\tUse kebab-case" in text

    def test_tab_in_field_sanitized(self, tmp_path: Path):
        findings = [
            {
                "engine": "spectral",
                "engine_rule": "camara-x",
                "rule_id": "S-001",
                "level": "warn",
                "message": "left\tright",
                "path": "a.yaml",
                "line": 10,
                "api_name": None,
                "blocks": False,
            }
        ]
        out = tmp_path / "output"
        write_diagnostics(_make_result(findings), _make_context(), out)
        text = (out / "findings.tsv").read_text(encoding="utf-8")
        # Tab inside the message must be flattened to a single space —
        # the row must still split into exactly 7 columns on `\t`.
        data_row = text.splitlines()[1]
        assert data_row.count("\t") == 6
        assert "left right" in data_row

    def test_newline_in_field_sanitized(self, tmp_path: Path):
        findings = [
            {
                "engine": "spectral",
                "engine_rule": "camara-x",
                "rule_id": "S-001",
                "level": "warn",
                "message": "first\nsecond",
                "path": "a.yaml",
                "line": 10,
                "api_name": None,
                "blocks": False,
            }
        ]
        out = tmp_path / "output"
        write_diagnostics(_make_result(findings), _make_context(), out)
        text = (out / "findings.tsv").read_text(encoding="utf-8")
        # Newline inside message must not break the row — header + 1 data row.
        rows = [line for line in text.splitlines() if line.strip()]
        assert len(rows) == 2
        assert "first second" in rows[1]

    def test_empty_findings(self, tmp_path: Path):
        out = tmp_path / "output"
        write_diagnostics(_make_result([]), _make_context(), out)
        text = (out / "findings.tsv").read_text(encoding="utf-8")
        # Header only.
        rows = [line for line in text.splitlines() if line.strip()]
        assert len(rows) == 1
        assert rows[0] == (
            "rule\tfile\tline\tlevel\tmessage\tsuggestion\tdocumentation_url"
        )

    def test_missing_optional_fields(self, tmp_path: Path):
        # Finding without `suggestion` field — TSV row writes empty string.
        findings = [
            {
                "engine": "spectral",
                "engine_rule": "camara-x",
                "level": "warn",
                "message": "msg",
                "path": "a.yaml",
                "line": 10,
                "api_name": None,
                "blocks": False,
            }
        ]
        out = tmp_path / "output"
        write_diagnostics(_make_result(findings), _make_context(), out)
        text = (out / "findings.tsv").read_text(encoding="utf-8")
        data_row = text.splitlines()[1]
        # 6 tabs → 7 columns; suggestion and documentation_url both empty.
        assert data_row.count("\t") == 6
        assert data_row.endswith("msg\t\t")

    def test_documentation_url_column(self, tmp_path: Path):
        url = (
            "https://github.com/camaraproject/tooling/blob/main/"
            "documentation/validation/faq.md#s-042-example"
        )
        findings = [
            {
                "engine": "spectral",
                "engine_rule": "camara-x",
                "rule_id": "S-042",
                "level": "error",
                "message": "Bad path",
                "path": "spec.yaml",
                "line": 47,
                "api_name": None,
                "blocks": True,
                "suggestion": "Use kebab-case",
                "documentation_url": url,
            }
        ]
        out = tmp_path / "output"
        write_diagnostics(_make_result(findings), _make_context(), out)
        text = (out / "findings.tsv").read_text(encoding="utf-8")
        data_row = text.splitlines()[1]
        assert data_row.endswith(f"\t{url}")
        assert data_row.count("\t") == 6
