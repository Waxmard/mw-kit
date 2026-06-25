---
tool: agent-instructions
scope: universal
tier: baseline
summary: "Agent-agnostic AGENTS.md as the source of truth, with CLAUDE.md symlinked to it"
targets: ["AGENTS.md", "CLAUDE.md"]
detect: ["AGENTS.md", "CLAUDE.md"]
---

# Agent Instructions (AGENTS.md)

## What

A single repo-root instructions file that teaches coding agents how this repo
works — build/test commands, layout, conventions, gotchas. The canonical file is
`AGENTS.md` (the cross-tool open standard, read natively by Codex and others).
Agents that insist on their own filename get a **symlink to `AGENTS.md`** instead of
a parallel copy: `CLAUDE.md` for Claude Code, optionally `GEMINI.md` for Gemini CLI.
One source of truth, every agent in lockstep.

## Why

- **One file, no drift.** Hand-maintaining parallel `CLAUDE.md` and `AGENTS.md` rots
  the moment you edit one and forget the other. A symlink makes that impossible.
- **AGENTS.md is the open standard**, so it's the real file; `CLAUDE.md` is the
  Claude-Code-specific alias pointing at it. Agent-agnostic by construction.
- **Baseline, not optional.** Almost every repo benefits from agent instructions;
  a repo with none is the gap this page exists to flag.

## Config

The contract has two halves, and **both are checked** (the body, not just the file's
existence):

1. **Structure** — `AGENTS.md` is the real file; each agent-specific filename
   (`CLAUDE.md`, optionally `GEMINI.md`) is a symlink to it, never a second real copy.
2. **Agent-agnostic body** — **zero** references to any specific agent anywhere in
   the prose. No `# CLAUDE.md` heading, no "guidance for Claude Code", no "Claude"
   / "Gemini" / any product name — always "the agent" / "AI agents". This holds even
   when `AGENTS.md` already exists; a named agent in the body is drift, full stop.
   (The symlink *filenames* `CLAUDE.md` / `GEMINI.md` are aliases, not body content —
   they're expected. A pointer to a sibling file that happens to be named `CLAUDE.md`
   gets reworded to drop the name, e.g. "the workspace instructions one level up".)

Set up the symlinks (AGENTS.md is the real file):

```bash
# if you currently have CLAUDE.md as the real file, rename it first:
git mv CLAUDE.md AGENTS.md       # (or: mv, if not yet tracked)
ln -s AGENTS.md CLAUDE.md         # Claude Code
ln -s AGENTS.md GEMINI.md         # Gemini CLI (only if you use it)
git add AGENTS.md CLAUDE.md GEMINI.md   # commits the aliases as symlinks
```

`CLAUDE.md` is the always-on alias; add `GEMINI.md` (or any other agent's file) only
for agents you actually use — an unused symlink is just noise.

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

## Why not @AGENTS.md import

Claude Code can instead load `AGENTS.md` via an `@AGENTS.md` line inside a real
`CLAUDE.md`. That's the right call **only** when you need Claude-specific
instructions layered on top of the shared content — and on Windows, where symlinks
need admin/Developer Mode. With agent-neutral content there's nothing Claude-only to
add, so the symlink (single file, zero duplication) is simpler. Reach for the import
the moment a genuine Claude-only section appears.

## Gotchas

- **Symlink direction matters.** `AGENTS.md` is the real file; `CLAUDE.md` /
  `GEMINI.md` point at it. Reverse it and tools expecting the standard file follow a
  dangling-looking alias.
- **Generated docs satisfy this too.** A repo using [[docs-gen]] renders both
  `CLAUDE.md` and `AGENTS.md` as real files from one template — that's the same
  lockstep guarantee by a different mechanism, so don't also symlink there. The
  symlink is the lighter default for repos without the partials machinery.
