---
tool: ci-gitlab
scope: universal
tier: baseline
summary: "Single-project GitLab CI: lint + typecheck + test pipeline skeleton"
targets: [".gitlab-ci.yml"]
platform: gitlab
---

# Single-Project CI (GitLab)

## What

The full `.gitlab-ci.yml` skeleton for a single-toolchain repo: a `test` stage with
lint, typecheck, and test jobs, sharing one image, one lockfile-keyed cache, and one
rules anchor. The GitLab equivalent of [ci-github](./ci-github.md).

This page owns the **pipeline body** (stages, image, cache, job definitions).
[gitlab-pipeline-dedup](./gitlab-pipeline-dedup.md) owns the **rules** that decide
*when* it runs (the `workflow:rules` dedup block + the `.test-rules` anchor). Apply
both: this gives you jobs, that stops them running twice.

## Why

- GitLab has no "run my Makefile" action — you spell out the image + install + command
  per job. Centralize the shared parts (`default:`, a `.setup` anchor, `.test-rules`)
  so each job is one `script:` line.
- Cache keyed on the lockfile (`uv.lock` / `package-lock.json`) survives across
  pipelines but invalidates the moment deps change — fast without going stale.
- Each job still calls the same underlying command as `make` locally, so "green
  locally" and "green in CI" stay in sync (the [ci-github](./ci-github.md) rationale).

## Config

`.gitlab-ci.yml` (Python / uv). The `workflow:` block is the dedup baseline — see
[gitlab-pipeline-dedup](./gitlab-pipeline-dedup.md) for why each rule is there:

```yaml
stages: [test]

default:
  image: ghcr.io/astral-sh/uv:python3.14-bookworm-slim

# One pipeline per change — MR pipeline when an MR is open, else branch pipeline.
workflow:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH && $CI_OPEN_MERGE_REQUESTS
      when: never
    - if: $CI_COMMIT_BRANCH

# Run on every MR and every branch (shared by all test-stage jobs).
.test-rules:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH

.uv:
  before_script:
    - uv sync --frozen
  cache:
    key:
      files: [uv.lock]
    paths: [.venv/, .cache/uv/]
  variables:
    UV_CACHE_DIR: .cache/uv

lint:
  stage: test
  extends: [.uv, .test-rules]
  script:
    - uv run ruff check .
    - uv run ruff format --check .

typecheck:
  stage: test
  extends: [.uv, .test-rules]
  script:
    - uv run mypy .

test:
  stage: test
  extends: [.uv, .test-rules]
  script:
    - uv run pytest
```

Three jobs instead of one `make ci` step: GitLab runs stage jobs in parallel, so
splitting lint/typecheck/test gives independent pass/fail and concurrent runners —
the opposite tradeoff from [ci-github](./ci-github.md)'s single `check` job. Collapse
to one `make ci` job if you'd rather have a single check.

## Node variant

Swap the image + setup anchor; the stage/rules structure is identical:

```yaml
default:
  image: node:22

.npm:
  before_script:
    - npm ci
  cache:
    key:
      files: [package-lock.json]
    paths: [node_modules/]

lint:
  stage: test
  extends: [.npm, .test-rules]
  script: [npm run lint]
```

## Gotchas

- **`uv sync --frozen`** fails if `uv.lock` is out of date with `pyproject.toml` —
  exactly what you want in CI (no silent re-resolve). Locally use plain `uv sync`.
- **Cache `key.files: [uv.lock]`** — keying on the lockfile means the cache busts only
  when deps actually change. Keying on branch/ref instead reuses stale `.venv` across
  dependency bumps.
- **Pin the image** (`uv:python3.14-...`, `node:22`), not `:latest` — reproducible
  pipelines, intentional bumps (renovate handles them — see [renovate](./renovate.md)).
- **Adding a `release` stage?** Don't rebuild — see
  [releases-python](../python/releases-python.md) / [releases-gitlab](./releases-gitlab.md)
  for the release job + the `[skip ci]` / `chore(release):` dedup that stops the
  release commit spawning another pipeline.
- **Multi-component repo?** This is single-project only — add `changes:` filters per
  [ci-paths](../monorepo/ci-paths.md) (the `workflow:` block stays identical).
