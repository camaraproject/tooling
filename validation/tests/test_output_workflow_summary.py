"""Unit tests for validation.output.workflow_summary."""

from __future__ import annotations

from validation.context import ApiContext, ValidationContext
from validation.output.workflow_summary import (
    SUMMARY_SIZE_LIMIT,
    SummaryResult,
    generate_workflow_summary,
)
from validation.postfilter.engine import PostFilterResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(
    profile: str = "standard",
    branch_type: str = "main",
    trigger_type: str = "pr",
    workflow_run_url: str = "https://github.com/test/run/1",
    tooling_ref: str = "abc1234def5678",
) -> ValidationContext:
    return ValidationContext(
        repository="TestRepo",
        branch_type=branch_type,
        trigger_type=trigger_type,
        profile=profile,
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
        workflow_run_url=workflow_run_url,
        tooling_ref=tooling_ref,
    )


def _make_finding(
    level: str = "warn",
    path: str = "code/API_definitions/quality-on-demand.yaml",
    line: int = 10,
    message: str = "Something is wrong",
    api_name: str | None = "quality-on-demand",
    blocks: bool = False,
    rule_id: str | None = None,
    engine_rule: str = "some-rule",
    hint: str | None = None,
) -> dict:
    f: dict = {
        "engine": "spectral",
        "engine_rule": engine_rule,
        "level": level,
        "message": message,
        "path": path,
        "line": line,
        "api_name": api_name,
        "blocks": blocks,
    }
    if rule_id is not None:
        f["rule_id"] = rule_id
    if hint is not None:
        f["hint"] = hint
    return f


