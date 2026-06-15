---
tool: pydantic
scope: python
tier: baseline
summary: "Data validation + settings via pydantic v2 / pydantic-settings"
targets: ["pyproject.toml"]
detect: ["**/*.py"]
---

# pydantic

## What

[pydantic v2](https://docs.pydantic.dev/) — runtime validation and serialization derived
from type hints. `BaseModel` for any data crossing a boundary (HTTP requests/responses,
webhook payloads, LLM structured output, message-queue records); `pydantic-settings`'
`BaseSettings` for config. The default validation layer for new Python projects, and the
native data model for FastAPI.

## Why

- Type hints you already write become enforced at runtime — no separate schema DSL.
- v2's core is Rust; fast enough to validate on every request without thinking about it.
- One model is request schema, response schema, and OpenAPI doc source at once.
- `pydantic-settings` validates env config with the same machinery, so bad config fails at
  startup, not at first use.

Always pin v2 (`pydantic>=2`). v1 is a different API — don't mix the two.

## Config

Dependencies (via [uv](./uv.md)):

```toml
dependencies = [
    "pydantic>=2",
    "pydantic-settings>=2",   # only if you load config from env
]
```

### Settings — `BaseSettings` + a cached getter

Config is a model. Env vars override field defaults; map each field to its env var with
`Field(alias=...)` and add constraints inline. Expose it through an `@lru_cache` getter so
the env is read once and the instance is shared (and easily overridden in tests).

```python
import functools
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", env_file=".env")

    api_key: str | None = Field(default=None, alias="API_KEY")
    timeout_seconds: int = Field(default=30, alias="TIMEOUT_SECONDS", gt=0)
    confidence_threshold: float = Field(default=0.99, ge=0.0, le=1.0)


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

`extra="ignore"` tolerates unrelated env vars. For nested settings models, set
`env_nested_delimiter="__"` so `AUTH__GROUPS_KEY=roles` populates `settings.auth.groups_key`.
Field constraints (`gt`, `ge`, `le`, `min_length`, …) turn invalid config into a clear
startup error.

### A shared base model

Give the project one `BaseModel` subclass that carries the config every model should share,
then inherit from it. Saves repeating `model_config` on every class.

```python
from pydantic import BaseModel, ConfigDict


class AppModel(BaseModel):
    model_config = ConfigDict(extra="ignore")  # forbid extra in stricter projects
```

### Models — separate inputs from outputs

Keep request and response models in separate modules (`requests.py` / `responses.py`, or
`models.py` for a small project). They diverge: requests are lenient and minimal, responses
carry computed and renamed fields.

```python
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import Field, computed_field


class NoteRequest(AppModel):
    content: str


class WebhookPayload(AppModel):
    # Literal narrows + lets you discriminate a union of payload types
    object_kind: Literal["merge_request"]
    reviewers: list[str] = Field(default_factory=list)


class InsightResponse(AppModel):
    id_: UUID = Field(serialization_alias="insight_id")   # clean attr, public wire name
    created_at: datetime
    duration_seconds: int | None = None

    @computed_field  # type: ignore[prop-decorator]
    def is_running(self) -> bool:
        return self.duration_seconds is None
```

Dump with `model_dump(by_alias=True)` to emit `serialization_alias` names. Use
`Field(default_factory=list)` for mutable/model defaults.

### Validation — reusable validators + `TypeAdapter`

For per-field or cross-field logic use `field_validator` / `model_validator`. For logic you
reuse across models, factor it into a named `BeforeValidator`/`AfterValidator` and attach it
with `Annotated`:

```python
from typing import Annotated, Any
from pydantic import BeforeValidator, model_validator


def _none_to_empty_list(value: Any) -> Any:
    return [] if value is None else value


NoneToEmptyList = BeforeValidator(_none_to_empty_list)

# in any model:
tags: Annotated[list[str], NoneToEmptyList] = Field(default_factory=list)


class SmtpSettings(AppModel):
    provider: str
    hostname: str = ""

    @model_validator(mode="before")
    @classmethod
    def _default_hostname(cls, data: Any) -> Any:
        if isinstance(data, dict) and not data.get("hostname"):
            if data.get("provider") == "gmail":
                data["hostname"] = "smtp.gmail.com"
        return data
```

Validate bare collections (no wrapper model) with `TypeAdapter`:

```python
from typing import Sequence
from pydantic import TypeAdapter

responses_adapter = TypeAdapter(Sequence[InsightResponse])
# responses_adapter.validate_python(raw)
# responses_adapter.dump_python(objs, by_alias=True)
```

## Gotchas

- **v1 vs v2 API.** `.dict()`/`.json()` → `.model_dump()`/`.model_dump_json()`;
  `@validator` → `@field_validator`; inner `class Config` → `model_config = ConfigDict(...)`.
  Don't paste v1 snippets.
- **`model_dump()` vs `model_dump(mode="json")`.** Plain dump keeps `UUID`/`datetime`/`Enum`
  as objects; use `mode="json"` (or `model_dump_json()`) for JSON-safe primitives.
- **Aliases are directional.** `serialization_alias` only renames output; to *accept* an
  aliased key on input use `validation_alias`, or `alias` for both (what `BaseSettings`
  needs to read env vars).
- **`by_alias` isn't automatic everywhere.** FastAPI response models apply it for you, but
  manual serialization (cache writes, queue messages) does not — pass `by_alias=True`.
- **Mutable defaults: use `default_factory`.** `= []` technically works (pydantic copies
  per-instance) but `Field(default_factory=list)` is the unambiguous idiom, especially for
  model and dict defaults.
- **`extra=` is a decision, not a default.** `"ignore"` for external payloads you don't
  control (webhooks, LLM JSON); `"forbid"` for internal models where an unexpected key is a
  bug. The silent default (`"ignore"` for settings, drop for models) hides typos.
