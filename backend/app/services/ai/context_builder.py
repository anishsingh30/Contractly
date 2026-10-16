import re
from typing import List, Dict, Any, Tuple, Optional
from app.models.contract import Contract, ContractClause, ContractRisk
from app.models.obligation import Obligation
from app.schemas.ai import ContractQASource

STOPWORDS = {
    "a", "an", "the", "and", "or", "is", "are", "was", "were", "to", "in", "of", "for",
    "with", "on", "at", "by", "from", "up", "about", "into", "over", "after", "it", "its",
    "this", "that", "these", "those", "can", "could", "will", "would", "shall", "should",
    "what", "when", "where", "who", "whom", "how", "why", "does", "do", "did", "have", "has",
    "contract", "agreement", "clause", "section"
}

CATEGORY_SYNONYMS = {
    "termination": ["termination", "cancel", "cancellation", "exit", "terminate", "notice period"],
    "liability": ["liability", "damages", "cap", "uncapped", "consequential", "indemnification", "indemnity", "limit"],
    "non-compete": ["non-compete", "non compete", "restrictive", "covenant", "restraint", "solicitation", "non-solicit"],
    "confidentiality": ["confidential", "confidentiality", "nda", "proprietary", "trade secret", "disclosure"],
    "payment": ["pay", "payment", "fees", "fee", "billing", "invoice", "cost", "price", "penalty"],
    "intellectual property": ["ip", "intellectual property", "ownership", "copyright", "patent", "trademark", "work for hire"],
    "governing law": ["governing law", "jurisdiction", "dispute", "arbitration", "courts"],
    "renewal": ["renew", "renewal", "auto-renew", "term", "duration", "expiration", "expiry"]
}

def tokenize(text: str) -> List[str]:
    """Tokenize and normalize text into clean search tokens, removing common stopwords."""
    if not text:
        return []
    words = re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", text.lower())
    return [w for w in words if w not in STOPWORDS]

def calculate_overlap_score(query_tokens: List[str], text: str, category_boost: float = 0.0) -> float:
    """Calculates relevance score based on token frequency and length normalization."""
    if not text or not query_tokens:
        return 0.0
    text_lower = text.lower()
    score = 0.0
    for token in query_tokens:
        if token in text_lower:
            # Add points for match
            score += 2.0
            # Exact word match bonus
            if re.search(r"\b" + re.escape(token) + r"\b", text_lower):
                score += 3.0
    return score + category_boost

