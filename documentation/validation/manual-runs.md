# Manual validation runs

In addition to running automatically on pull requests and on `/create-snapshot`, CAMARA Validation can be run on demand from the **Actions** tab of the API repository.

## When to use this

- Validate a feature branch before opening a pull request.
- Re-check `main` (or a maintenance branch) outside the pull-request flow.
- Spot-check any branch in the repository — the manual run can target any ref.

## How to run it

1. In the API repository, open the **Actions** tab.
2. Select the **CAMARA Validation** workflow from the left side.
3. Click **Run workflow**.
4. In the **Use workflow from** dropdown, choose the branch you want to validate.
5. Click **Run workflow** to start the run.

## Where to see the report

The run appears in the **Actions** list. Open it and use the **Summary** tab to see the workflow summary — the same complete report as for a pull request run. Manual runs do not produce pull-request annotations, since there is no pull request to annotate.

## How this differs from a pull-request run

- A manual run validates the chosen branch as it currently is. It does not compare against `main` or another base ref.
- There is no pull-request comment, no Files-changed annotations, and no pass/fail signal on a pull request.
- The validation rules and severity model are the same as on a pull request.

## Related

- [Where to see validation results](where-to-see-results.md)
- [Validation on pull requests](pull-requests.md)
- [Validation problem messages](problem-messages.md)
