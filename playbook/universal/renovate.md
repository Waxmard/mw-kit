---
tool: renovate
scope: universal
tier: baseline
summary: "Platform-agnostic dependency update bot (required on GitLab)"
targets: ["renovate.json"]
---

# renovate

## What

Platform-agnostic dep update bot. Opens MRs/PRs to bump outdated deps across npm, pip/uv, Docker base images, GitHub Actions, GitLab CI `include:`, Helm, Terraform, mise/asdf, pre-commit, and dozens more ecosystems. Self-hosted on GitLab via scheduled CI pipeline; native GitHub App on GitHub.

## Why

- **Works on GitLab.** Dependabot doesn't (without third-party shims). Repo on GitLab → use renovate.
- **More ecosystems than dependabot.** Helm charts, Dockerfile `FROM`, docker-compose, GitLab CI `include:`, pre-commit hooks, mise/asdf tool versions — all out of the box.
- **Better grouping & scheduling.** `packageRules` collapse coupled bumps into one MR.
- **Per-rule automerge.** Auto-merge devDeps patch/minor without touching prod deps.
- **`config:recommended` preset** = sane defaults; override only what each repo actually needs.

## Config

### Minimal baseline — every repo starts here

`renovate.json` at repo root:

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:recommended"],
  "prConcurrentLimit": 3,
  "prHourlyLimit": 0,
  "minimumReleaseAge": "7 days",
  "internalChecksFilter": "strict",
  "packageRules": [
    {
      "matchUpdateTypes": ["minor", "patch"],
      "groupName": "minor & patch deps"
    },
    { "matchUpdateTypes": ["major"], "prPriority": -5 }
  ]
}
```

Baseline does the triage work: minor/patch → one grouped MR (any count, 1 slot); majors → individual, never grouped. Since the group eats only 1 of the 3 slots, **at most 2 majors stay open at once** (`prConcurrentLimit − 1`). `prPriority: -5` ensures the group MR opens ahead of majors when slots are full. Everything below is **per-repo opt-in**.

`minimumReleaseAge: "7 days"` holds a release back for a week before opening any MR — a supply-chain buffer so a compromised or broken version gets yanked/fixed before it can land. `internalChecksFilter: "strict"` suppresses the pending-stability MRs while they age (no half-baked branches). **Vulnerability remediation bypasses the age automatically**, so security fixes are not delayed. Aligns with [[security]].

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
  "matchDepTypes": ["devDependencies"],
  "matchUpdateTypes": ["patch", "minor"],
  "automerge": true
}
```

Never automerge production deps. Never automerge `major`.

### GitLab self-hosted runner (`.gitlab-ci.yml`)

Renovate on GitLab is a scheduled CI job, not a managed app. Add a scheduled pipeline (Settings → CI/CD → Schedules, e.g. nightly) that runs:

```yaml
renovate:
  stage: maintenance
  image: renovate/renovate:latest
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

- **`prConcurrentLimit` is global, not per-update-type.** It's enforced per-repo across all branches at once — you **cannot** cap "majors to 1–2 concurrent" with it. To make majors trickle while minors flow, use `prPriority` (deprioritize majors) + grouping (collapse minors), not a per-type limit that doesn't exist. The trick: grouping collapses all minor/patch into 1 slot, so **concurrent majors = `prConcurrentLimit − 1`**. Baseline `3` → 1 group MR + at most 2 majors. Want fewer/more majors → adjust this one number.
- **`prHourlyLimit` is PRs created *per hour per run* — leave it `0` (off).** On a frequent runner (GitHub app) it only smooths bursts; on an infrequent one (GitLab nightly/weekly CI) it **throttles you to N PRs per run**, silently overriding `prConcurrentLimit`. Grouping already shrinks the per-run burst and `prConcurrentLimit` caps the onboarding flood, so the hourly limit just adds a footgun.
- **Don't re-impose the age on vulns.** `minimumReleaseAge` is bypassed by Renovate's vulnerability remediation by default — leave it that way. Adding a custom `vulnerabilityAlerts` block that re-applies the age delays security fixes by a week. Don't.
- **Don't over-group.** One giant MR that fails CI blocks every dep in the group. Group only deps that genuinely move together.
- **Major-pin without a calendar reminder rots.** When you write `"allowedVersions": "^2"`, leave a comment or issue saying when to revisit — otherwise you sit on stale majors forever.
- **Automerge needs real test coverage.** A green pipeline with low coverage is not "trusted CI." Start with devDeps patch only; expand later.
- **Renovate covers tool versions too** ([[mise]] `.mise.toml`, pre-commit hooks) — unlike dependabot. One bot for deps + tools + CI + Dockerfiles.
- **Pair with [[releases-gitlab]] / [[releases-github]].** Renovate commits use `chore(deps):` by default → semantic-release / release-please hide them from changelogs automatically. Aligns with [[conventional-commits]].
- **Not a replacement for [[security]].** Renovate bumps versions; trivy/semgrep find vulns. Run both.
