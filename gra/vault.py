"""Vault helpers shared across gra templates.

Everything that is about the vault rather than any one kind of page lives
here: building ``created at``, rendering YAML frontmatter the way Obsidian and
the rest of the vault write it, and writing a new page without clobbering an
existing one.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

# Default vault location; overridable with --vault or GRA_VAULT.
DEFAULT_VAULT = Path.home() / "main-vault"


class _VaultDumper(yaml.SafeDumper):
    """SafeDumper tuned to match the vault's hand-written frontmatter.

    - list items are indented under their key (``  - cuda``), as Obsidian
      writes them;
    - ``None`` renders as an empty value (``domain:``) rather than ``null``;
    - datetimes render as unquoted ``YYYY-MM-DDTHH:mm:ss``, which Obsidian
      reads as a Date & time property.
    """

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        return super().increase_indent(flow, False)


_VaultDumper.add_representer(
    type(None),
    lambda dumper, _: dumper.represent_scalar("tag:yaml.org,2002:null", ""),
)
_VaultDumper.add_representer(
    datetime,
    lambda dumper, value: dumper.represent_scalar(
        "tag:yaml.org,2002:timestamp", value.strftime("%Y-%m-%dT%H:%M:%S")
    ),
)


def now() -> datetime:
    """The current local time, to the second, for ``created at``."""
    return datetime.now().replace(microsecond=0)


def to_local(timestamp: str) -> datetime:
    """Convert an ISO 8601 UTC timestamp (e.g. GitHub's ``...Z``) to naive local time.

    The vault stores datetimes without a timezone, in local time, so this
    keeps external timestamps comparable with ``created at``.
    """
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return parsed.astimezone().replace(tzinfo=None)


def render(frontmatter: dict[str, Any], body: str = "") -> str:
    """Render a page: ``---``-fenced YAML frontmatter followed by ``body``."""
    yaml_text = yaml.dump(
        frontmatter,
        Dumper=_VaultDumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=10_000,
    )
    return f"---\n{yaml_text}---\n{body}"


def check_writable(path: Path) -> None:
    """Check that a new page can be written at ``path``.

    Raises ``FileExistsError`` if ``path`` exists and ``FileNotFoundError`` if
    its directory doesn't (directories in the vault are created by hand).
    """
    if path.exists():
        raise FileExistsError(f"{path} already exists")
    if not path.parent.is_dir():
        raise FileNotFoundError(f"{path.parent} does not exist")


def write_page(path: Path, content: str) -> None:
    """Write a new page, refusing to overwrite an existing one."""
    check_writable(path)
    path.write_text(content, encoding="utf-8")
