.DEFAULT_GOAL := help

.PHONY: help setup fmt lint typecheck test ci manifest

help:
	@echo "Setup:    setup           install dev deps (uv)"
	@echo "Quality:  fmt | lint | typecheck | test | ci"
	@echo "Playbook: manifest        regenerate playbook/MANIFEST.md"

# ----- Setup -----
setup:
	uv sync

# ----- Quality (single python subproject today; add Go targets later) -----
fmt:
	uv run ruff check --fix scripts/ tests/
	uv run ruff format scripts/ tests/

lint:
	uv run ruff check scripts/ tests/
	uv run ruff format --check scripts/ tests/

typecheck:
	uv run mypy scripts/

test:
	uv run pytest

# Aggregate gate (what CI runs)
ci: lint typecheck test

# ----- Playbook -----
manifest:
	python3 scripts/build_manifest.py
