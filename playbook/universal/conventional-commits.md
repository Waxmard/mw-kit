---
tool: conventional-commits
scope: universal
tier: baseline
summary: "Commit message format feeding release tooling"
targets: []
---

# Conventional Commits

## What

Commit message format: `<type>(<scope>): <subject>`.

Types: `feat`, `fix`, `perf`, `refactor`, `docs`, `style`, `test`, `chore`, `build`, `ci`.

`feat!` or `BREAKING CHANGE:` footer → major bump.

## Why

- Release tooling (release-please, semantic-release) parses these to compute version bumps and changelog sections.
- Browsing `git log` becomes a structured changelog by default.
- Forces 1 commit = 1 logical change.

Stated as a contributor expectation in [[contributing]].

## Examples

```
feat(auth): add Google OAuth flow
fix(api): handle null user_id in /me endpoint
refactor: tighten create_access_token subject type to UUID | str
ci: remove --legacy-peer-deps from frontend CI installs
chore(deps): bump biome to 2.4.14
```

## Enforcement

Optional — commitlint via lefthook `commit-msg` hook. In practice, code review + release-please's behavior (no version bump on chore-only) creates enough pressure without a hook.

If desired:

```yaml
# lefthook.yml
commit-msg:
  commands:
    commitlint:
      run: npx --no -- commitlint --edit {1}
```
