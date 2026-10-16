# Contractly Phase 13: Production Readiness Gap Audit Report

**Date:** October 14, 2026  
**Auditor:** Antigravity Autonomous Pair Programming Agent  
**Environment Audited:** Contractly Platform (FastAPI Async Backend + Next.js 14 App Router + Neon PostgreSQL Staging + Google Gemini AI + SMTP + Storage Engine)  
**Safety Status:** Strictly Read-Only Audit. Zero application code or database configuration modified. Zero infrastructure altered. Canonical SQLite database and staging PostgreSQL databases fully preserved.

---

## Executive Summary & Launch Recommendation

| Dimension | Assessment | Status |
| :--- | :--- | :--- |
| **Final Recommendation** | **NO-GO FOR PUBLIC CUSTOMER LAUNCH** (Pending Remediation of 6 Blockers) | 🔴 **BLOCKED** |
| **Staging Infrastructure** | Neon PostgreSQL operational; migrations in sync; direct & pooled connectivity verified | 🟢 **READY** |
| **Database Parity** | Zero DDL drift between SQLite canonical schema and Neon PostgreSQL | 🟢 **READY** |
| **Gemini AI Core** | API key, DNS, outbound TLS 1.3, model catalog, and live QA responses verified | 🟡 **CONDITIONAL** (Timeout bug fix needed) |
| **Storage Architecture** | Multi-tenant S3 adapter implemented; bypassed by hardcoded local imports | 🔴 **BLOCKED** |
| **Distributed Rate Limiting** | Fail-closed logic written; missing runtime `redis` package in environment | 🔴 **BLOCKED** |
| **Email Delivery** | SMTPEmailProvider tested in mock; unconfigured in staging/production | 🟡 **BLOCKED (CONFIG)** |
| **Security & Auth** | Platform role isolation verified; CORS restricted to localhost; cookies secure | 🟡 **BLOCKED (CONFIG)** |
| **Legal & Disclaimers** | Privacy Policy, Terms of Service, non-adjudicative disclaimers in place | 🟢 **READY** |

### Launch Decision Rationale
Contractly's foundational multi-tenant data architecture, relational database parity across SQLite and PostgreSQL, security authorization model, and legal disclaimers are mature, well-tested, and robust. However, **Contractly cannot safely launch to paying, multi-tenant customers today** because of six critical blocking findings (P0) across file storage, distributed caching, network resiliency, email delivery, and production routing. 

Once the prioritized P0 remediation sequence detailed in Section 11 is executed and verified, Contractly will be fully prepared for public production deployment.

---

## Prioritized Findings Matrix

| Finding ID | Domain | Title | Severity | Impact | Remediation Effort |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P0-01** | Storage | API endpoints hardcode `storage.local`; bypassing S3 provider proxy | **P0 (Blocker)** | Files lost in multi-container / serverless deployments | Low (<1 hour) |
| **P0-02** | Redis | `redis` Python package missing from `requirements.txt` and environment | **P0 (Blocker)** | Crash on startup if `REDIS_URL` set; HTTP 503 if `REDIS_REQUIRED` | Low (<30 mins) |
| **P0-03** | Gemini AI | Single timeout immediately aborts without retry or model fallback | **P0 (Blocker)** | Staging Q&A failures, false outages during Google API transient latency | Low (<1 hour) |
| **P0-04** | Email | SMTP credentials unconfigured & `APP_BASE_URL` points to `localhost:3000` | **P0 (Blocker)** | Verification & reset links in emails direct users to localhost | Low (<30 mins) |
| **P0-05** | Security | CORS `ALLOWED_ORIGINS` restricted to localhost / 127.0.0.1 | **P0 (Blocker)** | Frontend hosted on production domain blocked by browser CORS | Low (<15 mins) |
| **P0-06** | Storage | No frontend UI binding for contract document download endpoint | **P0 (Blocker)** | Users cannot download original PDF/DOCX agreements after upload | Medium (1-2 hours) |
| **P1-01** | UTC / Dates | Naive UTC datetime serialization lacks trailing `Z` timezone indicator | **P1 (High)** | Client-side `new Date()` parses as local time, creating timezone shifts | Low (<1 hour) |
| **P1-02** | Operations | `backup.py` relies on `pg_dump` binary missing from standard PATH | **P1 (High)** | Scheduled CLI database dump jobs fail on host without PostgreSQL client | Low (Docs / Neon PITR) |
| **P1-03** | Performance | Synchronous `smtplib.sendmail` called directly on async event loop | **P1 (High)** | Slow SMTP connections block FastAPI asyncio worker for all tenants | Low (<1 hour) |
| **P1-04** | Security | 7 high-severity `npm audit` vulnerabilities in frontend build tooling | **P1 (High)** | Build-time supply chain risk (`braces` / `micromatch` in Tailwind 3) | Medium (1 hour) |
| **P2-01** | Frontend | ESLint exhaustive-deps warnings in Calendar, Notes, and Tasks | **P2 (Medium)** | Potential stale state closures under rapid user tab switching | Low (<1 hour) |
| **P2-02** | Observability | Absence of structured JSON logging and Sentry / OpenTelemetry SDK | **P2 (Medium)** | Difficulty triaging live exceptions in multi-tenant production | Medium (2 hours) |

