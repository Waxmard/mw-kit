---
name: comment-audit
description: >
  Audit a codebase for redundant, stale, or noise comments and clean them up.
  A cheap `scc`-based pre-flight ranks code files by comment density/volume so
  the expensive LLM read only touches files that look over-commented; then it
  judges each comment (cut / keep / rewrite) one file at a time, pausing for a
  go/stop decision before editing. Use this whenever the user wants to find or
  remove unnecessary comments, reduce comment noise, check for over-commenting
  or redundant docstrings/JSDoc, clean up commented-out code, or asks "are there
  too many comments here" — even if they don't name a tool. Trigger: "audit
  comments", "too many comments", "find redundant comments", "clean up
  comments", "comment audit", "remove noise comments", or /comment-audit.
---

Find and remove comments that don't earn their place — restatements of the code,
stale or lying headers, commented-out code — while protecting the comments that
do real work (the *why*, the gotcha, the external constraint). The flow is
**rank → audit one file → decide → apply**, and it never edits code until the
user approves that file.

The core belief: comment quality is a judgment call, not a metric. `scc` can
tell you a file is comment-*heavy*, but only a reader can tell whether those
comments are redundant. So the pre-flight is just a cost gate that picks which
files are worth reading; you are the judge.

## Step 1 — Pre-flight (run the script, don't eyeball)

```bash
python3 "${MW_KIT:-/Users/maxwellward/personal-dev/mw-kit}/skills/comment-audit/scripts/preflight.py" <repo-or-dir>
# default target is CWD; add --table for a human view, --floor 0.10 to widen
```

It runs `scc`, keeps only code files whose comment density or raw comment count
is elevated, and emits JSON ranked worst-first:

```json
{"path": "...", "floor": 0.15, "count": 12, "suspects": [
  {"file": "src/constants/pagination.ts", "lang": "TypeScript",
   "ratio": 0.76, "comment": 54, "code": 17, "score": 1.324, "via": "dense"}
]}
```

If `scc` is missing the script says so — tell the user to `brew install scc`.
If `count` is 0, report the repo looks clean and stop; don't go hunting by hand.

**Don't re-derive the ranking or re-filter by hand.** The floor is a cost dial,
not a quality line — it only skips the obviously-fine majority. The script
already excludes config/markup languages and test files; trust it.

## Step 2 — Audit one file at a time, worst-first

Walk the `suspects` list in order. For each file: read it fully, then classify
**every** comment into cut / keep / rewrite using the rubric below. Judge each
comment against the code it sits on — redundancy is contextual, so you must see
the code, not just the comment.

### The rubric

**CUT — the comment adds nothing the code doesn't already say:**
- Restates the name or signature. `/** @param bytes - Number of bytes */` over
  `bytes: number` — the type already says it. `/** Whether the field is required */`
  over `isRequired?: boolean`.
- Per-member docblocks that just echo the member: `/** Default page size */`
  over `DEFAULT_PAGE_SIZE: 10`.
- Decorative dividers / section banners that carry no information.
- Commented-out code (dead code; git remembers it).
- Narration of the obvious next line (`// loop over users` above a `for`).

**KEEP — the comment carries something the code cannot:**
- The *why*: rationale, a deliberate tradeoff, why this and not the obvious thing.
- External constraints / magic numbers with a source (`// OpenSearch
  max_result_window; offset paging can't exceed this`).
- Gotchas, warnings, ordering hazards, "don't refactor this away because…".
- Non-obvious contracts on a public API beyond what the signature shows
  (side effects, units, nullability rules, lifecycle).
- Links to tickets / specs / RFCs.

**REWRITE — there's signal buried in noise, or the comment is wrong:**
- Stale or *lying* comments — a header describing code that no longer exists
  (e.g. a "Color utilities" banner on a file with no color code). These are
  worse than redundant; flag for correction or deletion.
- A useful point smothered in boilerplate — keep the kernel, cut the filler.
- A docstring that half-restates and half-explains — trim to just the explain.

When unsure, lean KEEP. The cost of cutting a load-bearing comment (a future
reader re-derives the *why* the hard way) is higher than leaving one mild
restatement. This audit removes noise; it is not a war on comments.

### Per-file report format

Present findings for the current file like this, then stop and wait:

```
### src/constants/pagination.ts  (76% comments, 9/12 flagged)

CUT (8)
  L5-7    `/** Default page size for general pagination */`  → restates DEFAULT_PAGE_SIZE
  L10-12  `/** Page size for document listings */`           → restates DOCUMENT_PAGE_SIZE
  ...
KEEP (3)
  L45-49  ES_MAX_OFFSET block — explains the OpenSearch window limit (the why)
REWRITE (1)
  L3      `Color utilities…` header is stale — file has no color code; delete or correct

Apply these cuts? (yes / skip this file / edit selection / stop)
```

Keep the reasoning to a short clause per comment — enough for the user to spot a
bad call, not an essay. Always show what you'd KEEP too, so the user can see you
didn't just nuke everything.

## Step 3 — Checkpoint, then apply

After each file's report, **wait for the user.** This per-file gate is the whole
cost-control mechanism — there is no batch mode and no "do them all." Honor:
- **yes** → apply the CUTs and REWRITEs to that file, then move to the next.
- **skip this file** → change nothing, move on.
- **edit selection** → user vetoes specific lines; apply the rest.
- **stop** → end the audit; summarize what was done.

Applying edits:
- Delete the **whole** comment span, including a multi-line `/** … */` block and
  any now-orphaned blank line it leaves behind. Don't leave a dangling `*/`.
- For REWRITEs, replace the span with the trimmed/corrected text.
- Never touch the code itself — only comment lines.
- After editing a file, if the repo has a fast formatter/linter (prettier,
  ruff, etc.), it's fine to let the user's normal tooling reflow; don't run
  builds yourself unless asked.

Then continue to the next file in the ranked list. Stop when the list is
exhausted or the user says stop.

## Step 4 — Wrap up

Summarize: files audited, comments cut/rewritten/kept, files skipped, and how
far down the ranked list you got (so the user knows what's left if they bailed
early). Don't commit — the user handles commits.

## Notes

- **Go and other low-comment languages** rarely trip the density path (Go's
  median comment ratio is ~1%); the volume path still catches big files. If a
  user specifically wants to audit a Go-heavy repo, widen with `--floor 0.10`.
- The pre-flight reads only line counts, never code — all judgment is in Step 2.
- This skill is read-only through Step 2; the only writes happen in Step 3 after
  an explicit per-file yes.
