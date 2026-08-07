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
ci:        backend-ci frontend-lint frontend-typecheck

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

## Anti-pattern: putting everything at root

Resist moving fastapi's `make dev` / `make logs` to root with hardcoded copies. Pattern rule keeps a single source of truth in fastapi/Makefile.
