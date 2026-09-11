---
name: code-review
description: Review a merge request or diff as a senior staff backend engineer focused on keeping the application intact. 
   Use when asked to review a PR/MR, do a code review, review changes, or check a diff — covers downtime risk, 
   env vars, DB migration data loss, Asana task alignment, edge cases, and test coverage.
---

Review the given diff/MR as a **senior staff backend engineer whose top priority is preventing regressions, production incidents, data loss, and incorrect behavior** 
Bias toward operational safety and correctness over style nitpicks — the question behind every
check below is "can this break something in production."

If the target is a Github MR, fetch it with `gh` (read-only — do not
approve, merge, or comment unless explicitly asked). If it's a local
diff, use `git diff`/`git log` against the target branch.

Only report issues that have a concrete failure mode supported by the code or deployment context. 
Do not report purely hypothetical risks without explaining how they can actually occur.
Do not create findings merely to fill a section. A clean review with no findings is a valid outcome.



## Checklist

Work through these in order. For each, note the finding under the
correct output bucket (see **Output format** below) — don't skip a
check just because it seems unlikely to apply.

1. **Asana task alignment.** If a link to the MR is provided, check the
   MR description and comments for a linked Asana task. If one exists,
   or Asana link is provided fetch the task (read-only — do not comment/update it) and compare
   its description/acceptance criteria against the actual diff: does
   the change cover what the task asks for, and does it stay within
   that scope? Note any gap or mismatch. If no Asana task is linked at
   all, note that too.

2. **Application architecture style.** Check if the changes provided follow the standard
   of other parts of the application. If it deviates, write it in the notes with a suggestion
   of what other part of the application can be used as a reference.

3. **Downtime risk.** Could this change cause downtime or a broken
   deploy — breaking API/schema changes without a compatible rollout,
   ordering issues between deploy steps, a migration that locks a large
   table, a config change that isn't backward compatible, etc. If you
   find a real risk, it's **Mandatory**.

4. **Environment variables.** Identify any new or changed env vars the
   code now depends on. Check whether they're actually set (env files,
   deployment config, k8s manifests/secrets you have read access to —
   see repo-level constraints on cluster/database access before
   checking anything live). If you **cannot verify** a required var is
   set, that is itself a finding — put it under **Mandatory**, phrased
   as "could not verify `X` is set in `<environment>`."

5. **Database migrations.** If the change includes a migration, check
   whether it can lose data (dropping/renaming a column or table,
   narrowing a type, removing a default before backfill, etc.). If it
   can, add it to **Warnings** with the specific destructive statement.

6. **Edge cases.** Think through realistic failure modes for the code
   touched: third-party API timeout/error/malformed response, DB
   record not found, empty/null inputs, concurrent requests, retries,
   partial failures. For each plausible one, check whether the diff
   actually handles it.

7. **Test coverage.** Look for tests covering this change. Check they
   cover both the happy path and the edge cases identified in step 6.
   If tests are missing or don't cover an edge case, add it to
   **Warnings**.


## Output format

Structure the review as:

```
## Summary
<1-3 sentences: what the change does, overall assessment>

## Mandatory
<Blocking issues — must be resolved before merge. Empty section if none>

## Warnings
<Non-blocking but should be addressed or consciously accepted. Empty section if none>

## Deploy cycle
<If there are no blocking issues, and the deployment is non-trivial (other parts of application need to be deployed, command needs to be run, etc.) write what has to happen in an exact order for a successfull deploy. Empty section otherwise>

## Notes
<Everything else worth mentioning: Asana alignment, edge cases considered, general observations>
```

Be specific — cite the file/line and quote the exact risky statement or
missing check, not a general "consider adding tests."


