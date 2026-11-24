"""Tests for sync_pr.py (post-release README/CHANGELOG sync PR).

Git runs for real against a local bare repository; the GitHub side is a
fake. The README block of the target branch is rendered from the published
releases (main: repository view; maintenance/rX: view of the release cycle),
the release-cycle CHANGELOG is copied from the tag.
"""

import pytest
import yaml

from release_automation.scripts.github_client import GitHubClientError, Release
from release_automation.scripts.readme_updater import ReadmeUpdater, branch_view
from release_automation.scripts.sync_pr import SyncPrOutcome, create_sync_pr
from release_automation.tests.local_git import git, git_ops, make_remote, push_branch

START = "<!-- CAMARA:RELEASE-INFO:START -->"
END = "<!-- CAMARA:RELEASE-INFO:END -->"

MAIN_README = f"# Example\n\nIntro.\n\n{START}\nNo release yet.\n{END}\n\nFooter.\n"

PR_BODY = (
    "Automated post-release sync PR for r1.3.\n"
    "\n"
    "This PR updates:\n"
    "- README.md Release Information section, from the published releases\n"
    "- CHANGELOG for the release cycle\n"
    "\n"
    "Created by release automation workflow."
)


def metadata(tag, release_type="public-release"):
    return yaml.safe_dump({
        "repository": {"release_tag": tag, "release_type": release_type},
        "apis": [{"api_name": "sample-service", "api_version": "1.0.0"}],
    })


class FakeGitHub:
    def __init__(self, files=None, open_prs=None, fail_create=False, fail_labels=False, releases=("r1.3",)):
        """releases: tags in publication order, all public releases unless "-pre"."""
        self.repo = "camaraproject/Example"
        self.files = files or {}
        self.open_prs = open_prs or {}
        self.fail_create = fail_create
        self.fail_labels = fail_labels
        self.releases = [
            Release(tag_name=t.removesuffix("-pre"), name=t, draft=False, prerelease=t.endswith("-pre"), html_url="")
            for t in releases
        ]
        self.created = []
        self.labelled = []
        self.labels = set()
        self.created_labels = []

    def get_file_content(self, path, ref="main", strict=False):
        return self.files.get((ref, path))

    def get_releases(self, include_drafts=False):
        return list(reversed(self.releases))

    def get_release_metadata(self, tag):
        content = self.files.get((tag, "release-metadata.yaml"))
        return yaml.safe_load(content) if content else None

    def get_repository_yaml_file(self, repo, path, ref="main"):
        return None

    def find_open_pr(self, head_branch):
        return self.open_prs.get(head_branch)

    def create_pr(self, title, body, head, base):
        if self.fail_create:
            raise GitHubClientError("gh command failed: pull request create failed")
        self.created.append({"title": title, "body": body, "head": head, "base": base})
        return 31, "https://github.com/camaraproject/Example/pull/31"

    def get_label(self, name):
        return {"name": name} if name in self.labels else None

    def create_label(self, name, color, description=""):
        self.labels.add(name)
        self.created_labels.append(name)

    def add_pr_labels(self, pr_number, labels):
        if self.fail_labels:
            raise GitHubClientError("gh command failed: label not found")
        self.labelled.append((pr_number, list(labels)))


def rendered(gh, branch, readme=MAIN_README):
    """The README with the block the sync PR renders for branch."""
    return ReadmeUpdater().replace_release_info(readme, *branch_view(gh, branch))


@pytest.fixture
def remote(tmp_path):
    return make_remote(tmp_path, "api", {
        "README.md": MAIN_README,
        "CHANGELOG/CHANGELOG-r1.md": "# r1.2\n",
    })


def run(tmp_path, remote, gh, tag="r1.3", base_branch="main", work="api"):
    return create_sync_pr(gh, git_ops(remote, tmp_path / work), tag, "release-bot[bot]",
                          "7+release-bot[bot]@users.noreply.github.com", base_branch=base_branch)


def remote_file(remote, branch, path):
    return git(remote, "show", f"{branch}:{path}")


def tag_files(tag="r1.3", **files):
    return {(tag, path): content for path, content in files.items()}


