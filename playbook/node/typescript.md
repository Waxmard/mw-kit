# TypeScript

## What

Strict TypeScript, no compile output (Vite/Expo/Metro handle bundling). `tsc --noEmit` is purely a type checker.

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

## Scripts

```json
{
  "scripts": {
    "typecheck": "tsc --noEmit"
  }
}
```

## CI

```yaml
- run: npx tsc --noEmit
```

## Gotchas

- `skipLibCheck: true` — third-party `.d.ts` files often have errors. Skip or you'll never get green.
- `isolatedModules: true` — required for Vite/Metro/swc; flags incompatible syntax early.
- Don't ship `.d.ts` from app code unless publishing a library.
