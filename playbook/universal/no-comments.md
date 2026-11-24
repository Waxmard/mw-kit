---
tool: no-comments
scope: universal
tier: optional
summary: "Block code comments and unapproved lint suppressions with a small keep-list"
targets: ["scripts/check-comments.py", "eslint.config.js"]
detect: ["**/*.{ts,tsx,js,jsx,svelte,vue,py}"]
---

# Zero-Comment & Suppression Gate

## What

A dependency-free Python script (`scripts/check-comments.py`) that blocks inline comments and unapproved lint/type suppressions across Python, JS/TS and Svelte files, allowing only a tight 6-item keep-list. Repos that already lint with ESLint use the inline rule under "ESLint repos" instead and do not install the script.

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
import re
import subprocess
import sys
import tokenize
from pathlib import Path

KEEP_PREFIXES = (
    "SPDX-License-Identifier:",
    "biome-ignore format:",
    "prettier-ignore",
    "ponytail:",
)
URL_RE = re.compile(r"https?://\S+")
SUPPRESSION_RE = re.compile(
    r"(?:eslint-disable|biome-ignore(?! format:)|svelte-ignore|@ts-ignore"
    r"|@ts-expect-error|#\s*noqa\b|#\s*type:\s*ignore\b)"
)
ALLOWED_SUPPRESSIONS: set[str] = set()
TARGET_SUFFIXES = frozenset(
    {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".svelte"}
)
REGEX_PRECEDERS = frozenset("(,=:[!&|?{};+-*%~^")
REGEX_KEYWORDS = frozenset(
    {
        "return",
        "typeof",
        "case",
        "void",
        "delete",
        "in",
        "of",
        "throw",
        "new",
        "do",
        "else",
        "yield",
        "await",
    }
)
WORD_END_RE = re.compile(r"[A-Za-z_$][\w$]*$")
SVELTE_BLOCK_RE = re.compile(
    r"<(script|style)\b(?:[^>\"']|\"[^\"]*\"|'[^']*')*>(.*?)</\1>", re.S
)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
MESSAGE = (
    "disallowed comment; delete narration or encode the constraint in a type, "
    "lint, or test"
)


def is_kept(comment: str, *, allow_docstrings: bool = False) -> bool:
    if comment.startswith("#!"):
        return True
    if SUPPRESSION_RE.search(comment) and not any(
        a in comment for a in ALLOWED_SUPPRESSIONS
    ):
        return False
    body = comment.removeprefix("<!--").lstrip("#/").lstrip("*").strip()
    if body.startswith(KEEP_PREFIXES) or URL_RE.search(body):
        return True
    return allow_docstrings and comment.startswith("/**")


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


def _starts_js_regex(text: str, i: int) -> bool:
    j = i - 1
    while j >= 0 and text[j] in " \t\r\n":
        j -= 1
    if j < 0 or text[j] in REGEX_PRECEDERS or text.endswith("=>", 0, j + 1):
        return True
    word = WORD_END_RE.search(text, max(0, j - 10), j + 1)
    return word is not None and word.group() in REGEX_KEYWORDS


def _skip_js_regex(text: str, start: int) -> int:
    i, n, in_class = start + 1, len(text), False
    while i < n and text[i] != "\n":
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "[":
            in_class = True
        elif ch == "]":
            in_class = False
        elif ch == "/" and not in_class:
            return i + 1
        i += 1
    return i


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
        if ch == "/" and _starts_js_regex(text, i):
            i = _skip_js_regex(text, i)
            continue
        i += 1
    return found


def scan_svelte_comments(text: str) -> list[tuple[int, str]]:
    def line_at(pos: int) -> int:
        return text.count("\n", 0, pos) + 1

    found: list[tuple[int, str]] = []
    for block in SVELTE_BLOCK_RE.finditer(text):
        start = block.start(2)
        if block.group(1) == "script":
            base = line_at(start) - 1
            found.extend(
                (base + line, body) for line, body in scan_js_comments(block.group(2))
            )
        else:
            found.extend(
                (line_at(start + css.start()), css.group())
                for css in CSS_COMMENT_RE.finditer(block.group(2))
            )
    markup = SVELTE_BLOCK_RE.sub(lambda b: "\n" * b.group().count("\n"), text)
    found.extend(
        (markup.count("\n", 0, html.start()) + 1, html.group())
        for html in HTML_COMMENT_RE.finditer(markup)
    )
    return sorted(found)


def comments_in(path: Path, text: str) -> list[tuple[int, str]]:
    if path.suffix == ".py":
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        return [(t.start[0], t.string) for t in tokens if t.type == tokenize.COMMENT]
    if path.suffix == ".svelte":
        return scan_svelte_comments(text)
    return scan_js_comments(text)


