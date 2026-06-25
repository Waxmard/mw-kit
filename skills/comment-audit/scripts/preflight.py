#!/usr/bin/env python3
"""Stage-1 pre-flight for the comment-audit skill: rank code files worth an
LLM comment-redundancy pass, cheaply, using `scc`.

The point of this gate is to NOT pay an LLM to read every file. `scc` counts
comment vs code lines per file in milliseconds; we keep the elevated ones and
hand the ranked list to stage 2 (the skill body), which is the actual judge of
whether a comment is redundant.

The floor is a COST DIAL, not a quality verdict. Across a 21-repo corpus the
median code file sits near a 7% comment ratio, so a 15% floor skips the
obviously-fine majority while surfacing anything elevated. It deliberately does
NOT assert that 15% (or any number) is "the right amount" of comments -- that
judgment is irreducibly contextual and belongs to stage 2. A human walks the
ranked list top-down and stops when satisfied, which is what bounds total cost,
so there is no top-N cap here: emit the whole list, ordered worst-first.

Two ways a file qualifies:
  - density: comment ratio >= floor (catches small bloated files)
  - volume:  >= VOLUME raw comment lines (catches big files whose ratio is
             diluted by lots of code but still carry many comments to review)

Only CODE languages are considered. Config/markup (YAML, Shell, JSON, Markdown,
Dockerfile, ...) comment to instruct or document, not to redundantly restate
code, so comment-redundancy auditing doesn't apply -- they're excluded.

Output is JSON on stdout (the skill consumes it); pass --table for a human view.
Requires `scc` on PATH (https://github.com/boyter/scc; `brew install scc`).
Runtime-stdlib only, so it runs under bare `python3`.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys

FLOOR = 0.15  # density path: comment / (code + comment) >= FLOOR
VOLUME = 80  # volume path: raw comment lines >= VOLUME
MIN_DENOM = 30  # ignore tiny files: one doc block swings the ratio
MIN_COMMENT = 8  # ...and require real comment mass on the density path

# scc's per-language name -> include only languages where comments tend to
# restate code (and thus can be redundant). Add languages here as needed.
CODE_LANGS = frozenset(
    {
        "TypeScript",
        "TSX",
        "JavaScript",
        "JSX",
        "Python",
        "Go",
        "Rust",
        "Java",
        "Kotlin",
        "Swift",
        "Lua",
        "C",
        "C++",
        "C Header",
        "C#",
        "PHP",
        "Scala",
        "Vue",
        "Svelte",
        "Ruby",
        "Objective-C",
        "Dart",
    }
)

# Paths that are code but not worth auditing for redundant comments.
SKIP_SUBSTR = (".test.", ".spec.", "/__tests__/", "/vendor/", "/node_modules/")


def scan(path: str, floor: float = FLOOR) -> list[dict[str, object]]:
    raw = subprocess.run(
        ["scc", "--by-file", "-f", "json", path],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    suspects: list[dict[str, object]] = []
    for lang in json.loads(raw or "[]"):
        if lang["Name"] not in CODE_LANGS:
            continue
        for f in lang["Files"]:
            if f["Generated"] or f["Minified"] or f["Binary"]:
                continue
            loc = f["Location"]
            if any(s in loc for s in SKIP_SUBSTR):
                continue
            code, comment = f["Code"], f["Comment"]
            denom = code + comment
            if denom == 0:
                continue
            ratio = comment / denom
            dense = ratio >= floor and denom >= MIN_DENOM and comment >= MIN_COMMENT
            voluminous = comment >= VOLUME
            if not (dense or voluminous):
                continue
            suspects.append(
                {
                    "file": loc,
                    "lang": lang["Name"],
                    "ratio": round(ratio, 3),
                    "comment": comment,
                    "code": code,
                    # rank key: blends density and volume so neither a tiny 70%
                    # file nor a huge 18% file dominates on its own.
                    "score": round(ratio * math.log10(comment + 1), 3),
                    "via": "+".join(
                        p for p, on in (("dense", dense), ("vol", voluminous)) if on
                    ),
                }
            )
    return sorted(suspects, key=lambda s: s["score"], reverse=True)  # type: ignore[arg-type, return-value]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Rank code files for a comment-redundancy audit."
    )
    ap.add_argument(
        "path", nargs="?", default=".", help="repo or directory to scan (default: .)"
    )
    ap.add_argument(
        "--floor",
        type=float,
        default=FLOOR,
        help=f"density cost-dial, comment ratio (default {FLOOR})",
    )
    ap.add_argument(
        "--table", action="store_true", help="human-readable table instead of JSON"
    )
    args = ap.parse_args()

    if shutil.which("scc") is None:
        print(
            "error: `scc` not found on PATH. Install with `brew install scc` "
            "(https://github.com/boyter/scc).",
            file=sys.stderr,
        )
        return 2

    suspects = scan(args.path, args.floor)

    if not args.table:
        json.dump(
            {
                "path": args.path,
                "floor": args.floor,
                "count": len(suspects),
                "suspects": suspects,
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
        return 0

    if not suspects:
        print(f"no suspects in {args.path} (floor {args.floor:.0%})")
        return 0
    print(f"{len(suspects)} suspect(s) @ floor {args.floor:.0%}, worst-first:\n")
    for s in suspects:
        print(
            f"  {s['score']:.3f}  {s['ratio']:>4.0%}  "
            f"{s['comment']:>4}c/{s['code']:<5}loc  {s['via']:<9} "
            f"{s['lang']:<11} {s['file']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
