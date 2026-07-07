import json
import re
from typing import Dict, Any


class OutputValidationError(Exception):
    pass


def extract_json(text: str) -> str:
    """
    Extract first JSON object from LLM response.
    """

    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        raise OutputValidationError("No JSON object found in LLM response")

    return match.group(0)


def parse_json(text: str) -> Dict[str, Any]:
    """
    Safe JSON parsing with extraction.
    """

    try:
        json_text = extract_json(text)
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        raise OutputValidationError(f"Invalid JSON: {e}")


def validate_fields(data: Dict[str, Any], allowed_fields: Dict[str, set]):
    """
    Validate JSON fields against allowed values.
    """

    for field, allowed in allowed_fields.items():

        if field not in data:
            raise OutputValidationError(f"Missing field: {field}")

        if data[field] not in allowed:
            raise OutputValidationError(
                f"Invalid value for {field}: {data[field]}"
            )


async def guarded_llm_call(
    call_fn,
    prompt,
    system_prompt,
    allowed_schema,
    retries=1
):

    last_error = None

    for _ in range(retries + 1):

        raw = await call_fn(prompt, system_prompt)

        try:

            parsed = parse_json(raw)

            validate_fields(parsed, allowed_schema)

            return parsed

        except OutputValidationError as e:
            last_error = e
            prompt = f"""Fix this JSON:

{raw}

Return ONLY valid JSON."""
            system_prompt = (system_prompt or "") + "\nReturn STRICT JSON. No text."

    raise OutputValidationError(
        f"LLM failed schema validation after retries: {last_error}"
    )
