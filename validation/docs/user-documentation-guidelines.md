# User documentation guidelines for CAMARA Validation

This document defines the structure and writing rules for user-facing CAMARA Validation documentation in the `tooling` repository.

It is for anyone extending the documentation, including human contributors and automation agents. It is not the user documentation itself.

## Scope

CAMARA Validation user documentation helps API contributors, API codeowners, release coordinators, release reviewers, and first-time readers understand validation results and decide what to do next.

The documentation must answer practical questions:

- Where do I see validation results?
- What does an error, warning, or hint mean here?
- What do I fix, and where?
- What changes on a normal pull request, during `/create-snapshot`, on a Release PR, or in a manual run?
- When should I inspect bundled API definitions?

The documentation must not explain validation internals unless the detail changes what the user should do.

## Audience boundaries

### In scope

Write for these readers:

| Audience | Main need |
|---|---|
| API contributors | Understand why a PR failed and how to fix it. |
| API codeowners | Decide whether a problem blocks merge or release progress. |
| Release coordinators | Understand validation around `/create-snapshot` and release recovery. |
| Release reviewers | Understand validation on Release PRs and what can or cannot be fixed there. |
| Curious newcomers | Understand what CAMARA Validation is and why it appeared in GitHub. |

### Out of scope

Do not include admin or implementation documentation in the user-facing documentation tree.

Keep these topics in developer/admin documentation, most likely under `validation/docs/`:

- how to configure CAMARA Validation centrally
- how rules are implemented
- how engines, post-processing, applicability, or rule metadata work internally
- regression testing and fixture design
- GitHub App deployment or permission setup, except for a short user-facing explanation of why the App appears in checks

## Documentation locations

Use two separate documentation areas:

```text
tooling/
├── documentation/
│   ├── README.md
│   └── validation/
│       ├── where-to-see-results.md
│       ├── pull-requests.md
│       ├── release-snapshots.md
│       ├── release-prs.md
│       ├── manual-runs.md
│       ├── bundled-api-definitions.md
│       ├── problem-messages.md
│       └── faq.md
└── validation/
    └── docs/
        └── user-documentation-guidelines.md
```

### Important navigation rule

Do not create `tooling/documentation/validation/README.md`.

The single user-facing navigation entry point is:

```text
tooling/documentation/README.md
```

The `validation/` directory under `tooling/documentation/` contains task pages only. This avoids two competing overview pages.

## GitHub App homepage URL

The CAMARA Validation GitHub App homepage URL should point to:

```text
tooling/documentation/README.md
```

Do not rely on a section anchor, such as `README.md#camara-validation`, until that behavior is tested in all GitHub surfaces.

This matters because the same homepage URL may be opened from annotation actions such as **View details**. The target must work for confused first-time readers as well as repeat users.

## Top-level README structure

`tooling/documentation/README.md` is the main navigation page for user-facing tooling documentation.

It should be short and task-oriented. It should leave room for future tooling areas, for example Release Automation, without forcing a reorganization.

Recommended structure:

```markdown
# CAMARA Tooling documentation

This documentation helps CAMARA API contributors, codeowners, and release coordinators use shared tooling in API repositories.

## CAMARA Validation

CAMARA Validation checks API definitions, test files, and release planning files in CAMARA API repositories.

### I need to ...

| I need to ... | Read |
|---|---|
| Understand why CAMARA Validation failed my PR | `validation/pull-requests.md` |
| Find the full validation results in GitHub | `validation/where-to-see-results.md` |
| Understand error, warning, and hint messages | `validation/problem-messages.md` |
| Get more help for a specific validation problem | `validation/faq.md` |
| Fix a failed `/create-snapshot` run | `validation/release-snapshots.md` |
| Understand validation on a Release PR | `validation/release-prs.md` |
| Preview the bundled API definition with resolved `$ref`s | `validation/bundled-api-definitions.md` |
| Run validation manually | `validation/manual-runs.md` |

## Future tooling area

Reserved for later user-facing documentation.
```

