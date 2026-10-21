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

## CI

```yaml
- run: npm run typecheck
```

## Gotchas

- `skipLibCheck: true` — third-party `.d.ts` files often have errors. Skip or you'll never get green.
- `isolatedModules: true` — required for Vite/Metro/swc; flags incompatible syntax early.
