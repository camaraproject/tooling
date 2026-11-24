"""
README release information updater for CAMARA release automation.

Replaces the "Release Information" section between the delimiter comments of
README.md with one of three views:

- tag_view: the README on a release tag describes that release only
- branch_view of main: the repository view (latest public release, preview of
  an upcoming pre-release), rendered from the GitHub release list
- branch_view of maintenance/rX: a warning that this is a maintenance branch
  and the latest release of release cycle rX
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pystache

from .config import MAIN_BRANCH, release_type as release_type_info
from .release_line import (
    MAINTENANCE_BRANCH_RE,
    latest_public_release,
    newest_pre_release,
    releases_of_cycle,
    tag_version,
)

ORG = "camaraproject"

# Which release cycle belongs to which meta-release: decided by Release
# Management, usually after the public release (never from release-plan.yaml)
META_RELEASE_MAPPINGS_REPO = "camaraproject/project-administration"
META_RELEASE_MAPPINGS_FILE = "config/meta-release-mappings.yaml"

# Wording of a pre-release in the Upcoming Release Preview
PRERELEASE_WORDING = {"pre-release-alpha": "alpha", "pre-release-rc": "release candidate"}


class ReadmeUpdateError(Exception):
    """Raised when README update fails (e.g., missing delimiters)."""
    pass


class ReadmeUpdater:
    """
    Renders a view of the Release Information section and replaces the
    content between the START and END delimiters of README.md with it.

    Example usage:
        updater = ReadmeUpdater()
        updater.update_release_info("README.md", *tag_view(repo, "r3.2", "public-release", api_versions))
    """

    DELIMITER_START = "<!-- CAMARA:RELEASE-INFO:START -->"
    DELIMITER_END = "<!-- CAMARA:RELEASE-INFO:END -->"

    VIEWS = {
        "tag": "release-info-tag",
        "main_no_release": "release-info-main-no-release",
        "main_prerelease_only": "release-info-main-prerelease-only",
        "main_public": "release-info-main-public",
        "main_public_with_prerelease": "release-info-main-public-with-prerelease",
        "maintenance_branch": "release-info-maintenance-branch",
    }

    DEFAULT_TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "readme"

    def __init__(self, template_dir: Optional[str] = None):
        """Initialize with path to templates directory.

        Args:
            template_dir: Custom template directory path.
                         Defaults to release_automation/templates/readme/
        """
        self.template_dir = Path(template_dir) if template_dir else self.DEFAULT_TEMPLATE_DIR
        self.renderer = pystache.Renderer(
            missing_tags='ignore',  # Templates may omit optional fields
            escape=lambda x: x,     # Don't HTML-escape (markdown context)
        )

    def update_release_info(self, readme_path: str, view: str, data: Dict[str, Any]) -> bool:
        """Replace the block in a README file; True if the file changed.

        Raises:
            ReadmeUpdateError: If delimiters are missing from README
            ValueError: If view is unknown
            FileNotFoundError: If readme_path does not exist
        """
        readme = Path(readme_path)
        content = readme.read_text()
        new_content = self.replace_release_info(content, view, data)
        if new_content == content:
            return False
        readme.write_text(new_content)
        return True

    def replace_release_info(self, content: str, view: str, data: Dict[str, Any]) -> str:
        """README content with the block replaced by the rendered view.

        Raises:
            ReadmeUpdateError: If delimiters are missing from content
            ValueError: If view is unknown
        """
        self._check_delimiters(content)
        return self._replace_delimited_content(content, self.render(view, data))

    def _check_delimiters(self, content: str) -> None:
        """Verify START and END delimiters exist in content.

        Raises:
            ReadmeUpdateError: With actionable message if delimiters are missing.
        """
        has_start = self.DELIMITER_START in content
        has_end = self.DELIMITER_END in content

        if not has_start and not has_end:
            raise ReadmeUpdateError(
                "README is missing both release information delimiters. "
                f"Add '{self.DELIMITER_START}' and '{self.DELIMITER_END}' "
                "markers to your README.md to define the release information section."
            )
        if not has_start:
            raise ReadmeUpdateError(
                f"README is missing the start delimiter '{self.DELIMITER_START}'. "
                "Both START and END delimiters are required."
            )
        if not has_end:
            raise ReadmeUpdateError(
                f"README is missing the end delimiter '{self.DELIMITER_END}'. "
                "Both START and END delimiters are required."
            )

    def render(self, view: str, data: Dict[str, Any]) -> str:
        """Render one view's template with its data."""
        if view not in self.VIEWS:
            raise ValueError(f"Invalid view: '{view}'. Must be one of: {', '.join(self.VIEWS)}")
        template_name = self.VIEWS[view]
        template_path = self.template_dir / f"{template_name}.mustache"
        if not template_path.exists():
            raise ReadmeUpdateError(
                f"Template not found: {template_name}.mustache (looked in {self.template_dir})"
            )
        return self.renderer.render(template_path.read_text(), data)

    def _replace_delimited_content(self, content: str, new_content: str) -> str:
        """Replace text between START and END delimiters with new content.

        Preserves delimiter lines. Returns full file content with replacement.
        """
        pattern = re.compile(
            re.escape(self.DELIMITER_START) + r"\n.*?" + re.escape(self.DELIMITER_END),
            re.DOTALL,
        )
        replacement = f"{self.DELIMITER_START}\n{new_content}{self.DELIMITER_END}"
        return pattern.sub(replacement, content)

    @staticmethod
    def format_api_links(
        apis: List[Dict[str, str]],
        repo_name: str,
        release_tag: str,
        org: str = ORG,
    ) -> str:
        """Format API list with YAML/ReDoc/Swagger links as pre-rendered markdown.

        This generates the complex multi-line structure that Mustache cannot handle.

        Args:
            apis: List of dicts with 'file_name' and 'version' keys
            repo_name: Repository name (e.g., "QualityOnDemand")
            release_tag: Release tag for URL construction (e.g., "r3.2")
            org: GitHub organization

        Returns:
            Pre-formatted markdown string with API entries and links.
        """
        if not apis:
            return ""

        lines = []
        for api in apis:
            file_name = api["file_name"]
            version = api["version"]
            base = f"https://github.com/{org}/{repo_name}"
            raw = f"https://raw.githubusercontent.com/{org}/{repo_name}"
            yaml_path = f"code/API_definitions/{file_name}.yaml"

            lines.append(f"  * **{file_name} {version}**")
            lines.append(
                f"  [[YAML]]({base}/blob/{release_tag}/{yaml_path})"
                f"  [[ReDoc]](https://redocly.github.io/redoc/"
                f"?url={raw}/{release_tag}/{yaml_path}&nocors)"
                f"  [[Swagger]](https://camaraproject.github.io/swagger-ui/"
                f"?url={raw}/{release_tag}/{yaml_path})"
            )

        return "\n".join(lines) + "\n"


