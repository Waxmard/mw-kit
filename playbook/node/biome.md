---
tool: biome
scope: node
tier: baseline
summary: "JS/TS lint + format + import sort (replaces eslint + prettier)"
targets: ["biome.json", "package.json"]
detect: ["package.json", "**/*.{ts,tsx,js,jsx}"]
---

# biome

## What

[biome](https://biomejs.dev/) — single Rust-based tool for JS/TS lint + format + import sort. Replaces eslint + prettier + organize-imports.

## Why

- One binary, one config (`biome.json`), one cache.
- 10-100x faster than eslint+prettier.
- Sensible default ruleset (`recommended: true`) covers ~80% of eslint:recommended + react/hooks.
- Format compatible with prettier defaults (mostly).

## Why not eslint + prettier

- Two configs, two caches, two install trees, plugin chaos.
- Slow. Flat config migration is painful.
- Biome covers the same ground in one tool now (2024+).

## Config

```json
{
  "$schema": "https://biomejs.dev/schemas/2.4.14/schema.json",
  "files": {
    "includes": ["src/**/*.{ts,tsx,js,jsx,json}"]
  },
  "formatter": {
    "enabled": true,
    "indentStyle": "space",
    "indentWidth": 2,
    "lineEnding": "lf",
    "lineWidth": 80
  },
  "javascript": {
    "formatter": {
      "semicolons": "always",
      "quoteStyle": "single",
      "jsxQuoteStyle": "double",
      "trailingCommas": "es5",
      "arrowParentheses": "always"
    }
  },
  "linter": {
    "enabled": true,
    "rules": {
      "recommended": true,
      "correctness": {
        "useExhaustiveDependencies": "error",
        "noUnusedVariables": "error"
      },
      "suspicious": {
        "noExplicitAny": "error",
        "noImplicitAnyLet": "error",
        "useIterableCallbackReturn": "error"
      },
      "style": {
        "useImportType": "error",
        "noNonNullAssertion": "error"
      }
    }
  }
}
```

### Strict bumps over `recommended`

- `useExhaustiveDependencies: error` — react-hooks/exhaustive-deps equivalent.
- `noUnusedVariables: error` — TS's `noUnusedLocals` only catches some cases.
- `noExplicitAny: error` — push to use `unknown` or proper types.
- `useImportType: error` — split type imports for cleaner bundles + faster builds.
- `noNonNullAssertion: error` — ban `!`. Forces real null handling.

### Style choices

- Single quotes JS, double quotes JSX.
- Semicolons always (avoids ASI footguns).
- `trailingCommas: es5` — diff-friendly without breaking older runtimes.

## package.json scripts

```json
{
  "scripts": {
    "lint": "biome lint src/",
    "lint:fix": "biome lint --write src/",
    "format": "biome format --write src/",
    "format:check": "biome format src/",
    "check": "biome check src/",
    "check:fix": "biome check --write src/",
    "check:staged": "biome check --write --no-errors-on-unmatched"
  }
}
```

`check` = lint + format + import sort combined. Prefer over individual commands.

`check:staged` exists for lefthook (allows files outside `includes` without erroring).

## Lefthook

```yaml
biome:
  root: frontend/
  glob: "src/**/*.{ts,tsx,js,jsx,json}"
  run: npm run check:staged -- {staged_files}
  stage_fixed: true
```

## CI

```yaml
- run: npm ci
- run: npm run lint
- run: npm run format:check
```

## Gotchas

- Pin biome version in devDependencies; the binary's behavior changes between minors.
- `includes` glob in biome.json scopes everything; keep narrow (`src/**`) to skip node_modules + build artifacts implicitly.
- Some eslint rules don't have biome equivalents yet (a-11y subset, jest-specific). If you hit one, add an issue link in the relevant code comment, don't reach for eslint.
