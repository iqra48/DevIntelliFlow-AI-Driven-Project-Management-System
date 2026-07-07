# Requirement Categorization Feature

FastAPI backend feature for AI-assisted requirement categorization, FR/NFR classification, and document-based requirement extraction.

## Features

- Generate structured requirements from natural language input.
- Classify requirements as functional or non-functional.
- Process uploaded requirement files.
- Use Groq-hosted LLMs through a dedicated infrastructure layer.

## Project Structure

```text
Requirement Categorization Feature/
  app/
    domain/
      classification_pipeline/
    infrastructure/
      llm/
      logging/
    services/
      documents/
      orchestrator/
      requirements/
    main.py
  scripts/
    run_cli.py
  api_server.py
  requirements.txt
  .env.example
```

## Prerequisites

- Python 3.11 or newer
- Groq API key

## Setup

```powershell
cd "Requirement Categorization Feature"
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Update `.env` with your local configuration:

```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

## Run

```powershell
python api_server.py
```

Default API URL:

```text
http://127.0.0.1:8000
```

Interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

## API Endpoints

- `GET /health`
- `GET /health/groq`
- `POST /process`
- `POST /process_file`

## Supported Upload Formats

- PDF: `.pdf`
- Word: `.docx`
- Text: `.txt`
- CSV: `.csv`
- Excel: `.xlsx`, `.xls`

## Optional CLI

```powershell
python scripts/run_cli.py
```

## Environment Variables

| Variable | Description | Default |
| --- | --- | --- |
| `LLM_PROVIDER` | LLM provider used by this feature | `groq` |
| `GROQ_API_KEY` | Groq API key | Required |
| `GROQ_MODEL` | Groq model name | `llama-3.3-70b-versatile` |
| `LLM_CALL_TIMEOUT` | LLM call timeout in seconds | `60` |
| `GROQ_REQUEST_TIMEOUT` | Groq request timeout in seconds | `45` |
| `GROQ_RATE_LIMIT_MAX_RETRIES` | Groq retry count for rate limits | `3` |
| `SENTENCE_TRANSFORMER_ALLOW_DOWNLOAD` | Allow semantic model download on first run | `false` |
| `SENTENCE_TRANSFORMER_CACHE` | Local cache path for semantic models | `./.cache/sentence_transformers` |
