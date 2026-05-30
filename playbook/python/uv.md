---
tool: uv
scope: python
tier: baseline
summary: "Fast Python package manager + venv + lockfile"
targets: ["pyproject.toml", "uv.lock"]
detect: ["pyproject.toml", "**/*.py"]
---

# uv

## What

[uv](https://docs.astral.sh/uv/) — fast Python package manager + venv tool from Astral.

## Why

- 10-100x faster than pip/pip-tools/poetry.
- Single binary, no Python bootstrap problem.
- Lockfile (`uv.lock`) is reproducible across platforms.
- `uv tool install` replaces pipx.
- Works directly off `pyproject.toml` — no second source of truth.

## Why not poetry / pip + venv / pipenv

- poetry: slow, opinionated lockfile, separate `poetry.lock` semantics. uv is faster and reads pyproject directly.
- pip + venv: no real lockfile.
- pipenv: dead.

## Commands

```bash
uv init                        # new project
uv add fastapi                 # add dep
uv add --group dev pytest      # add dev dep
uv sync                        # install from lockfile
uv sync --extra dev --group dev  # include optional + grouped extras
uv run pytest                  # run inside project env
uv lock                        # refresh lockfile
uv tool install ruff           # install global tool (pipx-style)
```

## Project layout

```toml
[project]
name = "my-app"
requires-python = ">=3.11"
dependencies = ["fastapi>=0.128"]

[project.optional-dependencies]
dev = ["pytest>=7", "mypy>=1.3", "ruff>=0.15"]

[dependency-groups]
dev = ["pytest-cov>=7", "tach>=0.34"]
```

Two dep buckets exist — historical reason. `[project.optional-dependencies]` is PEP 621 standard; `[dependency-groups]` is PEP 735 newer. Use whichever or both; CI installs `--extra dev --group dev`.

## CI

```yaml
- uses: astral-sh/setup-uv@v7
  with:
    enable-cache: true
    cache-dependency-glob: "fastapi/uv.lock"
- run: uv sync --extra dev --group dev
- run: uv run pytest
```

`enable-cache: true` is the killer feature — caches the entire resolution.

## Gotchas

- Commit `uv.lock`.
- `requires-python = ">=3.11"` — pin minor, not patch.
- `uv run` activates the venv per-command; don't `source .venv/bin/activate` manually.
