---
tool: layout
scope: monorepo
tier: optional
summary: "Polyglot monorepo directory shape + tooling boundaries"
targets: []
---

# Monorepo Layout

## Shape

```
my-repo/
├── package.json          # root: lefthook only (not a JS project)
├── lefthook.yml
├── mise.toml
├── Makefile              # orchestrator: delegates to subprojects
├── fastapi/              # python project (own pyproject, own Makefile)
├── frontend/             # node project (own package.json)
├── docs/src/             # doc templates
├── scripts/              # repo-wide tooling (build_docs.py)
└── .github/workflows/    # path-filtered per subproject
```

## Principles

- **Each subproject self-contained**: own deps, own Makefile, own lockfile.
- **Root is orchestration**: Makefile delegates with `make backend-X` → `make -C fastapi X`.
- **Hooks live at root**: one lefthook.yml covers all subprojects via `root:` per command.
- **CI workflows path-filtered**: backend.yml triggers on `fastapi/**`, frontend.yml on `frontend/**`.
- **No top-level package manager**: don't use npm workspaces / pnpm / yarn workspaces unless you have shared JS code. Adds resolution complexity for no gain when languages differ.

## Why this over Nx / Turborepo / pnpm workspaces

- Those tools shine for **same-language** monorepos (multiple JS packages).
- For polyglot (Python + RN + docs + Go), Make + path-filtered workflows are simpler and language-neutral.
- Cache invalidation is handled by GH Actions cache (uv.lock, package-lock.json) per workflow.

## Root package.json

```json
{
  "name": "my-repo-dev",
  "private": true,
  "devDependencies": { "lefthook": "^1.0.0" },
  "scripts": { "prepare": "lefthook install" }
}
```

`prepare` installs hooks on `npm install`.