def test_main_view_and_cycle_changelog(tmp_path, remote):
    gh = FakeGitHub(files={
        ("r1.3", "release-metadata.yaml"): metadata("r1.3"),
        ("r1.3", "CHANGELOG/CHANGELOG-r1.md"): "# r1.3\n\n# r1.2\n",
    })

    outcome = run(tmp_path, remote, gh)

    assert outcome == SyncPrOutcome(
        status="created", pr_url="https://github.com/camaraproject/Example/pull/31", pr_number="31"
    )
    readme = remote_file(remote, "pr-to-main/r1.3", "README.md")
    assert readme == rendered(gh, "main").rstrip("\n")
    assert "The latest public release is [r1.3](https://github.com/camaraproject/Example/releases/tag/r1.3)" in readme
    assert readme.startswith("# Example\n\nIntro.\n\n") and readme.endswith("Footer.")
    assert remote_file(remote, "pr-to-main/r1.3", "CHANGELOG/CHANGELOG-r1.md") == "# r1.3\n\n# r1.2"
    assert git(remote, "log", "-1", "--format=%s|%an|%ae|%cn", "pr-to-main/r1.3") == (
        "chore: post-release sync for r1.3|release-bot[bot]|"
        "7+release-bot[bot]@users.noreply.github.com|release-bot[bot]"
    )
    assert git(remote, "rev-parse", "pr-to-main/r1.3~1") == git(remote, "rev-parse", "main")
    assert gh.created == [{
        "title": "Release Automation: Post-release sync (r1.3)",
        "body": PR_BODY,
        "head": "pr-to-main/r1.3",
        "base": "main",
    }]
    assert gh.created_labels == ["post-release", "automated"]
    assert gh.labelled == [(31, ["post-release", "automated"])]


def test_main_view_names_the_highest_public_release_not_the_published_one(tmp_path, remote):
    # r1.4 published from maintenance/r1 after r2.1: main keeps r2.1
    gh = FakeGitHub(releases=("r1.3", "r2.1", "r1.4"),
                    files={("r1.4", "CHANGELOG/CHANGELOG-r1.md"): "# r1.4\n"})

    assert run(tmp_path, remote, gh, tag="r1.4").status == "created"
    readme = remote_file(remote, "pr-to-main/r1.4", "README.md")
    assert "The latest public release is [r2.1]" in readme


def test_tag_readme_is_not_copied(tmp_path, remote):
    gh = FakeGitHub(files={("r1.3", "README.md"): f"# Example\n\n{START}\nThis is release r1.3.\n{END}\n"})

    run(tmp_path, remote, gh)
    assert "This is release r1.3." not in remote_file(remote, "pr-to-main/r1.3", "README.md")


def test_flat_changelog_on_the_tag_is_not_synced(tmp_path, remote, capsys):
    gh = FakeGitHub(files=tag_files(**{"CHANGELOG.md": "# Changelog\n"}))

    run(tmp_path, remote, gh)
    assert "::warning::No CHANGELOG found at CHANGELOG/CHANGELOG-r1.md on tag r1.3" in capsys.readouterr().out


def test_cycle_changelog_directory_is_created(tmp_path):
    remote = make_remote(tmp_path, "api", {"README.md": MAIN_README})
    gh = FakeGitHub(releases=("r2.1",), files=tag_files("r2.1", **{"CHANGELOG/CHANGELOG-r2.md": "# r2.1\n"}))

    assert run(tmp_path, remote, gh, tag="r2.1").status == "created"
    assert remote_file(remote, "pr-to-main/r2.1", "CHANGELOG/CHANGELOG-r2.md") == "# r2.1"


def test_readme_without_delimiters_is_left_alone(tmp_path, capsys):
    remote = make_remote(tmp_path, "api", {"README.md": "# Example\n"})
    gh = FakeGitHub(files=tag_files(**{"CHANGELOG/CHANGELOG-r1.md": "# c\n"}))

    assert run(tmp_path, remote, gh).status == "created"
    assert "::warning::README.md on main has no release information delimiters" in capsys.readouterr().out
    assert remote_file(remote, "pr-to-main/r1.3", "README.md") == "# Example"


def test_nothing_to_sync_is_no_changes(tmp_path, capsys):
    remote = make_remote(tmp_path, "api", {"README.md": "# Example\n"})
    gh = FakeGitHub()

    assert run(tmp_path, remote, gh) == SyncPrOutcome(status="no_changes")
    assert "::warning::No content changes to sync" in capsys.readouterr().out
    assert gh.created == []


def test_identical_content_is_no_changes(tmp_path, capsys):
    gh = FakeGitHub(files=tag_files(**{"CHANGELOG/CHANGELOG-r1.md": "# r1.2\n"}))
    remote = make_remote(tmp_path, "api", {
        "README.md": rendered(gh, "main"),
        "CHANGELOG/CHANGELOG-r1.md": "# r1.2\n",
    })

    assert run(tmp_path, remote, gh) == SyncPrOutcome(status="no_changes")
    assert "::warning::No actual file changes detected" in capsys.readouterr().out
    assert gh.created == []


