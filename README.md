# DevIntelliFlow AI-Driven Project Management System

DevIntelliFlow is an AI-assisted project management system that supports:
- requirement categorization and FR/NFR classification,
- automated test case generation from structured requirements,
- a frontend project management interface.

## Repository structure

- `Frontend/` — Next.js frontend for project management and UI interaction.
- `Requirement Categorization Feature/` — Python backend for requirement extraction, classification, and Groq-based LLM integration.
- `Test Case Generation Feature/` — Python backend for generating source-grounded test cases from requirements.

## Added documentation

- `Requirement Categorization Feature/README.md`
- `Test Case Generation Feature/README.md`

## Getting started

1. Clone the repo:
   ```powershell
   git clone https://github.com/iqra48/DevIntelliFlow-AI-Driven-Project-Management-System.git
   cd DevIntelliFlow-AI-Driven-Project-Management-System
   ```

2. Explore each feature directory for its own setup and README.

## Notes

- This repository is organized into separate feature modules for clean separation of concerns.
- Each feature has its own `requirements.txt` and README for local setup.
- Add your environment variables locally and avoid committing secrets.
