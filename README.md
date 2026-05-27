# mw-kit

My tooling preferences for new projects. Narrative docs explaining each choice and *why*.

## Layout

```
playbook/        # tooling preferences, scoped
  universal/     # applies to every project
  python/        # python-specific
  node/          # node/typescript-specific
  monorepo/      # monorepo-specific (docker bake, multi-package)
```

## Tooling at a glance

| Concern | Choice |
|---|---|
| Tool versions | [mise](https://mise.jdx.dev/) |
| Git hooks | [lefthook](https://lefthook.dev/) (autofix + restage) |
| Python lint/format | [ruff](https://docs.astral.sh/ruff/) |
| Python typecheck | [mypy](https://mypy.readthedocs.io/) strict |
| Python deps | [uv](https://docs.astral.sh/uv/) |
| Python module boundaries | [tach](https://docs.gauge.sh/) |
| JS/TS lint/format | [biome](https://biomejs.dev/) |
| Releases (GitHub) | [release-please](https://github.com/googleapis/release-please) |
| Releases (GitLab) | semantic-release |
| Dep updates (GitHub) | [dependabot](https://docs.github.com/en/code-security/dependabot) |
| Dep updates (GitLab) | [renovate](https://docs.renovatebot.com/) |
| SAST | semgrep |
| Vuln scanning | trivy (fs + image) |
| Multi-arch builds | docker bake |
| Docs generation | python script with `{{ include:partials/X.md }}` directives |

## Conventions

- Each tool gets its own page under the right `playbook/<scope>/` folder.
- Each page: **What**, **Why**, **Config**, **Gotchas**.
