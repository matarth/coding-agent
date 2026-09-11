---

name: bug-fix
description: Reproduce and fix a concrete production bug using a test-driven workflow.
Use when a bug report provides concrete identifying data such as user ID, project ID, request ID, entity ID, or similar values,
and the expected correct behavior is known. The bug may be described directly or provided through an Asana task.
Uses production data through the read-only database tool to reproduce the bug in tests before changing application code.
---

Fix the reported bug using a strict **reproduce → fail → fix → pass** workflow.

Do not start modifying production code until the bug has been reproduced by an automated test.

## Activation requirements

Use this skill only when both of the following are available:

1. **Concrete reproduction data** identifying an affected production case, such as:

    * user ID,
    * project ID,
    * account ID,
    * entity ID,
    * email,
    * external identifier,
    * or another value that can be used to locate the relevant production state.

2. **Expected correct behavior** describing what should happen instead of the observed buggy behavior.

The bug report may be provided directly as text or through an Asana task.

If an Asana link is provided, fetch the task using the Asana MCP server in read-only mode and extract:

* the reported behavior,
* the expected behavior,
* concrete reproduction identifiers,
* relevant comments or additional reproduction information.

Never modify or comment on the Asana task unless explicitly asked.

## Workflow

### 1. Understand the bug

Extract from the bug report:

* the observed incorrect behavior,
* the expected correct behavior,
* all concrete identifiers and reproduction data,
* any known preconditions,
* the relevant application workflow.

Do not assume missing production state when it can be verified using the read-only database tool.

### 2. Inspect the production state

Delegate this step to the `investigator` subagent (via the `Task` tool):
give it the identifiers and preconditions extracted in step 1, and ask it
to find the exact production records and relationships needed to
reproduce the bug (entities, relationships, statuses, configuration,
historical/dependent records, and any values influencing the affected
code path). `Investigator` returns only what matters.

The database must be treated as strictly read-only regardless of who
queries it.

Use the records `investigator` returns as the source of truth for the
regression test fixtures in step 4. Do not copy secrets, credentials,
tokens, or unrelated sensitive data into tests.

### 4. Create a regression test

Create an automated regression test that reproduces the production bug.

Populate the test database with the relevant production-derived state discovered through `db-readonly`.

Recreate only the state necessary to trigger the bug while preserving the relationships and conditions that make the production case significant.

Prefer normal test fixtures, factories, builders, or persistence mechanisms already used by the project instead of introducing a new test setup style.

Avoid coupling the test unnecessarily to production-specific identifiers. Preserve exact production values only when those values are relevant to reproducing the bug.

The assertions must describe the **expected correct behavior**, not the current buggy behavior.

### 5. Verify the failing reproduction

Run the new regression test before modifying production code.

The test must fail.

Inspect the failure and verify that it corresponds to the behavior observed in production.

A valid reproduction means that:

* the tested scenario matches the supplied production case,
* the test reaches the intended code path,
* the failure represents the reported bug,
* the assertion describes the expected correct state.

If the test fails for an unrelated reason, fix the test setup and run it again.

If the test unexpectedly passes, do not modify production code. Investigate the difference between the test setup and the real production state until the bug can be reproduced or a concrete explanation is found.

Do not weaken or alter the expected assertion merely to obtain a failing test.

### 6. Fix the bug

Once the regression test reliably reproduces the bug, implement the smallest reasonable production-code change that fixes the underlying cause.

Prefer fixing the root cause over special-casing the supplied production identifiers or exact test data.

Do not:

* hard-code production IDs or values,
* add a workaround that only fixes the provided example,
* change unrelated behavior,
* perform unrelated refactoring,
* modify the regression test to accommodate an incorrect implementation.

Follow the existing architecture, conventions, naming, and patterns of the surrounding application.

### 7. Verify the fix

Run the regression test again.

The test must now pass.

If it still fails:

1. inspect the failure,
2. determine whether the implementation or reproduction assumptions are incorrect,
3. adjust the implementation as necessary,
4. rerun the test.

Repeat the cycle until the regression test passes for the correct reason.

Do not change the expected behavior of the regression test unless new evidence proves that the original expectation was incorrect.

### 8. Review test coverage of the fix

Delegate this step to the `test-coverage-reviewer` subagent (via the `Task`
tool): give it the diff of the fix together with the regression test added
in step 4, and ask it to confirm the fix's realistic edge cases are
covered by tests and flag any gap.

If it reports an uncovered edge case that's realistically reachable, add a
test for it, following the same test conventions used in step 4. Do not
change production code based on this step unless the missing coverage
reveals the fix itself is incomplete.

### 9. Check for regressions

After the regression test passes, run the smallest relevant existing test suite covering the affected area.

Where appropriate, also run the project's relevant static analysis, linting, or validation tools.

Verify that the fix does not break related existing behavior.

If an existing test fails because the expected behavior genuinely changed as part of the bug fix, inspect it carefully before modifying it. Do not update existing assertions merely to make the suite green.

## Test quality

The regression test should represent the general bug condition rather than only the exact production record.

Production data is evidence used to understand and reproduce the failure; it is not an excuse to hard-code a one-off solution.

When possible, the final test should make it clear:

* what state triggers the bug,
* what operation is performed,
* what behavior is expected,
* what regression it protects against.

Do not add unrelated scenarios to the regression test.

## Safety

* Never use production credentials or secrets in tests.
* Do not copy unnecessary personal or sensitive production data into the repository.
* Do not make unrelated production changes while investigating the bug.

## Completion criteria

The bug fix is complete only when:

1. the concrete production case has been investigated,
2. the relevant production state has been understood,
3. an automated test reproduces the bug,
4. the test was observed failing for the expected reason before the fix,
5. the underlying code was fixed,
6. the regression test passes after the fix,
7. `test-coverage-reviewer` confirmed the fix's realistic edge cases are
   covered by tests (or any gap it found was closed),
8. relevant existing tests still pass.

When reporting the result, briefly state:

* the root cause,
* what production state triggered it,
* which regression test was added,
* how the implementation was changed,
* what `test-coverage-reviewer` found and any test added as a result,
* what tests or checks were run.
