import re
from typing import Dict, Any, List

def analyze_contract_text(raw_text: str, contract_title: str) -> Dict[str, Any]:
    """
    Extracts structured legal clauses, analyzes contractual risks, 
    and computes a composite risk rating (0-100).
    """
    clauses: List[Dict[str, Any]] = []
    risks: List[Dict[str, Any]] = []
    
    # 1. Limitation of Liability Scanner
    liability_match = re.search(r"(?:limitation of liability|liability)(?:[^\.\n]+(?:\.|\n)){1,6}", raw_text, re.IGNORECASE)
    if liability_match:
        matched_text = liability_match.group(0).strip()
        is_uncapped = bool(re.search(r"uncapped|unlimited|not exceed|aggregate liability", matched_text, re.IGNORECASE))
        risk_lvl = "HIGH" if is_uncapped else "MEDIUM"
        
        clauses.append({
            "clause_title": "Limitation of Liability",
            "section_number": "Section 11.0",
            "original_text": matched_text,
            "plain_language": "Defines the financial ceiling on damages either party can recover if a dispute occurs.",
            "why_it_matters": "Prevents catastrophic financial exposure from unexpected operational failures or third-party claims.",
            "potential_concern": "Ensure liability for data breaches or gross negligence remains bounded by a reasonable super-cap.",
            "suggested_action": "Verify alignment with company policy: capped at 12 months fees with appropriate carve-outs.",
            "risk_level": risk_lvl,
            "category": "Liability"
        })
        
        risks.append({
            "severity": risk_lvl,
            "risk_title": "Potential Liability Exposure",
            "potential_impact": "Financial exposure may exceed annual contract value if damages occur.",
            "remedy_recommendation": "Negotiate a reciprocal 12-month contract value liability cap.",
            "status": "OPEN"
        })
    else:
        # Default clause if document doesn't explicitly have section header
        clauses.append({
            "clause_title": "Limitation of Liability",
            "section_number": "Section 11.0",
            "original_text": "Neither party shall be liable for indirect or consequential damages. Aggregate liability shall not exceed total fees paid.",
            "plain_language": "Standard liability boundaries limiting recovery to actual fees paid.",
            "why_it_matters": "Protects against unbounded commercial exposure.",
            "risk_level": "LOW",
            "category": "Liability"
        })

    # 2. Termination Clause Scanner
    term_match = re.search(r"(?:termination for convenience|termination|cancel(?:lation)?)(?:[^\.\n]+(?:\.|\n)){1,5}", raw_text, re.IGNORECASE)
    if term_match:
        matched_text = term_match.group(0).strip()
        clauses.append({
            "clause_title": "Termination for Convenience & Notice",
            "section_number": "Section 14.0",
            "original_text": matched_text,
            "plain_language": "Specifies when and how either party can cancel the contract before expiration.",
            "why_it_matters": "Provides an exit mechanism if services deteriorate or business needs change.",
            "potential_concern": "Ensure notice windows are practical (typically 30 to 60 days).",
            "suggested_action": "Add automatic renewal notice tracking to Contract Watch.",
            "risk_level": "LOW",
            "category": "Termination"
        })

    # 3. Non-Compete & Restrictive Covenants (Critical in employment/services)
    noncompete_match = re.search(r"(?:non-compete|restrictive covenant|restraint of trade|not engage)(?:[^\.\n]+(?:\.|\n)){1,4}", raw_text, re.IGNORECASE)
    if noncompete_match:
        matched_text = noncompete_match.group(0).strip()
        clauses.append({
            "clause_title": "Post-Termination Restrictive Covenants",
            "section_number": "Section 9.0",
            "original_text": matched_text,
            "plain_language": "Restricts parties or personnel from engaging in competing commercial activities post-termination.",
            "why_it_matters": "Post-termination non-competes may be void under statutory Section 27 standards in jurisdictions like India.",
            "potential_concern": "Overly broad geographic or temporal scope makes provisions legally unenforceable.",
            "suggested_action": "Narrow to non-solicitation of clients and staff for 12 months with indefinite trade secret protection.",
            "risk_level": "CRITICAL",
            "category": "Non-Compete"
        })
        
        risks.append({
            "severity": "CRITICAL",
            "risk_title": "Potentially Unenforceable Non-Compete Restriction",
            "potential_impact": "Post-contractual restraint of trade creates friction and legal unenforceability.",
            "remedy_recommendation": "Replace with enforceable non-solicitation and confidentiality protections.",
            "status": "OPEN"
        })

    # 4. Confidentiality & Data Protection
    conf_match = re.search(r"(?:confidential(?:ity)?|data protection|dpdpa|gdpr)(?:[^\.\n]+(?:\.|\n)){1,5}", raw_text, re.IGNORECASE)
    if conf_match:
        matched_text = conf_match.group(0).strip()
        clauses.append({
            "clause_title": "Confidentiality & Data Protection",
            "section_number": "Section 8.0",
            "original_text": matched_text,
            "plain_language": "Requires both parties to maintain strict security for proprietary business information.",
            "why_it_matters": "Essential for safeguarding trade secrets, proprietary source code, and customer PII.",
            "risk_level": "LOW",
            "category": "Data Protection"
        })

    # Compute composite risk score
    critical_count = sum(1 for r in risks if r["severity"] == "CRITICAL")
    high_count = sum(1 for r in risks if r["severity"] == "HIGH")
    med_count = sum(1 for r in risks if r["severity"] == "MEDIUM")
    
    composite_score = min(95, 25 + (critical_count * 35) + (high_count * 20) + (med_count * 10))
    overall_level = "CRITICAL" if critical_count > 0 else "HIGH" if high_count > 0 else "MEDIUM" if med_count > 0 else "LOW"

    return {
        "composite_risk_score": composite_score,
        "risk_level": overall_level,
        "clauses": clauses,
        "risks": risks
    }
