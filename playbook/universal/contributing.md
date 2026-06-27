---
tool: contributing
scope: universal
tier: baseline
summary: "CONTRIBUTING.md: branching, commits, MR/PR + review flow"
targets: ["CONTRIBUTING.md"]
---

# CONTRIBUTING.md

## What

Every repo ships a `CONTRIBUTING.md` at the root covering five things: branching,
commit messages, opening an MR/PR, the review flow, and how releases happen. It is the
one written description of how a change goes from a branch to production.

## Why

- One written flow beats tribal knowledge — new contributors (and future you) read one file.
- Release tooling reads every commit ([[conventional-commits]] → [[releases-github]] /
  [[releases-gitlab]]), so commit hygiene is load-bearing, not cosmetic. The guide is
  where that expectation is stated.
- **Bot-before-human review** keeps people off issues a bot already caught — they review
  already-clean code instead of re-treading machine comments.
- Ticket linking keeps MRs traceable back to *why* the change exists.

## Config

Canonical `CONTRIBUTING.md` **skeleton** — copy it, then fill the `{{placeholders}}` and
delete the platform (GitHub/GitLab) lines that don't apply. tooling-sync checks that a
repo's `CONTRIBUTING.md` *covers these sections*, not that it matches line-for-line.

```markdown
# Contributing to {{project}}

Thanks for contributing. This guide covers how a change flows from a branch to a release.

## Branching
`main` is the default and target branch — branch off the latest `main`, never push to it
directly. Every change lands through a merge request / pull request.

The best start is **from the ticket**: open the issue and use *Create merge request*
(GitLab) — it names the branch, links the ticket, and opens a draft MR. Otherwise:

    git switch main && git pull
    git switch -c feat/short-description

## Commit Messages
We follow [Conventional Commits](https://www.conventionalcommits.org/): `<type>(<scope>): <subject>`.
`feat:` → minor, `fix:` → patch, `!`/`BREAKING CHANGE:` → major. `docs`/`chore`/`refactor`/`test`
are used as normal. These types drive automated versioning (see Deploys & Releases).

Let [git-ai](https://github.com/Waxmard/git-ai) draft a conventional commit from staged changes.
Install the CLI once with `npm install -g @waxmard/git-ai` (or `uv tool install waxmard-git-ai` /
`pip install waxmard-git-ai` — same CLI, needs `bash` on `PATH`), then:

    git add -A
    git-ai commit                     # prints a Conventional Commits message to stdout — review it
    git commit -m "$(git-ai commit)"  # …or commit with it in one line

Run `git-ai setup` once to configure a provider.

## Merge Requests / Pull Requests
Always open one — even for small changes.

- **Squash on merge.** The branch's WIP commits collapse into a single commit on `main`,
  so the **squashed title and body must be the real, conventional message** — that line is
  what release tooling reads. Let git-ai draft it: `git-ai pr --base main`.
- **Reference the ticket.** If the change closes or relates to a ticket, add `#<ticketnum>`
  to the description so the MR/PR links back to the issue.
- **Keep it focused.** One logical change per MR keeps review and the changelog clean.

## Review & Approval
Every MR needs two passes — **automated review first, then a human.**

- **Bot first.** Let the review bot ({{WolfCoder/pupcoder on GitLab; configured review bot on GitHub}})
  review and approve before adding a human reviewer. Address its findings up front.
- **Then a human.** A [CODEOWNER](.gitlab/CODEOWNERS) is auto-requested; one human
  approval is required to merge.

## Deploys & Releases
On every push to `main`, release automation reads the conventional commits since the last
tag, bumps the version, updates `CHANGELOG.md`, and tags the release.
{{release-please (GitHub) / semantic-release (GitLab) / python-semantic-release}}.
This is why commit hygiene matters: every commit on `main` is read by the release tooling.
```

## Gotchas

- **Prose is not a literal diff target.** Unlike a structured config, tooling-sync verifies
  this page's *sections are present*, not that wording matches. Keep the section headings.
- **Keep the `{{placeholders}}`** in the source skeleton — they signal "fill this in" rather
  than implying every consumer repo should read identically.
- **Squash discipline is the whole game** for release accuracy: if the squashed commit title
  isn't conventional, the changelog and version bump are wrong regardless of the branch commits.
- **The bot does not replace the human approval** — it's an additional, earlier gate. The
  required approval still comes from a [[codeowners]] human.
- Pick the matching release page: [[releases-github]], [[releases-gitlab]], Python repos →
  [[releases-python]], monorepos → [[releases-monorepo]].
