# Contributing to mw-kit

Thanks for contributing. This guide covers how a change flows from a branch to a release.

## Branching
`main` is the default and target branch — branch off the latest `main`, never push to it
directly. Every change lands through a pull request.

    git switch main && git pull
    git switch -c feat/short-description

## Commit Messages
We follow [Conventional Commits](https://www.conventionalcommits.org/): `<type>(<scope>): <subject>`.
`feat:` → minor, `fix:` → patch, `!`/`BREAKING CHANGE:` → major. `docs`/`chore`/`refactor`/`test`
are used as normal. See [`.git-ai-instructions`](.git-ai-instructions) for this repo's
type-classification deltas (e.g. `docs` is the default here, not `feat`).

Let [git-ai](https://github.com/Waxmard/git-ai) draft a conventional commit from staged changes.
Install the CLI once with `npm install -g @waxmard/git-ai` (or `uv tool install waxmard-git-ai` /
`pip install waxmard-git-ai` — same CLI, needs `bash` on `PATH`), then:

    git add -A
    git-ai commit                     # prints a Conventional Commits message to stdout — review it
    git commit -m "$(git-ai commit)"  # …or commit with it in one line

Run `git-ai setup` once to configure a provider.

## Pull Requests
Always open one — even for small changes.

- **Squash on merge.** The branch's WIP commits collapse into a single commit on `main`,
  so the **squashed title and body must be the real, conventional message** — that line is
  what release tooling would read. Let git-ai draft it: `git-ai pr --base main`.
- **Reference the ticket.** If the change closes or relates to a ticket, add `#<ticketnum>`
  to the description so the PR links back to the issue.
- **Keep it focused.** One logical change per PR keeps review and the history clean.

## Review & Approval
- **Bot first.** The `claude-code-review` workflow reviews every PR automatically —
  address its findings up front.
- **Then a human.** A [CODEOWNER](.github/CODEOWNERS) is auto-requested; one human
  approval is required to merge.

## Deploys & Releases
No automated release tooling yet — no tags or `CHANGELOG.md` exist. If that changes,
wire up [release-please](https://github.com/googleapis/release-please) (see the
`universal/releases-github` playbook page) so it can read the conventional commit
history already being kept.
