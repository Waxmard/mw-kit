---
tool: git-ai-instructions
scope: universal
tier: baseline
summary: "Repo-local commit/PR guidance for git-ai, framed by user POV"
targets: [".git-ai-instructions"]
detect: [".git-ai-instructions"]
---

# .git-ai-instructions

## What

A free-form prose file at the repo root that teaches [git-ai](https://github.com/Waxmard/git-ai) the repo's commit/PR conventions. git-ai injects it verbatim into its commit and PR prompts as an authoritative `<repo_guidance>` block — when it conflicts with git-ai's built-in type heuristics, this file wins.

It is not a config schema. Three parts, in order:

1. **`User POV:`** — *who consumes what this repo produces, and what they perceive as its output.* This is the single biggest lever on prefix accuracy.
2. **What "user-facing" means** for that audience (git-ai's default `feat`-bias keys off "user-facing", so pinning the audience redirects it).
3. **Only the type rules where this repo diverges** from the standard heuristics, each as `case → type`.

## Why

git-ai's default heuristics assume a typical app repo (user-facing capability → `feat`, etc.). Repos with a different audience break that assumption: in a GitOps repo *every* change is a deploy, so the `feat`-bias misfires; in a tool whose product is generated text, restyling that text is `style`, not a feature. Stating the POV once fixes a whole class of misclassifications — far more leverage than enumerating rules. Pairs with [[conventional-commits]] (this file only encodes the *deltas* from that standard).

## Config

Canonical template — fill in the angle-bracket parts, delete the `#` guidance lines, keep it short:

```
User POV: <who consumes this repo's output> — <what they perceive as the product>.
"User-facing" = <what counts as visible to that audience>.

# List ONLY cases where this repo diverges from git-ai's default type heuristics:
- <repo-specific case> → <type>
- <repo-specific case> → <type>
```

Worked example — a GitOps/deploy repo:

```
User POV: the deployed apps. "User-facing" = what changes for someone using a running app,
not the fact that a manifest changed.

- Bumping an image tag to ship the same app's next build → chore
- Renaming or retuning an env var, resource limit, or replica count → fix
- A brand-new deployed service, or a genuinely new capability its users gain → feat
```

## Gotchas

- **POV first, rules second.** A precise `User POV:` line does most of the work; the rules just cover the cases the POV alone leaves ambiguous.
- **Encode deltas, not defaults.** Don't restate git-ai's standard precedence (`feat > fix > …`) — every line is prompt tokens. List only where this repo differs.
