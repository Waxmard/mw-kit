---
tool: tach
scope: python
tier: optional
summary: "Module-import boundary enforcement"
targets: ["tach.toml"]
detect: ["**/*.py"]
---

# tach

## What

[tach](https://docs.gauge.sh/) — enforce module-import boundaries in Python projects via `tach.toml`. Fails build if `app.crud` imports `app.api` (the wrong direction).

## Why

- Python's import system has no built-in layering. Tach adds it.
- Catches architecture drift in PRs, not after the fact.
- Forces explicit dependency edges — easy to audit.
- Fast (Rust).

## Why not import-linter / pylint custom checkers

import-linter works but config syntax is verbose. Pylint custom checkers are heavy and slow. Tach is purpose-built and fast enough for pre-commit.

## Config

`fastapi/tach.toml`:

```toml
exclude = ["tests", "scripts", ".venv", "**/__pycache__"]
source_roots = ["."]
forbid_circular_dependencies = true
exact = true

[[modules]]
path = "app.main"
depends_on = ["app.api", "app.db", "app.settings"]

[[modules]]
path = "app.api"
depends_on = ["app.core", "app.crud", "app.db", "app.schemas",
              "app.services", "app.settings", "app.utils"]

[[modules]]
path = "app.services"
depends_on = ["app.core", "app.crud", "app.db", "app.schemas",
              "app.settings", "app.utils"]

[[modules]]
path = "app.core"
depends_on = ["app.schemas"]

[[modules]]
path = "app.crud"
depends_on = ["app.core", "app.db", "app.schemas"]

[[modules]]
path = "app.utils"
depends_on = ["app.db"]

[[modules]]
path = "app.db"
depends_on = ["app.settings"]

[[modules]]
path = "app.schemas"
depends_on = []

[[modules]]
path = "app.settings"
depends_on = []
```

### Layering pattern

```
main → api → services → crud → db
        ↓
       core (pure leaf, reachable from api/services/crud)

schemas, settings, utils — cross-cutting (depended on, depend on nothing)
```

- `api` may call `crud` directly (endpoint handlers use `crud_*` helpers). Intentional, not a violation.
- `core` is a pure leaf: constants, security primitives, algorithms.
- `schemas` are pure data shapes; they import nothing.

## Commands

```bash
uv run tach check              # verify graph (CI)
uv run tach show               # print module dependency graph
uv run tach mod                # interactive boundary setup
```

## Lefthook

```yaml
tach:
  root: fastapi/
  glob:
    - "app/**/*.py"
    - "tach.toml"
  run: uv run tach check
```

No `{staged_files}` — tach scans the whole project.

## CI

```yaml
boundaries:
  steps:
    - run: uv sync --extra dev --group dev
    - run: uv run tach check
```

## Gotchas

- `exact = true` requires every module listed; partial graphs allowed when false. Use exact for confidence.
- `forbid_circular_dependencies = true` is a separate flag from layering — turn it on.
- Cross-cutting modules (`schemas`, `settings`) have `depends_on = []` — they're terminal sinks.
- When you genuinely need a new cross-layer call, update tach.toml in the same PR. Don't bypass.