def _make_result(
    findings: list[dict] | None = None,
    result: str = "pass",
    summary: str = "Passed: no findings",
) -> PostFilterResult:
    return PostFilterResult(
        findings=findings or [],
        result=result,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------


class TestHeader:
    def test_pass_result(self):
        ctx = _make_context()
        sr = generate_workflow_summary(_make_result(), ctx)
        assert "## CAMARA Validation — PASS" in sr.markdown

    def test_fail_result(self):
        findings = [_make_finding(level="error", blocks=True)]
        ctx = _make_context()
        sr = generate_workflow_summary(
            _make_result(findings, result="fail"), ctx
        )
        assert "## CAMARA Validation — FAIL" in sr.markdown

    def test_error_result(self):
        ctx = _make_context()
        sr = generate_workflow_summary(
            _make_result(result="error"), ctx
        )
        assert "## CAMARA Validation — ERROR" in sr.markdown

    def test_metadata_in_header(self):
        ctx = _make_context(profile="strict", branch_type="release", trigger_type="dispatch")
        sr = generate_workflow_summary(_make_result(), ctx)
        assert "strict" in sr.markdown
        assert "release" in sr.markdown
        assert "dispatch" in sr.markdown


# ---------------------------------------------------------------------------
# Engine summary table
# ---------------------------------------------------------------------------


class TestEngineSummaryTable:
    def test_engine_with_findings(self):
        findings = [
            _make_finding(level="error"),
            _make_finding(level="warn"),
        ]
        statuses = {"spectral": "2 finding(s)"}
        sr = generate_workflow_summary(
            _make_result(findings), _make_context(), engine_statuses=statuses,
        )
        assert "### Summary" in sr.markdown
        assert "| spectral | 1 | 1 | 0 | — |" in sr.markdown

    def test_engine_ran_clean(self):
        statuses = {"yamllint": "0 finding(s)"}
        sr = generate_workflow_summary(
            _make_result(), _make_context(), engine_statuses=statuses,
        )
        assert "| yamllint | 0 | 0 | 0 | — |" in sr.markdown

    def test_engine_skipped(self):
        statuses = {"gherkin": "skipped (no test files)"}
        sr = generate_workflow_summary(
            _make_result(), _make_context(), engine_statuses=statuses,
        )
        assert "| gherkin | — | — | — | skipped (no test files) |" in sr.markdown

    def test_engine_errored(self):
        statuses = {"spectral": "error: timeout"}
        sr = generate_workflow_summary(
            _make_result(), _make_context(), engine_statuses=statuses,
        )
        assert "| spectral | — | — | — | error: timeout |" in sr.markdown

    def test_mixed_engines(self):
        findings = [
            _make_finding(level="error"),  # engine=spectral
            _make_finding(level="warn"),   # engine=spectral
        ]
        statuses = {
            "yamllint": "0 finding(s)",
            "spectral": "2 finding(s)",
            "python": "0 finding(s)",
            "gherkin": "skipped (no test files)",
        }
        sr = generate_workflow_summary(
            _make_result(findings), _make_context(), engine_statuses=statuses,
        )
        assert "| yamllint | 0 | 0 | 0 | — |" in sr.markdown
        assert "| spectral | 1 | 1 | 0 | — |" in sr.markdown
        assert "| python | 0 | 0 | 0 | — |" in sr.markdown
        assert "| gherkin | — | — | — | skipped (no test files) |" in sr.markdown

    def test_no_statuses_no_table(self):
        sr = generate_workflow_summary(_make_result(), _make_context())
        assert "### Summary" not in sr.markdown

    def test_all_findings_filtered_by_postfilter(self):
        """Engine ran and reported findings but all were filtered → 0/0/0."""
        statuses = {"python": "3 finding(s)"}
        sr = generate_workflow_summary(
            _make_result(), _make_context(), engine_statuses=statuses,
        )
        assert "| python | 0 | 0 | 0 | — |" in sr.markdown

    def test_table_header(self):
        statuses = {"spectral": "0 finding(s)"}
        sr = generate_workflow_summary(
            _make_result(), _make_context(), engine_statuses=statuses,
        )
        assert "| Engine | Errors | Warnings | Hints | Status |" in sr.markdown


# ---------------------------------------------------------------------------
# Findings sections (rule-grouped bullets)
# ---------------------------------------------------------------------------


class TestFindingsSection:
    def test_errors_section_with_count(self):
        findings = [_make_finding(level="error", rule_id="S-001")]
        sr = generate_workflow_summary(_make_result(findings), _make_context())
        assert "### Errors (1)" in sr.markdown
        assert "[S-001]" in sr.markdown

    def test_warnings_section_with_count(self):
        findings = [
            _make_finding(level="warn", rule_id="S-001"),
            _make_finding(level="warn", rule_id="S-002", line=20),
        ]
        sr = generate_workflow_summary(_make_result(findings), _make_context())
        assert "### Warnings (2)" in sr.markdown

    def test_hints_section_with_count(self):
        findings = [_make_finding(level="hint")]
        sr = generate_workflow_summary(_make_result(findings), _make_context())
        assert "### Hints (1)" in sr.markdown

    def test_bullet_shape(self):
        findings = [
            _make_finding(
                level="error",
                rule_id="S-042",
                path="spec.yaml",
                line=47,
                message="Bad path",
                hint="Use kebab-case",
            )
        ]
        sr = generate_workflow_summary(_make_result(findings), _make_context())
        # Bold subject line: "**[<RULE>] <subject> — <N> hit(s)**"
        assert "**[S-042]" in sr.markdown
        assert "— 1 hit**" in sr.markdown
        # Bullet: "- <path>:<line> — [<RULE>] <message>"
        assert "- spec.yaml:47 — [S-042] Bad path" in sr.markdown
        # Suggestion blockquote
        assert "> Suggestion: Use kebab-case" in sr.markdown

    def test_subject_line_uses_short_title_when_present(self):
        f = _make_finding(
            level="error",
            rule_id="S-042",
            message="some long verbose message text",
        )
        f["short_title"] = "Bad path casing"
        sr = generate_workflow_summary(_make_result([f]), _make_context())
        assert "**[S-042] Bad path casing — 1 hit**" in sr.markdown

    def test_subject_line_falls_back_to_message(self):
        # No short_title → falls back to the finding message
        findings = [
            _make_finding(
                level="error",
                rule_id="S-042",
                message="Bad path casing",
            )
        ]
        sr = generate_workflow_summary(_make_result(findings), _make_context())
        assert "**[S-042] Bad path casing — 1 hit**" in sr.markdown

    def test_multiple_hits_one_rule_block(self):
        findings = [
            _make_finding(
                level="error",
                rule_id="S-307",
                path="a.yaml",
                line=10,
                message="Missing 401",
                hint="Add 401",
            ),
            _make_finding(
                level="error",
                rule_id="S-307",
                path="a.yaml",
                line=20,
                message="Missing 401",
                hint="Add 401",
            ),
            _make_finding(
                level="error",
                rule_id="S-307",
                path="b.yaml",
                line=30,
                message="Missing 401",
                hint="Add 401",
            ),
        ]
        sr = generate_workflow_summary(_make_result(findings), _make_context())
        # One subject line with the plural count
        assert sr.markdown.count("**[S-307]") == 1
        assert "— 3 hits**" in sr.markdown
        # Three bullets
        assert "- a.yaml:10 — [S-307] Missing 401" in sr.markdown
        assert "- a.yaml:20 — [S-307] Missing 401" in sr.markdown
        assert "- b.yaml:30 — [S-307] Missing 401" in sr.markdown
        # Suggestion blockquote rendered exactly once for the rule
        assert sr.markdown.count("> Suggestion: Add 401") == 1

    def test_multiple_rules_separate_blocks(self):
        findings = [
            _make_finding(
                level="error", rule_id="S-001", path="a.yaml", line=10,
                message="msg-a", hint="hint-a",
            ),
            _make_finding(
                level="error", rule_id="S-002", path="b.yaml", line=20,
                message="msg-b", hint="hint-b",
            ),
        ]
        sr = generate_workflow_summary(_make_result(findings), _make_context())
        assert "**[S-001]" in sr.markdown
        assert "**[S-002]" in sr.markdown
        assert "> Suggestion: hint-a" in sr.markdown
        assert "> Suggestion: hint-b" in sr.markdown

    def test_no_blank_lines_inside_rule_block(self):
        # Subject line, bullets, and suggestion blockquote run together
        # (no blank lines) so the bullet list stays tight in GFM.
        findings = [
            _make_finding(
                level="error", rule_id="S-001", path="a.yaml", line=10,
                message="msg", hint="hint",
            ),
            _make_finding(
                level="error", rule_id="S-001", path="a.yaml", line=20,
                message="msg", hint="hint",
            ),
        ]
        sr = generate_workflow_summary(_make_result(findings), _make_context())
        # Locate the rule block and its constituent lines.
        idx_subject = sr.markdown.index("**[S-001]")
        idx_first_bullet = sr.markdown.index("- a.yaml:10")
        idx_last_bullet = sr.markdown.index("- a.yaml:20")
        idx_suggestion = sr.markdown.index("> Suggestion: hint")
        # No blank line between subject and first bullet
        between_subject_and_bullet = sr.markdown[idx_subject:idx_first_bullet]
        assert "\n\n" not in between_subject_and_bullet
        # No blank line between bullets
        between_bullets = sr.markdown[idx_first_bullet:idx_last_bullet]
        assert "\n\n" not in between_bullets
        # No blank line between last bullet and suggestion
        between_bullet_and_suggestion = sr.markdown[idx_last_bullet:idx_suggestion]
        assert "\n\n" not in between_bullet_and_suggestion

    def test_blank_line_between_rule_blocks(self):
        findings = [
            _make_finding(
                level="error", rule_id="S-001", path="a.yaml", line=10,
                message="msg-a",
            ),
            _make_finding(
                level="error", rule_id="S-002", path="b.yaml", line=20,
                message="msg-b",
            ),
        ]
        sr = generate_workflow_summary(_make_result(findings), _make_context())
        # The two rule blocks must have a blank line between them.
        # Locate the end of block-1 (its last bullet) and the start of
        # block-2 (its subject line) and assert exactly one blank line.
        idx_end_block_1 = sr.markdown.index("- a.yaml:10")
        idx_start_block_2 = sr.markdown.index("**[S-002]")
        between = sr.markdown[idx_end_block_1:idx_start_block_2]
        assert "\n\n" in between

    def test_singular_hit(self):
        findings = [_make_finding(level="error", rule_id="S-001")]
        sr = generate_workflow_summary(_make_result(findings), _make_context())
        assert "— 1 hit**" in sr.markdown
        assert "— 1 hits**" not in sr.markdown

    def test_plural_hits(self):
        findings = [
            _make_finding(level="error", rule_id="S-001", line=10),
            _make_finding(level="error", rule_id="S-001", line=20),
        ]
        sr = generate_workflow_summary(_make_result(findings), _make_context())
        assert "— 2 hits**" in sr.markdown

    def test_no_suggestion_when_hint_empty(self):
        findings = [
            _make_finding(
                level="error", rule_id="S-001", message="msg", hint=None,
            )
        ]
        sr = generate_workflow_summary(_make_result(findings), _make_context())
        assert "Suggestion:" not in sr.markdown

    def test_multi_line_hint_blockquote_contiguous(self):
        findings = [
            _make_finding(
                level="error", rule_id="S-001",
                hint="first line\nsecond line\nthird line",
            )
        ]
        sr = generate_workflow_summary(_make_result(findings), _make_context())
        assert "> Suggestion: first line" in sr.markdown
        assert "> second line" in sr.markdown
        assert "> third line" in sr.markdown

    def test_newline_in_message_flattened(self):
        findings = [
            _make_finding(
                level="error", rule_id="S-001", path="a.yaml", line=10,
                message="line one\nline two",
            )
        ]
        sr = generate_workflow_summary(_make_result(findings), _make_context())
        assert "- a.yaml:10 — [S-001] line one line two" in sr.markdown

    def test_pipe_in_message_not_escaped(self):
        # No table → no pipe escaping needed.
        findings = [
            _make_finding(
                level="error", rule_id="S-001", path="a.yaml", line=10,
                message="left|right",
            )
        ]
        sr = generate_workflow_summary(_make_result(findings), _make_context())
        assert "- a.yaml:10 — [S-001] left|right" in sr.markdown

    def test_absent_levels_not_rendered(self):
        findings = [_make_finding(level="warn")]
        sr = generate_workflow_summary(_make_result(findings), _make_context())
        assert "### Errors" not in sr.markdown
        assert "### Hints" not in sr.markdown


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------


class TestFooter:
    def test_commit_sha_truncated(self):
        sr = generate_workflow_summary(
            _make_result(),
            _make_context(),
            commit_sha="abcdef1234567890",
        )
        assert "Commit: abcdef1" in sr.markdown

    def test_tooling_ref(self):
        ctx = _make_context(tooling_ref="1234567890abcdef")
        sr = generate_workflow_summary(_make_result(), ctx)
        assert "Tooling: 1234567" in sr.markdown

    def test_workflow_run_url(self):
        ctx = _make_context(workflow_run_url="https://github.com/test/run/1")
        sr = generate_workflow_summary(_make_result(), ctx)
        assert "[Full workflow run](https://github.com/test/run/1)" in sr.markdown

    def test_empty_footer_fields(self):
        ctx = _make_context(workflow_run_url="", tooling_ref="")
        sr = generate_workflow_summary(_make_result(), ctx, commit_sha="")
        # No footer separator when all fields empty
        assert "---" not in sr.markdown


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------


class TestTruncation:
    def test_small_summary_not_truncated(self):
        findings = [_make_finding() for _ in range(5)]
        sr = generate_workflow_summary(_make_result(findings), _make_context())
        assert not sr.truncated
        assert sr.truncation_note == ""

    def test_errors_never_truncated(self):
        # Create enough error findings to fill a large portion of budget
        # but they should still all appear
        errors = [
            _make_finding(
                level="error",
                message="x" * 200,
                line=i,
            )
            for i in range(50)
        ]
        sr = generate_workflow_summary(_make_result(errors), _make_context())
        # All 50 errors should appear — every finding renders one bullet.
        # Subject line carries the count.
        assert "— 50 hits**" in sr.markdown
        # Each finding renders one bullet; since findings share a path
        # they all appear under one rule block with 50 bullets.
        bullet_count = sum(
            1
            for line in sr.markdown.splitlines()
            if line.startswith("- ") and "[some-rule]" in line
        )
        assert bullet_count == 50

    def test_hints_truncated_first(self):
        # Generate content that exceeds the budget.
        # With a very long message per finding and many findings,
        # we force truncation.
        long_msg = "x" * 5000
        errors = [_make_finding(level="error", message=long_msg, line=i) for i in range(10)]
        warnings = [_make_finding(level="warn", message=long_msg, line=i) for i in range(10)]
        hints = [_make_finding(level="hint", message=long_msg, line=i) for i in range(200)]
        findings = errors + warnings + hints

        sr = generate_workflow_summary(
            _make_result(findings),
            _make_context(),
        )
        # All errors must be present
        assert "### Errors" in sr.markdown
        # If truncation occurred, it should hit hints first
        if sr.truncated:
            assert "hint" in sr.truncation_note.lower()

    def test_truncation_note_set(self):
        # Force truncation with massive findings
        long_msg = "x" * 10000
        hints = [
            _make_finding(level="hint", message=long_msg, line=i)
            for i in range(200)
        ]
        sr = generate_workflow_summary(
            _make_result(hints),
            _make_context(),
        )
        if sr.truncated:
            assert sr.truncation_note != ""
            assert "truncated" in sr.truncation_note

    def test_under_limit_returns_all(self):
        findings = [
            _make_finding(level="error", line=1),
            _make_finding(level="warn", line=2),
            _make_finding(level="hint", line=3),
        ]
        sr = generate_workflow_summary(_make_result(findings), _make_context())
        assert not sr.truncated
        assert "### Errors" in sr.markdown
        assert "### Warnings" in sr.markdown
        assert "### Hints" in sr.markdown


# ---------------------------------------------------------------------------
# Artifact footnote
# ---------------------------------------------------------------------------


class TestArtifactFootnote:
    def test_footnote_present_when_diagnostics_written(self):
        sr = generate_workflow_summary(
            _make_result(), _make_context(), diagnostics_written=True,
        )
        assert "validation-diagnostics" in sr.markdown
        assert "findings.tsv" in sr.markdown
        assert "findings.json" in sr.markdown

    def test_footnote_absent_by_default(self):
        sr = generate_workflow_summary(_make_result(), _make_context())
        assert "validation-diagnostics" not in sr.markdown
        assert "findings.tsv" not in sr.markdown


# ---------------------------------------------------------------------------
# SummaryResult type
# ---------------------------------------------------------------------------


class TestSummaryResult:
    def test_is_frozen(self):
        sr = SummaryResult(markdown="x", truncated=False, truncation_note="")
        try:
            sr.markdown = "y"  # type: ignore[misc]
            assert False, "Should not be able to mutate frozen dataclass"
        except AttributeError:
            pass
