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

[ruff](https://docs.astral.sh/ruff/) — single-tool lint + format for Python. Replaces flake8 + isort + pyupgrade + black + bandit (partial) + more.

## Why

- One tool, one config, one cache.
- Rust-fast — pre-commit becomes invisible.
- Format is black-compatible (drop-in).
- Rule selection is explicit (you opt in to families).

## Config

Canonical `[tool.ruff]` block — the full preferred config to diff a repo against:

```toml
[tool.ruff]
line-length = 88
target-version = "py314"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM", "RUF", "PL", "S"]
ignore = [
    "PLR0911",  # too-many-return-statements
    "PLR0913",  # too-many-arguments (noisy with FastAPI Depends)
    "PLR2004",  # magic-value-comparison (HTTP codes in tests)
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
| `PL` | pylint | Refactor + bugs; keep PLE (errors) + PLW (warnings), prune PLR* |
| `S` | bandit | Security: hardcoded passwords, subprocess shell=True, etc. |

**Skipped on purpose**: `D` (docstrings) — too noisy, comments are a per-project call; `ANN` (annotations) — mypy already enforces.

### Per-file overrides

`tests/**` exempts the bandit assert/password rules (`S101`/`S105`/`S106`) and scoped-import rule (`PLC0415`) — asserts and hardcoded test passwords are fine in tests, and fixtures legitimately import inside functions.

### FastAPI-specific

`flake8-bugbear.extend-immutable-calls` lists the FastAPI dependency markers. Without it, every `Depends(get_db)` in a default argument trips `B008` (function-call-in-default-argument).

### Import sorting

`isort.combine-as-imports = true` collapses `from x import (a, b)` style imports cleanly.

## Commands

```bash
uv run ruff check app/         # lint
uv run ruff check app/ --fix   # lint + autofix safe rules
uv run ruff format app/        # format (black-compat)
uv run ruff format --check app/  # check-only (CI)
```

## Lefthook

```yaml
ruff-lint:
  root: fastapi/
  glob: "**/*.py"
  run: uv run ruff check --fix {staged_files}
  stage_fixed: true

ruff-format:
  root: fastapi/
  glob: "**/*.py"
  run: uv run ruff format {staged_files}
  stage_fixed: true
```

## Gotchas

- Run lint **before** format, both with `stage_fixed: true` — format may rewrite lint-fixed code, both autofix layers compose cleanly.
- Don't enable `D` blanket. Pick specific docstring rules if needed.
- `PLR*` (refactor) is subjective. Default: ignore the high-cyclomatic ones (PLR0911, PLR0913), keep PLE/PLW.
- `S101` (asserts) trips tests — always exempt `tests/**`.
