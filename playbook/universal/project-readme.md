---
tool: readme
scope: universal
tier: optional
summary: "README.md: one-sentence opener, flow diagram, runnable commands, layout table"
targets: ["README.md"]
---

# README.md

## What

The README says what the project is in one or two sentences, shows how data or
control flows through it in a small text diagram, then gives commands that run.
Layout, deeper docs and open items come after.

## Why

- Commands with their result in a trailing comment are the quickest proof the
  repo works, and they break loudly when they stop working.
- Present-tense status ("still backfilling", "not decided yet") is false the
  moment it changes. Dated history and a command that checks the current
  state stay true.

## Config

Canonical README **skeleton**. Fill the `{{placeholders}}` and drop the
optional sections that don't apply. tooling-sync checks that a README *covers
these sections*, not that it matches line for line.

````markdown
# {{project}}

{{What it is, what it's built with, and what it deliberately leaves out, in one or two sentences.}}

```text
{{input}} ──{{step}}──▶ {{this repo}} ──▶ {{output}}
```

## {{Run | Install | Play}}

```sh
{{command}}        # {{what you get back}}
{{command}}        # {{what you get back}}
```

## Layout

|Path|What|
|---|---|
|`{{dir}}/`|{{what lives there}}|

## Open items

1. **{{The constraint.}}** {{Why it is open and what decides it.}}
````

## Gotchas

- **Prose is not a literal diff target.** The wording belongs to the repo.
- **No diagram for a single-file tool** or a library with one entry point. Skip
  it rather than draw one box.
- **Layout only past about five top-level paths.** A repo you can read with
  `ls` doesn't need the table.
- **No badges beyond one CI badge, no emoji in headings.**
- **Split by audience at about 400 lines.** Move data, provider or runbook
  detail into `docs/DATA.md`, `docs/RUNBOOK.md` and so on, and link them from a
  two-column `| | |` table.
- Pair with [contributing](./contributing.md). The README covers how the project runs;
  CONTRIBUTING covers how changes land.
