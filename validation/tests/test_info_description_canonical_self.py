"""Self-test for the Commonalities canonical ``info-description-templates.yaml``.

Validates that every entry in the canonical file wraps its ``content`` with a
matching ``<!-- CAMARA:MANDATORY:<key>:BEGIN -->`` / ``:END -->`` pair where
the template name in the markers matches the top-level YAML key.  Guards
against accidental marker corruption in future Commonalities edits — the rule
implementation relies on this invariant being upheld.

Skipped when the upstream Commonalities mirror is not present, so developer
environments without the workspace's full mirror can still run the test suite.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
import yaml


_MARKER_BEGIN_RE = re.compile(
    r"<!--\s*CAMARA:MANDATORY:([a-z][a-z0-9-]*):BEGIN\s*-->"
)
_MARKER_END_RE = re.compile(
    r"<!--\s*CAMARA:MANDATORY:([a-z][a-z0-9-]*):END\s*-->"
)


def _template_entries(canonical: dict) -> dict[str, dict]:
    """Return only canonical entries that carry mandatory template content."""
    return {
        name: entry
        for name, entry in canonical.items()
        if isinstance(entry, dict) and isinstance(entry.get("content"), str)
    }


def _resolve_canonical_path() -> Path | None:
    """Locate ``artifacts/common/info-description-templates.yaml`` in the workspace.

    Honours ``CAMARA_WORKSPACE_ROOT`` when set; falls back to walking up from
    this test file looking for ``upstream/traversals/Commonalities/``.
    """
    env_root = os.environ.get("CAMARA_WORKSPACE_ROOT")
    candidates: list[Path] = []
    if env_root:
        candidates.append(
            Path(env_root)
            / "upstream/traversals/Commonalities/artifacts/common/info-description-templates.yaml"
        )

    # Walk up from this test file looking for a `upstream/traversals/Commonalities`
    # sibling — handles running from a worktree under `worktrees/tooling/...`.
    cursor = Path(__file__).resolve()
    for _ in range(8):
        cursor = cursor.parent
        guess = (
            cursor
            / "upstream/traversals/Commonalities/artifacts/common/info-description-templates.yaml"
        )
        candidates.append(guess)

    for path in candidates:
        if path.is_file():
            return path
    return None


_CANONICAL_PATH = _resolve_canonical_path()


@pytest.mark.skipif(
    _CANONICAL_PATH is None,
    reason=(
        "Commonalities upstream mirror not present "
        "(set CAMARA_WORKSPACE_ROOT or check out the workspace)"
    ),
)
class TestInfoDescriptionTemplatesCanonical:
    """Invariants on ``artifacts/common/info-description-templates.yaml``."""

    @pytest.fixture(scope="class")
    def canonical(self) -> dict:
        assert _CANONICAL_PATH is not None
        data = yaml.safe_load(_CANONICAL_PATH.read_text(encoding="utf-8"))
        assert isinstance(data, dict), "canonical file root must be a mapping"
        return data

    def test_every_entry_has_content_field(self, canonical: dict) -> None:
        templates = _template_entries(canonical)
        assert templates, "canonical file must contain template entries"
        for name, entry in templates.items():
            assert isinstance(entry, dict), (
                f"template {name!r} is not a mapping"
            )
            assert isinstance(entry.get("content"), str), (
                f"template {name!r} missing string `content` field"
            )

    def test_markers_match_key_and_appear_once(self, canonical: dict) -> None:
        for name, entry in _template_entries(canonical).items():
            content = entry["content"]
            begins = _MARKER_BEGIN_RE.findall(content)
            ends = _MARKER_END_RE.findall(content)
            assert begins == [name], (
                f"template {name!r}: BEGIN markers {begins!r} do not match "
                f"single canonical name {name!r}"
            )
            assert ends == [name], (
                f"template {name!r}: END markers {ends!r} do not match "
                f"single canonical name {name!r}"
            )

    def test_begin_precedes_end(self, canonical: dict) -> None:
        for name, entry in _template_entries(canonical).items():
            content = entry["content"]
            begin_match = _MARKER_BEGIN_RE.search(content)
            end_match = _MARKER_END_RE.search(content)
            assert begin_match is not None and end_match is not None
            assert begin_match.start() < end_match.start(), (
                f"template {name!r}: BEGIN marker appears after END marker"
            )

    def test_expected_universal_templates_present(self, canonical: dict) -> None:
        """The three universal templates must exist in the canonical file."""
        required = {
            "authorization-and-authentication",
            "additional-error-responses",
            "request-body-strictness",
        }
        missing = required - set(canonical.keys())
        assert not missing, f"canonical file missing universal templates: {missing}"
