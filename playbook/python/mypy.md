---
tool: mypy
scope: python
tier: baseline
summary: "Static type checker, strict mode"
targets: ["pyproject.toml"]
detect: ["**/*.py"]
---

# mypy

## What

[mypy](https://mypy.readthedocs.io/) — static type checker.

## Config

```toml
[tool.mypy]
python_version = "3.X"  # newest stable Python; match requires-python
strict = true
follow_untyped_imports = true
```

### `follow_untyped_imports = true`

`follow_untyped_imports = true` inspects installed untyped third-party packages without silently turning missing imports into `Any` (which also breaks single-directory runs like `mypy tests/` by dropping local package types).

Typed-but-stubless deps: add `types-<lib>` to the `dev` dependency group.

For genuinely stubless or broken third-party packages, opt out per-module:

```toml
[[tool.mypy.overrides]]
module = "<untyped_lib>.*"
ignore_missing_imports = true
```

### IDE venv discovery (`[tool.pyright]`)

Optional editor-only Pyright/Pylance discovery so IDEs resolve `.venv` without making Pyright a CI gate (`mypy --strict` stays the sole CI typechecker):

```toml
[tool.pyright]
venv = ".venv"
venvPath = "."
```

## CI

```yaml
- run: uv sync --locked
- run: uv run mypy app/
```


## Gotchas

- Don't typecheck tests by default — too many assertion ergonomics. If you want to: separate config target.
- Pin `python_version` to match the `requires-python` floor in [uv](./uv.md) — newest stable for a service, the broad floor for a published library — *not* the version you dev on. Targeting a newer version than you support lets version-only syntax slip past the checker and break users on the floor.
