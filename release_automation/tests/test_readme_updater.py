"""
Unit tests for the README release information updater.

Three views of the delimited block: a release tag describes that release
(tag_view), main shows the repository view and maintenance/rX the view of
its release cycle (branch_view, from the GitHub release list).
"""

from pathlib import Path

import pytest
import yaml

from release_automation.scripts.readme_updater import (
    ReadmeUpdater,
    ReadmeUpdateError,
    branch_view,
    tag_view,
)
from release_automation.tests.fake_github import FakeGitHub

START = "<!-- CAMARA:RELEASE-INFO:START -->"
END = "<!-- CAMARA:RELEASE-INFO:END -->"
REPO = "camaraproject/DeviceLocation"
BASE = "https://github.com/camaraproject/DeviceLocation"


def render(view_and_data):
    view, data = view_and_data
    return ReadmeUpdater().render(view, data)


# --- Fixtures ---


@pytest.fixture
def updater():
    return ReadmeUpdater()


@pytest.fixture
def readme_with_delimiters(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(
        "# My API\n\nSome introduction.\n\n"
        f"{START}\n"
        "## Release Information\n\n"
        "Old release info here.\n"
        f"{END}\n\n"
        "## Contributing\n\nContribution guidelines.\n"
    )
    return str(readme)


@pytest.fixture
def readme_no_delimiters(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(
        "# My API\n\nSome introduction.\n\n"
        "## Release Information\n\n"
        "Manual release info.\n\n"
        "## Contributing\n\nContribution guidelines.\n"
    )
    return str(readme)


# --- Delimiter Checking ---


class TestDelimiterChecking:
    def test_both_delimiters_present_passes(self, updater):
        updater._check_delimiters(f"before\n{START}\ncontent\n{END}\nafter\n")

    def test_missing_start_delimiter_raises_error(self, updater):
        with pytest.raises(ReadmeUpdateError, match="start delimiter"):
            updater._check_delimiters(f"before\n{END}\nafter\n")

    def test_missing_end_delimiter_raises_error(self, updater):
        with pytest.raises(ReadmeUpdateError, match="end delimiter"):
            updater._check_delimiters(f"before\n{START}\nafter\n")

    def test_missing_both_delimiters_raises_error(self, updater):
        with pytest.raises(ReadmeUpdateError, match="missing both"):
            updater._check_delimiters("# README\n\nNo delimiters here.\n")


# --- Block replacement ---


class TestReplaceReleaseInfo:
    def test_replaces_only_the_block(self, updater):
        content = f"# Title\n\n{START}\nold\n{END}\n\n## Footer\n"
        result = updater.replace_release_info(content, *tag_view(REPO, "r1.1", "pre-release-alpha", {}))
        assert result.startswith(f"# Title\n\n{START}\n")
        assert result.endswith(f"{END}\n\n## Footer\n")
        assert "old" not in result

    def test_missing_delimiters_raise(self, updater):
        with pytest.raises(ReadmeUpdateError):
            updater.replace_release_info("# Title\n", *tag_view(REPO, "r1.1", "pre-release-alpha", {}))

    def test_unknown_view_raises_value_error(self, updater):
        with pytest.raises(ValueError, match="Invalid view"):
            updater.render("no_such_view", {})

    def test_block_says_it_is_generated(self):
        text = render(tag_view(REPO, "r1.1", "pre-release-alpha", {}))
        assert "release automation" in text
        assert "project-administration" not in text


# --- API Link Formatting ---


class TestApiLinkFormatting:
    def test_format_single_api(self):
        result = ReadmeUpdater.format_api_links(
            [{"file_name": "quality-on-demand", "version": "1.1.0"}], "QualityOnDemand", "r3.2"
        )
        assert "**quality-on-demand 1.1.0**" in result
        assert "[[YAML]]" in result
        assert "[[ReDoc]]" in result
        assert "[[Swagger]]" in result

    def test_format_zero_apis_returns_empty(self):
        assert ReadmeUpdater.format_api_links([], "QualityOnDemand", "r3.2") == ""

    def test_format_api_links_url_patterns(self):
        result = ReadmeUpdater.format_api_links(
            [{"file_name": "my-api", "version": "1.0.0"}], "TestRepo", "r4.1", org="myorg"
        )
        assert "https://github.com/myorg/TestRepo/blob/r4.1/code/API_definitions/my-api.yaml" in result
        assert ("https://redocly.github.io/redoc/?url=https://raw.githubusercontent.com/myorg/TestRepo/r4.1/"
                "code/API_definitions/my-api.yaml&nocors") in result
        assert ("https://camaraproject.github.io/swagger-ui/?url=https://raw.githubusercontent.com/myorg/TestRepo/"
                "r4.1/code/API_definitions/my-api.yaml") in result


# --- Tag view: the release itself ---


class TestTagView:
    def test_describes_the_release(self):
        text = render(tag_view(REPO, "r1.3", "maintenance-release", {"location-verification": "1.0.1"}))
        assert (
            f"This is release [r1.3]({BASE}/releases/tag/r1.3) of DeviceLocation, a maintenance release, "
            "with the following API versions:"
        ) in text
        assert "**location-verification 1.0.1**" in text
        assert f"{BASE}/blob/r1.3/code/API_definitions/location-verification.yaml" in text

    def test_links_the_release_cycle_changelog_on_the_tag_and_main_for_later_changes(self):
        text = render(tag_view(REPO, "r1.3", "maintenance-release", {}))
        assert f"For changes in this release see [CHANGELOG-r1.md]({BASE}/blob/r1.3/CHANGELOG/CHANGELOG-r1.md)" in text
        assert f"{BASE}/releases/latest" in text
        assert f"for changes in later releases see [CHANGELOG on main]({BASE}/tree/main/CHANGELOG)" in text

    def test_makes_no_statement_about_the_repository(self):
        text = render(tag_view(REPO, "r2.1", "public-release", {"location-verification": "1.0.0"}))
        assert "The latest public release is [" not in text
        assert "Upcoming Release Preview" not in text
        assert "main branch" not in text
        assert "a public release" in text

    @pytest.mark.parametrize("release_type,wording", [
        ("pre-release-alpha", "a pre-release"),
        ("pre-release-rc", "a release candidate"),
    ])
    def test_pre_releases_carry_a_note(self, release_type, wording):
        text = render(tag_view(REPO, "r3.1", release_type, {}))
        assert wording in text
        assert "> [!NOTE]" in text
        assert "may change before the public release" in text

    def test_public_release_has_no_note(self):
        assert "[!NOTE]" not in render(tag_view(REPO, "r2.1", "public-release", {}))


# --- update_release_info (file) ---


class TestUpdateReleaseInfo:
    def test_update_modifies_only_the_block(self, updater, readme_with_delimiters):
        changed = updater.update_release_info(readme_with_delimiters, *tag_view(REPO, "r2.1", "public-release", {}))
        assert changed is True
        content = Path(readme_with_delimiters).read_text()
        assert "This is release [r2.1]" in content
        assert "Old release info" not in content
        assert "# My API" in content
        assert "## Contributing" in content

    def test_idempotent_update_returns_false(self, updater, readme_with_delimiters):
        view = tag_view(REPO, "r2.1", "public-release", {})
        updater.update_release_info(readme_with_delimiters, *view)
        assert updater.update_release_info(readme_with_delimiters, *view) is False

    def test_missing_delimiters_raises_error(self, updater, readme_no_delimiters):
        with pytest.raises(ReadmeUpdateError):
            updater.update_release_info(readme_no_delimiters, *tag_view(REPO, "r2.1", "public-release", {}))


# --- Branch views: from the GitHub release list ---

MAPPINGS = ("camaraproject/project-administration", "config/meta-release-mappings.yaml")


def release(tag, prerelease=False):
    return {"tag": tag, "draft": False, "prerelease": prerelease, "html_url": f"{BASE}/releases/tag/{tag}"}


def metadata(tag, release_type, apis=None):
    return yaml.safe_dump({
        "repository": {"repository_name": "DeviceLocation", "release_tag": tag, "release_type": release_type},
        "apis": [{"api_name": n, "api_version": v} for n, v in (apis or {}).items()],
    })


def repo(releases, files=None, mappings=None):
    """Releases in publication order; metadata per tag in files."""
    fake = FakeGitHub(releases=releases, files=files or {},
                      repository_files={MAPPINGS: mappings} if mappings is not None else {})
    fake.repo = REPO
    return fake


class TestMainView:
    def test_no_release(self):
        text = render(branch_view(repo([]), "main"))
        assert "no (pre)releases yet" in text

    def test_pre_releases_only(self):
        gh = repo([release("r1.1", True), release("r1.2", True)],
                  {("r1.2", "release-metadata.yaml"): metadata("r1.2", "pre-release-rc", {"location-verification": "0.2.0-rc.1"})})
        text = render(branch_view(gh, "main"))
        assert f"The latest pre-release is [r1.2]({BASE}/releases/tag/r1.2) (release candidate)" in text
        assert "**location-verification 0.2.0-rc.1**" in text

    def test_latest_public_release_is_the_highest_tag(self):
        # r1.4 (maintenance on maintenance/r1) published after r2.1
        gh = repo([release("r1.3"), release("r2.1"), release("r1.4")],
                  {("r2.1", "release-metadata.yaml"): metadata("r2.1", "public-release", {"location-verification": "2.0.0"})})
        text = render(branch_view(gh, "main"))
        assert f"The latest public release is [r2.1]({BASE}/releases/tag/r2.1), with the following API versions:" in text
        assert f"{BASE}/blob/r2.1/code/API_definitions/location-verification.yaml" in text
        assert "r1.4" not in text
        assert "Upcoming Release Preview" not in text
        assert "main branch" in text

    def test_preview_of_a_pre_release_of_a_later_cycle(self):
        gh = repo([release("r2.1"), release("r3.1", True)], {
            ("r2.1", "release-metadata.yaml"): metadata("r2.1", "public-release"),
            ("r3.1", "release-metadata.yaml"): metadata("r3.1", "pre-release-alpha", {"location-verification": "3.0.0-alpha.1"}),
        })
        text = render(branch_view(gh, "main"))
        assert "The latest public release is [r2.1]" in text
        assert "### Upcoming Release Preview" in text
        assert f"* Pre-release: [r3.1]({BASE}/releases/tag/r3.1) (alpha)" in text
        assert f"{BASE}/blob/r3.1/code/API_definitions/location-verification.yaml" in text

    def test_no_preview_for_a_pre_release_of_the_same_or_an_earlier_cycle(self):
        gh = repo([release("r2.1", True), release("r2.2")])
        assert "Upcoming Release Preview" not in render(branch_view(gh, "main"))

    def test_meta_release_from_the_mapping(self):
        gh = repo([release("r2.1"), release("r2.2")],
                  mappings={"mappings": {"Fall25": {"DeviceLocation": "r1"}, "Sync26": {"DeviceLocation": "r2"}}})
        assert f"The latest public release is [r2.2]({BASE}/releases/tag/r2.2) (Sync26)," in render(branch_view(gh, "main"))

    def test_no_meta_release_without_a_mapping_entry(self, capsys):
        gh = repo([release("r2.1")], mappings={"mappings": {"Fall25": {"DeviceLocation": "r1"}}})
        text = render(branch_view(gh, "main"))
        assert "The latest public release is [r2.1]" in text
        assert "()" not in text and "(Fall25)" not in text

    def test_no_meta_release_when_the_mapping_cannot_be_read(self, capsys):
        text = render(branch_view(repo([release("r2.1")]), "main"))
        assert f"The latest public release is [r2.1]({BASE}/releases/tag/r2.1), with" in text
        assert "meta-release mappings" in capsys.readouterr().out

    def test_mapping_not_read_without_a_public_release(self):
        gh = repo([release("r1.1", True)])
        branch_view(gh, "main")
        assert "get_repository_yaml_file" not in gh.calls


class TestMaintenanceBranchView:
    def test_latest_release_of_the_cycle_with_a_warning(self):
        gh = repo([release("r1.6"), release("r1.7"), release("r2.1"), release("r1.8")], {
            ("r1.8", "release-metadata.yaml"): metadata("r1.8", "maintenance-release", {"location-verification": "1.0.2"}),
        }, mappings={"mappings": {"Fall25": {"DeviceLocation": "r1"}}})
        text = render(branch_view(gh, "maintenance/r1"))
        assert "> [!WARNING]" in text
        assert "This is the maintenance branch of release cycle r1, not the main branch." in text
        assert (f"* The latest release of release cycle r1 is [r1.8]({BASE}/releases/tag/r1.8) (maintenance release), "
                "with the following API versions:") in text
        assert f"{BASE}/blob/r1.8/code/API_definitions/location-verification.yaml" in text
        assert f"[CHANGELOG-r1.md]({BASE}/blob/maintenance/r1/CHANGELOG/CHANGELOG-r1.md)" in text
        assert f"{BASE}/releases/latest" in text
        assert "The latest public release is [" not in text
        assert "Fall25" not in text
        assert "r2.1" not in text

    def test_before_the_first_maintenance_release_the_patched_release(self):
        gh = repo([release("r1.1", True), release("r1.2"), release("r2.1")],
                  {("r1.2", "release-metadata.yaml"): metadata("r1.2", "public-release")})
        text = render(branch_view(gh, "maintenance/r1"))
        assert f"The latest release of release cycle r1 is [r1.2]({BASE}/releases/tag/r1.2) (public release)" in text
        assert "Upcoming Release Preview" not in text

    def test_preview_of_a_release_candidate_of_the_cycle(self):
        gh = repo([release("r1.2"), release("r2.1"), release("r1.3", True)],
                  {("r1.3", "release-metadata.yaml"): metadata("r1.3", "pre-release-rc")})
        text = render(branch_view(gh, "maintenance/r1"))
        assert "The latest release of release cycle r1 is [r1.2]" in text
        assert f"* Pre-release: [r1.3]({BASE}/releases/tag/r1.3) (release candidate)" in text

    def test_nothing_without_a_public_release_of_the_cycle(self):
        assert branch_view(repo([release("r1.1", True)]), "maintenance/r1") is None

    def test_nothing_for_another_branch(self):
        assert branch_view(repo([release("r1.1")]), "feature/x") is None
