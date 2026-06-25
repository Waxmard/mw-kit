---
tool: line-limit
scope: universal
tier: optional
summary: "Per-file line cap as a deliberate sprawl proxy — CI-gated script, optional local hook"
targets: ["scripts/check-line-limit.sh"]
---

# Per-File Line Limit

## What

A small portable-bash script fails the build when any hand-written source file
exceeds a per-file line cap (**default 500**). **CI is the gate** — a full-tree
scan that can't be bypassed. A local pre-commit hook is *optional* fast feedback,
not enforcement (any git hook is skippable with `--no-verify`).

It's a deliberate, blunt proxy for **module sprawl** — one file quietly
accumulating too many unrelated responsibilities.

## Why

- Forces decomposition before a file becomes a 1,500-line grab-bag nobody wants to touch.
- The cap is a forcing function: when CI goes red you split the file into focused modules — the cheap moment to do it, not six months later.
- Language-agnostic and dependency-free: one threshold across shell, Python, Go, TS, Makefiles, config. Just `wc -l` + git, so it works in repos with no linter at all.

## Why line count

Sprawl has no clean lint rule — cohesion metrics (LCOM/`cohesion`, Radon MI, Debtmap) are all class-scoped, single-language, or need git/coverage data, and none touches shell/Makefiles/config. Line count is the only file-level, all-language, zero-data proxy. It's orthogonal to *internal* complexity (long/branchy functions), which ruff (`C901`, `PLR091x`) and biome cover well — use both.

## When to use it / when not

- **Use** on repos you actively maintain and want to keep modular. Deliberate and opinionated — hence `optional` tier, not baseline.
- The threshold is a preference, **tune per repo** (default 500; a doc-heavy or generated-heavy repo may want higher, a tight library lower).
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
# Override the cap with LINE_LIMIT (default 500).
set -euo pipefail

LIMIT="${LINE_LIMIT:-500}"

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

## CI — the gate

This is the real enforcement: a full-tree scan that catches a pre-existing
over-limit file even if the current change didn't touch it, and can't be skipped
the way a local hook can.

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

## Optional: local pre-commit feedback

A latency optimization, not the gate — surface an over-limit file before it
reaches CI. Any hook runner can call the script on staged files. If you use
[lefthook](lefthook.md) (the playbook baseline):

```yaml
pre-commit:
  commands:
    line-limit:
      # Slashless glob → matches these extensions at any depth; is_source() in
      # the script does the real path filtering. Avoid a `src/**/*.ext` path
      # glob — it silently misses files directly under src/. See the lefthook
      # page's glob-semantics gotcha.
      glob: "*.{ts,tsx,vue,py,sh}"
      run: bash scripts/check-line-limit.sh {staged_files}
```

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

## Gotchas

- **Tune the threshold deliberately** — too low forces artificial splits that hurt cohesion (a blunt cap can fragment a genuinely cohesive module). When you raise the limit for a repo, log *why*.
- **It's a sprawl proxy, not a complexity check** — for internal complexity (long/branchy functions) lean on ruff `C901`/`PLR091x` and biome complexity rules instead; this script is orthogonal to those.
- **Exclude generated + fixtures**, or the check fights `docs-gen` output, big test fixtures, and vendored code.
- A hard cap is a guardrail, not a design principle — split along real seams (cohesive function clusters), not at the arbitrary line where the counter trips.
- A local pre-commit hook only sees *staged* files and is skippable; CI scans the whole tree and isn't — CI is the gate, the hook is just early warning.
