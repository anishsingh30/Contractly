# Contractly Phase 11: Managed PostgreSQL Staging Setup Report

**Date:** October 13, 2026  
**Status:** COMPLETE & VERIFIED  
**Target Provider:** Supabase Managed PostgreSQL (AWS `ap-northeast-2`)  
**Engine Version:** PostgreSQL 17.11 on x86_64-pc-linux-gnu (gcc 15.2.0, 64-bit)  
**Workspace:** `A:\Soft Computing`  
**Execution Type:** Live Remote Execution & Non-Destructive Verification  

---

## 1. Executive Summary

Phase 11 established a dedicated, live, disposable PostgreSQL staging database for Contractly using **Supabase** (`db.qkvtvgumxlptrujblpet.supabase.co`). 

All Phase 11 objectives have been achieved without compromising security or local state:
1. **Zero SQLite Contamination:** Canonical SQLite databases (`contractly.db` and `backend/contractly.db`) and all 28 stored document files remained 100% untouched and preserved.
2. **Clean Migration Chain Execution:** The complete Alembic migration sequence (`0001_initial_schema` -> `0002_email_security_workflows`) was executed against the clean staging database using direct port 5432 SSL connections.
3. **Verified Schema Parity:** All 22 application tables, 1 `alembic_version` tracker table, 33 foreign key constraints, and 65 indexes were created and verified directly via PostgreSQL information schema and catalogs.
4. **Live Integration Tests:** Live PostgreSQL integration tests verified connection stability, multi-session PostgreSQL advisory locking (`pg_try_advisory_lock` / `pg_advisory_unlock`), strict foreign key constraint enforcement, and transactional rollback lifecycle.
5. **Full Regression Suite Passed:** All 230 backend automated tests passed (0 failures), and the production frontend build (`npm.cmd run build`) completed cleanly across all 14 routes.

---

## 2. Provider Evaluation & Provisioning

### Selected Provider: Supabase
- **Project Ref:** `qkvtvgumxlptrujblpet`
- **Region:** `ap-northeast-2` (Seoul, AWS)
- **Engine:** PostgreSQL 17.11 64-bit
- **Rationale:**
  - Supabase delivers standard, unmodified PostgreSQL with native SSL support, making it completely compatible with SQLAlchemy 2.x and `asyncpg` without requiring any proprietary extensions or SDKs.
  - Direct port 5432 connection is available for DDL migration operations (Alembic), while PgBouncer connection pooling (port 6543) is available for high-concurrency app traffic.
  - Full support for PostgreSQL session-level advisory locks (`pg_try_advisory_lock` / `pg_advisory_unlock`) used by Contractly's scheduler worker.

---

## 3. Environment Isolation & Canonical SQLite Protection

### Absolute Safety Assertions
Prior to executing any remote command, strict assertions verified that:
1. Canonical databases `contractly.db` and `backend/contractly.db` were never opened for writing, stamped, or migrated.
2. `ALEMBIC_DATABASE_URL` and `DATABASE_URL` explicitly targeted remote host `*.supabase.co` on dialect `postgresql+asyncpg`.
3. Pre-flight connection confirmed `0` existing tables in the `public` schema prior to migration.

### Canonical SQLite Audit Baseline Comparison

| Artifact | Verification Metric | Baseline (Pre-Phase 11) | Post-Phase 11 Audit | Status |
| :--- | :--- | :--- | :--- | :--- |
| `contractly.db` | File Size | 606,208 bytes | 606,208 bytes | **UNTOUCHED** |
| `contractly.db` | SHA-256 | `da73f4aa70b36f5d142bdff787b80e31c018d61a9f66f9bc5fd6734ecb54363b` | `da73f4aa70b36f5d142bdff787b80e31c018d61a9f66f9bc5fd6734ecb54363b` | **IDENTICAL** |
| `contractly.db` | Contracts Count | 31 | 31 | **UNTOUCHED** |
| `contractly.db` | Clauses Count | 127 | 127 | **UNTOUCHED** |
| `contractly.db` | Versions Count | 28 | 28 | **UNTOUCHED** |
| `contractly.db` | SQLite PRAGMA check | `ok` | `ok` | **HEALTHY** |
| `backend/contractly.db` | File Size | 155,648 bytes | 155,648 bytes | **UNTOUCHED** |
| `backend/contractly.db` | SHA-256 | `105525662a340f833f29c57ba9cc836b9e1d8284ca015cbec4a9a3afa201341f` | `105525662a340f833f29c57ba9cc836b9e1d8284ca015cbec4a9a3afa201341f` | **IDENTICAL** |
| Stored Documents | Disk Count | 28 files | 28 files | **INTACT (28/28)** |

