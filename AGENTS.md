# AGENTS.md

## What this is

`mw-kit` is mostly a **prose playbook**: one Markdown page per tool, each explaining
the choice *and the reasoning*. It is the source of truth that the `tooling-sync`
skill diffs consumer repos against. It also ships two **runtime-stdlib-only** Python
scripts in `scripts/` (the manifest generator + the skill's scope resolver). The
`tooling-sync` skill itself lives in Waxmard/skills.

## Commands

```bash
make help                           # list targets
make ci                             # lint + typecheck + test (what CI runs)
make manifest                       # regenerate playbook/MANIFEST.md from frontmatter
make fmt                            # ruff autofix + format
python3 scripts/build_manifest.py   # (what `make manifest` calls)
python3 scripts/scope.py <repo>     # resolve which pages apply to a consumer repo (JSON plan)
```

**Run `make manifest` after editing any page's frontmatter** (a lefthook hook also
does this automatically on commit). `playbook/MANIFEST.md` is generated; never
hand-edit it.

### Dev tooling (dogfoods the playbook)

The scripts have **no runtime deps** (importable under bare `python3`), but the repo
carries a dev toolchain managed by uv: ruff + mypy (strict) + pytest. Run via
`make` / `uv run`; `make setup` (= `uv sync`) installs it.

**Local override — Python floor:** `requires-python = ">=3.9"` and
`ruff target-version = "py39"`, *not* the playbook's newest-stable policy. Reason:
`scripts/scope.py` is invoked by the `tooling-sync` skill via bare `python3` on
arbitrary machines (stock macOS ships 3.9.6), so the support floor is broad like a
published library, not a deployed app. mypy targets `3.10` only because mypy 2.x
can't go lower; ruff guards the real 3.9 floor.

## Page structure (the core contract)

Every `playbook/<scope>/<tool>.md` page has two halves, and both matter:

1. **YAML frontmatter** — the machine-readable index source. `build_manifest.py`
   parses it (with a hand-rolled parser, *not* PyYAML), so it only supports
   scalars and inline JSON lists (`["a", "b"]`). Required key: `tool`. Other keys:
   `scope`, `tier` (`baseline` | `optional`), `summary`, `targets` (files the page
   governs in a consumer repo), `detect` (path globs that signal relevance),
   `detect_content` (regexes matched against YAML file bodies — for repo classes
   with no path marker, e.g. plain-YAML k8s keyed on `^kind:`), optional `platform`
   (`github` | `gitlab`).
2. **Body** — sections `## What`, `## Why`, `## Config`, `## Gotchas` (pages add
   `## Commands`, `## Lefthook`, etc. as needed). `## Accepted alternative` names a
   tool a repo may already run instead; `tooling-sync` leaves such a repo on it, and
   new repos start on the page's tool. The `## Config` block is the
   **canonical config**: the literal snippet that `tooling-sync` diffs a repo's
   actual config against. Keep it copy-pasteable and current.

**Never hardcode versions** of runtimes, tools, images or packages in playbook
snippets; they rot. Tools/packages: use a `vX.Y.Z` / `X.Y.Z` placeholder plus a
`# pin to latest stable; renovate bumps it` comment. Runtimes: Python is `3.X`
(`# newest stable Python`) and Node is `NN` (`# current Node Active LTS`),
resolved to the real current version when tooling-sync applies the page.
Dependency lists in snippets name packages without version floors. *The one
exception stays concrete:* version-ref pins that must resolve to run and are
bot-managed (GitHub Action `uses:@v7`, GitLab CI component `@x.y.z`). The kit's own
files (`.github/workflows/ci.yml`, `pyproject.toml`) are real config, not snippets,
so they pin real versions.

`scope` is one of five, mirrored by the directory: `universal/` (every project),
`python/`, `node/`, `k8s/` (Kubernetes-manifest / GitOps repos), `monorepo/`.
`SCOPE_ORDER` in `build_manifest.py` controls manifest section order — add new
scopes there.

## When editing

- Adding a tool → new page under the right scope dir with full frontmatter +
  body, then regenerate the manifest. Also add it to that scope's `README.md`
  page list and the README "Tooling at a glance" table if it's a headline choice.
- Renaming/removing a tool → update the scope `README.md` and root `README.md`
  references too (manifest regenerates itself). Leaving stale cross-references is
  the main hazard here.
- `tier: baseline` means "most repos should adopt"; `optional` means
  context-specific. Pick deliberately — `tooling-sync` surfaces baseline gaps
  more loudly.
- This repo is consumed by the `tooling-sync` skill (source: Waxmard/skills; it
  reads this repo via `$MW_KIT` or a `~/.cache/mw-kit` clone). Keep `## Config`
  blocks accurate — they are read as the diff target, not just docs.
