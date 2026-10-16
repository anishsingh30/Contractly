import re
from typing import Dict, Any, List, Optional


KNOWN_HEADINGS = [
    "DEFINITIONS",
    "RECITALS",
    "PARTIES",
    "SCOPE OF WORK",
    "SCOPE OF SERVICES",
    "SERVICES",
    "PAYMENT",
    "PAYMENT TERMS",
    "FEES AND EXPENSES",
    "FEES",
    "PRICING",
    "TERM",
    "TERM AND TERMINATION",
    "TERMINATION",
    "TERMINATION FOR CONVENIENCE",
    "CONFIDENTIALITY",
    "CONFIDENTIAL INFORMATION",
    "DATA PROTECTION",
    "PRIVACY AND DATA SECURITY",
    "SECURITY",
    "INTELLECTUAL PROPERTY",
    "INTELLECTUAL PROPERTY RIGHTS",
    "PROPRIETARY RIGHTS",
    "INDEMNIFICATION",
    "INDEMNITY",
    "LIMITATION OF LIABILITY",
    "LIABILITY",
    "WARRANTIES",
    "REPRESENTATIONS AND WARRANTIES",
    "INSURANCE",
    "GOVERNING LAW",
    "GOVERNING LAW AND JURISDICTION",
    "DISPUTE RESOLUTION",
    "ARBITRATION",
    "AUDIT",
    "AUDIT RIGHTS",
    "ASSIGNMENT",
    "FORCE MAJEURE",
    "NON-SOLICITATION",
    "NON-COMPETE",
    "RESTRICTIVE COVENANTS",
    "NOTICES",
    "MISCELLANEOUS",
    "GENERAL PROVISIONS",
    "GENERAL TERMS",
    "SEVERABILITY",
    "ENTIRE AGREEMENT",
    "AMENDMENT",
]

# Patterns for section headings
SECTION_HEADER_REGEXES = [
    # Article I / ARTICLE 1: Title
    re.compile(r"^(?:ARTICLE|Article)\s+([IVXLCDM\d]+)[\.:\s\-—]+(.+)$", re.IGNORECASE),
    # Section 1.0 / SECTION 1: Title
    re.compile(r"^(?:SECTION|Section)\s+([\d\.]+)[\.:\s\-—]+(.+)$", re.IGNORECASE),
    # Clause 1.0 / CLAUSE 1: Title
    re.compile(r"^(?:CLAUSE|Clause)\s+([\d\.]+)[\.:\s\-—]+(.+)$", re.IGNORECASE),
    # 1. Title or 1.1 Title or 1.1.1 Title
    re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,2})\.?\s+([A-Z][A-Za-z0-9\s,\-–\(\)\/]{2,80})$"),
]


def map_char_to_page(char_index: int, pages: Optional[List[Dict[str, Any]]]) -> int:
    """
    Maps character offset in text to page number based on page metadata.
    """
    if not pages:
        return 1
    running_offset = 0
    for p in pages:
        p_len = len(p.get("text", "")) + 2  # plus spacing
        if char_index < running_offset + p_len:
            return p.get("page_number", 1)
        running_offset += p_len
    return pages[-1].get("page_number", 1) if pages else 1


def detect_sections(text: str, pages: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """
    Deterministically segments contract text into sections.
    Detects numbered sections, Articles, and standard/custom section headings.
    Preserves all section text, start/end character offsets, and page numbers.
    """
    if not text:
        return []

    lines = text.split("\n")
    headers: List[Dict[str, Any]] = []
    current_char_offset = 0

    for idx, line in enumerate(lines):
        line_stripped = line.strip()
        line_len = len(line) + 1  # includes newline

        if not line_stripped:
            current_char_offset += line_len
            continue

        matched = False

        # 1. Check explicit Regex Header Patterns
        for pattern in SECTION_HEADER_REGEXES:
            match = pattern.match(line_stripped)
            if match:
                sec_num = match.group(1).strip()
                sec_title = match.group(2).strip()
                # Clean trailing punctuation from title
                sec_title = re.sub(r"[\.:\-_]+$", "", sec_title).strip()
                headers.append({
                    "line_index": idx,
                    "section_number": f"Section {sec_num}" if not sec_num.lower().startswith("section") else sec_num,
                    "title": sec_title or f"Section {sec_num}",
                    "start_pos": current_char_offset,
                    "matched_pattern": "pattern"
                })
                matched = True
                break

        # 2. Check Known Headings on standalone lines
        if not matched and len(line_stripped) < 70:
            cleaned_upper = re.sub(r"^[0-9\.\s\-–:]+", "", line_stripped).strip().upper()
            cleaned_upper = re.sub(r"[\.:\-_]+$", "", cleaned_upper).strip()
            if cleaned_upper in KNOWN_HEADINGS:
                # Extract any leading numbering if present
                num_match = re.match(r"^(\d{1,2}(?:\.\d{1,2})*)[\.\s:]*", line_stripped)
                sec_num = f"Section {num_match.group(1)}" if num_match else f"Section {len(headers) + 1}.0"
                headers.append({
                    "line_index": idx,
                    "section_number": sec_num,
                    "title": line_stripped.title(),
                    "start_pos": current_char_offset,
                    "matched_pattern": "known_heading"
                })
                matched = True

        current_char_offset += line_len

    # If no headers detected, fallback to paragraph-level or single document section
    if not headers:
        return [{
            "section_number": "Section 1.0",
            "title": "General Terms & Agreement Content",
            "text": text,
            "start_pos": 0,
            "end_pos": len(text),
            "page_number": 1
        }]

    # Slice text between detected headers
    sections: List[Dict[str, Any]] = []

    # Handle preamble before first header if substantial
    first_header = headers[0]
    if first_header["start_pos"] > 60:
        preamble_text = text[:first_header["start_pos"]].strip()
        if preamble_text:
            sections.append({
                "section_number": "Preamble",
                "title": "Parties & Recitals",
                "text": preamble_text,
                "start_pos": 0,
                "end_pos": first_header["start_pos"],
                "page_number": map_char_to_page(0, pages)
            })

    for i in range(len(headers)):
        curr_h = headers[i]
        next_start = headers[i + 1]["start_pos"] if i + 1 < len(headers) else len(text)
        sec_text = text[curr_h["start_pos"]:next_start].strip()

        sections.append({
            "section_number": curr_h["section_number"],
            "title": curr_h["title"],
            "text": sec_text,
            "start_pos": curr_h["start_pos"],
            "end_pos": next_start,
            "page_number": map_char_to_page(curr_h["start_pos"], pages)
        })

    return sections
