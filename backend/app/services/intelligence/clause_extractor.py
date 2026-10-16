import re
from typing import Dict, Any, List, Optional

CLAUSE_CATEGORIES = [
    "DEFINITIONS",
    "PARTIES",
    "SCOPE",
    "PAYMENT",
    "FEES",
    "TERM",
    "RENEWAL",
    "TERMINATION",
    "CONFIDENTIALITY",
    "DATA_PROTECTION",
    "INTELLECTUAL_PROPERTY",
    "INDEMNIFICATION",
    "LIMITATION_OF_LIABILITY",
    "WARRANTIES",
    "INSURANCE",
    "GOVERNING_LAW",
    "DISPUTE_RESOLUTION",
    "AUDIT",
    "SECURITY",
    "ASSIGNMENT",
    "FORCE_MAJEURE",
    "NON_SOLICITATION",
    "NON_COMPETE",
    "NOTICE",
    "MISCELLANEOUS",
    "OTHER",
]

# Keywords dictionary for taxonomy classification
TAXONOMY_KEYWORDS: Dict[str, List[str]] = {
    "DEFINITIONS": ["defined terms", "definitions", "meaning of terms", "shall mean", "have the following meanings"],
    "PARTIES": ["parties", "entered into between", "by and between", "recitals", "whereas"],
    "SCOPE": ["scope of services", "statement of work", "deliverables", "services to be provided", "scope of work"],
    "PAYMENT": ["payment terms", "invoicing", "invoice", "late payment", "payment schedule", "net 30", "net 60"],
    "FEES": ["fees and expenses", "compensation", "service fee", "rates", "pricing schedule", "subscription fee"],
    "RENEWAL": ["auto-renew", "automatic renewal", "renewal term", "renewal period", "renews automatically"],
    "TERM": ["term of agreement", "initial term", "effective term", "duration of agreement"],
    "TERMINATION": ["termination for convenience", "termination for cause", "termination notice", "cancellation", "upon termination"],
    "CONFIDENTIALITY": ["confidential information", "non-disclosure", "proprietary information", "confidentiality"],
    "DATA_PROTECTION": ["data protection", "privacy policy", "personal data", "gdpr", "dpdpa", "data processor", "security breach"],
    "INTELLECTUAL_PROPERTY": ["intellectual property", "work made for hire", "ip rights", "patent", "copyright", "trademark", "ownership of deliverables"],
    "INDEMNIFICATION": ["indemnify", "indemnification", "hold harmless", "defense of claims", "indemnity"],
    "LIMITATION_OF_LIABILITY": ["limitation of liability", "indirect damages", "consequential damages", "aggregate liability", "liability cap"],
    "WARRANTIES": ["representations and warranties", "warranties", "as is", "express warranty", "implied warranties"],
    "INSURANCE": ["insurance coverage", "commercial general liability", "worker's compensation", "errors and omissions", "insurance policy"],
    "GOVERNING_LAW": ["governing law", "jurisdiction", "governed by the laws", "venue", "courts of"],
    "DISPUTE_RESOLUTION": ["dispute resolution", "arbitration", "mediation", "rules of arbitration"],
    "AUDIT": ["audit rights", "inspection of records", "books and records", "right to audit"],
    "SECURITY": ["information security", "cybersecurity", "access controls", "security standards", "soc 2"],
    "ASSIGNMENT": ["assignment", "neither party may assign", "binding upon successors", "transfer of rights"],
    "FORCE_MAJEURE": ["force majeure", "acts of god", "unforeseen events", "epidemic", "natural disaster"],
    "NON_SOLICITATION": ["non-solicitation", "solicitation of employees", "hire or solicit", "solicit customers"],
    "NON_COMPETE": ["non-compete", "competing business", "restraint of trade", "restrictive covenant"],
    "NOTICE": ["notices", "formal notice", "written notice", "addresses for notice"],
    "MISCELLANEOUS": ["miscellaneous", "severability", "entire agreement", "counterparts", "waiver", "headings"],
}


def classify_clause_category(title: str, text: str) -> str:
    """
    Deterministically assigns a category from the controlled taxonomy.
    Defaults to 'OTHER' if confidence/signals are insufficient.
    """
    title_lower = title.lower()
    text_lower = text.lower()[:1500]  # Examine first 1500 chars

    # 1. Match against Section Title (strongest signal)
    for cat, kws in TAXONOMY_KEYWORDS.items():
        for kw in kws:
            if kw in title_lower:
                return cat

    # 2. Match against Clause Body Text
    scores: Dict[str, int] = {}
    for cat, kws in TAXONOMY_KEYWORDS.items():
        score = 0
        for kw in kws:
            if kw in text_lower:
                score += 1
        if score > 0:
            scores[cat] = score

    if scores:
        best_cat = max(scores, key=scores.get)
        if scores[best_cat] >= 1:
            return best_cat

    return "OTHER"


