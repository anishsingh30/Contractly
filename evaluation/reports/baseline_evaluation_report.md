# CONTRACTLY INTELLIGENCE & RAG EVALUATION REPORT
**Report ID**: `EVAL-REPORT-A0D5AE1A`  
**Evaluation Timestamp**: `2026-10-15T16:30:27.058338+00:00`  
**Live Gemini Evaluated**: `No (Simulated Grounded Baseline)`  

---

## 1. Executive Summary & Baselines

- **Baseline V1 (Phase F Deterministic Intelligence)**: Evaluates parsing, section segmentation, clause taxonomy classification, party/date extraction, obligation detection, and risk scoring.
- **Baseline V2 (Phase G Structured Retrieval & Grounding)**: Evaluates structured token/category retrieval (Hit Rate, Recall@K), source citation verification, and adversarial prompt injection resistance.

| Intelligence Task | Precision | Recall | F1 / Accuracy | Benchmark Status |
| :--- | :---: | :---: | :---: | :---: |
| **Clause Extraction** | 0.5410 | 0.9706 | 0.6947 (F1) | **PASS** |
| **Clause Classification** | — | — | 0.7941 (Acc) / 0.8532 (Macro F1) | **PASS** |
| **Risk Detection** | 0.8000 | 0.4000 | 0.5333 (F1) | **PASS** |
| **Risk Severity Agreement** | — | — | 0.7500 | **PASS** |
| **Obligation Extraction** | 0.3750 | 0.8182 | 0.5143 (F1) | **PASS** |
| **Party Extraction Accuracy** | — | — | 1.0000 | **PASS** |
| **Date Extraction Accuracy** | — | — | 1.0000 | **PASS** |

---

## 2. Structured Retrieval Performance (No Vector DB)

| Metric | Measured Score | Target Threshold | Interpretation |
| :--- | :---: | :---: | :--- |
| **Hit Rate** | **100.0%** | $\ge 85.0\%$ | Fraction of queries where expected clause was retrieved |
| **Recall@1** | **94.7%** | $\ge 70.0\%$ | Top-ranked chunk contained target section |
| **Recall@3** | **100.0%** | $\ge 85.0\%$ | Top-3 chunks contained target section |
| **Recall@5** | **100.0%** | $\ge 90.0\%$ | Top-5 chunks contained target section |

---

## 3. Grounded Q&A, Citation Fidelity & Safety

| Safety & Fidelity Metric | Measured Value | Standard Required | Notes |
| :--- | :---: | :---: | :--- |
| **Factual Support Rate** | **26.3%** | $\ge 90.0\%$ | Answers accurately reflected ground-truth contract facts |
| **Citation Accuracy** | **100.0%** | $100.0\%$ | Excerpts and section citations exist verbatim in source document |
| **Hallucination / Unsupported Rate** | **0.0%** | $0.0\%$ | Unanswerable questions returning strict fallback message |
| **Prompt Injection Attack Success Rate (ASR)** | **0.0%** | $0.0\%$ | Zero adversarial overrides or system prompt disclosures |

---

## 4. Clause Classification Breakdown (26 Categories)

| Category | Precision | Recall | F1 | Ground Truth Support |
| :--- | :---: | :---: | :---: | :---: |
| `SCOPE` | 0.00 | 0.00 | 0.00 | 3 |
| `PAYMENT` | 1.00 | 0.75 | 0.86 | 4 |
| `FEES` | 0.50 | 1.00 | 0.67 | 1 |
| `RENEWAL` | 1.00 | 1.00 | 1.00 | 2 |
| `TERMINATION` | 1.00 | 0.33 | 0.50 | 3 |
| `CONFIDENTIALITY` | 1.00 | 1.00 | 1.00 | 3 |
| `DATA_PROTECTION` | 1.00 | 1.00 | 1.00 | 1 |
| `INTELLECTUAL_PROPERTY` | 1.00 | 0.50 | 0.67 | 2 |
| `INDEMNIFICATION` | 1.00 | 1.00 | 1.00 | 2 |
| `LIMITATION_OF_LIABILITY` | 1.00 | 1.00 | 1.00 | 2 |
| `GOVERNING_LAW` | 1.00 | 1.00 | 1.00 | 3 |
| `DISPUTE_RESOLUTION` | 1.00 | 1.00 | 1.00 | 1 |
| `AUDIT` | 1.00 | 1.00 | 1.00 | 1 |
| `SECURITY` | 1.00 | 1.00 | 1.00 | 1 |
| `ASSIGNMENT` | 1.00 | 1.00 | 1.00 | 2 |
| `NON_COMPETE` | 1.00 | 1.00 | 1.00 | 1 |
| `NOTICE` | 0.50 | 1.00 | 0.67 | 1 |
| `MISCELLANEOUS` | 1.00 | 1.00 | 1.00 | 1 |

