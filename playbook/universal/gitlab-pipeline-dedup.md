---
tool: gitlab-pipeline-dedup
scope: universal
tier: baseline
summary: "workflow:rules dedup + build-on-MR job rules for GitLab"
targets: [".gitlab-ci.yml"]
detect: [".gitlab-ci.yml"]
platform: gitlab
---

# GitLab Pipeline Dedup

## What

Two cooperating pieces in `.gitlab-ci.yml`:

1. A top-level `workflow:rules` block that runs **exactly one** pipeline per
   change — the MR pipeline when an MR is open, otherwise the branch pipeline.
2. Per-job `rules` on test + `build` (+ image-scan) that run on **every**
   pipeline the workflow allows (MR or any branch); only `release` gates to main.

The non-obvious bit: `build` needs its own `merge_request_event` rule — you want
the image built and scanned on every MR so reviewers test the real artifact, yet
without the workflow dedup you'd build it twice.

## Why

- **No duplicate pipelines.** Without the `$CI_OPEN_MERGE_REQUESTS → never` rule,
  a push to a branch that already has an open MR fires *both* a branch pipeline
  and an MR pipeline for the same commit — wasted runner minutes on every push
  (and every bot push, e.g. renovate, which pushes onto already-open MRs).
- **Build once, ship the tested artifact.** Build the image on the `main` push
  tagged `:$SHA`, then `crane`-retag it to the released version (`:$SHA → :X.Y.Z`)
  in the release job — never rebuild at tag time. No tag-triggered pipeline
  needed, and the published image is byte-identical to what the MR tested (no
  rebuild drift). Both release tools follow this model; only the way they stop the
  release commit/tag from spawning a rebuild differs: [[releases-gitlab]] (node
  semantic-release) skips `chore(release):` titles in `workflow:rules`, while
  [[releases-python]] / [[releases-monorepo]] (PSR) put `[skip ci]` in the release
  commit message.

## Config

Top of `.gitlab-ci.yml`:

```yaml
# Avoid duplicate pipelines: when a branch has an open MR, run only the MR
# pipeline; otherwise (e.g. main) run the branch pipeline.
workflow:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH && $CI_OPEN_MERGE_REQUESTS
      when: never
    - if: $CI_COMMIT_BRANCH
```

Test jobs (lint, type-check, unit tests), `build`, and `trivy-image-scan` all run on
every MR **and** every branch — same gate, so nothing builds untested:

```yaml
.test-rules:                          # shared by lint/type-check/test jobs
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH          # any branch, not just main

build:
  stage: build
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      when: always
    - if: "$CI_COMMIT_BRANCH"
      when: always
```

Only `release` gates to `main`:

```yaml
semantic-release:
  stage: release
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

In MR pipelines `CI_COMMIT_BRANCH` is empty but `CI_COMMIT_REF_NAME` holds the
source branch — use `CI_COMMIT_REF_NAME` when deriving an image tag from the
branch name:

```yaml
  before_script:
    - if [ -n "${CI_COMMIT_REF_NAME:-}" ]; then export BRANCH_SANITIZED=$(printf '%s' "$CI_COMMIT_REF_NAME" | tr '/' '-'); fi
```

## Gotchas

- **No project setting controls this.** MR pipeline creation is driven entirely
  by `workflow:rules`, not GitLab Settings. You can't "disable MR pipelines" in
  the UI — if you see duplicates, it's the missing `$CI_OPEN_MERGE_REQUESTS`
  rule, full stop.
- **Duplicates surface only on pushes while an MR is open.** If you push first
  then open the MR, the overlap window is small and the bug hides — until a bot
  (renovate/dependabot) starts pushing onto open MRs and doubles every run. Don't
  judge correctness by "I haven't noticed duplicates."
- **Testing every branch costs CI on WIP.** Matching `$CI_COMMIT_BRANCH` runs the
  full test+build on pre-MR feature pushes too. Workflow dedup keeps it to one run
  per push; if that churn is heavy, reach for `changes:` filters (below) rather
  than narrowing back to `main`.
- **Pairs with [[ci-paths]] in monorepos** — add `changes:` filters to the job
  rules to skip unaffected subprojects. The workflow dedup block stays identical.
