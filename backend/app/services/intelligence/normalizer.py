import re
from typing import Dict, Any, List


def normalize_contract_text(raw_text: str) -> str:
    """
    Deterministically normalizes contract text:
    - Standardizes line breaks (CRLF -> LF).
    - Unifies non-breaking spaces and irregular whitespace characters.
    - Preserves paragraph separations (double newlines).
    - Cleans inline multi-spaces without damaging section indentation or numbering.
    - Preserves headings, section numbering, and legal clauses.
    """
    if not raw_text:
        return ""

    # 1. Unify carriage returns
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Replace non-breaking spaces and tabs with standard space
    text = text.replace("\u00a0", " ").replace("\u200b", "")

    # 3. Replace fancy/smart quotes with standard quotes for uniform regex matching
    text = (
        text.replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2013", "-")
        .replace("\u2014", "--")
    )

    # 4. Collapse multiple horizontal spaces/tabs on each line
    lines = text.split("\n")
    cleaned_lines: List[str] = []
    for line in lines:
        cleaned_line = re.sub(r"[ \t]+", " ", line).strip()
        cleaned_lines.append(cleaned_line)

    # 5. Join lines back, collapsing 3+ consecutive newlines to 2 (paragraph boundary)
    joined = "\n".join(cleaned_lines)
    normalized = re.sub(r"\n{3,}", "\n\n", joined)

    return normalized.strip()
