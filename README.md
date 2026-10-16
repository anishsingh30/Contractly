# Contractly

**AI-powered contract lifecycle management, intelligence, and redlining platform.**

Contractly is an enterprise-grade contract management platform designed to help legal professionals, corporate procurement teams, and business operators organize agreements, extract critical obligations, detect contractual risks, navigate complex legal clauses, and collaborate with legal counsel.

---

## 1. Verified Core Features

- **Document Ingestion & Multi-Format Parsing:** Upload and parse `.pdf` and `.docx` agreements with automated text and layout extraction.
- **AI-Assisted Contract Intelligence:** Automated extraction of contract metadata, key dates, governing laws, parties, and commercial values using Google Gemini.
- **Risk Analysis & Clause Categorization:** Automatic identification of high-risk liabilities, indemnification terms, termination clauses, and non-standard covenants.
- **Contract-Grounded Q&A:** Grounded legal question answering with citation tracking back to specific contract provisions.
- **Redlining & Revision Assistant:** AI-assisted clause redlining with side-by-side revision proposals, rationale, and plain-language impact assessments.
- **Lifecycle & Obligation Tracking:** Automated tracking of renewal windows, expiry deadlines, and operational obligations with status tracking.
- **Calendar & Event Scheduling:** Integrated calendar view displaying upcoming contract milestones, renewals, and legal consultations.
- **Lawyer Consultation & Matter Oversight:** Dedicated legal professional portal for reviewing client contracts, managing consultation matters, and exchanging secure in-matter messages.
- **Multi-Tenant Isolation & Role-Based Access Control:** Strict organizational tenant isolation with granular role permissions (`admin`, `member`, `viewer`, `lawyer`).
- **Data Management & Privacy Controls:** Self-service organization data export, audit logging, and administrative demo data reset.

---

## 2. Architecture & Technology Stack

Contractly is built as a decoupled web application separating the user interface, API services, persistent data layer, and external integrations:

```text
               +--------------------------------------------------+
               |               Browser Client                     |
               |       (Corporate User / Legal Counsel / Admin)   |
               +--------------------------------------------------+
                                        |
                         HTTPS / JSON / Session Cookies
                                        v
               +--------------------------------------------------+
               |             Next.js 15 Web Frontend              |
               |        (React 18, TypeScript, Tailwind CSS)      |
               +--------------------------------------------------+
                                        |
                           REST API Calls (Port 8000)
                                        v
               +--------------------------------------------------+
               |              FastAPI Backend API                 |
               |       (Python 3.12, Pydantic v2, Uvicorn)        |
               +--------------------------------------------------+
                     |                |               |
       +-------------+                |               +--------------+
       v                              v                              v
+---------------+             +----------------+             +----------------+
| Relational DB |             |  AI Services   |             | Private Store  |
| SQLite (dev)  |             |  Google Gemini |             | Local Disk /   |
| Postgres (stg)|             | (Flash / Pro)  |             | AWS S3 Bucket  |
+---------------+             +----------------+             +----------------+
```

### Technology Stack
- **Frontend:** Next.js 15 (App Router), React 18, TypeScript 5, Tailwind CSS, Lucide React.
- **Backend API:** FastAPI, Pydantic v2, Pydantic-Settings, SQLAlchemy 2.0 (asyncio), Uvicorn.
- **Database Engine:** Dual-mode asynchronous storage:
  - Local Development: Canonical SQLite via `aiosqlite`.
  - Staging / Production: Managed PostgreSQL (Neon, Supabase) via `asyncpg`.
- **Database Migrations:** Alembic (revisions 0001 through 0004).
- **Authentication & Security:** JWT tokens with HTTP-only secure cookies, sliding-window rate limiting, and password hashing via Passlib/Bcrypt.
- **AI Provider:** Google Gemini API (`gemini-1.5-flash`, `gemini-flash-lite-latest`).
- **Document Processing:** PyMuPDF (`fitz`), Python-Docx.
- **Storage Providers:** Local filesystem storage with configurable Amazon S3 support.

---

## 3. Repository Structure

