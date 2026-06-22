---
tool: lefthook
scope: universal
tier: baseline
summary: "Git hooks with autofix + restage (stage_fixed)"
targets: ["lefthook.yml"]
---

# lefthook

## What

[lefthook](https://lefthook.dev/) runs git hooks (pre-commit, pre-push) in parallel against staged files.

## Why

- Faster than husky/pre-commit framework (parallel, no Python startup tax).
- One YAML config for all hooks across languages.
- **Autofix + restage** built-in via `stage_fixed: true` — formatter/linter fixes get committed automatically, no second-commit shuffle.
- Per-glob targeting (only run biome on `frontend/**/*.ts`, only ruff on `fastapi/**/*.py`).

## Why not husky / pre-commit

- husky: JS-only, no autofix-restage, no parallel by default.
- pre-commit (Python framework): slow cold start, language-specific runners reinvent each tool, autofix-restage clunky.

## Config

`lefthook.yml` at repo root:

```yaml
pre-commit:
  parallel: true
  commands:
    biome:
      root: frontend/
      glob: "*.{ts,tsx,js,jsx,json}" # slashless → matches at any depth; see Gotchas
      run: npm run check:staged -- {staged_files}
      stage_fixed: true

    ruff-lint:
      root: fastapi/
      glob: "*.py"
      run: uv run ruff check --fix {staged_files}
      stage_fixed: true

    ruff-format:
      root: fastapi/
      glob: "*.py"
      run: uv run ruff format {staged_files}
      stage_fixed: true
```

## Install

Root `package.json`:

```json
{
  "devDependencies": { "lefthook": "^1.0.0" },
  "scripts": { "prepare": "lefthook install" }
}
```

`npm install` triggers `prepare`, which installs hooks into `.git/hooks/`.

**No `package.json` (pure-Python / non-JS repo)?** Don't add one just for this.
Install the lefthook binary directly — `mise use lefthook`, `brew install lefthook`,
or `uv tool install lefthook` — then run `lefthook install` once. The hooks still
target each subproject via `root:` (e.g. `root: service-a/`), with the command
running `uv run ruff …` inside it.

## Gotchas

- `stage_fixed: true` is the whole point. Don't omit it.
- For tools that don't accept file lists, omit `{staged_files}` and let them scan the project.
- Use `root:` so commands run from the subproject directory.
- Keep a `check:staged` npm script for biome that uses `--no-errors-on-unmatched` (lefthook may pass paths outside biome's `includes`).
- **Glob path semantics — slashless vs slash (verified on lefthook 1.13).** lefthook matches each glob against the file's **repo-relative path**. `root:` only scopes *which* staged files are considered and sets the run cwd — it does **not** rebase the glob. Two consequences:
  - A **slashless** glob matches the **basename at any depth**: `*.{ts,tsx,vue}` catches `App.vue`, `src/App.vue`, and `src/a/b/Deep.vue` alike. This is almost always what you want — pair it with `root:` to scope the subtree and let the tool's own config (biome `includes`, the line-limit `is_source()` filter) handle path precision.
  - A glob **containing a `/`** matches the full repo-relative path, and `**/` requires ≥1 intervening directory — so `src/**/*.ts` silently **misses** `src/index.ts` (a direct child of `src/`). Worse, with `root: frontend/` the glob `src/**/*.ts` matches **nothing**, because the real paths are `frontend/src/...`, not `src/...`. The miss is silent — the hook still runs, just on a subset (or empty).
  
  Prefer the slashless form. Reach for a path glob only to pin a specific location, and then mind both traps above. Always verify a glob change with a staged probe (`git add` a file at each depth, `lefthook run pre-commit`).
