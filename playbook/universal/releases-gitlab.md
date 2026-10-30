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
        { "revert": true, "release": "patch" }
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

That's why `{ "breaking": true, "release": "major" }` is listed **first**: a `feat!` / `BREAKING CHANGE:` commit also matches `type: feat`, so if you ever add `{ "type": "feat", ... }` to the list above the breaking rule, breaking changes silently downgrade to that type's bump. Keep `breaking` first and you're safe regardless of what type rules follow. Beyond that, `feat`/`fix`/`perf` fall through to the analyzer defaults and every other type is non-releasing.

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
- **`@semantic-release/exec` commands are lodash templates.** `${...}` is evaluated as a template variable before the shell sees it, so `${GITLAB_TOKEN}` fails with `ReferenceError: GITLAB_TOKEN is not defined`. Write env vars as bare `$VAR`, and keep `${...}` for `nextRelease.*`.
