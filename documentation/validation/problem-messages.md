# Validation problem messages

CAMARA Validation reports problems in a consistent format. This page describes what the messages contain and how to read them. For where the messages appear, see [Where to see validation results](where-to-see-results.md).

## What you see

A typical annotation, as shown on the pull request's Checks panel, looks like this:

![Annotation for a single problem on a pull request: the title GET / DELETE must not have a request body shown in red bold, with the message [S-002] There must be no request body for Get and DELETE underneath, and the source file and line shown above](images/annotation-s002.png)

Rendered as text, the same annotation contains:

```
GET / DELETE must not have a request body
code/API_definitions/sample-service.yaml  line 130
[S-002] There must be no request body for Get and DELETE
```

The same problem in the workflow summary appears as a bullet under a rule block. All hits of the same rule share one block, with one bold subject line and one bullet per occurrence. When the rule supplies a suggested fix, it is shown once at the end as a `Suggestion:` blockquote:

```markdown
**[S-002] Request body present on GET / DELETE — 1 hit**
- code/API_definitions/sample-service.yaml:130 — [S-002] There must be no request body for Get and DELETE
```

Both views show the same information in different ways. Across both, every problem carries:

- a **severity** — `error`, `warning`, or `hint`
- a **rule code** in square brackets, for example `[S-002]`
- a **source file and line**, when a single line applies
- a one-sentence **message** describing the problem
- sometimes a **suggested fix or link**, shown after a `Suggestion:` label

Annotations also include a short title shown above the message.

## Severity

Severity is a property of every problem, but the way it is shown depends on where you see it:

- In annotations, severity is shown by icon and colour.
- In the workflow summary, problems are grouped under severity headings.
- The severity word itself is not always part of the message body text.

| Severity | What it means for you |
|---|---|
| **error** | Should be fixed before the pull request is merged. The release process will not pass while errors remain. |
| **warning** | The check still passes, but the problem will need attention before a stable release. Plan to fix it. |
| **hint** | Informational. May indicate a future requirement, an item to verify, or a benign pattern. Read the message before acting. |

Errors should not be left on `main` intentionally. During the pilot, GitHub may not technically block every pull request merge on validation errors, but errors will block `/create-snapshot` and the release process.

A few rules adjust severity by context. For example, missing test files are a hint on alpha releases but an error on stable releases. The FAQ entry for those rules explains when this happens.

## Rule codes

Each problem has a rule code in square brackets, for example `[S-002]` or `[P-006]`. The FAQ is organised by question, not by rule code, but the codes are searchable on that page. They are also useful when reporting an issue or asking for support — quoting the code lets others identify the same problem quickly.

## What to open next

- To find all problems in a run: open the workflow summary linked from the CAMARA Validation check.
- To understand a specific recurring rule: search the [Validation FAQ](faq.md) for the rule code.
- To fix a problem reported on a pull request: see [Validation on pull requests](pull-requests.md).
- To fix a problem reported by `/create-snapshot`: see [Validation during snapshot creation](release-snapshots.md).
- To handle a problem reported on a Release PR: see [Validation on a Release PR](release-prs.md).

## Related

- [Where to see validation results](where-to-see-results.md)
- [Validation on pull requests](pull-requests.md)
- [Validation FAQ](faq.md)
- [Release process: lifecycle](https://github.com/camaraproject/ReleaseManagement/blob/main/documentation/release-process/lifecycle.md)
