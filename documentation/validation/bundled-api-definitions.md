# Bundled API definitions

If an API definition uses external `$ref`s — for example to share schemas like common error models or CloudEvent definitions — CAMARA Validation may provide a workflow artifact named `validation-bundled-specs`. The artifact contains generated bundled API definitions with references resolved.

> Bundled API definitions are for previewing resolved `$ref`s, not for finding the source of a validation problem.

## What they are

A bundled API definition is a generated, standalone copy of a source API definition with its external `$ref`s **resolved into local references**: schemas referenced from outside the file are copied into the document's `components` section, and the original `$ref`s are rewritten to point at the local copies. It is a **preview** of the API as it would appear to a reader; it is not edited and not committed.

When the workflow produces bundles, you can find the artifact in the **Artifacts** section on the workflow run page:

```text
validation-bundled-specs
```

If a source API definition has no external `$ref`s, no bundle is produced for it.

## When to inspect them

Inspect a bundled API definition when you want to:

- Preview the complete API as it will appear in a published release.
- Confirm that a `$ref` resolves to the schema you expected.
- Review what a reader sees when an external schema (for example a common error model) is included.

You do **not** need a bundled file to find where a validation problem came from — every problem message already includes the source file path.

## Where they come from

Validation runs on **source files** before bundling. The validation report points at source paths:

- API definition files under `code/API_definitions/`
- The repository's `release-plan.yaml`
- Test files under `code/Test_definitions/`
- Cached common files under `code/common/` (for example `code/common/CAMARA_event_common.yaml`)

Bundled output is produced after validation, as a convenience artifact. It is not part of the validation report.

## Two kinds of files you do not edit

- **Bundled output** in the `validation-bundled-specs` artifact — generated; any local edits would be discarded the next time the bundle is produced, and the bundles are never committed to the repository.
- **Cached common files** under `code/common/` — managed by automation. For the practical recovery path when `code/common/` is missing or out of sync in your branch, see the FAQ entry for `[P-021]`.

## Related

- [Where to see validation results](where-to-see-results.md)
- [Validation problem messages](problem-messages.md)
- [Validation FAQ](faq.md) — entries for `[P-020]` (CloudEvent `$ref`) and `[P-021]` (cached common files)
- [Commonalities repository](https://github.com/camaraproject/Commonalities)
