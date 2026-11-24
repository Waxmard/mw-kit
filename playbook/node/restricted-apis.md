---
tool: restricted-apis
scope: node
tier: optional
summary: "Ban nuance-heavy APIs (React useEffect, imperative timers) outside dedicated modules"
targets: ["biome.json", "eslint.config.js"]
detect: ["biome.json", "eslint.config.*", "**/*.{ts,tsx,jsx}"]
---

# Restricted APIs

## What

Blocking lint rules for Biome and ESLint that ban nuance-heavy APIs (`useEffect` in React components, imperative browser timers like `setTimeout`, `requestAnimationFrame`, and `requestIdleCallback`) outside dedicated hook or helper directories.

## Why

- Direct `useEffect` calls in components are a frequent source of stale closures, infinite re-render loops, and uncleaned subscriptions.
- Ad-hoc `setTimeout` / `requestAnimationFrame` calls leak timers on unmount and make tests flaky.
- Restricting them to `src/hooks/**` or a shared timer helper forces lifecycle logic into tested, reusable primitives.

## Config

### Biome 2.x

In `biome.json`:

```json
{
  "plugins": [
    {
      "path": "./biome-plugins/no-timers.grit",
      "includes": ["src/**", "!src/hooks/**"]
    }
  ],
  "linter": {
    "rules": {
      "style": {
        "noRestrictedImports": {
          "level": "error",
          "options": {
            "paths": {
              "react": {
                "importNames": ["useEffect"],
                "message": "Do not call useEffect in product code; move lifecycle effects into src/hooks/."
              }
            }
          }
        }
      }
    }
  },
  "overrides": [
    {
      "includes": ["src/hooks/**"],
      "linter": {
        "rules": {
          "style": {
            "noRestrictedImports": "off"
          }
        }
      }
    }
  ]
}
```

`biome-plugins/no-timers.grit`:

```grit
`$fn($args)` where {
  $fn <: or { `setTimeout`, `requestAnimationFrame`, `requestIdleCallback` },
  register_diagnostic(
    span = $fn,
    message = "Do not call browser timers directly; use the shared timer helper.",
    severity = "error"
  )
}
```

### ESLint

```js
export default [
  {
    rules: {
      'no-restricted-imports': [
        'error',
        {
          paths: [
            {
              name: 'react',
              importNames: ['useEffect'],
              message: 'Do not call useEffect in product code; move lifecycle effects into src/hooks/.',
            },
          ],
        },
      ],
      'no-restricted-globals': [
        'error',
        {
          name: 'setTimeout',
          message: 'Do not call setTimeout directly; use the shared timer helper.',
        },
        {
          name: 'requestAnimationFrame',
          message: 'Do not call requestAnimationFrame directly; use the shared timer helper.',
        },
        {
          name: 'requestIdleCallback',
          message: 'Do not call requestIdleCallback directly; use the shared timer helper.',
        },
      ],
    },
  },
  {
    files: ['src/hooks/**'],
    rules: {
      'no-restricted-imports': 'off',
      'no-restricted-globals': 'off',
    },
  },
];
```

## Gotchas

- `noRestrictedImports` only blocks named imports (`import { useEffect } from 'react'`), not `React.useEffect(...)`; add a GritQL or `no-restricted-syntax` rule if your codebase uses namespace React imports.
- Keep `src/hooks/**` narrow and code-reviewed so it does not become a bypass folder for arbitrary component logic.
- `no-restricted-globals` only reports bare calls; `window.setTimeout(...)` passes. Add `no-restricted-properties` with `{ object: 'window', property: 'setTimeout' }` for each timer.
- Svelte repos: drop the `react` import rule and exempt the single timer module (`ignores: ['src/lib/timers.ts']`) instead of `src/hooks/**`.
