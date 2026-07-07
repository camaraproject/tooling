"""Test file checks.

Validates that test files exist for each API, are located in
``code/Test_definitions/``, and carry version-aligned Feature lines.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from validation.context import ValidationContext

from ._types import make_finding

_TEST_DIR = "code/Test_definitions"


def _stem_anchors_api(stem: str, api_name: str) -> bool:
    """Check if a test file stem is anchored on an API name.

    Anchored forms:
    - Exact: ``{api-name}``
    - With version: ``{api-name}.{version}``
    - With suffix: ``{api-name}-{suffix}``
    - With suffix + version: ``{api-name}-{suffix}.{version}``
    """
    if stem == api_name:
        return True
    if stem.startswith(f"{api_name}."):
        return True
    if stem.startswith(f"{api_name}-"):
        return True
    return False


def _stem_matches_api(
    stem: str, api_name: str, all_api_names: Sequence[str] = ()
) -> bool:
    """Check if a test file stem belongs to ``api_name``.

    A stem belongs to ``api_name`` when it is anchored on it AND no *longer*
    API name in ``all_api_names`` is also anchored on the same stem — the
    longest matching API name wins.  This disambiguates sibling APIs whose
    names share a prefix: ``dedicated-network-areas.feature`` belongs to
    ``dedicated-network-areas``, not to its prefix sibling
    ``dedicated-network`` (tooling#365).

    ``all_api_names`` is the full release-scope API-name set (see
    ``ValidationContext.all_api_names``); it survives the per-API narrowing
    in ``python_adapter``.  When empty (e.g. a single-API repo), the check
    degrades to a plain anchor match.  A ``{api-name}-{suffix}`` file whose
    suffix is not itself an API name (a per-operation split) still matches
    its base API, since no longer API name is anchored on it.
    """
    if not _stem_anchors_api(stem, api_name):
        return False
    return not any(
        other != api_name
        and len(other) > len(api_name)
        and _stem_anchors_api(stem, other)
        for other in all_api_names
    )


def check_test_directory_exists(
    repo_path: Path, context: ValidationContext
) -> List[dict]:
    """Verify ``code/Test_definitions/`` exists when APIs are present.

    Repo-level check — runs once, not per-API.
    """
    if not context.apis:
        return []

    test_dir = repo_path / _TEST_DIR
    if test_dir.is_dir():
        return []

    return [
        make_finding(
            engine_rule="check-test-directory-exists",
            level="error",
            message=(
                f"Directory '{_TEST_DIR}/' is missing — "
                f"test definitions are required when API specs are present"
            ),
            path=_TEST_DIR,
            line=1,
        )
    ]


def check_test_files_exist(
    repo_path: Path, context: ValidationContext
) -> List[dict]:
    """Verify at least one ``.feature`` file exists for the API.

    Per-API check.  Looks for files matching the api-name prefix in
    ``code/Test_definitions/``.
    """
    api = context.apis[0]
    test_dir = repo_path / _TEST_DIR

    if not test_dir.is_dir():
        # Directory-level check reports this; avoid duplicate findings.
        return []

    # Match files starting with the api-name.
    # Patterns: {api-name}.feature, {api-name}.{version}.feature,
    #           {api-name}-{suffix}.feature, {api-name}-{suffix}.{version}.feature
    matching = [
        f for f in test_dir.iterdir()
        if f.is_file()
        and f.suffix == ".feature"
        and _stem_matches_api(f.stem, api.api_name, context.all_api_names)
    ]

    if matching:
        return []

    return [
        make_finding(
            engine_rule="check-test-files-exist",
            level="error",
            message=(
                f"No .feature test file found for API '{api.api_name}' "
                f"in {_TEST_DIR}/"
            ),
            path=_TEST_DIR,
            line=1,
            api_name=api.api_name,
        )
    ]


# Regex to extract version from CAMARA Feature line. Aligned with the T1b
# transformation pattern in release_automation/config/transformations.yaml
# so that any line T1b can transform is also recognized here. The leading
# ``\s`` separator accepts both the comma-and-space form ("Feature: X, vwip")
# and the space-only form ("Feature: X vwip"). The captured token is
# ``wip`` / ``vwip`` (style variation on main/maintenance) or ``v{semver}``
# (release branches).
# Examples:
#   "Feature: CAMARA QoD API, vwip - Operation deleteSession"       → "vwip"
#   "Feature: CAMARA QoD API, wip - Operation deleteSession"        → "wip"
#   "Feature: CAMARA QoD API vwip - Operation deleteSession"        → "vwip"
#   "Feature: CAMARA QoD API, v2.2.0-alpha.5 - Operation create"    → "v2.2.0-alpha.5"
#   "Feature: CAMARA QoD API, v1.0.0"                               → "v1.0.0"
_FEATURE_VERSION_RE = re.compile(r"\s(v?wip|v\S+?)(?:\s+-\s|\s*$)")

# Match a Gherkin Feature line, allowing the leading whitespace that some
# files use. Comment lines (``#``), tag lines (``@…``), and blank lines
# preceding the Feature line are valid Gherkin and are skipped during the
# scan.
_FEATURE_LINE_RE = re.compile(r"^\s*Feature\s*:")

# Cap the Feature-line scan to bound work on pathological inputs. Real-world
# preambles (comment + tag + blanks) are at most a handful of lines.
_FEATURE_LINE_SCAN_CAP = 50


def _extract_feature_version(
    file_path: Path,
) -> Tuple[Optional[str], Optional[int]]:
    """Locate the Feature line and extract the version segment.

    Scans the first ``_FEATURE_LINE_SCAN_CAP`` lines for a line beginning
    with ``Feature:`` (skipping preceding comment, tag, and blank lines —
    all valid Gherkin) and applies the version regex to that line.

    Returns ``(version, line_number)`` when a Feature line is found and
    the version regex matches; ``(None, line_number)`` when the Feature
    line is found but carries no recognizable version token; and
    ``(None, None)`` when no Feature line is present in the scan window.
    """
    try:
        with open(file_path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                if lineno > _FEATURE_LINE_SCAN_CAP:
                    break
                if _FEATURE_LINE_RE.match(line):
                    m = _FEATURE_VERSION_RE.search(line.rstrip())
                    return (m.group(1) if m else None), lineno
    except (OSError, UnicodeDecodeError):
        pass
    return None, None


def check_test_file_version(
    repo_path: Path, context: ValidationContext
) -> List[dict]:
    """Validate that the version in test Feature lines matches the branch.

    Per-API check.  On main and maintenance the Feature line must carry
    ``vwip``.  On release branches it must match the version derived
    from ``target_api_version`` (sourced from release-metadata.yaml).
    Feature branches are skipped.

    This avoids cascading with P-003 (info.version format): on
    main/maintenance the expected value is hardcoded, not derived from
    the spec.

    Example Feature line::

        Feature: CAMARA Quality On Demand API, vwip - Operation deleteSession
    """
    api = context.apis[0]
    test_dir = repo_path / _TEST_DIR

    if not test_dir.is_dir():
        return []

    if context.branch_type in ("main", "maintenance"):
        expected_segment = "vwip"
    elif context.branch_type == "release":
        # Snapshot transformer T1b produces "v{api_version}" in Feature
        # lines.  api.target_api_version holds the full calculated
        # version (incl. pre-release extension) from release-metadata.
        expected_segment = f"v{api.target_api_version}"
    else:
        # Feature branches: no constraint.
        return []

    # Find all .feature files matching this API.
    matching = [
        f for f in test_dir.iterdir()
        if f.is_file()
        and f.suffix == ".feature"
        and _stem_matches_api(f.stem, api.api_name, context.all_api_names)
    ]

    if not matching:
        # No test files found — check_test_files_exist reports this.
        return []

    # Compare with leading-v stripped so bare "wip" and "vwip" are treated
    # as equivalent on main/maintenance (a style variation, parallel to
    # "0.1.0" vs "v0.1.0" in info.version). Release branches always carry
    # T1b's "v{api_version}" output, so the normalized comparison still
    # enforces an exact match there.
    expected_token = expected_segment.lower().removeprefix("v")

    findings: List[dict] = []
    for test_file in matching:
        actual_version, feature_lineno = _extract_feature_version(test_file)

        if feature_lineno is None:
            # No Feature line found in the scan window — emitted under
            # P-024 so its severity cannot be masked by P-007's
            # conditional_level.
            findings.append(
                make_finding(
                    engine_rule="check-test-file-feature-line-untransformable",
                    level="error",
                    message=(
                        f"Test file '{test_file.name}' has no 'Feature:' "
                        f"line in the first {_FEATURE_LINE_SCAN_CAP} lines "
                        f"(expected '{expected_segment}')"
                    ),
                    path=f"{_TEST_DIR}/{test_file.name}",
                    line=1,
                    api_name=api.api_name,
                )
            )
            continue

        if actual_version is None:
            # Feature line found but no recognizable version token. Same
            # P-024 rule, distinct message — points at the actual line.
            findings.append(
                make_finding(
                    engine_rule="check-test-file-feature-line-untransformable",
                    level="error",
                    message=(
                        f"Test file '{test_file.name}' Feature line has no "
                        f"'wip', 'vwip', or 'v{{version}}' token "
                        f"(expected '{expected_segment}')"
                    ),
                    path=f"{_TEST_DIR}/{test_file.name}",
                    line=feature_lineno,
                    api_name=api.api_name,
                )
            )
            continue

        actual_token = actual_version.lower().removeprefix("v")
        if actual_token != expected_token:
            findings.append(
                make_finding(
                    engine_rule="check-test-file-version",
                    level="error",
                    message=(
                        f"Test file '{test_file.name}' has version "
                        f"'{actual_version}' in Feature line but expected "
                        f"'{expected_segment}' "
                        f"(on {context.branch_type} branch)"
                    ),
                    path=f"{_TEST_DIR}/{test_file.name}",
                    line=feature_lineno,
                    api_name=api.api_name,
                )
            )

    return findings
