# Contractly Phase 11.2: Staging Switch from Supabase to Neon Migration Report

**Date:** October 13, 2026  
**Status:** COMPLETE & VERIFIED  
**Target Provider:** Neon Serverless PostgreSQL (`neon.tech`)  
**Project ID:** `noisy-bread-32418623` (`contractly-staging-disposable`)  
**Region:** `aws-ap-southeast-1` (Singapore)  
**Engine Version:** PostgreSQL 17.11 on aarch64-unknown-linux-gnu  
**Workspace:** `A:\Soft Computing`  
**Rollback Protection:** Supabase staging project and configuration preserved 100% intact  

---

## 1. Executive Summary

Phase 11.2 successfully established a disposable staging PostgreSQL database on **Neon**, migrated the canonical Contractly schema from scratch, and verified full compatibility with live integration tests.

### Key Milestones Achieved
1. **Automated CLI Provisioning:** Authenticated via `neonctl` and created project `contractly-staging-disposable` (ID: `noisy-bread-32418623`) in AWS region `aws-ap-southeast-1` (Singapore) on PostgreSQL 17.
2. **Rollback State Preserved:** The working Supabase staging project (`qkvtvgumxlptrujblpet`) was not modified or deleted. Its environment configuration is backed up in `.env.staging.supabase` and `backend/.env.staging.supabase`.
3. **Zero Local Database Contamination:** Canonical SQLite databases (`contractly.db` and `backend/contractly.db`) and all 28 stored contract documents remain completely untouched and verified.
4. **Direct Endpoint Pinning:** Both Alembic and application traffic were pinned to the **Direct connection endpoint** (`ep-lingering-fog-a1kusnf0.ap-southeast-1.aws.neon.tech`) to guarantee that session-level PostgreSQL advisory locks (`pg_try_advisory_lock` / `pg_advisory_unlock`) function without transaction-pooler collisions.
5. **Full Schema Parity:** Applied the complete migration chain (`0001_initial_schema` -> `0002_email_security_workflows`). Verified that all 22 application tables, 1 `alembic_version` table, 33 foreign key constraints, and 65 indexes exist on Neon.
6. **Live Test Suite Passed:** All **13/13 live PostgreSQL integration tests passed** in 25.00s.

---

## 2. Neon Project & Region Configuration

### Project Metadata
- **Project Name:** `contractly-staging-disposable`
- **Project ID:** `noisy-bread-32418623`
- **Organization ID:** `org-dawn-rice-22239072`
- **Region:** `aws-ap-southeast-1` (Singapore, AWS)
  - *Region Selection Rationale:* Singapore is the closest available Neon AWS region to India, offering optimal network latency (~35–50 ms) compared to US or European regions.
- **Database Engine:** PostgreSQL 17.11 (64-bit aarch64)
- **Database Name:** `contractly_staging_disposable`
- **Plan:** Free Tier ($0/month, within the 100-project quota)

---

## 3. Connection Strategy & Environment Configuration

### Direct Endpoint vs. Pooled Endpoint
As identified in Phase 11.1, Neon provides two endpoint hostnames:
1. **Direct Endpoint:** `ep-lingering-fog-a1kusnf0.ap-southeast-1.aws.neon.tech` (Port 5432)
2. **Pooled Endpoint:** `ep-lingering-fog-a1kusnf0-pooler.ap-southeast-1.aws.neon.tech` (Port 5432, PgBouncer in transaction mode)