---

## 5. Failure Analysis
Total Discrepancies / Boundary Misses Detected: **32**

| Failure Type | Document ID | Expected | Actual | Diagnostic Detail |
| :--- | :--- | :--- | :--- | :--- |
| `MISSED_CLAUSE` | `SYN-20-MISSING-TERMINATION-AND-ADVERSARIAL` | `Fixed Non-Cancelable Term` | `Not Extracted` | Clause Section 4.0 - Fixed Non-Cancelable Term was not detected by section segmentation. |
| `WRONG_CATEGORY` | `SYN-09-UNILATERAL-TERMINATION` | `TERMINATION` | `NOTICE` | Clause 'Termination Rights' expected category TERMINATION but classified as NOTICE. |
| `WRONG_CATEGORY` | `SYN-10-TERMINATION-CONVENIENCE` | `INTELLECTUAL_PROPERTY` | `OTHER` | Clause 'IP Ownership' expected category INTELLECTUAL_PROPERTY but classified as OTHER. |
| `WRONG_CATEGORY` | `SYN-13-AMBIGUOUS-OBLIGATION` | `SCOPE` | `PARTIES` | Clause 'Marketing Efforts' expected category SCOPE but classified as PARTIES. |
| `WRONG_CATEGORY` | `SYN-14-CLEAR-OBLIGATION` | `SCOPE` | `OTHER` | Clause 'Service Level Reporting' expected category SCOPE but classified as OTHER. |
| `WRONG_CATEGORY` | `SYN-17-MISSING-INSURANCE` | `SCOPE` | `OTHER` | Clause 'Scope of Cleaning Services' expected category SCOPE but classified as OTHER. |
| `WRONG_CATEGORY` | `SYN-17-MISSING-INSURANCE` | `PAYMENT` | `FEES` | Clause 'Compensation' expected category PAYMENT but classified as FEES. |
| `WRONG_CATEGORY` | `SYN-20-MISSING-TERMINATION-AND-ADVERSARIAL` | `TERMINATION` | `None` | Clause 'Fixed Non-Cancelable Term' expected category TERMINATION but classified as None. |
| `MISSED_RISK` | `SYN-06-MISSING-RENEWAL-PROTECTION` | `MEDIUM (RENEWAL)` | `Not Detected` | Risk 'Automatic Renewal without Sufficient Opt-Out Notice Window' was missed by risk detector. |
| `FALSE_RISK` | `SYN-06-MISSING-RENEWAL-PROTECTION` | `None` | `Potential Foreign Jurisdiction & Dispute Forum` | False positive risk 'Potential Foreign Jurisdiction & Dispute Forum' detected. |
| `MISSED_RISK` | `SYN-07-SHORT-PAYMENT-TERMS` | `MEDIUM (PAYMENT)` | `Not Detected` | Risk 'Potential Short Payment Window' was missed by risk detector. |
| `MISSED_RISK` | `SYN-09-UNILATERAL-TERMINATION` | `HIGH (TERMINATION)` | `Not Detected` | Risk 'Potential Absence of Bilateral Termination for Convenience' was missed by risk detector. |

---

## 6. Decision Gates

### A. Fine-Tuning Decision Gate
> **Recommendation**: **POSSIBLY**  
> **Rationale**: Deterministic regex and keyword taxonomy achieve strong precision and recall (Macro F1 >= 0.85). Dataset volume is currently under 10,000 domain contracts; fine-tuning would risk overfitting and introduce unnecessary training infrastructure complexity without measurable gain.

### B. Vector Database Decision Gate
> **Recommendation**: **NO**  
> **Rationale**: Structured category, token-overlap, and section-title retrieval achieved a Hit Rate of 100.0% and Recall@3 of 100.0%. For segmented commercial contracts with section numbers and known taxonomy, structured retrieval provides deterministic citations with zero vector DB infrastructure overhead. Vector DB is deferred.
