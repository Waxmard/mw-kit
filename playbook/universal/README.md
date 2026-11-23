# Universal Playbook

Tooling decisions applicable to every project regardless of language.

## Pages

- [mise.md](./mise.md) — pinned tool versions (node, python, uv, etc.)
- [lefthook.md](./lefthook.md) — git hooks with autofix + restage
- [line-limit.md](./line-limit.md) — per-file line cap as a sprawl proxy (CI gate, optional local hook)
- [ci-github.md](./ci-github.md) — single-project GitHub Actions CI: lint + typecheck + test
- [releases-github.md](./releases-github.md) — release-please for GitHub
- [github-settings.md](./github-settings.md) — GitHub repo settings, default-branch ruleset, Actions token, Dependabot alerts (gh api)
- [security.md](./security.md) — semgrep (SAST) + trivy (fs + image)
- [conventional-commits.md](./conventional-commits.md) — commit message format
- [codeowners.md](./codeowners.md) — required reviewers auto-assigned per path
- [claude-review.md](./claude-review.md) — optional Claude Code review on every non-draft pull request
- [dependabot.md](./dependabot.md) — automated dep updates (GH Actions + npm + uv)
- [dockerfile.md](./dockerfile.md) — Dockerfile + .dockerignore: digest-pinned Chainguard base, uv venv stage, non-root, build-time import check
- [doc-budgets.md](./doc-budgets.md) — ratcheting byte ceilings for standing docs like AGENTS.md
- [no-comments.md](./no-comments.md) — zero-comment and lint-suppression gate with a small keep-list
