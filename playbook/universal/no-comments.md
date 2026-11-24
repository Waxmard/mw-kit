---
tool: no-comments
scope: universal
tier: optional
summary: "Block code comments and unapproved lint suppressions with a small keep-list"
targets: ["scripts/check-comments.py"]
detect: ["**/*.{ts,tsx,js,jsx,svelte,vue,py}"]
---

# Zero-Comment & Suppression Gate

## What

A dependency-free Python script (`scripts/check-comments.py`) that blocks inline comments and unapproved lint/type suppressions across Python and JS/TS files, allowing only a tight 5-item keep-list.

## Why

- Narrating what code does rots faster than the code itself and clutters diffs.
- Unreviewed suppression comments (`eslint-disable`, `biome-ignore`, `@ts-ignore`, `@ts-expect-error`, `# noqa`, `# type: ignore`) silently punch holes in typecheckers and linters.
- An automated gate forces constraints into types, linters, tests, or clear naming instead of prose workarounds.

## Config

`scripts/check-comments.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import io
import os
import re
import sys
import tokenize
from pathlib import Path

KEEP_PREFIXES = (
    "SPDX-License-Identifier:",
    "biome-ignore format:",
    "prettier-ignore",
)
URL_RE = re.compile(r"https?://\S+")
SUPPRESSION_RE = re.compile(
    r"(?:eslint-disable|biome-ignore|@ts-ignore|@ts-expect-error"
    r"|#\s*noqa\b|#\s*type:\s*ignore\b)"
)
ALLOWED_SUPPRESSIONS: set[str] = set()
TARGET_SUFFIXES = frozenset({".py", ".ts", ".tsx", ".js", ".jsx"})
SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "dist",
        "build",
    }
)


def is_kept(comment: str, *, allow_docstrings: bool = False) -> bool:
    if comment.startswith("#!"):
        return True
    body = comment.lstrip("#/").lstrip("*").strip()
    if SUPPRESSION_RE.search(comment) and not any(
        a in comment for a in ALLOWED_SUPPRESSIONS
    ):
        return False
    if body.startswith(KEEP_PREFIXES) or URL_RE.search(body):
        return True
    return allow_docstrings and comment.startswith("/**")


def check_python(path: Path, text: str) -> list[str]:
    errs: list[str] = []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type == tokenize.COMMENT and not is_kept(tok.string):
            errs.append(
                f"{path}:{tok.start[0]}: disallowed comment; delete narration or "
                "encode the constraint in a type, lint, or test"
            )
    return errs


def _skip_js_string(text: str, start: int, line: int) -> tuple[int, int]:
    quote = text[start]
    i, n = start + 1, len(text)
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            if text[i + 1] == "\n":
                line += 1
            i += 2
            continue
        if ch == "\n":
            line += 1
        i += 1
        if ch == quote:
            break
    return i, line


def scan_js_comments(text: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    i, n, line = 0, len(text), 1
    while i < n:
        ch = text[i]
        if ch == "\n":
            line += 1
            i += 1
            continue
        if ch in ("'", '"', "`"):
            i, line = _skip_js_string(text, i, line)
            continue
        if text.startswith("//", i):
            end = text.find("\n", i)
            end = n if end == -1 else end
            found.append((line, text[i:end]))
            i = end
            continue
        if text.startswith("/*", i):
            start_line = line
            end = text.find("*/", i + 2)
            end = n if end == -1 else end + 2
            line += text[i:end].count("\n")
            found.append((start_line, text[i:end]))
            i = end
            continue
        i += 1
    return found


def iter_target_files(args: list[str]) -> list[Path]:
    if args:
        return [Path(raw) for raw in args]
    paths: list[Path] = []
    for root, dirs, files in os.walk("."):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            path = Path(root) / name
            if path.suffix in TARGET_SUFFIXES:
                paths.append(path)
    return paths


def main() -> int:
    errors: list[str] = []
    for p in iter_target_files(sys.argv[1:]):
        if not p.is_file():
            continue
        if p.suffix == ".py":
            errors.extend(check_python(p, p.read_text(encoding="utf-8")))
        elif p.suffix in TARGET_SUFFIXES:
            for ln, body in scan_js_comments(p.read_text(encoding="utf-8")):
                if not is_kept(body):
                    errors.append(
                        f"{p}:{ln}: disallowed comment; delete narration or "
                        "encode the constraint in a type, lint, or test"
                    )
    for err in errors:
        print(err, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### Keep-list (5 cases)

1. `SPDX-License-Identifier:` / license headers.
2. Formatter-ignore markers (`biome-ignore format:`, `prettier-ignore`).
3. Issue or RFC links (`https://...`).
4. Public API docstrings/JSDoc when opted in (`allow_docstrings=True`).
5. External-dependency workarounds tagged with an upstream URL.

Shebang lines (`#!`) are always preserved. Correctness suppressions (`eslint-disable`, `biome-ignore`, `@ts-ignore`, `@ts-expect-error`, `# noqa`, `# type: ignore`) are always rejected unless explicitly listed in `ALLOWED_SUPPRESSIONS`.

## Lefthook

```yaml
pre-commit:
  commands:
    no-comments:
      glob: "*.{py,ts,tsx,js,jsx}"
      run: python3 scripts/check-comments.py {staged_files}
```

## CI

```yaml
- run: python3 scripts/check-comments.py
```

## Gotchas

- `tokenize.generate_tokens` avoids false positives on `#` inside Python strings and URLs, and `is_kept` preserves `#!` shebangs so executable scripts pass unmodified.
- For JS/TS, the character scanner skips `'...'`, `"..."`, and `` `...` `` literals so `https://` URLs inside strings are never flagged; if your codebase uses regex literals containing `//`, extend the scanner or rely on Biome/ESLint AST rules.
