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
    - npx -p semantic-release -p @semantic-release/gitlab -p @semantic-release/changelog -p @semantic-release/git -p conventional-changelog-conventionalcommits@9 semantic-release
```

## Token

Project access token with `api` + `write_repository` scope. Save as `SEMANTIC_RELEASE_TOKEN` CI variable, masked.

## Bump rules

Each commit is matched against `releaseRules` **first-match-wins, in listed order**; only if *no* custom rule matches does the commit fall through to the analyzer defaults (`breaking`→major, `feat`→minor, `fix`/`perf`→patch). So a custom rule **shadows** the defaults for any commit it matches — it does not "merge."

That's why `{ "breaking": true, "release": "major" }` is listed **first**: a `feat!` / `BREAKING CHANGE:` commit also matches `type: feat`, so if you ever add `{ "type": "feat", ... }` to the list above the breaking rule, breaking changes silently downgrade to that type's bump. Keep `breaking` first and you're safe regardless of what type rules follow. The rules above then add `refactor`, `build`, `chore`, `ci`, `style` → patch so nearly every conventional commit cuts a release; `feat`/`fix`/`perf` fall through to defaults. Drop a line to exclude a type. `docs`/`test` stay non-releasing by omission.

## Preset

`"preset": "conventionalcommits"` on **both** `commit-analyzer` and `release-notes-generator` is required — without it semantic-release uses the **angular** preset, whose header regex doesn't recognize the `!` breaking marker, so `feat!:` is treated as a non-breaking `feat` (only a `BREAKING CHANGE:` footer would bump major). The preset ships in a separate package: add `conventional-changelog-conventionalcommits` as a devDep (and to the pipeline `npx -p …` list, as above).

**Pin that preset to `^9` — do not let it float to v10.** `@semantic-release/release-notes-generator@14` (the latest, bundled by `semantic-release@25`) is built on the old conventional-changelog generation (`conventional-changelog-writer@8`, `conventional-commits-parser@6`). `conventional-changelog-conventionalcommits@10` is a ground-up rewrite onto the new `@conventional-changelog/*` packages (`@conventional-changelog/template`) and is **silently incompatible** with `writer@8`: every commit is dropped during rendering, so *every* release — `feat`/`fix` included — produces a **header-only changelog with no body**. There is currently no `release-notes-generator` that supports v10. Pin `"conventional-changelog-conventionalcommits": "^9.3.1"` and add a Renovate guard so it can't be bumped:

```json
{
  "matchPackageNames": ["conventional-changelog-conventionalcommits"],
  "allowedVersions": "<10"
}
```

**The `^9` floor matters as much as the `<10` ceiling — and it is why the preset must be a *direct* devDep, not an inherited one.** `commit-analyzer@13` and `release-notes-generator@14` both end with `return { ...loadedConfig.parser, ...parserOpts }` — they read the **`.parser` / `.writer`** keys, which the preset only started exposing in **v8**. v7 and earlier expose the old `.parserOpts` / `.writerOpts` names, so the spread yields `undefined` and **every preset option is silently discarded**; the parser falls back to its built-in defaults, which have no `breakingHeaderPattern` at all. Verified on a clean install of `semantic-release@25.0.3`:

| preset version | `feat!: x` | `feat: x` | `chore: x` |
| --- | --- | --- | --- |
| `7.0.2` | **no release** | minor | patch |
| `9.3.1` | major | minor | patch |

Note the failure is *worse* than the angular fallback: angular at least parses `feat!` as a minor, while a v7 preset parses it as nothing at all. Nothing logs a warning — `preset` resolves, returns an object, and the options evaporate. This is the trap when the package arrives **transitively** (e.g. `@commitlint/config-conventional` pulls its own copy): a lockfile can say `9.3.1` while a stale `node_modules` still has `7.0.2`, and the two disagree about whether `feat!` cuts a release. Declare it in `devDependencies` yourself so the range is yours to control.

**`presetConfig.types` on the notes-generator is mandatory whenever `releaseRules` releases on types beyond `feat`/`fix`/`perf`.** The conventionalcommits preset's *default* type table hides `refactor`/`build`/`ci`/`chore`/`style` — so a release driven solely by one of those bumps the version but writes a **header-only changelog entry with no body**. The fix is to spell out a `presetConfig.types` list that un-hides every type you release on (config above). Keep `presetConfig.types` aligned with `releaseRules`: every type that cuts a release needs a visible `section` here, or its release lands blank.

## Gotchas

- **`feat!` needs the `conventionalcommits` preset** (see above) — under the default angular preset the `!` is ignored and the breaking change ships as a plain minor.
- **`feat!` silently cutting *no* release means the preset resolved below v8.** Not a config bug — declaring `preset` has no effect on v7 and earlier (key rename, see Preset). Check the installed version, not the lockfile: `npm ls conventional-changelog-conventionalcommits`. A stale `node_modules` reproduces this locally while CI is fine, and vice versa.
- Tag-on-push by default (no review PR). For a review workflow, use `dryRun` on MRs and let main pushes tag.
- The `@semantic-release/git` plugin commits the changelog back — make sure the bot user can push to `main` (protected branch exception).
- **`chore` now releases**, so dependency bumps (`chore(deps): ...`) cut a patch on their own — desired here, but it means more frequent tags than the stock config.
- **Empty changelog bodies = the preset floated to v10.** If releases suddenly start cutting versions with header-only changelog entries (no `### Features`/`### Bug Fixes`), check `conventional-changelog-conventionalcommits` — a v10 bump breaks rendering for the whole `semantic-release@25`/`writer@8` stack. Pin `^9` (see Preset). The breakage is silent: the version still bumps and the release still tags, only the notes go blank.
