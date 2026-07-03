# RULES.md

## General

* Read `PROJECT_SPEC.md`, `TODO.md`, and this file before making any code changes.
* Follow the architecture defined in `PROJECT_SPEC.md`.
* Never ignore these documents.
* Never change the project architecture without explicit approval.

## Implementation Rules

* Implement only the current task.
* Do not implement future features.
* If a future feature is required, create a placeholder interface rather than implementing it.
* Keep pull-request-sized changes.
* Avoid introducing unnecessary dependencies.

## Code Quality

* Follow SOLID principles.
* Follow DRY.
* Prefer readability over clever code.
* Write meaningful comments only where necessary.
* Use type hints everywhere possible.
* Do not leave TODO comments unless explicitly instructed.

## Testing

Every feature must include:

* Unit tests
* Integration tests where appropriate
* Edge case handling

Do not mark a task complete if tests fail.

## Documentation

Whenever a feature is completed:

* Update README if required.
* Update API documentation.
* Update architecture documentation if changes affect it.

## Logging

Every API endpoint should include:

* Structured logging
* Request ID
* User ID (if authenticated)
* Duration
* Error logging

## Security

Never:

* Hardcode secrets
* Disable validation
* Disable authentication
* Expose stack traces

Validate all user input.

## Git

Treat every completed task as a separate commit.

Suggested commit message format:

feat(...)
fix(...)
refactor(...)
test(...)
docs(...)

## Completion Checklist

Before considering a task finished:

* Code compiles
* Tests pass
* Lint passes
* Documentation updated
* No duplicated code
* No obvious security issues
* No unnecessary complexity

If any item fails, continue improving before marking the task complete.

