import re


def clean_document_text(text: str) -> str:
    lines = text.splitlines()

    cleaned = []

    for line in lines:
        line = line.strip()

        if not line:
            continue

        # remove page numbers
        if re.match(r"^page\s*\d+", line.lower()):
            continue

        # remove numeric-only lines
        if re.match(r"^\d+$", line):
            continue

        # remove obvious table-of-contents style dots
        if re.search(r"\.{3,}", line):
            continue

        cleaned.append(line)

    return "\n".join(cleaned)
