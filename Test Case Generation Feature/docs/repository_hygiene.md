# Repository Hygiene

## Secrets

API keys stay in `.env` only. `.env.example` is safe to commit because it uses
placeholders:

```text
GROQ_API_KEY=your_groq_key_here
CEREBRAS_API_KEY=your_cerebras_key_here
```

Do not commit real API keys or local secret files.

## Evidence

Final accepted baseline reports should be preserved. Dirty retry folders and
temporary provider-failure reports should not be used as final evidence.

## Ignored Clutter

Do not commit pycache folders, `.pyc` files, local logs, Streamlit/FastAPI temp
files, pytest cache, mypy cache, or ruff cache.

Accepted documentation should remain tracked, including:

- `docs/test_case_generation.md`
- `docs/provider_strategy.md`
- `docs/evaluation_baseline.md`
- `docs/demo_runbook.md`
