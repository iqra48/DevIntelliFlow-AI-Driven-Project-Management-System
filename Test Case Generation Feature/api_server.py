#!/usr/bin/env python
"""
Start the FastAPI server for Requirement Intelligence API

Usage:
    python api_server.py

The server will start on http://localhost:8000
API docs available at http://localhost:8000/docs
"""

import importlib
import sys

from app.main import app


def check_uvicorn():
    try:
        importlib.import_module("uvicorn")
        return True
    except ImportError:
        return False


if __name__ == "__main__":
    if not check_uvicorn():
        print("❌ Error: uvicorn not installed")
        print("   Run: python -m pip install uvicorn")
        exit(1)

    try:
        import uvicorn

        print("\n" + "=" * 70)
        print("REQUIREMENT INTELLIGENCE API SERVER")
        print("=" * 70)
        print("\nAPI will be available at: http://localhost:8000")
        print("API Docs:                 http://localhost:8000/docs")
        print("ReDoc:                    http://localhost:8000/redoc")
        print("\nTo use Streamlit UI, run in another terminal:")
        print("   streamlit run ui/streamlit_app.py")
        print("\n" + "=" * 70 + "\n")

        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n\nServer stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
