---
tool: dockerfile
scope: universal
tier: baseline
summary: "Dockerfile + .dockerignore: digest-pinned Chainguard base, uv venv stage, non-root, build-time import check"
targets: ["Dockerfile", ".dockerignore"]
detect: ["Dockerfile", "**/Dockerfile*"]
---

# Dockerfile

## What

Python services build in two stages on a digest-pinned Chainguard base: a `builder` stage resolves the `uv` lockfile into a virtualenv, and the runtime stage copies the venv and `src/` and runs as a non-root user. A `RUN python -c "import ..."` smoke check fails the build if a runtime dependency is missing. A `.dockerignore` keeps the build context small and free of secrets. Frontends that compile to static files use the nginx variant below.

## Why

- Chainguard images are minimal and ship few CVEs, so the [security](./security.md) image scan stays quiet.
- Pinning by digest makes builds reproducible, and renovate/dependabot bumps the digest in an MR/PR.
- A non-root `USER` limits what a compromised process can do, and Cloud Run and Kubernetes policies often require it.
- Installing dependencies before copying `src/` keeps the dependency layer cached across code-only changes.
- A missing dependency otherwise surfaces only after deploy, as an opaque Cloud Run "failed to listen on PORT" timeout. The import check turns that into an instant build failure.

## Config

Python service `Dockerfile`:

```dockerfile
# Stage 1: Build the virtual environment
# Chainguard's free tier publishes only `latest`/`latest-dev` (no version tags),
# so the runtime is pinned by digest for reproducibility; renovate bumps it.
# `requires-python>=3.X` (newest stable) makes `uv sync` below fail loudly if the base regresses.
FROM cgr.dev/chainguard/python:latest-dev@sha256:<digest> AS builder

# Copy the uv binary from the official image (static binary, works in Chainguard)
# pin to latest stable; renovate bumps it
COPY --from=ghcr.io/astral-sh/uv:X.Y.Z /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install dependencies (without project) using the lockfile
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Stage 2: Final runtime image
FROM cgr.dev/chainguard/python:latest-dev@sha256:<digest>

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY src/ ./src/

# Fail the build (not Cloud Run startup) if the venv is missing a runtime
# dependency. A startup ModuleNotFoundError only surfaces as an opaque
# "failed to listen on PORT" health-check timeout after deploy; catching it
# here turns that into an instant, legible build failure.
# Exec form: distroless runtimes (Chainguard `latest`, non-dev) have no /bin/sh.
RUN ["/app/.venv/bin/python", "-c", "import <runtime deps>"]

USER 65532

EXPOSE 8080

ENTRYPOINT []
CMD ["python", "src/<entry>.py"]
```

`.dockerignore`:

```gitignore
.git
.gitignore
__pycache__
*.pyc
.venv/
build/
dist/
*.egg-info/
.env
.env.*
.pytest_cache/
.mypy_cache/
.ruff_cache/
.uv-cache/
.cache/
.coverage
htmlcov/
tests/
docs/
node_modules/
.github/
.gitlab-ci.yml
renovate.json
```

## SPA frontend variant (nginx runtime)

For a frontend that builds to static files. Node only exists in the builder stage; the runtime is nginx as a non-root user.

```dockerfile
# ─── Stage 1: Build ───────────────────────────────────────────────────────────
# current Node Active LTS
FROM node:NN-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json .npmrc ./

# Inject a private registry token via BuildKit secret — never persists in image layers
ARG NPM_PKG_REGISTRY
RUN --mount=type=secret,id=npm_token \
    NPM_TOKEN=$(cat /run/secrets/npm_token) && \
    npm config set "//${NPM_PKG_REGISTRY}:_authToken" "${NPM_TOKEN}" && \
    npm ci --ignore-scripts && \
    npm config delete "//${NPM_PKG_REGISTRY}:_authToken"

COPY . .

RUN npm run build

# ─── Stage 2: Runtime ─────────────────────────────────────────────────────────
# pin to latest stable; renovate bumps it
FROM nginx:X.Y.Z-alpine

RUN addgroup -g 1000 appuser && \
    adduser -S -u 1000 -G appuser appuser

COPY --chown=appuser:appuser nginx.conf /etc/nginx/nginx.conf
COPY --from=builder --chown=appuser:appuser /app/dist /usr/share/nginx/html

RUN mkdir -p /tmp/nginx/client_body \
             /tmp/nginx/proxy \
             /tmp/nginx/fastcgi \
             /tmp/nginx/uwsgi \
             /tmp/nginx/scgi && \
    chown -R appuser:appuser /tmp/nginx \
                              /usr/share/nginx/html \
                              /var/log/nginx \
                              /var/cache/nginx

USER appuser

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
```

If using a private npm registry, build with `--build-arg NPM_PKG_REGISTRY=<registry host and path>` and `--secret id=npm_token,env=NPM_TOKEN`.

Why this shape: a built SPA needs no Node at runtime, so the final image has less attack surface, and `npm ci --ignore-scripts` blocks install-time scripts from running in the build.

## Gotchas

- Chainguard's free tier publishes only `latest`/`latest-dev`, so pin by digest; a bare tag gives you a different base on every build.
- Secrets go through `RUN --mount=type=secret,id=<id>`, never `ARG` (build args persist in image metadata). Pass `--secret` only when the Dockerfile mounts it.
- nginx must listen on 8080, not 80, to run as non-root. Set `listen 8080;` in `nginx.conf`.
- Alpine + Vite/rolldown builds need `ARG ROLLDOWN_SKIP_NATIVE_BUILD=true` in the builder stage.
- Use `python:3.X-slim` only when a native dependency needs glibc tooling Chainguard lacks; the default is Chainguard.
- Don't serve a built SPA from a Node runtime image; use the nginx variant above.
