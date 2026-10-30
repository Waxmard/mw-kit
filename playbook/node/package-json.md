---
tool: package-json
scope: node
tier: baseline
summary: "Standard scripts, dependency pinning, and release-age policy"
targets: ["package.json", ".npmrc"]
detect: ["package.json"]
---

# package.json Conventions

## Scripts

Biome repos use these names:

```json
{
  "scripts": {
    "check": "biome check src/",
    "check:fix": "biome check --write src/",
    "check:staged": "biome check --write --no-errors-on-unmatched",
    "typecheck": "tsc --noEmit",
    "ci": "npm run check && npm run typecheck && npm test"
  }
}
```

Prefer `check` / `check:fix` (lint + format + import sort); `check:staged` is for lefthook.

Repos on the ESLint + Prettier accepted alternative keep their own script names; don't add wrapper aliases.

## Dependencies

- Verify peer dependency ranges before major upgrades. Keep the latest compatible
  release when the framework's tools exclude the newest major, and document the
  constraint in the consumer repo. Never bypass peers to claim everything is latest.
- Match `@types/node` to the chosen Node LTS major rather than blindly following
  its `latest` tag.
- Pin biome exact (`"@biomejs/biome": "X.Y.Z"`, resolved to latest compatible stable)
  — minor releases change rules.
- Other devDeps caret OK.
- App deps: caret. Expo-managed packages: let `npx expo install` choose (see [Expo](expo.md)).

## Supply-chain delay

`.npmrc`:

```ini
engine-strict=true
min-release-age=7
```

`min-release-age` excludes package versions published within the last seven days
from resolution. Security fixes blocked by this window fail loudly; temporarily add
the package to `min-release-age-exclude[]` when a verified urgent fix cannot wait.
Requires npm 11.10 or newer.

## Root package.json (monorepo dev tooling)

If the repo isn't a JS project but needs lefthook installed:

```json
{
  "name": "myrepo-dev",
  "private": true,
  "devDependencies": { "lefthook": "^2" },
  "scripts": { "prepare": "lefthook install" }
}
```

`prepare` runs on `npm install` → hooks installed automatically.

## Expo

See [Expo iOS](expo.md) for package and development commands.

## Overrides

For peer-dep conflicts:

```json
{
  "overrides": {
    "<pkg>": "^N"
  }
}
```

Prefer `overrides` over `--legacy-peer-deps`. Legacy flag hides real conflicts.
