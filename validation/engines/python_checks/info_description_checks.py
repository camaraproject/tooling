"""Mandatory ``info.description`` content validation (P-026..P-031).

Enforces the BEGIN/END marker mechanism described in
``validation/docs/CAMARA-Validation-Framework-Info-Description-Design.md``.

A canonical YAML file ``code/common/info-description-templates.yaml`` (synced
from Commonalities by the cache-common feature) declares, per template name,
the mandatory text that an API spec MUST embed verbatim between
``<!-- CAMARA:MANDATORY:<template-name>:BEGIN -->`` and
``<!-- CAMARA:MANDATORY:<template-name>:END -->`` markers inside its
``info.description``.

A single function emits findings under six distinct ``engine_rule`` values:

* ``check-info-description-mandatory-missing`` (P-026, universal templates only)
* ``check-info-description-mandatory-drift`` (P-027)
* ``check-info-description-mandatory-duplicate`` (P-028)
* ``check-info-description-mandatory-unknown-template-name`` (P-029)
* ``check-info-description-folded-scalar`` (P-030)
* ``check-info-description-canonical-missing`` (P-031)

Only the first is registered as a :class:`CheckDescriptor` — the others are
satellite ``engine_rule`` values that the post-filter maps to their own
metadata entries.  Same pattern as the P-007 / P-024 split in
``test_checks.py``.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from validation.context import ValidationContext

from ._types import make_finding

logger = logging.getLogger(__name__)


_CANONICAL_REL_PATH = "code/common/info-description-templates.yaml"

# Universal templates: a finding fires when any of these is absent from
# info.description.  The two Appendix A templates are opt-in (codeowner
# judgement of the auth model) and absence is not a finding.
_UNIVERSAL_TEMPLATES = frozenset(
    {
        "authorization-and-authentication",
        "additional-error-responses",
        "request-body-strictness",
    }
)

# A marker line.  Group 1 is the template name (kebab-case), group 2 the
# BEGIN/END side.  Tolerant of internal whitespace inside the comment.
_MARKER_RE = re.compile(
    r"<!--\s*CAMARA:MANDATORY:([a-z][a-z0-9-]*):(BEGIN|END)\s*-->"
)

# engine_rule values emitted by this module.
_RULE_MISSING = "check-info-description-mandatory-missing"
_RULE_DRIFT = "check-info-description-mandatory-drift"
_RULE_DUPLICATE = "check-info-description-mandatory-duplicate"
_RULE_UNKNOWN = "check-info-description-mandatory-unknown-template-name"
_RULE_FOLDED = "check-info-description-folded-scalar"
_RULE_CANONICAL_MISSING = "check-info-description-canonical-missing"


# ---------------------------------------------------------------------------
# Canonical loading
# ---------------------------------------------------------------------------


# Cache: { canonical_path: (mtime_ns, {template_name: [normalised_paragraph, ...]}) }
_canonical_cache: Dict[Path, Tuple[int, Dict[str, List[str]]]] = {}


def _load_canonical(repo_path: Path) -> Optional[Dict[str, List[str]]]:
    """Load and paragraph-normalise the canonical templates.

    Returns ``{template_name: [normalised_paragraph, ...]}`` or ``None`` if
    the canonical file does not exist (e.g. r4.2 repo, or a release-review
    branch after the snapshot bundling step has cleared ``code/common/``).

    Cached by (path, mtime_ns) so the file is read at most once per
    validation run regardless of how many specs the repo contains.
    """
    canonical_path = (repo_path / _CANONICAL_REL_PATH).resolve()
    try:
        mtime = canonical_path.stat().st_mtime_ns
    except FileNotFoundError:
        return None

    cached = _canonical_cache.get(canonical_path)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    try:
        data = yaml.safe_load(canonical_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        logger.warning(
            "Canonical templates file is not valid YAML: %s", canonical_path
        )
        return None

    if not isinstance(data, dict):
        return None

    result: Dict[str, List[str]] = {}
    for name, entry in data.items():
        if not isinstance(entry, dict):
            continue
        content = entry.get("content")
        if not isinstance(content, str):
            continue
        body = _strip_markers(content, name)
        if body is None:
            continue
        result[name] = _normalize_paragraphs(body)

    _canonical_cache[canonical_path] = (mtime, result)
    return result


def _strip_markers(content: str, template_name: str) -> Optional[str]:
    """Remove the BEGIN/END marker lines surrounding the canonical content.

    Returns the inner body, or ``None`` if either marker is missing for the
    given template name.  The canonical file is expected to wrap each
    ``content`` value with its own markers so that block-paste-into-spec
    works without fix-up.
    """
    begin_marker = f"<!-- CAMARA:MANDATORY:{template_name}:BEGIN -->"
    end_marker = f"<!-- CAMARA:MANDATORY:{template_name}:END -->"
    if begin_marker not in content or end_marker not in content:
        return None
    after_begin = content.split(begin_marker, 1)[1]
    body = after_begin.split(end_marker, 1)[0]
    return body


# ---------------------------------------------------------------------------
# Paragraph normalisation
# ---------------------------------------------------------------------------


def _normalize_paragraphs(text: str) -> List[str]:
    """Split *text* on blank lines, normalise whitespace within paragraphs.

    Per design doc §4.2: within a paragraph runs of whitespace (including
    newlines) are collapsed to a single space; paragraph boundaries (blank
    lines) are preserved.  Empty paragraphs are dropped.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = re.split(r"\n[ \t]*\n+", text)
    result: List[str] = []
    for para in paragraphs:
        normalised = re.sub(r"\s+", " ", para).strip()
        if normalised:
            result.append(normalised)
    return result


