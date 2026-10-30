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

A portable Bash script checks hand-written source files against a line cap (default 800). Run a full-tree scan in CI and pass individual files for local checks.

## Why

Line count is a dependency-free, language-agnostic proxy for file sprawl, not cohesion. Use it alongside function-complexity checks, not instead of them.

## When to use it / when not

- Opt in by copying the script below. tooling-sync only compares repos that already contain it.
- Exclude generated files, vendored code, fixtures, prompt text, and lockfiles.

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

Adjust `is_source()` for the repo's source files and `EXCLUDE_DIRS` for excluded path substrings. The `${EXCLUDE_DIRS[@]+...}` expansion keeps empty arrays safe under `set -u` on Bash 3.2 (macOS).

## CI — the gate

Use a full-tree CI scan to catch existing over-limit files.

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

For earlier feedback, run the script on staged files with [lefthook](lefthook.md):

```yaml
pre-commit:
  commands:
    line-limit:
      # slashless glob; is_source() does path filtering (see lefthook.md Gotchas)
      glob: "*.{ts,tsx,vue,py,sh}"
      run: bash scripts/check-line-limit.sh {staged_files}
```

## Gotchas

- Treat the cap as a guardrail. Split along cohesive boundaries, not arbitrary lines; document why you raise the threshold.
