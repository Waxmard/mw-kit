---
tool: codeowners
scope: universal
tier: baseline
summary: "Required reviewers auto-assigned per path"
targets: [".github/CODEOWNERS", ".gitlab/CODEOWNERS"]
---

# CODEOWNERS

## What

A `CODEOWNERS` file maps path globs to owners. When a PR/MR touches a matched path,
those owners are **auto-requested as reviewers**, and — with the right branch-protection
rule — their approval becomes **required to merge**.

## Why

- It's the enforcement mechanism behind the contributing guide's "one human approval"
  rule (see [[contributing]]). Review routing lives in a file, not in someone's memory.
- New contributors don't have to guess who reviews what.
- Pairs with bot-first review: the bot reviews everything, CODEOWNERS routes the
  required *human* pass.

## Config

**GitHub** — `.github/CODEOWNERS`:

```
# Last matching rule wins. Order specific paths after the catch-all.
*                       @{{owner}}

/fastapi/               @{{backend-owner}}
/frontend/              @{{frontend-owner}}
*.tf                    @{{infra-owner}}
```

Then enable branch protection on the default branch:
**Settings → Branches → require review from Code Owners** (and require a PR before merging).

**GitLab** — `.gitlab/CODEOWNERS`. Same syntax, plus optional named sections that
become required-approval groups:

```
* @{{owner}}

[Backend]
/fastapi/ @{{backend-owner}}

[Frontend]
/frontend/ @{{frontend-owner}}
```

Then add the approval rule on the protected branch:
**Settings → Repository → Protected branches / Merge request approvals →
require Code Owner approval**.

## Gotchas

- **Last match wins.** Put the broad `*` rule first and narrow rules below it, or the
  catch-all overrides everything.
- Owners must have **write/push access** to the repo, or the entry is silently ignored.
- The file alone requests reviewers but does **not** block merge — you must also flip
  the branch-protection toggle (GitHub) / approval rule (GitLab). Without it, CODEOWNERS
  is advisory.
- **Don't list the review bot here** (WolfCoder/pupcoder). The bot reviews via CI; the
  code owner is the *human* whose approval the contributing flow requires.
