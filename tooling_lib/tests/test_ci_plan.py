"""Tests for Tooling CI path gating."""

from __future__ import annotations

from tooling_lib.ci_plan import ToolingCiPlan, plan_for_changed_files


def test_docs_only_change_skips_heavy_checks():
    assert plan_for_changed_files(["documentation/README.md"]) == ToolingCiPlan(
        npm=False,
        javascript=False,
        validation=False,
        release_automation=False,
    )


def test_workflow_change_runs_all_gated_checks():
    assert plan_for_changed_files([".github/workflows/tooling-ci.yml"]) == ToolingCiPlan(
        npm=True,
        javascript=True,
        validation=True,
        release_automation=True,
    )


def test_validation_lockfile_change_runs_npm_and_validation_tests():
    assert plan_for_changed_files(["validation/package-lock.json"]) == ToolingCiPlan(
        npm=True,
        javascript=False,
        validation=True,
        release_automation=False,
    )


def test_validation_shared_action_runs_validation_and_release_automation_tests():
    assert plan_for_changed_files(["shared-actions/run-validation/action.yml"]) == ToolingCiPlan(
        npm=False,
        javascript=False,
        validation=True,
        release_automation=True,
    )


def test_release_plan_shared_action_runs_validation_tests():
    assert plan_for_changed_files(
        ["shared-actions/validate-release-plan/action.yml"]
    ) == ToolingCiPlan(
        npm=False,
        javascript=False,
        validation=True,
        release_automation=False,
    )


def test_release_automation_shared_action_runs_release_automation_tests():
    assert plan_for_changed_files(["shared-actions/create-snapshot/action.yml"]) == ToolingCiPlan(
        npm=False,
        javascript=False,
        validation=False,
        release_automation=True,
    )


def test_tooling_lib_change_runs_both_python_suites():
    assert plan_for_changed_files(["tooling_lib/cache_sync.py"]) == ToolingCiPlan(
        npm=False,
        javascript=False,
        validation=True,
        release_automation=True,
    )


def test_workflow_dispatch_sentinel_runs_all_gated_checks():
    assert plan_for_changed_files(["__all__"]) == ToolingCiPlan(
        npm=True,
        javascript=True,
        validation=True,
        release_automation=True,
    )


def test_lint_function_change_runs_javascript_and_validation_tests():
    assert plan_for_changed_files(
        ["linting/config/lint_function/camara-reserved-words.js"]
    ) == ToolingCiPlan(
        npm=False,
        javascript=True,
        validation=True,
        release_automation=False,
    )
