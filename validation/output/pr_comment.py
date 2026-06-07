"""PR comment markdown generation.

Produces a concise summary comment for the pull request with a
create-or-update marker.  The actual posting is handled by the
workflow step (``actions/github-script``).

Design doc references:
  - Section 9.3: PR comment (concise, marker-based create-or-update)
"""

from __future__ import annotations

import logging

from validation.context import ValidationContext
from validation.postfilter.engine import PostFilterResult

from .formatting import count_findings, resolve_result_label

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MARKER = "<!-- camara-validation -->"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_pr_comment(
    post_filter_result: PostFilterResult,
    context: ValidationContext,
) -> str:
    """Generate the PR comment markdown string.

    The returned string includes the :data:`MARKER` for idempotent
    create-or-update by the workflow step.

    Args:
        post_filter_result: Output of the post-filter engine.
        context: Unified validation context.

    Returns:
        Complete Markdown string ready to post as a PR comment.
    """
    result = post_filter_result.result
    findings = post_filter_result.findings
    counts = count_findings(findings)
    result_label = resolve_result_label(result, context.profile, counts)

    lines = [
        MARKER,
        f"### CAMARA Validation — {result_label}",
        "",
        (
            f"{counts.errors} errors, {counts.warnings} warnings, "
            f"{counts.hints} hints | Profile: {context.profile}"
        ),
        "",
    ]
    if context.workflow_run_url:
        lines.append(f"[View full results]({context.workflow_run_url})")
    else:
        lines.append("See workflow summary for full results.")

    # On the release-review PR, point the codeowner to the deferral workflow
    # when warnings remain (MUST from rc onward, SHOULD at alpha).
    if context.is_release_review_pr and counts.warnings > 0:
        modal = (
            "SHOULD"
            if context.target_release_type == "pre-release-alpha"
            else "MUST"
        )
        lines.extend([
            "",
            (
                f"> Warnings {modal} be documented in one or more issues before "
                "this release — see the Codeowner Actions in the PR description."
            ),
        ])

    return "\n".join(lines)
