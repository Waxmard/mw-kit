---
tool: releases-python
scope: python
tier: baseline
summary: "python-semantic-release: tag + changelog for Python repos on GitLab (no node)"
targets: ["pyproject.toml", ".gitlab-ci.yml"]
detect: ["pyproject.toml", "**/*.py"]
platform: gitlab
---

# Releases for Python repos: python-semantic-release

## What

[python-semantic-release](https://python-semantic-release.readthedocs.io/) (PSR) cuts tags, bumps `pyproject.toml [project].version`, updates `CHANGELOG.md`, and creates a GitLab Release on every push to `main`, driven by Conventional Commits.

## Why over node semantic-release

[[releases-gitlab]] works, but drags `node:22` + five npm plugins into a Python repo just to cut a tag. PSR is one pip install, keeps the version where Python tooling expects it (`[project].version`), and configures in `pyproject.toml` next to ruff/mypy. **Python repo on GitLab → use this page instead of [[releases-gitlab]]; never both.** A multi-component monorepo → [[releases-monorepo]] instead: PSR computes one version per repo and can't path-scope the bump to a single component.

Reference implementations: `partshop/wolfcoder` (origin of this pattern), `data-den/braindump`.

## Config

`pyproject.toml`:

```toml
[project]
name = "myproject"
version = "0.0.0"

[tool.semantic_release]
version_toml = ["pyproject.toml:project.version"]
tag_format = "{version}"
commit_message = "chore(release): {version} [skip ci]"
commit_parser = "conventional"
changelog_file = "CHANGELOG.md"
upload_to_vcs_release = true

[tool.semantic_release.commit_parser_options]
patch_tags = ["fix", "perf", "refactor", "build", "chore", "ci", "style"]

[tool.semantic_release.changelog]
mode = "update"
insertion_flag = "<!-- version list -->"

[tool.semantic_release.remote]
type = "gitlab"
token = { env = "SEMANTIC_RELEASE_TOKEN" }

[tool.semantic_release.branches.main]
match = "main"
```

`patch_tags` **replaces** the parser default (`["fix", "perf"]`) — list every patch-bumping type, hence `fix`/`perf` are repeated. `minor_tags` stays default (`["feat"]`); `allowed_tags` already covers all these types, so no extra config. `docs`/`test` stay non-releasing by omission.

A pip-only repo (no packaging) still works: a tool-config-only `pyproject.toml` just needs the minimal `[project]` table for `version_toml` to point at — it doesn't force a build backend or change installs.

## Pipeline

`.gitlab-ci.yml` (add a `release` stage after deploy):

```yaml
semantic-release:
  stage: release
  image: python:3.12-slim
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
  variables:
    GIT_DEPTH: "0"
  before_script:
    - apt-get update && apt-get install -y --no-install-recommends git
    - pip install python-semantic-release==10.5.3
    - git checkout $CI_DEFAULT_BRANCH
    - git config user.email "release-bot@example.com"
    - git config user.name "Release Bot"
  script:
    - semantic-release version
```

`semantic-release version` does everything: parses commits since the last tag, bumps the version, writes the changelog, commits, tags, pushes, and creates the GitLab Release (`upload_to_vcs_release = true`). On uv repos, replace the pip install with a `dev` dependency-group entry + `uv run semantic-release version`.

## Token

Project access token with `api` + `write_repository` scope, saved as masked `SEMANTIC_RELEASE_TOKEN` CI variable. The bot pushes the release commit to `main` — add it to the protected-branch allowlist.

## Gotchas

- **`GIT_DEPTH: "0"` is required** — PSR needs full history + tags to find the previous release; a shallow clone silently computes the wrong bump.
- **`[skip ci]` in `commit_message` is load-bearing** — without it the release commit triggers another pipeline (and on a careless setup, a release loop).
- **Image tags ≠ release tags — don't build images on the release tag.** `[skip ci]` on the release commit suppresses the tag pipeline, so a tag-triggered image build never fires. Build the image on `main` with a `$CI_COMMIT_SHORT_SHA` tag, then `crane`-retag it to the released version inside (or right after) the release job. See [[releases-monorepo]] for the `crane tag` snippet.
- **`tag_format = "{version}"` means bare tags** (`1.4.0`, no `v` prefix). Fine, but pick once — changing the format later breaks previous-tag detection.
- **First run:** start `version = "0.0.0"`; changelog `mode = "update"` auto-initializes a missing `CHANGELOG.md`, then requires the `<!-- version list -->` insertion flag to stay in the file.
- **`chore(deps)` now releases.** With `chore` in `patch_tags`, Renovate bumps ([[renovate]]) each cut a patch instead of accumulating — more frequent tags than the stock config. Drop `chore` from `patch_tags` to revert to accumulate-until-`feat`/`fix`.
- **Coexists with CI image versioning** (e.g. a `determine-version` component tagging images): PSR versions the repo/changelog; image tags can stay on the pipeline's own scheme. Don't try to unify them in one step.
- Requires [[conventional-commits]] adherence — a `Fix stuff` commit is invisible to the version calculator.
