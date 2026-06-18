---
tool: claude-review
scope: universal
tier: baseline
summary: "Claude Code reviews every PR via claude-code-action + the code-review plugin"
targets: [".github/workflows/claude-code-review.yml"]
platform: github
---

# Claude Code Review

## What

Runs `anthropics/claude-code-action` on every PR, invoking the `code-review`
plugin from the official Claude Code marketplace. Claude reviews the diff and
posts findings as PR comments — the bot half of the bot-then-human review flow.

## Why

- Catches correctness bugs and obvious cleanups before a human reviewer spends
  time on them.
- Uses the maintained `code-review` plugin rather than a hand-rolled prompt, so
  the review behavior tracks upstream improvements.
- OAuth token auth (`CLAUDE_CODE_OAUTH_TOKEN`) reuses an existing Claude
  subscription — no separate API billing to manage.

## Config

`.github/workflows/claude-code-review.yml`:

```yaml
# Requires a CLAUDE_CODE_OAUTH_TOKEN repo secret.
# Generate with `claude setup-token`, then add under
# Settings → Secrets and variables → Actions.
name: Claude Code Review

on:
  pull_request:
    types: [opened, synchronize, ready_for_review, reopened]

jobs:
  claude-review:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
      issues: read
      id-token: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v6
        with:
          fetch-depth: 1

      - name: Run Claude Code Review
        id: claude-review
        uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          plugin_marketplaces: "https://github.com/anthropics/claude-code.git"
          plugins: "code-review@claude-code-plugins"
          prompt: "/code-review:code-review ${{ github.repository }}/pull/${{ github.event.pull_request.number }}"
          show_full_output: true
```

## Setup

Three things, all required — the action fails or self-skips without each:

1. **OAuth token** — add a `CLAUDE_CODE_OAUTH_TOKEN` repo secret. Generate it
   locally with `claude setup-token` (requires a Claude subscription), then store
   it under **Settings → Secrets and variables → Actions**.
2. **GitHub App** — install the Claude Code app at
   <https://github.com/apps/claude> and grant it the repo. The token authenticates
   *you*; the app grants the action permission to act on the repo. Skipping it
   gives `401 ... Claude Code is not installed on this repository`.
3. **Land it on `main` first** — see the default-branch gotcha below.

## Gotchas

- **Must exist on the default branch.** The action validates that the workflow
  file matches the version on `main` and self-skips otherwise (a security guard
  against a PR editing the review workflow to exfiltrate secrets). So on the PR
  that *first adds* this file you'll see `Skipping action due to workflow
  validation` — that's expected; merge to `main`, then every later PR reviews
  normally. (GitHub triggers the job from the head branch, but this extra check
  is the action's own.)
- `pull-requests: write` is required so Claude can post review comments;
  `id-token: write` is required for the action's OIDC auth.
- Fires on `synchronize` too, so each push re-reviews — expected, but it consumes
  usage on noisy branches. Scope with `paths:` under `on.pull_request` if needed.
- Filter to specific authors (e.g. first-time contributors only) with a job-level
  `if:` on `github.event.pull_request.author_association` to limit cost.
- GitHub-only — `code-review@code-review:code-review` (the local skill) covers
  GitLab MRs interactively; there's no equivalent CI action there.
