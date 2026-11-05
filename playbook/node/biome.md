---
tool: biome
scope: node
tier: baseline
summary: "JS/TS lint + format + import sort (replaces eslint + prettier)"
targets: ["biome.json", "package.json"]
detect: ["biome.json", "biome.jsonc", "**/*.{ts,tsx,js,jsx,mjs,cjs,vue}"]
---

# biome

## What

[biome](https://biomejs.dev/) — single Rust-based tool for JS/TS lint + format + import sort. Replaces eslint + prettier + organize-imports.

## Why

- One binary, one config (`biome.json`), one cache.

## Accepted alternative

ESLint + Prettier: a repo that already lints with `eslint.config.*` and formats with Prettier (`.prettierrc*`) keeps them; don't migrate it to biome. New repos usually start on biome. SvelteKit projects requiring full Svelte-aware diagnostics may use ESLint + Prettier from the start.

## Config

Pin `@biomejs/biome` exact in devDependencies (see [package-json](package-json.md)).

```json
{
  "$schema": "https://biomejs.dev/schemas/X.Y.Z/schema.json",
  "vcs": {
    "enabled": true,
    "clientKind": "git",
    "useIgnoreFile": true
  },
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

### SvelteKit: ESLint and Prettier

For SvelteKit projects using the ESLint + Prettier alternative, use the following configuration instead of the generic biome config. These settings do not apply to ordinary Node projects.

Use these dev dependencies: `eslint`, `@eslint/js`, `typescript-eslint`, `eslint-plugin-svelte`, `eslint-config-prettier`, `globals`, `prettier`, `prettier-plugin-svelte`, `svelte-check`, and `typescript`. Reuse the app's existing SvelteKit, Svelte, and Lefthook dependencies.

Set `eslint.config.js` to load `.gitignore` and apply the recommended JavaScript, TypeScript, and Svelte rules.

```js
import prettier from 'eslint-config-prettier';
import path from 'node:path';
import js from '@eslint/js';
import svelte from 'eslint-plugin-svelte';
import { defineConfig, includeIgnoreFile } from 'eslint/config';
import globals from 'globals';
import ts from 'typescript-eslint';

const gitignorePath = path.resolve(import.meta.dirname, '.gitignore');

export default defineConfig(
  includeIgnoreFile(gitignorePath),
  js.configs.recommended,
  ts.configs.recommended,
  svelte.configs.recommended,
  prettier,
  svelte.configs.prettier,
  {
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    rules: {
      'no-undef': 'off',
      '@typescript-eslint/consistent-type-imports': 'error',
      '@typescript-eslint/no-non-null-assertion': 'error',
    },
  },
  {
    files: ['**/*.svelte', '**/*.svelte.ts', '**/*.svelte.js'],
    languageOptions: {
      parserOptions: {
        projectService: true,
        extraFileExtensions: ['.svelte'],
        parser: ts.parser,
      },
    },
  }
);
```

Set `prettier.config.js` to format Svelte files with the Svelte parser.

```js
export default {
  useTabs: false,
  tabWidth: 2,
  singleQuote: true,
  trailingComma: 'es5',
  printWidth: 80,
  plugins: ['prettier-plugin-svelte'],
  overrides: [{ files: '*.svelte', options: { parser: 'svelte' } }],
};
```

Tailwind projects also need `prettier-plugin-tailwindcss`. Append it last in `plugins` and set `tailwindStylesheet` to the app's stylesheet.

Use the [SvelteKit scripts](package-json.md#sveltekit) and [SvelteKit TypeScript config](typescript.md#sveltekit).

## CI

```yaml
- run: npm ci
- run: npm run check
```

## Gotchas

- Keep `files.includes` and the CLI paths (`src/`) aligned.
- Custom AST rules use GritQL plugins (`"plugins": ["./biome-plugins/<rule>.grit"]` at top level or inside `"overrides"`) to ban project-specific APIs without ESLint.
