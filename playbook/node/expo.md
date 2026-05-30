---
tool: expo
scope: node
tier: optional
summary: "Expo SDK conventions for React Native apps"
targets: ["package.json", "app.json", "app.config.ts"]
detect: ["app.json", "app.config.ts", "app.config.js"]
---

# Expo / React Native

## What

Use Expo SDK (managed + dev client) for new React Native apps. Avoid bare RN unless you have a native-module need Expo can't solve.

## Why Expo

- Dev client = best of both worlds: custom native modules + Expo's tooling.
- EAS Build/Submit removes Xcode/Android Studio toolchain pain.
- Expo Router for file-based routing.
- Updates OTA via EAS Update.

## SDK pinning

- Pin Expo SDK exact (`"expo": "^54.0.32"` — caret OK within a major).
- React Native version is dictated by Expo SDK — don't pin independently.
- React + react-dom versions also dictated; let Expo's `expo install` resolve them.

```bash
npx expo install <pkg>     # respects SDK compat constraints
```

Avoid raw `npm install` for Expo-aware libs — version drift breaks dev client builds.

## Dependency overrides

```json
{
  "overrides": {
    "postcss": "^8.5.10"
  }
}
```

Common when web target pulls in stale postcss via transitive deps.

## Scripts

```json
{
  "scripts": {
    "start": "expo start",
    "ios": "expo run:ios",
    "android": "expo run:android",
    "web": "expo start --web"
  }
}
```

`expo run:ios` builds the dev client and launches in simulator. `expo start` runs Metro only — needs an existing build.

## TypeScript

Expo ships its own tsconfig base; extend:

```json
{
  "extends": "expo/tsconfig.base",
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true
  }
}
```

## Gotchas

- Don't commit `ios/` or `android/` if you're using managed + dev client; let prebuild regenerate.
- `expo-dev-client` must match Expo SDK major. Mismatch → silent crashes on launch.
- For web, Metro web is fine for small apps; Vite-with-React-Native-Web is faster for larger ones but more setup.
- Biome runs on `src/**/*.{ts,tsx}` — keep app code under `src/` so it's covered.
