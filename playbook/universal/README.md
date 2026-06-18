# Universal Playbook

Tooling decisions applicable to every project regardless of language.

## Pages

- [mise.md](./mise.md) — pinned tool versions (node, python, uv, etc.)
- [lefthook.md](./lefthook.md) — git hooks with autofix + restage
- [docs-gen.md](./docs-gen.md) — generate README/CLAUDE/AGENTS from partials
- [line-limit.md](./line-limit.md) — per-file line cap enforced in lefthook + CI
- [ci-github.md](./ci-github.md) — single-project GitHub Actions CI: lint + typecheck + test
- [ci-gitlab.md](./ci-gitlab.md) — single-project GitLab CI pipeline skeleton
- [releases-github.md](./releases-github.md) — release-please for GitHub
- [releases-gitlab.md](./releases-gitlab.md) — semantic-release for GitLab
- [gitlab-pipeline-dedup.md](./gitlab-pipeline-dedup.md) — workflow:rules dedup + build-on-MR job rules (GitLab)
- [security.md](./security.md) — semgrep (SAST) + trivy (fs + image)
- [claude-review.md](./claude-review.md) — Claude Code reviews every PR (GitHub only)
- [conventional-commits.md](./conventional-commits.md) — commit message format
- [git-ai-instructions.md](./git-ai-instructions.md) — repo-local commit/PR guidance for git-ai, framed by user POV
- [contributing.md](./contributing.md) — CONTRIBUTING.md: branching, commits, MR/PR + review flow
- [codeowners.md](./codeowners.md) — required reviewers auto-assigned per path
- [dependabot.md](./dependabot.md) — automated dep updates (GitHub only — GH Actions + npm + pip)
- [renovate.md](./renovate.md) — automated dep updates (GitLab + GitHub, broader ecosystem coverage)
