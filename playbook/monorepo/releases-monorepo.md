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

One git repo, several independently released components (`orchestrator/`,
`clamav/`, …). Each component gets its **own** version line, tag namespace
(`orchestrator-v1.4.0`), changelog, and image tag — driven by the commits that
touched *that component's directory*.

[node `semantic-release`](https://semantic-release.gitbook.io/) +
[`semantic-release-monorepo`](https://github.com/pmowrer/semantic-release-monorepo)
per component. The monorepo plugin rewrites commit analysis to only consider
commits whose changed files fall under the component's directory
(`git log --name-only` scoping).

## Why not [[releases-python]] / [[releases-gitlab]]

Both PSR and node `semantic-release` compute **one version per repo**. They read
commit *messages* in a range (since the last matching tag), not changed *paths*.
So in a monorepo:

- A `feat(clamav): …` commit still inflates an `orchestrator` bump — wrong.
- PSR has **no native path-scoped commit analysis** (its maintainers recommend
  one package per repo). GitLab `rules: changes:` can gate *whether* a release
  job runs, but once it runs the tool over-counts the range.

`semantic-release-monorepo` is the mature fix: it's the only widely-used plugin
that filters the bump by changed files. PSR has no equivalent — so a monorepo on
GitLab uses node `semantic-release` here even for a pure-Python component.

**Rule:** single package on GitLab → [[releases-python]] (Python) or
[[releases-gitlab]] (other). Multi-component repo → this page, per component.

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
        "releaseRules": [
          { "type": "refactor", "release": "patch" },
          { "type": "build", "release": "patch" },
          { "type": "chore", "release": "patch" },
          { "type": "ci", "release": "patch" },
          { "type": "style", "release": "patch" }
        ]
      }
    ],
    "@semantic-release/release-notes-generator",
    "@semantic-release/changelog",
    [
      "@semantic-release/exec",
      {
        "prepareCmd": "sed -i 's/^version = \".*\"/version = \"${nextRelease.version}\"/' pyproject.toml",
        "publishCmd": "echo \"$GCLOUD_TOKEN\" | crane auth login REGION-docker.pkg.dev -u oauth2accesstoken --password-stdin && crane tag $REGISTRY/<component>:$COMMIT_HASH ${nextRelease.version} && crane tag $REGISTRY/<component>:$COMMIT_HASH latest"
      }
    ],
    [
      "@semantic-release/git",
      {
        "assets": ["pyproject.toml", "CHANGELOG.md"],
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

- `releaseRules` extends the angular preset's `feat`→minor / `fix`,`perf`→patch
  so housekeeping types (`refactor`/`build`/`chore`/`ci`/`style`) also cut a
  patch — drop it for stock angular behaviour.
- `prepareCmd` writes the computed version back into the component's manifest
  (Python keeps `version = "0.0.0"` as a placeholder; the git tag is truth).
- `publishCmd` retags the already-built image (see CI below) — `crane` only runs
  when a release actually happens.

## CI wiring

Root `.gitlab-ci.yml` owns shared infra and `include`s each component:

```yaml
include:
  - component: $CI_SERVER_FQDN/.../gcp-auth@0.0.4
    inputs: { gcp_service_account: builder@PROJECT.iam.gserviceaccount.com }
  - local: orchestrator/.gitlab-ci.yml
  # - local: clamav/.gitlab-ci.yml   # added when the component lands

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
  image: node:22-alpine
  variables: { GIT_DEPTH: "0" }
  needs:
    - { job: gcp-auth, artifacts: true }
    - { job: <component>-build, optional: true }
  before_script:
    - apk add --no-cache curl git
    - export COMMIT_HASH=${CI_COMMIT_SHORT_SHA}
    - <download crane, verify checksum>      # see [[docker-bake]] / backend reference
    - test -n "$GITLAB_TOKEN"   || { echo "set GITLAB_TOKEN (api+write_repository)"; exit 1; }
    - test -n "$GCLOUD_TOKEN"   || { echo "gcp-auth must expose GCLOUD_TOKEN"; exit 1; }
    - cd <component>
  script:
    - npm install --no-save semantic-release@25 semantic-release-monorepo@8 @semantic-release/{changelog,commit-analyzer,exec,git,gitlab,release-notes-generator}
    - npx semantic-release
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'
  tags: [cloud]
```

The image build is one `docker buildx bake <component>` target (one per
component, see [[docker-bake]]).

## Commit convention

Releases need [[conventional-commits]], plus two monorepo rules:

1. **Scope every commit with the component dir** — `fix(orchestrator): …`.
2. **Keep commits atomic — one component each.** The plugin decides *whether* a
   component releases by changed files, but the *bump size* comes from the
   message; a commit touching two components releases both with the same message.

## Gotchas

- **`package.json` shim is required** even for non-JS components — the plugin
  (and `semantic-release` core) read it on load. Keep it `private`, no deps; CI
  installs the toolchain with `npm install --no-save`, so [[renovate]] ignores it.
- **No `version` BuildTools component / tag-pipeline build.** The release commit
  carries `[skip ci]`, which on GitLab suppresses the tag pipeline — so you
  *can't* build images on the tag. Build on `main` with `$SHORT_SHA`, then
  `crane`-retag to the version inside the release job. Same pattern works for a
  single repo (`releases-python` + crane).
- **`chore`→patch means [[renovate]] releases on every bump.** A patch per
  `chore(deps): …`. To accumulate instead, add
  `{ "type": "chore", "scope": "deps", "release": false }` ahead of the `chore`
  rule.
- **Sparse changelogs for housekeeping releases** — `release-notes-generator`
  (angular) only renders `feat`/`fix`/`perf` sections, so a `refactor`-only
  release bumps the version but writes a thin entry. Switch to the
  `conventionalcommits` preset if you want every type in the notes.
- **One version *per component*, not per repo.** Independent cadences are the
  point; don't try to unify them into a single repo version.
- **Tokens:** `GITLAB_TOKEN` (api + write_repository, bot allowed on protected
  `main`) for `@semantic-release/gitlab`; `GCLOUD_TOKEN` (Artifact Registry
  write, from the gcp-auth component) for the crane retag.
- Adding a component = copy both files (swap name / `tagFormat` / image path),
  add a [[docker-bake]] target, add an `include: local` line, mirror the
  component `.gitlab-ci.yml`.
