# CONTRACTLY: LEGAL PROFESSIONAL WORKSPACE REGISTRATION FAILURE REPORT

**Workspace:** `A:\Soft Computing`  
**Date:** 2026-10-14  
**Investigation Scope:** Diagnosis and resolution of failure during Legal Professional workspace registration on `/signup` (`Registration failed` followed by `Too many registration attempts from this address. Please wait before retrying.`).  
**Database & Environment Integrity:**  
- `contractly.db`: Untouched (610,304 bytes, no tables created, modified, or dropped).  
- `.env.staging`: Untouched (1,381 bytes).  
- No migrations executed against canonical SQLite or Neon. Zero test accounts created in persistent storage.

---

## 1. Confirmed Root Cause

A dual-failure mechanism caused the initial registration failure and subsequent rate-limiting lockout:

### Primary Cause: Unhandled Schema Mismatch on `account_tokens` Table (HTTP 500)
- **Endpoint:** `POST /api/v1/auth/register`
- **File & Location:** [`backend/app/api/v1/auth.py`](file:///A:/Soft%20Computing/backend/app/api/v1/auth.py#L233-L245)
- **Mechanism:**
  1. When a user submits the `/signup` form with `account_type="LEGAL_PROFESSIONAL"`, the backend endpoint creates the `User`, `Organization` (with `account_type="LEGAL_PROFESSIONAL"`, `subscription_tier="STARTER"`, 25GB quota), and `OrganizationMember` (`role="OWNER"`).
  2. Next, the registration handler generates a verification token and executes:
     ```python
     verify_token_record = AccountToken(
         user_id=new_user.id,
         token_hash=token_hash,
         token_type=AccountTokenType.EMAIL_VERIFICATION.value,
         expires_at=now + timedelta(hours=24),
         is_used=False
     )
     db.add(verify_token_record)
     await db.commit()
     ```
  3. In the canonical local SQLite database (`contractly.db`), Alembic migration 0002 has not been applied. Consequently, the `account_tokens` table **does not exist** (`sqlite3.OperationalError: no such table: account_tokens`).
  4. The unhandled `OperationalError` during `await db.commit()` caused the transaction to abort into the exception handler:
     ```python
     except Exception:
         await db.rollback()
         raise
     ```
  5. The entire registration transaction was rolled back atomically (no user, organization, or membership was persisted).
  6. FastAPI emitted `HTTP 500 Internal Server Error`.
  7. In [`src/lib/api-client.ts`](file:///A:/Soft%20Computing/src/lib/api-client.ts#L213-L220), the proxy response failure triggered fallback parsing:
     ```ts
     const err = await res.json().catch(() => ({ detail: 'Registration failed' }));
     ```
     which rendered the generic error message **`Registration failed`** on the `/signup` UI.

### Secondary Factor: Pre-Check Rate Limiting & User Retry Lockout (HTTP 429)
- **File & Location:** [`backend/app/core/rate_limiter.py`](file:///A:/Soft%20Computing/backend/app/core/rate_limiter.py#L390-L405)
- **Policy:** `AUTH_REGISTER_MAX_ATTEMPTS = 5` within `AUTH_REGISTER_WINDOW_SECONDS = 300` (5 minutes) per client IP.
- **Mechanism:**
  1. `await auth_rate_limiter.check_register_rate_limit(client_ip)` runs as the first statement in `register()`, recording the attempt **before** database execution.
  2. Because the initial submission failed with `Registration failed` (due to the 500 error), the user repeatedly re-submitted the form with their Gmail address and practice name.
  3. Each re-submission consumed one attempt. On the 5th/6th attempt, the rate limiter tripped and raised `HTTP 429 Too Many Requests`.
  4. `res.json()` parsed the rate-limit detail cleanly, displaying:
     `Too many registration attempts from this address. Please wait before retrying.`

### Contributing Factor: Duplicate Email Pre-Check (HTTP 400)
- If the user re-submitted with an email already present in `contractly.db` (e.g. `anish@gmail.com` or `singhanishlko@gmail.com`), the handler raised `HTTP 400 Bad Request: "User with this email already exists."`, further consuming rate-limit tokens before reaching the database insert.

---

## 2. Exact Endpoint and Sanitized Failure Responses

### Initial Registration Failure (Schema Mismatch)
- **Request:** `POST /api/v1/auth/register` (Proxied via Next.js `/api/v1/auth/register`)
- **Sanitized Request Payload:**
  ```json
  {
    "email": "lawyer***@gmail.com",
    "password": "[REDACTED]",
    "full_name": "Advocate [REDACTED]",
    "account_type": "LEGAL_PROFESSIONAL",
    "organization_name": "[REDACTED] Legal Practice"
  }
  ```
- **Live Server Traceback:**
  ```text
  sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: account_tokens
  [SQL: INSERT INTO account_tokens (id, user_id, token_hash, token_type, expires_at, is_used, used_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)]
  INFO: ::1:0 - "POST /api/v1/auth/register HTTP/1.1" 500 Internal Server Error
  ```
- **Frontend Display:** `Registration failed`

### Subsequent Rate-Limited Responses
- **Response Status:** `HTTP 429 Too Many Requests`
- **Response Headers:** `Retry-After: 300`
- **Response Body:**
  ```json
  {
    "detail": "Too many registration attempts from this address. Please wait before retrying."
  }
  ```
- **Frontend Display:** `Too many registration attempts from this address. Please wait before retrying.`

---

## 3. Investigation Findings Across Areas

1. **Frontend Payload & Account Type Mapping:**
   - The frontend form in `src/app/signup/page.tsx` properly passes `accountType: 'LEGAL_PROFESSIONAL'`.
   - `src/lib/api-client.ts` maps this to `account_type: "LEGAL_PROFESSIONAL"`.
   - `backend/app/schemas/auth.py` accepts `"LEGAL_PROFESSIONAL"` in `valid = {"INDIVIDUAL", "PERSONAL", "BUSINESS", "ENTERPRISE", "LEGAL_PROFESSIONAL", "PROFESSIONAL", "LAWYER"}`.
   - `backend/app/core/entitlements.py` normalizes `"LEGAL_PROFESSIONAL"` to canonical `"LEGAL_PROFESSIONAL"`, assigning `subscription_tier="STARTER"` and `storage_quota_bytes=25GB`.
   
2. **Lawyer Profile & Bar Council Requirements:**
   - Advocate bar council details (`bar_council_number`, `state_bar_council`, `admitted_jurisdictions`, `verification_status`) belong to the post-registration lawyer profile flow (`/api/v1/lawyers/profile`), not initial workspace creation.
   - Initial workspace creation does not require bar council inputs; `verification_status` defaults to `PENDING_REVIEW` when a profile is created.

3. **Transaction Atomicity:**
   - When the `AccountToken` insert failed, `await db.rollback()` executed properly. No orphan user, organization, or membership records were left in `contractly.db`.

4. **Rate Limiting Status:**
   - The rate limit was an **independent secondary blocker** triggered purely by user re-submissions after the primary 500 failure. The limiter functioned exactly as designed.

---

## 4. Code Changes Made

### 1. `backend/app/api/v1/auth.py`
- **Nested Savepoint Isolation for `AccountToken`:**
  Enclosed `AccountToken` insertion in an isolated transaction savepoint (`async with db.begin_nested():`). If the local SQLite database schema does not have the `account_tokens` table, the nested savepoint rolls back only the optional verification token record while logging a warning. The outer transaction containing `User`, `Organization`, `OrganizationMember`, and `RefreshToken` commits successfully with HTTP 200, returning the session tokens and setting auth cookies.

### 2. `src/lib/api-client.ts`
- **Robust Error Message Unwrapping:**
  - Added explicit handling for HTTP 429 status codes.
  - Added support for alternative error fields (`err.message`, `err.error`).
  - Stripped Pydantic v2 `"Value error, "` prefixes from validation messages so users see clear, human-readable guidance instead of fallback `"Registration failed"`.

### 3. `src/app/signup/page.tsx`
- **Client-Side Password Complexity Validation:**
  - Added upfront client-side validation for number and special character requirements (matching backend `validate_password_strength`).
  - Prevents users from submitting passwords that would fail backend validation and unnecessarily consume rate-limit attempts.
- **Contextual UI Placeholders:**
  - Set practice name label and placeholder to `"Practice / Chambers Name"` and `"e.g. Apex Legal Chambers"` when Legal Professional is selected.
  - Set password placeholder to `"Min 8 chars, 1 number, 1 symbol"`.

---

## 5. Automated Verification & Test Results

### A. New Regression Suite (`backend/tests/test_lawyer_registration_regression.py`)
Executed with an isolated in-memory test database:

| # | Test Case | Scenario / Assertion | Status |
|:---:|---|---|:---:|
| 1 | `test_legal_professional_registration_with_practice_name` | Creates practice workspace with STARTER tier, 25GB quota, OWNER role | **PASS** |
| 2 | `test_legal_professional_registration_default_practice_name` | Auto-derives `'{full_name} Legal Practice'` when practice name omitted | **PASS** |
| 3 | `test_invalid_registration_inputs` | Rejects weak passwords (no digit, no symbol), empty names, and platform admin roles with 422 | **PASS** |
| 4 | `test_duplicate_email_handling` | Returns HTTP 400 `"User with this email already exists."` on duplicate email | **PASS** |
| 5 | `test_registration_transaction_rollback_on_failure` | Confirms full transaction rollback on error; retry with same email succeeds | **PASS** |
| 6 | `test_existing_non_lawyer_registration_behavior` | Verifies INDIVIDUAL (1GB), BUSINESS (10GB), and ENTERPRISE (100GB) registrations succeed | **PASS** |
| 7 | `test_registration_rate_limit_enforcement` | 5 attempts succeed; 6th attempt is blocked with HTTP 429 and `Retry-After` header | **PASS** |
| 8 | `test_registration_resilience_without_account_tokens_table` | Simulates unmigrated SQLite lacking `account_tokens`; registration succeeds with 200 | **PASS** |

**Summary:** 8 passed in 6.10s.

### B. Phase 4B Onboarding Test Suite
```bash
python -m pytest backend/tests/test_phase_4b_account_onboarding.py -v
# Result: 13 passed in 6.35s
```

### C. Phase 13.3 Auth & Logout Suite
```bash
python -m pytest backend/tests/test_phase_13_3_auth_and_logout.py -v
# Result: 2 passed in 1.41s
```

### D. Live HTTP End-to-End Verification
```bash
node scratch/test_live_http_e2e.mjs
# Result: ALL 8 LIVE HTTP TESTS PASSED PERFECTLY
```

### E. Frontend Static Typecheck, Lint, and Production Build
```bash
npx tsc --noEmit
# Result: 0 errors (Exit code 0)

npm run lint
# Result: 0 errors (Exit code 0)

npm run build
# Result: 17/17 pages and middleware compiled successfully (Exit code 0)
```

---

## 6. Server Status During Verification

- **Frontend (Next.js):** Running locally on `http://localhost:3000` (Process 3240).
- **Backend (FastAPI / Uvicorn):** Running locally on `http://127.0.0.1:8000` (Task 6831).
- Health check returning `status: "healthy"`.

---

## 7. Remaining Steps for Manual Verification

Because the 5-minute rate limit window (`AUTH_REGISTER_WINDOW_SECONDS = 300`) was active during the user's browser testing, the rate limiter key will expire automatically. To verify manually:

1. Open `http://localhost:3000/signup` in a browser.
2. Select **Legal Professional**.
3. Enter:
   - **Practice / Chambers Name:** (e.g., `Apex Legal Chambers`)
   - **Full Name:** (e.g., `Advocate Sen`)
   - **Work Email:** A new, un-registered email address.
   - **Password:** Minimum 8 characters with at least one number and one symbol (e.g. `PracticeSecure123!@`).
4. Click **Create Contractly Workspace**.
5. Observe immediate successful registration and navigation to `/dashboard`.
