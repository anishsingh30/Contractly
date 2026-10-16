import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime


CURRENCY_SYMBOLS = {
    "₹": "INR",
    "INR": "INR",
    "RS.": "INR",
    "RS": "INR",
    "RUPEES": "INR",
    "$": "USD",
    "USD": "USD",
    "€": "EUR",
    "EUR": "EUR",
    "£": "GBP",
    "GBP": "GBP",
}

# Regex to detect liability caps, penalties, deposits, optional fees
EXCLUSION_PATTERNS = [
    r"liabilit(?:y|ies)\s+(?:shall\s+not\s+exceed|is\s+capped\s+at|cap|limited\s+to)",
    r"(?:total\s+aggregate|maximum)\s+liability",
    r"aggregate\s+liability\s+(?:shall|is)",
    r"penalt(?:y|ies)",
    r"liquidated\s+damages",
    r"security\s+deposit",
    r"earnest\s+money",
    r"optional\s+(?:fee|service|module|add-on)",
    r"discretionary",
    r"interest\s+(?:at|of)\s+[\d\.]+\s*%",
    r"per\s+hour\b",
    r"hourly\s+rate",
]

def is_excluded_context(line: str) -> bool:
    line_lower = line.lower()
    return any(re.search(pat, line_lower) for pat in EXCLUSION_PATTERNS)


def parse_numeric_amount(raw: str) -> Optional[float]:
    """
    Parses numeric strings including Indian numbering (12,00,000) and text multipliers (12 Lakhs).
    """
    cleaned = raw.strip().replace(",", "")
    
    # Check for text scale words
    m_lakh = re.search(r"^([\d\.]+)\s*(?:lakh|lac)s?$", cleaned, re.IGNORECASE)
    if m_lakh:
        try:
            return float(m_lakh.group(1)) * 100_000.0
        except ValueError:
            return None

    m_crore = re.search(r"^([\d\.]+)\s*(?:crore|cr)s?$", cleaned, re.IGNORECASE)
    if m_crore:
        try:
            return float(m_crore.group(1)) * 10_000_000.0
        except ValueError:
            return None

    m_thousand = re.search(r"^([\d\.]+)\s*(?:k|thousand)s?$", cleaned, re.IGNORECASE)
    if m_thousand:
        try:
            return float(m_thousand.group(1)) * 1_000.0
        except ValueError:
            return None

    m_million = re.search(r"^([\d\.]+)\s*(?:m|million)s?$", cleaned, re.IGNORECASE)
    if m_million:
        try:
            return float(m_million.group(1)) * 1_000_000.0
        except ValueError:
            return None

    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_currency(text: str) -> str:
    """Detects primary currency symbol or code from string."""
    text_upper = text.upper()
    if "₹" in text or "INR" in text_upper or "RS." in text_upper or re.search(r"\bRS\b", text_upper) or "RUPEES" in text_upper:
        return "INR"
    if "$" in text or "USD" in text_upper:
        return "USD"
    if "€" in text or "EUR" in text_upper:
        return "EUR"
    if "£" in text or "GBP" in text_upper:
        return "GBP"
    return "INR"