```text
Contractly/
├── .env.example                 # Root environment template for Next.js frontend
├── .gitignore                   # Root Git exclusion rules
├── .vercelignore                # Frontend deployment exclusions
├── README.md                    # Primary project documentation
├── package.json                 # Frontend dependencies and scripts
├── tsconfig.json                # TypeScript compiler configuration
├── next.config.mjs              # Next.js configuration
├── tailwind.config.js           # Tailwind CSS theme configuration
├── pytest.ini                   # Pytest configuration and test filters
├── docker-compose.test.yml      # Local testing service definitions
│
├── src/                         # Next.js frontend application source
│   ├── app/                     # App router pages (dashboard, admin, login, etc.)
│   ├── components/              # Reusable UI components and modal workflows
│   └── lib/                     # Client-side API clients, hooks, and utilities
│
├── backend/                     # FastAPI backend application source
│   ├── .env.example             # Backend environment template
│   ├── requirements.txt         # Python dependencies
│   ├── alembic.ini              # Alembic database migration configuration
│   ├── alembic/                 # Alembic migrations (revisions 0001 to 0004)
│   ├── app/
│   │   ├── main.py              # Application entry point and middleware configuration
│   │   ├── config.py            # Typed settings via Pydantic BaseSettings
│   │   ├── dependencies.py      # Dependency injection (database sessions, auth, RBAC)
│   │   ├── api/v1/              # API routes (contracts, auth, ai, lawyers, admin)
│   │   ├── core/                # Security, database connection, rate-limiting, permissions
│   │   ├── models/              # SQLAlchemy ORM declarative models
│   │   ├── schemas/             # Pydantic request and response schemas
│   │   └── services/            # Business logic (AI, intelligence, notifications, storage)
│   ├── scripts/                 # Maintenance, backup, restore, and storage migration scripts
│   └── tests/                   # Automated pytest suite (46 test modules, 328 test cases)
│
├── docs/                        # Operational runbooks and architecture documentation
│   ├── BACKUP_AND_RECOVERY.md   # Backup procedures and disaster recovery guide
│   ├── STAGING_RUNBOOK.md       # Staging deployment and operations guide
│   └── milestones/              # Historical milestone reports and audit archives
│
└── evaluation/                  # Intelligence pipeline benchmark suite and datasets
```

---

## 4. Prerequisites

- **Node.js:** v18.18.0 or later (v20+ recommended)
- **npm:** v9.0.0 or later
- **Python:** v3.11 or v3.12 (Python 3.12 recommended)
- **Git:** v2.30 or later
- **Google Gemini API Key:** (Optional for local UI workflows; required for AI analysis, Q&A, and redlining)

---

## 5. Local Setup & Installation

### Step 1: Clone the Repository
```bash
git clone <PRIVATE_REPOSITORY_URL>
cd Contractly
```

### Step 2: Configure Backend Environment & Dependencies
```bash
cd backend
python -m venv .venv

# Activate virtual environment (Windows PowerShell):
.\.venv\Scripts\Activate.ps1
# Or on macOS/Linux: source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
```

### Step 3: Configure Frontend Environment & Dependencies
```bash
# From project root:
cp .env.example .env.local
npm install
```

### Step 4: Run the Application Locally

#### Terminal 1 — FastAPI Backend:
```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
API Documentation: `http://127.0.0.1:8000/docs`

#### Terminal 2 — Next.js Frontend:
```bash
npm run dev
```
Web Application: `http://localhost:3000`

---

## 6. Environment Variables Reference

Never commit `.env` or `.env.local` files containing real secrets. Use `.env.example` as a clean reference.

### Frontend Environment (`.env.local`)
| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | Base URL of the FastAPI backend API | `http://localhost:8000` |
| `BACKEND_INTERNAL_URL` | Internal URL for Next.js SSR requests | `http://127.0.0.1:8000` |

### Backend Environment (`backend/.env`)
| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `ENVIRONMENT` | Runtime environment (`development`, `staging`, `production`) | `development` |
| `DEBUG` | Enable FastAPI debug mode | `True` |
| `SECRET_KEY` | Secret key for signing JWT tokens (min 32 characters in production) | Auto-configured for local dev |
| `DATABASE_URL` | Asynchronous SQLAlchemy connection string | `sqlite+aiosqlite:///contractly.db` |
| `NEON_DATABASE_URL` | Managed PostgreSQL connection string (staging/production) | `postgresql+asyncpg://user:pass@host/db` |
| `GEMINI_API_KEY` | Google Gemini AI API Key | *(Optional for local dev)* |
| `GEMINI_MODEL` | Gemini AI model identifier | `gemini-flash-lite-latest` |
| `STORAGE_PROVIDER` | Document storage engine (`local` or `s3`) | `local` |
| `LOCAL_STORAGE_DIR` | Absolute path for local file storage | `backend/storage/uploads` |
| `ALLOWED_ORIGINS` | Permitted CORS origins (comma-separated) | `http://localhost:3000,http://127.0.0.1:3000` |
| `EMAIL_ENABLED` | Enable transactional email delivery | `False` |
| `SMTP_HOST` | Outgoing SMTP server address | `smtp.example.com` |
| `SMTP_PORT` | SMTP port | `587` |
| `SMTP_USERNAME` | SMTP account username | `notifications@example.com` |
| `SMTP_PASSWORD` | SMTP account password | *(Secret)* |

