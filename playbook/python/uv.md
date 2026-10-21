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

- Lockfile (`uv.lock`) is reproducible across platforms.
- `uv tool install` replaces pipx.
- Works directly off `pyproject.toml` — no second source of truth.

## Commands

```bash
uv init                        # new project
uv add fastapi                 # add dep
uv add --group dev pytest      # add dev dep
uv sync                        # install from lockfile
uv run pytest                  # run inside project env
uv lock                        # refresh lockfile
uv tool install ruff           # install global tool (pipx-style)
```

## Project layout

```toml
[project]
name = "my-app"
requires-python = ">=3.X"   # newest stable Python; only broaden for a published library
dependencies = ["fastapi"]

[dependency-groups]
dev = ["pytest", "pytest-cov", "mypy", "ruff"]
```

Dev tooling goes in `[dependency-groups]` (PEP 735); `uv sync` installs the `dev` group by default. `[project.optional-dependencies]` is only for user-facing extras.

## Application vs package

A **library** you publish/import needs a build backend so it installs into the
venv. A **deployable service** (FastAPI app, CronJob, worker) usually doesn't —
you run it as a module, not `import` it. For those, omit packaging entirely:

```toml
[project]
name = "my-service"
version = "0.0.0"
requires-python = ">=3.X"   # you own the runtime → newest stable Python
dependencies = ["fastapi[standard]"]

[dependency-groups]
dev = ["pytest", "mypy", "ruff"]

[tool.uv]
package = false              # explicit non-package (virtual) project
```

- **No `[build-system]`** → uv treats the project as a *virtual* (non-package)
  project: it installs deps + builds the venv but doesn't try to build/install
  the project itself. No `src/` layout, no `[project.scripts]`.
- **Flat `app/` package**, `tests/` sibling. Run via `python -m app.main` (or
  `uvicorn app.main:app`), not a console-script entry point.
- `uv sync` works locally; in Docker use `uv sync --frozen --no-install-project`
  and copy `app/` into the image separately:

  ```dockerfile
  WORKDIR /app
  ENV UV_COMPILE_BYTECODE=1 UV_PYTHON_DOWNLOADS=never
  COPY pyproject.toml uv.lock ./
  RUN --mount=type=cache,target=/root/.cache/uv \
      uv sync --frozen --no-dev --no-install-project
  COPY app/ ./app/
  ENTRYPOINT ["/app/.venv/bin/python", "-m", "app.main"]
  ```

- Full image conventions (base, non-root, import check): [dockerfile](../universal/dockerfile.md).
- pytest finds the flat package via `pythonpath = ["."]`; coverage targets
  `source = ["app"]`.

Pick packaged (`src/` + `[build-system]`) only when something actually imports
or installs the project. Most services are apps — skip the ceremony.

## CI

```yaml
- uses: astral-sh/setup-uv@vX.Y.Z # pin to latest stable; dependabot bumps it
  with:
    enable-cache: true
    cache-dependency-glob: "uv.lock"
- run: uv sync --locked
- run: uv run pytest
```

`enable-cache: true` caches uv downloads across runs, keyed on the lockfile.

## Gotchas

- Commit `uv.lock`.
- **Prefer newest, by default.** `requires-python` is your **support floor** — the oldest interpreter you promise to run on, pinned minor not patch. Pick it by who installs your code:
  - **Service / app** (you deploy it, you own the runtime): pin to the **newest stable** (check [python.org/downloads](https://www.python.org/downloads/) when applying). Nothing external constrains you, so ride the latest — newer interpreters are faster and let you use current syntax. Bump it as new stables land.
  - **Published library** (others `pip install` it): keep the floor **broad** (two or more minors below newest). A high floor makes uv/pip *refuse to install* for anyone on an older interpreter — only raise it when you actually need a newer feature.
  Either way, the floor is independent of the version you dev on (the [mise](../universal/mise.md) pin) — keep that on the newest stable regardless.
- `uv run` activates the venv per-command; don't `source .venv/bin/activate` manually.
- Minimal/Chainguard Python images set `ENTRYPOINT ["/usr/bin/python"]`, so setting `ENTRYPOINT` (not `CMD`) to `/app/.venv/bin/...` is required to use the virtualenv's packages.