def extract_term_months_from_text(text: str, candidate_dates: Optional[List[Dict[str, Any]]] = None) -> Optional[int]:
    """
    Extracts the contractual term in months deterministically:
    - 'Initial term: 12 months' -> 12
    - 'term of one (1) year' / 'one year' -> 12
    - 'term of two (2) years' -> 24
    - 'term ends on 30 September 2027' + start 1 October 2026 -> 12
    """
    text_lower = text.lower()

    # Pattern: X months
    m_months = re.search(
        r"(?:initial\s+term|term|period)(?:\s+of\s+[^0-9,.:\n]+?)?\s*(?:is|of|:|=|shall\s+be)?\s*(\d{1,3})\s*months?",
        text_lower
    )
    if m_months:
        try:
            val = int(m_months.group(1))
            if 1 <= val <= 120:
                return val
        except ValueError:
            pass

    # Pattern: X years
    m_years = re.search(
        r"(?:initial\s+term|term|period)(?:\s+of\s+[^0-9,.:\n]+?)?\s*(?:is|of|:|=|shall\s+be)?\s*(\d{1,2})\s*(?:\([0-9]+\)\s*)?years?",
        text_lower
    )
    if m_years:
        try:
            val = int(m_years.group(1))
            if 1 <= val <= 10:
                return val * 12
        except ValueError:
            pass

    # Word-based years: "one (1) year", "two (2) years", "one-year", "two years"
    word_year_map = {
        "one": 12, "two": 24, "three": 36, "four": 48, "five": 60
    }
    for word, m in word_year_map.items():
        if re.search(rf"(?:term|initial\s+term|period|renews?)(?:\s+of\s+[^0-9,.:\n]+?)?\s*(?:is|of|:|=|shall\s+be)?\s*{word}\s*(?:\([0-9]+\)\s*)?year", text_lower):
            return m

    # Derive from explicit start and end dates if present in candidate_dates or text
    # e.g., "1 November 2026 to 31 October 2027" or "begins on 1 November 2026 and ends on 31 October 2027"
    m_range = re.search(
        r"(?:begins|commences?|entered\s+into)\s+(?:on\s+)?(\d{1,2}\s+[A-Za-z]+\s+\d{4}|\d{4}-\d{2}-\d{2}).*?(?:ends|expires?|terminates?)\s+(?:on\s+)?(\d{1,2}\s+[A-Za-z]+\s+\d{4}|\d{4}-\d{2}-\d{2})",
        text,
        re.IGNORECASE | re.DOTALL
    )
    if m_range:
        d1_str, d2_str = m_range.group(1).strip(), m_range.group(2).strip()
        d1 = parse_date_safely(d1_str)
        d2 = parse_date_safely(d2_str)
        if d1 and d2 and d2 > d1:
            diff_days = (d2 - d1).days
            months = round(diff_days / 30.4375)
            if 1 <= months <= 120:
                return months

    return None


def parse_date_safely(s: str) -> Optional[datetime]:
    formats = [
        "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y",
        "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y",
        "%B %d, %Y", "%b %d, %Y"
    ]
    cleaned = re.sub(r"(st|nd|rd|th),?", "", s).strip()
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