Do not repeat the same overview in another README.

## Validation document set

### `where-to-see-results.md`

Purpose: explain where validation results appear in GitHub.

Cover:

- PR check result
- workflow details and workflow summary
- changed-files annotations
- fork PR behavior
- same-repository PR behavior, if different
- Release Issue bot messages for `/create-snapshot`
- limits of annotations, for example only changed files and category limits

Key message:

> The workflow summary is the complete report. Annotations are useful but partial.

### `pull-requests.md`

Purpose: explain what to do when CAMARA Validation runs on a PR to `main`.

Cover:

- what contributors see on fork PRs
- what codeowners should check before merge
- how to interpret error, warning, and hint in normal development
- why some problems must be fixed before merge
- why some hints are early signals for a later release step
- where to find the full report
- when to consult `faq.md`

Use the pattern:

```markdown
## What you see

...

## What you do

...

## What can block you

...
```

### `release-snapshots.md`

Purpose: explain validation around `/create-snapshot`.

Cover:

- `/create-snapshot` validates the current base branch before creating a snapshot
- if validation fails, no snapshot is created
- the Release Issue remains in PLANNED state
- fixes happen on `main` or the applicable maintenance branch
- after fixes are merged, run `/create-snapshot` again
- discarding and retrying snapshots is normal recovery, not a broken state

Do not imply that users fix validation problems in the Release Issue itself.

### `release-prs.md`

Purpose: explain validation on Release PRs.

Cover:

- the Release PR exists after a successful snapshot
- the Release PR is for reviewable release content, not general API fixes
- validation is a transparency check on generated or assembled release content
- API specification problems found at this point should be fixed on `main`
- the active snapshot is discarded and a new snapshot is created after the fix

Do not tell users to edit mechanical release changes on the snapshot branch.

### `manual-runs.md`

Purpose: explain on-demand validation runs.

Cover:

- when to use a manual run
- what branch or ref is checked
- where the output appears
- how manual output differs from PR checks and `/create-snapshot`
- what users can and cannot infer from a manual run

Keep this page short until manual-run behavior becomes a common user path.

### `bundled-api-definitions.md`

Purpose: explain how and when to inspect bundled API definitions with resolved references.

Cover:

- if bundled APIs are produced, the workflow exposes a `validation-bundled-specs` artifact containing the bundled files
- bundled files are useful to preview the resolved API definition that a reader or release artifact may show
- validation problems are produced before the bundling step, based on source files
- a problem message already contains the source file path, for example an API definition file or `code/common/CAMARA_event_common.yaml`
- `code/common/` files are cached in the API repository next to API definitions, for example in parallel to `code/API_definitions/sample-service.yaml`
- bundled files are not needed to find where a problem came from
- do not fix bundled output directly; fix the source file or cached common file, then rerun validation

Key message:

> Bundled API definitions are for previewing resolved `$ref`s, not for tracing validation problem provenance.

### `problem-messages.md`

Purpose: explain the common format of validation messages.

Cover:

- title
- severity: error, warning, hint
- rule code, for example `[S-002]`
- source file and line, when available
- short explanation
- optional hint
- link or button to details
- relationship between annotations, check results, and workflow summary

Do not list every rule here. Link to `faq.md` for specific recurring problems.

### `faq.md`

Purpose: provide additional explanation for concrete validation problems where the short message is not enough.

This is not a full rule catalog.

Use FAQ entries only when at least one of these is true:

- the rule has context-dependent severity
- the short title is technically correct but not enough for a contributor to act
- the problem commonly appears in annotations
- the rule interacts with release state, API status, or Commonalities version
- the rule has a non-obvious recovery path
- the rule has an explicit hint that needs more context

Recommended structure:

```markdown
# CAMARA Validation FAQ

This page explains common validation problems that need extra context.
For the complete list of validation results, use the workflow summary.

## API definition problems

### Why is a GET or DELETE request body rejected?

Applies to: `[S-002] GET / DELETE must not have a request body`

...
```

