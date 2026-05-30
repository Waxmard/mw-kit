---
tool: dependabot
scope: universal
tier: baseline
summary: "GitHub-native dependency update PRs"
targets: [".github/dependabot.yml"]
platform: github
---

# dependabot

## What

GitHub's built-in dep update bot. PRs to bump `package.json`, `pyproject.toml`, GH Actions, Docker base images. Free, just needs `.github/dependabot.yml`. GitLab → use [[renovate]].

## Config

### Baseline — every repo starts here

`.github/dependabot.yml`. Groups minor/patch into one weekly PR per ecosystem; majors stay individual and trickle under the limit.

```yaml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    groups:
      actions:
        patterns: ["*"]
    commit-message:
      prefix: "chore(ci)"

  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 3
    groups:
      minor-and-patch:
        applies-to: version-updates
        update-types: ["minor", "patch"]
    commit-message:
      prefix: "chore(deps)"
```

One block per ecosystem **per directory** — monorepos repeat the `npm`/`pip` block per path (`/`, `/frontend`, `/fastapi`). Each repeat carries the same `groups` + limit.

### Patterns (per-repo opt-in)

**Group a coupled family** — collapse lockstep deps into one PR:

```yaml
    groups:
      expo:
        patterns: ["expo*", "react-native*"]
```

**Auto-merge low-risk dev bumps** — needs a GH Actions workflow + trusted CI. Dev-only deps (biome, ruff, lefthook). Never prod, never major.

## Gotchas

- **`update-types` in `groups` is how you batch by risk.** This is the triage lever — minor/patch → one PR, majors excluded → individual. No `prPriority` equivalent, so majors can't be ordered, only capped by `open-pull-requests-limit`.
- **`open-pull-requests-limit` is per-ecosystem-block, not per-repo.** Baseline `3`. Since minor/patch collapse to 1 grouped PR, **concurrent majors = limit − 1** → 1 group + at most 2 majors per block. Three blocks = that × 3, so total open can still reach ~9 across ecosystems. Adjust the number to change the major ceiling.
- **`github-actions` block is mandatory.** Workflow pins (`@v4`, `@v6`) rot silently otherwise.
- **Security updates ignore the limit** and aren't grouped by `version-updates` rules — they always land.
- **`chore(deps):` prefix** → release-please / semantic-release hide bumps from changelogs. Aligns with [[conventional-commits]].