def test_pr_creation_failure_is_failed(tmp_path, remote, capsys):
    gh = FakeGitHub(fail_create=True)

    assert run(tmp_path, remote, gh) == SyncPrOutcome(status="failed")
    assert "::error::Failed to create post-release sync PR" in capsys.readouterr().out


def test_label_failure_is_a_warning(tmp_path, remote, capsys):
    gh = FakeGitHub(fail_labels=True)

    assert run(tmp_path, remote, gh).status == "created"
    assert "::warning::Could not add labels post-release, automated to #31" in capsys.readouterr().out


def test_clone_failure_is_failed(tmp_path, capsys):
    outcome = run(tmp_path, tmp_path / "missing.git", FakeGitHub())

    assert outcome == SyncPrOutcome(status="failed")
    assert "::error::Failed to create post-release sync PR" in capsys.readouterr().out


def test_push_failure_is_failed(tmp_path, remote, capsys):
    # A pre-receive hook rejecting every push stands in for a protected or unreachable remote.
    hook = remote / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    gh = FakeGitHub()

    assert run(tmp_path, remote, gh) == SyncPrOutcome(status="failed")
    assert gh.created == []
    assert "::error::Failed to create post-release sync PR" in capsys.readouterr().out


# ── re-runs: the pr-to-main/<tag> branch may already exist ───────────────────


def test_existing_branch_from_an_earlier_run_is_rebuilt(tmp_path, remote):
    push_branch(remote, tmp_path, "pr-to-main/r1.3", {"README.md": "half-done\n"})
    gh = FakeGitHub()

    assert run(tmp_path, remote, gh).status == "created"
    assert remote_file(remote, "pr-to-main/r1.3", "README.md") == rendered(gh, "main").rstrip("\n")
    assert git(remote, "rev-parse", "pr-to-main/r1.3~1") == git(remote, "rev-parse", "main")


def test_existing_open_pr_is_reused(tmp_path, remote):
    push_branch(remote, tmp_path, "pr-to-main/r1.3", {"README.md": "kept\n"})
    gh = FakeGitHub(open_prs={"pr-to-main/r1.3": (29, "https://github.com/camaraproject/Example/pull/29")})

    assert run(tmp_path, remote, gh) == SyncPrOutcome(
        status="created", pr_url="https://github.com/camaraproject/Example/pull/29", pr_number="29"
    )
    assert remote_file(remote, "pr-to-main/r1.3", "README.md") == "kept"
    assert gh.created == []


# ── case B: into the maintenance branch and main (M9, spec 7.1) ──────────────

MB = "maintenance/r1"


def line_repo():
    return FakeGitHub(releases=("r1.9", "r2.1", "r1.10"), files={
        ("r1.10", "release-metadata.yaml"): metadata("r1.10", "maintenance-release"),
        ("r1.10", "CHANGELOG/CHANGELOG-r1.md"): "# r1.10\n\n# r1.9\n",
    })


def test_case_b_maintenance_branch_gets_the_view_of_its_release_cycle(tmp_path, remote):
    push_branch(remote, tmp_path, MB, {"README.md": MAIN_README, "CHANGELOG/CHANGELOG-r1.md": "# r1.9\n"})
    gh = line_repo()

    assert run(tmp_path, remote, gh, tag="r1.10", base_branch=MB).status == "created"
    branch = "pr-to-maintenance/r1/r1.10"
    assert git(remote, "rev-parse", f"{branch}~1") == git(remote, "rev-parse", MB)
    readme = remote_file(remote, branch, "README.md")
    assert readme == rendered(gh, MB).rstrip("\n")
    assert "This is the maintenance branch of release cycle r1" in readme
    assert "The latest release of release cycle r1 is [r1.10]" in readme
    assert remote_file(remote, branch, "CHANGELOG/CHANGELOG-r1.md") == "# r1.10\n\n# r1.9"
    (created,) = gh.created
    assert (created["head"], created["base"]) == (branch, MB)
    assert created["title"] == f"Release Automation: Post-release sync (r1.10) into {MB}"
    assert "README.md Release Information section" in created["body"]


def test_case_b_main_gets_the_repository_view(tmp_path, remote):
    gh = line_repo()

    assert run(tmp_path, remote, gh, tag="r1.10").status == "created"
    readme = remote_file(remote, "pr-to-main/r1.10", "README.md")
    assert "The latest public release is [r2.1]" in readme
    assert remote_file(remote, "pr-to-main/r1.10", "CHANGELOG/CHANGELOG-r1.md") == "# r1.10\n\n# r1.9"
    assert gh.created[0]["title"] == "Release Automation: Post-release sync (r1.10)"
