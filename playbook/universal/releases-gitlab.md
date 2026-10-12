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
  image: node:24
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
