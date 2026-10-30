---
tool: mise
scope: universal
tier: optional
summary: "Opt-in tool version pins: compared only in repos that already have mise.toml"
targets: ["mise.toml"]
detect: ["mise.toml"]
---

# mise

## What

[mise](https://mise.jdx.dev/) pins tool versions per-project (node, python, uv, go, …) so contributors and CI agree.

## When to use

- **Node / polyglot repos** (node + python + go): strong fit. One `mise.toml` replaces `.nvmrc`/`.python-version`/`.tool-versions`, and `mise install` bootstraps everything.
- **Pure-python + uv repos**: skip it. uv already owns the python version (via `requires-python` + its own python management); mise's `python =` line just duplicates that. Its only unique value there is pinning uv itself — rarely worth a second source of truth.

## Config

`mise.toml` at repo root:

```toml
[tools]
node = "NN"      # current Node Active LTS
python = "3.X"   # newest stable Python
uv = "X.Y"  # pin to latest stable; renovate bumps it
```

## Setup

Use the latest Node LTS major for new apps, not the newer Current
release. Verify the [Node release table](https://nodejs.org/en/about/previous-releases)
when scaffolding. Keep Node runtime, CI, container images, and `@types/node` on the same major.

```bash
brew install mise
mise install
```

Shell activation: add `eval "$(mise activate zsh)"` to `~/.zshrc`.

## Gotchas

- Pin the major (`python = "3.X"`, `node = "NN"`); for 0.x tools (uv) pin the minor.
- CI: `mise exec -- python3 scripts/foo.py` is the cleanest way to invoke at pinned version inside a Makefile.
- **uv-managed python:** the mise `python =` pin is *local dev convenience only* — never mirror it into `requires-python` as an upper bound (e.g. `<3.X`). The mise pin says "what I dev on"; `requires-python` says "what we support" — keep it broad (a minor or more below the mise pin). Capping `requires-python` to match the mise pin makes uv download a managed interpreter inside the build image when the base python moves past the cap, producing a venv whose interpreter/site-packages path doesn't exist in the runtime stage → container crashes on its first import.
