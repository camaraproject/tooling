# Workspace Configuration

Shared configuration files that should be placed in the **root** of each CAMARA API repository.

These files standardize editor behavior, line-ending enforcement, and ignored-file patterns across all contributors, regardless of OS or IDE.

## Files

| File | Purpose | Placement in API repo |
|------|---------|----------------------|
| `.editorconfig` | Consistent indentation, charset, and line endings across editors ([spec](https://editorconfig.org)) | Copy as-is to repo root |
| `.gitattributes` | Enforces LF line endings at the Git layer and marks binary formats | Copy as-is to repo root |
| `.gitignore-template` | Common ignore patterns for OS, editor, and tooling artifacts | Copy to repo root **and rename** to `.gitignore` |

> `.gitignore-template` is named with a `-template` suffix so that Git does not pick it up inside this tooling repository itself.

## Adoption

To adopt these configurations in an API repository:

1. Copy `.editorconfig` and `.gitattributes` into the repository root.
2. Copy `.gitignore-template` to the repository root and rename it to `.gitignore`. Merge with any existing `.gitignore` entries the repo already has.
3. Commit and push.

If the repository already contains files with CRLF line endings, a separate normalization PR should be created after `.gitattributes` is in place — see [#113](https://github.com/camaraproject/tooling/issues/113) for the migration approach.

## How the files work together

- `.editorconfig` guides editors to use the correct settings **while editing**, so contributors produce correctly formatted files from the start.
- `.gitattributes` acts as a **safety net at the Git layer** — even if an editor writes CRLF, Git normalizes to LF on commit.
- `.gitignore` keeps OS junk and editor artifacts out of version control.

## Alignment with linting rules

The `.editorconfig` settings are derived from the existing linting configurations in [`linting/config/`](../linting/config/):

- **YAML** indent/whitespace rules match [`.yamllint.yaml`](../linting/config/.yamllint.yaml)
- **Gherkin** indent rules match [`.gherkin-lintrc`](../linting/config/.gherkin-lintrc)

This keeps editor formatting and CI linting in sync, so contributors get feedback while editing rather than failing in CI.
