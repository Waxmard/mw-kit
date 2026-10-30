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

Jobs run on MRs and branches. The `workflow:` block keeps one pipeline per change (the MR pipeline when an MR is open, otherwise the branch pipeline) and lets a newer commit cancel the in-flight one.

## Why

- GitLab has no "run my Makefile" action — you spell out the image + install + command
  per job. Centralize the shared parts (`default:`, a `.setup` anchor, `.test-rules`)
  so each job is one `script:` line.
- Each job still calls the same underlying command as `make` locally, so "green
  locally" and "green in CI" stay in sync (the [ci-github](./ci-github.md) rationale).

## Config

`.gitlab-ci.yml` (Python / uv):

```yaml
stages: [test]

default:
  image: ghcr.io/astral-sh/uv:python3.X-trixie-slim  # newest stable Python
  interruptible: true              # a newer commit cancels these (deploys opt out, see below)

# One pipeline per change; a newer commit cancels interruptible jobs of the old one.
workflow:
  auto_cancel:
    on_new_commit: interruptible
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
    - uv sync --locked
  cache:
    key:
      files: [uv.lock]
    paths: [.venv/, .cache/uv/]
    policy: pull
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
  cache:
    - key:
        files: [uv.lock]
      paths: [.venv/, .cache/uv/]
      policy: pull
    - key: mypy-$CI_COMMIT_REF_SLUG
      fallback_keys:
        - mypy-$CI_DEFAULT_BRANCH
      paths: [.mypy_cache/]
      policy: pull-push
  script:
    - uv run mypy .

test:
  stage: test
  extends: [.uv, .test-rules]
  cache:
    key:
      files: [uv.lock]
    paths: [.venv/, .cache/uv/]
    policy: pull-push
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
  interruptible: true
  image: node:NN  # current Node Active LTS

.npm:
  before_script:
    - npm ci
  cache:
    key:
      files: [package-lock.json]
    paths: [node_modules/]
    policy: pull

lint:
  stage: test
  extends: [.npm, .test-rules]
  script: [npm run check]

test:
  stage: test
  extends: [.npm, .test-rules]
  cache:
    key:
      files: [package-lock.json]
    paths: [node_modules/]
    policy: pull-push
  script: [npm test]
```

## Monorepo variant

Same `workflow:` block. Scope each component's jobs with one `changes:` list and one rules anchor, defined **above** the first job that uses them:

```yaml
.service-a-changes: &service-a-changes
  - service-a/**/*
  - docker-bake.hcl

.service-a-rules: &service-a-rules
  - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    changes: *service-a-changes
  - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH   # default branch always runs
  - if: $CI_COMMIT_BRANCH
    changes: *service-a-changes

service-a-lint:
  stage: test
  extends: [.uv]
  rules: *service-a-rules
```

Every component job, build and image scan included, uses the same anchor. Only `release` stays gated to the default branch (see [releases-monorepo](../monorepo/releases-monorepo.md)).

## Gotchas

- **`uv sync --locked`** fails if `uv.lock` is out of date with `pyproject.toml` —
  exactly what you want in CI (no silent re-resolve). Locally use plain `uv sync`.
- **Cache `key.files: [uv.lock]`** — keying on the lockfile means the cache busts only
  when deps actually change. Keying on branch/ref instead reuses stale `.venv` across
  dependency bumps.
- **Cache `policy: pull` on consumer jobs, `pull-push` on only one.** In a
  parallel stage, default cache policy causes every job to re-pack and upload the
  identical multi-gigabyte cache archive on finish. Set `policy: pull` on the base
  anchor (`.uv`, `.npm`) and override with `policy: pull-push` exclusively on the
  `test` job.
- **Pin the image** (`uv:python3.X-trixie-slim`, `node:NN`) with the real current version, not `:latest` — reproducible
  pipelines, intentional bumps (renovate handles them — see [renovate](./renovate.md)).
- **Adding a `release` stage?** Don't rebuild. See
  [releases-python](../python/releases-python.md) / [releases-gitlab](./releases-gitlab.md).
  Give release and deploy jobs `interruptible: false`; `default: interruptible: true`
  otherwise lets `auto_cancel` kill them mid-release.
- **Every job needs a `merge_request_event` rule.** The `workflow:` block drops the
  branch pipeline while an MR is open, so a job gated only on `$CI_COMMIT_BRANCH` never
  runs on MRs. If no job matches, GitLab refuses the pipeline with `Pipeline creation failed`.
- **An alias before its anchor fails pipeline creation.** YAML anchors (`&name`) must
  appear above every `*name` use. Run `glab ci lint` after inserting jobs.
