# pytest + coverage

## What

[pytest](https://docs.pytest.org/) for tests, `pytest-cov` for coverage.

## Config

```toml
dev = [
    "pytest>=7",
    "pytest-asyncio>=0.21",
    "pytest-cov>=7",
    "httpx>=0.24",
    "aiosqlite>=0.19",
]

[tool.coverage.run]
source = ["app"]
concurrency = ["greenlet", "thread"]
omit = [
    "app/__init__.py",
    "app/main.py",
    "app/settings.py",
    "app/db/database.py",
    "app/*/__init__.py",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
```

### Omit list

Bootstrap files (`main.py`, `settings.py`, `database.py`) wire dependencies and have meaningful test value only via integration runs. Excluding them gives a meaningful unit-test coverage number.

### `concurrency = ["greenlet", "thread"]`

Required for async SQLAlchemy with greenlet executors. Without it, coverage doesn't see code that runs inside greenlet contexts.

## Commands

```bash
uv run pytest                                       # all tests
uv run pytest tests/test_items.py                   # one file
uv run pytest -k "test_name"                        # filter
uv run pytest --cov=app --cov-report=term-missing   # with coverage
```

## CI

```yaml
- run: uv run pytest --cov=app --cov-report=term-missing
```

## Gotchas

- `pytest-asyncio` mode: prefer `mode = "auto"` so `async def test_*` works without `@pytest.mark.asyncio` on every test.
- Use `aiosqlite` as test DB to skip Postgres in unit tests. Integration tests can hit real Postgres.
- Set `S101`/`S105`/`S106` ruff ignores for `tests/**` — assertions and test passwords are fine.
