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
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@vX.Y.Z # pin to latest stable; dependabot bumps it
        with:
          enable-cache: true
          cache-dependency-glob: "fastapi/uv.lock"
      - run: uv sync --locked
      - run: uv run pytest --cov=app --cov-fail-under=<n>
```

Add lint/typecheck jobs with the same `working-directory` pattern.

`.github/workflows/frontend.yml`:

```yaml
name: Frontend
on:
  push:
    branches: [main]
    paths: ["frontend/**"]
  pull_request:
    branches: [main]
    paths: ["frontend/**"]
# jobs: same shape as backend.yml, working-directory: frontend
```

## Required-checks trap

A workflow-level `paths:` filter means the check never reports, so a required check blocks the merge (`paths-ignore` has the same failure mode). Require an always-running aggregate job (`if: always()` that checks `needs.*.result`), or use the single-workflow variant below.

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
      - uses: actions/checkout@v7
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            backend: ['fastapi/**']
            frontend: ['frontend/**']

  backend:
    needs: changes
    if: needs.changes.outputs.backend == 'true'
    # steps: same as the split workflow
```

`dorny/paths-filter` checks against base branch (handles force-pushes). The split workflow file approach is simpler if branch protection isn't in play.

## Cron / security workflows

`security.yml` runs on **all** PRs (no path filter) + scheduled. Security can't be path-gated — any change might introduce a vuln.
