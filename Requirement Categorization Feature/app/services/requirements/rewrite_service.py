from app.services.requirements.req_rewriter import rewrite_requirement_async
from app.infrastructure.llm.call_llm import call_llm
import json
import logging
import os

logger = logging.getLogger(__name__)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct-q4_K_M")


async def rewrite_requirement(text: str) -> str:
    """
    Service wrapper for IEEE-style rewriting.
    """
    return await rewrite_requirement_async(text)


async def rewrite_requirements_batch(requirements: list[str]) -> list[str]:
    """
    Production-grade batch rewrite in single LLM call.
    
    - Handles multiple requirements efficiently
    - Returns one call instead of N calls
    - Deterministic JSON parsing
    - Fallback to original if parsing fails
    """
    
    if not requirements:
        return []
    
    # Number the requirements for clarity
    numbered = "\n".join(f"{i+1}. {r}" for i, r in enumerate(requirements))
    
    system_prompt = """You are a senior software requirements engineer.

Rewrite each requirement into:
- One concise, testable IEEE-style sentence.
- Begin with "The system shall ..." where appropriate.
- Do NOT add explanations, examples, or new functionality.
- If vague, rewrite generically without inventing context.

Return ONLY valid JSON in this exact format:

{
  "rewritten": {
    "1": "Rewritten sentence",
    "2": "Rewritten sentence",
    "3": "Rewritten sentence"
  }
}"""

    user_prompt = f"""Rewrite each of these requirements:

{numbered}"""

    try:
        raw = await call_llm(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=OLLAMA_MODEL
        )
        
        cleaned = raw.strip()
        
        # Remove markdown code block markers if present
        if "```" in cleaned:
            start = cleaned.find("```") + 3
            end = cleaned.rfind("```")
            if start < end:
                cleaned = cleaned[start:end]
                if cleaned.strip().lower().startswith("json"):
                    cleaned = cleaned.strip()[4:].strip()
        
        # Find the JSON object
        brace_pos = cleaned.find("{")
        if brace_pos == -1:
            logger.warning("No JSON object found in batch rewrite response, using fallback")
            return requirements
        
        cleaned = cleaned[brace_pos:]
        data = json.loads(cleaned)
        
        rewritten_map = data.get("rewritten", {})
        
        result = []
        for i in range(len(requirements)):
            text = rewritten_map.get(str(i + 1))
            if not text or not text.strip():
                # Fallback: use original if rewritten missing
                result.append(requirements[i])
            else:
                # Clean up the rewritten text
                cleaned_text = text.strip()
                if cleaned_text and not cleaned_text.endswith("."):
                    cleaned_text += "."
                result.append(cleaned_text)
        
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in batch rewrite: {e}, using fallback")
        return requirements
    except Exception as e:
        logger.error(f"Batch rewrite failed: {e}, using fallback")
        return requirements