def iter_target_files(args: list[str]) -> list[Path]:
    names = (
        args
        or subprocess.run(
            ["git", "ls-files", "-z"], capture_output=True, text=True, check=True
        ).stdout.split("\0")
    )
    return [Path(name) for name in names if Path(name).suffix in TARGET_SUFFIXES]


def main() -> int:
    failed = False
    for path in iter_target_files(sys.argv[1:]):
        if not path.is_file():
            continue
        for line, comment in comments_in(path, path.read_text(encoding="utf-8")):
            if not is_kept(comment):
                print(f"{path}:{line}: {MESSAGE}", file=sys.stderr)
                failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### Keep-list (6 cases)

1. `SPDX-License-Identifier:` / license headers.
2. Formatter-ignore markers (`biome-ignore format:`, `prettier-ignore`).
3. Issue or RFC links (`https://...`).
4. Public API docstrings/JSDoc when opted in (`allow_docstrings=True`).
5. External-dependency workarounds tagged with an upstream URL.
6. Deliberate-shortcut markers (`ponytail:`) that name the ceiling and the upgrade path.

Shebang lines (`#!`) are always preserved. Correctness suppressions (`eslint-disable`, `biome-ignore`, `svelte-ignore`, `@ts-ignore`, `@ts-expect-error`, `# noqa`, `# type: ignore`) are always rejected unless explicitly listed in `ALLOWED_SUPPRESSIONS`.

## Lefthook

```yaml
pre-commit:
  commands:
    no-comments:
      glob: "*.{py,ts,tsx,js,jsx,mjs,cjs,svelte}"
      run: python3 scripts/check-comments.py {staged_files}
```

## CI

```yaml
- run: python3 scripts/check-comments.py
```

## ESLint repos

When ESLint already parses the code, ban comments with an inline rule in `eslint.config.js` and skip the script, its Lefthook command and its CI step. The parser finds comments exactly, so no string or regex heuristics are needed. Keep the script only if the repo also has Python sources.

```js
const keptComment = /^\s*(?:ponytail:|prettier-ignore)|https?:\/\/\S+/;
const suppression = /eslint-disable|svelte-ignore|@ts-ignore|@ts-expect-error/;
const cssComment = /\/\*[\s\S]*?\*\//g;
const noComments = {
  create(context) {
    const source = context.sourceCode;
    const check = (text, loc) => {
      if (suppression.test(text) || !keptComment.test(text))
        context.report({
          loc,
          message:
            'Disallowed comment; delete narration or encode the constraint in a type, lint, or test.',
        });
    };
    return {
      Program() {
        for (const comment of source.getAllComments())
          if (comment.type !== 'Shebang') check(comment.value, comment.loc);
      },
      SvelteHTMLComment(node) {
        check(node.value, node.loc);
      },
      SvelteStyleElement(node) {
        for (const match of source.getText(node).matchAll(cssComment)) {
          const start = node.range[0] + match.index;
          check(match[0].slice(2, -2), {
            start: source.getLocFromIndex(start),
            end: source.getLocFromIndex(start + match[0].length),
          });
        }
      },
    };
  },
};

export default [
  {
    linterOptions: { noInlineConfig: true },
    plugins: { local: { rules: { 'no-comments': noComments } } },
    rules: { 'local/no-comments': 'error' },
  },
];
```

The two `Svelte*` visitors only fire under `svelte-eslint-parser`; drop them in repos without Svelte. The keep-list is `ponytail:`, `prettier-ignore`, and any comment carrying a URL; shebangs always pass.

## Gotchas

- `tokenize.generate_tokens` avoids false positives on `#` inside Python strings and URLs, and `is_kept` preserves `#!` shebangs so executable scripts pass unmodified.
- For JS/TS, the character scanner skips `'...'`, `"..."`, and `` `...` `` literals so `https://` URLs inside strings are never flagged; regex literals are skipped by looking at the token before the `/`; JSX text and template literals that nest backticks inside `${}` are not parsed.
- Svelte: only `<script>`, `<style>` and markup comments are scanned; a `/* */` inside a `{...}` template expression is not.
- ESLint variant: `noInlineConfig: true` is required. Without it an `eslint-disable` comment switches the rule off before the rule can report that comment.
- ESLint variant: `svelte-eslint-parser` exposes script and `{...}` expression comments through `getAllComments()`, markup comments as `SvelteHTMLComment` nodes, and nothing for `<style>`, so style comments are matched by regex on the `SvelteStyleElement` text.
