# src/req_extractor.py
import re
from typing import List

# Accept 1.  1)  1:  1 - 
_NUMBERED_RE = re.compile(r'^\s*\d+\s*[\.\)\-:]\s*(.+)$')

def extract_numbered_requirements(llm_text: str) -> List[str]:
    if not llm_text:
        return []

    lines = llm_text.splitlines()
    out = []

    for line in lines:
        m = _NUMBERED_RE.match(line.strip())
        if m:
            s = m.group(1).strip()

            # Basic unicode normalization
            s = s.replace("–", "-").replace("—", "-").replace("“", '"').replace("”", '"')

            # Normalize whitespace
            s = " ".join(s.split())

            # Ensure final period
            if s and not s.endswith("."):
                s = s + "."

            # Validate IEEE requirement structure
            tokens = s.lower().split()

            # Rule 1 — must contain minimal semantic structure
            if len(tokens) < 5:
                continue

            # Rule 2 — enforce IEEE requirement format
            # "The system shall <action> ..."
            if not (
                tokens[0] == "the" and
                tokens[1] == "system" and
                tokens[2] == "shall"
            ):
                continue

            # Rule 3 — ensure an action exists after "shall"
            # (prevents fragments like "The system shall.")
            if len(tokens[3]) < 2:
                continue

            out.append(s)

    return out
