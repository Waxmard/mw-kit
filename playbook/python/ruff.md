---
tool: ruff
scope: python
tier: baseline
summary: "Lint + format (replaces flake8 + isort + black + bandit-partial)"
targets: ["pyproject.toml"]
detect: ["**/*.py"]
---

# ruff

## What

[ruff](https://docs.astral.sh/ruff/) — single-tool lint + format for Python. Replaces flake8 + isort + pyupgrade + black + bandit (partial).

## Config

Canonical `[tool.ruff]` block — the full preferred config to diff a repo against:

```toml
[tool.ruff]
target-version = "py314"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM", "RUF", "PL", "S"]
ignore = [
    "PLR0911",  # too-many-return-statements
    "PLR0913",  # too-many-arguments (noisy with FastAPI Depends)
    "PLR2004",  # magic-value-comparison (HTTP status codes)
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = [
    "S101",     # asserts ok in tests
    "S105",     # hardcoded test passwords ok
    "S106",     # same kwarg form
    "PLC0415",  # scoped imports in fixtures
]

[tool.ruff.lint.isort]
combine-as-imports = true

[tool.ruff.lint.flake8-bugbear]
extend-immutable-calls = [
    "fastapi.Depends", "fastapi.Query", "fastapi.Path",
    "fastapi.Body", "fastapi.Header", "fastapi.Cookie",
    "fastapi.File", "fastapi.Form", "fastapi.Security",
]
```

### Rule selection

| Code | Pack | Why |
|---|---|---|
| `E` | pycodestyle errors | Baseline |
| `F` | pyflakes | Unused imports, undefined names |
| `I` | isort | Import sorting |
| `B` | bugbear | Real bug patterns |
| `UP` | pyupgrade | Use modern syntax (no `.format()`, etc.) |
| `SIM` | simplify | `if x: return True else: return False` → `return bool(x)` |
| `RUF` | ruff-specific | Misc bugs + style |
| `PL` | pylint | pylint; PLR0911/PLR0913/PLR2004 ignored in Config, rest kept |
| `S` | bandit | Security: hardcoded passwords, subprocess shell=True, etc. |

**Skipped on purpose**: `D` (docstrings) — too noisy, comments are a per-project call; `ANN` (annotations) — mypy already enforces.

### FastAPI-specific

`flake8-bugbear.extend-immutable-calls` lists the FastAPI dependency markers. Without it, every `Depends(get_db)` in a default argument trips `B008` (function-call-in-default-argument).

## Commands

```bash
uv run ruff check app/         # lint
uv run ruff check app/ --fix   # lint + autofix safe rules
uv run ruff format app/        # format (black-compat)
uv run ruff format --check app/  # check-only (CI)
```

Hook: see [lefthook](../universal/lefthook.md).

## Gotchas

- Run lint **before** format, both with `stage_fixed: true` — format may rewrite lint-fixed code, both autofix layers compose cleanly.
- **`target-version` must match the lowest runtime, not the newest.** Code loaded by another project's interpreter (plugins, scripts loaded via `importlib`) must target *that* project's `requires-python`.
