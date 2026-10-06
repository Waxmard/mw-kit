---
tool: agent-instructions
scope: universal
tier: baseline
summary: "Agent-agnostic AGENTS.md as the only instructions file, no CLAUDE.md"
targets: ["AGENTS.md"]
detect: ["AGENTS.md", "CLAUDE.md"]
---

# Agent Instructions (AGENTS.md)

## What

A single repo-root instructions file that teaches coding agents how this repo
works — build/test commands, layout, conventions, gotchas. The file is `AGENTS.md`
(the cross-tool open standard). Codex, Claude Code (2.1.277+) and most other agents
read it natively, so there is no `CLAUDE.md` — not a copy, not a symlink.

## Why

- **One file, no drift.** Parallel `CLAUDE.md` and `AGENTS.md` rot the moment you
  edit one and forget the other. With native support there is nothing to keep in step.
- **A `CLAUDE.md` hides `AGENTS.md` from Claude Code.** Its default mode
  (`claude-md-or-agents-md`) loads `AGENTS.md` only when the project has no
  `CLAUDE.md` of its own. A stale or divergent `CLAUDE.md` silently wins.
- **Baseline, not optional.** Almost every repo benefits from agent instructions;
  a repo with none is the gap this page exists to flag.

## Config

The contract has two halves, and **both are checked** (the body, not just the file's
existence):

1. **Structure** — `AGENTS.md` is the only instructions file. No `CLAUDE.md` at the
   root or in a subdirectory: a real one is drift (it shadows `AGENTS.md`), and a
   symlink to `AGENTS.md` is a leftover to delete.
2. **Agent-agnostic body** — **zero** references to any specific agent anywhere in
   the prose. No `# CLAUDE.md` heading, no "guidance for Claude Code", no "Claude"
   / "Gemini" / any product name — always "the agent" / "AI agents". A named agent in
   the body is drift, full stop. A pointer to a sibling file named `CLAUDE.md` gets
   reworded to drop the name, e.g. "the workspace instructions one level up".

Migrate an older layout:

```bash
rm CLAUDE.md                # was a symlink to AGENTS.md
# or, if CLAUDE.md is the real file:
git mv CLAUDE.md AGENTS.md  # (or: mv, if not yet tracked)
```

Only for an agent that still reads just its own filename, add a symlink to
`AGENTS.md` for it — never a second real copy, and never for Claude Code.

Write the body neutrally — refer to "the agent" / "AI agents", not "Claude":

```markdown
# AGENTS.md

Guidance for AI agents working in this repo.

## Commands
- `make ci` — lint + typecheck + test (what CI runs)
- ...

## Layout
- ...

## Conventions
- ...
```

## Why not CLAUDE.md

Claude Code used to need a `CLAUDE.md`, either symlinked to `AGENTS.md` or importing
it with `@AGENTS.md`. Since 2.1.277 it reads `AGENTS.md` directly, nested ones
included, so both are dead weight. Keep a real `CLAUDE.md` only for a genuine
Claude-only section, and then have it `@AGENTS.md` import the shared content so the
shared instructions still load.

## Gotchas

- **The fallback is setting-dependent.** Claude Code's `/config` row "Project
  instructions" can be set to `claude-md`, which ignores `AGENTS.md`. The default
  reads it; if an agent seems to ignore the file, check that row first.
- **Generating both files is drift, not a second valid answer.** A template that
  renders `CLAUDE.md` and `AGENTS.md` as two real files pays for a generator script,
  a `make` target, a CI staleness gate, and a pre-commit hook, all to keep two copies
  of one document in step. Collapse it to `AGENTS.md` and delete the machinery that
  existed only to duplicate it. Keep a doc generator only for shared prose across
  genuinely *different* documents, and take the agent guides out of it even then.
