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
      glob: "src/**/*.{ts,tsx,js,jsx,json}"
      run: npm run check:staged -- {staged_files}
      stage_fixed: true

    ruff-lint:
      root: fastapi/
      glob: "**/*.py"
      run: uv run ruff check --fix {staged_files}
      stage_fixed: true

    ruff-format:
      root: fastapi/
      glob: "**/*.py"
      run: uv run ruff format {staged_files}
      stage_fixed: true

    tach:
      root: fastapi/
      glob:
        - "app/**/*.py"
        - "tach.toml"
      run: uv run tach check
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

## Gotchas

- `stage_fixed: true` is the whole point. Don't omit it.
- For tools that don't accept file lists (like `tach`), omit `{staged_files}` and let them scan the project.
- Use `root:` so commands run from the subproject directory.
- Keep a `check:staged` npm script for biome that uses `--no-errors-on-unmatched` (lefthook may pass paths outside biome's `includes`).
