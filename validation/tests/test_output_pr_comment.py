"""Unit tests for validation.output.pr_comment."""

from __future__ import annotations

from validation.context import ValidationContext
from validation.output.pr_comment import MARKER, generate_pr_comment
from validation.postfilter.engine import PostFilterResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(
    profile: str = "standard",
    workflow_run_url: str = "https://github.com/test/run/1",
    is_release_review_pr: bool = False,
    target_release_type: str | None = None,
) -> ValidationContext:
    return ValidationContext(
        repository="TestRepo",
        branch_type="main",
        trigger_type="pr",
        profile=profile,
        stage="enabled",
        target_release_type=target_release_type,
        commonalities_release=None,
        commonalities_version=None,
        icm_release=None,
        base_ref=None,
        is_release_review_pr=is_release_review_pr,
        release_plan_changed=None,
        pr_number=None,
        apis=(),
        workflow_run_url=workflow_run_url,
        tooling_ref="abc1234",
    )


def _make_finding(level: str = "warn", blocks: bool = False) -> dict:
    return {
        "engine": "spectral",
        "engine_rule": "some-rule",
        "level": level,
        "message": "Something is wrong",
        "path": "spec.yaml",
        "line": 10,
        "api_name": "quality-on-demand",
        "blocks": blocks,
    }


def _make_result(
    findings: list[dict] | None = None,
    result: str = "pass",
) -> PostFilterResult:
    return PostFilterResult(
        findings=findings or [],
        result=result,
        summary="test summary",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGeneratePrComment:
    def test_contains_marker(self):
        comment = generate_pr_comment(_make_result(), _make_context())
        assert MARKER in comment

    def test_marker_is_first_line(self):
        comment = generate_pr_comment(_make_result(), _make_context())
        assert comment.startswith(MARKER)

    def test_pass_result(self):
        comment = generate_pr_comment(_make_result(result="pass"), _make_context())
        assert "PASS" in comment

    def test_fail_result(self):
        comment = generate_pr_comment(_make_result(result="fail"), _make_context())
        assert "FAIL" in comment

    def test_error_result(self):
        comment = generate_pr_comment(_make_result(result="error"), _make_context())
        assert "ERROR" in comment

    def test_counts_displayed(self):
        findings = [
            _make_finding(level="error"),
            _make_finding(level="warn"),
            _make_finding(level="warn"),
            _make_finding(level="hint"),
        ]
        comment = generate_pr_comment(_make_result(findings), _make_context())
        assert "1 errors" in comment
        assert "2 warnings" in comment
        assert "1 hints" in comment

    def test_profile_displayed(self):
        comment = generate_pr_comment(
            _make_result(), _make_context(profile="strict")
        )
        assert "Profile: strict" in comment

    def test_workflow_url_linked(self):
        url = "https://github.com/test/run/42"
        comment = generate_pr_comment(
            _make_result(), _make_context(workflow_run_url=url)
        )
        assert f"[View full results]({url})" in comment

    def test_no_url_fallback(self):
        comment = generate_pr_comment(
            _make_result(), _make_context(workflow_run_url="")
        )
        assert "View full results" not in comment
        assert "See workflow summary" in comment

    def test_empty_findings(self):
        comment = generate_pr_comment(_make_result([]), _make_context())
        assert "0 errors, 0 warnings, 0 hints" in comment

    def test_pass_with_warnings_label(self):
        comment = generate_pr_comment(
            _make_result([_make_finding(level="warn")]), _make_context()
        )
        assert "CAMARA Validation — PASS (with warnings)" in comment

    def test_hints_only_keeps_plain_pass(self):
        comment = generate_pr_comment(
            _make_result([_make_finding(level="hint")]), _make_context()
        )
        assert "CAMARA Validation — PASS" in comment
        assert "(with warnings)" not in comment

    def test_review_pr_warning_note_must_for_rc(self):
        ctx = _make_context(
            is_release_review_pr=True, target_release_type="pre-release-rc"
        )
        comment = generate_pr_comment(_make_result([_make_finding(level="warn")]), ctx)
        assert "Warnings MUST be documented in one or more issues" in comment

    def test_review_pr_warning_note_should_for_alpha(self):
        ctx = _make_context(
            is_release_review_pr=True, target_release_type="pre-release-alpha"
        )
        comment = generate_pr_comment(_make_result([_make_finding(level="warn")]), ctx)
        assert "Warnings SHOULD be documented in one or more issues" in comment

    def test_no_review_note_on_normal_pr(self):
        comment = generate_pr_comment(
            _make_result([_make_finding(level="warn")]), _make_context()
        )
        assert "be documented in one or more issues before" not in comment

    def test_no_review_note_when_no_warnings(self):
        ctx = _make_context(
            is_release_review_pr=True, target_release_type="pre-release-rc"
        )
        comment = generate_pr_comment(_make_result([_make_finding(level="hint")]), ctx)
        assert "be documented in one or more issues before" not in comment
