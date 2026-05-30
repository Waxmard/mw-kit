---
tool: mise
scope: universal
tier: baseline
summary: "Pinned per-project tool versions (node, python, uv, ...)"
targets: ["mise.toml"]
---

# mise

## What

[mise](https://mise.jdx.dev/) pins tool versions per-project (node, python, uv, go, …) so contributors and CI agree.

## Why

- One file (`mise.toml`) replaces `.nvmrc`, `.python-version`, `.tool-versions`, etc.
- Polyglot-friendly.
- `mise install` reads and installs everything.
- CI: `mise exec -- <cmd>` runs commands at pinned versions without extra setup actions.

## Config

`mise.toml` at repo root:

```toml
[tools]
node = "22"
python = "3.11"
uv = "0.6"
```

## Setup

```bash
brew install mise
mise install
```

Shell activation: add `eval "$(mise activate zsh)"` to `~/.zshrc`.

## Gotchas

- Pin major versions, not patch (e.g. `"22"`, not `"22.11.0"`). Patches bring security fixes free.
- CI: `mise exec -- python3 scripts/foo.py` is the cleanest way to invoke at pinned version inside a Makefile.
