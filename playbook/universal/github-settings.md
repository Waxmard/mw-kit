---
tool: github-settings
scope: universal
tier: baseline
summary: "Repo settings, default-branch ruleset, Actions token, Dependabot alerts via gh api"
targets: []
platform: github
---

# GitHub repo settings

## What

Settings that live on GitHub, not in the tree: merge buttons, a ruleset on the default branch, the default Actions token scope, and security features. All of them are set with `gh api`, so a new repo is bootstrapped by pasting the Config block once.

## Why

- **Squash + rebase only, PR title as the squash subject.** Main stays linear and every commit subject is the Conventional Commit PR title that release-please reads. Merge commits would add noise subjects release-please ignores.
- **Delete head branches, offer "Update branch", allow auto-merge.** Auto-merge is what the release-please workflow's `gh pr merge --auto` step turns on.
- **Ruleset on `~DEFAULT_BRANCH`.** No deletion, no force-push, linear history, PR required (0 approvals, solo-friendly). The admin role can bypass, so an emergency direct push still works. Rulesets over classic branch protection: one JSON document, idempotent PUT, and they stack with org rulesets.
- **Actions token read-only by default.** Workflows that need writes declare `permissions:` themselves (release-please does). Actions can't approve PRs.
- **Dependabot alerts + security-update PRs, secret scanning + push protection.** Free on public repos and independent of [[dependabot]] version-update config.

## Config

Run from anywhere with `gh` authenticated as a repo admin. Set `R` first.

```bash
R=OWNER/REPO

gh api -X PATCH "repos/$R" \
  -F allow_merge_commit=false -F allow_squash_merge=true -F allow_rebase_merge=true \
  -f squash_merge_commit_title=PR_TITLE -f squash_merge_commit_message=PR_BODY \
  -F delete_branch_on_merge=true -F allow_update_branch=true -F allow_auto_merge=true

gh api -X PUT "repos/$R/actions/permissions/workflow" \
  -f default_workflow_permissions=read -F can_approve_pull_request_reviews=false

gh api -X PUT "repos/$R/vulnerability-alerts"
gh api -X PUT "repos/$R/automated-security-fixes"
gh api -X PATCH "repos/$R" --input - <<'JSON'
{ "security_and_analysis": {
    "secret_scanning": { "status": "enabled" },
    "secret_scanning_push_protection": { "status": "enabled" } } }
JSON

RULESET='{
  "name": "main",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "bypass_actors": [ { "actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always" } ],
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "required_linear_history" },
    { "type": "pull_request", "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false,
        "allowed_merge_methods": ["squash", "rebase"] } }
  ]
}'
ID=$(gh api "repos/$R/rulesets" --jq '.[] | select(.name=="main") | .id')
if [ -n "$ID" ]; then
  echo "$RULESET" | gh api -X PUT "repos/$R/rulesets/$ID" --input -
else
  echo "$RULESET" | gh api -X POST "repos/$R/rulesets" --input -
fi
```

Once CI exists, add its job names as required checks. Append this rule to `rules` and re-run the ruleset part (`15368` is the GitHub Actions app; `context` is the job `name:`, or the job id if unnamed):

```json
{ "type": "required_status_checks", "parameters": {
    "strict_required_status_checks_policy": true,
    "do_not_enforce_on_create": false,
    "required_status_checks": [ { "context": "check", "integration_id": 15368 } ] } }
```

## Audit

Read-only. Compare against the Config block:

```bash
gh api "repos/$R" --jq '{allow_merge_commit, allow_squash_merge, allow_rebase_merge, squash_merge_commit_title, squash_merge_commit_message, delete_branch_on_merge, allow_update_branch, allow_auto_merge, security_and_analysis}'
gh api "repos/$R/actions/permissions/workflow"
gh api "repos/$R/vulnerability-alerts" --silent && echo alerts-on
gh api "repos/$R/automated-security-fixes"
gh api "repos/$R/rules/branches/$(gh api "repos/$R" --jq .default_branch)" --jq '[.[].type]'
```

## Gotchas

- **Re-running the ruleset POST creates a duplicate.** The Config block looks the ruleset up by name and PUTs if it exists. Keep that pattern.
- **`actor_id: 5` is the built-in admin repository role.** `current_user_can_bypass` on `GET repos/$R/rulesets/$ID` should read `always` for the owner.
- **A ruleset `allowed_merge_methods` must include whatever the release workflow uses.** [[releases-github]] merges with `--rebase`.
- **Auto-merge on a PR with nothing pending.** With 0 required approvals and no required checks, a release PR is already mergeable, and `gh pr merge --auto` may fail with "Pull request is in clean status". Add a required check, or drop `--auto` in that repo's release workflow.
- **Private repos.** Secret scanning and push protection need GitHub Advanced Security there. The `security_and_analysis` PATCH fails, so skip that call.
- **Classic branch protection on an existing repo** (`GET repos/$R/branches/<b>/protection` returns 200) stacks with the ruleset. Migrate its required checks into the ruleset, then `gh api -X DELETE repos/$R/branches/<b>/protection`.
