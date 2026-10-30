---
tool: renovate
scope: universal
tier: baseline
summary: "Platform-agnostic dependency update bot (required on GitLab)"
targets: ["renovate.json"]
---

# renovate

## What

Platform-agnostic dep update bot. Opens MRs/PRs to bump outdated deps across npm, pip/uv, Docker base images, GitHub Actions, GitLab CI `include:`, Helm, Terraform, mise/asdf, pre-commit, and dozens more ecosystems.

## Why

- **Works on GitLab.** Dependabot doesn't (without third-party shims). Repo on GitLab → use renovate.
- **More ecosystems than dependabot.** Helm charts, Dockerfile `FROM`, docker-compose, GitLab CI `include:`, pre-commit hooks, mise/asdf tool versions — all out of the box.

## Config

### Minimal baseline — every repo starts here

`renovate.json` at repo root:

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:recommended"],
  "prConcurrentLimit": 5,
  "minimumReleaseAge": "3 days",
  "internalChecksFilter": "strict",
  "packageRules": [
    { "matchUpdateTypes": ["major"], "prPriority": -5 }
  ]
}
```

Baseline: one MR/PR per dependency upgrade, at most 5 open at once across the repo. Minor and patch MRs/PRs share the default priority; `prPriority: -5` makes majors wait until no minor/patch upgrade is pending, so when slots are full the non-major upgrades open first. Updates beyond the cap wait as rate-limited on the dependency dashboard. `config:recommended` still groups packages released together (`group:monorepos`, `group:recommended`, e.g. all `@angular/*`), which counts as one upgrade. Everything below is **per-repo opt-in**.

`minimumReleaseAge: "3 days"` holds a release back for three days before opening any MR — a supply-chain buffer so a compromised or broken version gets yanked/fixed before it can land. `internalChecksFilter: "strict"` suppresses the pending-stability MRs while they age (no half-baked branches). **Vulnerability remediation bypasses the age automatically**, so security fixes are not delayed. Aligns with [security](./security.md).

### Patterns (pick what fits the repo)

Treat these as snippets to drop into `packageRules`. **Do not paste all of them** — each adds noise unless that repo actually has those deps.

**Group coupled ecosystems** — when multiple deps move in lockstep, one grouped MR beats five separate ones:

```json
{
  "matchPackagePrefixes": ["@some-ecosystem/"],
  "groupName": "Some Ecosystem"
}
```

Good fits: framework + its types (`react` + `@types/react`), UI lib families, lint plugin families. Bad fits: random unrelated deps — a failing group blocks the whole batch.

**Pin major version** — block premature upgrades to a major you can't take yet:

```json
{
  "matchPackageNames": ["some-lib"],
  "allowedVersions": "^2"
}
```

Use when the next major has a known breaking change you've deferred. Remove the pin when you're ready.

**Automerge low-risk dev bumps** — only enable if CI is trusted to catch regressions:

```json
{
  "matchDepTypes": ["devDependencies", "dependency-groups"],
  "matchUpdateTypes": ["patch", "minor"],
  "automerge": true
}
```

Never automerge production deps. Never automerge `major`.

**GitLab CI components (`include: component:`)** — Renovate's built-in `gitlabci` manager cannot resolve `$CI_SERVER_FQDN` on `include: component:` lines and logs a package lookup failure. Repos that include internal components add a top-level `customManagers` regex rule that queries the GitLab host's tags directly and a `packageRules` entry that disables the broken native lookup:

```json
"customManagers": [
  {
    "customType": "regex",
    "description": "Update GitLab CI components referenced via include: component: ...@X.Y.Z",
    "managerFilePatterns": ["/\\.gitlab-ci\\.ya?ml$/"],
    "matchStrings": [
      "component: \"?(?:\\$CI_SERVER_FQDN|gitlab\\.example\\.com)/(?<depName>.+)/(?<componentName>[^/]+?)@(?<currentValue>[^\\s\"]+)\"?"
    ],
    "datasourceTemplate": "gitlab-tags",
    "versioningTemplate": "semver-coerced",
    "registryUrlTemplate": "https://gitlab.example.com"
  }
]
```

Add to `packageRules`:

```json
{
  "description": "Disable native gitlabci lookup for $CI_SERVER_FQDN components (handled by customManagers)",
  "matchManagers": ["gitlabci"],
  "matchPackageNames": ["/^my-group//", "/^shared-ci//"],
  "enabled": false
}
```

### GitLab self-hosted runner (`.gitlab-ci.yml`)

Renovate on GitLab is a scheduled CI job, not a managed app. Add a scheduled pipeline (Settings → CI/CD → Schedules, e.g. nightly) that runs:

```yaml
renovate:
  stage: maintenance
  image: renovate/renovate:X.Y.Z # pin to latest stable; renovate bumps it
  rules:
    - if: '$CI_PIPELINE_SOURCE == "schedule" && $RENOVATE == "true"'
  variables:
    LOG_LEVEL: info
    RENOVATE_PLATFORM: gitlab
    RENOVATE_ENDPOINT: $CI_API_V4_URL
    RENOVATE_TOKEN: $RENOVATE_BOT_TOKEN
    RENOVATE_AUTODISCOVER: "true"
  script:
    - renovate
```

`RENOVATE_BOT_TOKEN` = GitLab personal access token (api scope) of a bot user. Set as masked CI variable.

### GitHub (native app)

Install the [Renovate GitHub App](https://github.com/apps/renovate) on the org. No CI job needed — config is just `renovate.json`.

## Gotchas

- **`prConcurrentLimit` is global, not per-update-type.** It caps all open Renovate MRs/PRs in the repo; there is no per-type limit. `prPriority` decides which pending upgrades take a free slot, so majors (`-5`) trickle in behind minor/patch. A `groupName` rule (Patterns below) collapses its members into one slot.
- Leave `prHourlyLimit` unset (default 0 = off).
- **Don't re-impose the age on vulns.** `minimumReleaseAge` is bypassed by Renovate's vulnerability remediation by default — leave it that way. Adding a custom `vulnerabilityAlerts` block that re-applies the age delays security fixes by three days. Don't.
- **Major-pin without a calendar reminder rots.** When you write `"allowedVersions": "^2"`, leave a comment or issue saying when to revisit — otherwise you sit on stale majors forever.
- **Automerge needs real test coverage.** A green pipeline with low coverage is not "trusted CI." Start with devDeps patch only; expand later.
- **Renovate covers tool versions too** ([mise](./mise.md) `.mise.toml`, pre-commit hooks) — unlike dependabot. One bot for deps + tools + CI + Dockerfiles.
- **Renovate commits as `chore(deps):`** when the repo uses semantic commits. `chore` doesn't release in this playbook's release configs, so bumps ship with the next `feat`/`fix` release.
- **Not a replacement for [security](./security.md).** Renovate bumps versions; trivy/semgrep find vulns. Run both.
- **Use the `customManagers` snippet above for `include: component: $CI_SERVER_FQDN/...` refs** — never silence native `gitlabci` lookup warnings with `ignoreDeps`. If a component project lives in a group the Renovate runner cannot read, grant the Renovate runner project read access on the component project under **Settings → CI/CD → Job token permissions** (`Fine-grained permissions` → `Repositories: Read`).
