---
tool: docs-gen
scope: universal
tier: optional
summary: "Generate README/CLAUDE/AGENTS from partials via a small Python script"
targets: ["docs/src/", "scripts/build_docs.py"]
---

# Docs Generation (Partials)

## What

A small Python script renders `README.md`, `CLAUDE.md`, `AGENTS.md`, and sub-READMEs from templates in `docs/src/` using `{{ include:partials/<name>.md }}` directives.

## Why

- DRY: setup instructions, repo layout, commands all live in one partial and appear in multiple docs.
- `CLAUDE.md` and `AGENTS.md` share one template — keeping AI agents (Claude Code, Codex, Gemini CLI) in lockstep. This is the heavier alternative to the [[agent-instructions]] symlink: reach for it when partials earn their keep (shared setup/layout across several docs), not just to keep the two agent files aligned.
- CI check fails on stale generated docs → can't merge if you edited template but forgot to render.
- No heavy doc tooling (mkdocs, sphinx) — just markdown + a regex.

## Why not mkdocs / hugo / docusaurus

Overkill for a few READMEs. We want files at known paths (README.md, CLAUDE.md) that GitHub/IDEs/agents read natively, not a built site.

## Layout

```
docs/src/
  README.md                  # template → ./README.md
  CLAUDE.md                  # template → ./CLAUDE.md AND ./AGENTS.md
  fastapi/README.md          # template → ./fastapi/README.md
  frontend/README.md         # template → ./frontend/README.md
  partials/
    setup.md
    repo_layout.md
    backend_commands.md
    ...
scripts/build_docs.py        # the renderer
```

Templates include partials:

```markdown
## First-Time Setup
{{ include:partials/setup.md }}
```

## Renderer

Single Python file, ~115 lines. Stdlib only. Two modes:

- `--write` — render all templates.
- `--check` — exit non-zero if any generated file is stale (CI gate).

A single template can render to multiple outputs (CLAUDE.md → both CLAUDE.md and AGENTS.md).

Includes are re-run up to 10 times so partials can include other partials.

## Makefile

```makefile
docs-build:
	mise exec -- python3 scripts/build_docs.py --write

docs-check:
	mise exec -- python3 scripts/build_docs.py --check
```

`make ci` includes `docs-check`.

## Gotchas

- Generated header at top of each output file warns editors off:
  `<!-- Generated from docs/src. Run `make docs-build` to update. Do not edit directly. -->`
- Partials should not start/end with blank lines that disrupt surrounding template flow — script `.strip()`s included content.
- Don't put `{{ ... }}` in unrelated code blocks inside templates (Jinja-style braces collide).
