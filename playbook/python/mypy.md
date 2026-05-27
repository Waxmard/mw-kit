# mypy

## What

[mypy](https://mypy.readthedocs.io/) — static type checker. Strict mode by default.

## Why strict

If you bothered with type hints, run them in strict mode or skip them. Half-typed codebases mislead.

## Config

```toml
[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true
disallow_untyped_decorators = false
```

### `disallow_untyped_decorators = false`

FastAPI's `@app.get(...)` and SQLAlchemy declarative decorators are dynamically typed. Strict mode complains for every endpoint. Disable this one strict sub-rule rather than silencing per-decorator.

### `ignore_missing_imports = true`

Many libraries ship without type stubs. Without this, every third-party import is an error. Lose precision; gain pragmatism.

For libraries that DO have stubs but you want enforced, override per-module:

```toml
[[tool.mypy.overrides]]
module = "passlib.*"
ignore_missing_imports = false
```

## Stubs

Add type-only deps for stubs:

```toml
dev = [
    "types-passlib>=1.7.7",
    "types-python-jose>=3.3.4",
]
```

## CI

```yaml
- run: uv sync --extra dev
- run: uv run mypy app/
```

## Gotchas

- Don't typecheck tests by default — too many assertion ergonomics. If you want to: separate config target.
- Pin `python_version` to your minimum supported. mypy will reject syntax newer than that.
- SQLAlchemy 2.0 mapped types work out of box. SQLAlchemy 1.x needs `sqlalchemy-stubs`.
