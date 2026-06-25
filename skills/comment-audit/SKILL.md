---
name: comment-audit
description: >
  Audit a codebase for redundant, stale, verbose, or noise comments and clean
  them up. A cheap `scc`-based pre-flight ranks code files by comment
  density/volume so the expensive LLM read only touches files worth checking;
  then it judges each comment (cut redundant / tighten verbose / keep
  load-bearing) one file at a time, pausing for a go/stop decision before
  editing. Aggressive by default — it trims accurate-but-wordy comments, not just
  redundant ones. Use this whenever the user wants to find or remove unnecessary
  comments, reduce comment noise, tighten verbose or over-long comments, check
  for over-commenting or redundant docstrings/JSDoc, clean up commented-out code,
  or asks "are there too many comments here" or "these comments are too verbose"
  — even if they don't name a tool. Trigger: "audit comments", "too many
  comments", "comments too verbose", "find redundant comments", "clean up
  comments", "tighten comments", "comment audit", "remove noise comments", or
  /comment-audit.
---

Find and remove comments that don't earn their place — restatements of the code,
stale or lying headers, commented-out code — while protecting the comments that
do real work (the *why*, the gotcha, the external constraint). The flow is
**rank → audit one file → decide → apply**, and it never edits code until the
user approves that file.

The core belief: comment quality is a judgment call, not a metric. `scc` can
tell you a file is comment-*heavy*, but only a reader can tell whether those
comments are redundant **or just too wordy**. So the pre-flight is a deliberately
wide cost gate that picks which files are worth reading; you are the judge — and
the bar is high. A good comment earns its space by saying something the code
can't, *concisely*. Length is a cost: every extra line is more to read and more
to drift out of date, so an accurate-but-bloated comment is a defect too, not
just a redundant one.

## Step 1 — Pre-flight (run the script, don't eyeball)

```bash
python3 "${MW_KIT:-/Users/maxwellward/personal-dev/mw-kit}/skills/comment-audit/scripts/preflight.py" <repo-or-dir>
# default target is CWD; add --table for a human view. The default floor (0.08)
# sits just above the corpus median, so it sweeps wide on purpose; raise --floor
# (e.g. 0.15) to be more selective on a large repo.
```

It runs `scc`, keeps only code files whose comment density or raw comment count
is elevated, and emits JSON ranked worst-first:

```json
{"path": "...", "floor": 0.08, "count": 12, "suspects": [
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
**every** comment into cut / tighten / keep using the rubric below. Judge each
comment against the code it sits on — both redundancy and verbosity are
contextual, so you must see the code, not just the comment.

This is an **aggressive** pass. The goal is the leanest set of comments that
still carries every non-obvious fact — bias toward less. Two independent
questions per comment: *does it say anything the code doesn't?* (if no → CUT) and
*does it say it in more words than needed?* (if yes → TIGHTEN). A comment only
KEEPs when it passes **both** — load-bearing **and** already terse.

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
- Stale or *lying* comments — a header describing code that no longer exists
  (e.g. a "Color utilities" banner on a file with no color code). Worse than
  redundant. Cut it, or TIGHTEN to an accurate one-liner if a header is wanted.

**TIGHTEN — the point is real but the wording is bloated.** This is the default
verdict for any accurate comment that runs long, and where most of the work is.
Keep every fact; cut the words around it. Patterns:
- Multi-sentence prose that states one idea. A 5-line file header explaining a
  data shape can usually be 2 lines. Drop the throat-clearing ("This function
  is responsible for…", "Note that…", "Basically…").
- A useful kernel smothered in boilerplate — keep the kernel, cut the filler.
- A docstring that half-restates the signature and half-explains — drop the
  restatement, keep the explain.
- `@param`/`@returns` tags whose text only restates the typed signature — cut the
  tags, keep any genuine note.
- Cute or narrative asides — keep the technical content, lose the flavor text.
Always show the proposed replacement so the user sees exactly what it becomes.

**KEEP — load-bearing AND already concise; leave it untouched:**
- The *why*: rationale, a deliberate tradeoff, why this and not the obvious thing.
- External constraints / magic numbers with a source (`// OpenSearch
  max_result_window; offset paging can't exceed this`).
