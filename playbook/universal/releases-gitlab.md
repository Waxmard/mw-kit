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
    ["@semantic-release/release-notes-generator", { "preset": "conventionalcommits" }],
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
    - npx -p semantic-release -p @semantic-release/gitlab -p @semantic-release/changelog -p @semantic-release/git -p conventional-changelog-conventionalcommits semantic-release
```

## Token

Project access token with `api` + `write_repository` scope. Save as `SEMANTIC_RELEASE_TOKEN` CI variable, masked.

## Bump rules

Each commit is matched against `releaseRules` **first-match-wins, in listed order**; only if *no* custom rule matches does the commit fall through to the analyzer defaults (`breaking`→major, `feat`→minor, `fix`/`perf`→patch). So a custom rule **shadows** the defaults for any commit it matches — it does not "merge."

That's why `{ "breaking": true, "release": "major" }` is listed **first**: a `feat!` / `BREAKING CHANGE:` commit also matches `type: feat`, so if you ever add `{ "type": "feat", ... }` to the list above the breaking rule, breaking changes silently downgrade to that type's bump. Keep `breaking` first and you're safe regardless of what type rules follow. The rules above then add `refactor`, `build`, `chore`, `ci`, `style` → patch so nearly every conventional commit cuts a release; `feat`/`fix`/`perf` fall through to defaults. Drop a line to exclude a type. `docs`/`test` stay non-releasing by omission.

## Preset

`"preset": "conventionalcommits"` on **both** `commit-analyzer` and `release-notes-generator` is required — without it semantic-release uses the **angular** preset, whose header regex doesn't recognize the `!` breaking marker, so `feat!:` is treated as a non-breaking `feat` (only a `BREAKING CHANGE:` footer would bump major). The preset ships in a separate package: add `conventional-changelog-conventionalcommits` as a devDep (and to the pipeline `npx -p …` list, as above). The notes-generator preset also renders every type's section in the changelog, not just `feat`/`fix`/`perf`.

## Gotchas

- **`feat!` needs the `conventionalcommits` preset** (see above) — under the default angular preset the `!` is ignored and the breaking change ships as a plain minor.
- Tag-on-push by default (no review PR). For a review workflow, use `dryRun` on MRs and let main pushes tag.
- The `@semantic-release/git` plugin commits the changelog back — make sure the bot user can push to `main` (protected branch exception).
- **`chore` now releases**, so dependency bumps (`chore(deps): ...`) cut a patch on their own — desired here, but it means more frequent tags than the stock config.
