---
tool: ci-github
scope: universal
tier: baseline
summary: "Single-project GitHub Actions CI: lint + typecheck + test on every PR"
targets: [".github/workflows/ci.yml"]
platform: github
---

# Single-Project CI (GitHub Actions)

## What

One workflow that runs the full check suite — lint, typecheck, test — on every PR
and every push to `main`. The single-repo counterpart to
[ci-paths](../monorepo/ci-paths.md) (which path-filters per subproject). The GitLab
equivalent is [ci-gitlab](./ci-gitlab.md). If the repo has exactly one toolchain at
its root, this page applies; if it has multiple subprojects, use `ci-paths` instead.

## Why

- One required status check per repo, always run (no path filter to misfire — see the
  required-checks trap in [ci-paths](../monorepo/ci-paths.md)).
- Mirrors the local `make ci` target, so "green locally" and "green in CI" mean the
  same thing. CI calls the same entrypoint instead of re-listing commands that drift.
- Caching keyed on the lockfile keeps runs fast without going stale.

## Config

`.github/workflows/ci.yml` (Python / uv):

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6

      - uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"

      - run: uv sync

      # Lint + typecheck + tests (mirrors `make ci`)
      - run: make ci
```

The single `make ci` step is the contract: CI runs whatever `ci` runs locally. Add a
matrix (`strategy.matrix.python-version`) only if you actually support multiple
runtimes — otherwise it's wasted minutes.

## Node variant

Swap the toolchain setup; the skeleton is identical:

```yaml
      - uses: actions/checkout@v6
      - uses: actions/setup-node@v4
        with:
          node-version-file: ".nvmrc"
          cache: "npm"
      - run: npm ci
      - run: npm run ci   # or: biome check + tsc + test
```

## Generated-file freshness gate

If the repo commits a generated artifact (manifest, lockfile-derived index, docs from
partials), add a job that regenerates it and fails on drift — the generator stays
honest without a human noticing a stale checkout:

```yaml
      - name: generated file is committed in sync
        run: |
          python3 scripts/build_manifest.py
          git diff --exit-code playbook/MANIFEST.md
```

`git diff --exit-code` returns nonzero if the regenerated file differs from what's
committed. Same pattern works for any deterministic generator.

## Gotchas

- **Pin major versions** of actions (`@v6`, `@v7`), not floating `@main`. Dependabot
  bumps them (see [dependabot](./dependabot.md)).
- **`cache-dependency-glob` must point at the lockfile** (`uv.lock` / `package-lock.json`),
  not the manifest — the lock is what determines the resolved tree.
- **Don't duplicate command lists** between `ci.yml` and the Makefile. One `make ci`
  step; the Makefile owns the steps. Drift between them is the whole failure mode this
  avoids.
- **GitLab** uses `.gitlab-ci.yml` with a different shape (stages + `workflow:rules`);
  see [ci-gitlab](./ci-gitlab.md) for the pipeline skeleton and
  [gitlab-pipeline-dedup](./gitlab-pipeline-dedup.md) for the dedup rules. This page's
  canonical block is GitHub-only.