Use user questions as headings. Do not use rule codes alone as headings.

Good heading:

```markdown
### Why are missing test files only a hint on my alpha release?
```

Avoid:

```markdown
### P-006 check-test-files-exist
```

Recommended first FAQ entries:

| Rule | Suggested question |
|---|---|
| `[S-002]` | Why is a GET or DELETE request body rejected? |
| `[S-222]` | Why does my operation tag need to be listed globally? |
| `[P-002]` | Why can a draft API be listed before the API file exists? |
| `[P-006]` | Why are missing test files sometimes a hint, warning, or error? |
| `[P-020]` | Why should CloudEvent use `$ref` instead of an inline schema? |
| `[P-021]` | Why is `code/common/` missing or out of sync? |
| `[P-022]` | Why must `release-plan.yaml` change in its own PR? |
| `[P-023]` | Why does CAMARA Validation say a dependency tag was not found? |
| `[S-024]`, `[S-307]` | Why do operations need standard error responses? |
| `[S-211]` | Why is an unused component only a hint? |
| `[S-300]` | Why should resource identifiers not be numeric? |
| `[S-309]` to `[S-313]` | Why do arrays, integers, and strings need limits? |

## Minimum documentation set for pilot

For an initial pilot announcement, create at least:

```text
tooling/documentation/
├── README.md
└── validation/
    ├── where-to-see-results.md
    ├── pull-requests.md
    ├── release-snapshots.md
    ├── problem-messages.md
    ├── bundled-api-definitions.md
    └── faq.md
```

These pages cover the normal PR path, the snapshot gating path, concrete problem help, and the bundled-definition preview task.

The following can be added later if needed:

```text
tooling/documentation/validation/
├── release-prs.md
└── manual-runs.md
```

Do not add a `validation/README.md` later as a shortcut. Add links to the top-level README instead.

## Writing style

Match the style of the CAMARA Release Process documentation:

- concise
- action-oriented
- plain language
- short sections
- task-first navigation
- `I need to ...` entry points
- `What you do` / `What you see` / `What can block you` patterns where useful

Prefer:

```markdown
## What you do

1. Open the workflow summary.
2. Find errors first.
3. Fix the source file shown in the message.
4. Push the change to the PR.
```

Avoid:

```markdown
## Architecture

The validation subsystem evaluates post-filtered findings through engine-specific profiles...
```

## Vocabulary rules

Use words that match what users see and what they need to do.

### Severity words

Only use these severity words:

- error
- warning
- hint

Do not introduce additional severity labels.

### Preferred terms

| Prefer | Avoid | Notes |
|---|---|---|
| validation result | finding | Use for the report as a whole. |
| problem | finding | Use for one reported item. |
| problem message | finding details | Use when explaining what appears in GitHub. |
| validation check | engine rule | Use unless discussing internals. |
| full report | workflow summary | Use both where helpful: “full report in the workflow summary.” |
| source file | upstream file | Avoid “upstream” as a generic direction. |
| before this step | upstream | Be explicit. |
| shared common file | common cache | Use `code/common/` when exact. |
| bundled API definition | bundled artifact | Use when referring to resolved `$ref`s. |

### Terms to avoid in user-facing headings

Avoid these in headings and navigation unless there is no alternative:

- system
- subsystem
- finding
- upstream
- engine
- engine rule
- post-filter
- ruleset
- advisory
- blocking gate
- stage
- profile

Some of these words may appear in developer documentation. They should not become user navigation terms.

## Release terminology

Reuse canonical release-process terms exactly. Do not redefine them in validation pages.

Use:

- Release Issue
- Release PR
- `/create-snapshot`
- `/publish-release`
- PLANNED
- SNAPSHOT ACTIVE
- DRAFT READY
- PUBLISHED
- NOT_PLANNED
- `release-plan.yaml`
- `release-metadata.yaml`
- `main`
- snapshot branch
- release-review branch

