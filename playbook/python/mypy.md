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
python_version = "3.14"
strict = true
ignore_missing_imports = true
```

### `ignore_missing_imports = true`

Many libraries ship without type stubs. Without this, every third-party import is an error. Lose precision; gain pragmatism.

For libraries that DO have stubs but you want enforced, override per-module:

```toml
[[tool.mypy.overrides]]
module = "<typed_lib>.*"
ignore_missing_imports = false
```

Typed-but-stubless deps: add `types-<lib>` to the `dev` dependency group.

## CI

```yaml
- run: uv sync --locked
- run: uv run mypy app/
```

In GitLab CI, cache `.mypy_cache/` keyed by branch slug with a fallback to the default branch (see [ci-gitlab](../universal/ci-gitlab.md)). This avoids repeating AST/type analysis from scratch on every run.

## Gotchas

- Don't typecheck tests by default — too many assertion ergonomics. If you want to: separate config target.
- Pin `python_version` to match the `requires-python` floor in [uv](./uv.md) — newest stable for a service (`3.14`), the broad floor for a published library — *not* the version you dev on. Targeting a newer version than you support lets version-only syntax slip past the checker and break users on the floor.
