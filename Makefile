.DEFAULT_GOAL := help

.PHONY: help setup fmt lint typecheck test line-limit ci manifest

help:
	@echo "Setup:    setup           install dev deps (uv)"
	@echo "Quality:  fmt | lint | typecheck | test | line-limit | ci"
	@echo "Playbook: manifest        regenerate playbook/MANIFEST.md"

setup:
	uv sync

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

line-limit:
	@bash scripts/check-line-limit.sh

# Aggregate gate (what CI runs)
ci: lint typecheck test line-limit

manifest:
	python3 scripts/build_manifest.py