def extract_contract_financials(
    text: str,
    clauses: Optional[List[Dict[str, Any]]] = None,
    candidate_dates: Optional[List[Dict[str, Any]]] = None,
    contract_start_date: Optional[str] = None,
    contract_expiry_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Deterministically extracts and normalizes contractual committed value:
    1. Checks for genuine zero consideration / gratuitous agreements.
    2. Identifies explicit total contract value / fixed fee.
    3. Identifies one-time implementation/setup fees and recurring service fees.
    4. Applies contractual term duration without fabricating unstated durations.
    5. Filters liability caps, penalties, deposits, and optional fees.
    6. Guards against mixing multiple currencies.
    7. Provides transparent calculation_explanation and value_basis.
    """
    result = {
        "value": None,
        "currency": "INR",
        "value_basis": "NOT_SPECIFIED",
        "calculation_explanation": "No monetary terms or consideration specified in agreement",
        "is_verified": False,
        "one_time_fees": 0.0,
        "recurring_fee": None,
        "recurring_frequency": None,
        "term_months": None,
    }

    if not text or not text.strip():
        return result

    units: List[str] = []
    for line in text.split("\n"):
        line_s = line.strip()
        if not line_s:
            continue
        units.append(line_s)
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", line_s) if len(s.strip()) > 3]
        if len(sentences) > 1:
            units.extend(sentences)

    # 1. Check for Genuine Zero Consideration
    zero_patterns = [
        r"(?:at\s+no\s+(?:cost|charge)|free\s+of\s+charge|without\s+fee|pro\s*bono|without\s+monetary\s+consideration)",
        r"(?:total|contract)\s+value\s*(?:of|is|:)?\s*(?:INR|USD|EUR|GBP|Rs\.?|₹|\$|€|£)?\s*0(?:\.00)?\b",
        r"(?:total|fixed)\s+fee\s*(?:of|is|:)?\s*(?:INR|USD|EUR|GBP|Rs\.?|₹|\$|€|£)?\s*0(?:\.00)?\b"
    ]
    for pat in zero_patterns:
        if re.search(pat, text, re.IGNORECASE):
            result["value"] = 0.0
            result["currency"] = extract_currency(text)
            result["value_basis"] = "GENUINE_ZERO"
            result["calculation_explanation"] = "Explicitly stated as zero fee / no monetary consideration"
            result["is_verified"] = True
            return result

    # Determine term months
    term_months = extract_term_months_from_text(text, candidate_dates)
    if not term_months and contract_start_date and contract_expiry_date:
        d1 = parse_date_safely(contract_start_date)
        d2 = parse_date_safely(contract_expiry_date)
        if d1 and d2 and d2 > d1:
            diff_days = (d2 - d1).days
            calc_months = round(diff_days / 30.4375)
            if 1 <= calc_months <= 120:
                term_months = calc_months

    result["term_months"] = term_months

    # Currencies found in non-excluded financial clauses
    currencies_found = set()
    currency_amount_pattern = r"(?:(INR|USD|EUR|GBP|Rs\.?|₹|\$|€|£)\s*[\d,]+(?:\.\d+)?|[\d,]+(?:\.\d+)?\s*(INR|USD|EUR|GBP))"
    for line in units:
        if is_excluded_context(line):
            continue
        for m_curr in re.finditer(currency_amount_pattern, line, re.IGNORECASE):
            raw_c = m_curr.group(1) or m_curr.group(2)
            if raw_c:
                currencies_found.add(extract_currency(raw_c))

    # 2. Check for Explicit Total Contract Value
    # (Requirement: "Prefer explicit total contract value when available and trustworthy.")
    explicit_total_val = None
    explicit_total_curr = None
    explicit_total_match_str = ""

    explicit_patterns = [
        r"(?:total\s+contract\s+value|total\s+value\s+of\s+the\s+agreement|total\s+agreement\s+value|aggregate\s+contract\s+value)\s*(?:is|of|:)?\s*(?:INR|USD|EUR|GBP|Rs\.?|₹|\$|€|£)?\s*([\d,]+(?:\.\d+)?|\d+\s*(?:lakh|lac|crore|cr|thousand|million)s?)\b",
        r"(?:fixed\s+fee|total\s+fee|total\s+consideration|contract\s+sum|total\s+price)\s*(?:is|of|:)?\s*(?:INR|USD|EUR|GBP|Rs\.?|₹|\$|€|£)?\s*([\d,]+(?:\.\d+)?|\d+\s*(?:lakh|lac|crore|cr|thousand|million)s?)\b",
        r"shall\s+pay\s+(?:the\s+)?(?:service\s+provider|vendor|consultant|contractor|company)\s+a\s+total\s+contract\s+value\s+of\s*(?:INR|USD|EUR|GBP|Rs\.?|₹|\$|€|£)?\s*([\d,]+(?:\.\d+)?|\d+\s*(?:lakh|lac|crore|cr|thousand|million)s?)\b",
        r"shall\s+pay\s+(?:the\s+)?(?:service\s+provider|vendor|consultant|contractor|company)\s+a\s+fixed\s+fee\s+of\s*(?:INR|USD|EUR|GBP|Rs\.?|₹|\$|€|£)?\s*([\d,]+(?:\.\d+)?|\d+\s*(?:lakh|lac|crore|cr|thousand|million)s?)\b",
    ]

    for line in units:
        if is_excluded_context(line):
            continue
        for pat in explicit_patterns:
            m = re.search(pat, line, re.IGNORECASE)
            if m:
                amt_str = m.group(1)
                amt = parse_numeric_amount(amt_str)
                if amt and amt > 0:
                    curr = extract_currency(line[max(0, m.start() - 15):min(len(line), m.end() + 15)])
                    currencies_found.add(curr)
                    explicit_total_val = amt
                    explicit_total_curr = curr
                    explicit_total_match_str = line.strip()
                    break
        if explicit_total_val:
            break

    # 3. Check for One-time Fee
    one_time_val = 0.0
    one_time_curr = None
    one_time_patterns = [
        r"(?:one[- ]time|setup|implementation|onboarding|initial|upfront)\s+(?:service\s+|platform\s+)?(?:fee|charge|cost)\s*(?:is|of|:)?\s*(?:INR|USD|EUR|GBP|Rs\.?|₹|\$|€|£)?\s*([\d,]+(?:\.\d+)?|\d+\s*(?:lakh|lac|crore|cr|thousand|million)s?)\b",
        r"(?:fee|charge|cost)\s*:\s*(?:INR|USD|EUR|GBP|Rs\.?|₹|\$|€|£)?\s*([\d,]+(?:\.\d+)?)\s*(?:one[- ]time|non[- ]refundable)",
    ]

    for line in units:
        if is_excluded_context(line):
            continue
        for pat in one_time_patterns:
            m = re.search(pat, line, re.IGNORECASE)
            if m:
                amt_str = m.group(1)
                amt = parse_numeric_amount(amt_str)
                if amt and amt > 0:
                    curr = extract_currency(line[max(0, m.start() - 15):min(len(line), m.end() + 15)])
                    currencies_found.add(curr)
                    one_time_val += amt
                    one_time_curr = curr
                    break

    # 4. Check for Recurring Fee & Frequency
    recurring_val = None
    recurring_freq = None
    recurring_curr = None

    recurring_patterns = [
        # "recurring service fee: INR 25,000 per month" or "Ongoing Maintenance: INR 50,000 per month"
        r"(?:recurring|ongoing|periodic|monthly|annual|quarterly)?\s*(?:service|subscription|maintenance|license|platform|support)?\s*(?:fee|charge|cost|salary|compensation|maintenance|support|retainer)\s*(?:is|of|:)?\s*(?:INR|USD|EUR|GBP|Rs\.?|₹|\$|€|£)?\s*([\d,]+(?:\.\d+)?|\d+\s*(?:lakh|lac|crore|cr|thousand|million)s?)\s*(?:per|\/)\s*(month|year|annum|quarter|week)\b",
        # "Annual Subscription Fee: INR 12,00,000 payable annually" or "payable annually"
        r"(?:recurring|ongoing|annual|monthly|quarterly|service|subscription|maintenance|license)?\s*(?:[a-z]+\s+)?(?:fee|charge|cost|subscription|maintenance|salary)\s*(?:is|of|:)?\s*(?:INR|USD|EUR|GBP|Rs\.?|₹|\$|€|£)?\s*([\d,]+(?:\.\d+)?|\d+\s*(?:lakh|lac|crore|cr|thousand|million)s?)\s*(?:payable|billed|invoiced|paid)?\s*(monthly|annually|yearly|quarterly|weekly)\b",
        # "pays INR 12,00,000 annually"
        r"(?:pays?|paying|paid)\s*(?:INR|USD|EUR|GBP|Rs\.?|₹|\$|€|£)?\s*([\d,]+(?:\.\d+)?|\d+\s*(?:lakh|lac|crore|cr|thousand|million)s?)\s*(monthly|annually|yearly|quarterly|weekly)\b",
        # "Gross annual salary is INR 9,60,000" or "Annual Subscription Fee: INR 12,00,000"
        r"(?:gross\s+)?annual\s+(?:[a-z]+\s+)?(?:salary|subscription|fee|charge|compensation|cost)\s*(?:is|of|:)?\s*(?:INR|USD|EUR|GBP|Rs\.?|₹|\$|€|£)?\s*([\d,]+(?:\.\d+)?|\d+\s*(?:lakh|lac|crore|cr|thousand|million)s?)\b",
        # "Annual Subscription Fee | INR 12,00,000"
        r"annual\s+(?:[a-z]+\s+)?(?:fee|charge|cost|subscription|salary)\s*\|\s*(?:INR|USD|EUR|GBP|Rs\.?|₹|\$|€|£)?\s*([\d,]+(?:\.\d+)?|\d+\s*(?:lakh|lac|crore|cr|thousand|million)s?)\b",
        # "Customer pays INR 12,00,000 annually"
        r"pays?\s*(?:INR|USD|EUR|GBP|Rs\.?|₹|\$|€|£)?\s*([\d,]+(?:\.\d+)?|\d+\s*(?:lakh|lac|crore|cr|thousand|million)s?)\s+annually\b",
    ]

    for line in units:
        if is_excluded_context(line):
            continue
        for pat in recurring_patterns:
            m = re.search(pat, line, re.IGNORECASE)
            if m:
                amt_str = m.group(1)
                amt = parse_numeric_amount(amt_str)
                if amt and amt > 0:
                    curr = extract_currency(line[max(0, m.start() - 15):min(len(line), m.end() + 15)])
                    currencies_found.add(curr)
                    recurring_val = amt
                    recurring_curr = curr

                    # Determine frequency
                    freq_word = m.group(2).lower() if m.lastindex and m.lastindex >= 2 and m.group(2) else ""
                    if not freq_word:
                        if "annual" in line.lower():
                            freq_word = "annually"
                        elif "month" in line.lower():
                            freq_word = "monthly"
                        elif "quarter" in line.lower():
                            freq_word = "quarterly"

                    if "month" in freq_word:
                        recurring_freq = "MONTHLY"
                    elif "year" in freq_word or "annu" in freq_word:
                        recurring_freq = "ANNUALLY"
                    elif "quarter" in freq_word:
                        recurring_freq = "QUARTERLY"
                    elif "week" in freq_word:
                        recurring_freq = "WEEKLY"
                    else:
                        recurring_freq = "MONTHLY"
                    break
        if recurring_val is not None:
            break

    # 5. Check for Multiple Conflicting Currencies
    if len(currencies_found) > 1:
        # Multiple currencies in payment terms - conservative behavior
        result["value"] = None
        result["currency"] = list(currencies_found)[0]
        result["value_basis"] = "NEEDS_VERIFICATION"
        result["calculation_explanation"] = f"Multiple conflicting currencies detected ({', '.join(sorted(currencies_found))}); manual review required"
        result["is_verified"] = False
        return result

    primary_curr = (list(currencies_found)[0] if currencies_found else extract_currency(text))
    result["currency"] = primary_curr
    result["one_time_fees"] = one_time_val
    result["recurring_fee"] = recurring_val
    result["recurring_frequency"] = recurring_freq

    # 6. Apply Preference & Term Calculation Rules
    # Rule 1: Fixed / Explicit Total preferred when available
    if explicit_total_val is not None:
        result["value"] = explicit_total_val
        result["currency"] = explicit_total_curr or primary_curr
        result["value_basis"] = "FIXED_TOTAL"
        result["calculation_explanation"] = f"Stated contract total: {result['currency']} {explicit_total_val:,.0f}"
        result["is_verified"] = True
        return result

    # Rule 2: Component-based calculation (recurring + one-time)
    if recurring_val is not None:
        # Convert recurring to monthly rate for calculation
        if recurring_freq == "MONTHLY":
            monthly_rate = recurring_val
            freq_label = "month"
        elif recurring_freq == "ANNUALLY":
            monthly_rate = recurring_val / 12.0
            freq_label = "year"
        elif recurring_freq == "QUARTERLY":
            monthly_rate = recurring_val / 3.0
            freq_label = "quarter"
        elif recurring_freq == "WEEKLY":
            monthly_rate = recurring_val * 52.0 / 12.0
            freq_label = "week"
        else:
            monthly_rate = recurring_val
            freq_label = "month"

        # Check if duration is ambiguous
        if term_months is None:
            # Ambiguous duration -> DO NOT FABRICATE TOTAL
            result["value"] = None
            result["value_basis"] = "NEEDS_VERIFICATION"
            parts = []
            if one_time_val > 0:
                parts.append(f"one-time {primary_curr} {one_time_val:,.0f}")
            parts.append(f"recurring {primary_curr} {recurring_val:,.0f}/{freq_label}")
            result["calculation_explanation"] = f"{', '.join(parts)} identified, but contractual term duration is ambiguous"
            result["is_verified"] = False
            return result

        # Duration is known -> compute total
        computed_recurring = monthly_rate * term_months
        total = one_time_val + computed_recurring
        result["value"] = round(total, 2)
        result["value_basis"] = "CALCULATED_TERM"

        explanation_parts = []
        if one_time_val > 0:
            explanation_parts.append(f"{primary_curr} {one_time_val:,.0f} one-time")
        explanation_parts.append(f"{primary_curr} {recurring_val:,.0f}/{freq_label} × {term_months} months")
        result["calculation_explanation"] = " + ".join(explanation_parts)
        result["is_verified"] = True
        return result

    # Rule 3: Only One-Time Fee
    if one_time_val > 0:
        result["value"] = round(one_time_val, 2)
        result["value_basis"] = "ONE_TIME_FEE"
        result["calculation_explanation"] = f"One-time fee: {primary_curr} {one_time_val:,.0f}"
        result["is_verified"] = True
        return result

    # No financial terms identified
    result["value"] = None
    result["value_basis"] = "NOT_SPECIFIED"
    result["calculation_explanation"] = "No committed monetary amount identified in agreement terms"
    result["is_verified"] = False
    return result
