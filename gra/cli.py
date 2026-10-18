"""gra command-line interface."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from gra import github, vault

app = typer.Typer(
    add_completion=False,
    help="A small CLI for creating new pages in my Obsidian vault.",
    no_args_is_help=True,
)

new_app = typer.Typer(
    help="Create a new page from a template.",
    no_args_is_help=True,
)
app.add_typer(new_app, name="new")

# Folders (relative to the vault root) that GitHub notes go in.
GITHUB_DIR = "Issues and PRs"
REPOS_DIR = "Repos"

# Body of a repo note: an embedded Base listing the PR/issue notes whose
# `repo` matches this note's, so the repo page acts as a hub for them.
REPO_BODY = """
```base
filters:
  and:
    - note.repo == this.repo
    - note.github != "repo"
views:
  - type: table
    name: PRs and issues
    order:
      - note.github
      - note.number
      - note.title
      - note.author
      - note.opened
    sort:
      - property: note.opened
        direction: DESC
```
"""

VaultOption = Annotated[
    Path,
    typer.Option(
        "--vault",
        envvar="GRA_VAULT",
        help="Root of the Obsidian vault.",
    ),
]

DomainOption = Annotated[
    list[str] | None,
    typer.Option(
        "--domain",
        "-d",
        help="Subject the note is about (repeatable), e.g. -d cuda -d cpp.",
    ),
]


@app.callback()
def main() -> None:
    """A small CLI for creating new pages in my Obsidian vault."""


def _err(message: str) -> typer.Exit:
    """Print an error to stderr and return an Exit(1) to raise."""
    typer.secho(f"Error: {message}", fg=typer.colors.RED, err=True)
    return typer.Exit(code=1)


def _warn(message: str) -> None:
    """Print a warning to stderr."""
    typer.secho(f"Warning: {message}", fg=typer.colors.YELLOW, err=True)


@new_app.command("gh")
def new_gh(
    url: Annotated[
        str,
        typer.Argument(help="URL of the GitHub repository, pull request or issue."),
    ],
    domain: DomainOption = None,
    vault_dir: VaultOption = vault.DEFAULT_VAULT,
) -> None:
    """Create a note for a GitHub repository, pull request or issue.

    A PR/issue note is written to "Issues and PRs/OWNER-REPO-NUMBER.md" with
    an empty body. A repo note is written to "Repos/OWNER-REPO.md" with an
    embedded Base listing that repo's PR/issue notes. Frontmatter is filled
    from GitHub, using only fields that never change.
    """
    try:
        ref = github.parse_url(url)
    except ValueError as exc:
        raise _err(str(exc))

    # The file name comes from the URL alone, so check it before fetching.
    if ref.kind == "repo":
        path = vault_dir.expanduser() / REPOS_DIR / f"{ref.owner}-{ref.repo}.md"
    else:
        path = vault_dir.expanduser() / GITHUB_DIR / f"{ref.owner}-{ref.repo}-{ref.number}.md"
    try:
        vault.check_writable(path)
    except (FileExistsError, FileNotFoundError) as exc:
        raise _err(str(exc))

    try:
        data = github.fetch(ref)
    except RuntimeError as exc:
        raise _err(str(exc))

    if not domain:
        _warn("no --domain given; the note will show up under 'Needs a domain'")

    frontmatter: dict[str, object] = {
        "created at": vault.now(),
        "domain": domain or None,
        "github": ref.kind,
        "url": data["url"],
        "repo": ref.slug,
    }
    if ref.kind == "repo":
        parent = data.get("parent")
        frontmatter |= {
            "owner": ref.owner,
            "fork of": f"{parent['owner']['login']}/{parent['name']}" if parent else None,
        }
        body = REPO_BODY
    else:
        frontmatter |= {
            "number": data["number"],
            "title": data["title"],
            "author": (data.get("author") or {}).get("login", ""),
            "opened": vault.to_local(data["createdAt"]),
        }
        body = ""

    try:
        vault.write_page(path, vault.render(frontmatter, body))
    except (FileExistsError, FileNotFoundError) as exc:
        raise _err(str(exc))

    typer.secho(f"Created {path}", fg=typer.colors.GREEN)
