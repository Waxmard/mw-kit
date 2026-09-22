---
tool: svelte
scope: node
tier: baseline
summary: "Svelte lint, format, and compiler-aware type checking"
targets: ["eslint.config.js", "prettier.config.js", "tsconfig.json", "package.json"]
detect: ["**/*.svelte", "svelte.config.js", "svelte.config.ts"]
---

# Svelte tooling

## What

Use ESLint with `eslint-plugin-svelte` for template rules, Prettier with its Svelte
plugin for formatting, and `svelte-check` for compiler and TypeScript diagnostics.
For SvelteKit, let `svelte-kit sync` generate the base tsconfig.

## Why

Svelte templates and compiler diagnostics need Svelte-aware tooling. This is the
exception to the [Biome baseline](biome.md) for a single-project Svelte app.
In a mixed monorepo, keep Biome for other components and scope each tool to its
own component.

## Config

Install the latest compatible versions of `eslint`, `@eslint/js`,
`typescript-eslint`, `eslint-plugin-svelte`, `eslint-config-prettier`,
`prettier`, `prettier-plugin-svelte`, `svelte-check`, and `typescript`.
Add `prettier-plugin-tailwindcss` when the app uses Tailwind CSS.

`eslint.config.js`:

```js
import js from '@eslint/js';
import prettier from 'eslint-config-prettier';
import svelte from 'eslint-plugin-svelte';
import { defineConfig } from 'eslint/config';
import ts from 'typescript-eslint';

export default defineConfig(
  js.configs.recommended,
  ts.configs.recommended,
  svelte.configs.recommended,
  prettier,
  svelte.configs.prettier,
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

`prettier.config.js`:

```js
export default {
  singleQuote: true,
  printWidth: 80,
  plugins: ['prettier-plugin-svelte'],
  overrides: [{ files: '*.svelte', options: { parser: 'svelte' } }],
};
```

For Tailwind CSS, append `prettier-plugin-tailwindcss` last in `plugins` and set
`tailwindStylesheet` to the app's stylesheet. The plugin order matters.

`tsconfig.json` for SvelteKit:

```json
{
  "extends": "./.svelte-kit/tsconfig.json",
  "compilerOptions": {
    "strict": true,
    "moduleResolution": "bundler",
    "skipLibCheck": true
  }
}
```

`package.json` scripts:

```json
{
  "scripts": {
    "lint": "eslint . --max-warnings 0",
    "lint:fix": "eslint . --fix",
    "format": "prettier --write .",
    "format:check": "prettier --check .",
    "check": "npm run lint && npm run format:check",
    "typecheck": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json --fail-on-warnings"
  }
}
```

## Gotchas

- Run `svelte-kit sync` before diagnostics so generated route types exist.
- Outside SvelteKit, remove `svelte-kit sync` from `typecheck` and use the app's
  own tsconfig.
- Ignore generated output in ESLint and Prettier. Include `.svelte-kit`, build
  output, and generated data in the repo's ignore rules.
- Use the repo's existing globals and framework rules. Do not replace a working
  ESLint config wholesale when applying this baseline.
