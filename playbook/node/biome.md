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

## Config

Pin `@biomejs/biome` exact in devDependencies (see [package-json](package-json.md)).

```json
{
  "$schema": "./node_modules/@biomejs/biome/configuration_schema.json",
  "files": {
    "includes": ["src/**/*.{ts,tsx,js,jsx,json}"]
  },
  "formatter": {
    "indentStyle": "space"
  },
  "javascript": {
    "formatter": {
      "quoteStyle": "single",
      "trailingCommas": "es5"
    }
  },
  "linter": {
    "rules": {
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

Scripts: see [package-json](package-json.md).

Hook: see [lefthook](../universal/lefthook.md).

## CI

```yaml
- run: npm ci
- run: npm run check
```

## Gotchas

- Keep `files.includes` and the CLI paths (`src/`) aligned.
