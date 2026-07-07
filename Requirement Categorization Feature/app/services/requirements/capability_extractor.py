import re

from app.infrastructure.llm.call_llm import call_llm
from app.infrastructure.llm.output_validation import guarded_llm_call


def normalize_capabilities(capabilities):

    normalized = []

    for c in capabilities:
        if c.get("type") == "behavior":
            action = c.get("action")

            if action:
                parts = re.split(r"\band\b|\bor\b|,", action)

                for p in parts:
                    p = p.strip()
                    if len(p.split()) >= 2:
                        normalized.append(p)

        elif c.get("type") == "quality":
            constraint = c.get("constraint")

            if constraint:
                parts = re.split(r"\band\b|\bor\b|,", constraint)

                for p in parts:
                    p = p.strip()
                    if len(p.split()) >= 2:
                        normalized.append(f"QUALITY_CONSTRAINT: {p}")

    return normalized


async def extract_capabilities(text: str):

    system_prompt = """
You are a software requirement semantic analyzer.

Extract EVERY system capability and EVERY quality constraint.

A capability describes an action the system performs.
A quality constraint describes how well, how fast, how secure, or how reliably the system operates.

CRITICAL RULES

1. Every action must become a behavior capability.
2. Every performance, security, availability, reliability, usability, or scalability statement must become a quality capability.
3. Never ignore quality constraints.
4. If a sentence contains both behavior and quality, extract both.
5. Do not merge actions or constraints.

Return ONLY JSON:

{
 "capabilities":[
  {
   "type":"behavior",
   "actor":"...",
   "action":"..."
  },
  {
   "type":"quality",
   "quality_type":"...",
   "constraint":"..."
  }
 ]
}
"""

    user_prompt = f"""
Input description:
{text}
"""

    data = await guarded_llm_call(
        lambda prompt, system: call_llm(
            prompt=prompt,
            system_prompt=system,
            num_predict=300
        ),
        user_prompt,
        system_prompt,
        {}
    )

    return data.get("capabilities", [])
