#!/usr/bin/env python
"""
Start the FastAPI server for the Requirement Categorization Feature.

Usage:
    python api_server.py
"""

import importlib
import os
import sys

from app.main import app


def check_uvicorn() -> bool:
    try:
        importlib.import_module("uvicorn")
        return True
    except ImportError:
        return False


if __name__ == "__main__":
    if not check_uvicorn():
        print("Error: uvicorn is not installed")
        print("Run: python -m pip install -r requirements.txt")
        sys.exit(1)

    try:
        import uvicorn

        host = os.getenv("REQ_API_HOST", "127.0.0.1")
        port = int(os.getenv("REQ_API_PORT", "8000"))

        print("\n" + "=" * 70)
        print("REQUIREMENT CATEGORIZATION FEATURE SERVER")
        print("=" * 70)
        print(f"\nAPI:  http://{host}:{port}")
        print(f"Docs: http://{host}:{port}/docs")
        print("\n" + "=" * 70 + "\n")

        uvicorn.run(app, host=host, port=port, log_level="info")
    except KeyboardInterrupt:
        print("\nServer stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
