# Security Scanning

## What

Three scanners running on every PR + weekly cron, results uploaded as SARIF to GitHub Code Scanning:

1. **semgrep** — SAST against curated rule packs.
2. **trivy fs** — vuln scan of dependencies + IaC + secrets in the filesystem.
3. **trivy image** — vuln scan of built container images.

## Why

- SARIF integration → findings appear inline on PRs and in the Security tab.
- Semgrep catches code-pattern bugs (injection, unsafe deserialization). Trivy catches CVEs.
- Image scan catches base-image vulns the source scan misses.
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
  contents: read
  security-events: write
jobs:
  semgrep:
    runs-on: ubuntu-latest
    container:
      image: semgrep/semgrep:1.163.0
    steps:
      - uses: actions/checkout@v6
      - run: git config --global --add safe.directory "$GITHUB_WORKSPACE"
      - run: semgrep ci --sarif --output=semgrep.sarif
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
      - uses: actions/checkout@v6
      - uses: aquasecurity/trivy-action@v0.36.0
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
      - uses: actions/checkout@v6
      - run: docker build -t app-backend:ci ./fastapi
      - uses: aquasecurity/trivy-action@v0.36.0
        with:
          scan-type: image
          image-ref: app-backend:ci
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

## Rule selection

Cherry-pick semgrep packs per language. Don't enable everything — noise kills triage. Default set:

- `p/python` or `p/typescript` (language baseline)
- `p/react` if frontend
- `p/security-audit` (cross-language)
- `p/secrets` (credentials in code)
- `p/owasp-top-ten`
- `p/dockerfile` if you ship images

**Skipped on purpose**: `p/default` — too noisy and overlaps everything else.

## Gotchas

- `ignore-unfixed: true` on trivy — there's nothing you can do about an unfixed CVE except wait, so don't gate PRs on it.
- `severity: CRITICAL,HIGH,MEDIUM` — drop MEDIUM if signal-to-noise hurts.
- Semgrep container pin (`semgrep/semgrep:1.163.0`) gives reproducible scans. Bump intentionally.
- `if: always()` on SARIF upload so a scan failure still uploads partial results.
