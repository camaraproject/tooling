# CAMARA Validation FAQ

This page explains common validation problems that need extra context. It is not a full rule catalog — for the complete list of validation results, open the workflow summary linked from the CAMARA Validation check on a pull request.

Each entry has a question heading. The rule code in square brackets is searchable on this page; quoting it when you ask for support also helps others identify the same problem quickly.

## API definition problems

### Why is a GET or DELETE request body rejected?

Applies to: `[S-002] GET / DELETE must not have a request body`

GET and DELETE operations must not declare a request body. The information that a body would carry should be expressed differently:

- For GET, use path parameters or query parameters.
- For DELETE, use path parameters; if a body is genuinely required to express what is being deleted, choose a different method.

**What you do:** open the API definition file shown in the message and remove the `requestBody` from the GET or DELETE operation, or change the operation to a method that accepts a body.

### Why does my operation tag need to be listed globally?

Applies to: `[S-222] Operation tag not defined in tags list`

A tag used on an operation must also be declared in the OpenAPI document's top-level `tags` list. The global list is what describes the tag for readers and tooling; an undeclared tag breaks documentation rendering and grouping.

**What you do:** either add the missing tag to the document's top-level `tags` section with a description, or correct the tag on the operation to one that is already declared globally.

### Why is an unused component only a hint?

Applies to: `[S-211] Component may be unused`

The check may not follow every discriminator mapping. A component that looks unused to the check may still be referenced indirectly. The hint is a prompt to verify, not an instruction to remove.

**What you do:** confirm the component is genuinely unused — for example, by checking discriminator mappings and any oneOf/anyOf indirection — before removing it. If it is in use indirectly, no change is needed.

## Test definition problems

### Why are missing test files sometimes a hint, warning, or error?

Applies to: `[P-006] Missing test definition file for API`

The severity of this rule depends on the API's release type and maturity:

- For alpha releases, test files are optional. The rule reports a hint.
- For a **0.x** API (version below 1.0.0) targeting a release candidate or public release, the rule reports a **warning**.
- For a **stable** (≥1.0.0) API targeting a release candidate or public release, the rule reports an **error**.

**What you do:** add the expected test definition file under `code/Test_definitions/`. The CAMARA Testing Guidelines describe the expected file layout. Address this before the next release type, even when the rule is currently a hint or warning.

## Release-plan problems

### Why can a draft API be listed before the API file exists?

Applies to: `[P-002] API definition file must match release-plan api_name`

`release-plan.yaml` can list an API as `target_api_status: draft` before the API definition file exists in `code/API_definitions/`. This is the intended way to declare a new API: list it as `draft` first, then add the file later. The rule reports this as a **hint** while the entry is `draft`, so the missing file does not block the run.

If the same entry is listed at any other status (`alpha`, `rc`, `public`, `stable`, ...) the rule reports an **error**, because at those statuses the API definition file is required.

**What you do:** if you are starting a new API, keep the entry at `target_api_status: draft` until the API definition file is committed. Promote the status to `alpha` (or higher) only when the file is present in `code/API_definitions/` with a matching filename.

### Why must `release-plan.yaml` change in its own pull request?

Applies to: `[P-022] release-plan.yaml must change in its own PR`

`release-plan.yaml` declares release intent. Mixing release-intent changes with API or test definition changes makes review and validation ambiguous: a reviewer cannot tell which API change goes with which release intent.

**What you do:** split the pull request. Keep `release-plan.yaml` changes in a dedicated pull request, and move the other listed files to a separate pull request.

## Commonalities and shared files

### Why should CloudEvent use `$ref` instead of an inline schema?

Applies to: `[P-020] CloudEvent should be $ref, not inline`

Subscription APIs should reuse the shared CloudEvent schema from `CAMARA_event_common.yaml` rather than maintaining a local inline copy. A `$ref` keeps the API in step with the shared definition; an inline copy drifts over time and produces inconsistent client behaviour across APIs.

**What you do:** replace the local CloudEvent schema with `$ref: './CAMARA_event_common.yaml#/components/schemas/CloudEvent'`. Where you also need an API-specific event type, use `allOf` combining the `$ref` with an API-specific `ApiEventType` schema. The implicit-events API template in the Commonalities artifacts directory shows the recommended pattern.

### Why is `code/common/` missing or out of sync?

Applies to: `[P-021] code/common/ is missing or out of sync`

`code/common/` contains cached copies of shared schemas owned by the [Commonalities](https://github.com/camaraproject/Commonalities) repository. They are managed by automation; if the cache drifts from what the API definitions and the active Commonalities release require, this rule fires.

**What you do:** the recovery depends on what is wrong:

- If your pull request manually edits `code/common/`, revert those edits. The cached files will be re-synchronised by automation.
- If your branch is missing files that should be present, merge `main` into your branch — `main` carries the latest synchronised files.
- If `main` is also behind, merge the auto-created sync pull request, or dispatch the release-automation sync workflow on the repository.

A real issue with the *content* of a cached common file is fixed upstream in [Commonalities](https://github.com/camaraproject/Commonalities), not in the API repository.

This rule is a warning by default, and an error during release automation runs.

### What should I do about missing or drifted mandatory `info.description` blocks?

Applies to: `[P-026] Mandatory info.description template missing`, `[P-027] info.description mandatory template content drift`

CAMARA API specifications must include mandatory `info.description` text blocks from the API Design Guide and the Identity and Consent Management profile. Starting with Commonalities r4.3, the canonical text is synchronized into each API repository as `code/common/info-description-templates.yaml`. The API definition marks each mandatory block with `<!-- BEGIN: ... -->` and `<!-- END: ... -->` delimiters, and validation compares the delimited content with the canonical file.

The severity depends on the API status in `release-plan.yaml`:

- `target_api_status: alpha`: P-026/P-027 are hints. The blocks should be added or corrected before the API progresses to rc.
- `target_api_status: rc`: P-026/P-027 are warnings. The API can still use the r4.3 sync PR to receive the canonical file, but codeowners should fix the warnings before the rc pre-release.
- `target_api_status: public`: P-026/P-027 are errors. The API is expected to contain the mandatory blocks verbatim; validation fails and would block the release until they are fixed.

**What you do:** copy the reported template from `code/common/info-description-templates.yaml` into the affected API file's `info.description`, keeping the BEGIN/END delimiters and the canonical text unchanged. For P-027, replace the whole drifted delimited block with the matching block from the canonical file.

If the finding appears on the automated Commonalities r4.3 sync pull request itself, first check the API status. For alpha or rc APIs, merge the sync PR so the repository receives `code/common/info-description-templates.yaml`, then open a follow-up API PR to copy the canonical blocks into `info.description`. For APIs already marked `public`, change the release plan only if the API is actually still preparing an rc release; otherwise fix the missing or drifted blocks before release.

Do not edit `code/common/info-description-templates.yaml` in the API repository. That file is owned by Commonalities and updated by the common-file synchronization.

## Related

- [Validation problem messages](problem-messages.md) — the shape of each message
- [Where to see validation results](where-to-see-results.md) — where messages appear in GitHub
- [Validation on pull requests](pull-requests.md) — what a contributor or codeowner does
- [Validation during snapshot creation](release-snapshots.md) — what happens at `/create-snapshot`
- [Validation on a Release PR](release-prs.md) — what changes on a Release PR
- [Bundled API definitions](bundled-api-definitions.md)
