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

# Folder (relative to the vault root) that GitHub PR/issue notes go in.
GITHUB_DIR = "Issues and PRs"

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
        typer.Argument(help="URL of the GitHub pull request or issue."),
    ],
    domain: DomainOption = None,
    vault_dir: VaultOption = vault.DEFAULT_VAULT,
) -> None:
    """Create a note for a GitHub pull request or issue.

    The note is written to "Issues and PRs/OWNER-REPO-NUMBER.md" with
    frontmatter filled from GitHub (only fields that never change), and an
    empty body.
    """
    try:
        ref = github.parse_url(url)
    except ValueError as exc:
        raise _err(str(exc))

    # The file name comes from the URL alone, so check it before fetching.
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
        "number": data["number"],
        "title": data["title"],
        "author": (data.get("author") or {}).get("login", ""),
        "opened": vault.to_local(data["createdAt"]),
    }

    try:
        vault.write_page(path, vault.render(frontmatter))
    except (FileExistsError, FileNotFoundError) as exc:
        raise _err(str(exc))

    typer.secho(f"Created {path}", fg=typer.colors.GREEN)
