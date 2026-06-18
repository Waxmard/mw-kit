---
name: tooling-sync
description: >
  Compare the current repo's tooling/config against the mw-kit playbook
  (the user's source-of-truth for favorite tooling), report what's missing,
  drifted, or could be added, let the user choose which updates to make, then
  apply the chosen ones — merging into existing config, never clobbering.
  Read-only until the user picks; never commits or pushes. Language-agnostic,
  driven by playbook/MANIFEST.md. Trigger: "sync tooling", "compare tooling",
  "check tooling against mw-kit", "tooling diff", "update tooling from the
  playbook", "what's my playbook say vs this repo", or /tooling-sync.
---

Compare the **current repo** (CWD) against the mw-kit playbook and apply chosen updates. The playbook is the user's curated source-of-truth; this repo is the consumer being checked. The flow is **scope → compare → report → decide → apply**, and it is strictly read-only until the user chooses what to apply.

**Source of truth:** `${MW_KIT:-/Users/maxwellward/personal-dev/mw-kit}`. The index is `playbook/MANIFEST.md` there; each row points at a page whose `## Config` block is the canonical config to diff against. If the env var isn't set, use the default path.

## Pre-flight & Step 1 — Scope (run the resolver)

The deterministic half — repo validation, platform + structure detection, glob-based scoping, alternative resolution, and target presence — lives in a script in the playbook. **Run it and parse its JSON; do not re-derive any of it by hand** (no per-page Glob sweeps, no manual platform/monorepo reasoning).

```bash
python3 "${MW_KIT:-/Users/maxwellward/personal-dev/mw-kit}/scripts/scope.py" "$(git rev-parse --show-toplevel)"
```

The plan JSON:

- `preflight` — `{ok, repo, platform, platform_source}`; on failure `{ok:false, error}` (not a git repo / mw-kit itself / manifest missing).
- `structure` — `{verdict: single_project|multi_component|ambiguous, ambiguous, manifests, root_orchestrator}`.
- `alternatives` — `{dep_updates:{chosen,reason}, releases:{chosen,reason,note?}, dropped:[…]}`. The losing alternatives are already moved to `skipped`; `chosen` is guaranteed in-scope.
- `in_scope` — one row per relevant page: `{tool, page, scope, tier, platform, targets, targets_present, targets_missing, matched_detect, platform_pending?}`.
- `skipped` — `{tool, page, reason}` (no detect match / platform / single-project / alternative not chosen).
- `needs_ask` — questions the script refused to guess (unknown platform, ambiguous structure).
- `warnings` — plan-coherence issues; surface any to the user.

Then:

1. **`preflight.ok` false** → stop and surface `preflight.error`. (Manifest-missing means check the path / `$MW_KIT`.)
2. **`needs_ask` non-empty** → ask each question, then **re-run the script with the answer as an override** so the plan stays deterministic — don't hand-patch it:
   - platform → `--platform github|gitlab`
   - structure → `--structure single_project|multi_component`
   For the ambiguous-structure case, a nested single component is a strong monorepo signal — present it that way. When the answer is monorepo, also consult an existing **sibling component or org reference repo** for the concrete shape (CI include structure, image-tag flow) — the playbook block is canonical, the sibling shows the wired-up reality.
3. **Relay the scoped set** before diffing, from the JSON: in-scope tools, the chosen alternatives (with the dropped ones named), and what was skipped + why. State single-project vs monorepo. Example: "Relevant: ruff, mypy, uv, pytest, lefthook, dependabot, releases-github. Skipped: node/* (no JS), renovate (alternative to dependabot), gitlab-only pages. Scoped as single-project."

## Step 2 — Compare

The resolver already told you, per page, which `targets` exist (`targets_present` / `targets_missing`). Use that to avoid needless reads:

- **No targets present** → classify directly from `tier` without reading the page: ❌ **missing (baseline)** or ➕ **suggest (optional)**. (For `conventional-commits` and other target-less pages, judge by convention/commit history, not a file.)
- **Some/all targets present** → this is the drift question. Read the page's canonical `## Config` block and the present target file(s), then classify match vs drift.

For each page needing a config read, compare its `targets` files against the page's canonical `## Config` block. Read the page body only for the in-scope ones.

**Dispatch rule:** the per-page diff is independent and mostly mechanical (does the target exist, does its config match the canonical block).
- **≤ 7 in-scope pages** → compare inline yourself.
- **≥ 8** → fan out one **Haiku** subagent per page (Agent tool, `model: haiku`), in parallel. Each subagent reads its page's canonical `## Config` block from the playbook + the repo's `targets` file(s), and returns a structured classification row (status, target file(s), headline delta, quoted deltas for drift). Escalate a page to **Sonnet** only when its config needs *semantic* merge reasoning (e.g. reconciling a hand-customized `biome.json` or a multi-section `pyproject.toml`) rather than a flat presence/equality check. You collect the rows and assemble the Step 3 report. **Apply (Step 5) stays inline in the parent** — it touches files and must stay coherent across confirmations.

Each compare subagent is read-only: it reads the playbook page and the repo target, returns its row, writes nothing.

| Status | Meaning |
|---|---|
| ✅ **match** | Repo config aligns with the playbook's canonical block (semantically — ignore key ordering / formatting). |
| ⚠️ **drift** | Tool is present but config differs from canonical. Show the specific deltas. |
| ❌ **missing (baseline)** | `tier: baseline` page applies but the repo has no corresponding config. |
| ➕ **suggest (optional)** | `tier: optional` page applies and could be adopted, but absence isn't a problem. |
| 🔧 **local override** | Repo deliberately diverges (documented in its `CLAUDE.md`, or an obvious project-specific reason). Flag, don't fight it. |

Comparison notes:
- Configs are often **fragments**, not whole files. `ruff`/`mypy`/`pytest`/`uv` live in sections of `pyproject.toml`; `package-json` scripts are keys inside `package.json`; `biome`/`tsconfig`/`renovate` are whole files. Diff the relevant slice, not the whole file.
- For drift, report the **direction**: which keys the playbook adds, changes, or is stricter on. Quote both sides for changed values.
- Versions matter: pinned tool versions (`mise.toml`, biome `$schema`, `target-version`, action pins) — note when the repo is behind the playbook, but treat newer-in-repo as fine (the playbook may just be stale).
- Do not treat the playbook as a mandate. If the repo's choice looks intentional, classify it 🔧 and surface the tension rather than proposing a revert.

## Step 3 — Report

Present a grouped summary the user can act on. One line per tool: status, target file(s), and the headline delta. Order: ❌ baseline-missing first, then ⚠️ drift, then ➕ suggestions, then ✅ matches (collapsed). Example:

```
❌ security      .github/workflows/security.yml — no scanning workflow (playbook: semgrep + trivy fs/image)
⚠️ ruff          pyproject.toml [tool.ruff] — missing select packs S, SIM, PL; no per-file test ignores
⚠️ mise          mise.toml — python pinned 3.10, playbook 3.11
➕ tach          (optional) no module-boundary enforcement — app/ has 6 layers, could benefit
✅ uv, mypy, lefthook — aligned
```

## Step 4 — Decide

Ask which to apply. Offer: **all baseline fixes**, **a specific subset** (numbered), **just one**, or **none / report-only**. Default to nothing until told. For ⚠️ drift items, the user may want only part of the delta — let them say so.

## Step 5 — Apply

For each chosen item, one at a time:

1. Re-read the canonical block from the page and the current target file.
2. **Merge, don't clobber.** Bring the playbook's opinionated values into the repo's existing config; preserve repo-specific keys (extra deps, project name, custom scripts, local ignores). Whole-file targets with no existing file → create from the canonical block, adjusted to the repo (paths, project name, roots like `fastapi/` → the repo's actual layout).
3. Show the proposed change as a diff and **confirm before writing**. Then apply with Edit (fragment merge) or Write (new whole file).
4. Adjust for repo reality: the playbook examples assume paths like `fastapi/`, `frontend/`, `app/`. Rewrite globs/roots/`source` to the repo's actual structure. Flag anything you couldn't auto-map.
5. After applying, note any **follow-up** the user must do manually (install a dep, add a CI secret, run a formatter once, add a workflow token) — don't run installs or commits yourself.

