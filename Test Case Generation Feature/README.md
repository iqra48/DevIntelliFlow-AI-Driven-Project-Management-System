# Test Case Generation Feature

This feature provides an AI-assisted pipeline for generating structured test cases from finalized software requirements. It supports both functional and non-functional requirements and includes an API server plus a demo interface for local testing.

## Features

- Extract and normalize atomic requirements from raw requirement text.
- Classify requirements as FR/NFR and prepare them for test generation.
- Generate source-grounded test case drafts with planning and validation stages.
- Review outputs for unsupported invention and structural issues.
- Run locally through a FastAPI server or a simple interactive demo.

## Project Structure

```text
Test Case Generation Feture/
  app/
    config.py
    main.py
    core/
    domain/
    orchestrator/
    services/
    shared/
  docs/
  eval/
  logs/
  scripts/
  tests/
  ui/
  api_server.py
  run_system.py
  requirements.txt
  .env.example
```

## Prerequisites

- Python 3.11 or newer
- Ollama or another configured LLM provider
- Required Python dependencies from requirements.txt

## Setup

```powershell
cd "Test Case Generation Feture"
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Update `.env` with your local configuration as needed.

## Run the API

```powershell
python api_server.py
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Interactive API docs:

```text
http://127.0.0.1:8000/docs
```

## Run the Demo

```powershell
python run_system.py
```

## Notes

- Generated test cases are AI-assisted drafts and should still be reviewed by a human QA engineer.
- The pipeline is designed to avoid unsupported invention by validating generated content against the source requirements.
