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

| Concern | Choice |
|---|---|
| Tool versions (node/polyglot) | [mise](https://mise.jdx.dev/) — uv covers pure-python |
| Git hooks | [lefthook](https://lefthook.dev/) (autofix + restage) |
| Python lint/format | [ruff](https://docs.astral.sh/ruff/) |
| Python typecheck | [mypy](https://mypy.readthedocs.io/) strict |
| Python deps | [uv](https://docs.astral.sh/uv/) |
| Python validation/settings | [pydantic](https://docs.pydantic.dev/) v2 + pydantic-settings |
| JS/TS lint/format | [biome](https://biomejs.dev/) |
| Svelte lint/format/typecheck | ESLint + Prettier + `svelte-check` ([playbook](playbook/node/svelte.md)) |
| YAML lint (k8s) | [yamllint](https://www.yamllint.com/) (kubectl-style config) |
| K8s manifest validation | [kubeconform](https://github.com/yannh/kubeconform) (schema + CRD catalog, CI) |
| Releases (GitHub) | [release-please](https://github.com/googleapis/release-please) |
| Releases (GitLab) | semantic-release |
| GitHub repo settings | `gh api` baseline: squash/rebase only, ruleset on default branch, read-only Actions token ([playbook](playbook/universal/github-settings.md)) |
| CI (single project) | GitHub: `ci.yml` runs `make ci` · GitLab: `.gitlab-ci.yml` test stage |
| GitLab CI dedup | `workflow:rules` (one pipeline per change, build-on-MR) |
| Dep updates (GitHub) | [dependabot](https://docs.github.com/en/code-security/dependabot) |
| Dep updates (GitLab) | [renovate](https://docs.renovatebot.com/) |
| SAST | semgrep |
| Vuln scanning | trivy (fs + image) |
| Multi-arch builds | docker bake |
| Agent instructions | `AGENTS.md` (agent-agnostic) as the only instructions file, no `CLAUDE.md` |
| README | One-sentence opener, flow diagram, commands that run ([playbook](playbook/universal/project-readme.md)) |
| Per-file size cap | line-limit script (CI gate, optional local hook), default 800 lines |
| Contribution flow | `CONTRIBUTING.md` — branching, commits, MR/PR + human review |
| Required reviewers | `CODEOWNERS` — path → owner, gates the human approval |
| Commit/PR AI guidance | `.git-ai-instructions` — repo user-POV for [git-ai](https://github.com/Waxmard/git-ai) prefixing |

## Page format

- Each tool gets one page under `playbook/<scope>/`.
- Frontmatter: `tool`, `scope`, `tier` (`baseline` or `optional`), `summary`,
  `targets`, `detect` and/or `detect_content`, and optional `platform`.
  `detect_content` matches regexes against YAML bodies, for repos with no path
  marker (k8s keys on `^kind:`). A page with neither applies to every repo in
  its scope.
- Body: **What**, **Why**, **Config**, **Gotchas**. `## Config` is what
  tooling-sync diffs a repo against.
- `MANIFEST.md` is generated. Run `make manifest` after editing frontmatter;
  never hand-edit it.
