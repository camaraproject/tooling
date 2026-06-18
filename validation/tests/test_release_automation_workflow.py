"""Static checks for release automation workflow wiring."""

from __future__ import annotations

from pathlib import Path

import yaml


WORKFLOW = (
    Path(__file__).resolve().parents[2]
    / ".github"
    / "workflows"
    / "release-automation-reusable.yml"
)


def _create_snapshot_steps() -> list[dict]:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]["create-snapshot"]["steps"]


def _step_by_name(steps: list[dict], name: str) -> dict:
    for step in steps:
        if step.get("name") == name:
            return step
    raise AssertionError(f"step not found: {name}")


def test_create_snapshot_passes_release_history_to_pre_snapshot_validation():
    steps = _create_snapshot_steps()
    names = [step.get("name") for step in steps]

    assert "Resolve published release history" in names
    assert names.index("Resolve published release history") < names.index(
        "Run pre-snapshot validation"
    )

    resolver = _step_by_name(steps, "Resolve published release history")
    assert resolver["id"] == "release-history"
    assert "GH_TOKEN" in resolver["env"]
    assert "_tooling/validation/scripts/resolve-release-history.py" in resolver["run"]
    assert '--repo "${{ github.repository }}"' in resolver["run"]
    assert '--output "${RUNNER_TEMP}/release-history.json"' in resolver["run"]

    validation = _step_by_name(steps, "Run pre-snapshot validation")
    assert validation["with"]["release_history_path"] == (
        "${{ steps.release-history.outputs.release_history_path || '' }}"
    )
