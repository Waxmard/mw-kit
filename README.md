# mw-kit

My tooling preferences for new projects. Narrative docs explaining each choice and *why*.

## Layout

```
playbook/        # tooling preferences, scoped
  MANIFEST.md    # generated index: tool → scope, tier, target files, detect globs
  universal/     # applies to every project
  python/        # python-specific
  node/          # node/typescript-specific
  k8s/           # kubernetes-manifest / gitops repos (content-detected on `kind:`)
  monorepo/      # monorepo-specific (docker bake, multi-package)
scripts/
  build_manifest.py  # regenerates playbook/MANIFEST.md from page frontmatter
skills/            # Claude Code skills (symlinked into ~/.claude/skills)
  tooling-sync/    # diff a repo against the playbook, apply chosen updates
  comment-audit/   # scc pre-flight + LLM pass to find/remove redundant comments
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
| YAML lint (k8s) | [yamllint](https://www.yamllint.com/) (kubectl-style config) |
| K8s manifest validation | [kubeconform](https://github.com/yannh/kubeconform) (schema + CRD catalog, CI) |
| Releases (GitHub) | [release-please](https://github.com/googleapis/release-please) |
| Releases (GitLab) | semantic-release |
| CI (single project) | GitHub: `ci.yml` runs `make ci` · GitLab: `.gitlab-ci.yml` test stage |
| GitLab CI dedup | `workflow:rules` (one pipeline per change, build-on-MR) |
| Dep updates (GitHub) | [dependabot](https://docs.github.com/en/code-security/dependabot) |
| Dep updates (GitLab) | [renovate](https://docs.renovatebot.com/) |
| SAST | semgrep |
| Vuln scanning | trivy (fs + image) |
| AI PR review (GitHub) | [claude-code-action](https://github.com/anthropics/claude-code-action) + `code-review` plugin |
| Multi-arch builds | docker bake |
| Docs generation | python script with `{{ include:partials/X.md }}` directives |
| Per-file size cap | line-limit script (CI gate, optional local hook), default 500 lines |
| Contribution flow | `CONTRIBUTING.md` — branching, commits, MR/PR + bot-then-human review |
| Required reviewers | `CODEOWNERS` — path → owner, gates the human approval |
| Commit/PR AI guidance | `.git-ai-instructions` — repo user-POV for [git-ai](https://github.com/Waxmard/git-ai) prefixing |

## Skills

Claude Code skills sourced here and symlinked into `~/.claude/skills`:

| Skill | What it does |
|---|---|
| [tooling-sync](skills/tooling-sync/) | Diffs the current repo against the playbook and applies chosen updates — merging, never clobbering. Driven by `playbook/MANIFEST.md`. |
| [comment-audit](skills/comment-audit/) | Ranks code files by comment density/volume with an [`scc`](https://github.com/boyter/scc) pre-flight, then judges each comment (cut/keep/rewrite) one file at a time, applying edits only on per-file approval. |

## Conventions

- Each tool gets its own page under the right `playbook/<scope>/` folder.
- Each page opens with YAML frontmatter (`tool`, `scope`, `tier`, `summary`, `targets`, `detect` and/or `detect_content`, optional `platform`) — the machine-readable index source. `detect_content` matches regexes against YAML bodies, for repo classes with no path marker (e.g. k8s keyed on `^kind:`).
- Each page body: **What**, **Why**, **Config**, **Gotchas**. The `## Config` block is the canonical config to diff a consumer repo against.
- `playbook/MANIFEST.md` is generated from frontmatter — run `python3 scripts/build_manifest.py` after editing any frontmatter. Don't hand-edit it.
