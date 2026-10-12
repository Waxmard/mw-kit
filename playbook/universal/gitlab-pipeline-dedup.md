---
tool: gitlab-pipeline-dedup
scope: universal
tier: baseline
summary: "GitLab workflow:rules dedup (one pipeline per change) + auto-cancel of superseded runs"
targets: [".gitlab-ci.yml"]
detect: [".gitlab-ci.yml"]
platform: gitlab
---

# GitLab Pipeline Dedup

## What

The **rules** half of a GitLab pipeline — when jobs run. For the full pipeline body
(stages, image, cache, the lint/typecheck/test jobs themselves) see
[ci-gitlab](./ci-gitlab.md); this page is the `workflow:rules` + job-`rules` it plugs in.

The job of this half: produce **exactly one** pipeline per change. GitLab can make
two kinds — a **branch pipeline** (on push) and an **MR pipeline**
(`merge_request_event`). A duplicate happens only when a single commit triggers
*both*, which is only possible if your **jobs run on both events**. So the dedup
you need is decided entirely by where your jobs run:

**Deterministic test — does any job `rules` entry reference `merge_request_event`?**
(`grep -n 'merge_request_event' .gitlab-ci.yml`; hits inside the `workflow:` block don't count.)

- **No** — every job gates on `$CI_COMMIT_BRANCH`. GitLab never creates MR
  pipelines, so duplicates are *impossible*. You need nothing — or the
  **branch-preferred** block below as a cheap guard. This is the common case.
- **Yes** — jobs run on MRs *and* branches, so both can fire for one commit. You
  need real dedup, and you have a working MR pipeline to keep.

Either way the rule is the same shape: **suppress the pipeline source your jobs
don't use; keep the one they do.** Two pieces always work together — a top-level
`workflow:rules` block (which pipelines get created) and per-job `rules` (which
jobs run in each). They must agree, or the surviving pipeline is empty and GitLab
fails to create it (see Gotchas). The default repo runs on branches → suppress MR
pipelines (safe, can't break); MR-preferred is the deliberate opt-in for teams who
want merged-results pipelines, and it carries a precondition.

## Why

- **No duplicate pipelines.** Without the `$CI_OPEN_MERGE_REQUESTS → never` rule,
  a push to a branch that already has an open MR fires *both* a branch pipeline
  and an MR pipeline for the same commit — wasted runner minutes on every push
  (and every bot push, e.g. renovate, which pushes onto already-open MRs). This
  assumes your jobs already run on MRs (piece 2 below); a **branch-only pipeline
  has no MR pipeline to duplicate**, so the dedup rule fixes nothing there and
  actively breaks it — see the precondition gotcha.
- **Build once, ship the tested artifact.** Build the image once on the branch push (`:$CI_COMMIT_SHORT_SHA`) and `crane`-retag it in the release job — never rebuild at tag time. All three release pages ([releases-gitlab](./releases-gitlab.md), [releases-python](../python/releases-python.md), [releases-monorepo](../monorepo/releases-monorepo.md)) put `[skip ci]` in the release commit so it doesn't spawn a rebuild.

## Config

Pick the strategy that matches where your jobs run (deterministic test above).

### Safe default — branch-preferred (suppress MR pipelines)

For the common repo whose jobs run on branch pushes. Run the **branch** pipeline,
never the MR pipeline:

```yaml
workflow:
  rules:
    - if: $CI_COMMIT_TAG              # keep release/tag pipelines
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      when: never                    # never create MR pipelines
    - if: $CI_COMMIT_BRANCH           # exactly one pipeline per branch push
```

The trade-off: you forgo **merged-results pipelines** (testing the real merge
result) and other MR-only features. Most repos don't miss them — adopt the
MR-preferred variant below only when you specifically want them.

### Opt-in — MR-preferred (suppress the branch pipeline)

When you *want* MR pipelines: reviewers test the merged result, MR-scoped
`changes:` filters, the image built and scanned on every MR. Run the **MR**
pipeline when a branch has an open MR, otherwise the branch pipeline:

```yaml
# Run only the MR pipeline when a branch has an open MR; otherwise (e.g. main)
# the branch pipeline.
workflow:
  rules:
    - if: $CI_COMMIT_TAG              # keep release/tag pipelines
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH && $CI_OPEN_MERGE_REQUESTS
      when: never
    - if: $CI_COMMIT_BRANCH
```

⚠️ Read the precondition gotcha before using this block.

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

In MR pipelines `CI_COMMIT_BRANCH` is empty; derive image tags from the predefined `$CI_COMMIT_REF_SLUG`.

## Monorepo (GitLab)

Assumes the **MR-preferred** variant (jobs run on `merge_request_event`) — the
`changes:`-scoping below hangs off those MR rules. A branch-preferred monorepo
just adds `changes:` to the `$CI_COMMIT_BRANCH` rules instead.

Define one rule anchor per component and apply it to every job — test jobs as-is,
build/scan with `when: always`:

```yaml
.service-a-changes: &service-a-changes
  - service-a/**/*
  - docker-bake.hcl

.service-a-rules: &service-a-rules
  - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    changes: *service-a-changes
  - if: $CI_COMMIT_BRANCH == "main"          # main always runs (no changes gate)
  - if: $CI_COMMIT_BRANCH
    changes: *service-a-changes              # pre-MR feature pushes, deduped

service-a-lint:
  extends: [.uv]
  rules: *service-a-rules

# build + image-scan: same conditions, plus when: always so the artifact builds
# even if a test job failed (you still want to scan what shipped).
service-a-build:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      changes: *service-a-changes
      when: always
    - if: $CI_COMMIT_BRANCH == "main"
      when: always
    - if: $CI_COMMIT_BRANCH
      changes: *service-a-changes
      when: always
```

Anchors are file-local across GitLab `include`s, so if you split per-component
files (`include: local:`) each `*-changes` / `*-rules` anchor must live in the
file that uses it; in a single root pipeline they sit at the top. Only `release`
stays gated to `main` (see [releases-monorepo](../monorepo/releases-monorepo.md)) — its per-component scoping is
the semantic-release-monorepo plugin's job, not a `rules:` one.

## Auto-cancel superseded pipelines

Dedup (above) stops *two* pipelines firing for *one* commit. This is the orthogonal
waste: a pipeline still running when a **newer commit** lands on the same branch is
now testing dead code — kill it. GitLab's UI calls this "auto-cancel redundant
pipelines"; the `workflow:auto_cancel` keyword sets it **in code**
and *overrides* the project setting, so you never touch the UI.

```yaml
workflow:
  auto_cancel:
    on_new_commit: interruptible   # a newer commit cancels still-running interruptible jobs
  rules:
    # ... dedup rules from Config above ...
```

Only does anything for jobs marked **`interruptible: true`** — that flag lives in the
pipeline body, so it's set repo-wide via `default:` in [ci-gitlab](./ci-gitlab.md),
with deploy/release jobs opted back out (`interruptible: false`). The two halves are a
pair: `auto_cancel` decides the policy, `interruptible` marks which jobs it may cancel.

`on_new_commit` values: `conservative` (default — won't cancel a pipeline once any
*uninterruptible* job has started), **`interruptible`** (cancel the running
interruptible jobs and let the rest finish — the one you want), `none` (off).

## Gotchas

- **`auto_cancel` does nothing without `interruptible: true` on the jobs.** The
  keyword names a policy; the flag opts each job in. A pipeline of all-default
  (uninterruptible) jobs is never auto-cancelled no matter the `on_new_commit` value.
  Set `default: interruptible: true` (see [ci-gitlab](./ci-gitlab.md)) so it's on by
  default, then exempt only the jobs that must finish.
- **Exempt deploys/releases — `interruptible: false`.** A superseded commit cancelling
  a half-done deploy or a `crane`-retag release leaves the registry/cluster in a torn
  state. Mark any job with external side effects uninterruptible; `interruptible` is
  safe only for read-only checks (lint/typecheck/test/build-to-throwaway-tag).
- **Precondition: the dedup rule needs jobs that run on `merge_request_event` —
  retrofitting it onto a branch-only pipeline breaks *all* CI.** The two Config
  pieces are a contract, not independent: `$CI_OPEN_MERGE_REQUESTS → never`
  suppresses the branch pipeline *on the assumption the MR pipeline runs the jobs
  instead*. If every job gates on `$CI_COMMIT_BRANCH` only — no
  `merge_request_event` rule anywhere, common in older pipelines that never
  adopted MR pipelines — then `$CI_COMMIT_BRANCH` is empty in the MR pipeline, **no
  job matches, and GitLab refuses the empty pipeline with `Pipeline creation
  failed. Please try again.`** The branch pipeline that *would* have run is gone
  and nothing replaces it: **zero pipelines** on every push to a branch with an
  open MR. This is worse than the duplicates it was meant to fix. Fix: add the job
  `merge_request_event` rules first (Config above), confirm MR pipelines actually
  run, *then* add the MR-preferred workflow block. If you're **not** converting
  jobs to run on MRs, use the **branch-preferred** block instead (Config above) —
  it suppresses MR pipelines rather than branch ones, so it can't starve anything;
  a branch-only pipeline has no duplicates to fix in the first place (its MR
  pipelines are always empty/uncreated).
- **Testing every branch costs CI on WIP.** Scope with `changes:` rather than narrowing back to `main`.
- **Don't drop `build`'s `merge_request_event` rule when adding `changes:`.** The
  easy monorepo mistake: gate build on `$CI_COMMIT_BRANCH` + `changes:` only. In
  an MR pipeline `$CI_COMMIT_BRANCH` is empty, so the image then **never builds on
  MRs** — and the branch pipeline that would've built it is suppressed by the
  workflow dedup. Build (and the image-scan that `needs:` it) needs its own
  `merge_request_event` rule, also `changes:`-scoped. This asymmetry hides behind
  a green dedup: no *duplicate* pipelines, but *missing* jobs. See
  [Monorepo (GitLab)](#monorepo-gitlab) for the full per-component anchor.
- **An `if: $CI_COMMIT_TAG` job rule is dead without a workflow tag rule — and harmful
  with one if the job `needs:` branch-only jobs.** The MR-preferred workflow block
  creates no tag pipelines, so a `$CI_COMMIT_TAG` rule on push jobs silently never
  fires (looks like release tagging, does nothing). Adding the workflow rule then
  breaks pipeline creation if those jobs `needs:` build jobs that only run on
  MR/branch. Give tag pipelines a dedicated retag job with its own `needs` (see
  [releases-gitlab](./releases-gitlab.md#manually-cut-release-tags-retag-dont-rebuild)) and drop
  `$CI_COMMIT_TAG` from the branch push jobs.
