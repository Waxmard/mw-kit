---
tool: gitlab-pipeline-dedup
scope: universal
tier: baseline
summary: "workflow:rules dedup for GitLab — exactly one pipeline per change (branch- or MR-preferred)"
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
(`grep -n 'merge_request_event' .gitlab-ci.yml`, scoped to job rules.)

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

**This can't break.** It only ever *removes* MR pipelines and *keeps* the branch
pipeline — and the branch pipeline always has jobs (every repo's jobs gate on
`$CI_COMMIT_BRANCH` by default), so it can never produce the empty-pipeline error.
On a repo that never had MR pipelines it's a harmless no-op; if someone later adds
an MR job rule, it silently prevents the duplicate instead of letting it appear.
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
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH && $CI_OPEN_MERGE_REQUESTS
      when: never
    - if: $CI_COMMIT_BRANCH
```

⚠️ **Precondition — your jobs must run on `merge_request_event`.** This block
*suppresses the branch pipeline*, betting the MR pipeline runs the jobs instead. If
no job opts into `merge_request_event`, the MR pipeline is empty and GitLab fails
with `Pipeline creation failed. Please try again.` — zero pipelines, worse than the
duplicate. So the job rules below ship **with** this block, not optionally. When
retrofitting, add the job rules first, confirm MR pipelines run, *then* add the
workflow block. If you don't want MR pipelines, use the branch-preferred default
above instead — never this block alone.

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

## Monorepo (GitLab)

Assumes the **MR-preferred** variant (jobs run on `merge_request_event`) — the
`changes:`-scoping below hangs off those MR rules. A branch-preferred monorepo
just adds `changes:` to the `$CI_COMMIT_BRANCH` rules instead.

[[ci-paths]] is GitHub-only (`paths:` on `.github/workflows/`). On GitLab the same
idea — skip the jobs of the component that didn't change — folds into the job
`rules` themselves, **combined with** the dedup conditions above. The dedup
contract is unchanged: every test/build/scan job still runs on an MR **and** any
branch; it's now also `changes:`-scoped per component.

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
stays gated to `main` (see [[releases-monorepo]]) — its per-component scoping is
the semantic-release-monorepo plugin's job, not a `rules:` one.

## Gotchas

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
  pipelines are always empty/uncreated). This is the whole-pipeline version of the
  `build`-specific asymmetry below.
- **Duplicates surface only on pushes while an MR is open.** If you push first
  then open the MR, the overlap window is small and the bug hides — until a bot
  (renovate/dependabot) starts pushing onto open MRs and doubles every run. Don't
  judge correctness by "I haven't noticed duplicates."
- **Testing every branch costs CI on WIP.** Matching `$CI_COMMIT_BRANCH` runs the
  full test+build on pre-MR feature pushes too. Workflow dedup keeps it to one run
  per push; if that churn is heavy, reach for `changes:` filters (below) rather
  than narrowing back to `main`.
- **Don't drop `build`'s `merge_request_event` rule when adding `changes:`.** The
  easy monorepo mistake: gate build on `$CI_COMMIT_BRANCH` + `changes:` only. In
  an MR pipeline `$CI_COMMIT_BRANCH` is empty, so the image then **never builds on
  MRs** — and the branch pipeline that would've built it is suppressed by the
  workflow dedup. Build (and the image-scan that `needs:` it) needs its own
  `merge_request_event` rule, also `changes:`-scoped. This asymmetry hides behind
  a green dedup: no *duplicate* pipelines, but *missing* jobs. See
  [Monorepo (GitLab)](#monorepo-gitlab) for the full per-component anchor.
- **Monorepos** — [[ci-paths]] covers GitHub (`paths:`); on GitLab add `changes:`
  filters to the job `rules` instead (see [Monorepo (GitLab)](#monorepo-gitlab)).
  The workflow dedup block stays identical either way.
