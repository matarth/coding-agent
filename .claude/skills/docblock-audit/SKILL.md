---
name: docblock-audit
description: Audit docblocks (PHPDoc, JSDoc/TSDoc, Python docstrings) in a path against what the code actually does, skip ones already verified recently, and refresh a browsable HTML report. Use when asked to check/audit docblocks, verify documentation accuracy, or refresh the docblock report.
---

Audit docblocks in the given path against actual code behavior, tracking
per-docblock state across runs so unchanged, recently-checked docblocks
aren't re-verified every time.

Only report and record what the code actually shows. Do not create
findings to fill out the report — a docblock that matches the code is a
clean `match`, not an excuse to invent nitpicks.

## Scope

Take the target path/glob from the request (default: the whole repo,
excluding `vendor/`, `node_modules/`, and test directories — those
document test behavior, not the public contract). Take an optional
max-age override (default **180 days**) for how long a `match` verdict
stays valid without a re-check.

## 1. Discover docblocks

`Grep`/`Glob` the scope for doc comments, by file extension:

* `.php` — `/** ... */` immediately above a function/method/class.
* `.js`/`.ts`/`.jsx`/`.tsx` — `/** ... */` (JSDoc/TSDoc) above a
  function/method/class.
* `.py` — the triple-quoted string as the first statement of a
  `def`/`class` body.

For each one, capture: file path, symbol name, starting line, the
docblock text, and the body of the code it documents.

## 2. Load the report state

Read `.claude/tools/docblock_checker/reports/docblock_report.json`
(create it as `{"entries": {}}` if it doesn't exist yet). Entries are
keyed `"<file>#<symbol>"` and hold `docblock_hash`, `last_checked`,
`status`, and `findings` from the last check.

## 3. Decide what needs (re-)checking

For each docblock found in step 1, compute
`docblock_hash = sha256(docblock text + code body text)` and compare
against the stored entry (if any). It needs a check when:

* there is no stored entry for it (new docblock), **or**
* the computed hash differs from the stored one (docblock or code
  changed since the last check), **or**
* `last_checked` is older than the max-age threshold (default 180
  days) — a periodic re-check even when nothing changed.

Anything else is skipped — its existing entry carries forward unchanged
into the updated report.

## 4. Delegate to docblock-checker

Group the docblocks that need checking **by file**. For each file, make
one `Task` call to the `docblock-checker` subagent with that file path
and the list of symbols (with their docblock text) to check. Parse its
JSON response.

Do not check docblocks yourself inline — always go through the
subagent, so the main conversation only sees clean per-file verdicts,
not the exploration behind them.

## 5. Merge and persist

For each symbol the subagent returned a verdict for, update its entry:
new `docblock_hash`, `last_checked` set to now, and the returned
`status`/`findings`. Remove entries for symbols/files no longer present
in the codebase. Write the updated JSON back to
`.claude/tools/docblock_checker/reports/docblock_report.json`.

## 6. Render the report

Run `.claude/tools/docblock_checker/generate_report.py` — it reads the
JSON report and (re)writes
`.claude/tools/docblock_checker/reports/docblock_report.html` as a
self-contained page (the data is inlined, so it opens directly from
disk, no server needed).

## 7. Summarize

Report back: how many docblocks were checked this run vs. skipped as
already up to date, the count per status, any `mismatch`/`partial`
findings worth calling out by name, and the path to the HTML report.
