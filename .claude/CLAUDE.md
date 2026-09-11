## What (not) to do

* Unless explicitly asked otherwise, do not commit changes.
* Unless explicitly asked otherwise, do not push anything to a remote repository.
* When asked to create a new branch for a new piece of work, create and switch to a dedicated branch before making changes. Never make feature changes directly on `dev`, `main`, `master`, or another shared branch.
* Never push directly to protected branches.
* Never create tags unless explicitly asked.
* When writing a commit message, keep it short and to the point. Describe what changed, not the circumstances or history behind the change.
* Unless explicitly asked otherwise, use the Asana MCP server strictly as a read-only tool.
* Unless explicitly asked otherwise, use `gh` strictly for read-only operations.
* Never run `kubectl`, `k9s`, or any other command that interacts with a Kubernetes cluster. If Kubernetes interaction is required, ask a human to run the command.
* Never modify unrelated code just because you notice an opportunity to clean it up.
* Do not introduce or update dependencies unless they are necessary for the requested change.
* Do not modify generated files manually unless the repository explicitly expects them to be edited.
* Never expose, print, commit, or otherwise leak secrets, credentials, tokens, or sensitive configuration.
* When creating a new file, always add it to git.

## Coding standards

* When implementing a new feature, first inspect the existing codebase for implementations of similar use cases or responsibilities, such as creating an endpoint, adding a service, introducing an email template, or handling a comparable workflow.
* Use the closest existing implementation as a reference and follow its structure, conventions, naming, patterns, and level of abstraction as closely as reasonably possible.
* Prefer consistency with the existing codebase over introducing a new style or architecture unless there is a clear reason to deviate.
* Prefer simple designs that respect SOLID principles where they are applicable. Do not introduce abstractions solely for the sake of satisfying a principle.
* Use established design patterns when they naturally fit the problem and improve the solution. Do not introduce a design pattern where a simpler implementation is sufficient.
* Prefer clear, straightforward, and easy-to-read code over clever, overly compact, or sophisticated solutions.
* Optimize for maintainability and immediate comprehension by another developer, even if that means writing a few more lines of code.
* Avoid unnecessary abstractions, tricks, indirection, or "smart" logic when a simpler implementation communicates the intent more clearly.
* Keep the scope of a change as small as reasonably possible. Do not refactor unrelated code as part of implementing a feature or fixing a bug.
* Preserve existing public behavior and backwards compatibility unless the requested change explicitly requires breaking it.
* Before introducing a new helper, abstraction, utility, service, or dependency, check whether the codebase already contains something suitable.
* Follow the repository's existing naming, formatting, architecture, and testing conventions instead of imposing generic best practices that conflict with the project.

## Comments

* Avoid comments that merely restate what the code already says. Prefer self-explanatory code with clear naming and straightforward structure.
* Add a comment when it explains something that is not obvious from the code itself, such as a non-obvious decision, workaround, external constraint, or behavior that may otherwise appear incorrect or unnecessary.
* Keep comments short, specific, and focused on the "why", not the "what".

## Testing and validation

* When changing existing behavior, inspect the existing tests covering that behavior before implementing the change.
* Add or update tests for new or changed behavior when the repository has an established testing approach for it.
* Follow the style and structure of nearby tests rather than introducing a different testing approach.
* Run the smallest relevant test suite, static analysis, formatter, or linter needed to validate the change when those tools are available locally.
* Do not change production code merely to make an incorrectly written test pass.
* Never suppress, ignore, or work around a failing test, static-analysis error, or linting error without understanding the cause.
* If validation cannot be completed, clearly state what was not verified and why.

## Working with existing code

* Read enough surrounding code to understand the existing design before making changes.
* Do not assume how an internal API, framework abstraction, or project-specific convention works when it can be verified from the repository.
* Prefer modifying an existing abstraction over creating a parallel one when the existing abstraction already represents the same responsibility.
* Avoid speculative generalization. Implement the requirements that exist now rather than abstractions for hypothetical future requirements.

## Implementation
* When you create a new file that is part of the requested change, always add it to the Git index with `git add` so it is tracked. Do not leave required files untracked.
* Do not add generated files, temporary files, local configuration, secrets, or other files that are intentionally excluded by the repository.

