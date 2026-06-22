---
tool: yamllint
scope: k8s
tier: baseline
summary: "Lint all YAML for syntax/style, tuned for kubectl-style manifests"
targets: [".yamllint"]
detect_content: ["^kind:\\s"]
platform: any
---

# yamllint

## What

[yamllint](https://www.yamllint.com/) checks every YAML file for syntax errors and
style problems — duplicate keys, tabs, bad indentation, trailing whitespace, missing
final newline. In a manifest repo where YAML *is* the product and whitespace is
load-bearing, it's the cheapest gate that catches a whole class of "it parsed but
meant something else" bugs before they reach the cluster. Pairs with
[kubeconform](./kubeconform.md): yamllint checks the YAML is well-formed, kubeconform
checks the resource is schema-valid.

## Why

- **Duplicate keys are silent data loss.** YAML keeps the last value; yamllint is the
  only thing that flags `env:` declared twice in one container.
- **Tabs and trailing whitespace** creep into hand-edited manifests and break block
  scalars or indentation in non-obvious ways. yamllint catches them mechanically.
- **Wired into both pre-commit and CI** — same `.yamllint` config, so commit-time and
  pipeline agree.

## Config

`.yamllint` at repo root. The non-negotiable line is `indent-sequences: consistent` —
without it yamllint's default floods on every Kubernetes manifest (see Gotchas):

```yaml
# Relaxed yamllint config for Kubernetes / Argo CD manifests.
extends: default

rules:
  document-start: disable # k8s manifests routinely omit the leading ---
  indentation:
    spaces: 2
    indent-sequences: consistent # allow the kubectl-style non-indented block lists
  line-length:
    max: 200
    level: warning # long image refs / URLs shouldn't fail the build
  comments:
    min-spaces-from-content: 1
  truthy:
    check-keys: false # allow keys like `on:` without truthy warnings
```

### Pre-commit hook

Add to `.pre-commit-config.yaml`:

```yaml
  - repo: https://github.com/adrienverge/yamllint
    rev: vX.Y.Z # pin to latest stable; renovate's pre-commit manager bumps it
    hooks:
      - id: yamllint
        args: ["-c", ".yamllint"]
```

### CI job (GitLab)

```yaml
yaml-lint:
  stage: lint
  image: python:3.14-slim
  rules:
    - changes: ["**/*.yaml", "**/*.yml", ".yamllint"]
  script:
    - pip install --no-cache-dir yamllint==X.Y.Z # match the pre-commit rev; renovate bumps it
    - yamllint -c .yamllint .
```

On GitHub, run `pip install yamllint && yamllint -c .yamllint .` in a workflow step.

## Gotchas

- **`indent-sequences: consistent` is mandatory for k8s.** Manifests use the kubectl
  style where a block sequence sits at the *same* indent as its parent key:

  ```yaml
  spec:
    rules:
    - matches: ...     # '-' at col 2, NOT col 4
  ```

  yamllint's `default` profile expects sequences indented two further spaces and will
  report `wrong indentation: expected 4 but found 2` on essentially every file.
  `consistent` accepts either style as long as a file doesn't mix them — so it still
  catches the genuine within-file inconsistency (one list indented, another not).
- **Adopting on an existing repo floods the first run.** Almost all of it is the
  sequence-indent style choice above (fixed by config, not edits). After that, expect a
  short tail of *real* issues — a stray tab, trailing spaces, a missing EOF newline.
  Fix those; they're exactly what the tool is for.
- **`line-length` as `warning`, not error.** Image refs (`registry/long/path:sha`) and
  annotation URLs blow past any sane column limit. Warnings don't fail CI (yamllint
  exits non-zero only on errors unless you pass `--strict`), so leave them visible
  without blocking.
- **yamllint lints *all* YAML**, including `.gitlab-ci.yml`, Helm `values.yaml`, and
  config dotfiles — that's desirable (it's syntax, not schema). Only [kubeconform](./kubeconform.md)
  needs to be restricted to actual manifests.