---

## 4. Staging Configuration

Two staging configuration files were established and added to `.gitignore` to prevent credential exposure:
- `A:\Soft Computing\.env.staging`
- `A:\Soft Computing\backend\.env.staging`

### Redacted Environment Variable Template
```ini
# ==============================================================================
# CONTRACTLY STAGING ENVIRONMENT CONFIGURATION (SUPABASE)
# Project ID: qkvtvgumxlptrujblpet (ap-northeast-2)
# ==============================================================================

# Database Password (Percent-encoded for special characters)
STAGING_DB_PASSWORD=[REDACTED]

# Direct connection (Port 5432) - for Alembic migrations & DDL
ALEMBIC_DATABASE_URL=postgresql+asyncpg://postgres:[REDACTED]@db.qkvtvgumxlptrujblpet.supabase.co:5432/postgres?ssl=require

# Application traffic connection
DATABASE_URL=postgresql+asyncpg://postgres:[REDACTED]@db.qkvtvgumxlptrujblpet.supabase.co:5432/postgres?ssl=require

# Staging Environment Flags
ENVIRONMENT=staging
DEBUG=false
AUTO_CREATE_TABLES=false
SECRET_KEY=[REDACTED_64_CHAR_HEX_KEY]
```

> **Security Note:** Special character `@` in the staging password was percent-encoded as `%40` to ensure robust RFC 3986 URL parsing across SQLAlchemy and asyncpg.

---

## 5. Live Alembic Migration Execution

### Migration Execution Command
```bash
python -m alembic -c backend/alembic.ini upgrade head
```
**Environment:** `ALEMBIC_DATABASE_URL` directed to Supabase port 5432.

### Execution Log Output
```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 0001_initial_schema, Initial schema baseline for Contractly
INFO  [alembic.runtime.migration] Running upgrade 0001_initial_schema -> 0002_email_security_workflows, Phase 5 Email Delivery and Account Security Workflows schema migration
Returncode: 0
MIGRATION TO SUPABASE COMPLETED SUCCESSFULLY!
```

### Migrated Schema Inventory (Live Supabase Inspection)
- **Current Version:** `0002_email_security_workflows`
- **Total Tables in Public Schema:** 23 (22 application tables + 1 `alembic_version`)
  - `account_tokens` (0 rows)
  - `alembic_version` (1 row)
  - `audit_logs` (0 rows)
  - `calendar_events` (0 rows)
  - `contract_approval_steps` (0 rows)
  - `contract_clauses` (0 rows)
  - `contract_notes` (0 rows)
  - `contract_redlines` (0 rows)
  - `contract_risks` (0 rows)
  - `contract_versions` (0 rows)
  - `contracts` (0 rows)
  - `departments` (0 rows)
  - `notifications` (0 rows)
  - `obligation_evidence` (0 rows)
  - `obligations` (0 rows)
  - `organization_invitations` (0 rows)
  - `organization_members` (0 rows)
  - `organizations` (0 rows)
  - `playbook_rules` (0 rows)
  - `refresh_tokens` (0 rows)
  - `user_notification_preferences` (0 rows)
  - `users` (0 rows)
  - `vendors` (0 rows)
- **Foreign Key Constraints:** 33 verified in `information_schema.table_constraints`.
- **Indexes:** 65 verified in `pg_indexes`.

---

## 6. Live PostgreSQL Integration Tests & Results

