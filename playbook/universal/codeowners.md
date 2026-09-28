---
tool: codeowners
scope: universal
tier: baseline
summary: "Required reviewers auto-assigned per path"
targets: [".github/CODEOWNERS", ".gitlab/CODEOWNERS"]
---

# CODEOWNERS

## What

Maps path globs to owners. Owners of a touched path are auto-requested on the PR/MR;
with branch protection on, their approval is **required to merge**.

## Why

- Enforces the "one human approval" rule from [[contributing]] in a file, not in memory.
- Pairs with bot-first review: the bot reviews everything, CODEOWNERS routes the human pass.

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

**GitLab** — `.gitlab/CODEOWNERS`. Same syntax; `[Section]` headers each become a
required approval rule:

```
* @{{owner}}

[Backend]
/backend/ @{{backend-owner}}

[Frontend]
/frontend/ @{{frontend-owner}}

[CODEOWNERS]
/.gitlab/CODEOWNERS @{{owner}}
```

Then **Settings → Repository → Protected branches → `main`**: enable *Code owner approval*.

## Gotchas

- **Last match wins.** Keep `*` first; narrower rules below override it.
- **Without branch protection it's advisory** — reviewers are requested, merge isn't blocked.
- Owners without write access (GitHub) / Developer+ membership (GitLab) are **silently
  ignored**. Prefer teams/groups (`@org/team`) over individuals so one absence doesn't block merges.
- Own the `CODEOWNERS` file itself, or anyone can reroute review in the same PR.
- GitLab: prefix a section with `^` (`^[Docs]`) to make it optional (requested, not required).