# ---------------------------------------------------------------------------
# Marker extraction from the spec's info.description
# ---------------------------------------------------------------------------


def _extract_markers(description: str) -> Tuple[List[Dict], List[Dict]]:
    """Walk *description* and group BEGIN/END markers by template name.

    Returns ``(blocks, anomalies)``:

    * ``blocks`` — one dict per matched BEGIN/END pair, ordered by appearance:
      ``{"name": str, "body": str, "begin_line": int, "end_line": int}``.
    * ``anomalies`` — unmatched markers (BEGIN without END, or END without
      preceding BEGIN), to be reported as ``unknown-template-name`` findings
      with a clarifying message.  Unbalanced markers can produce silent
      passes otherwise.
    """
    lines = description.splitlines()
    blocks: List[Dict] = []
    anomalies: List[Dict] = []
    open_block: Optional[Dict] = None
    for line_no, line in enumerate(lines, start=1):
        match = _MARKER_RE.search(line)
        if match is None:
            continue
        name, side = match.group(1), match.group(2)
        if side == "BEGIN":
            if open_block is not None:
                # A second BEGIN before the previous END — treat the
                # dangling BEGIN as an anomaly and start fresh from here.
                anomalies.append(
                    {
                        "name": open_block["name"],
                        "line": open_block["begin_line"],
                        "reason": "begin-without-end",
                    }
                )
            open_block = {"name": name, "begin_line": line_no, "body_lines": []}
        else:  # END
            if open_block is None:
                anomalies.append(
                    {"name": name, "line": line_no, "reason": "end-without-begin"}
                )
                continue
            if open_block["name"] != name:
                # Mismatched END name — close the open block with a name
                # mismatch anomaly, do not extract content.
                anomalies.append(
                    {
                        "name": open_block["name"],
                        "line": open_block["begin_line"],
                        "reason": "name-mismatch",
                    }
                )
                open_block = None
                continue
            blocks.append(
                {
                    "name": name,
                    "body": "\n".join(open_block["body_lines"]),
                    "begin_line": open_block["begin_line"],
                    "end_line": line_no,
                }
            )
            open_block = None
            continue
        # If we reach here a marker line was processed; we do not include
        # the marker line itself in body_lines.

    # Body capture: walk again, accumulating content lines between matched
    # BEGIN/END.  Simpler than tracking inside the loop above given the
    # anomaly handling.
    blocks = []  # rebuild with bodies
    open_block = None
    for line_no, line in enumerate(lines, start=1):
        match = _MARKER_RE.search(line)
        if match is None:
            if open_block is not None:
                open_block["body_lines"].append(line)
            continue
        name, side = match.group(1), match.group(2)
        if side == "BEGIN":
            open_block = {"name": name, "begin_line": line_no, "body_lines": []}
        else:  # END
            if open_block is None or open_block["name"] != name:
                # Anomaly already recorded above; skip.
                open_block = None
                continue
            blocks.append(
                {
                    "name": name,
                    "body": "\n".join(open_block["body_lines"]),
                    "begin_line": open_block["begin_line"],
                    "end_line": line_no,
                }
            )
            open_block = None
    return blocks, anomalies


# ---------------------------------------------------------------------------
# Folded-scalar detection (raw YAML AST)
# ---------------------------------------------------------------------------


# Cache: { spec_path: (mtime_ns, scalar_style_or_None) }
_scalar_style_cache: Dict[Path, Tuple[int, Optional[str]]] = {}