---

## 1. Gemini AI Integration & Staging Timeout Root Cause

### Diagnostic Findings & Live Connectivity Proof
In Phase 12 staging E2E tests, live contract Q&A timed out after 30 seconds (`Gemini request timed out after 30.0 seconds`). During this Phase 13 audit, we executed non-invasive, live network and API diagnostics to inspect the health of the Gemini service:

1. **DNS Resolution:** `generativelanguage.googleapis.com` resolves successfully to Google anycast addresses (`142.250.193.10`, `142.250.193.74`).
2. **Network Layer:** Outbound TCP handshake to port 443 completed in 32ms.
3. **Transport Layer:** TLS 1.3 negotiation with Google edge servers succeeded without cipher degradation.
4. **Authentication & Catalog:** Successfully queried `GET /v1beta/models` using the configured staging key (`HTTP 200` in 0.35s). Returned 46 operational models, confirming that the Google Cloud project and API key are active and valid.
5. **Direct Completion Probe:** Tested raw `generateContent` with `gemini-flash-lite-latest`. The API responded with `HTTP 200` in **1.11 seconds**.
6. **End-to-End Contract Q&A Probe:** Tested real legal text analysis with grounded context (12-page MSA terms). The API responded with `HTTP 200` in **5.02 seconds**, correctly citing Section 14.0 and appending Contractly's non-adjudicative disclaimer.

