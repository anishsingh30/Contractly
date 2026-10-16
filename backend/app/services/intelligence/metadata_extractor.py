import re
from typing import Dict, Any, List, Optional
from datetime import datetime


DATE_PATTERNS = [
    # YYYY-MM-DD
    (r"\b(\d{4}-\d{2}-\d{2})\b", "%Y-%m-%d"),
    # DD/MM/YYYY or DD-MM-YYYY
    (r"\b(\d{2}[\/\-]\d{2}[\/\-]\d{4})\b", "%d/%m/%Y"),
    # Month DD, YYYY (e.g. October 15, 2026 or Oct 15, 2026)
    (r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4})\b", None),
    # DD Month YYYY (e.g. 15 October 2026)
    (r"\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})\b", None),
]


def clean_party_string(raw: str) -> Optional[str]:
    """
    Cleans candidate party string. Validates against hallucination or sentence capture.
    """
    if not raw:
        return None
    cleaned = re.sub(r"^(?:the\s+|a\s+|an\s+)", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"[\.,;:\"\']+$", "", cleaned).strip()
    cleaned = re.sub(r"\s*\((?:hereinafter|referred\s+to\s+as|\"|\').*$", "", cleaned, flags=re.IGNORECASE).strip()

    # Reject if too long (captured a paragraph), too short, or looks like a clause sentence
    if len(cleaned) < 2 or len(cleaned) > 100:
        return None
    words = cleaned.split()
    if len(words) > 10:
        return None

    # Reject if contains verbs like 'shall', 'is agreed', 'entered'
    lower = cleaned.lower()
    if any(b in lower for b in ["shall", "agrees to", "warrants that", "undertakes to", "is entered", "effective date"]):
        return None

    return cleaned


def extract_parties(text: str) -> List[Dict[str, Any]]:
    """
    Extracts contract parties deterministically from recitals, preamble, and header.
    Conservative: if uncertain, returns empty list rather than hallucinating company names.
    """
    parties: List[Dict[str, Any]] = []
    first_chunk = text[:3500]  # Examine first 3500 chars (preamble/recitals)

    # 1. Pattern: "by and between Party A and Party B" or "between Party A and Party B"
    m = re.search(
        r"(?:by\s+and\s+between|entered\s+into\s+between|between)\s+([A-Z0-9][A-Za-z0-9\s,\.\(\)\&]+?)\s+(?:and|&)\s+([A-Z0-9][A-Za-z0-9\s,\.\(\)\&]+?)(?:\s*\((?:hereinafter|\"|\'|the\s+)|,\s*each|\.\s|\n)",
        first_chunk,
        re.IGNORECASE
    )
    if m:
        p1 = clean_party_string(m.group(1))
        p2 = clean_party_string(m.group(2))
        if p1 and p2:
            parties.append({"name": p1, "role": "Party 1", "source": "Agreement Preamble"})
            parties.append({"name": p2, "role": "Party 2", "source": "Agreement Preamble"})
            return parties

    # 2. Pattern: Defined roles (Customer: ..., Vendor: ..., Provider: ...)
    for role in ["Customer", "Client", "Vendor", "Supplier", "Service Provider", "Contractor", "Company"]:
        role_match = re.search(rf"{role}\s*:\s*([A-Z0-9][A-Za-z0-9\s,\.\&]{{2,80}})", first_chunk, re.IGNORECASE)
        if role_match:
            cand = clean_party_string(role_match.group(1))
            if cand and not any(p["name"].lower() == cand.lower() for p in parties):
                parties.append({"name": cand, "role": role.title(), "source": f"{role} definition"})

    return parties


def extract_candidate_dates(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deterministically identifies candidate dates across sections:
    Effective date, Expiry date, Renewal deadline, Notice periods.
    """
    candidates: List[Dict[str, Any]] = []

    for sec in sections:
        sec_text = sec["text"]
        sec_num = sec["section_number"]

        for pattern, _ in DATE_PATTERNS:
            for match in re.finditer(pattern, sec_text, re.IGNORECASE):
                date_str = match.group(1).strip()
                # Determine date type context
                start_window = max(0, match.start() - 60)
                end_window = min(len(sec_text), match.end() + 60)
                context = sec_text[start_window:end_window].lower()

                date_type = "GENERAL_DATE"
                if any(w in context for w in ["effective", "commencement", "start date", "begins on", "as of"]):
                    date_type = "EFFECTIVE_DATE"
                elif any(w in context for w in ["expire", "expiration", "end date", "terminates on", "conclusion"]):
                    date_type = "EXPIRY_DATE"
                elif any(w in context for w in ["renewal", "renews", "renewed on"]):
                    date_type = "RENEWAL_DATE"
                elif any(w in context for w in ["execution", "signed on", "dated as of"]):
                    date_type = "EXECUTION_DATE"

                candidates.append({
                    "date_type": date_type,
                    "date_str": date_str,
                    "section_number": sec_num,
                    "section_title": sec["title"],
                    "excerpt": sec_text[max(0, match.start() - 30):min(len(sec_text), match.end() + 30)].strip()
                })

    return candidates


def detect_renewal_metadata(text: str) -> Dict[str, Any]:
    """
    Extracts auto-renewal flags and notice periods from contract text.
    """
    text_lower = text.lower()

    # 1. Auto-renewal signal
    auto_renew = bool(re.search(r"auto(?:matically)?[\s\-]renew(?:s|al|ed)?", text_lower))

    # 2. Renewal Notice Days
    renewal_notice_days = 30
    rn_match = re.search(r"(\d{1,3})\s*(?:business\s*)?days?\s*(?:prior|advance)?\s*(?:written\s*)?notice\s*(?:prior\s*to\s*renewal|to\s*prevent\s*renewal)", text_lower)
    if rn_match:
        try:
            renewal_notice_days = int(rn_match.group(1))
        except ValueError:
            pass

    # 3. Termination Notice Days
    termination_notice_days = 30
    tn_match = re.search(r"(?:terminate|termination|notice)[\s\w]{1,40}?(\d{1,3})\s*(?:business\s*)?days?\s*(?:prior|advance)?\s*(?:written\s*)?notice", text_lower)
    if tn_match:
        try:
            termination_notice_days = int(tn_match.group(1))
        except ValueError:
            pass

    return {
        "auto_renew": auto_renew,
        "renewal_notice_days": renewal_notice_days,
        "termination_notice_days": termination_notice_days
    }
