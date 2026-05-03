"""Diagnostic artifact writing.

Writes the full (untruncated) findings list, validation context, summary
metadata, a tab-separated ``findings.tsv`` for spreadsheet review, and
optional engine reports to a specified directory.  The workflow step
uploads this directory via ``actions/upload-artifact``.

Design doc references:
  - Section 9.5: diagnostic artifacts (always available regardless of token)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from validation.context import ValidationContext
from validation.postfilter.engine import PostFilterResult

from .formatting import count_findings, format_rule_label

# TSV columns (header row + per-finding rows).
_TSV_COLUMNS = ("rule", "file", "line", "level", "message", "suggestion")

logger = logging.getLogger(__name__)


def write_diagnostics(
    post_filter_result: PostFilterResult,
    context: ValidationContext,
    output_dir: Path,
    engine_reports: Optional[Dict[str, Any]] = None,
) -> List[Path]:
    """Write diagnostic artifact files to *output_dir*.

    Creates the directory if it does not exist.

    Files written:
      - ``findings.json`` — full findings list (no truncation)
      - ``context.json`` — serialised validation context
      - ``summary.json`` — result, summary string, and aggregate counts
      - ``findings.tsv`` — full findings as tab-separated rows
      - ``engine-reports.json`` — raw engine reports (only when provided)

    Args:
        post_filter_result: Output of the post-filter engine.
        context: Unified validation context.
        output_dir: Target directory for artifact files.
        engine_reports: Optional raw engine output to include.

    Returns:
        List of paths to the files that were written.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    written: List[Path] = []

    # findings.json
    findings_path = output_dir / "findings.json"
    findings_path.write_text(
        json.dumps(post_filter_result.findings, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    written.append(findings_path)

    # context.json
    context_path = output_dir / "context.json"
    context_path.write_text(
        json.dumps(context.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    written.append(context_path)

    # summary.json
    counts = count_findings(post_filter_result.findings)
    summary_data = {
        "result": post_filter_result.result,
        "summary": post_filter_result.summary,
        "counts": {
            "errors": counts.errors,
            "warnings": counts.warnings,
            "hints": counts.hints,
            "total": counts.total,
            "blocking": counts.blocking,
        },
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    written.append(summary_path)

    # findings.tsv
    tsv_path = output_dir / "findings.tsv"
    _write_findings_tsv(post_filter_result.findings, tsv_path)
    written.append(tsv_path)

    # engine-reports.json (optional)
    if engine_reports is not None:
        reports_path = output_dir / "engine-reports.json"
        reports_path.write_text(
            json.dumps(engine_reports, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        written.append(reports_path)

    logger.info("Wrote %d diagnostic files to %s", len(written), output_dir)
    return written


def _sanitize_tsv_field(value: Any) -> str:
    """Return *value* with tab and newline characters replaced by spaces.

    TSV has no quoting convention, so tabs and newlines in field values
    must be flattened to keep the row alignment intact.
    """
    text = "" if value is None else str(value)
    return text.replace("\t", " ").replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


def _write_findings_tsv(findings: List[dict], path: Path) -> None:
    """Write the full findings list as a tab-separated table.

    Header row matches :data:`_TSV_COLUMNS`.  Rule code uses
    :func:`format_rule_label` (same as the workflow summary and
    annotation surfaces).  Other fields come straight from each
    finding dict; tabs and newlines inside fields are sanitized.
    """
    lines = ["\t".join(_TSV_COLUMNS)]
    for f in findings:
        row = (
            format_rule_label(f),
            f.get("path", "") or "",
            f.get("line", 0),
            f.get("level", "") or "",
            f.get("message", "") or "",
            f.get("suggestion", "") or "",
        )
        lines.append("\t".join(_sanitize_tsv_field(v) for v in row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
