---
tool: releases-monorepo
scope: monorepo
tier: baseline
summary: "Per-component independent releases via semantic-release-monorepo (path-scoped bumps, component-scoped tags)"
targets: [".releaserc.json", "package.json", ".gitlab-ci.yml"]
platform: gitlab
---

# Monorepo releases: semantic-release-monorepo

## What

One git repo, several independently released components (`service-a/`,
`service-b/`, …). Each component gets its **own** version line, tag namespace
(`service-a-v1.4.0`), changelog, and image tag — driven by the commits that
touched *that component's directory*.

[node `semantic-release`](https://semantic-release.gitbook.io/) +
[`semantic-release-monorepo`](https://github.com/pmowrer/semantic-release-monorepo)
per component. The monorepo plugin rewrites commit analysis to only consider
commits whose changed files fall under the component's directory
(`git log --name-only` scoping).

## Why not [releases-python](../python/releases-python.md) / [releases-gitlab](../universal/releases-gitlab.md)

Both PSR and node `semantic-release` compute **one version per repo**. They read
commit *messages* in a range (since the last matching tag), not changed *paths*.
So in a monorepo:

- PSR has **no native path-scoped commit analysis** (its maintainers recommend
  one package per repo). GitLab `rules: changes:` can gate *whether* a release
  job runs, but once it runs the tool over-counts the range.

**Rule:** single package on GitLab → [releases-python](../python/releases-python.md) (Python) or
[releases-gitlab](../universal/releases-gitlab.md) (other). Multi-component repo → this page, per component.

## Config

Each component dir holds two files.

`<component>/.releaserc.json`:

```json
{
  "extends": "semantic-release-monorepo",
  "branches": ["main"],
  "tagFormat": "<component>-v${version}",
  "plugins": [
    [
      "@semantic-release/commit-analyzer",
      {
        "preset": "conventionalcommits",
        "releaseRules": [
          { "breaking": true, "release": "major" },
          { "revert": true, "release": "patch" }
        ]
      }
    ],
    ["@semantic-release/release-notes-generator", {
      "preset": "conventionalcommits",
      "presetConfig": {
        "types": [
          { "type": "feat", "section": "Features" },
          { "type": "fix", "section": "Bug Fixes" },
          { "type": "perf", "section": "Performance Improvements" },
          { "type": "revert", "section": "Reverts" },
          { "type": "refactor", "hidden": true },
          { "type": "build", "hidden": true },
          { "type": "chore", "hidden": true },
          { "type": "ci", "hidden": true },
          { "type": "style", "hidden": true },
          { "type": "docs", "hidden": true },
          { "type": "test", "hidden": true }
        ]
      }
    }],
    "@semantic-release/changelog",
    [
      "@semantic-release/exec",
      {
        "prepareCmd": "sed -i 's/^version = \".*\"/version = \"${nextRelease.version}\"/' pyproject.toml && N=$(sed -n 's/^name = \"\\(.*\\)\"/\\1/p' pyproject.toml | head -n 1) && sed -i \"/^name = \\\"$N\\\"\\$/{n;s/^version = \\\".*\\\"/version = \\\"${nextRelease.version}\\\"/}\" uv.lock",
        "publishCmd": "cd \"$CI_PROJECT_DIR\" && gcrane tag $REGISTRY/<component>:$COMMIT_HASH ${nextRelease.version} && gcrane tag $REGISTRY/<component>:$COMMIT_HASH latest"
      }
    ],
    [
      "@semantic-release/git",
      {
        "assets": ["pyproject.toml", "uv.lock", "CHANGELOG.md"],
        "message": "chore(release): <component>-v${nextRelease.version} [skip ci]\n\n${nextRelease.notes}"
      }
    ],
    "@semantic-release/gitlab"
  ]
}
```

`<component>/package.json` — a shim so the monorepo plugin reads a deterministic
name + path (the component is e.g. a Python app, not a JS package):

```json
{
  "name": "<component>",
  "version": "0.0.0",
  "private": true,
  "description": "Release metadata only — semantic-release-monorepo scopes commits to this directory."
}
```

- `releaseRules`, `preset`, `presetConfig.types`, and the `^9` preset pin follow [releases-gitlab](../universal/releases-gitlab.md) (Bump rules / Preset) exactly.
- `prepareCmd` writes the computed version back into the component's manifest
  (Python keeps `version = "0.0.0"` as a placeholder; the git tag is truth).
- It also bumps the component's own entry in `uv.lock`. [ci-gitlab](../universal/ci-gitlab.md)
  runs `uv sync --locked`, which fails on the next pipeline once `pyproject.toml` and the
  lock's root `version` disagree. The name is read from `pyproject.toml` because forks rename
  it. The shell variable is `$N`, never `${N}`: semantic-release expands `${…}` as a template
  before the shell runs. `sed` instead of `uv lock` because `node:NN-alpine` has no `uv`.
- `publishCmd` retags the already-built image (see CI below) — `gcrane` only runs
  when a release actually happens. It `cd`s back to the repo root because the
  credential paths are relative to it (see Gotchas).

## CI wiring

Root `.gitlab-ci.yml` owns shared infra and `include`s each component:

```yaml
include:
  - component: $CI_SERVER_FQDN/.../gcp-auth@0.0.4
    inputs: { gcp_service_account: builder@PROJECT.iam.gserviceaccount.com }
  - local: service-a/.gitlab-ci.yml
  # - local: service-b/.gitlab-ci.yml   # added when the component lands

# The component's id_token + GAC_JSON are what release jobs use; its job is not.
gcp-auth:
  rules: [{ when: never }]

variables:
  REGISTRY: REGION-docker.pkg.dev/PROJECT/REPO
stages: [test, build, scan, release, maintenance]
```

`<component>/.gitlab-ci.yml` — build tags the image with `$CI_COMMIT_SHORT_SHA`,
the release job (node) retags it to the version. The release job runs on every
`main` pipeline; the monorepo plugin no-ops when nothing under the component
changed:

```yaml
<component>-semantic-release:
  stage: release
  image: node:NN-alpine  # current Node Active LTS
  variables: { GIT_DEPTH: "0" }
  needs:
    - { job: <component>-build, optional: true }
  before_script:
    - apk add --no-cache curl git
    - export COMMIT_HASH=${CI_COMMIT_SHORT_SHA}
    - <download gcrane, verify checksum>     # same go-containerregistry release tarball as crane
    - test -n "$GITLAB_TOKEN"   || { echo "set GITLAB_TOKEN (api+write_repository)"; exit 1; }
    - mkdir -p .gcloud
    - echo "${GCP_JOB_JWT}" > .gcloud/gcp_job_jwt.json
    - echo "${GAC_JSON}" > "${GOOGLE_APPLICATION_CREDENTIALS}"
    - cd <component>
  script:
    - npm install --no-save semantic-release@25 semantic-release-monorepo@8 conventional-changelog-conventionalcommits@9 @semantic-release/{changelog,commit-analyzer,exec,git,gitlab,release-notes-generator}
    - npx semantic-release
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'
  tags: [cloud]
```

The image build is one `docker buildx bake <component>` target (one per
component, see [docker-bake](./docker-bake.md)).

Test/build/scan job `rules`: the [ci-gitlab](../universal/ci-gitlab.md#monorepo-variant) monorepo anchor.

## Commit convention

Two monorepo commit rules:

1. **Scope every commit with the component dir** — `fix(service-a): …`.
2. **Keep commits atomic — one component each.** The plugin decides *whether* a
   component releases by changed files, but the *bump size* comes from the
   message; a commit touching two components releases both with the same message.

## Gotchas

- **`package.json` shim is required** even for non-JS components — the plugin
  (and `semantic-release` core) read it on load. Keep it `private`, no deps; CI
  installs the toolchain with `npm install --no-save`, so [renovate](../universal/renovate.md) ignores it.
- **No build on the tag pipeline.** The release commit
  carries `[skip ci]`, which on GitLab suppresses the tag pipeline — so you
  *can't* build images on the tag. Build on `main` with `$SHORT_SHA`, then
  `gcrane`-retag to the version inside the release job. Same pattern works for a
  single repo (`releases-python` + gcrane).
- **Tokens:** `GITLAB_TOKEN` (api + write_repository, bot allowed on protected
  `main`) for `@semantic-release/gitlab`. Artifact Registry auth is minted in the
  release job itself: the gcp-auth component injects a `GCP_JOB_JWT` id_token
  into every job plus `GAC_JSON`/`GOOGLE_APPLICATION_CREDENTIALS`, and `gcrane`
  exchanges them for a fresh token on demand.
- **Never pass `GCLOUD_TOKEN` between jobs.** The gcp-auth job's dotenv token
  lives one hour; a release job that queues behind the build, or a retry the
  next day, fails with `401 UNAUTHORIZED: authentication failed` (not a 403 —
  IAM is fine). `crane auth login` doesn't validate, so the error surfaces only
  at the push.
- **No `needs: gcp-auth` on the release job.** The component injects the id_token and
  `GAC_JSON` into every job, and the `before_script` above writes fresh `.gcloud/` files
  from them. The gcp-auth job's artifacts add a dependency and creds that expire about an
  hour after that job ran. Reviewers (human or bot) who reason "explicit `needs:` drops
  artifacts" will flag the omission; it's deliberate.
- **Gitignore `.gcloud/`.** The credential files land in `$CI_PROJECT_DIR/.gcloud/`.
  `@semantic-release/git` stages only `assets`, but the ignore rule keeps them out of any
  broader `git add`.
- **`gcrane` fails silently.** If the env credentials don't resolve (wrong cwd,
  missing file) it falls back to anonymous and you only see `DENIED:
  Unauthenticated request`. Add `-v` to see the real `Google env error`. Both
  `GOOGLE_APPLICATION_CREDENTIALS` and `credential_source.file` inside
  `GAC_JSON` are relative to `$CI_PROJECT_DIR`, hence the `cd` in `publishCmd`.
- New component: copy both files, add a docker-bake target and an `include: local` line.

## Unified repo-wide release (alternative)

For monorepos whose components deploy in lockstep under a single version number, use a single root `.releaserc.json` ([releases-gitlab](../universal/releases-gitlab.md)) instead of per-component releases:

- `@semantic-release/exec` `prepareCmd` updates every component's manifest (`npm version --prefix frontend --no-git-tag-version --allow-same-version ${nextRelease.version}` and `sed -i 's/^version = ".*"/version = "${nextRelease.version}"/' backend/pyproject.toml`). It also updates each Python component's `uv.lock` root entry with the per-component `sed` above, paths prefixed (`backend/pyproject.toml`, `backend/uv.lock`), plus any other file that carries the version (e.g. an A2A agent card's `version:`).
- `publishCmd` retags all component images with `gcrane tag`.
- `@semantic-release/git` commits every updated file (`frontend/package.json`, `frontend/package-lock.json`, `backend/pyproject.toml`, `backend/uv.lock`, `CHANGELOG.md`, plus any extra version files) in one release commit.
