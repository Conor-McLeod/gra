"""GitHub access helpers for gra.

Fetches repository, pull request and issue metadata by shelling out to the ``gh`` CLI,
so authentication (including private repos) is whatever ``gh auth login``
already set up.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

# https://github.com/OWNER/REPO/pull/123 or .../issues/123, with optional
# trailing path (/files, /commits), query string or fragment.
URL_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/"
    r"(?P<kind>pull|issues)/(?P<number>\d+)(?:[/?#].*)?$"
)

# https://github.com/OWNER/REPO, with optional trailing slash, ``.git``, query
# string or fragment. Deeper paths (/tree/main, /pull/1) are not repo URLs.
REPO_URL_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/?#]+?)(?:\.git)?/?(?:[?#].*)?$"
)

# Fields requested from `gh pr view` / `gh issue view`. Only ones that never
# change once the PR/issue exists, so notes don't go stale.
FIELDS = "url,number,title,author,createdAt"

# Fields requested from `gh repo view`. Same rule: description, topics,
# language etc. are left out because maintainers change them.
REPO_FIELDS = "url,parent"


@dataclass(frozen=True)
class Ref:
    """A repository, pull request or issue, as identified by its URL."""

    owner: str
    repo: str
    kind: str  # "repo", "pr" or "issue"
    number: int | None = None  # None for a repo

    @property
    def slug(self) -> str:
        """``owner/repo``."""
        return f"{self.owner}/{self.repo}"


def parse_url(url: str) -> Ref:
    """Parse a GitHub repository, pull request or issue URL.

    Raises ``ValueError`` if ``url`` isn't one.
    """
    url = url.strip()
    match = REPO_URL_RE.match(url)
    if match:
        return Ref(owner=match["owner"], repo=match["repo"], kind="repo")

    match = URL_RE.match(url)
    if not match:
        raise ValueError(
            f"{url!r} is not a GitHub repository, pull request or issue URL "
            "(expected https://github.com/OWNER/REPO, .../pull/N or .../issues/N)"
        )
    return Ref(
        owner=match["owner"],
        repo=match["repo"],
        kind="pr" if match["kind"] == "pull" else "issue",
        number=int(match["number"]),
    )


def fetch(ref: Ref) -> dict[str, Any]:
    """Fetch metadata for ``ref`` via ``gh``.

    Raises ``RuntimeError`` if ``gh`` is missing or the lookup fails (not
    found, no access, not logged in).
    """
    if shutil.which("gh") is None:
        raise RuntimeError("the GitHub CLI `gh` is not installed")

    if ref.kind == "repo":
        subcommand, url, fields = "repo", f"https://github.com/{ref.slug}", REPO_FIELDS
    else:
        subcommand = "pr" if ref.kind == "pr" else "issue"
        url = f"https://github.com/{ref.slug}/{'pull' if ref.kind == 'pr' else 'issues'}/{ref.number}"
        fields = FIELDS
    result = subprocess.run(
        ["gh", subcommand, "view", url, "--json", fields],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"gh {subcommand} view failed")
    return json.loads(result.stdout)
