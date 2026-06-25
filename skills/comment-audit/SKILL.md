---
name: comment-audit
description: >
  Audit a codebase for redundant, stale, verbose, or noise comments and clean
  them up. A cheap `scc`-based pre-flight ranks code files by comment
  density/volume so the expensive LLM read only touches files worth checking;
  then it judges each comment (cut redundant / tighten verbose / keep
  load-bearing) and applies the edits, defaulting to auto-apply across the repo
  with a `git diff` review after (a per-file gate is available on request).
  Aggressive by default — it trims accurate-but-wordy comments, not just
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
**rank → audit → apply → review the diff**. By default it applies edits as it
goes and the user reviews the whole `git diff` after; a per-file gate is
available on request. Edits are comment-only and git-revertible, which is what
makes applying-without-asking safe.

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

## Step 2 — Audit: classify every comment, worst-first

Walk the `suspects` list in order. For each file: read it fully, then classify
**every** comment into cut / tighten / keep using the rubric below. Judge each
comment against the code it sits on — both redundancy and verbosity are
contextual, so you must see the code, not just the comment. How the edits get
applied (auto vs. per-file) is Step 3; the judgment here is the same either way.

This is a **ruthless** pass. Presume every comment is noise until it proves
otherwise. The reader is competent and has the code, the types, and `git blame` —
so anything recoverable from those in a few seconds does not deserve a comment.
A comment survives **only** by carrying a specific fact the code cannot show: a
non-obvious *why*, an external constraint, a real hazard. Default to removing;
make every KEEP justify itself by naming the fact it preserves — if you can't
name that fact in a few words, it's a CUT.

Two questions per comment: (1) *Could a competent reader get this from the
code, types, or name?* → CUT. (2) *Is the point real but the wording fat?* →
TIGHTEN to the bone. KEEP is the rare residue: a non-recoverable fact, already in
the fewest possible words.

### The rubric

**CUT — the comment tells the reader nothing they can't get from the code:**
- Restates the name or signature. `/** @param bytes - Number of bytes */` over
  `bytes: number`; `/** Whether the field is required */` over `isRequired?: boolean`.
- Per-member docblocks that echo the member: `/** Default page size */` over
  `DEFAULT_PAGE_SIZE: 10`.
- Explains *what* or *how* the code does something — that's the code's job. Only
  *why* can earn a comment; description of mechanism is noise.
- Teaches a standard language/library idiom a competent reader already knows.
- States a "why" that's actually obvious from the surrounding context.
- Redundant with a clear name — if renaming the symbol would make the comment
  pointless, the name already carries it; cut the comment.
- Decorative dividers / section banners that carry no information.
- Commented-out code (dead code; git remembers it).
- Narration of the obvious next line (`// loop over users` above a `for`).
- Stale or *lying* comments — a header describing code that no longer exists.
  Worse than noise. Cut it (or TIGHTEN to an accurate one-liner if a header earns
  its place).

**TIGHTEN — the fact is real but the wording is fat.** Cut to the bone, not just
trim. Telegraphic is the target: fragments over sentences, drop articles and
filler ("the", "this", "basically", "note that", "is responsible for"), one line
wherever one line will do — a multi-line block has to justify every line it keeps.
Patterns:
- Multi-sentence prose stating one idea → one fragment. A 5-line file header is
  usually 1–2 lines.
- A real kernel buried in boilerplate → keep the kernel, drop the rest.
- A docstring half-restating the signature and half-explaining → delete the
  restatement, keep only the explain, shortened.
- `@param`/`@returns` tags that just restate the typed signature → cut the tags,
  keep any genuine note as a bare line.
- Cute or narrative asides → keep the technical fact, lose the flavor.
Always show the exact replacement so the user sees what it becomes.

**KEEP — a non-recoverable fact, already at its leanest. Rare.**
- The *why* the code can't show: a deliberate tradeoff, why this not the obvious thing.
- External constraint / magic number with a source (`// OpenSearch
  max_result_window; offset paging can't exceed this`).
