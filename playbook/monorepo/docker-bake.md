---
tool: docker-bake
scope: monorepo
tier: optional
summary: "Declarative multi-platform builds + skip-redundant-push CI"
targets: ["docker-bake.hcl"]
detect: ["**/Dockerfile*", "docker-bake.hcl"]
---

# Docker Bake

## What

[docker buildx bake](https://docs.docker.com/build/bake/) — declarative multi-target/multi-platform builds via HCL. Replaces shell-script orchestration of `docker buildx build` calls.

## Why

- Build matrix in code, not bash.
- Parallel builds across targets.
- Multi-arch (amd64 + arm64) in one command.
- Shared base layers across services in a monorepo (one cache).
- `--push` per-target controllable.

## Use case: monorepo with automated registry pushes

Goal: every push to main builds + pushes service images, **but skip pushes if source/Dockerfile unchanged** (no churn, faster CI, smaller registry storage).

## docker-bake.hcl

```hcl
variable "REGISTRY" {
  default = "ghcr.io/waxmard"
}

variable "TAG" {
  default = "latest"
}

group "default" {
  targets = ["backend"]
}

group "all" {
  targets = ["backend", "frontend"]
}

target "backend" {
  context    = "./fastapi"
  dockerfile = "Dockerfile"
  tags       = ["${REGISTRY}/backend:${TAG}"]
  platforms  = ["linux/amd64", "linux/arm64"]
}

target "frontend-web" {
  context    = "./frontend"
  dockerfile = "Dockerfile.web"
  tags       = ["${REGISTRY}/frontend-web:${TAG}"]
  platforms  = ["linux/amd64", "linux/arm64"]
}

target "local" {
  inherits  = ["backend"]
  platforms = ["linux/amd64"]
  tags      = ["app-backend:local"]
}
```

## Avoiding redundant pushes (CI pattern)

Strategy: compute a content hash of each service's source tree. Tag image with that hash. Check registry — skip push if tag exists.

```yaml
- name: Compute backend source hash
  id: hash
  run: |
    HASH=$(git ls-tree -r HEAD fastapi/ | sha256sum | cut -c1-12)
    echo "tag=$HASH" >> $GITHUB_OUTPUT

- name: Check if image already exists
  id: check
  run: |
    if docker manifest inspect ghcr.io/waxmard/backend:${{ steps.hash.outputs.tag }} >/dev/null 2>&1; then
      echo "exists=true" >> $GITHUB_OUTPUT
    else
      echo "exists=false" >> $GITHUB_OUTPUT
    fi

- name: Build + push backend
  if: steps.check.outputs.exists == 'false'
  run: |
    TAG=${{ steps.hash.outputs.tag }} docker buildx bake backend --push

- name: Tag :latest from existing hash
  if: steps.check.outputs.exists == 'true'
  run: |
    docker buildx imagetools create \
      -t ghcr.io/waxmard/backend:latest \
      ghcr.io/waxmard/backend:${{ steps.hash.outputs.tag }}
```

### Key idea

- Tag every build with the source hash (immutable).
- `:latest` is a pointer that always retags from the matching hash.
- `manifest inspect` is a HEAD request — cheap probe before the expensive build.
- `imagetools create` retags multi-arch manifests server-side (no rebuild, no transfer).

## Local Makefile glue

```makefile
build-local:
	docker buildx bake local

build-multi:
	docker buildx bake backend

push:
	@if [ -z "$(REGISTRY)" ]; then echo "Set REGISTRY"; exit 1; fi
	REGISTRY=$(REGISTRY) docker buildx bake --push

setup-buildx:
	docker buildx create --name multiplatform --driver docker-container --use
	docker buildx inspect --bootstrap
```

## Gotchas

- `git ls-tree -r HEAD <path>` includes file modes + sha hashes, so it changes only on real content change — better than `git rev-parse HEAD:<path>` for selective hashing.
- The hash must include the Dockerfile and any build-context files outside the service dir (e.g. shared `requirements/` or `.dockerignore`).
- `docker manifest inspect` returns 0 only if all platforms exist. If you add a new platform later, all old hashes are "missing" → rebuild.
- Use `--cache-from` / `--cache-to` GH Actions cache backend for additional speedup beyond skip-on-hash.
