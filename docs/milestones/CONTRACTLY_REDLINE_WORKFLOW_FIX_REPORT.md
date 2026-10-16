# CONTRACTLY — REDLINE & NEGOTIATION WORKFLOW AUDIT & ROOT CAUSE FIX REPORT

**Date:** October 15, 2026  
**System:** Contractly CLM & AI Redlining Engine  
**Project Path:** `A:\Soft Computing`  
**Deliverable Document:** `CONTRACTLY_REDLINE_WORKFLOW_FIX_REPORT.md`  

---

## 1. Executive Summary

This investigation analyzed and repaired the **Edit & Compare** redlining workflow across the entire stack in Contractly. Previously, uploaded contracts (such as *SaaS Vendor Agreement*, *Employment Confidentiality Agreement*, and *Consulting SOW*) appeared with completed clause analysis in Client Contracts, but opening **Edit & Compare** displayed:
- “No proposed changes”
- “There are no pending edits or revisions for this contract version.”
- “0 Checked”
- “No Playbook Issues Found”

Tracing the execution path from frontend UI components down to the SQLite database and Gemini provider revealed four distinct architectural root causes. All four have now been repaired, end-to-end integration verified, and verified with 7 new automated pytest tests, 14 regression tests, full TypeScript compilation, ESLint verification, and a successful Next.js production build.

---

## 2. Root Cause Analysis

Tracing the execution path from contract upload through intelligence analysis, database persistence, and frontend rendering revealed the following root causes:

