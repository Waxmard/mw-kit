---
tool: design-system-lint
scope: node
tier: optional
summary: "Block raw hex colors, arbitrary Tailwind values, and off-system styles outside tokens"
targets: ["biome.json", "eslint.config.js"]
detect: ["**/*.{tsx,jsx,svelte,vue}"]
---

# Design System Lint

## What

Blocking lint rules for both Biome 2.x (GritQL plugins) and ESLint (`no-restricted-syntax`) that reject raw hex colors and arbitrary Tailwind bracket values outside your design-system tokens directory.

## Why

- Agents frequently reach for `#hex` literals or `bg-[#123456]` / `p-[13px]` escape hatches instead of using semantic tokens.
- Scoping the exclusion strictly to `src/design-system/tokens/**` keeps token definitions clean while blocking off-system styling everywhere else.

## Config

### Biome 2.x (GritQL plugins)

Add top-level `"plugins"` in `biome.json`:

```json
{
  "plugins": [
    {
      "path": "./biome-plugins/no-raw-hex.grit",
      "includes": ["src/**", "!src/design-system/tokens/**"]
    },
    {
      "path": "./biome-plugins/no-raw-hex-css.grit",
      "includes": ["src/**", "!src/design-system/tokens/**"]
    },
    {
      "path": "./biome-plugins/no-arbitrary-tailwind.grit",
      "includes": ["src/**", "!src/design-system/tokens/**"]
    }
  ]
}
```

`biome-plugins/no-raw-hex.grit`:

```grit
`$lit` where {
  $lit <: r"^['\"]#[0-9a-fA-F]{3,8}['\"]$",
  register_diagnostic(
    span = $lit,
    message = "Use a color token from src/design-system/tokens instead of a raw hex literal.",
    severity = "error"
  )
}
```

`biome-plugins/no-raw-hex-css.grit`:

```grit
language css;

`$prop: $val` where {
  $val <: r"^#[0-9a-fA-F]{3,8}$",
  register_diagnostic(
    span = $val,
    message = "Use a CSS color token instead of a raw hex literal.",
    severity = "error"
  )
}
```

`biome-plugins/no-arbitrary-tailwind.grit`:

```grit
`className="$cls"` where {
  $cls <: r".*\b(?:bg|text|border|p|px|py|pt|pb|pl|pr|m|mx|my|mt|mb|ml|mr|w|h|gap|rounded)-\[[^\]]+\].*",
  register_diagnostic(
    span = $cls,
    message = "Use design-system theme utilities instead of arbitrary Tailwind bracket values.",
    severity = "error"
  )
}
```

### ESLint (Svelte / Vue / ESLint-based repos)

```js
export default [
  {
    ignores: ['src/design-system/tokens/**'],
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          selector: 'Literal[value=/^#[0-9a-fA-F]{3,8}$/]',
          message: 'Use a color token from src/design-system/tokens instead of a raw hex literal.',
        },
        {
          selector:
            'JSXAttribute[name.name=/^(class|className)$/] Literal[value=/\\b(?:bg|text|border|p|px|py|pt|pb|pl|pr|m|mx|my|mt|mb|ml|mr|w|h|gap|rounded)-\\[[^\\]]+\\]/]',
          message: 'Use design-system theme utilities instead of arbitrary Tailwind bracket values.',
        },
      ],
    },
  },
];
```

## Gotchas

- Always verify every adapted GritQL or ESLint rule fires on a real violating file before shipping it; a syntax mismatch in GritQL can fail silently with zero diagnostics.
- For existing repos with legacy violations, ratchet existing files via file-level `overrides` so no new off-system styling lands while legacy screens are migrated.