View = Tuple[str, Dict[str, Any]]


def _repo_data(repo: str) -> Dict[str, Any]:
    org, repo_name = repo.split("/")
    return {"org": org, "repo_name": repo_name, "base_url": f"https://github.com/{org}/{repo_name}"}


def _api_links(api_versions: Dict[str, str], repo: str, release_tag: str) -> str:
    org, repo_name = repo.split("/")
    apis = [{"file_name": name, "version": version} for name, version in api_versions.items()]
    return ReadmeUpdater.format_api_links(apis, repo_name, release_tag, org)


def tag_view(repo: str, release_tag: str, release_type: str, api_versions: Dict[str, str]) -> View:
    """The block on a release tag: that release only, no statement about the repository.

    Args:
        repo: "owner/name"
        release_tag: e.g. "r1.3"
        release_type: release-metadata.yaml release_type, e.g. "maintenance-release"
        api_versions: api_name -> version of this release
    """
    info = release_type_info(release_type)
    version = tag_version(release_tag)
    return "tag", {
        **_repo_data(repo),
        "release_tag": release_tag,
        "cycle": f"r{version[0]}" if version else "",
        "release_type_description": info.description if info else release_type,
        "prerelease": bool(info and info.prerelease),
        "formatted_apis": _api_links(api_versions, repo, release_tag),
    }


