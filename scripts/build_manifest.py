#!/usr/bin/env python3
"""Generate playbook/MANIFEST.md from each page's YAML frontmatter.

Source of truth = the frontmatter block at the top of every
playbook/<scope>/<tool>.md page. This script collects those blocks into a
single index table that the tooling-sync skill reads first to decide which
pages are relevant to a given repo.

Stdlib only. Run: python3 scripts/build_manifest.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PLAYBOOK = ROOT / "playbook"
MANIFEST = PLAYBOOK / "MANIFEST.md"

SCOPE_ORDER = ["universal", "python", "node", "k8s", "monorepo"]

ROW_TEMPLATE = (
    "| `{tool}` | {tier} | {summary} | {targets} | {detect} | [{path}]({path}) |"
)

VALID_TIERS = {"baseline", "optional"}
SEMVER_RE = re.compile(r"(?<!\d\.)\b\d+\.\d+\.\d+\b(?!\.\d)")
PIN_COMMENT_RE = re.compile(r"#\s*v\d+\.\d+\.\d+\b")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)")


def parse_frontmatter(text: str) -> dict[str, Any] | None:
    """Parse a leading `---` YAML-ish frontmatter block.

    Handles scalars (quoted or bare) and inline JSON lists (`["a", "b"]`),
    which is all our schema uses — no PyYAML dependency.
    """
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    data: dict[str, Any] = {}
    for raw in text[3:end].splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if val.startswith(("[", "{")):
            try:
                val = json.loads(val)
            except json.JSONDecodeError as e:
                raise ValueError(f"invalid JSON for key {key!r}: {val!r}") from e
        else:
            val = val.strip('"').strip("'")
        data[key] = val
    return data


def fmt_list(val: object) -> str:
    return ", ".join(f"`{x}`" for x in as_list(val)) or "—"


def as_list(val: object) -> list[str]:
    if isinstance(val, list):
        return [str(x) for x in val]
    return [str(val)] if val else []


def combined_detect(p: dict[str, Any]) -> list[str]:
    """Path globs (`detect`) plus content regexes (`detect_content`, shown as
    `content:<re>`) — both signal relevance, so both appear in the Detect column."""
    return as_list(p.get("detect")) + [
        f"content:{c}" for c in as_list(p.get("detect_content"))
    ]


def load_pages(*, warn: bool = False) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    for md in sorted(PLAYBOOK.rglob("*.md")):
        if md.name in {"README.md", "MANIFEST.md"}:
            continue
        try:
            fm = parse_frontmatter(md.read_text())
        except ValueError as e:
            raise ValueError(f"{md.relative_to(ROOT)}: {e}") from e
        if not fm or "tool" not in fm:
            if warn:
                print(
                    f"warn: no frontmatter in {md.relative_to(ROOT)}",
                    file=sys.stderr,
                )
            continue
        rel = md.relative_to(PLAYBOOK).as_posix()
        fm["_page"] = rel
        pages.append(fm)
    return pages


def _validate_page_meta(
    md: Path,
    rel: str,
    text: str,
    playbook_dir: Path,
    readme_cache: dict[Path, str],
) -> list[str]:
    errors: list[str] = []
    try:
        fm = parse_frontmatter(text)
    except ValueError as e:
        errors.append(f"{rel}: {e}")
        fm = None
    if fm is None:
        errors.append(f"{rel}: missing or invalid frontmatter")
    else:
        tool = fm.get("tool")
        if not isinstance(tool, str) or not tool.strip():
            errors.append(f"{rel}: missing or empty 'tool'")
        scope = fm.get("scope")
        if not isinstance(scope, str) or scope not in SCOPE_ORDER:
            errors.append(f"{rel}: invalid 'scope' {scope!r}")
        elif scope != md.parent.name:
            errors.append(
                f"{rel}: 'scope' {scope!r} does not match dir {md.parent.name!r}"
            )
        tier = fm.get("tier")
        if not isinstance(tier, str) or tier not in VALID_TIERS:
            errors.append(f"{rel}: invalid 'tier' {tier!r}")
        summary = fm.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            errors.append(f"{rel}: missing or empty 'summary'")
        targets = fm.get("targets")
        if not isinstance(targets, list) or not all(
            isinstance(t, str) and bool(t.strip()) for t in targets
        ):
            errors.append(f"{rel}: 'targets' must be a list of non-empty strings")

    readme = md.parent / "README.md"
    if not readme.exists():
        errors.append(f"{rel}: missing scope README {readme.name}")
    else:
        rtext = readme_cache.setdefault(readme, readme.read_text())
        if f"({md.name})" not in rtext and f"(./{md.name})" not in rtext:
            errors.append(f"{rel}: not linked in {readme.relative_to(playbook_dir)}")
    return errors


def _validate_markdown_body(
    md: Path, rel: str, text: str, *, is_page: bool
) -> list[str]:
    errors: list[str] = []
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence and is_page:
            if "uses:" in line:
                continue
            pins = [(m.start(), m.end()) for m in PIN_COMMENT_RE.finditer(line)]
            for m in SEMVER_RE.finditer(line):
                ver = m.group(0)
                if ver in {"0.0.0", "0.1.0"}:
                    continue
                if any(a <= m.start() and m.end() <= b for a, b in pins):
                    continue
                errors.append(
                    f"{rel}:{lineno}: hardcoded semver {ver!r} in fenced block"
                )
        elif not in_fence:
            for m in LINK_RE.finditer(line):
                dest = m.group(1)
                if dest.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                target = dest.split("#", 1)[0]
                if target and not (md.parent / target).exists():
                    errors.append(f"{rel}:{lineno}: broken relative link {dest!r}")
    return errors


def validate_playbook(playbook_dir: Path = PLAYBOOK) -> list[str]:
    errors: list[str] = []
    readme_cache: dict[Path, str] = {}
    for md in sorted(playbook_dir.rglob("*.md")):
        if md.name == "MANIFEST.md":
            continue
        rel = md.relative_to(playbook_dir).as_posix()
        text = md.read_text()
        is_page = md.name != "README.md"
        if is_page:
            errors.extend(
                _validate_page_meta(md, rel, text, playbook_dir, readme_cache)
            )
        errors.extend(_validate_markdown_body(md, rel, text, is_page=is_page))
    return errors


def main() -> int:
    errors = validate_playbook()
    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1
    pages = load_pages(warn=True)
    out = [
        "<!-- GENERATED by scripts/build_manifest.py from page frontmatter. "
        "Do not edit by hand. -->",
        "",
        "# Playbook Manifest",
        "",
        "Machine-readable index of every playbook page. Source of truth = each "
        "page's YAML frontmatter; regenerate with `python3 scripts/build_manifest.py`.",
        "",
        "- **tier** — `baseline` (most repos should adopt) vs `optional` "
        "(context-specific pattern).",
        "- **targets** — files/dirs in a consumer repo this page governs "
        "(what to compare / where to apply).",
        "- **detect** — path globs, plus `content:<re>` regexes matched against "
        "YAML bodies; if any matches the page is relevant "
        "(— = always relevant for its scope).",
        "",
    ]

    for scope in SCOPE_ORDER:
        group = sorted(
            (p for p in pages if p.get("scope") == scope),
            key=lambda p: p.get("tool", ""),
        )
        if not group:
            continue
        out += [
            f"## {scope}",
            "",
            "| Tool | Tier | Summary | Targets | Detect | Page |",
            "|---|---|---|---|---|---|",
        ]
        for p in group:
            out.append(
                ROW_TEMPLATE.format(
                    tool=p.get("tool", ""),
                    tier=p.get("tier", "") or "—",
                    summary=p.get("summary", "") or "",
                    targets=fmt_list(p.get("targets")),
                    detect=fmt_list(combined_detect(p)),
                    path=p["_page"],
                )
            )
        out.append("")

    MANIFEST.write_text("\n".join(out).rstrip() + "\n")
    print(f"wrote {MANIFEST.relative_to(ROOT)} ({len(pages)} pages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