Pause after each applied change. Don't batch silently.

## Hard rules

- **Read-only until the user picks.** Steps 1–3 never modify the repo.
- **Never commit, never push, never `git add`** — global rule. Apply edits to the working tree only; the user commits.
- **Never clobber a config wholesale** when the repo already has one — merge. Only Write a fresh file when none exists.
- **Never run installs** (`npm install`, `uv add`, `pip install`) — surface them as follow-ups.
- **Respect local overrides.** A documented or obviously-intentional divergence is flagged, not overwritten.
- **The resolver owns scope.** Don't re-derive scope by hand-globbing or reading every page — trust `scope.py`'s plan. If a page exists but the resolver never considers it (missing from its output entirely), the manifest/frontmatter may be stale; tell the user to run `python3 scripts/build_manifest.py` in mw-kit. Never run either script *from* the consumer repo.

## Permissions (pre-approve these)

The read-only scope+compare phase needs, in addition to defaults:

- `Read(//Users/maxwellward/personal-dev/mw-kit/**)` — read the playbook + page bodies (outside the workspace, so it prompts otherwise). **This is the key one.**
- `Bash(python3 //Users/maxwellward/personal-dev/mw-kit/scripts/scope.py:*)` — run the scope resolver (does its own git/glob/presence work). **The other key one.**
- `Bash(git rev-parse:*)` — resolve the consumer repo toplevel to pass to the resolver. (Already allowed globally.)

The apply phase uses `Edit` / `Write` on the consumer repo's own config files. These are intentionally left to prompt (and the skill confirms each change anyway) — don't blanket-allow them. Reading the consumer repo's own files needs no extra permission (it's the workspace).

## Pitfalls

- **Path assumptions:** playbook configs hardcode `fastapi/`, `frontend/`, `app/`, `src/`. Always remap to the repo's real layout before applying — a copied `root: fastapi/` lefthook entry silently no-ops in a repo with no `fastapi/`.
- **Fragment vs whole-file:** editing `[tool.ruff]` into a `pyproject.toml` that already has it = merge the keys, don't append a duplicate table. Whole-file (`biome.json`) with an existing file = reconcile, don't overwrite custom rules.
- **Alternatives double-count:** never propose both dependabot and renovate, or both release tools — pick by platform + what's already present.
- **Stale playbook:** if the repo pins a newer version than the playbook, the playbook is behind — note it, maybe suggest the user update mw-kit, don't downgrade the repo.
- **Optional noise:** don't push `tier: optional` pages hard. Mention once, only when the repo plausibly benefits (e.g. tach only for a layered app, docker-bake only if it ships images).
- **Platform mismatch:** a github-only page (security workflow, dependabot, release-please) on a gitlab repo is out of scope — its gitlab counterpart applies instead.
