# Provider Strategy

The accepted production strategy is hybrid stage routing.

## Production Profile

- Planner: Cerebras `gpt-oss-120b`
- Generator: Groq `llama-3.1-8b-instant`
- Reviewer: Cerebras `gpt-oss-120b`

Expected provider signature:

```text
planner=cerebras|generator=groq|reviewer=cerebras
```

## Environment Profile

```text
LLM_PROVIDER=groq
LLM_STRICT_PROVIDER=false
LLM_PROVIDER_ROUTING_MODE=stage
LLM_PLANNER_PROVIDER=cerebras
LLM_GENERATOR_PROVIDER=groq
LLM_REVIEWER_PROVIDER=cerebras
LLM_FALLBACK_POLICY=rate_limit_only
LLM_ALLOWED_FALLBACKS=cerebras
CEREBRAS_MODEL=gpt-oss-120b
CEREBRAS_MIN_SECONDS_BETWEEN_CALLS=45
LLM_CALL_TIMEOUT_SECONDS=120
TEST_CASE_CACHE_ENABLED=true
```

API keys are environment secrets and must not be committed to repository files.

## Operational Notes

Cerebras calls are paced at provider level. The final clean evaluation needed
45 seconds between Cerebras calls for stability. Provider selection remains
environment-based; the UI does not expose a provider selector.
