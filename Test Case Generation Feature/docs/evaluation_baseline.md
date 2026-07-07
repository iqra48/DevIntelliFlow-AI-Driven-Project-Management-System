# Evaluation Baseline

The accepted hybrid-stage structural and manual review baseline is:

```text
total_eval_items=45
schema_pass_rate=1.0
requirement_id_mismatch_total=0
coverage_item_mismatch_total=0
unsupported_invention_rate=0.022222222222222223
rate_limit_failures=0
provider_failures=0
phase12_gate_passed=true
```

Provider signature for all 45 items:

```text
planner=cerebras|generator=groq|reviewer=cerebras
```

This baseline means the hybrid strategy passed the required gate, including
manual unsupported-invention review. It does not mean generated cases are final
approved QA artifacts. Human QA review is still expected before execution,
especially for rows marked `NEEDS_REVIEW`, assumptions, warnings, and cases
marked as needing human edits.