Cross-link to release-process terminology when the documentation is published and the relative link is known.

## Process model to preserve

Documentation must preserve these user-facing truths:

1. `release-plan.yaml` declares release intent.
2. The Release Issue reflects state and provides commands; it does not define release intent.
3. Validation on PRs helps keep `main` ready.
4. `/create-snapshot` validates current content before creating release artifacts.
5. If `/create-snapshot` fails, no snapshot is created.
6. Problems are fixed on `main` or the applicable maintenance branch, then validation is rerun.
7. Snapshot branches are automation-owned.
8. Mechanical release changes are not edited by users.
9. Release PRs are for reviewable release content, mainly documentation.
10. Discarding and recreating a snapshot is normal recovery.

## GitHub surfaces to explain consistently

CAMARA Validation appears in several GitHub places. Be explicit about which one the page describes.

| Surface | How to describe it |
|---|---|
| PR check | Overall pass/fail status for CAMARA Validation. |
| Workflow summary | Full validation report. |
| Changed-files annotations | Inline messages near changed lines; useful but partial. |
| Release Issue bot message | Status and valid actions during release automation. |
| Release PR check | Transparency check on release review content or generated content. |
| Manual workflow run | On-demand check for spot-checking and triage. |

For fork PRs, do not assume there is a PR comment. Fork PRs may only show checks, annotations, and workflow details.

## Message and example rules

When writing examples:

- show realistic GitHub labels and commands
- keep examples short
- prefer paths that look like CAMARA API repositories
- include one clear action per step
- explain whether the user fixes source files, `release-plan.yaml`, or release-review documentation

Example problem explanation pattern:

```markdown
## Why does this happen?

...

## What you do

1. ...
2. ...

## When this is only a hint

...

## Related pages

- ...
```

## FAQ entry quality bar

Each FAQ entry should include:

- a question heading
- “Applies to” with one or more rule codes and short titles
- what the message means
- why CAMARA Validation reports it
- what the user should change
- where to make the change
- whether the problem may appear as error, warning, or hint depending on context
- related pages, if useful

Do not include implementation details such as engine names unless the user needs them to act.

## Rules for bundled API definition documentation

Do not imply that bundled API definitions are the source of validation problems.

Write this distinction consistently:

- Validation runs before bundling.
- Validation reports point to the source file where the problem was detected.
- Bundled API definitions are useful to preview resolved `$ref`s.
- If a problem points to `code/common/CAMARA_event_common.yaml`, that is a cached common file in the API repository.
- Fix the source or cached common file according to the guidance; do not edit bundled output.

Use the workflow artifact name exactly:

```text
validation-bundled-specs
```

## Maintenance rules for this documentation set

When adding a new page:

1. Add it only if it answers a distinct user task.
2. Link it from `tooling/documentation/README.md`.
3. Do not add a local README inside `tooling/documentation/validation/`.
4. Keep admin/developer material out of the user-facing tree.
5. Add FAQ entries selectively.
6. Use the same severity vocabulary and release terminology as the rest of the documentation.

When adding a new FAQ entry:

1. Check whether the short validation message is already enough.
2. Check whether a hint already exists in rule metadata.
3. Explain the user action, not the implementation mechanism.
4. Include the rule code so users can search for it.
5. Do not turn the FAQ into a complete rule inventory.

## Review checklist

Before merging documentation changes, check:

- [ ] The top-level README remains the only navigation entry point.
- [ ] No `tooling/documentation/validation/README.md` was added.
- [ ] The page answers a user task, not an internal architecture question.
- [ ] The page says where the user sees the result in GitHub.
- [ ] The page says what the user should do next.
- [ ] The page distinguishes source files from bundled output.
- [ ] The page uses only error, warning, and hint for severity.
- [ ] The page avoids internal vocabulary in headings.
- [ ] Release process terms are reused consistently.
- [ ] FAQ entries are selective and question-based.
