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

release-please is GitHub-flavored (uses Actions, GitHub PR auto-merge labels). semantic-release runs anywhere; GitLab plugin handles releases + MR comments cleanly.

**Python repos: use [[releases-python]] (python-semantic-release) instead** — same conventional-commits flow without pulling node into a Python pipeline. This page is for node/other repos on GitLab. Never apply both.

## Config

`.releaserc.json`:

```json
{
  "branches": ["main"],
  "plugins": [
    ["@semantic-release/commit-analyzer", {
      "releaseRules": [
        { "type": "refactor", "release": "patch" },
        { "type": "build", "release": "patch" },
        { "type": "chore", "release": "patch" },
        { "type": "ci", "release": "patch" },
        { "type": "style", "release": "patch" }
      ]
    }],
    "@semantic-release/release-notes-generator",
    ["@semantic-release/changelog", { "changelogFile": "CHANGELOG.md" }],
    ["@semantic-release/git", {
      "assets": ["CHANGELOG.md", "package.json"],
      "message": "chore(release): ${nextRelease.version}\n\n${nextRelease.notes}"
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
  image: node:22
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
  variables:
    GITLAB_TOKEN: $SEMANTIC_RELEASE_TOKEN
  script:
    - npx -p semantic-release -p @semantic-release/gitlab -p @semantic-release/changelog -p @semantic-release/git semantic-release
```

## Token

Project access token with `api` + `write_repository` scope. Save as `SEMANTIC_RELEASE_TOKEN` CI variable, masked.

## Bump rules

`releaseRules` **merges with**, doesn't replace, the analyzer defaults: breaking → major, `feat` → minor, `fix`/`perf`/`revert` → patch. The rules above add `refactor`, `build`, `chore`, `ci`, `style` → patch so nearly every conventional commit cuts a release. Drop a line to exclude a type. `docs`/`test` stay non-releasing here by omission.

## Gotchas

- Tag-on-push by default (no review PR). For a review workflow, use `dryRun` on MRs and let main pushes tag.
- The `@semantic-release/git` plugin commits the changelog back — make sure the bot user can push to `main` (protected branch exception).
- **`chore` now releases**, so dependency bumps (`chore(deps): ...`) cut a patch on their own — desired here, but it means more frequent tags than the stock config.
