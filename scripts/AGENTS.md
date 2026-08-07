# scripts/

`scope.py` is the deterministic pre-flight + scope half of the `tooling-sync`
skill: given a consumer repo path it validates the repo, detects platform +
project structure, globs each page's `detect` patterns, resolves the baseline
alternatives (dependabot/renovate, release tool), and reports which `targets`
exist — emitting a JSON plan the skill consumes. It reads page frontmatter
directly (reusing `parse_frontmatter` from `build_manifest.py`), so the two never
disagree. It deliberately does **not** read config contents or judge drift — that
stays in the skill. Edit it when a scoping rule changes (new alternative, new
scope dir, changed monorepo heuristic).

It also powers **incremental sync**: it reads the consumer repo's committed
`.tooling-sync.json` (per-tool decisions + the mw-kit commit each was made at,
written by the skill in its Step 6) and annotates each in-scope row with the
recalled decision plus whether that page has changed in mw-kit since — via
`git log <decided-commit>..HEAD -- playbook/<page>`. Rows whose decision still
holds come back `settled: true`, so the skill skips re-comparing them (declines
stay quiet until their page moves). `--no-state` forces a full re-compare. The
script only *reads* the state file; the skill owns *writing* it.
