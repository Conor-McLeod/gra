"""End-to-end tests for `gra new resource`, with a fake `ntn` on PATH."""

import json
import os
import stat
import sys

import pytest
from typer.testing import CliRunner

from gra.cli import app

PAGE_URL = "https://app.notion.com/p/3fea39e73411819ebc7ec5b1761f5e2e"

PAGE = {
    "object": "page",
    "id": "3fea39e7-3411-819e-bc7e-c5b1761f5e2e",
    "parent": {
        "type": "data_source_id",
        "data_source_id": "3f3a39e7-3411-8095-80f7-000b7e21a5bd",
        "database_id": "3f3a39e7-3411-802a-b0b1-c942a2416bb7",
    },
    "properties": {
        "Title": {"type": "title", "title": [{"plain_text": "Introduction to tensor core arithmetic"}]},
        "URL": {
            "type": "url",
            "url": "https://simonveitner.substack.com/p/introduction-to-tensor-core-arithmetic",
        },
        "Type": {"type": "select", "select": {"name": "article"}},
        "Topic": {
            "type": "multi_select",
            "multi_select": [{"name": "GPU kernels"}, {"name": "hardware architecture"}],
        },
        "Status": {"type": "status", "status": {"name": "Inbox"}},
    },
}


@pytest.fixture
def fake_ntn(tmp_path, monkeypatch):
    """Install a fake `ntn` that prints ``stdout``/``stderr`` and exits with ``code``."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    def install(stdout="", stderr="", code=0):
        script = bin_dir / "ntn"
        script.write_text(
            f"#!{sys.executable}\n"
            "import sys\n"
            f"sys.stdout.write({stdout!r})\n"
            f"sys.stderr.write({stderr!r})\n"
            f"sys.exit({code})\n"
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC)

    return install


@pytest.fixture
def vault_dir(tmp_path):
    root = tmp_path / "vault"
    (root / "Resources").mkdir(parents=True)
    return root


def run(*args):
    return CliRunner().invoke(app, ["new", "resource", *args])


def test_writes_note(fake_ntn, vault_dir):
    fake_ntn(stdout=json.dumps(PAGE))
    result = run(PAGE_URL, "--vault", str(vault_dir))
    assert result.exit_code == 0, result.output

    note = (vault_dir / "Resources" / "Introduction to tensor core arithmetic.md").read_text()
    lines = note.splitlines()
    assert lines[0] == "---"
    assert lines[1].startswith("created at: 20")
    assert lines[2:] == [
        "domain:",
        "  - GPU kernels",
        "  - hardware architecture",
        "resource: article",
        "notion: https://app.notion.com/p/3fea39e73411819ebc7ec5b1761f5e2e",
        "url: https://simonveitner.substack.com/p/introduction-to-tensor-core-arithmetic",
        "title: Introduction to tensor core arithmetic",
        "---",
    ]


def test_refuses_to_overwrite(fake_ntn, vault_dir):
    fake_ntn(stdout=json.dumps(PAGE))
    existing = vault_dir / "Resources" / "Introduction to tensor core arithmetic.md"
    existing.write_text("mine")
    result = run(PAGE_URL, "--vault", str(vault_dir))
    assert result.exit_code == 1
    assert "already exists" in result.output
    assert existing.read_text() == "mine"


def test_missing_folder(fake_ntn, tmp_path):
    fake_ntn(stdout=json.dumps(PAGE))
    result = run(PAGE_URL, "--vault", str(tmp_path))
    assert result.exit_code == 1
    assert "Resources does not exist" in result.output


def test_bad_ref(vault_dir):
    result = run("https://example.com/nope", "--vault", str(vault_dir))
    assert result.exit_code == 1
    assert "not a Notion page URL or ID" in result.output


def test_ntn_missing(vault_dir, monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    result = run(PAGE_URL, "--vault", str(vault_dir))
    assert result.exit_code == 1
    assert "`ntn` is not installed" in result.output


def test_not_signed_in(fake_ntn, vault_dir):
    fake_ntn(stderr="error: not logged in\n", code=1)
    result = run(PAGE_URL, "--vault", str(vault_dir))
    assert result.exit_code == 1
    assert "not logged in" in result.output
    assert "ntn login" in result.output


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("object_not_found", "was not found"),
        ("unauthorized", "ntn login"),
        ("restricted_resource", "no access"),
    ],
)
def test_api_errors(fake_ntn, vault_dir, code, message):
    body = json.dumps({"object": "error", "status": 404, "code": code, "message": "x"})
    fake_ntn(stdout=body, code=1)
    result = run(PAGE_URL, "--vault", str(vault_dir))
    assert result.exit_code == 1
    assert message in result.output


def test_not_in_resources(fake_ntn, vault_dir):
    other = {**PAGE, "parent": {"type": "page_id", "page_id": "00000000-0000-0000-0000-000000000000"}}
    fake_ntn(stdout=json.dumps(other))
    result = run(PAGE_URL, "--vault", str(vault_dir))
    assert result.exit_code == 1
    assert "not in the MLSys resources database" in result.output


def test_no_topic_warns(fake_ntn, vault_dir):
    page = json.loads(json.dumps(PAGE))
    page["properties"]["Topic"]["multi_select"] = []
    fake_ntn(stdout=json.dumps(page))
    result = run(PAGE_URL, "--vault", str(vault_dir))
    assert result.exit_code == 0, result.output
    assert "Needs a domain" in result.output
    note = (vault_dir / "Resources" / "Introduction to tensor core arithmetic.md").read_text()
    assert "domain:\nresource:" in note
