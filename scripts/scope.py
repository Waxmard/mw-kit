#!/usr/bin/env python3
"""Deterministic pre-flight + scope resolution for the tooling-sync skill.

Given a consumer repo path, this script does the mechanical half of tooling-sync:
validate the repo, detect platform + project structure, glob each playbook page's
`detect` patterns against the repo's tracked files, resolve the baseline
alternatives (dependabot vs renovate, which release tool), and check which of each
in-scope page's `targets` files actually exist. It emits a single JSON "scope plan"
on stdout.

It does NOT read config contents or judge drift — that stays in the skill, which is
where semantic merge reasoning belongs. Anything genuinely ambiguous (unknown
platform, single-component-but-nested layout) is surfaced under `needs_ask` rather
than guessed.

Reads page frontmatter directly (the source of truth), not the generated MANIFEST.

Stdlib only. Run: python3 scripts/scope.py [REPO_PATH]   (default: CWD)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path

# parse_frontmatter / PLAYBOOK live next door in build_manifest.py — reuse them so
# the two scripts can never disagree on how a page's frontmatter is read.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_manifest import PLAYBOOK, parse_frontmatter  # noqa: E402

# Manifest files that signal a project root, used for structure detection.
PROJECT_MANIFESTS = ["pyproject.toml", "package.json", "go.mod"]


# ---------------------------------------------------------------------------
# glob helpers (detect patterns + target paths)
# ---------------------------------------------------------------------------


def expand_braces(pattern: str) -> list[str]:
    """Expand a single `{a,b,c}` group, e.g. `*.{ts,tsx}` -> [`*.ts`, `*.tsx`].

    Only one group is supported — that is all the detect schema uses.
    """
    start = pattern.find("{")
    end = pattern.find("}", start)
    if start == -1 or end == -1:
        return [pattern]
    pre, body, post = pattern[:start], pattern[start + 1 : end], pattern[end + 1 :]
    return [f"{pre}{opt}{post}" for opt in body.split(",")]


def detect_matches(pattern: str, files: list[str]) -> bool:
    """True if any tracked file matches a `detect` glob.

    `**/*.py` means "any .py anywhere" — match it against the full path, the
    `**/`-stripped suffix, and the basename so root-level files count too.
    """
    for pat in expand_braces(pattern):
        suffix = pat[3:] if pat.startswith("**/") else None
        for f in files:
            base = f.rsplit("/", 1)[-1]
            if fnmatch(f, pat) or (suffix and (fnmatch(f, suffix) or fnmatch(base, suffix))):
                return True
    return False


def target_present(target: str, repo: Path) -> bool:
    """True if a page `target` exists in the repo (file, dir, or glob match)."""
    if any(c in target for c in "*?["):
        for pat in expand_braces(target):
            if list(repo.glob(pat)):
                return True
        return False
    return (repo / target).exists()


# ---------------------------------------------------------------------------
# repo inspection
# ---------------------------------------------------------------------------


def git(repo: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def detect_platform(repo: Path) -> tuple[str, str]:
    """Return (platform, source). platform is github | gitlab | unknown."""
    url = git(repo, "remote", "get-url", "origin")
    if not url:
        return "unknown", "no-remote"
    low = url.lower()
    if "gitlab" in low:
        return "gitlab", "remote"
    if "github.com" in low:
        return "github", "remote"
    return "unknown", "remote"


def detect_structure(tracked: list[str]) -> dict:
    """Classify single_project | multi_component | ambiguous from manifest layout."""
    manifests = [f for f in tracked if f.rsplit("/", 1)[-1] in PROJECT_MANIFESTS]
    dirs = {f.rsplit("/", 1)[0] if "/" in f else "" for f in manifests}
    root_orchestrator = any(
        f in ("Makefile", "docker-bake.hcl") for f in tracked
    )

    if len(dirs) >= 2:
        verdict, ambiguous = "multi_component", False
    elif len(manifests) == 1 and "/" in manifests[0]:
        # one project, but nested under a named component dir — strong monorepo
        # signal but not conclusive. Ask.
        verdict, ambiguous = "ambiguous", True
    elif manifests:
        verdict, ambiguous = "single_project", False
    else:
        verdict, ambiguous = "single_project", False

    return {
        "verdict": verdict,
        "ambiguous": ambiguous,
        "manifests": sorted(manifests),
        "root_orchestrator": root_orchestrator,
    }


# ---------------------------------------------------------------------------
# page scoping
# ---------------------------------------------------------------------------


def load_pages() -> list[dict]:
    pages = []
    for md in sorted(PLAYBOOK.rglob("*.md")):
        if md.name in {"README.md", "MANIFEST.md"}:
            continue
        fm = parse_frontmatter(md.read_text())
        if not fm or "tool" not in fm:
            continue
        fm["_page"] = md.relative_to(PLAYBOOK).as_posix()
        pages.append(fm)
    return pages


def as_list(val) -> list[str]:
    if isinstance(val, list):
        return val
    return [val] if val else []


def scope_pages(pages, repo, tracked, platform, structure) -> dict:
    in_scope, skipped = [], []
    for p in pages:
        tool = p.get("tool", "")
        page = p["_page"]
        scope = p.get("scope", "")
        pf = p.get("platform") or "any"
        detect = as_list(p.get("detect"))
        targets = as_list(p.get("targets"))

        # 1. monorepo pages only apply to multi-component repos
        if scope == "monorepo" and structure["verdict"] == "single_project":
            skipped.append({"tool": tool, "page": page, "reason": "single-project (monorepo scope)"})
            continue

        # 2. platform restriction
        platform_pending = False
        if pf != "any" and platform != "unknown" and pf != platform:
            skipped.append({"tool": tool, "page": page, "reason": f"platform: {pf}-only"})
            continue
        if pf != "any" and platform == "unknown":
            platform_pending = True  # can't decide until platform known

        # 3. detect globs ("—"/empty = always relevant within its scope)
        matched = None
        if detect:
            matched = next((d for d in detect if detect_matches(d, tracked)), None)
            if matched is None:
                skipped.append({"tool": tool, "page": page, "reason": "no detect match"})
                continue

        present = [t for t in targets if target_present(t, repo)]
        row = {
            "tool": tool,
            "page": page,
            "scope": scope,
            "tier": p.get("tier", ""),
            "platform": pf,
            "targets": targets,
            "targets_present": present,
            "targets_missing": [t for t in targets if t not in present],
            "matched_detect": matched,
        }
        if platform_pending:
            row["platform_pending"] = True
        in_scope.append(row)
    return {"in_scope": in_scope, "skipped": skipped}


def resolve_alternatives(in_scope, platform, structure) -> dict:
    """Pick dep-update bot + release tool; drop the losing alternatives in place."""
    tools = {r["tool"] for r in in_scope}
    has = lambda t: any(r["targets_present"] for r in in_scope if r["tool"] == t)  # noqa: E731
    dropped, notes = [], []

    # --- dep updates: dependabot vs renovate ---
    if platform == "gitlab":
        dep, dep_reason = "renovate", "gitlab (renovate only)"
    elif has("renovate") and not has("dependabot"):
        dep, dep_reason = "renovate", "renovate already configured"
    elif has("dependabot") and not has("renovate"):
        dep, dep_reason = "dependabot", "dependabot already configured"
    else:
        dep, dep_reason = "dependabot", "github default (renovate is the alternative)"
    for alt in ("dependabot", "renovate"):
        if alt != dep and alt in tools:
            dropped.append(alt)

    # --- releases: monorepo overrides, but only where a page exists for the
    # platform. The releases-monorepo page is gitlab-only; release-please
    # (github) handles monorepos natively via config, so on a github
    # multi-component repo we stay on releases-github and flag the caveat.
    is_py = any(r["scope"] == "python" for r in in_scope)
    multi = structure["verdict"] == "multi_component"
    rel_note = None
    if multi and platform == "gitlab":
        rel, rel_reason = "releases-monorepo", "gitlab multi-component (path-scoped bumps)"
    elif platform == "github":
        rel, rel_reason = "releases-github", "github (release-please)"
        if multi:
            rel_note = "multi-component: configure release-please for monorepo (no dedicated page)"
    elif platform == "gitlab" and is_py:
        rel, rel_reason = "releases-python", "gitlab + python (python-semantic-release)"
    elif platform == "gitlab":
        rel, rel_reason = "releases-gitlab", "gitlab (semantic-release)"
    else:
        rel, rel_reason = None, "platform unknown"
    release_tools = {"releases-github", "releases-gitlab", "releases-python", "releases-monorepo"}
    for alt in release_tools:
        if alt != rel and alt in tools:
            dropped.append(alt)

    releases = {"chosen": rel, "reason": rel_reason}
    if rel_note:
        releases["note"] = rel_note
    return {
        "dep_updates": {"chosen": dep, "reason": dep_reason},
        "releases": releases,
        "dropped": sorted(dropped),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="tooling-sync scope resolver")
    ap.add_argument("repo", nargs="?", default=".", help="consumer repo path (default: CWD)")
    ap.add_argument(
        "--platform",
        choices=["github", "gitlab"],
        help="override platform detection (use after resolving a needs_ask)",
    )
    ap.add_argument(
        "--structure",
        choices=["single_project", "multi_component"],
        help="override structure detection (use after resolving a needs_ask)",
    )
    a = ap.parse_args()
    repo = Path(a.repo).resolve()

    # --- pre-flight ---
    toplevel = git(repo, "rev-parse", "--show-toplevel")
    if not toplevel:
        print(json.dumps({"preflight": {"ok": False, "error": "not a git repo"}}, indent=2))
        return 1
    repo = Path(toplevel)
    if repo == PLAYBOOK.parent:
        print(json.dumps({"preflight": {"ok": False, "error": "this is mw-kit itself"}}, indent=2))
        return 1
    if not (PLAYBOOK / "MANIFEST.md").is_file():
        print(json.dumps({"preflight": {"ok": False, "error": "playbook MANIFEST.md not found"}}, indent=2))
        return 1

    if a.platform:
        platform, platform_source = a.platform, "override"
    else:
        platform, platform_source = detect_platform(repo)

    tracked = (git(repo, "ls-files") or "").splitlines()
    structure = detect_structure(tracked)
    if a.structure:
        structure["verdict"] = a.structure
        structure["ambiguous"] = False
        structure["source"] = "override"

    pages = load_pages()
    scoped = scope_pages(pages, repo, tracked, platform, structure)
    alternatives = resolve_alternatives(scoped["in_scope"], platform, structure)

    # drop the losing alternatives out of in_scope into skipped
    in_scope, skipped = [], list(scoped["skipped"])
    for r in scoped["in_scope"]:
        if r["tool"] in alternatives["dropped"]:
            skipped.append({"tool": r["tool"], "page": r["page"], "reason": "alternative not chosen"})
        else:
            in_scope.append(r)

    # sanity: a chosen alternative must be in scope, else the plan is incoherent
    scoped_tools = {r["tool"] for r in in_scope}
    warnings = []
    for kind in ("dep_updates", "releases"):
        chosen = alternatives[kind]["chosen"]
        if chosen and chosen not in scoped_tools:
            warnings.append(f"{kind}: chosen '{chosen}' is not in scope ({alternatives[kind]['reason']})")

    needs_ask = []
    if platform == "unknown":
        needs_ask.append({
            "key": "platform",
            "question": "Could not detect platform from the remote — is this GitHub or GitLab?",
        })
    if structure["ambiguous"]:
        needs_ask.append({
            "key": "structure",
            "question": (
                f"Found one nested manifest ({', '.join(structure['manifests'])}) — is this a "
                "single project, or is it becoming a multi-component monorepo?"
            ),
        })

    plan = {
        "preflight": {"ok": True, "repo": str(repo), "platform": platform, "platform_source": platform_source},
        "structure": structure,
        "alternatives": alternatives,
        "in_scope": in_scope,
        "skipped": sorted(skipped, key=lambda r: r["tool"]),
        "needs_ask": needs_ask,
        "warnings": warnings,
    }
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
