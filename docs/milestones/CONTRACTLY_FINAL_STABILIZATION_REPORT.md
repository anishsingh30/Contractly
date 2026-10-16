# CONTRACTLY FINAL STABILIZATION, PERFORMANCE AND DEPLOYMENT PREPARATION REPORT

**Date:** October 15, 2026  
**Project Path:** `A:\Soft Computing`  
**Application Architecture:** Next.js Frontend (`localhost:3000`), FastAPI Backend (`127.0.0.1:8000`), SQLite Canonical Local DB (`contractly.db`), Neon PostgreSQL Staging DB (`ep-lingering-fog-a1kusnf0`), Resend SMTP (`smtp.resend.com`), Google Gemini (`gemini-flash-lite-latest`), Local/S3 Storage Abstraction.

---

## 1. Executive Summary

Contractly is an enterprise LegalTech SaaS platform providing contract lifecycle management, automated obligations extraction, grounded AI Q&A, and redlining. Prior to deployment, this stabilization and optimization cycle was conducted with zero new features, zero UI redesigns, and strict preservation of all 20 existing user accounts, 28 stored contracts, and tenant data.

Key achievements in this phase:
1. **Full Directory Audit & Footprint Optimization:** Identified that 99.4% (935.4 MB of 942 MB total) was local build caches and virtual environments. Authored `.gitignore` and `.vercelignore` to isolate production deployments down to under 5 MB.
2. **Root Cause Resolution for Authentication:** Resolved the recurring `Authentication failed` issue across local restarts and browser reloads (tackling Neon timeout falls, refresh token race condition invalidations, and orphaned Windows process locks).
3. **Verified Security & Reliability:** Enforced RFC 6749 BCP 212 refresh-token concurrency windows, strict tenant-isolation validation, and hardened process management scripts (`run.vbs` / `stop.vbs`).
4. **Comprehensive Regression Testing:** Executed 83 automated backend pytest test cases (100% pass), a 9-step local end-to-end authentication suite (100% pass), and full Next.js static build/lint checks with zero errors.

---

## 2. Phase 1: Directory & Dependency Audit

An automated audit of `A:\Soft Computing` was conducted using a custom file tree scanner. The project directory totaled **942.06 MB**.

### Largest Folders and Files Breakdown

| Component | Path / Directory | Size (MB) | Classification | Action / Deployment Handling |
| :--- | :--- | :--- | :--- | :--- |
| Frontend Dependencies | `node_modules/` | 529.14 MB | Local Dependencies | Excluded from git; installed clean via `package-lock.json` |
| Next.js Cache & Build | `.next/cache/` | 209.88 MB | Ephemeral Cache | Excluded from git and deployment bundles |
| Next.js Build Output | `.next/` (other) | 33.17 MB | Ephemeral Build | Rebuilt on target CI/CD (Vercel) |
| Backend Python venv | `backend/.venv/` | 163.24 MB | Local Virtualenv | Excluded from git; installed on backend host via `requirements.txt` |
| Legacy/System Artifacts | Miscellaneous cache & logs | 1.21 MB | Ephemeral | Excluded via `.gitignore` |
| Canonical SQLite DB | `contractly.db` | 0.69 MB | Local Database | Preserved strictly; excluded from public bundles |
| Backend SQLite DB Copy | `backend/contractly.db` | 0.10 MB | Local Database | Preserved strictly; excluded from public bundles |
| Stored Contract Uploads | `backend/storage/uploads/` | 0.24 MB | Local File Storage | Preserved strictly; excluded from code bundles |
| Frontend Source Code | `src/`, `public/` | 1.15 MB | Required Source | Committed and bundled for frontend deployment |
| Backend Source Code | `backend/app/`, `backend/alembic/` | 1.08 MB | Required Source | Committed and bundled for backend host deployment |
| Project Total | **`A:\Soft Computing`** | **942.06 MB** | — | — |

### Safe Exclusion and Cleanup Actions Taken

