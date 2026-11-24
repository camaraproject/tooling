**❌ Publication failed — State: `{{state}}`**
{{#workflow_run_url}}[View workflow logs]({{workflow_run_url}}){{/workflow_run_url}}

{{#error_message}}
```
{{error_message}}
```
{{/error_message}}

{{#state_draft_ready}}
Retry `/publish-release --confirm {{release_tag}}`, or contact Release Management for unexpected errors.

{{valid_actions}}
{{/state_draft_ready}}
{{^state_draft_ready}}
The Release PR is merged, but the release was not published. Please contact Release Management (options: re-run the failed jobs of the workflow run, or `/discard-snapshot <reason>` and a new `/create-snapshot`).
{{/state_draft_ready}}
