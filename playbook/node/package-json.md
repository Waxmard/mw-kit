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

Standard names across all projects:

```json
{
  "scripts": {
    "lint": "biome lint src/",
    "lint:fix": "biome lint --write src/",
    "format": "biome format --write src/",
    "format:check": "biome format src/",
    "check": "biome check src/",
    "check:fix": "biome check --write src/",
    "check:staged": "biome check --write --no-errors-on-unmatched",
    "typecheck": "tsc --noEmit"
  }
}
```

- `lint` / `lint:fix` — lint only
- `format` / `format:check` — format only
- `check` / `check:fix` — combined (prefer this)
- `check:staged` — lefthook-friendly variant
- `typecheck` — TypeScript only (no biome overlap)

## Dependencies

- Resolve current stable versions from the registry before scaffolding, skipping any
  published within the `min-release-age` window (below) — `npm install` rejects them
  with `ETARGET`. Template and playbook versions may lag; check the lockfile as well
  as manifest ranges.
- Verify peer dependency ranges before major upgrades. Keep the latest compatible
  release when the framework's tools exclude the newest major, and document the
  constraint in the consumer repo. Never bypass peers to claim everything is latest.
- Match `@types/node` to the chosen Node LTS major rather than blindly following
  its `latest` tag.
- Pin biome exact (`"@biomejs/biome": "X.Y.Z"`, resolved to latest compatible stable)
  — minor releases change rules.
- Other devDeps caret OK.
- App deps: caret for libs you trust to follow semver, exact for ones that don't (Expo, React Native).

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
  "devDependencies": { "lefthook": "^1.0.0" },
  "scripts": { "prepare": "lefthook install" }
}
```

`prepare` runs on `npm install` → hooks installed automatically.

## Overrides

For peer-dep conflicts (postcss in Expo etc.):

```json
{
  "overrides": {
    "postcss": "^8.5.10"
  }
}
```

Prefer `overrides` over `--legacy-peer-deps`. Legacy flag hides real conflicts.