A dedicated live test suite (`backend/tests/test_phase_11_supabase_live.py`) was implemented and executed alongside `backend/tests/test_phase_3_postgresql_readiness.py`:

```bash
python -m pytest backend/tests/test_phase_3_postgresql_readiness.py backend/tests/test_phase_11_supabase_live.py -v
```

### Test Results

| Test ID | Description | Result | Execution Details |
| :--- | :--- | :--- | :--- |
| `test_alembic_migration_fresh_database_upgrade_and_downgrade` | Disposable Alembic upgrade/downgrade | **PASSED** | Validated DDL lifecycle |
| `test_migration_environment_variable_precedence` | ALEMBIC_DATABASE_URL env override precedence | **PASSED** | Confirmed offline SQL generation |
| `test_auto_create_tables_setting_prevents_silent_schema_mutation` | Unmanaged create_all prevention | **PASSED** | `AUTO_CREATE_TABLES=False` verified |
| `test_postgresql_availability_detection` | Truthful live PostgreSQL gate | **PASSED** | Live Supabase endpoint detected |
| `test_scheduler_advisory_lock_connection_pinning` | Advisory lock connection pinning | **PASSED** | Unit verification |
| `test_scheduler_advisory_lock_busy_second_instance_skips` | Multi-instance lock concurrency | **PASSED** | Unit verification |
| `test_upload_validator_bounded_streaming_memory` | 413 stream limits without memory spike | **PASSED** | Memory bounds enforced |
| `test_health_check_does_not_leak_connection_strings_or_secrets` | Zero credential leakage on /health | **PASSED** | Health payload sanitized |
| `test_supabase_live_connection_and_version` | Live connection & version query | **PASSED** | Returned PostgreSQL 17.11 on Supabase |
| `test_supabase_live_advisory_locking` | Live multi-connection advisory lock acquisition & release | **PASSED** | `pg_try_advisory_lock` / `pg_advisory_unlock` verified across distinct connections |
| `test_supabase_live_schema_foreign_key_enforcement` | Live FK constraint violation check | **PASSED** | Non-existent org insertion failed with foreign key constraint error |
| `test_supabase_live_transactional_lifecycle_and_cleanup` | Live transaction, unique constraint, & rollback | **PASSED** | Inserted org/user, verified unique duplicate email/slug constraints via savepoints, verified complete rollback |

**Live Test Suite Summary:** 12 passed in 32.76s.

### Full Regression Suite
- **Backend Test Suite:** `230 passed, 5 skipped, 0 failed` in 129.62s.
- **Frontend Build (`next build`):** `Compiled successfully in 4.3s`. All 14 routes statically generated with 0 errors.

---

## 7. PostgreSQL Parity Assessment & Key Observations

1. **Transactional Strictness:** PostgreSQL strictly marks a transaction as aborted (`InFailedSqlTransactionError`) if a statement encounters an error (e.g. duplicate key or foreign key violation). Application code executing speculative queries inside an open transaction must use savepoints (`conn.begin_nested()`) or execute in independent transactions.
2. **Advisory Locking Reliability:** Native `pg_try_advisory_lock(int8)` behaves identically to expectations on Supabase, allowing Contractly's `NotificationScheduler` to run across multi-process container deployments without task race conditions.
3. **Session vs Pool Connection:**
   - **Direct Port 5432:** Must continue to be used for Alembic DDL migrations and operations relying on session-level advisory locks.
   - **PgBouncer Port 6543 (Transaction Mode):** Can be used for general REST API query traffic once production traffic scaling is required.

---

## 8. Single Safest Next Step

**Phase 11 is 100% complete.**

The single safest next step is **Contractly Phase 12: Staging Application Deployment & E2E Validation**:
- Run Contractly's FastAPI backend locally with `ENVIRONMENT=staging` and `DATABASE_URL` pointing to the Supabase database.
- Execute authenticated API requests (registration, login, contract creation, approval workflow) against the staging database to confirm end-to-end runtime behavior.
- Validate that the frontend UI interacts seamlessly with the staging backend.

*Awaiting your instruction to proceed.*
