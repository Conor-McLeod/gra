"""Notion access helpers for gra.

Fetches pages from the MLSys resources database by shelling out to Notion's
official CLI ``ntn``, so authentication is whatever ``ntn login`` already set
up (or ``NOTION_API_TOKEN``, which ``ntn`` reads itself). gra only reads from
Notion; it never writes to it.

``ntn`` is in beta, so every call to it and all reading of its output lives in
this module. It is called as ``ntn api v1/pages/ID`` with a pinned
``Notion-Version``, so the output is the documented Notion API page object
rather than ``ntn``'s own (undocumented) JSON shape.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlsplit

# Notion API version requested from `ntn api`. Pinned so the response shape
# (notably `parent.data_source_id`) doesn't change under us.
API_VERSION = "2026-03-11"

# The MLSys resources database, and its (only) data source. A page counts as
# a resource if its parent is either.
RESOURCES_DATABASE_ID = "3f3a39e7-3411-802a-b0b1-c942a2416bb7"
RESOURCES_DATA_SOURCE_ID = "3f3a39e7-3411-8095-80f7-000b7e21a5bd"

# A page ID: 32 hex digits, optionally dashed 8-4-4-4-12.
_ID = r"[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}"
ID_RE = re.compile(rf"^{_ID}$")
# The ID at the end of a URL path segment, e.g. "Some-Title-<id>" or "<id>".
SEGMENT_RE = re.compile(rf"(?:^|-)({_ID})$")

# Hosts whose URLs point at Notion pages.
HOSTS = ("notion.so", "notion.com", "notion.site")


@dataclass(frozen=True)
class Ref:
    """A Notion page, as identified by its ID."""

    id: str  # dashed UUID

    @property
    def url(self) -> str:
        """A stable link to the page (unlike Notion's own, it has no title in it)."""
        return f"https://app.notion.com/p/{self.id.replace('-', '')}"


def _normalise_id(raw: str) -> str:
    """Turn a 32-hex or dashed ID into a lowercase dashed UUID."""
    hex_id = raw.replace("-", "").lower()
    return f"{hex_id[:8]}-{hex_id[8:12]}-{hex_id[12:16]}-{hex_id[16:20]}-{hex_id[20:]}"


def _same_id(a: str | None, b: str) -> bool:
    return a is not None and a.replace("-", "").lower() == b.replace("-", "").lower()


def parse_ref(arg: str) -> Ref:
    """Parse a Notion page URL or a bare page ID.

    Accepts ``app.notion.com/p/ID``, ``notion.so/[workspace/]Title-ID`` (with
    any query string or fragment, e.g. ``?pvs=4``; a ``?p=ID`` peek link
    wins over the path), and a 32-hex or dashed ID. Raises ``ValueError``
    otherwise.
    """
    arg = arg.strip()
    if ID_RE.match(arg):
        return Ref(id=_normalise_id(arg))

    parts = urlsplit(arg if "://" in arg else f"https://{arg}")
    host = (parts.hostname or "").lower()
    if any(host == h or host.endswith(f".{h}") for h in HOSTS):
        # A database row opened as a peek: notion.so/DB?v=VIEW&p=PAGE.
        peek = parse_qs(parts.query).get("p", [""])[0]
        if ID_RE.match(peek):
            return Ref(id=_normalise_id(peek))
        segment = parts.path.rstrip("/").rsplit("/", 1)[-1]
        match = SEGMENT_RE.search(segment)
        if match:
            return Ref(id=_normalise_id(match[1]))

    raise ValueError(
        f"{arg!r} is not a Notion page URL or ID "
        "(expected https://app.notion.com/p/ID, a notion.so page URL, or a 32-character ID)"
    )


def _api_error(output: str) -> dict[str, Any] | None:
    """The Notion API error object in ``output``, if there is one."""
    try:
        data = json.loads(output)
    except ValueError:
        return None
    if isinstance(data, dict) and data.get("object") == "error":
        return data
    return None


def _error_message(error: dict[str, Any], ref: Ref) -> str:
    code = error.get("code", "")
    if code == "unauthorized":
        return "Notion rejected the credentials; sign in with `ntn login`"
    if code == "object_not_found":
        return (
            f"Notion page {ref.id} was not found, or your Notion login has no "
            "access to it"
        )
    if code == "restricted_resource":
        return f"your Notion login has no access to page {ref.id}"
    return f"Notion API error ({code or 'unknown'}): {error.get('message', '')}".rstrip(": ")


def fetch(ref: Ref) -> dict[str, Any]:
    """Fetch the Notion API page object for ``ref`` via ``ntn``.

    Raises ``RuntimeError`` if ``ntn`` is missing, you aren't signed in, the
    page isn't found or access is denied, or the page isn't in MLSys
    resources.
    """
    if shutil.which("ntn") is None:
        raise RuntimeError(
            "Notion's CLI `ntn` is not installed (see https://ntn.dev), "
            "then sign in with `ntn login`"
        )

    result = subprocess.run(
        ["ntn", "api", f"v1/pages/{ref.id}", "--notion-version", API_VERSION],
        capture_output=True,
        text=True,
    )
    # Where `ntn` puts an API error body isn't documented, so look in both.
    error = _api_error(result.stdout) or _api_error(result.stderr)
    if error is not None:
        raise RuntimeError(_error_message(error, ref))
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no output"
        raise RuntimeError(
            f"`ntn api` failed: {detail} "
            "(if you aren't signed in, run `ntn login`; `ntn doctor` checks the setup)"
        )

    try:
        page = json.loads(result.stdout)
    except ValueError:
        raise RuntimeError("`ntn api` did not return JSON; its output format may have changed")
    if not isinstance(page, dict) or page.get("object") != "page":
        raise RuntimeError(f"{ref.id} is not a Notion page")

    parent = page.get("parent") or {}
    if not (
        _same_id(parent.get("data_source_id"), RESOURCES_DATA_SOURCE_ID)
        or _same_id(parent.get("database_id"), RESOURCES_DATABASE_ID)
    ):
        raise RuntimeError(f"Notion page {ref.id} is not in the MLSys resources database")
    return page


def _property(page: dict[str, Any], name: str, kind: str) -> Any:
    """The value of property ``name`` (of type ``kind``), or ``None`` if missing/wrong type."""
    prop = (page.get("properties") or {}).get(name) or {}
    if prop.get("type") != kind:
        return None
    return prop.get(kind)


def resource_fields(page: dict[str, Any]) -> dict[str, Any]:
    """Pull the MLSys resources fields out of a Notion API page object.

    Returns ``title`` (str, may be empty), ``url`` (str or None), ``type``
    (str or None) and ``topics`` (list of str). Status is left out on
    purpose: it changes over time and stays in Notion.
    """
    title_parts = _property(page, "Title", "title") or []
    select = _property(page, "Type", "select") or {}
    topics = _property(page, "Topic", "multi_select") or []
    return {
        "title": "".join(part.get("plain_text", "") for part in title_parts).strip(),
        "url": _property(page, "URL", "url") or None,
        "type": select.get("name") or None,
        "topics": [topic["name"] for topic in topics if topic.get("name")],
    }
