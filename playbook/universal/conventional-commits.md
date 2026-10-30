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

PRs and MRs are squash-merged, so the squashed commit title must itself be conventional; it's the line release tooling reads.

## Why

- Release tooling (release-please, semantic-release) parses these to compute version bumps and changelog sections.

## Examples

```
feat(auth): add Google OAuth flow
fix(api): handle null user_id in /me endpoint
refactor: tighten create_access_token subject type to UUID | str
ci: remove --legacy-peer-deps from frontend CI installs
chore(deps): bump biome
```

## Enforcement

Optional: commitlint via a lefthook `commit-msg` hook. Code review is usually enough without it.

If desired:

```yaml
# lefthook.yml
commit-msg:
  commands:
    commitlint:
      run: npx --no -- commitlint --edit {1}
```

`commitlint.config.js` — disable the body/footer line cap (the most-hit rule;
bodies carry URLs, pasted output, and release notes that don't wrap cleanly).
Keep the load-bearing subject/type rules:

```js
export default {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "body-max-line-length": [0],
    "footer-max-line-length": [0],
  },
};
```

Needs `@commitlint/cli` + `@commitlint/config-conventional` as devDeps.
