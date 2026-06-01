---
tool: mise
scope: universal
tier: optional
summary: "Pinned per-project tool versions — best for node/polyglot; uv covers pure-python"
targets: ["mise.toml"]
detect: ["package.json", "go.mod", "**/*.go"]
---

# mise

## What

[mise](https://mise.jdx.dev/) pins tool versions per-project (node, python, uv, go, …) so contributors and CI agree.

## When to use

- **Node / polyglot repos** (node + python + go): strong fit. One `mise.toml` replaces `.nvmrc`/`.python-version`/`.tool-versions`, and `mise install` bootstraps everything.
- **Pure-python + uv repos**: skip it. uv already owns the python version (via `requires-python` + its own python management); mise's `python =` line just duplicates that. Its only unique value there is pinning uv itself — rarely worth a second source of truth.

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
- **uv-managed python:** the mise `python =` pin is *local dev convenience only* — never mirror it into `requires-python` as an upper bound (e.g. `<3.14`). The mise pin says "what I dev on"; `requires-python` says "what we support" — keep it broad (`>=3.13`). Capping `requires-python` to match the mise pin makes uv download a managed interpreter inside the build image when the base python moves past the cap, producing a venv whose interpreter/site-packages path doesn't exist in the runtime stage → container crashes on its first import. Your prod base image (e.g. chainguard `latest`) floats forward and won't match a fixed mise pin anyway.