def generate_clause_explanations(category: str, title: str, text: str) -> Dict[str, Any]:
    """
    Produces deterministic plain-language explanations, business relevance,
    potential concerns, suggested actions, and initial risk levels.
    """
    text_lower = text.lower()

    if category == "LIMITATION_OF_LIABILITY":
        is_uncapped = bool(re.search(r"uncapped|unlimited|not exceed|aggregate liability", text_lower))
        risk = "HIGH" if is_uncapped else "LOW"
        return {
            "plain_language": "Limits the monetary amount either party can recover in damages if a dispute or failure occurs.",
            "why_it_matters": "Crucial commercial clause that caps organizational financial exposure against runaway claims.",
            "potential_concern": "Exposures on data breach, confidentiality, or gross negligence must have appropriate balanced caps.",
            "suggested_action": "Verify liability is capped at 12 months fees paid or agreed mutual super-cap.",
            "risk_level": risk
        }

    if category == "INDEMNIFICATION":
        is_unilateral = bool(re.search(r"vendor shall indemnify|supplier shall indemnify|customer shall indemnify", text_lower))
        risk = "HIGH" if is_unilateral else "MEDIUM"
        return {
            "plain_language": "Obligates one party to pay legal costs and damages if a third party sues the other party.",
            "why_it_matters": "Shields against third-party intellectual property infringement or bodily injury claims.",
            "potential_concern": "Ensure indemnification obligations are mutual and exclude gross negligence of the other party.",
            "suggested_action": "Require prompt notice of claims, sole defense control, and mutual indemnification.",
            "risk_level": risk
        }

    if category == "TERMINATION":
        has_convenience = "convenience" in text_lower
        return {
            "plain_language": "Defines the conditions under which either party can cancel or exit this agreement.",
            "why_it_matters": "Guarantees a clean contractual exit path if vendor performance drops or strategy changes.",
            "potential_concern": "Watch out for unilateral lock-ins or notice periods longer than 60 days.",
            "suggested_action": "Ensure termination for convenience exists with 30–60 days advance written notice.",
            "risk_level": "LOW" if has_convenience else "MEDIUM"
        }

    if category == "NON_COMPETE":
        return {
            "plain_language": "Restricts personnel or companies from engaging in competing business operations.",
            "why_it_matters": "Post-contractual non-competes may violate statutory trade laws (e.g., Section 27 in India).",
            "potential_concern": "Overbroad scope may lead to invalidity, employment disputes, or commercial paralysis.",
            "suggested_action": "Limit restrictive covenants to non-solicitation of clients/staff and trade secret confidentiality.",
            "risk_level": "CRITICAL"
        }

    if category == "DATA_PROTECTION" or category == "CONFIDENTIALITY":
        return {
            "plain_language": "Safeguards proprietary corporate data and confidential business communications.",
            "why_it_matters": "Critical for privacy compliance (DPDPA, GDPR) and trade secret preservation.",
            "potential_concern": "Verify that return or secure destruction of data is mandated upon contract expiry.",
            "suggested_action": "Maintain standard 3–5 year survival for business data and perpetual for trade secrets.",
            "risk_level": "LOW"
        }

    if category == "GOVERNING_LAW":
        return {
            "plain_language": "Specifies which jurisdiction's laws and courts govern disputes arising from the agreement.",
            "why_it_matters": "Dictates legal interpretation, court convenience, and dispute costs.",
            "potential_concern": "Avoid foreign jurisdictions unless supported by local legal counsel.",
            "suggested_action": "Confirm choice of law is aligned with standard organization domicile.",
            "risk_level": "LOW"
        }

    if category == "PAYMENT" or category == "FEES":
        return {
            "plain_language": "Outlines invoice issuance, billing milestones, and payment schedule terms.",
            "why_it_matters": "Directly controls working capital, cash flow, and financial commitments.",
            "potential_concern": "Check for excessive interest penalties on disputed invoice amounts.",
            "suggested_action": "Standardize to Net 30 or Net 45 with reasonable invoice dispute procedures.",
            "risk_level": "LOW"
        }

    # Default / Other
    return {
        "plain_language": f"Defines terms and operational guidelines for {title}.",
        "why_it_matters": "Establishes legal clarity and operational rights across both parties.",
        "potential_concern": None,
        "suggested_action": "Review during standard legal intake review.",
        "risk_level": "LOW"
    }


def extract_clauses(sections: List[Dict[str, Any]], contract_id: str, version_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Transforms detected sections into structured ContractClause records.
    """
    clauses: List[Dict[str, Any]] = []

    for order_idx, sec in enumerate(sections, start=1):
        cat = classify_clause_category(sec["title"], sec["text"])
        exp = generate_clause_explanations(cat, sec["title"], sec["text"])

        clauses.append({
            "contract_id": contract_id,
            "contract_version_id": version_id,
            "clause_title": sec["title"],
            "section_number": sec["section_number"],
            "original_text": sec["text"],
            "plain_language": exp["plain_language"],
            "why_it_matters": exp["why_it_matters"],
            "potential_concern": exp.get("potential_concern"),
            "suggested_action": exp.get("suggested_action"),
            "risk_level": exp["risk_level"],
            "category": cat,
            "page_number": sec.get("page_number", 1),
            "position_order": order_idx,
            "start_pos": sec.get("start_pos"),
            "end_pos": sec.get("end_pos"),
        })

    return clauses
