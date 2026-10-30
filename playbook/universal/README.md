# Universal Playbook

Tooling decisions applicable to every project regardless of language.

## Pages

- [mise.md](./mise.md) — pinned tool versions (node, python, uv, etc.)
- [lefthook.md](./lefthook.md) — git hooks with autofix + restage
- [line-limit.md](./line-limit.md) — per-file line cap as a sprawl proxy (CI gate, optional local hook)
- [ci-github.md](./ci-github.md) — single-project GitHub Actions CI: lint + typecheck + test
- [ci-gitlab.md](./ci-gitlab.md) — single-project GitLab CI pipeline skeleton
- [releases-github.md](./releases-github.md) — release-please for GitHub
- [releases-gitlab.md](./releases-gitlab.md) — semantic-release for GitLab
- [github-settings.md](./github-settings.md) — GitHub repo settings, default-branch ruleset, Actions token, Dependabot alerts (gh api)
- [security.md](./security.md) — semgrep (SAST) + trivy (fs + image)
- [conventional-commits.md](./conventional-commits.md) — commit message format
- [codeowners.md](./codeowners.md) — required reviewers auto-assigned per path
- [dependabot.md](./dependabot.md) — automated dep updates (GitHub only — GH Actions + npm + pip)
- [renovate.md](./renovate.md) — automated dep updates (GitLab + GitHub, broader ecosystem coverage)
- [dockerfile.md](./dockerfile.md) — Dockerfile + .dockerignore: digest-pinned Chainguard base, uv venv stage, non-root, build-time import check