- A real hazard: ordering dependency, "don't refactor this away because…", a footgun.
- A genuine API contract beyond the signature (side effects, units, nullability).
- Link to a ticket / spec / RFC.
*What* and *how* never qualify — those are the code's. If a keeper is wordy it's a
TIGHTEN, not a KEEP; KEEP is only for comments already telegraphic.

The one inviolable guard: **never delete a fact that isn't recoverable from the
code** — a real why / constraint / hazard. Ruthless means fewer and shorter,
never lossy. The tiebreak: if you're unsure because the comment looks like
something the code already shows, cut it; if you're unsure because it asserts an
external fact or hazard you *can't verify from the code*, keep it (tightened) —
you can't safely drop what you can't confirm is redundant.

### Per-file report format

Report each file's findings like this (in auto mode it's a record of what you
applied; in per-file mode you show it and wait):

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
```

Keep the reasoning to a short clause per comment — enough for the user to spot a
bad call, not an essay. For every TIGHTEN, show the exact replacement text, so
the record (or the approval, in per-file mode) is a concrete edit, not a vibe.
Always show what you'd KEEP too, so the user can see what survived and why.

## Step 3 — Apply

There are two modes. **Auto-apply is the default** — the user almost always
accepts the cuts, so per-file gating is just friction, and `git diff` is the
better review surface (every edit is comment-only and trivially revertible).

### Auto mode (default)

Stream through the ranked list: for each file, classify (Step 2), **apply the
CUTs and TIGHTENs immediately**, and emit a one-line record (e.g.
`mockBackend.ts — 2 cut, 3 tightened, 4 kept`). No per-file pause. Keep going to
the end of the list, then hand off to Step 4 so the user reviews the whole diff
at once.

One precondition makes this safe: **the audit's edits should be the only
uncommitted change**, so `git diff` shows exactly what the audit did and
`git checkout -- <file>` cleanly reverts. Check `git status --short` first; if the
tree is already dirty with unrelated changes, say so and offer to either proceed
anyway (the diff will be mixed) or let the user stash/commit first. Don't block on
a clean tree — just make the user aware so the review surface isn't a surprise.

Announce the mode in one line before starting (e.g. "Auto-applying across N files;
review the diff after — say 'review per-file' for the gated mode instead"). That
sentence is the *only* interaction in the default path.

### Per-file mode (on request)

When the user asks to go file-by-file (or wants control on a risky repo), fall
back to a gate after each file's report:
- **yes** → apply the CUTs and TIGHTENs, move on.
- **skip this file** → change nothing, move on.
- **edit selection** → user vetoes specific lines; apply the rest.
- **stop** → end the audit; summarize what was done.

### Applying edits (both modes)

- For a CUT, delete the **whole** comment span, including a multi-line `/** … */`
  block and any now-orphaned blank line it leaves behind. Don't leave a dangling `*/`.
- For a TIGHTEN, replace the span with the exact shortened text from the report —
  same comment style (`//` vs `/** */`), just fewer lines.
- Never touch the code itself — only comment lines.
- After editing, it's fine to let the user's normal formatter/linter (prettier,
  ruff) reflow; don't run builds yourself unless asked.

## Step 4 — Wrap up

Summarize: files audited, comments cut/tightened/kept, files skipped, and how far
down the ranked list you got (so the user knows what's left if they bailed early).
In auto mode, point them at the review surface explicitly: **`git diff` to see
every change, `git checkout -- <file>` to revert any file** you were too
aggressive on. Don't commit — the user handles commits.

## Notes

- **Go and other low-comment languages** rarely trip the density path (Go's
  median comment ratio is ~1%); the volume path still catches big files. If a
  user specifically wants to audit a Go-heavy repo, lower with `--floor 0.05`.
- The pre-flight reads only line counts, never code — all judgment is in Step 2.
- Writes happen in Step 3. In the default auto mode they land without a per-file
  gate; the safety net is git (comment-only edits, reviewed via `git diff`,
  reverted via `git checkout`). Use per-file mode when you want a gate instead.
