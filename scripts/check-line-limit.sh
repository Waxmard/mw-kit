#!/bin/bash
# check-line-limit.sh - fail if any hand-written source file exceeds the limit.
#
# Usage:
#   scripts/check-line-limit.sh            # scan the repo source set (CI)
#   scripts/check-line-limit.sh FILE...    # check only the given files (local hook)
#
# Override the caps with LINE_LIMIT (default 800) and TEST_LINE_LIMIT (default 1500).
set -euo pipefail

LIMIT="${LINE_LIMIT:-800}"
TEST_LIMIT="${TEST_LINE_LIMIT:-1500}"

# Folders this check never governs, even when the file matches the source set.
# Substring match, so 'src/data/' skips everything beneath it.
EXCLUDE_DIRS=(
  '/fixtures/'      # test data
)

# Is PATH one of the source files this check governs? Adjust per repo — list the
# hand-written source dirs/extensions. Exclusions go in EXCLUDE_DIRS above.
is_source() {
  local f="$1" ex
  case "$f" in
    scripts/*.py | scripts/*.sh | tests/*.py) ;;
    *) return 1 ;;
  esac
  for ex in ${EXCLUDE_DIRS[@]+"${EXCLUDE_DIRS[@]}"}; do
    [[ "$f" == *"$ex"* ]] && return 1
  done
  return 0
}
is_test() {
  case "$1" in
    tests/* | */tests/* | __tests__/* | */__tests__/* | e2e/* | */e2e/* | test_* | */test_* | *_test.* | *.test.* | *.spec.*) return 0 ;;
    *) return 1 ;;
  esac
}

files=()
if [[ $# -gt 0 ]]; then
  for f in "$@"; do
    f="${f#./}"
    is_source "$f" && [[ -f "$f" ]] && files+=("$f")
  done
else
  while IFS= read -r f; do is_source "$f" && [[ -f "$f" ]] && files+=("$f"); done < <(git ls-files)
fi

status=0
checked=0
for f in "${files[@]:-}"; do
  [[ -z "$f" ]] && continue
  checked=$((checked + 1))
  if is_test "$f"; then cap="$TEST_LIMIT"; else cap="$LIMIT"; fi
  n=$(wc -l <"$f")
  if ((n > cap)); then
    printf 'LINE LIMIT: %s has %d lines (max %d)\n' "$f" "$n" "$cap" >&2
    status=1
  fi
done

if ((status != 0)); then
  printf '\nSplit the file(s) above into focused modules.\n' >&2
  exit 1
fi
printf 'line-limit OK (<= %d src, <= %d test): %d files checked\n' "$LIMIT" "$TEST_LIMIT" "$checked"
