from typing import List

from app.infrastructure.llm.call_llm import call_llm
from app.infrastructure.llm.output_validation import guarded_llm_call


async def split_intents(text: str) -> List[str]:
    """
    Production semantic intent splitter.

    Extracts independent system intents from natural language.
    """

    system_prompt = """
You are a software requirements decomposition engine.

Your task is to extract ALL independent system capabilities and quality constraints.

Each output must represent exactly ONE capability or ONE quality constraint.

CRITICAL RULES

1. Every capability mentioned in the input must be preserved.
2. Do NOT merge multiple actions into a single capability.
3. If multiple actions appear in a sentence, output each action separately.
4. Preserve the original action verbs when possible.
5. Do not summarize or generalize capabilities.

Examples:

Input:
Customers can browse products, add items to their cart, and place orders.

Output:
{
 "intents":[
  "browse products",
  "add items to cart",
  "place orders"
 ]
}

Input:
Users upload documents and delete files while the system stores them securely.

Output:
{
 "intents":[
  "upload documents",
  "delete files",
  "store documents securely"
 ]
}

Return JSON only.
"""

    user_prompt = f"""
Input:
{text}
"""

    data = await guarded_llm_call(
        lambda prompt, system: call_llm(
            prompt=prompt,
            system_prompt=system,
            num_predict=200
        ),
        user_prompt,
        system_prompt,
        {}
    )

    intents = data.get("intents", [])

    cleaned = []

    for i in intents:
        if isinstance(i, str) and len(i.split()) >= 2:
            cleaned.append(i.strip())

    return cleaned