**Architecture Decision:** We configured **both** `ALEMBIC_DATABASE_URL` and `DATABASE_URL` to use the **Direct Endpoint**:
- **Alembic:** Strictly requires direct connection for DDL execution.
- **Application (`NotificationScheduler`):** Requires session-level advisory locks ([`backend/app/services/notifications/scheduler.py`](file:///A:/Soft%20Computing/backend/app/services/notifications/scheduler.py#L70-L111)). If routed through the pooler, transaction-mode PgBouncer rotates connections between queries, causing advisory lock loss. Using the direct endpoint eliminates this failure mode.
- **Connection Recovery:** Contractly's `DB_POOL_PRE_PING: bool = True` ([`backend/app/config.py`](file:///A:/Soft%20Computing/backend/app/config.py#L48)) automatically recycles connections whenever Neon compute wakes up from its 5-minute auto-suspend.

### Redacted `.env.staging` Configuration
```ini
# ==============================================================================
# CONTRACTLY STAGING ENVIRONMENT CONFIGURATION (NEON POSTGRESQL)
# Project ID: noisy-bread-32418623 (aws-ap-southeast-1)
# ==============================================================================

# Direct connection (Port 5432) - for Alembic migrations, DDL & session advisory locks
ALEMBIC_DATABASE_URL=postgresql+asyncpg://[REDACTED_USER]:[REDACTED_PASS]@ep-lingering-fog-a1kusnf0.ap-southeast-1.aws.neon.tech/contractly_staging_disposable?ssl=require

# Application traffic connection (Direct endpoint ensuring session-level advisory locks work)
DATABASE_URL=postgresql+asyncpg://[REDACTED_USER]:[REDACTED_PASS]@ep-lingering-fog-a1kusnf0.ap-southeast-1.aws.neon.tech/contractly_staging_disposable?ssl=require

# Staging Environment Flags
ENVIRONMENT=staging
DEBUG=false
AUTO_CREATE_TABLES=false
SECRET_KEY=[REDACTED_64_CHAR_HEX_KEY]
```

---

## 4. Pre-Flight Verification & Alembic Migration

### Pre-Flight Verification
Executed `scratch/verify_neon_staging.py` prior to running migrations:
- **Dialect:** `postgresql`
- **Driver:** `postgresql+asyncpg`
- **Host:** `ep-lingering-fog-a1kusnf0.ap-southeast-1.aws.neon.tech`
- **Database:** `contractly_staging_disposable`
- **User:** `contractly_staging_disposable_owner`
- **Schema Emptiness:** Confirmed exactly `0` tables in `public` schema.

### Alembic Migration Command
```bash
python -m alembic -c backend/alembic.ini upgrade head
```
**Output:**
```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 0001_initial_schema, Initial schema baseline for Contractly
INFO  [alembic.runtime.migration] Running upgrade 0001_initial_schema -> 0002_email_security_workflows, Phase 5 Email Delivery and Account Security Workflows schema migration
Returncode: 0
MIGRATION COMPLETED SUCCESSFULLY!
```

### Schema Inventory on Neon
- **Alembic Version:** `0002_email_security_workflows`
- **Total Tables in Public Schema:** 23 (22 application tables + 1 `alembic_version`)
  - `account_tokens`
  - `alembic_version`
  - `audit_logs`
  - `calendar_events`
  - `contract_approval_steps`
  - `contract_clauses`
  - `contract_notes`
  - `contract_redlines`
  - `contract_risks`
  - `contract_versions`
  - `contracts`
  - `departments`
  - `notifications`
  - `obligation_evidence`
  - `obligations`
  - `organization_invitations`
  - `organization_members`
  - `organizations`
  - `playbook_rules`
  - `refresh_tokens`
  - `user_notification_preferences`
  - `users`
  - `vendors`
- **Foreign Key Constraints:** 33 verified in `information_schema.table_constraints`.
- **Indexes:** 65 verified in `pg_indexes`.

---

## 5. Live PostgreSQL Integration Test Results

A live integration suite targeting the Neon database was executed:
```bash
python scratch/run_live_tests.py
```
*(Runs `backend/tests/test_phase_3_postgresql_readiness.py` and `backend/tests/test_phase_11_2_neon_live.py`)*

### Test Execution Summary

| Test ID | Area Tested | Result | Verification Notes |
| :--- | :--- | :--- | :--- |
| `test_alembic_migration_fresh_database_upgrade_and_downgrade` | DDL Lifecycle | **PASSED** | Upgrade/downgrade isolated cycle |
| `test_migration_environment_variable_precedence` | Env Precedence | **PASSED** | Offline SQL generation verified |
| `test_auto_create_tables_setting_prevents_silent_schema_mutation` | DDL Protection | **PASSED** | `AUTO_CREATE_TABLES=False` verified |
| `test_postgresql_availability_detection` | Live Detection Gate | **PASSED** | Live Neon endpoint verified |
| `test_scheduler_advisory_lock_connection_pinning` | Advisory Lock Unit | **PASSED** | Connection pinning verified |
| `test_scheduler_advisory_lock_busy_second_instance_skips` | Multi-Process Skip | **PASSED** | Lock contention handled |
| `test_upload_validator_bounded_streaming_memory` | Streaming Limits | **PASSED** | 413 limits enforced |
| `test_health_check_does_not_leak_connection_strings_or_secrets` | Sanitization | **PASSED** | /health endpoint sanitized |
| `test_neon_live_connectivity_and_version` | Live Connectivity | **PASSED** | Live PostgreSQL 17 on Neon verified |
| `test_neon_live_session_advisory_locking_concurrency` | Live Concurrency Lock | **PASSED** | Connection 1 held lock; Connection 2 received `False`; lock cleanly released |
| `test_neon_live_foreign_key_constraint_enforcement` | FK Enforcement | **PASSED** | Orphan department insert rejected |
| `test_neon_live_transaction_lifecycle_uniqueness_and_rollback` | ACID & Uniqueness | **PASSED** | Verified duplicate slug/email unique constraints via nested savepoints and rollback |
| `test_neon_live_tokens_and_invitations_lifecycle` | Phase 5 Workflows | **PASSED** | Verified `organization_invitations` and `account_tokens` foreign keys & queryability |

**Result:** **13 passed in 25.00s (0 failures)**.

---

## 6. Canonical SQLite Protection Audit

Strict read-only verification confirmed zero mutation of local data:

| Metric | `contractly.db` (Root) | `backend/contractly.db` | Status |
| :--- | :--- | :--- | :--- |
| **File Size** | 606,208 bytes | 155,648 bytes | **UNTOUCHED** |
| **Quick Check** | `ok` | `ok` | **HEALTHY** |
| **Contracts Count** | 31 | 0 | **UNTOUCHED** |
| **Clauses Count** | 127 | 0 | **UNTOUCHED** |
| **Versions Count** | 28 | 0 | **UNTOUCHED** |
| **Stored Documents** | 28 / 28 verified files | N/A | **INTACT** |

---

## 7. Known Limitations & Cost Considerations (Neon Free Tier)

1. **Scale-to-Zero Auto-Suspend:**
   - Compute suspends after 5 minutes of idle.
   - The first request after suspension has a ~1.0–1.5s cold-start latency.
   - `DB_POOL_PRE_PING: bool = True` prevents disconnected socket errors on wake.
2. **Compute Allowance:**
   - 100 Compute Unit-hours (CU-hrs)/month included free.
   - For staging development, this allows ~400 hours of active testing time.
   - **Recommendation:** Do not configure continuous background worker polling (e.g. every 10 seconds) in staging; run on-demand or at 15-minute intervals.
3. **Storage:**
   - 1 GB included per project (Contractly's empty staging schema uses < 10 MB).
4. **Cost:**
   - $0 / month (no credit card required, within free tier).

---

## 8. Rollback Procedure: Switching Back to Supabase

The Supabase staging database remains completely untouched and ready. If you ever wish to switch back to Supabase:

1. Restore the backed-up environment files:
   ```powershell
   Copy-Item "A:\Soft Computing\.env.staging.supabase" "A:\Soft Computing\.env.staging" -Force
   Copy-Item "A:\Soft Computing\backend\.env.staging.supabase" "A:\Soft Computing\backend\.env.staging" -Force
   ```
2. Verify connectivity:
   ```powershell
   python "scratch/verify_supabase_staging.py"
   ```

No re-migration or cloud recreation is necessary.

---

## 9. Conclusion & Next Step

Neon staging is **100% configured, migrated, verified, and operational**.

### Recommended Next Step
Advance to **Contractly Phase 12: Staging Application Deployment & E2E Validation**:
- Launch the backend against Neon staging: `uvicorn app.main:app --env-file .env.staging`.
- Run end-to-end user registration, login, contract upload, redline, and approvals workflows.
- Validate frontend UI integration.

*Awaiting your instruction to proceed.*
