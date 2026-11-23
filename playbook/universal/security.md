---
tool: security
scope: universal
tier: baseline
summary: "semgrep (SAST) + trivy fs/image scanning in CI"
targets: [".github/workflows/security.yml", ".trivyignore.yaml"]
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

## Config

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
      image: semgrep/semgrep:X.Y.Z # pin to latest stable
    steps:
      - uses: actions/checkout@v7
      - run: git config --global --add safe.directory "$GITHUB_WORKSPACE"
      - run: semgrep ci --sarif --output=semgrep.sarif --exclude-rule=yaml.github-actions.security.github-actions-mutable-action-tag.github-actions-mutable-action-tag
        env:
          SEMGREP_RULES: >-
            p/python
            p/typescript
            p/react
            p/secrets
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

### Ignoring CVEs (`.trivyignore.yaml`)

`.trivyignore.yaml`:

```yaml
vulnerabilities: []
```

Trivy auto-detects `.trivyignore.yaml` at the scan root. Use `.trivyignore.yaml` with `expired_at` dates (e.g. `id: CVE-YYYY-NNNN` + `expired_at: YYYY-MM-DD`) so temporary suppressions re-alert automatically if unaddressed.

## Gotchas

- Add one pack per repo language (`p/typescript` for TS, `p/react` for frontends, `p/dockerfile` if you ship images). Leave out `p/security-audit`, `p/owasp-top-ten` and `p/default`: their config-hygiene rules (e.g. dependabot `cooldown`) fail PRs on things that aren't vulnerabilities.
- `ignore-unfixed: true` on trivy — there's nothing you can do about an unfixed CVE except wait, so don't gate PRs on it.
- `TRIVY_INCLUDE_DEV_DEPS: 'true'` keeps npm/yarn/Gradle application dependencies
  visible when they live under development dependency classifications. Without it,
  an app with every package in `devDependencies` produces an empty vulnerability scan.
- `severity: CRITICAL,HIGH,MEDIUM` — drop MEDIUM if signal-to-noise hurts.
- Semgrep container pin (`semgrep/semgrep:X.Y.Z`) gives reproducible scans — pin to a real version, don't run `:latest`.
- `if: always()` on SARIF upload so a scan failure still uploads partial results.
- `--exclude-rule=…github-actions-mutable-action-tag` — semgrep otherwise blocks on every `uses: …@vN` tag, including this workflow's own. Major-tag pins are deliberate policy here (Dependabot bumps them); SHA pinning isn't worth the churn — except `trivy-action`, which is SHA-pinned because its tags were force-pushed to malware on 2026-03-19 (GHSA-69fq-xp46-6x23). Dependabot still bumps the SHA + version comment.
- `actions: read` is required by `upload-sarif` on **private** repos (it reads the workflow run); without it the upload fails with `Resource not accessible by integration`.
- **Code scanning needs a public repo or GitHub Advanced Security.** On a private repo without GHAS, every upload fails with `Code scanning is not enabled`. Either make the repo public, or drop the `upload-sarif` steps and gate on exit codes: `semgrep ci` (no `--sarif`) already exits 1 on blocking findings; give trivy `format: table` + `exit-code: '1'`. Findings then live in job logs, not the Security tab.
- **Kubernetes / Kustomize GitOps repos: set `scanners: vuln,secret` (drop `misconfig`) on `trivy-fs`.** Trivy's raw-file `misconfig` scanner false-positives on Kustomize strategic-merge patches (partial `Deployment` fragments are flagged for default security contexts such as `KSV-0118`) and floods on vendored upstream operator manifests (Argo CD, cert-manager, ESO ClusterRoles). Dropping `misconfig` keeps `trivy-fs` scanning for leaked secrets and vulnerable dependencies without silencing rules repo-wide in `.trivyignore.yaml`. If you want K8s policy checks, run them against `rendered/` manifests (e.g. a non-blocking policy job) rather than raw overlay patches.
- **Omit `trivy-image`** in repos that do not build container images.
