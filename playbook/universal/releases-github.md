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
- Auto-merge supported (label-driven), so simple repos can be fully automated.
- Google maintains it. Works well with monorepos via packages config.

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
      - uses: googleapis/release-please-action@v4
        id: release
        with:
          token: ${{ secrets.RELEASE_PLEASE_TOKEN }}

      - name: Auto-merge release PR
        run: |
          PR_NUMBER=$(gh pr list --repo "${{ github.repository }}" \
            --label "autorelease: pending" --json number --jq '.[0].number')
          if [ -n "$PR_NUMBER" ]; then
            gh pr merge --rebase --auto --repo "${{ github.repository }}" "$PR_NUMBER"
          fi
        env:
          GH_TOKEN: ${{ secrets.RELEASE_PLEASE_TOKEN }}
```

## Token

A fine-grained PAT with `contents: write` and `pull-requests: write`. The default `GITHUB_TOKEN` works but **won't trigger downstream workflows** when the release PR merges (e.g. publish workflows that listen on `release` events).

## Gotchas

- `release-type: simple` = manage version in `.release-please-manifest.json`. Use `release-type: python` / `node` to also bump `pyproject.toml`/`package.json`.
- Hidden sections still influence release-or-not. `chore` alone won't cut a release; needs a `feat`/`fix`.
- Pair with a CONTRIBUTING note enforcing Conventional Commits.
