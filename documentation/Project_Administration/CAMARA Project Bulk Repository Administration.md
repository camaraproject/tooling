# CAMARA Project Bulk Repository Administration

This system provides modular GitHub Actions workflows for managing bulk changes across all CAMARA project repositories with proper testing and safety mechanisms.

Initially two operations are defined:
- **disable-wiki**: Safely disables GitHub wiki on repositories (only if wiki has no content)
- **add-changelog-codeowners**: Adds release management team as reviewers for CHANGELOG.MD changes

## Workflow Architecture

The system consists of three core workflows that work together:

### 1. Single Repository Test (`project-admin-single-repo-test.yml`)
- Tests operations on individual repositories before bulk execution
- Validates repository access and permissions
- Provides detailed feedback on what changes would be made
- **Always start here** when testing new operations

### 2. Repository Worker (`project-admin-repository-worker.yml`) 
- Reusable workflow component that executes operations on individual repositories
- Called by both single test and bulk workflows
- Handles all the actual file modifications and git operations
- Supports dry-run mode for safe testing

### 3. Bulk Repository Changes (`project-admin-bulk-repository-changes.yml`)
- Orchestrates operations across multiple repositories simultaneously  
- Includes repository filtering and exclusion capabilities
- Runs operations in parallel with configurable limits
- Provides comprehensive execution summaries

## File Structure

Place these files in your `.github/workflows/` directory:

```
.github/workflows/
├── project-admin-single-repo-test.yml
├── project-admin-repository-worker.yml
└── project-admin-bulk-repository-changes.yml
```

## Quick Start Guide

### 1. Setup (to be updated)
1. Create the workflow files in your repository (personal or organizational)
2. If running from personal repo targeting `camaraproject`:
   - Create a Personal Access Token with `repo` and `read:org` scopes
   - Add it as a repository secret named `CAMARA_TOKEN`
   - Update the `github-token` parameter in scripts

### 2. Recommended Testing Workflow
```
Single Repo Test (Dry Run) → Single Repo Test (Live) → Bulk Dry Run → Live Bulk Execution
```

This progressive approach ensures:
- Operations work correctly on individual repositories
- No unexpected side effects before bulk execution
- Safe rollout across the entire organization

### 3. Usage Examples

**Test on Single Repository:**
1. Go to Actions → "Single Repository Test"
2. Enter repository name (e.g., "DeviceStatus")
3. Select operation type
4. Enable dry-run mode
5. Review results before proceeding

**Execute Bulk Changes:**
1. Go to Actions → "Bulk Repository Changes"  
2. Select operation type
3. Choose which repository categories to include:
   - Check/uncheck Sandbox API Repositories
   - Check/uncheck Incubating API Repositories
   - Check/uncheck Working Group Repositories  
   - Check/uncheck Other Repositories
4. Configure additional repository filters if needed
5. Start with dry-run mode enabled
6. Review results across selected repositories
7. Re-run with dry-run disabled for live execution

**Category Selection Examples:**
- **API-only changes**: Select only Sandbox and Incubating API repositories
- **Governance updates**: Select only Working Group and Other repositories
- **Universal changes**: Select all categories (default behavior)
- **Targeted rollout**: Start with Sandbox repositories, then expand to others

## Available Operations

### Current Operations
- **disable-wiki**: Safely disables GitHub wiki on repositories (only if wiki has no content)
- **add-changelog-codeowners**: Adds release management team as reviewers for CHANGELOG.MD changes

### Operation Details

**disable-wiki:**
- ✅ Safety check: Only disables wiki if currently enabled but has no content
- ✅ Permission validation: Requires admin access to repository
- ✅ Content protection: Skips repositories where wiki contains content
- ✅ Clear status reporting: Different outcomes for various scenarios

**add-changelog-codeowners:**
- ✅ Adds release management reviewers to root CODEOWNERS file
- ✅ Smart detection: Skips if CHANGELOG.MD rule already exists
- ✅ Creates CODEOWNERS file if it doesn't exist
- ✅ Preserves existing CODEOWNERS content

### Repository Filtering
- **Repository Categories**: Select which types of repositories to include:
  - **Sandbox API Repositories**: Repositories with `sandbox-api-repository` topic
  - **Incubating API Repositories**: Repositories with `incubating-api-repository` topic  
  - **Working Group Repositories**: Repositories with `workinggroup` topic
  - **Other Repositories**: Repositories without the above topics
- **Repository Filter**: Target specific repositories by name pattern
- **Exclude Repositories**: Skip specific repositories (default: 'Governance,.github')
- **Auto-exclusions**: Automatically skips archived repositories

## Key Features

### Safety Mechanisms
- **Dry-run mode**: Test operations without making actual changes
- **Repository validation**: Verify access and permissions before execution
- **Parallel execution limits**: Prevent overwhelming GitHub API
- **Fail-fast disabled**: Continue processing other repos if one fails

### Monitoring & Feedback
- **Detailed summaries**: Clear reporting of what was changed where
- **Progress tracking**: Monitor execution across multiple repositories
- **Error handling**: Graceful handling of permission issues and failures
- **Change detection**: Only commit when actual changes are made

## Token Requirements & Permissions

**For Wiki Operations:**
- **Required Permissions**: Admin access to target repositories
- **Token Scopes**: `repo` (full repository access)
- **Organization Role**: Must be organization owner or repository admin
- **Permission Check**: Automatically verified before operations (even in dry-run mode)

**For CODEOWNERS Operations:**
- **Required Permissions**: Write access to repositories  
- **Token Scopes**: `repo` (full repository access)
- **File Location**: CODEOWNERS file is managed in repository root directory

**Setting up Personal Access Token:**
1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Generate new token with `repo` scope
3. Add token as repository secret named `CAMARA_TOKEN`
4. Ensure your GitHub account has admin access to target repositories

## Best Practices

1. **Always test first**: Use single repository test before bulk operations
2. **Start with dry-run**: Review changes before live execution  
3. **Filter wisely**: Use repository filters to target specific subsets when appropriate
4. **Monitor execution**: Watch for failures and address them before continuing
5. **Verify results**: Check a few repositories manually after bulk operations

## Troubleshooting

**Common Issues:**
- **Repository not found**: Check repository name spelling and organization access
- **Permission denied (wiki operations)**: Verify you have admin access and proper token scopes
- **Wiki has content**: Wiki disable operation skipped for safety - content found
- **CODEOWNERS rule exists**: CHANGELOG.MD rule already present, no changes needed
- **Token insufficient**: Ensure CAMARA_TOKEN has `repo` scope and admin permissions

**Permission-Related Errors:**
- **403 Forbidden**: Token lacks required permissions or user lacks admin access
- **404 Not Found**: Repository doesn't exist or token lacks access
- **422 Unprocessable**: Organization policies may prevent certain operations

**Wiki Operation Status Codes:**
- `no-change`: Wiki already disabled
- `wiki-has-content`: Wiki has content, skipped for safety  
- `would-disable-wiki`: Dry run would disable empty wiki
- `wiki-disabled`: Successfully disabled empty wiki

**CODEOWNERS Operation Status Codes:**
- `no-change`: CHANGELOG.MD rule already exists
- `created`: New CODEOWNERS file created with rule
- `modified`: Rule added to existing CODEOWNERS file


