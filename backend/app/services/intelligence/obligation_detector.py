import re
from typing import Dict, Any, List, Optional

OBLIGATION_PATTERNS = [
    re.compile(r"([A-Z][A-Za-z0-9\s,\(\)]+?)\s+(?:shall|must|agrees to|is required to|undertakes to)\s+([^\.\n]+(?:\.|\n))", re.IGNORECASE),
    re.compile(r"([A-Z][A-Za-z0-9\s,\(\)]+?)\s+(?:will provide|will maintain|must notify|shall deliver|shall pay)\s+([^\.\n]+(?:\.|\n))", re.IGNORECASE),
]

PARTY_ROLES = ["Customer", "Vendor", "Supplier", "Provider", "Company", "Contractor", "Recipient", "Disclosing Party", "Receiving Party", "Licensor", "Licensee"]


def extract_obligation_candidates(clauses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Conservatively detects actionable obligations from extracted clauses.
    Identifies responsible party, requirement text, frequency, and source clause references.
    """
    candidates: List[Dict[str, Any]] = []

    for clause in clauses:
        clause_id = clause.get("id")
        sec_num = clause.get("section_number", "Section")
        sec_title = clause.get("clause_title", "")
        text = clause.get("original_text", "")
        category = clause.get("category", "GENERAL")

        # Split into sentences
        sentences = re.split(r"(?<=[.!?])\s+", text)

        for sentence in sentences:
            sentence_clean = sentence.strip()
            if len(sentence_clean) < 25 or len(sentence_clean) > 350:
                continue

            # Check for imperative obligation signals
            has_shall = "shall " in sentence_clean.lower()
            has_must = "must " in sentence_clean.lower()
            has_agrees_to = "agrees to " in sentence_clean.lower()
            has_required = "required to " in sentence_clean.lower()
            has_responsible = "responsible for " in sentence_clean.lower()

            if not (has_shall or has_must or has_agrees_to or has_required or has_responsible):
                continue

            # Detect party
            detected_party = "Contract Party"
            for role in PARTY_ROLES:
                if role.lower() in sentence_clean.lower():
                    detected_party = role
                    break

            # Detect frequency
            freq = "ONE_TIME"
            lower_s = sentence_clean.lower()
            if any(w in lower_s for w in ["monthly", "each month", "every month"]):
                freq = "MONTHLY"
            elif any(w in lower_s for w in ["quarterly", "each quarter"]):
                freq = "QUARTERLY"
            elif any(w in lower_s for w in ["annual", "annually", "each year"]):
                freq = "ANNUAL"
            elif any(w in lower_s for w in ["within", "upon request", "promptly", "immediately"]):
                freq = "UPON_EVENT"

            # Derive title
            words = sentence_clean.split()[:8]
            title = " ".join(words) + "..."

            candidates.append({
                "title": title,
                "clause_id": clause_id,
                "section_number": sec_num,
                "section_title": sec_title,
                "source_text": sentence_clean,
                "responsible_party": detected_party,
                "category": category,
                "frequency": freq,
                "confidence": "HIGH" if (has_shall or has_must) else "MEDIUM"
            })

            # Limit candidates per clause to avoid noise
            if len([c for c in candidates if c.get("section_number") == sec_num]) >= 3:
                break

    return candidates