---

## 7. Database Migrations

Contractly uses Alembic to manage database schema versions consistently across SQLite and PostgreSQL:

```bash
cd backend

# Apply all pending migrations to the latest revision:
alembic upgrade head

# Inspect migration history:
alembic history

# Verify current database revision:
alembic current
```

---

## 8. Quality Checks & Testing

Ensure all quality gates pass prior to opening a pull request:

### Backend Test Suite
```bash
# Run the complete test suite (46 test modules, 328 test cases):
pytest backend/tests

# Run core unit tests:
pytest backend/tests/test_tenant_isolation.py
pytest backend/tests/test_auth.py
pytest backend/tests/test_redline_generation.py
```

### Frontend Linting & Type Checking
```bash
# Run ESLint across Next.js source:
npm run lint

# Run strict TypeScript type verification without emitting bundles:
npx tsc --noEmit

# Test production build:
npm run build
```

---

## 9. Security, Privacy & Secret Management

- **Tenant Isolation:** Every contract, matter, obligation, and notification is scoped to an `organization_id`. Database queries strictly validate organizational ownership.
- **Authentication & Sessions:** Authentication utilizes short-lived JWT access tokens and sliding-window refresh tokens delivered via `HttpOnly`, `SameSite=Lax` cookies.
- **Document Protection:** Contract documents are stored in isolated per-contract storage directories. Direct disk traversal is blocked, and access requires verified active session authorization.
- **Zero Secrets in Repository:** Real secrets, passwords, production database connection strings, and customer contracts must never be committed to Git. `.gitignore` strictly excludes all `.env` files, `.db` databases, and `storage/uploads/`.

---

## 10. Deployment Architecture & External Services

### Implemented & Verified
- FastAPI REST backend with asynchronous PostgreSQL (`asyncpg`) and SQLite (`aiosqlite`) drivers.
- Multi-revision Alembic migration chain supporting PostgreSQL staging databases (Neon, Supabase).
- S3-compatible cloud storage adapter (`backend/app/services/storage/s3.py`) with pre-signed upload/download URLs.
- Next.js 15 production build with standalone SSR support.

### Production Prerequisites
- Managed PostgreSQL database instance with SSL enabled (`sslmode=require`).
- Private AWS S3 bucket or compatible object storage with private ACLs.
- Google Cloud Gemini API key configured with appropriate quota.
- SMTP provider (e.g., Amazon SES, SendGrid, or Postmark) for automated notifications.

---

## 11. Known Limitations & Legal Disclaimer

- **AI Recommendations:** Contractly provides automated contract analysis, obligation tracking, and redlining assistance for informational and operational efficiency. It does **not** provide formal legal advice. Contract revisions and risk flags should be verified by qualified legal counsel.
- **File Ingestion:** Optical character recognition (OCR) for scanned, non-searchable image PDFs is not currently enabled; uploaded documents must contain selectable text.

---

## 12. Contributing Guidelines

1. Review the existing test suite and architectural documentation in `docs/`.
2. Create a dedicated feature branch from `main`.
3. Ensure all backend tests (`pytest backend/tests`), frontend linting (`npm run lint`), and type checks (`npx tsc --noEmit`) pass with 0 errors.
4. Verify that no private data, databases, or local credentials are staged.
5. Submit a pull request with a clear description of changes and test verification results.

---

## 13. License

Copyright (c) 2026 Anish Kumar Singh. All rights reserved.

This project is proprietary and confidential. The source code is made publicly visible for evaluation and review purposes only. See the [LICENSE](LICENSE) file for complete licensing terms and inquiry details.
