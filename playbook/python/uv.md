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
requires-python = ">=3.14"   # newest stable; only broaden for a published library
dependencies = ["fastapi>=0.128"]

[project.optional-dependencies]
dev = ["pytest>=7", "mypy>=1.3", "ruff>=0.15"]

[dependency-groups]
dev = ["pytest-cov>=7"]
```

Two dep buckets exist — historical reason. `[project.optional-dependencies]` is PEP 621 standard; `[dependency-groups]` is PEP 735 newer. Use whichever or both; CI installs `--extra dev --group dev`.

## Application vs package

A **library** you publish/import needs a build backend so it installs into the
venv. A **deployable service** (FastAPI app, CronJob, worker) usually doesn't —
you run it as a module, not `import` it. For those, omit packaging entirely:

```toml
[project]
name = "my-service"
version = "0.0.0"
requires-python = ">=3.14"   # you own the runtime → pin to newest stable
dependencies = ["fastapi[standard]>=0.121"]

[dependency-groups]
dev = ["pytest>=8", "mypy>=1.18", "ruff>=0.13"]

# no [build-system] — flat app/ layout, run as a module
```

- **No `[build-system]`** → uv treats the project as a *virtual* (non-package)
  project: it installs deps + builds the venv but doesn't try to build/install
  the project itself. No `src/` layout, no `[project.scripts]`.
- **Flat `app/` package**, `tests/` sibling. Run via `python -m app.main` (or
  `uvicorn app.main:app`), not a console-script entry point.
- `uv sync` works locally; in Docker use `uv sync --frozen --no-install-project`
  and copy `app/` into the image separately:

  ```dockerfile
  COPY pyproject.toml uv.lock ./
  RUN uv sync --frozen --no-dev --no-install-project
  COPY app/ ./app/
  ENTRYPOINT ["/app/venv/bin/python", "-m", "app.main"]
  ```

- pytest finds the flat package via `pythonpath = ["."]`; coverage targets
  `source = ["app"]`.

Pick packaged (`src/` + `[build-system]`) only when something actually imports
or installs the project. Most services are apps — skip the ceremony.

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
- **Prefer newest, by default.** `requires-python` is your **support floor** — the oldest interpreter you promise to run on, pinned minor not patch. Pick it by who installs your code:
  - **Service / app** (you deploy it, you own the runtime): pin to the **newest stable** (`>=3.14` as of mid-2026). Nothing external constrains you, so ride the latest — newer interpreters are faster and let you use current syntax. Bump it as new stables land.
  - **Published library** (others `pip install` it): keep the floor **broad** (`>=3.13` or lower). A high floor makes uv/pip *refuse to install* for anyone on an older interpreter — only raise it when you actually need a newer feature.
  Either way, the floor is independent of the version you dev on (the [[mise]] pin) — keep that on the newest stable regardless.
- `uv run` activates the venv per-command; don't `source .venv/bin/activate` manually.
