---
tool: claude-review
scope: universal
tier: optional
summary: "Optional Claude Code review on every non-draft pull request"
targets: [".github/workflows/claude.yml"]
platform: github
---

# Claude review on pull requests

## What

An optional workflow that runs [claude-code-action](https://github.com/anthropics/claude-code-action) on every non-draft pull request. Claude posts inline and top-level comments, approves when it finds no problem, and requests changes if a later push breaks a PR it already approved. tooling-sync suggests the workflow once per GitHub repo and records a decline.

## Why

- A second reader for solo repos, where the ruleset in [github-settings](./github-settings.md) requires zero approvals.
- The prompt limits the review to bugs, security problems, and `AGENTS.md` violations. It rules out comments on PR scope and on the PR title, description, and commit messages.
- `--allowedTools` limits Claude to reading the PR, commenting, and reviewing this one PR number. It cannot push, merge, or review another PR.
- `concurrency` cancels the in-flight review when a new commit arrives, so only the latest commit is reviewed.

## Config

`.github/workflows/claude.yml`:

```yaml
name: Claude Review

on:
  pull_request:
    types: [opened, synchronize, ready_for_review, reopened]

concurrency:
  group: claude-review-${{ github.event.pull_request.number }}
  cancel-in-progress: true

jobs:
  review:
    if: |
      github.event.pull_request.draft == false &&
      github.event.pull_request.user.login != 'dependabot[bot]' &&
      github.event.pull_request.head.repo.full_name == github.repository &&
      !startsWith(github.event.pull_request.head.ref, 'release-please--')
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
      id-token: write
    steps:
      - name: Checkout repository
        uses: actions/checkout@v7
        with:
          fetch-depth: 1

      - name: Run Claude review
        uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          prompt: |
            REPO: ${{ github.repository }}
            PR NUMBER: ${{ github.event.pull_request.number }}

            Review this pull request for bugs, security problems, and violations of AGENTS.md.
            Do not comment on PR scope, unrelated changes, or whether to split the PR.
            Do not comment on the PR title, description, or commit messages, including whether they match the changes.
            The PR branch is already checked out in the current working directory.

            Use `gh pr comment` for top-level feedback.
            Use `mcp__github_inline_comment__create_inline_comment` (with `confirmed: true`) for specific code issues.
            Only post GitHub comments; do not submit review text as messages.
            If you have already commented on this PR, cover only what changed since and do not repeat earlier comments.
            Approve only when every problem you raised earlier on this PR is fixed or answered and the current changes add no bug, security problem, or AGENTS.md violation.
            To approve, run exactly `gh pr review ${{ github.event.pull_request.number }} --approve --body "<one sentence>"` and post no other comment.
            Before reporting a problem, read your own reviews with `gh pr view ${{ github.event.pull_request.number }} --json reviews` and ignore those whose state is COMMENTED.
            If the newest remaining one is APPROVED, run `gh pr review ${{ github.event.pull_request.number }} --request-changes --body "<each problem on its own line>"` in place of `gh pr comment`, and still add inline comments for specific code issues.
            In every other case post your comments and submit no review.
          claude_args: |
            --append-system-prompt "Follow the repo rules in AGENTS.md."
            --allowedTools "mcp__github_inline_comment__create_inline_comment,Bash(gh pr comment:*),Bash(gh pr diff:*),Bash(gh pr view:*),Bash(gh pr review ${{ github.event.pull_request.number }} --approve:*),Bash(gh pr review ${{ github.event.pull_request.number }} --request-changes:*)"
```

## Setup

Both steps need a repo admin.

1. Install the [Claude GitHub app](https://github.com/apps/claude) on the repository.
2. Generate a token with `claude setup-token` (Pro or Max plan) and store it as an Actions secret. `gh secret set` prompts for the value:

```bash
gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo OWNER/REPO
```

## Gotchas

- **The PR that adds or edits the workflow gets no review.** The action requires `claude.yml` to match the default branch's copy. On a mismatch it logs "Skipping action due to workflow validation" and the run still passes. Reviews start once the change is merged.
- **Approvals are submitted by the Claude app.** `can_approve_pull_request_reviews=false` from [github-settings](./github-settings.md) only restricts the Actions token, so keep it.
- **Dependabot and fork PRs are skipped.** Neither receives repository secrets, so the job `if` excludes them. It also excludes `release-please--` branches from [releases-github](./releases-github.md); drop that line in a repo without release-please.
