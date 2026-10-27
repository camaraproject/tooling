**🔁 Post-release steps run again — State: `published`**
{{#has_sync_pr}}Post-release sync PR: [#{{sync_pr_number}}]({{sync_pr_url}}){{#has_main_sync_pr}} and [#{{main_sync_pr_number}}]({{main_sync_pr_url}}) into main{{/has_main_sync_pr}} (requires codeowner merge).{{/has_sync_pr}}{{^has_sync_pr}}{{#has_main_sync_pr}}Post-release sync PR into main: [#{{main_sync_pr_number}}]({{main_sync_pr_url}}) (requires codeowner merge).{{/has_main_sync_pr}}{{^has_main_sync_pr}}{{^has_publish_warnings}}The post-release content is already on `{{base_branch}}`; no sync PR was needed.{{/has_publish_warnings}}{{/has_main_sync_pr}}{{/has_sync_pr}}
{{#has_publish_warnings}}
⚠️ **Not finished:** {{publish_warnings}} ([view log]({{workflow_run_url}})). This issue stays open; `/sync-issue` retries.
{{/has_publish_warnings}}
{{^has_publish_warnings}}
This issue is closed.
{{/has_publish_warnings}}
**Release:** [`{{release_tag}}`]({{release_url}})
