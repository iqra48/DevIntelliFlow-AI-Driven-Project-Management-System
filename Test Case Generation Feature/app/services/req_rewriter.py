# src/req_rewriter.py
import os
import logging
from typing import Optional
from app.shared.llm.call_llm import call_llm

logger = logging.getLogger(__name__)

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct-q4_K_M")

REWRITE_PROMPT = """
You are a senior software requirements engineer.

Rewrite the following single requirement sentence to be:
- One concise, testable, and unambiguous sentence.
- In canonical IEEE-style beginning with "The system shall ..." if that fits.
- Do NOT add explanation, examples, numbering, or JSON.
- Output ONLY the rewritten requirement sentence (single line).

Original:
\"\"\"{REQ}\"\"\""

Output:
"""

PREFIXES = [
    "Improved requirement:",
    "Improved Requirement:",
    "Rewritten requirement:",
    "Rewritten Requirement:",
    "Rephrased requirement:",
    "Rephrase:",
    "Output:",
    "Final requirement:",
    "Here is the rewritten requirement:",
    "Here is the improved requirement:",
]

async def rewrite_requirement_async(req_text: str, model: Optional[str] = None) -> str:
    if not req_text or not req_text.strip():
        return req_text

    prompt = REWRITE_PROMPT.format(REQ=req_text)
    raw = await call_llm(
        prompt=prompt,
        model=model or OLLAMA_MODEL
    )
    if not raw:
        return req_text

    s = " ".join(raw.strip().split())

    # Remove common hallucinated prefixes
    for p in PREFIXES:
        if s.lower().startswith(p.lower()):
            s = s[len(p):].strip()

    # Normalize unicode punctuation
    s = (
        s.replace("–", "-")
         .replace("—", "-")
         .replace("“", '"')
         .replace("”", '"')
    )

    # Strip wrapping quotes
    s = s.strip('"“”\'')

    # Ensure final period
    if s and not s.endswith("."):
        s += "."

    return s

def rewrite_requirement(req_text: str, model: Optional[str] = None) -> str:
    import asyncio as _asyncio
    return _asyncio.run(rewrite_requirement_async(req_text, model=model))

