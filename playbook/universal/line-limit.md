---
tool: line-limit
scope: universal
tier: optional
summary: "Per-file line cap enforced by a small script in lefthook + CI"
targets: ["scripts/check-line-limit.sh", "lefthook.yml"]
---

# Per-File Line Limit

## What

A small portable-bash script fails the build when any hand-written source file exceeds a per-file line cap (**default 800**). Wired into a `line-limit` lefthook job (staged-file scoped, instant local feedback) and a CI job (full-tree scan, the real gate).

## Why

- Forces decomposition before a file becomes a 1,500-line grab-bag nobody wants to touch.
- The cap is a forcing function: when CI goes red you split the file into focused modules — which is the cheap moment to do it, not six months later.
- Language-agnostic and dependency-free: one threshold across shell, Python, Go, TS, whatever. No per-linter `max-lines` rule to configure and keep in sync.
- Cheap to run (just `wc -l`), so it costs nothing on every commit.

## Why not a linter's max-lines rule

- ESLint `max-lines` / pylint `too-many-lines` / etc. are per-language and per-tool — you'd configure and tune the same number in N places, and they don't cover shell/Makefiles/config.
- A standalone script is one threshold, one exclusion list, one place to reason about. It also runs in repos with no linter at all.

## When to use it / when not

- **Use** on repos you actively maintain and want to keep modular. It's a deliberate, opinionated guardrail — hence `optional` tier, not baseline.
- The threshold is a preference, **tune per repo** (default 800; a doc-heavy or generated-heavy repo may want higher, a tight library lower).
- **Exclude** what shouldn't be governed: generated files, vendored code, test fixtures, prompt text, lockfiles. The check only looks at *hand-written source*.

## The script

`scripts/check-line-limit.sh` — dual-mode so the same script backs both lefthook and CI:

```bash
#!/bin/bash
# check-line-limit.sh - fail if any hand-written source file exceeds the limit.
#
# Usage:
#   scripts/check-line-limit.sh            # scan the repo source set (CI)
#   scripts/check-line-limit.sh FILE...    # check only the given files (lefthook)
#
# Override the cap with LINE_LIMIT (default 800).
set -euo pipefail

LIMIT="${LINE_LIMIT:-800}"

# Is PATH one of the source files this check governs? Adjust per repo — list the
# hand-written source dirs/extensions, exclude generated/vendored/fixtures.
is_source() {
  case "$1" in
    src/*.ts | src/*.tsx) return 0 ;;
    lib/*.sh | bin/*) return 0 ;;
    */*.py) case "$1" in test/*|*/migrations/*) return 1 ;; *) return 0 ;; esac ;;
    *) return 1 ;;
  esac
}

# The full governed set, for the no-argument (CI) scan.
collect_default() {
  git ls-files
}

files=()
if [[ $# -gt 0 ]]; then
  for f in "$@"; do is_source "$f" && [[ -f "$f" ]] && files+=("$f"); done
else
  while IFS= read -r f; do is_source "$f" && [[ -f "$f" ]] && files+=("$f"); done < <(collect_default)
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

The single per-repo knob is `is_source()` — list the hand-written source paths and exclude generated/vendored/test-fixture paths there. `collect_default` uses `git ls-files` so untracked junk is never counted.

## Decomposition pattern (when a file nears the cap)

Split into focused modules without changing the public source contract:

- **Shell** — umbrella pattern: keep the entry file thin and have it `source` the split-out siblings, so `source entry.sh` still pulls the full surface and nothing that sources it needs to change.

  ```bash
  # entry.sh keeps core helpers, then:
  _DIR="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
  source "${_DIR}/auth.sh"
  source "${_DIR}/config.sh"
  ```

- **Python** — extract a cohesive cluster into a new module that imports its low-level deps *one-directionally* (no cycle), then re-export from the package `__init__.py` so the public API is unchanged.

If `make install`-style symlinking enumerates lib files explicitly, switch it to a `lib/*.sh` loop so new split-out modules are picked up automatically.

## lefthook job

```yaml
pre-commit:
  commands:
    line-limit:
      glob: "{bin/*,lib/*.sh,src/**/*.ts,**/*.py}"   # match is_source()
      run: bash scripts/check-line-limit.sh {staged_files}
```

## CI

**GitHub** — `.github/workflows/line-limit.yml`:

```yaml
name: Line limit
on:
  push: { branches: [main, dev] }
  pull_request: { branches: [main, dev] }
jobs:
  line-limit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
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

## Gotchas

- **Tune the threshold deliberately** — too low forces artificial splits that hurt cohesion (a blunt cap can fragment a genuinely cohesive module). When you raise the limit for a repo, log *why*.
- **Exclude generated + fixtures**, or the check fights `docs-gen` output, big test fixtures, and vendored code.
- A hard cap is a guardrail, not a design principle — split along real seams (cohesive function clusters), not at the arbitrary line where the counter trips.
- The lefthook job only sees *staged* files; CI scans the whole tree — so a pre-existing over-limit file is caught by CI even if you didn't touch it.