- Gotchas, warnings, ordering hazards, "don't refactor this away because…".
- Non-obvious contracts on a public API beyond what the signature shows
  (side effects, units, nullability rules, lifecycle).
- Links to tickets / specs / RFCs.
If one of these is wordy, it's a TIGHTEN, not a KEEP — KEEP is only for comments
already at their leanest.

The one guard against over-cutting: **never drop a fact.** Aggressive means
shorter, not lossy — if you can't preserve the *why* / constraint / gotcha in
fewer words, leave it. When genuinely unsure whether a fact matters, TIGHTEN
(shorten) rather than CUT (delete) so the information survives.

### Per-file report format

Present findings for the current file like this, then stop and wait:

```
### src/api/mockBackend.ts  (12% comments, 7/9 flagged)

CUT (2)
  L30   `/** Pipeline order, for ranking… */`   → restates the const name
  L176  `/** Mimics fetch latency. */`          → restates setTimeout below it

TIGHTEN (5)
  L1-6   6-line file header → 2 lines:
         `// In-memory mock backend (VITE_SIMULATE_BACKEND). Canned stateful`
         `// responses; keep shapes in sync with types/tracker.ts.`
  L17-20 `/** Mock backend is dev-only — gating on import.meta.env.DEV…  */`
         → `/** Dev-only: import.meta.env.DEV keeps it out of prod builds. */`
  L45-46 drop the "march through the oven" flavor, keep:
         `// Staggered timelines: two files finish clean, one is quarantined.`
  ...

KEEP (2)
  L114-116  live-session attribution note — explains why dropzone_id is absent (the why)

Apply these? (yes / skip this file / edit selection / stop)
```

Keep the reasoning to a short clause per comment — enough for the user to spot a
bad call, not an essay. For every TIGHTEN, show the exact replacement text so the
user is approving a concrete edit, not a vibe. Always show what you'd KEEP too,
so the user can see what survived and why.

## Step 3 — Checkpoint, then apply

After each file's report, **wait for the user.** This per-file gate is the whole
cost-control mechanism — there is no batch mode and no "do them all." Honor:
- **yes** → apply the CUTs and TIGHTENs to that file, then move to the next.
- **skip this file** → change nothing, move on.
- **edit selection** → user vetoes specific lines; apply the rest.
- **stop** → end the audit; summarize what was done.

Applying edits:
- For a CUT, delete the **whole** comment span, including a multi-line `/** … */`
  block and any now-orphaned blank line it leaves behind. Don't leave a dangling `*/`.
- For a TIGHTEN, replace the span with the exact shortened text you showed in the
  report — same comment style (`//` vs `/** */`), just fewer lines.
- Never touch the code itself — only comment lines.
- After editing a file, if the repo has a fast formatter/linter (prettier,
  ruff, etc.), it's fine to let the user's normal tooling reflow; don't run
  builds yourself unless asked.

Then continue to the next file in the ranked list. Stop when the list is
exhausted or the user says stop.

## Step 4 — Wrap up

Summarize: files audited, comments cut/tightened/kept, files skipped, and how
far down the ranked list you got (so the user knows what's left if they bailed
early). Don't commit — the user handles commits.

## Notes

- **Go and other low-comment languages** rarely trip the density path (Go's
  median comment ratio is ~1%); the volume path still catches big files. If a
  user specifically wants to audit a Go-heavy repo, lower with `--floor 0.05`.
- The pre-flight reads only line counts, never code — all judgment is in Step 2.
- This skill is read-only through Step 2; the only writes happen in Step 3 after
  an explicit per-file yes.