def _detect_info_description_style(spec_path: Path) -> Optional[str]:
    """Return the YAML scalar style of ``$.info.description``, or ``None``.

    Uses :func:`yaml.compose` to walk the node tree without value
    resolution.  Scalar nodes carry a ``.style`` attribute: ``'|'`` for
    block literal, ``'>'`` for block folded, ``''`` for plain, ``'"'`` or
    ``"'"`` for quoted.

    Returns ``None`` when ``info.description`` is missing or the file is
    unreadable.
    """
    try:
        mtime = spec_path.stat().st_mtime_ns
    except FileNotFoundError:
        return None

    cached = _scalar_style_cache.get(spec_path)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    try:
        with spec_path.open("r", encoding="utf-8") as f:
            root = yaml.compose(f, Loader=yaml.SafeLoader)
    except (yaml.YAMLError, OSError):
        _scalar_style_cache[spec_path] = (mtime, None)
        return None

    style = _scalar_style_at(root, ("info", "description"))
    _scalar_style_cache[spec_path] = (mtime, style)
    return style


def _scalar_style_at(node, path: Tuple[str, ...]) -> Optional[str]:
    """Walk a yaml.compose() node tree along *path* and return scalar .style."""
    from yaml.nodes import MappingNode, ScalarNode

    current = node
    for key in path:
        if not isinstance(current, MappingNode):
            return None
        next_node = None
        for k_node, v_node in current.value:
            if isinstance(k_node, ScalarNode) and k_node.value == key:
                next_node = v_node
                break
        if next_node is None:
            return None
        current = next_node
    if isinstance(current, ScalarNode):
        return current.style or ""
    return None


# ---------------------------------------------------------------------------
# Check entry point
# ---------------------------------------------------------------------------


