---
tool: doc-budgets
scope: universal
tier: optional
summary: "Ratcheting byte ceilings for standing docs like AGENTS.md"
targets: ["scripts/check-doc-budgets.sh", "doc-budgets.json"]
detect: ["AGENTS.md"]
---

# Standing Doc Budgets

## What

A ratcheting byte-size check (`scripts/check-doc-budgets.sh` + `doc-budgets.json`) that fails CI and pre-commit hooks when standing instruction files like `AGENTS.md` or `CLAUDE.md` grow past their ceiling.

## Why

- Standing docs accumulate one-off rules until they bloat agent context windows and dilute signal.
- A hard byte cap forces every new rule onto the corrections ladder: enforce it in a linter, type, or test, or move step-by-step procedures into an on-demand skill, instead of appending prose.
- Ratchet-down ceilings prevent silent creep while allowing intentional reductions.

## Config

`doc-budgets.json`:

```json
{
  "AGENTS.md": 12000
}
```

`scripts/check-doc-budgets.sh`:

```bash
#!/bin/bash
set -euo pipefail

python3 -B - <<'PY'
import json
import os
import sys

with open("doc-budgets.json", encoding="utf-8") as fh:
    budgets = json.load(fh)

failed = False
for path, cap in sorted(budgets.items()):
    if not os.path.exists(path):
        print(f"DOC BUDGET: missing {path} listed in doc-budgets.json", file=sys.stderr)
        failed = True
        continue
    size = os.path.getsize(path)
    if size > cap:
        print(
            f"DOC BUDGET: {path} is {size} bytes (max {cap}); "
            "move enforceable rules into linters/types or procedures into skills "
            "instead of growing prose",
            file=sys.stderr,
        )
        failed = True

if failed:
    sys.exit(1)
print(f"doc-budgets OK: {len(budgets)} file(s) checked")
PY
```

## Makefile

```makefile
doc-budgets:
	@bash scripts/check-doc-budgets.sh
```

## Lefthook

```yaml
pre-commit:
  commands:
    doc-budgets:
      glob: "{AGENTS.md,doc-budgets.json}"
      run: bash scripts/check-doc-budgets.sh
```

## Gotchas

- Use `python3 -B` + `os.path.getsize` rather than `wc -c` or `stat` so byte counts and flags behave identically on macOS and Linux.
- Lower the cap in `doc-budgets.json` whenever you trim a doc so the ceiling ratchets down over time.