def _published(gh, repo: str, tag: str) -> Tuple[str, str]:
    """(release_type, formatted API links) of a published release, from its release-metadata.yaml."""
    org, repo_name = repo.split("/")
    metadata = gh.get_release_metadata(tag) or {}
    release_type = (metadata.get("repository") or {}).get("release_type", "")
    apis = [
        {"file_name": api.get("api_file_name", api.get("api_name", "")), "version": api.get("api_version", "")}
        for api in metadata.get("apis") or []
    ]
    return release_type, ReadmeUpdater.format_api_links(apis, repo_name, tag, org)


def _preview(gh, repo: str, release) -> Dict[str, Any]:
    release_type, apis = _published(gh, repo, release.tag_name)
    return {
        "newest_prerelease": release.tag_name,
        "prerelease_type": PRERELEASE_WORDING.get(release_type, ""),
        "formatted_prerelease_apis": apis,
    }


def meta_release_of(gh, repo_name: str, cycle: int) -> str:
    """The meta-release the mappings assign release cycle rX of the repository to; "" if none or unreadable."""
    content = gh.get_repository_yaml_file(META_RELEASE_MAPPINGS_REPO, META_RELEASE_MAPPINGS_FILE)
    if content is None:
        print(f"Could not read the meta-release mappings ({META_RELEASE_MAPPINGS_REPO}/{META_RELEASE_MAPPINGS_FILE}); "
              "meta-release omitted")
        return ""
    for meta_release, repositories in (content.get("mappings") or {}).items():
        if (repositories or {}).get(repo_name) == f"r{cycle}":
            return meta_release
    print(f"No meta-release mapping for {repo_name} r{cycle}; meta-release omitted")
    return ""


def _main_view(gh, repo: str, releases) -> View:
    data = _repo_data(repo)
    latest = latest_public_release(releases)
    pre = newest_pre_release(releases)
    if latest and pre and tag_version(pre.tag_name)[0] <= tag_version(latest.tag_name)[0]:
        pre = None
    if not latest:
        return ("main_prerelease_only", {**data, **_preview(gh, repo, pre)}) if pre else ("main_no_release", data)

    _, apis = _published(gh, repo, latest.tag_name)
    data.update({
        "latest_public_release": latest.tag_name,
        "meta_release": meta_release_of(gh, data["repo_name"], tag_version(latest.tag_name)[0]),
        "formatted_apis": apis,
    })
    if pre:
        return "main_public_with_prerelease", {**data, **_preview(gh, repo, pre)}
    return "main_public", data


def _maintenance_branch_view(gh, repo: str, releases, branch: str, cycle: int) -> Optional[View]:
    in_cycle = releases_of_cycle(releases, cycle)
    latest = next((r for r in in_cycle if not r.prerelease), None)
    if not latest:
        return None
    release_type, apis = _published(gh, repo, latest.tag_name)
    info = release_type_info(release_type)
    data = {
        **_repo_data(repo),
        "branch": branch,
        "cycle": f"r{cycle}",
        "latest_release": latest.tag_name,
        "latest_release_type": info.description if info else "",
        "formatted_apis": apis,
    }
    pre = next((r for r in in_cycle if r.prerelease), None)
    if pre and tag_version(pre.tag_name) > tag_version(latest.tag_name):
        data.update(_preview(gh, repo, pre))
    return "maintenance_branch", data


def branch_view(gh, branch: str) -> Optional[View]:
    """The block on main or maintenance/rX, from the repository's published releases.

    Args:
        gh: GitHub client of the API repository
        branch: "main" or "maintenance/rX"

    Returns:
        (view, data), or None when the branch has no view (another branch, or
        a maintenance branch whose cycle has no public release)
    """
    releases = gh.get_releases(include_drafts=False)
    if branch == MAIN_BRANCH:
        return _main_view(gh, gh.repo, releases)
    if MAINTENANCE_BRANCH_RE.match(branch):
        return _maintenance_branch_view(gh, gh.repo, releases, branch, int(branch.split("/r")[1]))
    return None