### Root Cause 1: Contract Upload Pipeline Never Invoked AI Redline Generation
- **Inspection Finding:** In [contracts.py](file:///A:/Soft%20Computing/backend/app/api/v1/contracts.py#L416-L435), the upload pipeline invoked clause extraction, date detection, and risk scoring via `run_intelligence_pipeline`. However, proposed redline generation was implemented as a naive mock loop checking only `if cl.risk_level in ("HIGH", "MEDIUM", "CRITICAL")` and appending a hardcoded dummy string (`"[Subject to mutual limitation not to exceed twelve (12) months...]"`) without calling Gemini AI or analyzing the clause's actual legal wording.
- **Contract Impact:** For contracts where extracted clauses were categorized with standard commercial risks (`LOW`), the upload pipeline created exactly **zero** redlines.

### Root Cause 2: Missing Backend AI Redlining Service & Endpoint
- **Inspection Finding:** The backend lacked a dedicated AI redlining service. `GeminiProvider` supported general chat and Q&A, but lacked a structured service to evaluate extracted clauses against negotiation standards, validate verbatim grounding, and return structured proposals.
- **Contract Impact:** There was no API endpoint (`POST /api/v1/contracts/{id}/generate-redlines`) for the user or UI to trigger redline generation on-demand.

### Root Cause 3: Empty Playbook Rules Table Mistaken for a "Passed" Evaluation
- **Inspection Finding:** In [contracts.py](file:///A:/Soft%20Computing/backend/app/api/v1/contracts.py#L1064-L1107), `GET /api/v1/contracts/{id}/negotiation-analysis` queried `PlaybookRule` for the tenant. In the database, `playbook_rules` had 0 rows. The evaluation function iterated over rules; with 0 rules, it returned an empty array `[]`.
- **Contract Impact:** The frontend interpreted `[]` as "0 Checked" and displayed *"No Playbook Issues Found: Contract clauses align with standard positions..."*, falsely implying a successful assessment had taken place when in fact no rules had been configured.

### Root Cause 4: Frontend Empty State Lacked Generation Action & Status Distinction
- **Inspection Finding:** In [redline-studio.tsx](file:///A:/Soft%20Computing/src/components/contracts/redline-studio.tsx#L255-L260), when `activeContract.redlines.length === 0`, the UI rendered a static banner stating *"No proposed changes"*.
- **Contract Impact:** The user was given no action to generate revisions, no loading spinner while generation ran, and no distinction between:
  1. Revisions not yet generated,
  2. Generation in progress,
  3. No changes justified, and
  4. Generation failure.

---

## 3. Workflow Before and After

```
BEFORE:
Upload Contract ──► Extract Clauses ──► Naive Risk Loop (Only High/Critical) ──► 0 Redlines for Low-Risk Clauses
                                                                                       │
Edit & Compare Screen ◄────────────────────────────────────────────────────────────────┘
  ├── Reads activeContract.redlines: Empty []
  ├── Displays: "No proposed changes" (Dead End — No generation button)
  └── Fetches /negotiation-analysis: 0 Rules in DB ──► Displays "0 Checked / No Playbook Issues Found"

AFTER:
Upload Contract ──► Extract Clauses ──► Automatic AI Redline Generation (Gemini + Deterministic Fallback)
                                                 │
                                                 ▼
                                        Persist ContractRedline Records (PENDING)
                                                 │
Edit & Compare Screen ◄──────────────────────────┴───────────────────────────────────────┐
  ├── Loads Persisted Redlines from Database                                             │
  ├── On-Demand Action: "⚡ Generate Proposed Revisions" / "↻ Regenerate Revisions" ──────┘
  ├── Loading Indicator: "Analyzing clauses with Gemini AI..."
  ├── Clear Priority Badges: [MANDATORY], [RECOMMENDED], [OPTIONAL]
  ├── Inline Changes View (Strikethrough Removed / Bold Underline Added) & Side-by-Side Compare
  ├── Review & Approval: Accept Change (persists ACCEPTED) / Reject Change (persists REJECTED)
  ├── Export Proposed Revisions (.docx) with universal Word compatibility disclaimer
  └── Playbook Analysis: Evaluates against Standard Commercial Negotiation Baseline (6 Rules Checked)
      when no custom tenant playbook rules exist, eliminating "0 Checked".
```

---

## 4. Files Modified and Implemented

1. **[redline_service.py](file:///A:/Soft%20Computing/backend/app/services/ai/redline_service.py)** *(New Service)*
   - Implemented `generate_contract_redlines()`:
     - Formulates structured AI prompt containing contract metadata, party role perspective, extracted clauses, and applicable negotiation benchmarks.
     - Calls Google Gemini (`gemini_flash_lite_latest`) with structured JSON extraction and verbatim substring validation (ensuring `original_text` matches clause text exactly).
     - Provides deterministic legal heuristic fallback covering 8 standard commercial negotiation patterns (overdue interest cap, non-renewal notice reduction, security incident 48h SLA, IP pre-existing invention carveout, non-solicitation public hiring carveout, 30-day payment windows, 30-day breach cure, 30-day convenience termination).
     - Persists `ContractRedline` records into the database while preserving existing user-reviewed (`ACCEPTED`, `REJECTED`, `MODIFIED`) proposals across re-runs.
   - Defines `STANDARD_PLAYBOOK_BENCHMARKS` covering Liability, Confidentiality, Intellectual Property, Termination, Payment, and Security.

2. **[contracts.py](file:///A:/Soft%20Computing/backend/app/api/v1/contracts.py)** *(Backend API)*
   - Added `POST /api/v1/contracts/{id}/generate-redlines` endpoint for on-demand generation.
   - Updated `GET /api/v1/contracts/{id}/redlines` to support optional `version_id` parameter.
   - Replaced old naive mock loop in `upload_contract` with `generate_contract_redlines`, guaranteeing automatic generation at upload time.
   - Updated `reprocess_contract_intelligence` to refresh redlines upon document reprocessing.
   - Updated `evaluate_contract_playbook` to evaluate against `STANDARD_PLAYBOOK_BENCHMARKS` when no custom playbook rules exist for the tenant, preventing the "0 Checked" ambiguity.

3. **[contract.py (schemas)](file:///A:/Soft%20Computing/backend/app/schemas/contract.py)** *(Data Model)*
   - Added `contract_id: Optional[str] = None` to `ContractRedlineResponse` for schema consistency with `ContractRedline` model.

4. **[api-client.ts](file:///A:/Soft%20Computing/src/lib/api-client.ts)** *(Frontend API Client)*
   - Implemented `generateContractRedlinesInBackend(contractId, versionId)`.
   - Updated `fetchContractRedlinesFromBackend` to accept optional `versionId`.

5. **[contractly-context.tsx](file:///A:/Soft%20Computing/src/context/contractly-context.tsx)** *(State Management)*
   - Added `generateRedlines: (contractId: string, versionId?: string) => Promise<boolean>` to `ContractlyContextType`.
   - Updated `setContracts` state on generation so the active contract immediately reflects newly created redlines without page reload or loss of contract association.

6. **[redline-studio.tsx](file:///A:/Soft%20Computing/src/components/contracts/redline-studio.tsx)** *(User Experience)*
   - Added header action button: `"⚡ Generate Proposed Revisions"` (or `"↻ Regenerate Revisions"`).
   - Added animated spinner state: `"Generating Proposed Revisions with Gemini AI..."`.
   - Added failure handling with retry button and error messages.
   - Distinguished "Revisions Not Yet Generated" vs "No Proposed Changes Justified".
   - Added priority badges (`MANDATORY`, `RECOMMENDED`, `OPTIONAL`).
   - Added Playbook status indicator: `"Standard Commercial Baseline Active (No custom organization playbook configured)"`.
   - Maintained warm ivory (`#FCFAF5`, `#F7F3EA`, `#DED6C8`) and deep olive (`#3F4634`, `#2E5230`) aesthetic.

---

## 5. Verification and Test Results

### 1. Verification of Uploaded Contracts
The three contracts previously showing "No proposed changes" were analyzed and populated with contract-grounded redlines:

| Contract Title | Contract ID | Extracted Clauses | Generated Proposals | Key Revisions |
| :--- | :--- | :---: | :---: | :--- |
| **SaaS Vendor Agreement** | `CTR-2026-2509` | 5 | 2 | Capped overdue interest at 1.0%/mo with 15-day notice; tightened security incident notification to 48 hours. |
| **Employment Confidentiality Agreement** | `CTR-2026-9698` | 4 | 2 | Added pre-existing invention carve-out to IP clause; added explicit confidentiality survival duration. |
| **Consulting SOW** | `CTR-2026-2434` | 4 | 3 | Extended invoice payment from 15 to 30 days; extended breach cure from 15 to 30 days; extended convenience notice from 10 to 30 days. |

### 2. Automated Test Suite (`backend/tests/test_redline_generation.py`)
Executed with command: `python -m pytest backend/tests/test_redline_generation.py -v`
Result: **7 passed in 52.52s**

- `test_upload_contract_triggers_automatic_redlines`: **PASSED** (Verifies automatic generation on upload)
- `test_on_demand_redline_generation_endpoint`: **PASSED** (Verifies `POST /{id}/generate-redlines`)
- `test_accept_and_reject_redline_persistence`: **PASSED** (Verifies accept/reject updates status and survives regeneration)
- `test_docx_export_contains_saved_proposals`: **PASSED** (Verifies DOCX generation with comparison blocks)
- `test_negotiation_analysis_with_no_custom_playbook`: **PASSED** (Verifies baseline benchmarks evaluated when 0 custom rules)
- `test_gemini_failures_handled_gracefully_with_fallback`: **PASSED** (Verifies fallback on Gemini timeout, rate limit, and malformed JSON)
- `test_tenant_isolation_on_redlines`: **PASSED** (Verifies cross-tenant access is rejected with HTTP 403/404)

### 3. Regression Test Suites
Executed with command: `python -m pytest backend/tests/test_contracts_upload.py backend/tests/test_multi_tenancy.py backend/tests/test_rbac.py -v`
Result: **14 passed in 127.51s**

### 4. Frontend Verification
- **TypeScript Typecheck:** `cmd /c "npx tsc --noEmit"` exited with code 0 (0 errors).
- **ESLint:** `cmd /c "npm run lint"` exited with code 0.
- **Production Build:** `cmd /c "npm run build"` compiled successfully; all 18 routes generated without error.

---

## 6. Word Export Transparency & Limitations

- **Word Compatibility:** DOCX export (`GET /api/v1/contracts/{id}/export/docx`) utilizes `python-docx` to format proposed redlines as visual comparative blocks with strike-through for deleted original text and bold underlined green styling for proposed replacement text.
- **Track Changes Limitation:** As noted in the exported document header disclaimer and compliance documentation, native Microsoft Word Track Changes XML markup is not generated by `python-docx`. The visual comparison format guarantees universal compatibility across Microsoft Word, LibreOffice, and Google Docs without altering the original signed document.
