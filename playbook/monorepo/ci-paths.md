---
tool: ci-paths
scope: monorepo
tier: baseline
summary: "Path-filtered per-subproject CI workflows"
targets: [".github/workflows/"]
platform: github
---

# Path-Filtered CI Workflows

## What

Separate workflow files per subproject, each gated with `paths:` filters so only relevant changes trigger.

## Why

- Frontend-only PR shouldn't run backend tests (and vice versa).
- Required status checks stay green when unrelated subproject is broken.
- Less CI minutes, faster feedback.

## Pattern

`.github/workflows/backend.yml`:

```yaml
name: Backend
on:
  push:
    branches: [main]
    paths: ["fastapi/**"]
  pull_request:
    branches: [main]
    paths: ["fastapi/**"]

jobs:
  test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: fastapi
    steps:
      - uses: actions/checkout@v6
      - uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
          cache-dependency-glob: "fastapi/uv.lock"
      - run: uv sync --extra dev --group dev
      - run: uv run pytest --cov=app --cov-fail-under=95
  lint: ...
  typecheck: ...
  boundaries: ...
```

`.github/workflows/frontend.yml`:

```yaml
name: Frontend
on:
  push:
    branches: [main]
    paths: ['frontend/**']
  pull_request:
    branches: [main]
    paths: ['frontend/**']
jobs:
  typecheck: ...
  lint: ...
```

## Required-checks trap

If a check is required by branch protection but skipped (paths filter didn't match), the PR can't merge. Two fixes:

1. **`paths-ignore`** instead of `paths` — runs on everything by default, skips only certain paths. Inverts the bias toward running.
2. **Synthetic "success" job** that always runs with `paths-ignore` matching the inverse. Required check points at it.

Simplest: don't make the path-filtered job required. Make a top-level `ci-aggregate` job (also conditional) required, OR use a single workflow with conditional jobs internally.

## Single-workflow alternative

```yaml
name: CI
on: [push, pull_request]
jobs:
  changes:
    runs-on: ubuntu-latest
    outputs:
      backend: ${{ steps.filter.outputs.backend }}
      frontend: ${{ steps.filter.outputs.frontend }}
    steps:
      - uses: actions/checkout@v6
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            backend: ['fastapi/**']
            frontend: ['frontend/**']

  backend:
    needs: changes
    if: needs.changes.outputs.backend == 'true'
    ...
```

`dorny/paths-filter` checks against base branch (handles force-pushes). The split workflow file approach is simpler if branch protection isn't in play.

## Cron / security workflows

`security.yml` runs on **all** PRs (no path filter) + scheduled. Security can't be path-gated — any change might introduce a vuln.
