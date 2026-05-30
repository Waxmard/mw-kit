---
tool: makefile
scope: monorepo
tier: optional
summary: "Root Makefile orchestrator delegating to subprojects"
targets: ["Makefile"]
---

# Root Makefile Pattern

## What

Root Makefile orchestrates subprojects. Top-level targets are aggregates; subproject targets reachable via `<sub>-<target>` prefix, dispatched with pattern rules.

## Pattern

```makefile
.DEFAULT_GOAL := help

.PHONY: help
help:
	@echo "Setup: setup"
	@echo "Quality: lint | fix | typecheck | test | ci"
	@echo "Docs: docs-build | docs-check"
	@echo "Subprojects: backend-<target> | frontend-<target>"

# ----- Setup -----
.PHONY: setup
setup:
	npm install
	cd frontend && npm install
	cd fastapi && uv sync --extra dev --group dev

# ----- Aggregate -----
.PHONY: lint fix typecheck test ci
lint:      backend-lint frontend-lint
fix:       backend-fix frontend-fix
typecheck: backend-typecheck frontend-typecheck
test:      backend-test
ci:        backend-ci frontend-lint frontend-typecheck docs-check

# ----- Docs (generated from docs/src) -----
.PHONY: docs-build docs-check
docs-build:
	mise exec -- python3 scripts/build_docs.py --write
docs-check:
	mise exec -- python3 scripts/build_docs.py --check

# ----- Backend: pattern rule delegates anything -----
backend-%:
	$(MAKE) -C fastapi $*

# ----- Frontend -----
.PHONY: frontend-lint frontend-fix frontend-typecheck
frontend-lint:
	cd frontend && npm run lint && npm run format:check
frontend-fix:
	cd frontend && npm run lint:fix && npm run format
frontend-typecheck:
	cd frontend && npm run typecheck
```

## Why the pattern rule for backend

`backend-%: $(MAKE) -C fastapi $*` means **any** target in `fastapi/Makefile` is reachable from root as `make backend-X`. Add `make logs` to fastapi/Makefile → `make backend-logs` works at root automatically.

Frontend uses explicit targets because npm scripts aren't structured the same way.

## Why `mise exec --` for docs

Ensures python version pinned by `mise.toml` is used, even outside a shell with mise activated (CI runners).

## Anti-pattern: putting everything at root

Resist moving fastapi's `make dev` / `make logs` to root with hardcoded copies. Pattern rule keeps a single source of truth in fastapi/Makefile.