def check_info_description_templates(
    repo_path: Path, context: ValidationContext
) -> List[dict]:
    """Validate the mandatory ``info.description`` blocks for one API spec.

    API-scoped (one invocation per API in ``context.apis``; the adapter
    narrows ``context.apis`` to a single API before calling).

    Returns findings tagged with six distinct ``engine_rule`` values
    (see module docstring).  Returns ``[]`` when:

    * the spec file is absent
    * the spec lacks ``info.description`` entirely (covered by built-in
      OAS rule S-201 ``info-description``)

    When the canonical file is absent or unreadable, emits a warning so
    r4.3+ branches do not silently skip the template validation family.
    """
    if not context.apis:
        return []
    api = context.apis[0]
    spec_path = repo_path / api.spec_file
    if not spec_path.is_file():
        return []

    canonical = _load_canonical(repo_path)
    if canonical is None:
        return [
            make_finding(
                engine_rule=_RULE_CANONICAL_MISSING,
                level="warn",
                message=(
                    f"Cannot validate mandatory info.description templates "
                    f"because {_CANONICAL_REL_PATH!r} is missing or "
                    f"unreadable. The common-file sync must provide this "
                    f"file before P-026..P-030 can check mandatory "
                    f"info.description blocks."
                ),
                path=api.spec_file,
                line=1,
                api_name=api.api_name,
            )
        ]

    try:
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return []
    if not isinstance(spec, dict):
        return []

    info = spec.get("info")
    if not isinstance(info, dict):
        return []
    description = info.get("description")
    if not isinstance(description, str) or not description.strip():
        return []

    findings: List[dict] = []
    spec_file = api.spec_file

    # Folded-scalar check (P-030).  When info.description uses folded
    # style ('>' / '>-' / '>+') the YAML parser collapses line breaks
    # into spaces, flattening the BEGIN/END markers into a paragraph.
    style = _detect_info_description_style(spec_path)
    if style == ">":
        findings.append(
            make_finding(
                engine_rule=_RULE_FOLDED,
                level="warn",
                message=(
                    "info.description uses YAML folded-scalar style "
                    "('description: >'). Line-anchored BEGIN/END markers "
                    "for mandatory templates are flattened by the parser "
                    "and will not be detected."
                ),
                path=spec_file,
                line=1,
                api_name=api.api_name,
            )
        )

    blocks, anomalies = _extract_markers(description)

    # Anomaly findings (P-029).  Unbalanced markers point at an authoring
    # mistake and would otherwise silently slip through.
    for anomaly in anomalies:
        if anomaly["reason"] == "begin-without-end":
            msg = (
                f"info.description has a BEGIN marker for template "
                f"{anomaly['name']!r} without a matching END marker."
            )
        elif anomaly["reason"] == "end-without-begin":
            msg = (
                f"info.description has an END marker for template "
                f"{anomaly['name']!r} without a preceding BEGIN marker."
            )
        else:  # name-mismatch
            msg = (
                f"info.description has mismatched BEGIN/END marker names "
                f"around template {anomaly['name']!r}."
            )
        findings.append(
            make_finding(
                engine_rule=_RULE_UNKNOWN,
                level="warn",
                message=msg,
                path=spec_file,
                line=1,
                api_name=api.api_name,
            )
        )

    # Group blocks by template name to find duplicates.
    by_name: Dict[str, List[Dict]] = {}
    for block in blocks:
        by_name.setdefault(block["name"], []).append(block)

    # Unknown template names (P-029): block names that are not in the
    # canonical catalog.  Reported once per distinct unknown name.
    for name, occurrences in by_name.items():
        if name in canonical:
            continue
        findings.append(
            make_finding(
                engine_rule=_RULE_UNKNOWN,
                level="warn",
                message=(
                    f"info.description references unknown template "
                    f"{name!r}. The canonical file "
                    f"{_CANONICAL_REL_PATH!r} declares: "
                    f"{sorted(canonical.keys())!r}."
                ),
                path=spec_file,
                line=occurrences[0]["begin_line"],
                api_name=api.api_name,
            )
        )

    # Duplicates (P-028).  Same template name appearing more than once.
    # Reported once per duplicated name; the message lists the line numbers.
    for name, occurrences in by_name.items():
        if name not in canonical:
            continue
        if len(occurrences) <= 1:
            continue
        line_list = ", ".join(str(o["begin_line"]) for o in occurrences)
        findings.append(
            make_finding(
                engine_rule=_RULE_DUPLICATE,
                level="error",
                message=(
                    f"info.description includes the mandatory template "
                    f"{name!r} more than once (BEGIN markers at lines "
                    f"{line_list}). Each template must appear at most once."
                ),
                path=spec_file,
                line=occurrences[0]["begin_line"],
                api_name=api.api_name,
            )
        )

    # Drift (P-027).  For every known-template block that is present
    # (whether universal or opt-in), compare paragraph-by-paragraph
    # against the canonical.  Only fires once per name even on the
    # duplicate path (use the first occurrence).
    for name, occurrences in by_name.items():
        if name not in canonical:
            continue
        block = occurrences[0]
        found_paragraphs = _normalize_paragraphs(block["body"])
        canonical_paragraphs = canonical[name]
        if found_paragraphs == canonical_paragraphs:
            continue
        diff_msg = _format_drift_message(
            name, canonical_paragraphs, found_paragraphs
        )
        findings.append(
            make_finding(
                engine_rule=_RULE_DRIFT,
                level="warn",
                message=diff_msg,
                path=spec_file,
                line=block["begin_line"],
                api_name=api.api_name,
            )
        )

    # Missing (P-026).  Universal templates not present at all.  Opt-in
    # Appendix A templates are not reported when absent — codeowner
    # judgement of the auth model.
    for template_name in _UNIVERSAL_TEMPLATES:
        if template_name in by_name:
            continue
        if template_name not in canonical:
            # Canonical file present but missing this template — unusual
            # but not a per-spec concern.  Self-test catches this.
            continue
        findings.append(
            make_finding(
                engine_rule=_RULE_MISSING,
                level="warn",
                message=(
                    f"info.description is missing the mandatory template "
                    f"{template_name!r}. Paste the BEGIN..END block from "
                    f"{_CANONICAL_REL_PATH!r}."
                ),
                path=spec_file,
                line=1,
                api_name=api.api_name,
            )
        )

    return findings


def _format_drift_message(
    template_name: str,
    canonical_paragraphs: List[str],
    found_paragraphs: List[str],
) -> str:
    """Build a drift finding message that names the first differing paragraph."""
    if len(canonical_paragraphs) != len(found_paragraphs):
        return (
            f"info.description template {template_name!r} has "
            f"{len(found_paragraphs)} paragraph(s); canonical has "
            f"{len(canonical_paragraphs)}. Re-copy the BEGIN..END block "
            f"from {_CANONICAL_REL_PATH!r}."
        )
    for idx, (canon, found) in enumerate(
        zip(canonical_paragraphs, found_paragraphs), start=1
    ):
        if canon == found:
            continue
        return (
            f"info.description template {template_name!r} has drifted from "
            f"canonical at paragraph {idx}.\n"
            f"  canonical: {_clip(canon)}\n"
            f"  found:     {_clip(found)}\n"
            f"Re-copy the BEGIN..END block from "
            f"{_CANONICAL_REL_PATH!r}."
        )
    # Same paragraph count and all equal — caller should have skipped.
    return (
        f"info.description template {template_name!r} differs from "
        f"canonical (no paragraph-level difference detected; check "
        f"trailing whitespace)."
    )


def _clip(text: str, limit: int = 160) -> str:
    """Truncate *text* to *limit* characters for inline diff display."""
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."
