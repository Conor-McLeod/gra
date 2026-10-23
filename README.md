# gra

A small CLI for creating new pages in my Obsidian vault.

Pages are written with YAML frontmatter in the format Obsidian uses and an
empty body. gra never overwrites an existing page and never creates folders:
it stops with an error if the page already exists or its folder is missing.

## Install

```sh
uv tool install .     # or: uv run gra ...
```

The vault defaults to `~/main-vault`. Set it with `--vault PATH` or the
`GRA_VAULT` environment variable.

## Commands

### `gra new gh <URL> [-d DOMAIN ...]`

Creates a note for a GitHub pull request or issue at
`Issues and PRs/OWNER-REPO-NUMBER.md`.

```sh
gra new gh https://github.com/pytorch/pytorch/pull/12345 -d cuda -d cpp
```

```yaml
created at: 2026-10-21T14:03:12
domain:
  - cuda
  - cpp
github: pr            # or issue
url: https://github.com/pytorch/pytorch/pull/12345
repo: pytorch/pytorch
number: 12345
title: ...
author: ...
opened: 2026-10-01T09:30:00
```

- Only fields that never change are copied, so notes don't go stale.
- `-d/--domain` can be repeated. Without it, gra warns that the note will
  show up under "Needs a domain".
- Requires the GitHub CLI `gh`, signed in with `gh auth login`.

### `gra new resource <NOTION-URL-OR-ID>`

Creates a note for a resource in the Notion database **MLSys resources** at
`Resources/TITLE.md`.

```sh
gra new resource https://app.notion.com/p/3fea39e73411819ebc7ec5b1761f5e2e
```

```yaml
created at: 2026-10-21T14:03:12
domain:               # from Topic
  - GPU kernels
  - hardware architecture
resource: article     # from Type
notion: https://app.notion.com/p/3fea39e73411819ebc7ec5b1761f5e2e
url: https://simonveitner.substack.com/p/introduction-to-tensor-core-arithmetic
title: Introduction to tensor core arithmetic
```

- The argument can be an `app.notion.com/p/...` or `notion.so/...` page URL
  (query strings such as `?pvs=4` are fine) or a bare page ID. gra refuses
  pages that aren't in MLSys resources.
- `domain` comes from the Notion page's Topic. Notion is the source of
  truth, so there is no `-d` option. To recategorise a resource, change its
  Topic in Notion. If the page has no Topic, gra warns that the note will
  show up under "Needs a domain".
- Status is left out on purpose. It changes over time and stays in Notion.
- The file name is the title with `/ \ : * ? " < > | # ^ [ ]` removed.
- gra only reads from Notion; it never writes to it.
- Requires Notion's CLI [`ntn`](https://ntn.dev), signed in with
  `ntn login`, or with `NOTION_API_TOKEN` set. gra runs
  `ntn api v1/pages/ID` with a pinned Notion API version. `ntn doctor` checks
  the setup.
- The `Resources/` folder must already exist in the vault.

## Development

```sh
uv run pytest
```
