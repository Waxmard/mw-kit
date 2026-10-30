---
tool: releases-github
scope: universal
tier: baseline
summary: "release-please: PR-driven versioning + changelog on GitHub"
targets: ["release-please-config.json", ".release-please-manifest.json", ".github/workflows/release-please.yml"]
platform: github
---

# Releases on GitHub: release-please

## What

[release-please](https://github.com/googleapis/release-please) opens/maintains a PR that bumps the version and updates `CHANGELOG.md` based on Conventional Commits since the last release. Merging the PR cuts the release + tags.

## Why

- Driven by commit messages — no manual version bumping.
- The release PR is reviewable: see exactly what's going out before tagging.
- The workflow below auto-merges the release PR (`gh pr merge --auto`); drop that step to keep merges manual.

## Why not semantic-release

semantic-release is more flexible but Node-centric and tag-on-push (no review PR). release-please's review-PR model is safer for solo/small teams.

## Config

`release-please-config.json`:

```json
{
  "$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
  "packages": {
    ".": {
      "release-type": "simple",
      "include-component-in-tag": false,
      "changelog-sections": [
        { "type": "feat", "section": "Features" },
        { "type": "fix", "section": "Bug Fixes" },
        { "type": "perf", "section": "Performance Improvements" },
        { "type": "refactor", "section": "Code Refactoring" },
        { "type": "docs", "section": "Documentation", "hidden": true },
        { "type": "chore", "section": "Miscellaneous", "hidden": true },
        { "type": "test", "section": "Tests", "hidden": true }
      ]
    }
  }
}
```

`.release-please-manifest.json`:

```json
{ ".": "0.1.0" }
```

## Workflow

`.github/workflows/release-please.yml`:

```yaml
name: Release Please
on:
  push:
    branches: [main]
permissions:
  contents: write
  pull-requests: write
jobs:
  release-please:
    runs-on: ubuntu-latest
    steps:
      - uses: googleapis/release-please-action@v5
        id: release
        with:
          token: ${{ secrets.RELEASE_PLEASE_TOKEN }}

      - name: Auto-merge release PR
        if: steps.release.outputs.prs_created == 'true'
        run: gh pr merge --rebase --auto --repo "${{ github.repository }}" "${{ fromJSON(steps.release.outputs.pr).number }}"
        env:
          GH_TOKEN: ${{ secrets.RELEASE_PLEASE_TOKEN }}
```

## Token

A fine-grained PAT with `contents: write` and `pull-requests: write`. The default `GITHUB_TOKEN` works but **won't trigger downstream workflows** when the release PR merges (e.g. publish workflows that listen on `release` events).

## Bump rules

release-please's bump algorithm is **hardcoded**: breaking → major, `feat` → minor, `fix` → patch, everything else → no release. **It is not configurable per commit type** — `changelog-sections` only controls changelog *display*, not whether a type bumps. Making `refactor`/`build`/`chore` cut a patch requires a custom `VersioningStrategy` class (code, not config), which isn't worth it.

The only built-in knobs (`bump-minor-pre-major`, `bump-patch-for-minor-pre-major`) *lower* severity for pre-1.0 repos — the opposite direction.

## Gotchas

- `release-type: simple` = manage version in `.release-please-manifest.json`. Use `release-type: python` / `node` to also bump `pyproject.toml`/`package.json`.
- Version living in another file (a browser extension's `manifest.json`, a Helm `Chart.yaml`, or `pyproject.toml`)? Keep `simple` and add `"extra-files": [{ "type": "json", "path": "src/manifest.json", "jsonpath": "$.version" }]` to the package config (`type: yaml` for YAML, or `{ "type": "toml", "path": "pyproject.toml", "jsonpath": "$.project.version" }` for TOML).
- **Default branch not `main`:** `release-please-action` defaults `target-branch` to the repo's default branch. Set `target-branch: main` under `with:` if development happens on `dev` and releases cut from `main`. For the full dev → main flow, including back-syncing `dev` after a release, see [Dev → main flow](#dev--main-flow-back-sync-dev) below.

## Dev → main flow: back-sync dev

For repos where work lands on `dev` (the default branch) and releases cut from `main`. The release PR merges into `main` only, so `dev` never gets the version bump or `CHANGELOG.md`. Add a back-sync step to the release-please workflow so it rebases `dev` onto `main` once a release is created:

```yaml
      - uses: googleapis/release-please-action@v5
        id: release
        with:
          token: ${{ secrets.RELEASE_PLEASE_TOKEN }}
          target-branch: main

      # ...auto-merge step unchanged...

      - uses: actions/checkout@v7
        if: steps.release.outputs.release_created == 'true'
        with:
          ref: main
          fetch-depth: 0
          token: ${{ secrets.RELEASE_PLEASE_TOKEN }}

      - name: Back-sync dev
        if: steps.release.outputs.release_created == 'true'
        run: |
          git checkout -B dev origin/dev
          git -c user.name="github-actions[bot]" -c user.email="41898282+github-actions[bot]@users.noreply.github.com" rebase origin/main
          git push --force-with-lease origin dev
```

`release_created` is the root-component output (path `.`). In a manifest monorepo, use `releases_created`.

**Promote `dev` → `main` with "Rebase and merge" (never "Squash and merge").** GitHub's "Rebase and merge" button rewrites commit timestamps and SHAs on `main`, so `main` is never a fast-forward descendant of `dev` after a PR merge. Rebasing `origin/dev` onto `origin/main` in the back-sync step automatically skips the patch-equivalent pre-merge commits already on `main` and replays any newer `dev` commits on top of the release commit, then updates `dev` with `--force-with-lease`. Never squash a `dev` → `main` promotion PR: squashing collapses all commits since the last release into one commit on `main`, which both loses per-commit changelog entries and prevents `git rebase origin/main` from skipping individual `dev` commits as patch-equivalent.

Do not swallow failures with `|| echo "::warning::..."`: if a rebase conflict or concurrent push to `dev` rejects the back-sync, let the step fail so GitHub flags the workflow run instead of leaving `dev` silently behind `main`.

Settings to go with it (see [github-settings](./github-settings.md)):

- **Ruleset covers both branches.** With `dev` as the default branch, `~DEFAULT_BRANCH` only matches `dev`. Set the ruleset's `conditions.ref_name.include` to `["~DEFAULT_BRANCH", "refs/heads/main"]`.
- **Admin bypass stays on** (`actor_id: 5`, `bypass_mode: always`). The back-sync step's `--force-with-lease` push to `dev` bypasses both the `pull_request` and `non_fast_forward` rules on `dev`, so the `RELEASE_PLEASE_TOKEN` owner must be a repo admin.

Gotchas:

- **The back-sync push starts `dev` CI.** It's pushed with a PAT, not `GITHUB_TOKEN`, so `on: push` workflows for `dev` run on the rebased tip. That's harmless; if no new commits landed on `dev` during the release, it's the same tree `main` already tested.
- **If the back-sync step fails, the release is already out.** The tag and GitHub Release exist. Run `git fetch origin && git checkout dev && git rebase origin/main && git push --force-with-lease origin dev` locally to finish the back-sync.
