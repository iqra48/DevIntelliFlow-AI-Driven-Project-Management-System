# Test Case Generation

The test-case generator is designed for final, atomic FR/NFR requirements.

## Flow

1. `/process` or `/process_file` produces final atomic requirements.
2. `/generate_test_cases` accepts only final FR/NFR requirements.
3. The test-case pipeline validates input, plans coverage, generates cases,
   validates source and planner consistency, reviews unsupported invention, and
   returns the final response.

## Pipeline Stages

- Validate input requirements and mode.
- Planner: decide whether each requirement is testable and define coverage.
- Generator: create source-grounded draft test cases from planner coverage.
- Validation: discard structurally invalid or untraceable cases.
- Reviewer: filter unsupported invention from generated cases.
- Final response: return `SUCCESS`, `NEEDS_REVIEW`,
  `BLOCKED_MISSING_INFORMATION`, `FAILED_SCHEMA_VALIDATION`, `RATE_LIMITED`,
  or `PROVIDER_FAILED`.

## Human Review

Generated test cases are source-grounded AI-assisted QA drafts. The reviewer
filters unsupported invention, but human QA review is still expected before
execution. The system must not be treated as a fully automatic final approval
step.
