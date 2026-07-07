# Demo Runbook

This runbook starts the FastAPI backend and Streamlit UI for a local demo.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env`, then replace the placeholder keys with local
secrets. Keep real API keys in `.env` only.

## Start Backend

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Start Streamlit UI

```powershell
streamlit run ui/streamlit_app.py
```

## Health Checks

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/health/groq
Invoke-RestMethod http://127.0.0.1:8000/health/cerebras
```

`/health/groq` should return a configured result or a clear error.
`/health/cerebras` should return a configured result or `NOT_CONFIGURED`.

## Process Example

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/process `
  -ContentType "application/json" `
  -Body '{"text":"User can log in to the system."}'
```

## Generate Test Cases Example

Sample payload:

```json
{
  "requirements": [
    {
      "id": "REQ_1",
      "requirement": "User can log in to the system.",
      "classification_type": "FR"
    }
  ],
  "project_context": "Web-based requirement management system for business users.",
  "mode": "mvp_fast"
}
```

PowerShell:

```powershell
$payload = @{
  requirements = @(
    @{
      id = "REQ_1"
      requirement = "User can log in to the system."
      classification_type = "FR"
    }
  )
  project_context = "Web-based requirement management system for business users."
  mode = "mvp_fast"
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/generate_test_cases `
  -ContentType "application/json" `
  -Body $payload
```

curl:

```bash
curl -X POST http://127.0.0.1:8000/generate_test_cases \
  -H "Content-Type: application/json" \
  -d '{"requirements":[{"id":"REQ_1","requirement":"User can log in to the system.","classification_type":"FR"}],"project_context":"Web-based requirement management system for business users.","mode":"mvp_fast"}'
```

## Status Values

- `SUCCESS`: source-grounded draft test cases were returned.
- `NEEDS_REVIEW`: output exists or was filtered, and human QA review is required.
- `BLOCKED_MISSING_INFORMATION`: requirement needs clarification before cases can be generated.
- `FAILED_SCHEMA_VALIDATION`: request or model output failed structural validation.
- `RATE_LIMITED`: provider rate limit prevented completion.
- `PROVIDER_FAILED`: provider failure prevented completion.

Generated test cases are AI-assisted QA drafts, not final approved QA artifacts.
Human QA review is expected before execution.

## Final Smoke Checklist

- Backend starts.
- UI starts.
- `/health` returns OK.
- `/health/groq` returns configured result or clear error.
- `/health/cerebras` returns configured result or `NOT_CONFIGURED`.
- `/process` returns final requirements.
- UI only allows final FR/NFR for test-case generation.
- `/generate_test_cases` returns status and budget metadata.
- Provider metadata appears in UI.
- No "Approved" or "Accepted Review" wording appears.
- Draft/human-review warning appears.
