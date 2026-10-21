---
tool: releases-gitlab
scope: universal
tier: baseline
summary: "semantic-release: tag + changelog on GitLab"
targets: [".releaserc.json", ".gitlab-ci.yml"]
platform: gitlab
---

# Releases on GitLab: semantic-release

## What

[semantic-release](https://semantic-release.gitbook.io/) cuts tags + changelogs on every push to `main` based on Conventional Commits.

## Why on GitLab

release-please is GitHub-flavored (uses Actions, GitHub PR auto-merge labels). GitLab plugin handles releases + MR comments cleanly.

**Python repos: use [releases-python](../python/releases-python.md) (python-semantic-release) instead** — same conventional-commits flow without pulling node into a Python pipeline. This page is for node/other repos on GitLab. Never apply both.

## Config

`.releaserc.json`:

```json
{
  "branches": ["main"],
  "plugins": [
    ["@semantic-release/commit-analyzer", {
      "preset": "conventionalcommits",
      "releaseRules": [
        { "breaking": true, "release": "major" },
        { "revert": true, "release": "patch" },
        { "type": "refactor", "release": "patch" },
        { "type": "build", "release": "patch" },
        { "type": "chore", "release": "patch" },
        { "type": "ci", "release": "patch" },
        { "type": "style", "release": "patch" }
      ]
    }],
    ["@semantic-release/release-notes-generator", {
      "preset": "conventionalcommits",
      "presetConfig": {
        "types": [
          { "type": "feat", "section": "Features" },
          { "type": "fix", "section": "Bug Fixes" },
          { "type": "perf", "section": "Performance Improvements" },
          { "type": "revert", "section": "Reverts" },
          { "type": "refactor", "section": "Refactoring" },
          { "type": "build", "section": "Build System" },
          { "type": "chore", "section": "Chores" },
          { "type": "ci", "section": "Continuous Integration" },
          { "type": "style", "section": "Styles" },
          { "type": "docs", "hidden": true },
          { "type": "test", "hidden": true }
        ]
      }
    }],
    ["@semantic-release/changelog", { "changelogFile": "CHANGELOG.md" }],
    ["@semantic-release/git", {
      "assets": ["CHANGELOG.md", "package.json"],
      "message": "chore(release): ${nextRelease.version} [skip ci]\n\n${nextRelease.notes}"
    }],
    "@semantic-release/gitlab"
  ]
}
```

## Pipeline

`.gitlab-ci.yml`:

```yaml
release:
  stage: release
  image: node:NN  # current Node Active LTS
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
  variables:
    GITLAB_TOKEN: $SEMANTIC_RELEASE_TOKEN
  script:
    - npx -p semantic-release -p @semantic-release/gitlab -p @semantic-release/changelog -p @semantic-release/git -p conventional-changelog-conventionalcommits@9 semantic-release
```

## Token

Project access token with `api` + `write_repository` scope. Save as `SEMANTIC_RELEASE_TOKEN` CI variable, masked.

## Bump rules

Each commit is matched against `releaseRules` **first-match-wins, in listed order**; only if *no* custom rule matches does the commit fall through to the analyzer defaults (`breaking`→major, `feat`→minor, `fix`/`perf`→patch). So a custom rule **shadows** the defaults for any commit it matches — it does not "merge."

That's why `{ "breaking": true, "release": "major" }` is listed **first**: a `feat!` / `BREAKING CHANGE:` commit also matches `type: feat`, so if you ever add `{ "type": "feat", ... }` to the list above the breaking rule, breaking changes silently downgrade to that type's bump. Keep `breaking` first and you're safe regardless of what type rules follow. The rules above then add `refactor`, `build`, `chore`, `ci`, `style` → patch so nearly every conventional commit cuts a release; `feat`/`fix`/`perf` fall through to defaults. Drop a line to exclude a type. `docs`/`test` stay non-releasing by omission.

## Preset

`"preset": "conventionalcommits"` on **both** `commit-analyzer` and `release-notes-generator` is required — without it semantic-release uses the **angular** preset, whose header regex doesn't recognize the `!` breaking marker, so `feat!:` is treated as a non-breaking `feat` (only a `BREAKING CHANGE:` footer would bump major). The preset ships in a separate package: add `conventional-changelog-conventionalcommits` as a devDep (and to the pipeline `npx -p …` list, as above).

Pin `conventional-changelog-conventionalcommits` to `^9` and Renovate-guard it below 10 (JSON below): v10 is silently incompatible with `release-notes-generator@14` — every release gets a header-only changelog. Below v8 the preset's options are silently dropped and `feat!` cuts no release. If a package.json exists, declare it as a direct devDependency so a transitive v7 can't win; check with `npm ls conventional-changelog-conventionalcommits`.

```json
{
  "matchPackageNames": ["conventional-changelog-conventionalcommits"],
  "allowedVersions": "<10"
}
```

Every type `releaseRules` releases on needs a visible `section` in `presetConfig.types`, or that release's changelog entry is empty.

## Gotchas

- The `@semantic-release/git` plugin commits the changelog back — make sure the bot user can push to `main` (protected branch exception).
- **`chore` now releases**, so dependency bumps (`chore(deps): ...`) cut a patch on their own — desired here, but it means more frequent tags than the stock config.
- **`@semantic-release/exec` commands are lodash templates.** `${...}` is evaluated as a template variable before the shell sees it, so `${GITLAB_TOKEN}` fails with `ReferenceError: GITLAB_TOKEN is not defined`. Write env vars as bare `$VAR`, and keep `${...}` for `nextRelease.*`.

## Dev → main flow: back-sync dev

For repos where work lands on `dev` and `dev` → `main` MRs cut releases. The release commit (`chore(release): X.Y.Z [skip ci]`) exists only on `main`, so the next `dev` → `main` MR can't fast-forward and `dev` never sees the bumped versions or `CHANGELOG.md`. Add `@semantic-release/exec` with a `successCmd` that fast-forwards `dev` to the release commit:

```json
["@semantic-release/exec", {
  "successCmd": "git push \"https://gitlab-ci-token:$GITLAB_TOKEN@$CI_SERVER_HOST/$CI_PROJECT_PATH.git\" HEAD:refs/heads/dev || echo 'WARN: dev moved ahead during release; merge main into dev manually'"
}]
```

Add `@semantic-release/exec` to the pipeline `npx -p …` list. The push only fast-forwards, so if `dev` got new commits during the release it is rejected and the job just warns. The release commit carries `[skip ci]`, so the `dev` push doesn't start a pipeline.

Project settings to go with it:

- **Merge method: fast-forward** (Settings → Merge requests). Keeps `dev` and `main` on identical SHAs.
- **Squash on `main`: Do not allow** (Settings → Repository → Branch rules → `main`). Leave `All branches` on Encourage for feature → `dev` MRs. A squashed `dev` → `main` merge would collapse every commit into one and lose the per-commit bumps and changelog entries.
- **Untick "Enable 'Delete source branch' option by default"** (Settings → Merge requests), or untick it on each `dev` → `main` MR, so the merge never removes `dev`.
- **Token role: Maintainer.** The token pushes to protected `main` and `dev`.

Gotchas:

- **No tag yet means the first release is `1.0.0`.** Tag the current `main` first (`git tag 0.1.0 origin/main && git push origin 0.1.0`) to stay on `0.x`.
- **`[skip ci]` anywhere in the tip commit message skips the pipeline**, including a commit body that only quotes it. If the tip of `dev` mentions `[skip ci]`, run the pipeline by hand (`glab ci run -b dev`) or push another commit before opening the `dev` → `main` MR.
- **If `successCmd` fails, the release is already out.** The tag, images, and GitLab Release exist and only the job is red. Don't retry: semantic-release finds nothing new to release and skips `successCmd`. Run `git merge --ff-only origin/main` on `dev` and push it before committing anything else to `dev`.
- GitHub equivalent: [releases-github](./releases-github.md#dev--main-flow-back-sync-dev).

## Manually cut release tags (retag, don't rebuild)

For repos that cut release tags by hand (no release tool creating them in a
release job). The tag pipeline must exist — the `$CI_COMMIT_TAG` workflow rule in
[gitlab-pipeline-dedup](./gitlab-pipeline-dedup.md) — and must run only a retag job:

```yaml
release-images:
  stage: push
  image: gcr.io/go-containerregistry/crane:debug
  interruptible: false
  needs: []                       # build jobs don't exist in tag pipelines
  script:
    - for img in api worker; do crane tag "$REGISTRY/$img:$CI_COMMIT_SHORT_SHA" "$CI_COMMIT_TAG" || exit 1; done
  rules:
    - if: $CI_COMMIT_TAG =~ /^\d+\.\d+\.\d+/
```

Registry auth goes in `before_script`, per registry (`crane auth login …`). For
Artifact Registry (`*.pkg.dev`), use `gcrane` with the job's own id_token instead
of a `GCLOUD_TOKEN` handed over from another job — that token expires after an
hour, so retries fail; see [releases-monorepo](../monorepo/releases-monorepo.md) §"Gotchas". This
is the manual-tag form of "Build once, ship the tested artifact"
([gitlab-pipeline-dedup](./gitlab-pipeline-dedup.md) Why): a
missing `:$CI_COMMIT_SHORT_SHA` image fails the job instead of rebuilding.