1. **Updated Root `.gitignore`:**
   - Excluded `.venv/`, `backend/.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`.
   - Excluded `contractly.db`, `backend/contractly.db`, `*.db`, `*.sqlite3`.
   - Excluded contract storage directory: `backend/storage/uploads/`, `storage/uploads/`.
   - Excluded local scratch and diagnostic artifacts: `scratch/`, `.vercel/`, `*.log`.
   - Excluded all secret configuration files: `.env`, `.env.*`, `!backend/.env.example`.

2. **Created Root `.vercelignore`:**
   - Configured `.vercelignore` to strictly prevent backend Python code, local database files, uploads, and large reports from being sent to Vercel build containers.
   - Result: Frontend deployment bundle is reduced from ~940 MB to **< 2.5 MB** of clean TypeScript/Next.js code.

3. **Dependency Integrity Restored:**
   - Repaired `backend/.venv` by bootstrapping `pip` via `ensurepip`.
   - Installed missing AWS S3 dependencies (`boto3`, `botocore`) into `backend/.venv`.
   - Added `alembic>=1.13.0` to `backend/requirements.txt` to ensure reproducible database migration runs on production containers.

---

## 3. Phase 2: Authentication & Core Reliability (Root Cause Analysis)

### Root Causes Diagnosed

Users previously encountered sporadic `Authentication failed` errors on `http://localhost:3000/signin` after restarting the project or refreshing the browser. Three distinct root causes were identified:

1. **Database Fallback and Network Stalling (Neon Timeout):**
   - In `backend/.env`, `DATABASE_URL` had been directly pointed to the remote Neon PostgreSQL instance (`ep-lingering-fog-a1kusnf0.ap-southeast-1.aws.neon.tech`).
   - On Windows local development environments, cold-starting SSL connections over Python's `asyncio` Proactor event loop experienced intermittent network stalls (`[WinError 121] The semaphore timeout period has expired`).
   - When this timed out, the backend failed unhandled, returning HTTP 500 errors to the frontend, which the UI reported as generic `Authentication failed`.

2. **Token Rotation Race Condition on Browser Multi-Tab / Parallel Reloads:**
   - Next.js renders multiple client components concurrently on dashboard load (contracts, obligations, notifications, user profile). Each component triggered API calls via `api-client.ts`.
   - If the access token expired (15-minute default), multiple concurrent requests attempted to refresh using the exact same refresh token.
   - The first request succeeded and rotated the token family in the database. The second concurrent request arrived milliseconds later with the old token, triggering `TOKEN_REUSE_DETECTED` in `auth.py`.
   - In accordance with strict security standards, `TOKEN_REUSE_DETECTED` immediately revoked all tokens in the lineage and cleared auth cookies, forcing the user into an invalid session state.

3. **Orphaned Windows Process Locks on Port 8000:**
   - When FastAPI or Uvicorn crashed or was stopped forcefully, Windows sockets retained child `python3.12` processes in `Bound` or `TIME_WAIT` states on port 8000.
   - Subsequent execution of `run.vbs` failed with `[Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000)`.
   - As a result, the frontend proxied auth requests to a dead port, yielding 502/504 errors that manifested as `Authentication failed`.

### Fixes Applied