def retrieve_relevant_contract_context(
    contract: Contract,
    question: str,
    max_clauses: int = 4,
    max_risks: int = 2,
    max_obligations: int = 2,
    max_excerpt_len: int = 400
) -> Tuple[str, List[ContractQASource], bool]:
    """
    Structured retrieval from database records.
    Filters and ranks clauses, risks, obligations, and dates.
    Returns:
      (structured_context_prompt_text, list_of_database_sources, has_relevant_context)
    """
    query_tokens = tokenize(question)
    question_lower = question.lower()

    # Identify category boosts from question
    category_boosts: Dict[str, float] = {}
    for cat, synonyms in CATEGORY_SYNONYMS.items():
        if any(syn in question_lower for syn in synonyms):
            category_boosts[cat.lower()] = 10.0

    scored_clauses: List[Tuple[float, ContractClause]] = []
    if contract.clauses:
        for clause in contract.clauses:
            cat = (clause.category or "General").lower()
            boost = 0.0
            for boosted_cat, b_val in category_boosts.items():
                if boosted_cat in cat or cat in boosted_cat:
                    boost += b_val

            clause_text_combined = f"{clause.clause_title} {clause.section_number} {clause.original_text} {clause.plain_language} {clause.category or ''}"
            score = calculate_overlap_score(query_tokens, clause_text_combined, boost)
            if score > 0:
                scored_clauses.append((score, clause))

    # Sort clauses by score descending
    scored_clauses.sort(key=lambda x: x[0], reverse=True)
    selected_clauses = [c for _, c in scored_clauses[:max_clauses]]

    # If no clauses scored positive but clauses exist and question seems general, fallback to top 2 clauses
    # only if query specifically asked about general terms, otherwise leave empty so model can detect missing context
    has_clause_match = len(selected_clauses) > 0

    # Scored Risks
    scored_risks: List[Tuple[float, ContractRisk]] = []
    if contract.risks:
        for risk in contract.risks:
            risk_text = f"{risk.risk_title} {risk.potential_impact} {risk.remedy_recommendation} {risk.category or ''}"
            score = calculate_overlap_score(query_tokens, risk_text)
            if score > 0:
                scored_risks.append((score, risk))
    scored_risks.sort(key=lambda x: x[0], reverse=True)
    selected_risks = [r for _, r in scored_risks[:max_risks]]

    # Scored Obligations
    scored_obligations: List[Tuple[float, Obligation]] = []
    if contract.obligations:
        for obl in contract.obligations:
            obl_text = f"{obl.title} {obl.description} {obl.source_text or ''} {obl.obligor_party} {obl.due_date or ''}"
            score = calculate_overlap_score(query_tokens, obl_text)
            if score > 0:
                scored_obligations.append((score, obl))
    scored_obligations.sort(key=lambda x: x[0], reverse=True)
    selected_obligations = [o for _, o in scored_obligations[:max_obligations]]

    # Check date relevance
    date_related_keywords = ["when", "date", "expire", "expiration", "renewal", "renew", "start", "term", "deadline"]
    is_date_relevant = any(kw in question_lower for kw in date_related_keywords)

    # Determine whether ANY grounded context was retrieved
    has_relevant_context = bool(has_clause_match or selected_risks or selected_obligations or is_date_relevant)

    # Build DB-backed sources from selected clauses
    sources: List[ContractQASource] = []
    for c in selected_clauses:
        raw_snippet = c.original_text.strip() if c.original_text else ""
        if len(raw_snippet) > max_excerpt_len:
            raw_snippet = raw_snippet[:max_excerpt_len] + "..."

        sources.append(ContractQASource(
            clause_id=c.id,
            section=c.section_number or "General",
            title=c.clause_title,
            page=c.page_number if c.page_number is not None else 1,
            excerpt=raw_snippet
        ))

    # Assemble Structured Context String
    lines = [
        "CONTRACT METADATA:",
        f"Title: {contract.title}",
        f"Contract ID: {contract.contract_id}",
        f"Version: {contract.version}",
        f"Counterparty: {contract.counterparty}",
        f"Governing Law: {contract.governing_law}",
        f"Total Value: {contract.currency} {contract.value}"
    ]

    if is_date_relevant or contract.expiry_date or contract.start_date:
        lines.append("\nKEY DATES & TERMS:")
        lines.append(f"- Effective / Start Date: {contract.start_date or 'Not specified'}")
        lines.append(f"- Expiry Date: {contract.expiry_date or 'Not specified'}")
        lines.append(f"- Renewal Date: {contract.renewal_date or 'Not specified'}")
        lines.append(f"- Auto-Renew: {'Yes' if contract.auto_renew else 'No'}")
        lines.append(f"- Renewal Notice Window: {contract.renewal_notice_days} days")
        lines.append(f"- Termination Notice Window: {contract.termination_notice_days} days")

    if selected_clauses:
        lines.append("\nRELEVANT CLAUSES (RETRIEVED FROM DATABASE):")
        for idx, c in enumerate(selected_clauses, 1):
            excerpt = c.original_text.strip() if c.original_text else ""
            if len(excerpt) > max_excerpt_len:
                excerpt = excerpt[:max_excerpt_len] + "..."
            lines.append(
                f"[{idx}] {c.section_number or 'Section'} — {c.clause_title} (Page {c.page_number or 1})\n"
                f"Text: \"{excerpt}\"\n"
                f"Plain Summary: {c.plain_language}"
            )
    else:
        lines.append("\nRELEVANT CLAUSES: None retrieved matching query keywords.")

    if selected_risks:
        lines.append("\nRELEVANT IDENTIFIED RISKS:")
        for r in selected_risks:
            lines.append(f"- [{r.severity}] {r.risk_title}: {r.potential_impact}")

    if selected_obligations:
        lines.append("\nRELEVANT OBLIGATIONS:")
        for o in selected_obligations:
            lines.append(f"- Due: {o.due_date or 'Ongoing'} | Responsible: {o.obligor_party} | Title: {o.title}: {o.description}")

    context_str = "\n".join(lines)
    return context_str, sources, has_relevant_context
