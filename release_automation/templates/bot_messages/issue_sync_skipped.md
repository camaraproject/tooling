**ℹ️ Nothing to sync — State: `{{state}}`**
{{#state_published}}Release `{{release_tag}}` is published and its Release Issue is closed; nothing is left to do.{{/state_published}}{{^state_published}}No Release Issue to sync for `{{release_tag}}` in this state.{{/state_published}}
{{#workflow_run_url}}[View workflow run]({{workflow_run_url}}){{/workflow_run_url}}
