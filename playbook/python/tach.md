---
tool: tach
scope: python
tier: optional
summary: "Enforce Python module dependency boundaries and forbid cycles"
targets: ["tach.toml"]
detect: ["pyproject.toml", "**/*.py"]
---

# tach

## What

[tach](https://docs.astral.sh/ruff/) — fast Rust CLI that enforces module dependency boundaries and forbids circular imports across Python packages using `tach.toml`.

## Why

- Prevents circular imports and layer violations (for example, `crud` importing `api`, or `db` importing `services`) before they calcify.
- `exact = true` rejects undeclared cross-module imports instead of silently allowing new coupling.
- Runs in milliseconds on every commit and in CI without importing or executing application code.

## Config

Canonical `tach.toml` for a layered FastAPI/Python app:

```toml
exclude = [
    "tests",
    "scripts",
    ".venv",
    "**/__pycache__",
]
source_roots = ["."]
forbid_circular_dependencies = true
exact = true

# Layers: main -> api -> services -> crud -> db -> settings
# core and schemas are shared leaves.

[[modules]]
path = "app.main"
depends_on = ["app.api", "app.db"]

[[modules]]
path = "app.api"
depends_on = [
    "app.core",
    "app.crud",
    "app.db",
    "app.schemas",
    "app.services",
    "app.settings",
]

[[modules]]
path = "app.services"
depends_on = [
    "app.core",
    "app.crud",
    "app.db",
    "app.schemas",
    "app.settings",
]

[[modules]]
path = "app.crud"
depends_on = ["app.db", "app.core", "app.schemas"]

[[modules]]
path = "app.db"
depends_on = ["app.settings"]

[[modules]]
path = "app.schemas"
depends_on = ["app.core"]

[[modules]]
path = "app.core"
depends_on = []

[[modules]]
path = "app.settings"
depends_on = []
```

## Makefile

```makefile
tach:
	uv run tach check
```

## Lefthook

```yaml
pre-commit:
  commands:
    tach:
      glob: "*.py"
      run: uv run tach check
```

## CI

```yaml
- run: uv run tach check
```

## Gotchas

- `exact = true` fails if `depends_on` lists an unused dependency as well as an undeclared one; keep `depends_on` minimal.
- `source_roots` must point to the parent of `app/` (for example `["."]` or `["src"]`) so module paths resolve consistently locally and in CI.
- Add new top-level packages under `app/` to `tach.toml` when creating them, or `tach check` will reject imports to or from the undeclared module.