1. **Intelligent Environment-Based Database Routing ([`backend/app/config.py`](file:///a:/Soft%20Computing/backend/app/config.py)):**
   - Separated local development from remote staging/production.
   - In `development` mode (`ENVIRONMENT="development"`), the backend automatically and deterministically routes to the local canonical SQLite database (`contractly.db`).
   - Added `NEON_DATABASE_URL: Optional[str]` to the configuration schema. In `staging` or `production`, the backend strictly validates and routes to the managed PostgreSQL instance.
   - Added `SECURE_COOKIES` toggle in `Settings`: set to `False` in local development (allowing HTTP on `localhost`), but strictly set to `True` in `production` and `staging` (enforcing HTTPS `Secure; SameSite=lax; HttpOnly`).

2. **Token Rotation Concurrency Grace Window ([`backend/app/api/v1/auth.py`](file:///a:/Soft%20Computing/backend/app/api/v1/auth.py)):**
   - Implemented an RFC 6749 BCP 212 compliant 30-second concurrency grace window for refresh token rotation.
   - When a refresh token is rotated, its hash and the newly issued token are cached temporarily in the active token family. If parallel frontend requests present the previous token within 30 seconds of its rotation, the endpoint returns the newly issued token without triggering reuse revocation.
   - Genuine token reuse attacks outside the grace window still trigger immediate family-wide revocation.

3. **Case-Insensitive & Whitespace-Tolerant Email Handling:**
   - Updated `POST /api/v1/auth/login` to sanitize input: `clean_email = payload.email.strip().lower()`.
   - Database queries now query using `func.lower(User.email) == clean_email`.
   - Updated `src/lib/api-client.ts` to trim and normalize emails on client submission.

4. **Service Outage Distinctions (HTTP 503 vs HTTP 401):**
   - Wrapped database query execution during login in a targeted exception handler.
   - If a database timeout, connection failure, or pool exhaustion occurs, the API returns HTTP 503 `{"detail": "Database service is temporarily unavailable. Please try again shortly."}` rather than HTTP 401 `{"detail": "Invalid email or password"}`.

5. **Hardened Process Lifecycle Scripts ([`run.vbs`](file:///a:/Soft%20Computing/run.vbs) & [`stop.vbs`](file:///a:/Soft%20Computing/stop.vbs)):**
   - Updated batch logic to inspect `netstat -ano` for any PID listening or bound on ports 8000 and 3000.
   - Executes `taskkill /f /t /pid <PID>` across the entire process tree to cleanly terminate orphaned workers before spawning new servers.

---

## 4. Phase 3: Performance Measurements & Optimizations

### Baseline Latency Benchmarks

Benchmarks were measured using `scratch/benchmark_endpoints.py` against both direct backend API (`http://127.0.0.1:8000`) and the Next.js frontend proxy (`http://localhost:3000`).

| Endpoint / Operation | HTTP Method | Mean Latency (ms) | Target / SLA | Status | Analysis / Notes |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `/health` | GET | **14.66 ms** | < 50 ms | Optimal | Fast liveness and dependency status check |
| `/api/v1/auth/login` | POST | **448.36 ms** | < 600 ms | Optimal | Includes cryptographic bcrypt verification (work factor 12) |
| `/api/v1/auth/me` | GET | **12.50 ms** | < 50 ms | Optimal | Authenticated session validation |
| `/api/v1/contracts` | GET | **12.54 ms** | < 100 ms | Optimal | Tenant-isolated list query with indexed `organization_id` |
| `/api/v1/obligations` | GET | **12.37 ms** | < 100 ms | Optimal | Tenant-isolated list query |
| `/api/v1/calendar/events` | GET | **12.55 ms** | < 100 ms | Optimal | Date-range filtered calendar query |
| `/api/v1/notifications` | GET | **15.83 ms** | < 100 ms | Optimal | Notification fetch with user index |
| Frontend Landing `/` | GET | **360.40 ms** | < 500 ms | Optimal | Next.js server-rendered static layout |
| Frontend Signin `/signin` | GET | **124.63 ms** | < 250 ms | Optimal | Prerendered client component |

### Architectural Optimizations Applied

1. **Configurable Next.js Reverse Proxy ([`next.config.mjs`](file:///a:/Soft%20Computing/next.config.mjs)):**
   - Configured rewrites to dynamically resolve `BACKEND_INTERNAL_URL` or `NEXT_PUBLIC_API_URL` (falling back to `http://127.0.0.1:8000` in local development).
   - In production on Vercel, this prevents CORS pre-flight penalties by funneling frontend requests through Next.js edge rewrites to the public backend host.

2. **CORS Allowlist Parsing ([`backend/app/config.py`](file:///a:/Soft%20Computing/backend/app/config.py)):**
   - Enabled comma-separated parsing for `ALLOWED_ORIGINS` to allow seamless multi-domain deployments (e.g., `https://contractly.vercel.app,https://app.contractly.com`).
   - Automatically synchronizes `APP_BASE_URL` into the CORS allowlist.

3. **Database Index Verification:**
   - Confirmed critical query indexes are active on all tenant-isolated tables:
     - `users.email` (Unique)
     - `memberships.organization_id`, `memberships.user_id`
     - `contracts.organization_id`, `contracts.created_at`
     - `obligations.organization_id`, `obligations.contract_id`, `obligations.due_date`
     - `refresh_tokens.token_hash`, `refresh_tokens.family_id`

---

## 5. Phase 4: Storage, Database & Service Integrity

### Storage Abstraction Integrity
- The backend storage architecture implements `StorageService` (`backend/app/services/storage_service.py`), supporting two distinct providers:
  - `local`: Writes files to `backend/storage/uploads/` (used in local development).
  - `s3`: Connects via `boto3` to AWS S3, Cloudflare R2, or Supabase S3-compatible storage using `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, and `AWS_S3_BUCKET`.
- Validated that private contract documents cannot be accessed across organizations. All download and redline operations query using `WHERE contract_id = :id AND organization_id = :org_id`.
- Verified that original file downloads and DOCX export generation stream file handles directly without unbounded RAM allocation.

### Database Staging vs Production
- The canonical local database is `contractly.db` located at `A:\Soft Computing\contractly.db`.
- The Neon PostgreSQL staging instance is hosted at `ep-lingering-fog-a1kusnf0.ap-southeast-1.aws.neon.tech`.
- Its credentials and connection strings are cleanly captured in `.env.staging` and `backend/.env.staging`.
- No destructive migrations, table resets, or schema modifications were executed against Neon. Staging data remains completely intact and uncorrupted.

### Email (Resend SMTP)
- Connected to `smtp.resend.com` on port 587 with TLS.
- Transactional flows (account verification, password reset, organization invitation) format links using `APP_BASE_URL`.
- If SMTP credentials fail or an upstream network drop occurs, the email dispatcher logs the error gracefully without crashing the active request.

### Google Gemini AI Integration
- Uses `gemini-flash-lite-latest` through the backend Google GenAI SDK.
- API keys are accessed exclusively server-side in `backend/app/services/ai_service.py`. No client-side exposure exists in frontend bundles.
- Grounded Q&A relies on contract text extraction (PyMuPDF) and passes bounded context chunks to Gemini with citations.

---

## 6. Phase 5: Production Deployment Blueprint

### Target Architecture

```
                  ┌────────────────────────────────────────┐
                  │          End Users / Browsers          │
                  └───────────────────┬────────────────────┘
                                      │ HTTPS
                                      ▼
                  ┌────────────────────────────────────────┐
                  │             Vercel Edge                │
                  │   Next.js 14 Frontend (SSR & Static)   │
                  │   Domain: https://contractly.vercel.app│
                  └───────────────────┬────────────────────┘
                                      │ Rewrites / API calls
                                      ▼
                  ┌────────────────────────────────────────┐
                  │    Persistent Container Backend Host   │
                  │   (Render / Railway / Fly.io / ECS)    │
                  │   FastAPI + Uvicorn + APScheduler      │
                  │   Public URL: https://api.contractly...│
                  └──────┬────────────┬────────────┬───────┘
                         │            │            │
         PostgreSQL TLS  │            │ S3 API     │ REST API
                         ▼            ▼            ▼
             ┌───────────────┐ ┌─────────────┐ ┌───────────────┐
             │ Neon Database │ │ AWS S3 / R2 │ │ Google Gemini │
             │  PostgreSQL   │ │ Encrypted   │ │      AI       │
             └───────────────┘ └─────────────┘ └───────────────┘
```

> [!IMPORTANT]
> **Why Vercel Cannot Run the Backend:**
> The FastAPI backend utilizes `APScheduler` for a 12-hour background notification scheduler, native C libraries (`PyMuPDF` for PDF document analysis), and persistent streaming endpoints. Vercel serverless functions have execution duration limits and lack persistent background processes. The backend must be hosted on a containerized service (such as Render Web Service, Railway, Fly.io, or AWS ECS).

### Required Environment Variables by Service

#### 1. Next.js Frontend (Vercel Project Settings)

| Variable Name | Environment | Description / Recommended Value |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | Production | Public HTTPS URL of the backend API (e.g., `https://api.contractly.com`) |
| `NEXT_PUBLIC_APP_URL` | Production | Public HTTPS URL of the frontend (e.g., `https://contractly.vercel.app`) |
| `BACKEND_INTERNAL_URL` | Production | Target backend URL for Next.js API rewrites |
| `NODE_ENV` | Production | `production` |

#### 2. FastAPI Backend Host (Render / Railway / Container Service)

| Variable Name | Environment | Description / Recommended Value |
| :--- | :--- | :--- |
| `ENVIRONMENT` | Production | `production` |
| `DATABASE_URL` | Production | Neon PostgreSQL pooled URL (`postgres://...@ep-...-pooler...neon.tech/neondb?sslmode=require`) |
| `NEON_DATABASE_URL` | Production | Fallback / Direct Neon connection string |
| `APP_BASE_URL` | Production | Frontend URL for email link generation (`https://contractly.vercel.app`) |
| `ALLOWED_ORIGINS` | Production | Comma-separated CORS origins (`https://contractly.vercel.app`) |
| `JWT_SECRET_KEY` | Production | 64-character random hexadecimal string |
| `JWT_ALGORITHM` | Production | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| Production| `15` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Production | `7` |
| `SECURE_COOKIES` | Production | `True` |
| `STORAGE_PROVIDER` | Production | `s3` |
| `AWS_ACCESS_KEY_ID` | Production | S3 / R2 access key ID |
| `AWS_SECRET_ACCESS_KEY` | Production | S3 / R2 secret access key |
| `AWS_REGION` | Production | AWS region (e.g., `us-east-1`) |
| `AWS_S3_BUCKET` | Production | Dedicated private S3 bucket name |
| `GEMINI_API_KEY` | Production | Google Gemini API key |
| `SMTP_HOST` | Production | `smtp.resend.com` |
| `SMTP_PORT` | Production | `587` |
| `SMTP_USER` | Production | `resend` |
| `SMTP_PASSWORD` | Production | Resend API Key (`re_...`) |
| `SMTP_FROM_EMAIL` | Production | Verified domain email (`notifications@yourdomain.com` or `onboarding@resend.dev`) |
| `SMTP_TLS` | Production | `True` |

### Step-by-Step Deployment Sequence

1. **Step 1: Database Verification on Neon**
   - Ensure the Neon PostgreSQL instance is active.
   - Run Alembic migration check using:
     ```bash
     alembic upgrade head
     ```
   - Verify connection pooling is enabled on port 6543 or the `-pooler` endpoint.

2. **Step 2: S3 Object Storage Provisioning**
   - Create a private S3 bucket (or Cloudflare R2 bucket) with public access completely blocked.
   - Configure lifecycle rules for temporary export artifacts if needed.
   - Generate IAM credentials restricted strictly to `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` for that bucket.

3. **Step 3: Backend Container Deployment**
   - Deploy backend to Render/Railway using the repository's `backend/` directory.
   - Build command:
     ```bash
     pip install -r requirements.txt
     ```
   - Start command:
     ```bash
     uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2
     ```
   - Configure all backend environment variables listed above.
   - Verify health check response at `https://<backend-domain>/health`.

4. **Step 4: Frontend Deployment on Vercel**
   - Link repository to Vercel.
   - Set Root Directory to `./`.
   - Set Build Command to `npm run build` and Output Directory to `.next`.
   - Configure `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_APP_URL`.
   - Deploy and verify domain alias.

---

## 7. Phase 6: Regression & Verification Test Results

All tests were executed against the actual codebases and local endpoints.

### 1. Frontend Production Build & Code Quality

```bash
npx tsc --noEmit && npm run lint && npm run build
```
- **TypeScript Type Check:** Passed (0 errors).
- **ESLint Check:** Passed (0 warnings, 0 errors).
- **Next.js Production Compilation:** Passed.
  - Successfully generated 18 static/dynamic routes.
  - Route tree:
    - `○ /` (Static)
    - `○ /_not-found` (Static)
    - `○ /admin` (Static)
    - `○ /calendar` (Static)
    - `○ /contracts` (Static)
    - `ƒ /contracts/[id]` (Dynamic)
    - `ƒ /contracts/[id]/redline` (Dynamic)
    - `○ /dashboard` (Static)
    - `○ /forgot-password` (Static)
    - `○ /lawyers` (Static)
    - `○ /notifications` (Static)
    - `○ /obligations` (Static)
    - `○ /reports` (Static)
    - `○ /reset-password` (Static)
    - `○ /settings` (Static)
    - `○ /signin` (Static)
    - `○ /signup` (Static)
    - `○ /verify-email` (Static)

### 2. Backend Automated Test Suite (pytest)

```bash
backend\.venv\Scripts\python.exe -m pytest backend/tests/
```
- **Results:** **83 passed, 0 failed** in 77.72s.
- **Coverage Areas:**
  - `test_phase_13_3_auth_and_logout.py`: Authentication, login, logout, token revocation, session invalidation, cookie expiration.
  - `test_phase_13_3_rbac.py`: Role-based access control (Admin, Lawyer, Client, Super Admin).
  - `test_phase_13_3_tenant_isolation.py`: Cross-tenant boundary enforcement across contracts, obligations, and reports.
  - `test_phase_13_3_contract_upload.py`: File type validation, document parsing, error handling.
  - `test_phase_13_3_storage_durability.py`: Local & S3 storage persistence, file integrity.
  - `test_phase_13_3_calendar_obligations.py`: Due dates, recurrence, obligation status transitions.
  - `test_phase_13_3_email_notifications.py`: SMTP payload construction, notification triggers.
  - `test_phase_13_3_lawyer_directory.py`: Lawyer profiles, public/private directory access.

### 3. Local End-to-End Authentication Test (`verify_local_auth_e2e.py`)

Executed direct and proxied authentication flows:
1. **Direct Backend Login (`admin@contractly.com`):** `PASS` (HTTP 200, JWT tokens returned).
2. **Next.js Proxy Login (`localhost:3000/api/v1/auth/login`):** `PASS` (HTTP 200, cookies forwarded).
3. **Protected Route Validation (`/api/v1/auth/me`):** `PASS` (HTTP 200, user identity returned).
4. **Token Refresh & Rotation:** `PASS` (HTTP 200, new token family generated).
5. **Concurrency Grace Window:** `PASS` (Concurrent request with previous token accepted within 30s window).
6. **Token Reuse Detection Outside Grace Window:** `PASS` (Rejected with 401, lineage invalidated).
7. **Session Signout:** `PASS` (Tokens invalidated in DB, auth cookies cleared).
8. **Invalid Credential Handling:** `PASS` (Rejected with HTTP 401, informative error detail).
9. **User Registration & Case Sensitivity:** `PASS` (Case-insensitive login and whitespace trimming verified).

---

## 8. Files Changed and Rationale

| File Path | Nature of Change | Architectural Rationale |
| :--- | :--- | :--- |
| [`.gitignore`](file:///a:/Soft%20Computing/.gitignore) | Modification | Excludes caches, Python virtualenvs, local databases, and temporary artifacts from version control. |
| [`.vercelignore`](file:///a:/Soft%20Computing/.vercelignore) | New File | Prevents heavy backend files, databases, and local assets from bloating the Vercel frontend build container. |
| [`backend/requirements.txt`](file:///a:/Soft%20Computing/backend/requirements.txt) | Modification | Added `alembic>=1.13.0` to guarantee reproducible migration capability on container hosts. |
| [`backend/app/config.py`](file:///a:/Soft%20Computing/backend/app/config.py) | Modification | Added `NEON_DATABASE_URL`, environment-aware database routing, cookie security enforcement by environment, and comma-separated CORS origin parsing. |
| [`backend/app/api/v1/auth.py`](file:///a:/Soft%20Computing/backend/app/api/v1/auth.py) | Modification | Added 30-second token rotation concurrency grace window, case-insensitive/trimmed email queries, and database exception isolation returning 503 instead of 500. |
| [`src/lib/api-client.ts`](file:///a:/Soft%20Computing/src/lib/api-client.ts) | Modification | Normalized email inputs before submission; updated error handling to preserve actionable backend error messages. |
| [`next.config.mjs`](file:///a:/Soft%20Computing/next.config.mjs) | Modification | Made backend proxy rewrites configurable via `BACKEND_INTERNAL_URL` / `NEXT_PUBLIC_API_URL` to facilitate deployment routing. |
| [`run.vbs`](file:///a:/Soft%20Computing/run.vbs) | Modification | Hardened process startup to kill bound and listening process trees on ports 8000 and 3000 before spawning servers. |
| [`stop.vbs`](file:///a:/Soft%20Computing/stop.vbs) | Modification | Guaranteed clean termination of Python and Node child processes across the system. |

---

## 9. Remaining Blockers & Post-Deployment Checklist

### Deployment Blockers (External Actions Required Prior to Production Cutover)

1. **Object Storage Provisioning:** An AWS S3 or Cloudflare R2 bucket must be created, and credentials supplied to the backend container host. The local filesystem storage cannot be used in a stateless container environment.
2. **Backend Container Hosting Account:** A container hosting platform (Render, Railway, Fly.io, or AWS ECS) must be selected and configured with the backend environment variables.
3. **Resend Domain Verification:** If sending emails to external users in production, the custom domain (e.g., `contractly.com`) must be verified in the Resend dashboard with proper SPF, DKIM, and DMARC records. (Testing can proceed using `onboarding@resend.dev` to registered email addresses).

### Post-Deployment Verification Checklist

Upon deploying to production, execute the following verification steps in sequence:

- [ ] **Liveness Check:** Request `GET https://<backend-host>/health` and verify all dependencies report `"status": "healthy"`.
- [ ] **Database Connection Check:** Confirm the backend reports `dependencies.database.status == "healthy"` pointing to Neon PostgreSQL.
- [ ] **Frontend Loading:** Load `https://<frontend-host>/signin` in an incognito window; ensure no CSP or CORS console errors appear.
- [ ] **Authentication Flow:**
  - [ ] Log in with an existing administrator account.
  - [ ] Verify `contractly_access_token` and `contractly_refresh_token` are set with `Secure; HttpOnly; SameSite=lax`.
  - [ ] Open a second tab and verify session state restores seamlessly.
- [ ] **Contract Lifecycle:**
  - [ ] Upload a test PDF contract.
  - [ ] Verify the file is persisted in S3 object storage.
  - [ ] Verify metadata, clauses, and obligations extraction completes.
  - [ ] Ask a grounded Q&A question in the contract viewer; confirm citation links back to contract text.
- [ ] **Export & Redline:**
  - [ ] Generate and download a redline diff.
  - [ ] Download the original document and verify DOCX export generates without error.
- [ ] **Sign Out:** Sign out and confirm cookies are cleared and immediate redirect to `/signin` occurs.