### Root Cause Analysis of the Staging Timeout
Inspection of [backend/app/services/ai/gemini_provider.py](file:///A:/Soft%20Computing/backend/app/services/ai/gemini_provider.py#L220-L294) revealed the exact failure mechanism:

```python
# Lines 286-288 in backend/app/services/ai/gemini_provider.py
except httpx.TimeoutException as exc:
    logger.error("Gemini API call timed out after %.1f seconds", self.timeout)
    raise GeminiTimeoutError(f"Gemini request timed out after {self.timeout} seconds.") from exc
```

- **Mechanism:** The retry loop (`for attempt in range(self.max_retries + 1)`) encloses the `client.post` invocation. However, when an `httpx.TimeoutException` occurs, lines 286–288 catch it and **immediately re-raise `GeminiTimeoutError`**, aborting the entire loop on Attempt 0!
- **Consequence:** The loop never proceeds to Attempt 1 or Attempt 2. Furthermore, the fallback model switch logic (lines 222–250) only triggers on HTTP 404 or 429 status codes, never on a connection timeout.
- **Trigger:** During Phase 12 staging, a single transient delay on Google's model cold-start (>30s) permanently failed the end-to-end test without retrying.

### Finding P0-03 Details
- **Severity:** P0 (Blocker)
- **Evidence:** `backend/app/services/ai/gemini_provider.py` lines 286–288 directly break out of retry loop on any `httpx.TimeoutException`.
- **Business Impact:** High failure rates for user contract analysis during peak Google Cloud hours; false outage alerts; user workflow blockage.
- **Remediation:**
  1. Catch `httpx.TimeoutException` inside the retry loop body, log a warning, wait with exponential backoff (`asyncio.sleep(2 ** attempt)`), and retry up to `self.max_retries`.
  2. If attempt 0 times out, switch endpoint target to `gemini-flash-lite-latest` for faster response latency.
  3. Increase default `GEMINI_TIMEOUT_SECONDS` from 30.0s to 45.0s for complex, multi-clause contracts.
- **Concrete Verification Test:**
  Create an automated test in `backend/tests/test_gemini_resilience.py` with `httpx.MockTransport` simulating a timeout on attempt 0 followed by HTTP 200 on attempt 1. Assert that the request succeeds and logs attempt 2 recovery.

---

## 2. Email & SMTP Architecture

### Current Implementation Audit
- **Service Location:** [backend/app/services/email/provider.py](file:///A:/Soft%20Computing/backend/app/services/email/provider.py)
- **Architecture:** Implements `EmailProvider` base class with three concrete providers:
  1. `DisabledEmailProvider`: Suppresses outbound delivery cleanly when unconfigured (`EMAIL_ENABLED=false`).
  2. `MockEmailProvider`: In-memory recording provider for deterministic CI testing with failure simulation.
  3. `SMTPEmailProvider`: Production implementation utilizing Python standard library `smtplib`, `MIMEMultipart`, `STARTTLS`, and credential-scrubbed error logging.

### Identified Gaps & Production Deficiencies

#### Finding P0-04: SMTP Unconfigured & Localhost Base URL
- **Severity:** P0 (Blocker)
- **Evidence:** `.env.staging` (and `.env.example`) has `EMAIL_ENABLED=false`, `SMTP_HOST=""`, `SMTP_USERNAME=""`, and `APP_BASE_URL="http://localhost:3000"`.
- **Business Impact:** In production, user registration emails, invitation links, and password reset links will generate URLs pointing to `http://localhost:3000/auth/verify?token=...`, rendering self-service onboarding unusable for remote customers.
- **Remediation:**
  1. Configure verified transactional SMTP credentials (e.g., AWS SES, SendGrid, Postmark, or Resend SMTP relay).
  2. Set `EMAIL_ENABLED=true` and `EMAIL_SERVICE_ENABLED=true` in production environment.
  3. Set `APP_BASE_URL=https://app.contractly.com` (or the actual launch domain).
- **Concrete Verification Test:**
  Run a test verification flow: trigger `/api/v1/auth/register`, inspect the generated email message, and assert that the verification link matches `^https://app\.contractly\.com/auth/verify\?token=[A-Za-z0-9_-]+$`.

#### Finding P1-03: Blocking Synchronous I/O in Async Handlers
- **Severity:** P1 (High)
- **Evidence:** `backend/app/services/email/provider.py` lines 200–215 execute `with smtplib.SMTP(...) as server:` synchronously inside `async def send_email(...)` without delegating to a worker thread.
- **Business Impact:** If an SMTP server experiences latency (e.g. 5–10s handshake), the main FastAPI asyncio event loop is blocked, freezing all concurrent API traffic across all tenants.
- **Remediation:** Wrap the synchronous `provider.send_email(...)` call in `asyncio.to_thread(provider.send_email, to_email, subject, html_body, text_body)`.
- **Concrete Verification Test:**
  Run a mock test with a 2-second sleep inside `send_email`. Send concurrent requests to `/health`. Assert that `/health` returns in <10ms while the email is sending.

---

## 3. Storage Architecture: Local vs. S3 & Tenant Isolation

### Current State Analysis
Contractly maintains two storage adapters under [backend/app/services/storage/](file:///A:/Soft%20Computing/backend/app/services/storage/):
1. `LocalStorageAdapter`: Writes files to disk under `LOCAL_STORAGE_DIR`, isolating tenants via directory paths (`storage/contracts/{tenant_id}/...`). Directory traversal attacks (`../`) are blocked via path resolution checks.
2. `S3StorageAdapter`: Implements private bucket storage using `boto3`, applying tenant path prefixes (`tenants/{tenant_id}/contracts/...`), server-side encryption (`AES256`), SHA256 integrity calculation, and presigned download URL generation.

### Critical Deficiencies

#### Finding P0-01: API Endpoints Hardcode Local Storage Import
- **Severity:** P0 (Blocker)
- **Evidence:**
  - `backend/app/api/v1/contracts.py` line 63:
    `from app.services.storage.local import storage_client, compute_sha256`
  - `backend/app/api/v1/obligations.py` line 28:
    `from app.services.storage.local import storage_client`
- **Business Impact:** Even when an operator sets `STORAGE_PROVIDER=s3` and supplies AWS credentials in `.env.production`, the contract upload and obligation evidence routes completely bypass S3, saving files to the local container disk. In multi-container (ECS, Kubernetes, Cloud Run) deployments, files uploaded on Container A will 404 when requested on Container B. Container restarts destroy all uploaded customer agreements.
- **Remediation:**
  Change imports in both `contracts.py` and `obligations.py` to:
  `from app.services.storage import storage_client, compute_sha256`
  `backend/app/services/storage/__init__.py` already contains `StorageClientProxy` which dynamically delegates to `S3StorageAdapter` or `LocalStorageAdapter` based on `settings.STORAGE_PROVIDER`.
- **Concrete Verification Test:**
  Set `STORAGE_PROVIDER=s3` with a mocked S3 client. Upload a contract version via `POST /api/v1/contracts/{id}/versions`. Assert that `s3_client.put_object` is called with key `tenants/{tenant_id}/contracts/...` and that no files are written to local disk.

#### Finding P0-06: Document Download UI Missing in Frontend
- **Severity:** P0 (Blocker)
- **Evidence:**
  - Backend provides `GET /api/v1/contracts/{id}/versions/{version_id}/download` (lines 744–787 of `contracts.py`), with tenant boundaries and authorization checks.
  - However, in [src/components/contracts/](file:///A:/Soft%20Computing/src/components/contracts/), neither `document-viewer.tsx` nor `contract-table.tsx` provides a button or user-facing action to invoke this download endpoint. Only DOCX redline export is exposed (`redline-studio.tsx`).
- **Business Impact:** Real users who upload PDF or Word agreements cannot download their original legal files from the platform.
- **Remediation:** Add a "Download Original Agreement" button in `document-viewer.tsx` header toolbar and in the version history drawer, invoking `/api/v1/contracts/${contractId}/versions/${versionId}/download`.
- **Concrete Verification Test:**
  Verify via Next.js component test or manual browser check that clicking "Download" triggers a browser file download with matching `Content-Disposition` header.

---

## 4. Redis, Distributed Rate Limiting & Fail-Closed Behavior

### Current Implementation Audit
- **Limiter Implementation:** [backend/app/core/rate_limiter.py](file:///A:/Soft%20Computing/backend/app/core/rate_limiter.py)
- **Endpoints Protected:**
  - Login attempts: 5 requests / min per IP (`AUTH_IP_MAX_REQUESTS_PER_MINUTE`)
  - Account lockout: 5 consecutive failed logins triggers lockout
  - Verification emails: 5 requests / 5 min per email & IP
  - Org invitations: 25 requests / 5 min per organization
  - AI analysis / Q&A: 30 requests / min (`ai_rate_limiter`)

### Critical Deficiencies

#### Finding P0-02: Missing `redis` Dependency in Python Environment
- **Severity:** P0 (Blocker)
- **Evidence:**
  - `backend/requirements.txt` does **not** include `redis`.
  - In `backend/app/core/rate_limiter.py` line 148, `_get_client()` executes:
    `import redis.asyncio as aioredis`
  - In the current virtualenv, running `import redis` raises:
    `ModuleNotFoundError: No module named 'redis'`.
- **Business Impact:**
  - If an operator deploys to production and configures `REDIS_URL`, the application catches `ModuleNotFoundError`.
  - If `REDIS_REQUIRED=true` (the recommended production security posture to prevent DDoS across multiple instances), the backend raises `HTTP 503 Service Unavailable` on **every single login, registration, and AI request**, completely crashing user authentication.
  - If `REDIS_REQUIRED=false`, the backend silently falls back to process-local in-memory storage. On multi-worker or multi-container deployments, rate limits are bypassed by rotating requests across pods.
- **Remediation:**
  1. Add `redis>=5.0.0` to `backend/requirements.txt`.
  2. Install `redis` into the production Python virtual environment.
  3. Ensure `ai_rate_limiter` delegates to `RedisRateLimiterBackend` when configured.
- **Concrete Verification Test:**
  Run `python -c "import redis.asyncio as aioredis; print(aioredis.__name__)"` and assert exit code 0. Run `pytest backend/tests/test_phase_8_rate_limiting.py` with mock Redis to verify distributed counter behavior.

---

## 5. UTC Timestamp Serialization & Database Engine Parity

### Phase 12 Staging Fix Review
In Phase 12, the database model base was adjusted to resolve an `asyncpg` driver crash on PostgreSQL:
- **Location:** [backend/app/models/base.py](file:///A:/Soft%20Computing/backend/app/models/base.py#L12)
- **Implementation:** `utc_now() -> datetime.now(timezone.utc).replace(tzinfo=None)`.
- **Parity Result:** PostgreSQL `TIMESTAMP WITHOUT TIME ZONE` and SQLite `DATETIME` columns both accept naive UTC datetimes cleanly, eliminating the `TypeError: can't subtract offset-naive and offset-aware datetimes` exception.

### Identified Gap: Timezone Deserialization on Frontend

#### Finding P1-01: Serialized Naive UTC Strings Lack `Z` Suffix
- **Severity:** P1 (High)
- **Evidence:**
  - When Pydantic v2 serializes a naive `datetime` object (`created_at = datetime(2026, 10, 14, 10, 30, 0)`), the output JSON is `"2026-10-14T10:30:00"`.
  - In [src/app/admin/page.tsx](file:///A:/Soft%20Computing/src/app/admin/page.tsx#L87) and [src/components/contracts/contract-watch.tsx](file:///A:/Soft%20Computing/src/components/contracts/contract-watch.tsx), the frontend formats dates with `new Date(log.created_at).toLocaleString()`.
  - Under ECMAScript specifications (ISO 8601), date-time strings without a trailing `Z` or offset are parsed as **local device time**, not UTC.
- **Business Impact:**
  - A user in New York (EDT, UTC-4) viewing an audit log created at 14:00 UTC sees 14:00 EDT (which is 18:00 UTC), introducing a 4-hour chronological discrepancy.
  - Users in India (IST, UTC+5:30) see a 5.5-hour discrepancy.
  - Contract signing deadlines and obligation reminders risk being calculated incorrectly if parsed without explicit UTC semantics.
- **Remediation:**
  In `backend/app/schemas/base.py` or individual response schemas, attach a custom field serializer:
  ```python
  @field_serializer("created_at", "updated_at", check_fields=False)
  def serialize_utc_dt(self, dt: Optional[datetime]) -> Optional[str]:
      if dt is None:
          return None
      return dt.replace(tzinfo=timezone.utc).isoformat()
  ```
- **Concrete Verification Test:**
  Query `GET /api/v1/auth/me` or `/api/v1/audit/logs` and verify the serialized date strings end with `+00:00` or `Z`. In JavaScript, assert `new Date(res.created_at).toISOString()` exactly matches the original UTC timestamp.

---

## 6. Security, Authentication, CORS, Cookies & Vulnerabilities

### Security Audit Summary
1. **Authentication & Token Rotation:**
   - JWT access tokens (15-minute expiry) and refresh tokens (7-day expiry) verified.
   - Refresh token rotation enforced; invalidated on logout; single-use tokens stored with cryptographic hashes.
2. **Tenant Isolation:**
   - Multi-tenant boundary verified at database query layer: all SQL statements filter by `organization_id == tenant.id`.
   - Path-based directory traversal protections verified in storage adapters.
3. **Platform Role Separation:**
   - Platform routes (`/platform/*`) strictly require `PLATFORM_SUPER_ADMIN` or `PLATFORM_SUPPORT`. Customer administrators cannot access platform telemetry or configure other tenants.
4. **Cookie Security:**
   - `SECURE_COOKIES=true` in staging and production configurations.
   - Flags enforced: `HttpOnly=True`, `SameSite=lax`, `Secure=True`.

### Identified Gaps

#### Finding P0-05: CORS `ALLOWED_ORIGINS` Restricted to Localhost
- **Severity:** P0 (Blocker)
- **Evidence:** `backend/app/config.py` line 44:
  `ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]`
- **Business Impact:** Deploying the Next.js frontend to `https://app.contractly.com` or Vercel will cause all browser API requests to fail with HTTP 403 / CORS policy rejection.
- **Remediation:** Update `backend/app/config.py` to parse `ALLOWED_ORIGINS` from an environment variable list (e.g. `ALLOWED_ORIGINS="https://app.contractly.com,https://staging.contractly.com"`).
- **Concrete Verification Test:** Send an `OPTIONS` preflight request with `Origin: https://app.contractly.com` to `/api/v1/auth/login` and assert `Access-Control-Allow-Origin: https://app.contractly.com`.

#### Finding P1-04: Frontend DevDependency Vulnerabilities
- **Severity:** P1 (High)
- **Evidence:** `npm audit` reports 7 high-severity vulnerabilities in build dependencies:
  - `braces <3.0.3` (Uncontrolled resource consumption)
  - `micromatch <4.0.8` (ReDoS)
  - Transitive via `tailwindcss@3.4.14` and `postcss`.
- **Business Impact:** While restricted to build-time tooling, vulnerable devDependencies expose CI/CD build environments to potential supply-chain attacks.
- **Remediation:** Run `npm update braces micromatch` or upgrade to patched Tailwind/PostCSS versions.
- **Concrete Verification Test:** Run `npm audit` and verify 0 high or critical vulnerabilities.

---

## 7. Operations, Backups, Migrations & Neon Recovery

### Backup & Restore Script Inspection
- **Script:** [backend/scripts/backup.py](file:///A:/Soft%20Computing/backend/scripts/backup.py)
- **Features:** Supports automated SQLite file copy, document tarball archiving with SHA-256 manifests, and PostgreSQL dumping via `pg_dump`.

### Operational Gaps

#### Finding P1-02: `pg_dump` Missing from System PATH
- **Severity:** P1 (High)
- **Evidence:** `backend/scripts/backup.py` line 104 catches `FileNotFoundError` and raises `RuntimeError("pg_dump executable not found on system PATH")`. The host running Contractly staging does not have PostgreSQL client binaries installed.
- **Business Impact:** Standalone CLI backup scripts will fail if executed as a cron job on production app servers lacking `postgresql-client`.
- **Remediation:**
  1. For Neon PostgreSQL: Document and rely on Neon Point-In-Time Recovery (PITR) and automated continuous WAL archiving, which allows restoration to any second within the retention window without local `pg_dump`.
  2. For cold, off-site S3 backups: Run scheduled backup jobs inside a dedicated Docker container containing `postgresql-client` and AWS CLI.
- **Concrete Verification Test:** Document runbook for point-in-time branch creation using `neonctl branches create --source main --timestamp <ISO_TIME>`.

---

## 8. Legal, Launch & Compliance Verification

### Compliance Audit Checklist

| Item | Requirement | Status | Evidence / Notes |
| :--- | :--- | :--- | :--- |
| **Terms of Service** | Active terms page with clear liability limits | 🟢 **PASS** | `src/app/terms/page.tsx` renders complete 7-section platform terms |
| **Privacy Policy** | Active policy detailing data retention & rights | 🟢 **PASS** | `src/app/privacy/page.tsx` details GDPR/CCPA rights & data boundaries |
| **AI Disclaimers** | Non-adjudicative disclaimer for legal analysis | 🟢 **PASS** | Displayed in Terms, Document Viewer, Redline Studio, and Q&A |
| **No Model Training** | Clear commitment on customer confidentiality | 🟢 **PASS** | Section 4 of Terms confirms customer agreements are never used to train foundational AI models |
| **Favicon & Icons** | Professional brand favicon, no default Next.js | 🟢 **PASS** | Custom olive/paper themed SVG and `.ico` in `public/favicon.ico` |
| **Brand Integrity** | Zero references to AI models, Google Deepmind, Antigravity | 🟢 **PASS** | Clean customer-facing branding across entire interface |
| **HTTPS / TLS** | Strict transport security enforced | 🟡 **PENDING DNS** | Production reverse proxy (Cloudflare/Caddy/AWS ALB) must enforce TLS 1.3 |

---

## 9. Preserved Artifacts & Integrity Verification

To satisfy strict safety boundaries, all canonical and rollback databases were verified untouched:

1. **Canonical SQLite Database:** `contractly.db` confirmed preserved at exactly **610,304 bytes**. All 22 tables, 14 mock agreements, and user credentials remain intact.
2. **Neon Staging Project:** `contractly-staging-disposable` (Project ID: `lingering-fog-64539151`, AWS `ap-southeast-1`) confirmed active, migrated to revision `head`, and passing health checks.
3. **Supabase Rollback Config:** `.env.staging.supabase` remains intact and unmodified as a secondary recovery option.
4. **Physical Document Vault:** All mock agreements in `storage/contracts/` verified intact with SHA-256 integrity checks passing.

---

## 10. Pre-Launch Remediation Sequence

Before launching Contractly to real customers, execute the following remediation phases in sequential order:

```mermaid
graph TD
    A[Phase 13 Audit Completed] --> B[Phase 13.1: Critical Code Fixes P0]
    B --> C[Fix Storage Imports in contracts.py & obligations.py]
    B --> D[Add redis to requirements.txt & Install]
    B --> E[Fix Gemini Timeout Retry Loop in gemini_provider.py]
    B --> F[Add Contract Document Download UI Button]
    C --> G[Phase 13.2: Configuration & Secrets P0]
    D --> G
    E --> G
    F --> G
    G --> H[Configure Production SMTP Credentials & APP_BASE_URL]
    G --> I[Configure ALLOWED_ORIGINS with Production Domain]
    G --> J[Configure S3 Storage Bucket & AWS IAM Keys]
    H --> K[Phase 13.3: High-Priority Reliability P1]
    I --> K
    J --> K
    K --> L[Wrap SMTP sendmail in asyncio.to_thread]
    K --> M[Add Trailing Z to Naive UTC ISO Serialization]
    K --> N[Resolve npm audit High-Severity DevDependencies]
    L --> O[Phase 13.4: Final End-to-End Verification]
    M --> O
    N --> O
    O --> P[Go/No-Go Production Launch Gate]
```

### Step-by-Step Action Plan
1. **P0 Storage Fix:** Update `backend/app/api/v1/contracts.py` and `obligations.py` to import `storage_client` from `app.services.storage` instead of `.local`.
2. **P0 Redis Dependency:** Add `redis>=5.0.0` to `requirements.txt` and run `pip install -r requirements.txt`.
3. **P0 Gemini Provider Resilience:** Update `backend/app/services/ai/gemini_provider.py` to catch `httpx.TimeoutException` inside the retry loop and retry with backoff.
4. **P0 Frontend Download Action:** Connect `GET /api/v1/contracts/{id}/versions/{version_id}/download` to a download button in `document-viewer.tsx`.
5. **P0 Configuration:** Populate production environment variables for SMTP, S3, Redis, and CORS.
6. **P1 UTC Date Serialization:** Attach UTC timezone serializer to Pydantic datetime fields.
7. **P1 Async Email Dispatch:** Wrap synchronous `smtplib.sendmail` in `asyncio.to_thread`.
8. **Final E2E Verification:** Run full test suite against staging environment with all integrations active.

---

## 11. Final Go/No-Go Recommendation

### Verdict: **NO-GO (Conditionally Blocked)**
**Contractly is not yet ready for public customers.** Launching in its current state would lead to lost files upon container restarts, broken email verifications, rate limiting failures, and occasional AI timeouts.

### Path to GO
All 6 blocking issues (P0) are straightforward, isolated, and low-risk to remediate. With focused implementation, all blockers can be resolved and validated in **under 4 hours of development time**.

Upon completion of the Phase 13.1 remediation sequence and passing the verification tests outlined above, Contractly will achieve full production readiness.

---
*Report completed autonomously by Antigravity. Awaiting user approval before implementing remediation fixes.*
