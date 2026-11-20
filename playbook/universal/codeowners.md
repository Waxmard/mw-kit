---
tool: codeowners
scope: universal
tier: baseline
summary: "Required reviewers auto-assigned per path"
targets: [".github/CODEOWNERS"]
---

# CODEOWNERS

## What

Maps path globs to owners. Owners of a touched path are auto-requested on the PR;
with branch protection on, their approval is **required to merge**.

## Why

- Enforces the one-human-approval rule ([github-settings](./github-settings.md)) in a file, not in memory.

## Config

**GitHub** — `.github/CODEOWNERS`:

```
*                       @{{owner}}

/backend/               @{{backend-owner}}
/frontend/              @{{frontend-owner}}
*.tf                    @{{infra-owner}}

/.github/CODEOWNERS     @{{owner}}
```

Then **Settings → Branches → protect `main`**: require a PR + review from Code Owners.


## Gotchas

- **Last match wins.** Keep `*` first; narrower rules below override it.
- **Without branch protection it's advisory** — reviewers are requested, merge isn't blocked.
- Owners without write access are **silently
  ignored**. Prefer teams/groups (`@org/team`) over individuals so one absence doesn't block merges.
- Own the `CODEOWNERS` file itself, or anyone can reroute review in the same PR.
