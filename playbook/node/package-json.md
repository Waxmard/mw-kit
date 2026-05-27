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

- Pin biome exact (`"@biomejs/biome": "2.4.14"`) — minor releases change rules.
- Other devDeps caret OK.
- App deps: caret for libs you trust to follow semver, exact for ones that don't (Expo, React Native).

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
