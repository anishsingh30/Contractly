import re
from typing import Dict, Any, List, Optional


def detect_contract_risks(clauses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deterministic risk detector analyzing contractual clauses.
    Categorizes severity (CRITICAL, HIGH, MEDIUM, LOW) and uses conservative
    terminology: 'Potential Risk', 'Potential Issue', 'Potential Negotiation Concern'.
    """
    risks: List[Dict[str, Any]] = []

    for cl in clauses:
        clause_id = cl.get("id")
        sec_num = cl.get("section_number", "Section")
        sec_title = cl.get("clause_title", "")
        text = cl.get("original_text", "")
        text_lower = text.lower()
        category = cl.get("category", "")

        # 1. Limitation of Liability
        if category == "LIMITATION_OF_LIABILITY" or "liability" in sec_title.lower():
            if re.search(r"uncapped|unlimited|shall not be limited|without limitation", text_lower):
                risks.append({
                    "clause_id": clause_id,
                    "section_number": sec_num,
                    "category": "LIABILITY",
                    "severity": "CRITICAL",
                    "risk_title": "Potential Uncapped Liability Exposure",
                    "potential_impact": "Financial exposure may exceed annual contract value or result in catastrophic commercial claims.",
                    "remedy_recommendation": "Negotiate a reciprocal 12-month contract value liability cap with standard carve-outs.",
                    "status": "OPEN"
                })
            elif not re.search(r"aggregate liability|not exceed|limited to", text_lower):
                risks.append({
                    "clause_id": clause_id,
                    "section_number": sec_num,
                    "category": "LIABILITY",
                    "severity": "HIGH",
                    "risk_title": "Potential Missing Liability Cap",
                    "potential_impact": "Absence of explicit financial aggregate limitation exposes the organization to unbounded disputes.",
                    "remedy_recommendation": "Insert standard organization liability limitation provision.",
                    "status": "OPEN"
                })

        # 2. Indemnification
        if category == "INDEMNIFICATION" or "indemn" in sec_title.lower():
            if re.search(r"customer shall indemnify|client shall indemnify|unconditionally indemnify", text_lower) and not re.search(r"mutual|each party", text_lower):
                risks.append({
                    "clause_id": clause_id,
                    "section_number": sec_num,
                    "category": "INDEMNIFICATION",
                    "severity": "HIGH",
                    "risk_title": "Potential Unilateral Indemnification Obligation",
                    "potential_impact": "One-sided indemnification creates defense and settlement exposure without reciprocal vendor protections.",
                    "remedy_recommendation": "Restructure into mutual indemnification limited to third-party IP infringement and gross negligence.",
                    "status": "OPEN"
                })

        # 3. Restrictive Covenants / Non-Compete
        if category == "NON_COMPETE" or any(w in text_lower for w in ["non-compete", "restraint of trade", "not engage in competing"]):
            risks.append({
                "clause_id": clause_id,
                "section_number": sec_num,
                "category": "NON_COMPETE",
                "severity": "CRITICAL",
                "risk_title": "Potentially Unenforceable Non-Compete Restriction",
                "potential_impact": "Post-contractual restraint of trade creates friction and may be legally void under statutory law (e.g. Section 27 in India).",
                "remedy_recommendation": "Replace with enforceable non-solicitation of clients/staff and trade secret confidentiality.",
                "status": "OPEN"
            })

        # 4. Termination
        if category == "TERMINATION" or "termination" in sec_title.lower():
            if not re.search(r"convenience|without cause|any reason", text_lower) and not re.search(r"either party may terminate", text_lower):
                risks.append({
                    "clause_id": clause_id,
                    "section_number": sec_num,
                    "category": "TERMINATION",
                    "severity": "MEDIUM",
                    "risk_title": "Potential Lack of Termination for Convenience",
                    "potential_impact": "Inability to terminate without cause creates commercial lock-in if service expectations are unmet.",
                    "remedy_recommendation": "Request mutual termination for convenience upon 30–60 days advance written notice.",
                    "status": "OPEN"
                })

        # 5. Auto-Renewal Lock-in
        if category == "RENEWAL" or re.search(r"auto(?:matically)?[\s\-]renew", text_lower):
            if re.search(r"60\s*days|90\s*days|120\s*days", text_lower):
                risks.append({
                    "clause_id": clause_id,
                    "section_number": sec_num,
                    "category": "AUTO_RENEWAL",
                    "severity": "MEDIUM",
                    "risk_title": "Potential Long Renewal Notice Window",
                    "potential_impact": "Extended notice window (60+ days) increases likelihood of accidental contract renewal and budget lock.",
                    "remedy_recommendation": "Track notification date in Contract Watch and negotiate notice window down to 30 days.",
                    "status": "OPEN"
                })

        # 6. Governing Law & Jurisdiction
        if category == "GOVERNING_LAW" or "governing law" in sec_title.lower():
            if any(j in text_lower for j in ["england and wales", "new york", "delaware", "california", "singapore", "hong kong"]):
                risks.append({
                    "clause_id": clause_id,
                    "section_number": sec_num,
                    "category": "GOVERNING_LAW",
                    "severity": "MEDIUM",
                    "risk_title": "Potential Foreign Jurisdiction & Dispute Forum",
                    "potential_impact": "Foreign governing law significantly increases litigation expense and requires international counsel.",
                    "remedy_recommendation": "Seek alignment with organization primary operating jurisdiction or mutual neutral arbitration.",
                    "status": "OPEN"
                })

        # 7. Assignment
        if category == "ASSIGNMENT" or "assignment" in sec_title.lower():
            if re.search(r"may assign without consent|assign this agreement freely", text_lower):
                risks.append({
                    "clause_id": clause_id,
                    "section_number": sec_num,
                    "category": "ASSIGNMENT",
                    "severity": "MEDIUM",
                    "risk_title": "Potential Uncontrolled Assignment Rights",
                    "potential_impact": "Counterparty may transfer agreement to competitor or unvetted third party without prior approval.",
                    "remedy_recommendation": "Require prior written consent for any assignment (except for internal restructuring).",
                    "status": "OPEN"
                })

    return risks


def compute_explainable_risk_score(risks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes an explainable composite risk rating (0-100) derived strictly
    from actual detected risk records.
    """
    critical_count = sum(1 for r in risks if r["severity"] == "CRITICAL")
    high_count = sum(1 for r in risks if r["severity"] == "HIGH")
    med_count = sum(1 for r in risks if r["severity"] == "MEDIUM")
    low_count = sum(1 for r in risks if r["severity"] == "LOW")
    total_count = len(risks)

    if total_count == 0:
        return {
            "composite_risk_score": 15,
            "risk_level": "LOW",
            "critical_count": 0,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
            "explanation": "No significant potential concerns detected. Baseline low risk profile."
        }

    # Deterministic calculation formula:
    # Base: 20 + (critical * 30) + (high * 20) + (med * 10) + (low * 5)
    raw_score = 20 + (critical_count * 30) + (high_count * 20) + (med_count * 10) + (low_count * 5)
    composite_score = min(95, max(15, raw_score))

    if critical_count > 0:
        level = "CRITICAL"
    elif high_count > 0:
        level = "HIGH"
    elif med_count > 0:
        level = "MEDIUM"
    else:
        level = "LOW"

    explanation = (
        f"Calculated from {total_count} detected risk signal(s): "
        f"{critical_count} Critical, {high_count} High, {med_count} Medium, {low_count} Low."
    )

    return {
        "composite_risk_score": composite_score,
        "risk_level": level,
        "critical_count": critical_count,
        "high_count": high_count,
        "medium_count": med_count,
        "low_count": low_count,
        "explanation": explanation
    }
