---
tool: line-limit
scope: universal
tier: optional
summary: "Opt-in per-file line cap: compared only in repos that already ship scripts/check-line-limit.sh"
targets: ["scripts/check-line-limit.sh"]
detect: ["scripts/check-line-limit.sh"]
---

# Per-File Line Limit

## What

A small portable-bash script fails the build when any hand-written source file
exceeds a per-file line cap (**default 800**). **CI is the gate** — a full-tree
scan that can't be bypassed.

## Why

- Forces decomposition before a file becomes a 1,500-line grab-bag nobody wants to touch.
- Language-agnostic and dependency-free: one threshold across shell, Python, Go, TS, Makefiles, config. Just `wc -l` + git, so it works in repos with no linter at all.

## Why line count

Sprawl has no clean lint rule — cohesion metrics (LCOM/`cohesion`, Radon MI, Debtmap) are all class-scoped, single-language, or need git/coverage data, and none touches shell/Makefiles/config. Line count is the only file-level, all-language, zero-data proxy. It's orthogonal to *internal* complexity (long/branchy functions), which ruff (`C901`, `PLR091x`) and biome cover well — use both.

## When to use it / when not

- **Use** on repos you actively maintain and want to keep modular. Deliberate and opinionated, so it's opt-in: tooling-sync only compares repos that already have the script. To adopt it, copy the script below.
- **Exclude** what shouldn't be governed: generated files, vendored code, test fixtures, prompt text, lockfiles. The check only looks at *hand-written source*.

## The script

`scripts/check-line-limit.sh` — dual-mode: a no-arg full-tree scan for CI, or a file list for any local hook:

```bash
#!/bin/bash
# check-line-limit.sh - fail if any hand-written source file exceeds the limit.
#
# Usage:
#   scripts/check-line-limit.sh            # scan the repo source set (CI)
#   scripts/check-line-limit.sh FILE...    # check only the given files (local hook)
#
# Override the cap with LINE_LIMIT (default 800).
set -euo pipefail

LIMIT="${LINE_LIMIT:-800}"

# Folders this check never governs, even when the file matches the source set.
# Substring match, so 'src/data/' skips everything beneath it.
EXCLUDE_DIRS=(
  '/migrations/'    # generated
  '/fixtures/'      # test data
)

# Is PATH one of the source files this check governs? Adjust per repo — list the
# hand-written source dirs/extensions. Exclusions go in EXCLUDE_DIRS above.
is_source() {
  local f="$1" ex
  case "$f" in
    src/*.ts | src/*.tsx) ;;
    lib/*.sh | bin/*) ;;
    */*.py) ;;
    *) return 1 ;;
  esac
  for ex in ${EXCLUDE_DIRS[@]+"${EXCLUDE_DIRS[@]}"}; do
    [[ "$f" == *"$ex"* ]] && return 1
  done
  return 0
}

files=()
if [[ $# -gt 0 ]]; then
  for f in "$@"; do is_source "$f" && [[ -f "$f" ]] && files+=("$f"); done
else
  while IFS= read -r f; do is_source "$f" && [[ -f "$f" ]] && files+=("$f"); done < <(git ls-files)
fi

status=0
checked=0
for f in "${files[@]:-}"; do
  [[ -z "$f" ]] && continue
  checked=$((checked + 1))
  n=$(wc -l <"$f")
  if ((n > LIMIT)); then
    printf 'LINE LIMIT: %s has %d lines (max %d)\n' "$f" "$n" "$LIMIT" >&2
    status=1
  fi
done

if ((status != 0)); then
  printf '\nSplit the file(s) above into focused modules.\n' >&2
  exit 1
fi
printf 'line-limit OK (<= %d lines): %d files checked\n' "$LIMIT" "$checked"
```

Two per-repo knobs: `EXCLUDE_DIRS` — folder paths to skip, as plain substrings —
and `is_source()`, the hand-written source set (dirs + extensions). Keep the
exclusions in the list rather than folding them into the `case`: a `case`-branch
exclusion is invisible at a glance, and `${EXCLUDE_DIRS[@]+...}` is what keeps the
script safe under `set -u` on bash 3.2 (macOS) when the array is empty.

## CI — the gate

CI is the gate: a full-tree scan that also catches pre-existing over-limit files.

**GitHub** — `.github/workflows/line-limit.yml`:

```yaml
name: Line limit
on:
  push: { branches: [main] }
  pull_request: { branches: [main] }
jobs:
  line-limit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - run: bash scripts/check-line-limit.sh
```

**GitLab** — add a job to `.gitlab-ci.yml`:

```yaml
line-limit:
  stage: test
  script: bash scripts/check-line-limit.sh
```

## Makefile

```makefile
line-limit:
	@bash scripts/check-line-limit.sh
```

Fold `line-limit` into the aggregate `make ci`/`make lint` target.

## Optional: local pre-commit feedback

A latency optimization, not the gate — surface an over-limit file before it
reaches CI. Any hook runner can call the script on staged files. If you use
[lefthook](lefthook.md) (the playbook baseline):

```yaml
pre-commit:
  commands:
    line-limit:
      # slashless glob; is_source() does path filtering (see lefthook.md Gotchas)
      glob: "*.{ts,tsx,vue,py,sh}"
      run: bash scripts/check-line-limit.sh {staged_files}
```

## Gotchas

- **Tune the threshold deliberately** — too low forces artificial splits that hurt cohesion (a blunt cap can fragment a genuinely cohesive module). When you raise the limit for a repo, log *why*.
- A hard cap is a guardrail, not a design principle — split along real seams (cohesive function clusters), not at the arbitrary line where the counter trips.
