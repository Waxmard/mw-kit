---
tool: typescript
scope: node
tier: baseline
summary: "Strict tsconfig, noEmit type-checking"
targets: ["tsconfig.json"]
detect: ["tsconfig.json", "**/*.{ts,tsx}"]
---

# TypeScript

## What

Strict TypeScript, no compile output (Vite/Expo/Metro handle bundling).

## tsconfig.json baseline

```json
{
  "compilerOptions": {
    "strict": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "noEmit": true
  },
  "include": ["src/**/*"]
}
```

For Expo, extend their base instead:

```json
{
  "extends": "expo/tsconfig.base",
  "compilerOptions": {
    "strict": true
  }
}
```

### SvelteKit

For SvelteKit, extend its framework-provided base instead of the standalone config. This strict example includes the app source and Vite config.

```json
{
  "extends": "$app/tsconfig",
  "include": ["src", "vite.config.ts"],
  "exclude": ["node_modules"],
  "compilerOptions": {
    "strict": true
  }
}
```

Keep the existing framework-provided base if the installed SvelteKit version uses a different one. `tsc --noEmit` alone does not check Svelte templates. Use `svelte-check` with warnings treated as failures, as shown in the [SvelteKit scripts](package-json.md#sveltekit).

## CI

```yaml
- run: npm run typecheck
```

## Gotchas

- `skipLibCheck: true` — third-party `.d.ts` files often have errors. Skip or you'll never get green.
- `isolatedModules: true` — required for Vite/Metro/swc; flags incompatible syntax early.
