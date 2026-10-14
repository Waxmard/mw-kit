---
tool: security
scope: universal
tier: baseline
summary: "semgrep (SAST) + trivy fs/image scanning in CI"
targets: [".github/workflows/security.yml", ".gitlab-ci.yml"]
---

# Security Scanning

## What

Three scanners running on every PR + weekly cron, results uploaded as SARIF to GitHub Code Scanning:

1. **semgrep** — SAST against curated rule packs.
2. **trivy fs** — vuln + secret scan of dependencies and the filesystem.
3. **trivy image** — vuln scan of built container images.

## Why

- SARIF integration → findings appear inline on PRs and in the Security tab.
- Cron run catches new CVEs disclosed against unchanged code.

## Workflow

`.github/workflows/security.yml`:

```yaml
name: Security
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 12 * * 1'
permissions:
  actions: read
  contents: read
  security-events: write
jobs:
  semgrep:
    runs-on: ubuntu-latest
    container:
      image: semgrep/semgrep:X.Y.Z # pin to latest stable; renovate bumps it
    steps:
      - uses: actions/checkout@v7
      - run: git config --global --add safe.directory "$GITHUB_WORKSPACE"
      - run: semgrep ci --sarif --output=semgrep.sarif --exclude-rule=yaml.github-actions.security.github-actions-mutable-action-tag.github-actions-mutable-action-tag
        env:
          SEMGREP_RULES: >-
            p/python
            p/typescript
            p/react
            p/security-audit
            p/secrets
            p/owasp-top-ten
            p/dockerfile
      - uses: github/codeql-action/upload-sarif@v4
        if: always()
        with:
          sarif_file: semgrep.sarif
          category: semgrep
  trivy-fs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25 # v0.36.0
        env:
          TRIVY_INCLUDE_DEV_DEPS: 'true'
        with:
          scan-type: fs
          scan-ref: .
          format: sarif
          output: trivy-fs.sarif
          severity: CRITICAL,HIGH,MEDIUM
          ignore-unfixed: true
      - uses: github/codeql-action/upload-sarif@v4
        if: always()
        with:
          sarif_file: trivy-fs.sarif
          category: trivy-fs
  trivy-image:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - run: docker build -t app:ci .
      - uses: aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25 # v0.36.0
        with:
          scan-type: image
          image-ref: app:ci
          format: sarif
          output: trivy-image.sarif
          severity: CRITICAL,HIGH,MEDIUM
          ignore-unfixed: true
      - uses: github/codeql-action/upload-sarif@v4
        if: always()
        with:
          sarif_file: trivy-image.sarif
          category: trivy-image
```

## GitLab variant

In `.gitlab-ci.yml`, run the scanners as `test`-stage jobs on MRs and the default branch:

```yaml
semgrep-sast:
  stage: test
  image: semgrep/semgrep:X.Y.Z # pin to latest stable; renovate bumps it
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
  script:
    - semgrep scan --error --config p/python --config p/security-audit --config p/secrets --config p/owasp-top-ten .

trivy-fs:
  stage: test
  image:
    name: ghcr.io/aquasecurity/trivy:X.Y.Z # pin to latest stable; renovate bumps it
    entrypoint: [""]
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
  script:
    - trivy fs --scanners vuln,misconfig,secret --exit-code 1 --severity CRITICAL,HIGH --ignore-unfixed --ignorefile .trivyignore.yaml .

trivy-image:
  stage: test
  image:
    name: ghcr.io/aquasecurity/trivy:X.Y.Z # pin to latest stable; renovate bumps it
    entrypoint: [""]
  needs: ["build-image"]
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
  script:
    - trivy image --scanners vuln --exit-code 1 --severity CRITICAL,HIGH --ignore-unfixed --ignorefile .trivyignore.yaml "$IMAGE_TAG"
```

Use `.trivyignore.yaml` with `expired_at` dates (e.g. `id: CVE-YYYY-NNNN` + `expired_at: 2026-06-01`) so temporary suppressions re-alert automatically if unaddressed.

## Gotchas

- Keep only the semgrep packs matching the repo's languages (`p/react` for frontends, `p/dockerfile` if you ship images). Skipped on purpose: `p/default` — noisy, overlaps the rest.
- `ignore-unfixed: true` on trivy — there's nothing you can do about an unfixed CVE except wait, so don't gate PRs on it.
- `TRIVY_INCLUDE_DEV_DEPS: 'true'` keeps npm/yarn/Gradle application dependencies
  visible when they live under development dependency classifications. Without it,
  an app with every package in `devDependencies` produces an empty vulnerability scan.
- `severity: CRITICAL,HIGH,MEDIUM` — drop MEDIUM if signal-to-noise hurts.
- Semgrep container pin (`semgrep/semgrep:X.Y.Z`) gives reproducible scans — pin to a real version, don't run `:latest`. Renovate bumps it.
- `if: always()` on SARIF upload so a scan failure still uploads partial results.
- `--exclude-rule=…github-actions-mutable-action-tag` — semgrep otherwise blocks on every `uses: …@vN` tag, including this workflow's own. Major-tag pins are deliberate policy here (Dependabot bumps them); SHA pinning isn't worth the churn — except `trivy-action`, which is SHA-pinned because its tags were force-pushed to malware on 2026-03-19 (GHSA-69fq-xp46-6x23). Dependabot still bumps the SHA + version comment.
- `actions: read` is required by `upload-sarif` on **private** repos (it reads the workflow run); without it the upload fails with `Resource not accessible by integration`.
- **Code scanning needs a public repo or GitHub Advanced Security.** On a private repo without GHAS, every upload fails with `Code scanning is not enabled`. Either make the repo public, or drop the `upload-sarif` steps and gate on exit codes: `semgrep ci` (no `--sarif`) already exits 1 on blocking findings; give trivy `format: table` + `exit-code: '1'`. Findings then live in job logs, not the Security tab.
