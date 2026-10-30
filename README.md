# mw-kit

My tooling choices for new projects: one page per tool with the reason and the
canonical config, plus the resolver that the
[`tooling-sync`](https://github.com/Waxmard/skills) skill runs against a repo.

```text
playbook/<scope>/<tool>.md ──build_manifest.py──▶ playbook/MANIFEST.md
           │
           └──▶ scope.py <repo> ──▶ JSON scope plan ──▶ tooling-sync ──▶ diffs and edits in <repo>
```

## Run

```sh
make setup                                    # uv sync
python3 scripts/scope.py ~/code/some-repo     # JSON: which pages apply, which targets exist
python3 scripts/scope.py --no-state .         # same, ignoring .tooling-sync.json decisions
make manifest                                 # regenerate MANIFEST.md after editing frontmatter
make ci                                       # lint, typecheck, tests
```

## Layout

```text
playbook/            one page per tool, by scope
  MANIFEST.md        generated index: tool, scope, tier, targets, detect globs
  universal/         every project
  python/ node/      language-specific
  k8s/               kubernetes manifest repos, detected by `kind:` in YAML
  monorepo/          docker bake, multi-package layout
scripts/
  build_manifest.py  regenerates MANIFEST.md from page frontmatter
  scope.py           the deterministic half of tooling-sync
tests/               pytest for scope.py
```

## Tooling at a glance

See the [playbook manifest](playbook/MANIFEST.md) for tool choices, applicability, and configuration pages.

## Page format

- Each tool gets one page under `playbook/<scope>/`.
- Frontmatter: `tool`, `scope`, `tier` (`baseline` or `optional`), `summary`,
  `targets`, `detect` and/or `detect_content`, and optional `platform`.
  `detect_content` matches regexes against YAML bodies, for repos with no path
  marker (k8s keys on `^kind:`). A page with neither applies to every repo in
  its scope.
- Body: **What**, **Why**, **Config**, **Gotchas**. `## Config` is what
  tooling-sync diffs a repo against.
