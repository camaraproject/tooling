# Validation Framework — Mandatory `info.description` Content Validation Design

**Status**: Design accepted
**Last updated**: 2026-05-15

> This document supplements the [Validation Framework Detailed Design](https://github.com/camaraproject/ReleaseManagement/blob/main/documentation/SupportingDocuments/CAMARA-Validation-Framework-Detailed-Design.md) with the design of a focused mechanism for validating mandatory `info.description` content in CAMARA API specifications. It defines a canonical-content file managed in Commonalities, a delimited-block convention in `info.description`, and a small set of Spectral rules that enforce presence and content. Activation is planned for the r4.3 ruleset.

---

## 1. Overview

### 1.1 Problem

CAMARA APIs include several mandatory text blocks in `info.description` that originate from the [CAMARA API Design Guide](https://github.com/camaraproject/Commonalities/blob/main/documentation/CAMARA-API-Design-Guide.md) and the [Identity and Consent Management profile](https://github.com/camaraproject/IdentityAndConsentManagement/blob/main/documentation/CAMARA-API-access-and-user-consent.md). Each API specification today copy-pastes these texts into its own `info.description`. Every change to a mandatory section in the authoritative source produces a parallel copy-paste update across 60+ API specifications.

[Commonalities#634](https://github.com/camaraproject/Commonalities/pull/634) adds a new mandatory block (§3.2.4, request body strictness) and surfaces this cost again.

### 1.2 Approach

This design retains authoritative prose in the API Design Guide and the ICM profile, and adds a machine-readable canonical file in Commonalities that carries the same text in a structured form. API specifications mark each mandatory block with HTML-comment delimiters that identify which template the block instantiates. Validation reads the delimited regions from each specification and compares them against the canonical content.

The mechanism is layered on the existing validation framework described in [Validation Framework Detailed Design](https://github.com/camaraproject/ReleaseManagement/blob/main/documentation/SupportingDocuments/CAMARA-Validation-Framework-Detailed-Design.md). The canonical file is distributed to each API repository through the same `code/common/` cache-common synchronisation that the framework already uses for `CAMARA_common.yaml`.

### 1.3 Authoritative sources

| Mandatory block | Authoritative source |
|---|---|
| Authorization and authentication | ICM [Mandatory template for `info.description` in CAMARA API specs](https://github.com/camaraproject/IdentityAndConsentManagement/blob/main/documentation/CAMARA-API-access-and-user-consent.md#mandatory-template-for-infodescription-in-camara-api-specs) |
| Additional CAMARA error responses | API Design Guide §3.2.3 (Error Responses — Mandatory Template for `info.description`) |
| Request body strictness | API Design Guide §3.2.4 (new in r4.3) |
| Identifying the device from the access token | API Design Guide Appendix A — device variant |
| Identifying the phone number from the access token | API Design Guide Appendix A — phone-number variant |

Authoritative prose is unchanged by this design.

---

## 2. Canonical File

### 2.1 Location and sync mechanism

The canonical content lives in `code/common/info-description-templates.yaml` of each API repository. The file is owned by Commonalities, where it is maintained at `artifacts/common/info-description-templates.yaml`. The existing cache-common synchronisation copies the file into every onboarded API repository on each Commonalities release. No change to the synchronisation mechanism is required — its file-discovery step scans every `*.yaml` file under `artifacts/common/` and records the result in `.sync-manifest.yaml`.

### 2.2 YAML structure

The file uses one top-level key per template. Each key holds a `content:` field with a block-literal scalar that includes the begin/end delimiters and the canonical text between them. Indentation places the text body at column 4. This matches the indentation that `info.description` content takes in a CAMARA API specification (`info:` at column 0, `description: |` at column 2, body at column 4), so a code-owner can copy a region from the canonical file directly into a target specification without re-indenting.

```yaml
# code/common/info-description-templates.yaml
# Canonical mandatory info.description blocks for CAMARA APIs.
# Synced from Commonalities; do not edit in API repositories.

# Authorization and authentication (ICM template) — mandatory for every CAMARA API
authorization-and-authentication:
  content: |
    <!-- CAMARA:MANDATORY:authorization-and-authentication:BEGIN -->
    # Authorization and authentication

    The "Camara Security and Interoperability Profile" provides ...
    <!-- CAMARA:MANDATORY:authorization-and-authentication:END -->

# Design Guide §3.2.3 — mandatory for every CAMARA API
additional-error-responses:
  content: |
    <!-- CAMARA:MANDATORY:additional-error-responses:BEGIN -->
    # Additional CAMARA error responses

    The list of error codes in this API specification is not exhaustive ...
    <!-- CAMARA:MANDATORY:additional-error-responses:END -->

# Design Guide §3.2.4 — mandatory for every CAMARA API (new in r4.3)
request-body-strictness:
  content: |
    <!-- CAMARA:MANDATORY:request-body-strictness:BEGIN -->
    # Request body strictness

    This API rejects requests with JSON request bodies that contain properties ...
    <!-- CAMARA:MANDATORY:request-body-strictness:END -->
```

YAML comments above each top-level key carry the authoritative-source reference and any guidance on when the template applies. These comments are part of the canonical file and are read by code-owners directly from the file.

### 2.3 Template catalog

| Template name | Authoritative source | Applicability |
|---|---|---|
| `authorization-and-authentication` | ICM authorization-and-authentication template | Required in every CAMARA API |
| `additional-error-responses` | Design Guide §3.2.3 | Required in every CAMARA API |
| `request-body-strictness` | Design Guide §3.2.4 (new in r4.3) | Required in every CAMARA API |
| `identifying-device-from-access-token` | Design Guide Appendix A — device variant | Included only when the API uses the access-token-subject identifier pattern with a `device` object |
| `identifying-phone-number-from-access-token` | Design Guide Appendix A — phone-number variant | Included only when the API uses the access-token-subject identifier pattern with a `phoneNumber` field |

The two Appendix A templates are mutually exclusive within a single API specification. No combined-variant template exists; if a future API genuinely supports both alternatives, a third template can be added at that time.

**The Appendix A templates are not selected by a schema-property scan.** Appendix A specifies the identifier-from-access-token contract — the identifier is implied by a three-legged token and provided with a two-legged token, with `422 MISSING_IDENTIFIER` and `422 UNNECESSARY_IDENTIFIER` semantics. An API may carry a `device` or `phoneNumber` field as a data property without participating in this contract (for example, NumberVerification matches a request `phoneNumber` against the access-token subject; OTPValidation's `phoneNumber` is the OTP recipient, not the access-token subject). Code-owners choose the template that matches the API's authentication model. The validation rules do not infer this choice from the schema.

---

## 3. Delimiter Mechanism

### 3.1 Shape

```
<!-- CAMARA:MANDATORY:<template-name>:BEGIN -->
<template content>
<!-- CAMARA:MANDATORY:<template-name>:END -->
```

`<template-name>` is the top-level key from the canonical file, written in lowercase with hyphens.

The delimiters carry no other annotation. They identify the template and mark the begin/end of the region. Anything that needs to vary by API — for example, an API-specific introduction or example — is placed outside the delimited region.

### 3.2 Pipeline compatibility

HTML comments are stripped by the Markdown renderers used in published CAMARA API documentation (Swagger UI, Redocly). The delimiters are invisible to readers of the rendered API documentation.

The delimiters were validated against the full release pipeline on `camaraproject/ReleaseTest`. A test specification was wrapped with `<!-- CAMARA:MANDATORY:authorization-and-authentication:BEGIN -->` / `:END -->` and processed through PR-time Spectral validation, snapshot creation, Redocly bundling, release-review PR validation, and tag publication. The delimiters survived at every stage and were stripped only at Markdown rendering time.

### 3.3 YAML scalar style requirement

The delimiters depend on line-anchored text. They work with the YAML block-literal scalar style (`description: |` or `description: |-`). They do not work with the folded-scalar style (`description: >` or `description: >-`), where the YAML parser collapses line breaks into spaces and the begin/end markers are flattened into the surrounding paragraph.

API specifications that use folded-scalar style for `info.description` must migrate to block-literal style before adopting the delimiter mechanism. A dedicated validation rule covers this precondition (see §4.1).

---

## 4. Validation Rules

### 4.1 Rule set

| Rule | Fires when | Severity |
|---|---|---|
| `info-description-mandatory-missing` | A required template's BEGIN/END delimiter pair is absent from `info.description` | Per template, by `target_api_status` (see §4.3) |
| `info-description-mandatory-drift` | A delimiter pair is present but the content between the delimiters differs from the canonical text | Per template, by `target_api_status` |
| `info-description-mandatory-duplicate` | The same template name's delimiter pair appears more than once in `info.description` | Error |
| `info-description-mandatory-unknown-template-name` | A delimiter pair uses a template name that is not present in the canonical file | Warning |
| `info-description-folded-scalar` | `info.description` uses YAML folded-scalar style (`>` or `>-`) | Warning |

The first two rules carry the substantive validation. The remaining three guard against authoring mistakes that would otherwise produce silent passes or confusing failures.

The Appendix A templates are not universally required — a specification that omits both Appendix A blocks is not flagged by the missing rule. The missing rule applies to the three universal templates (`authorization-and-authentication`, `additional-error-responses`, `request-body-strictness`). The drift and duplicate rules apply to any template that is present in the specification.

### 4.2 Content match — paragraph-normalised diff

Content comparison normalises whitespace within paragraphs before comparing. Within a paragraph, runs of whitespace including newlines are collapsed to a single space. Paragraph boundaries — blank lines — are preserved as paragraph separators. The diff then proceeds paragraph by paragraph.

This is tolerant to differences in line wrapping (which varies across the existing API specifications) and strict on the textual content. A specification that wraps a sentence to 80 columns matches the same sentence wrapped to 100 columns. A specification that has a typo in the sentence does not.

### 4.3 Severity by `target_api_status`

| `target_api_status` | Severity |
|---|---|
| `alpha` | hint |
| `rc` | warning |
| `public` | error |

Severity is the same at pull-request time and at the snapshot pre-flight stage. The blocking behaviour differs by stage: a snapshot pre-flight failure on `error` blocks snapshot creation, while a pull-request finding can be exceptionally merged. The mapping is configurable per template.

### 4.4 Rule UX — hint message contract

Every finding hint must include:

1. The canonical local path: `code/common/info-description-templates.yaml`
2. The template name
3. For a drift finding: an inline diff of the differing paragraph (canonical paragraph adjacent to the specification paragraph)
4. For a missing finding: a copy-paste-ready snippet of the canonical block
5. For a folded-scalar finding: the trivial fix (`|` in place of `>`)

The hint message is the primary user interface for the rule. CAMARA API code-owners reach the rule through CI findings; the Design Guide and supplementary docs are secondary references. Implementation work invests in hint message quality accordingly.

---

## 5. Activation and Refresh Model

### 5.1 Ruleset scope

The rules activate in `.spectral-r4.3.yaml` and later rulesets. Specifications on earlier rulesets continue to manage `info.description` content by manual review. There is no plan to back-port the rules to r3.x.

### 5.2 Commonalities canonical refresh cycle

1. The Design Guide or ICM authoritative source changes
2. The Commonalities maintainer updates `info-description-templates.yaml` in sync with the change
3. Commonalities cuts a release (for example, r4.3, r4.4, ...)
4. The API code-owner updates the Commonalities dependency in `release-plan.yaml` to the new release
5. The cache-common synchronisation opens a pull request in each onboarded API repository with the updated `code/common/info-description-templates.yaml`
6. The next CI run on each API specification validates `info.description` against the new canonical
7. Findings flag specifications whose content has diverged
8. The API code-owner re-copies the BEGIN/END region from the canonical file into the specification

### 5.3 Cache-common sync coverage

The existing cache-common synchronisation discovers source files by scanning `artifacts/common/*.yaml` in Commonalities and copies each match to `code/common/` in the API repository. A new file added at `artifacts/common/info-description-templates.yaml` is picked up without any change to the synchronisation logic. The result is recorded in the `.sync-manifest.yaml` blob list used by the framework's freshness check.

The relevant section of the framework design is [Validation Framework Detailed Design §3 — Bundling Pipeline](https://github.com/camaraproject/ReleaseManagement/blob/main/documentation/SupportingDocuments/CAMARA-Validation-Framework-Detailed-Design.md#3-bundling-pipeline), which covers the broader bundling and synchronisation model.

---

## 6. Sample Templates and Disclaimer

The Commonalities `artifacts/api-templates/sample-*.yaml` files are published with the applicable mandatory blocks already wrapped in delimiters, and a disclaimer in `info.description`:

> In case of conflict, the authoritative source (API Design Guide for §3.2.3 / §3.2.4 / Appendix A; the ICM authorization-and-authentication template) takes precedence. This disclaimer applies to the mandatory texts and to any other content in this sample.

Per-sample content:

| Sample | Auth | §3.2.3 | §3.2.4 | Appendix A |
|---|---|---|---|---|
| `sample-service.yaml` | yes | yes | yes | `device` variant (illustrative) |
| `sample-service-subscriptions.yaml` | yes | yes | yes | `device` variant |
| `sample-implicit-events.yaml` | yes | yes | yes | none (event-only specification) |

---

## 7. Out of Scope for v1

### 7.1 Authoritative content changes

This design does not change the prose of the API Design Guide or the ICM profile. The authoritative sources remain as they are. The canonical file mirrors the authoritative text without re-defining it.

### 7.2 Per-repository wrap-migration pull requests

The first round of adoption is code-owner-driven, prompted by rule findings on each API repository. There is no programmatic mass-PR step.

### 7.3 Auto-update pull-request mechanism

A future check-and-reconcile workflow may detect content that has diverged from the canonical after a refresh and open an update pull request that replaces each delimited region in one operation. The delimiter contract defined in this document is the substrate that such a mechanism would depend on. Auto-update is not part of the v1 scope.

### 7.4 r3.x back-port

Maintenance releases on the r3.x line are reviewed manually for mandatory-content changes. No rule activation is planned for the r3.4 or earlier rulesets.

---

## Appendix A: Fall25 meta-release baseline

The mechanism was scoped against the Fall25 meta-release. Each of the 40 Fall25-tagged API repositories was inspected at its release tag, covering 60 OpenAPI specifications in total. The findings inform the migration cost.

| Mandatory block | Specifications matching canonical content | Notes |
|---|---|---|
| Authorization and authentication (ICM template) | 60 / 60 | Match under whitespace, case, and Markdown normalisation across all seven required text components |
| Additional CAMARA error responses (§3.2.3) | 60 / 60 | Same normalisation; all seven required components present |
| Request body strictness (§3.2.4) | 0 / 60 | Not yet present in the Fall25 meta-release; adoption is concurrent with the §3.2.4 Design Guide entry in r4.3 |
| Identifying-from-access-token (Appendix A) | 39 / 60 included (26 `device` variant, 13 `phone-number` variant); 21 / 60 not applicable | No combined variant present in the meta-release |

Six specifications use the YAML folded-scalar style for `info.description` (`>` or `>-`). These specifications must migrate to block-literal style before adopting the delimiter mechanism. The folded-scalar validation rule (§4.1) covers this precondition.

The migration cost per specification for the universal blocks is the time to wrap the existing text with BEGIN/END delimiters and the canonical heading. For the Appendix A variants, the cost includes a code-owner judgement on the applicable variant. For the §3.2.4 block, the cost is the same as the Design Guide §3.2.4 adoption itself.
