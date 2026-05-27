# dependabot

## What

GitHub's built-in dep update bot. Opens PRs to bump outdated deps in `package.json`, `pyproject.toml`, GH Actions workflows, Docker base images.

## Why

- Free, no setup beyond `.github/dependabot.yml`.
- Keeps `actions/checkout@v6` → `v7` automatically. Security patches land without manual tracking.
- Paired with release-please: dep bumps show as `chore(deps):` → hidden in changelog, no noise.

## Config

`.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    commit-message:
      prefix: "chore(ci)"

  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
    commit-message:
      prefix: "chore(deps)"

  - package-ecosystem: "npm"
    directory: "/frontend"
    schedule:
      interval: "weekly"
    commit-message:
      prefix: "chore(deps)"

  - package-ecosystem: "pip"
    directory: "/fastapi"
    schedule:
      interval: "weekly"
    commit-message:
      prefix: "chore(deps)"
```

## Gotchas

- Add one block per package-ecosystem per directory. Monorepos need multiple `npm` or `pip` blocks.
- `github-actions` block should always be included — workflow file pins (`@v4`, `@v6`) rot silently.
- Group related bumps with `groups` key (dependabot v2) to collapse minor dep PRs:

```yaml
  - package-ecosystem: "npm"
    directory: "/frontend"
    schedule:
      interval: "weekly"
    groups:
      expo:
        patterns: ["expo*", "react-native*"]
```

- Auto-merge dependabot PRs with a GH Actions workflow if CI is trusted to catch regressions. Good pattern for dev-only deps (biome, ruff, lefthook).
