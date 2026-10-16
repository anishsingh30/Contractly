# CONTRACTLY: CANONICAL DATABASE & DOCUMENT INTEGRITY VERIFICATION

**Workspace:** `A:\Soft Computing`  
**Execution Date:** 2026-10-13  
**Mode:** Strictly Read-Only (Zero Mutations)  

---

## 1. Database Identification and Physical File Resolution

Two database file paths exist in the repository. Both paths were inspected and resolved to their absolute filesystem locations:

| Path | Absolute Path | Exists | Size (Bytes) | Last Modified (UTC) | SHA-256 Checksum |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `backend/contractly.db` | `A:\Soft Computing\backend\contractly.db` | Yes | 155,648 | 2026-10-07T15:19:45Z | `105525662a340f833f29c57ba9cc836b9e1d8284ca015cbec4a9a3afa201341f` |
| `contractly.db` | `A:\Soft Computing\contractly.db` | Yes | 598,016 | 2026-10-13T15:20:17Z | `81e633e08568f74e8cd8d258d909f3c1ec74dfd3681e311947aca89b2ef9edc5` |

### Physical File Analysis
- **Same File Check (`os.path.samefile`):** `False` (They do not share inodes or hard links).
- **Checksum Match:** `False` (They are separate files with different schemas and contents).

### Canonical Role Determination
- **Authoritative Canonical Database:** `A:\Soft Computing\contractly.db`.
  - Configured in [backend/app/config.py](file:///a:/Soft%20Computing/backend/app/config.py):
    ```python
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    CANONICAL_DB_PATH = os.path.join(BASE_DIR, "contractly.db").replace("\\", "/")
    DATABASE_URL: str = f"sqlite+aiosqlite:///{CANONICAL_DB_PATH}"
    ```
  - Configured in [backend/alembic/env.py](file:///a:/Soft%20Computing/backend/alembic/env.py) via fallback to `settings.DATABASE_URL`.
  - Configured in [backend/migrate_db.py](file:///a:/Soft%20Computing/backend/migrate_db.py) (`sqlite3.connect('../contractly.db')`).
  - Contains all customer organizations, users, agreements, extracted clauses, risks, approval workflows, and audit logs.
- **Secondary Database (`backend/contractly.db`):**
  - Static 155 KB SQLite file unmodified since October 7, 2026.
  - Contains an empty initial 11-table schema template with 0 records across all tables.

---

## 2. SQLite Integrity and Foreign Key Checks

Both databases were opened strictly in read-only mode (`file:<path>?mode=ro`, `uri=True`).

| Target Database | PRAGMA integrity_check | PRAGMA foreign_key_check | Status |
| :--- | :---: | :---: | :---: |
| `backend/contractly.db` | `[('ok',)]` | `[]` (0 violations) | **HEALTHY** |
| `contractly.db` (Root Canonical) | `[('ok',)]` | `[]` (0 violations) | **HEALTHY** |

Neither database shows page corruption, freelist leaks, index inconsistencies, or orphaned foreign keys.

---

## 3. Schema Inspection and Record Counts

### Table Counts by Database

| Table Name | `backend/contractly.db` | `contractly.db` (Canonical) | Notes |
| :--- | :---: | :---: | :---: |
| `contracts` | 0 | **31** | Core contract records |
| `contract_versions` | 0 | **28** | Document versions and storage metadata |
| `contract_clauses` | 0 | **127** | Extracted and normalized clauses |
| `contract_risks` | 0 | **31** | Identified legal and commercial risks |
| `contract_approval_steps` | 0 | **4** | Multi-step approval records |
| `contract_redlines` | 0 | **2** | Inline redline revisions |
| `contract_notes` | - | **0** | Table present, empty |
| `organizations` | 0 | **19** | Multi-tenant organization entities |
| `organization_members` | 0 | **17** | Tenant membership associations |
| `departments` | 0 | **6** | Organizational departments |
| `users` | 0 | **17** | User accounts |
| `refresh_tokens` | - | **65** | Active & historical refresh tokens (rotated) |
| `obligations` | 0 | **10** | Extracted obligations |
| `obligation_evidence` | 0 | **0** | Table present, empty |
| `audit_logs` | 0 | **18** | Privacy-first audit trail events |
| `calendar_events` | - | **0** | Table present, empty |
| `notifications` | - | **0** | Table present, empty |
| `user_notification_preferences` | - | **3** | User notification settings |
| `vendors` | - | **0** | Table present, empty |
| `playbook_rules` | - | **0** | Table present, empty |
| **Total Tables** | **11** | **20** | - |

*(Sensitive user details, contract texts, password hashes, and token strings were suppressed in accordance with safety instructions).*

### Migration Revision & Alembic Compatibility
- **`alembic_version` Table:** Neither database currently contains an `alembic_version` table.
- **Alembic Revisions Comparison:**
  - `0001_initial_schema.py` defines exactly 20 tables: all 20 tables exist in `contractly.db` with identical schema definitions.
  - `0002_email_security_workflows.py` defines `account_tokens` and `organization_invitations`: these tables have not been created in `contractly.db`, as migrations against canonical databases are strictly disabled (`AUTO_CREATE_TABLES = False`).
  - The canonical schema is fully compatible with `0001_initial_schema` and can be stamped to revision `0001_initial_schema` when a disposable staging migration is prepared.

---

## 4. Document Reference and Storage Verification

The `contract_versions` table was inspected for document storage metadata (`file_storage_path`, `file_byte_size`, and `sha256_checksum`).

### Storage Audit Summary
- **Referenced Document Records:** **28**
- **Files Found on Disk:** **28** (100% found in `backend/storage/uploads/<tenant_id>/...`)
- **Missing Files:** **0**
- **Exact Size Matches (`file_byte_size`):** **28** (100% exact byte-for-byte match)
- **Size Mismatches:** **0**
- **Cryptographic SHA-256 Matches:** **28** (100% exact match against stored checksums)
- **Checksum Mismatches:** **0**
- **Unverified Documents (No Checksum Stored):** **0**
- **Evidence Files (`obligation_evidence`):** 0 records referenced; 0 files missing.

Every uploaded contract document on disk is cryptographically intact and matches its database record.

---

## 5. Genuine Baseline Comparison

### Available Historical Baselines
1. **Phase 6 Audit Report (`CONTRACTLY_PHASE_6_AUDIT_REPORT.md`):**
   - Verified `backend/contractly.db` integrity check: `PRAGMA integrity_check -> ok`.
   - Stated zero canonical records or stored documents were modified.
   - Did not record a pre-audit SHA-256 hash or per-table row counts for `contractly.db`.
2. **Phase 7 Report (`CONTRACTLY_PHASE_7_REPORT.md`):**
   - Recorded `backend/contractly.db`: 155,648 bytes, 11 tables, 0 records. (Matches current state 100%).
   - Recorded `contractly.db` core entity counts:
     - `contracts`: 31 (Matches: **31**)
     - `contract_clauses`: 127 (Matches: **127**)
     - `contract_risks`: 31 (Matches: **31**)
     - `contract_versions`: 28 (Matches: **28**)
     - `users`: 17 (Matches: **17**)
     - `organizations`: 19 (Matches: **19**)
     - `organization_members`: 17 (Matches: **17**)
     - `obligations`: 10 (Matches: **10**)
     - `departments`: 6 (Matches: **6**)
     - `contract_approval_steps`: 4 (Matches: **4**)
     - `contract_redlines`: 2 (Matches: **2**)
     - `audit_logs`: 18 (Matches: **18**)
     - `user_notification_preferences`: 3 (Matches: **3**)
     - `refresh_tokens`: 64 (Current: **65**)

### Variance Analysis
- All business entities (contracts, versions, clauses, risks, approvals, redlines, obligations, users, orgs, departments, and audit logs) are **100% identical** to the Phase 7 baseline.
- `refresh_tokens` increased by 1 (from 64 to 65 records) at `2026-10-13 15:20:17 UTC`. Inspection confirmed this was caused by an automatic session keepalive refresh request from the user's active browser session on `http://localhost:3000` interacting with the background development server.
- Because no cryptographic SHA-256 baseline manifest was recorded prior to Phase 7 for `contractly.db`, historical bit-for-bit preservation from Phase 1–5 cannot be conclusively proven from the database alone, even though current integrity is pristine and all document checksums match.

---

## 6. Anomalies and Recommended Next Steps

### Anomalies Detected
1. **Dual Database Presence:** `backend/contractly.db` (155 KB empty template) and `contractly.db` (598 KB active canonical) coexist. The active backend configuration specifically targets `contractly.db` at workspace root.
2. **Missing `alembic_version` Table:** Neither SQLite database has an `alembic_version` tracking table, although the schema in `contractly.db` matches `0001_initial_schema` exactly.
3. **Active Background Dev Server:** The background development server running on port 8000 writes session refresh tokens to `contractly.db` when an authenticated browser tab remains open.

### Recommended Next Steps
1. Archive `backend/contractly.db` to a backup location (`docs/backups/`) or clarify its role as a template in documentation to prevent confusion about which database is canonical.
2. When creating the dedicated PostgreSQL staging database in Phase 8, run `alembic stamp 0001_initial_schema` and `alembic upgrade head` exclusively against the disposable PostgreSQL target, never against `contractly.db`.
3. To freeze `contractly.db` completely for offline audits, execute `stop.vbs` to terminate background hot-reload server processes and stop token rotation.

---

## Status

**PARTIAL: Current integrity verified, but historical preservation is not fully proven.**  
*(Current SQLite page integrity is clean, all foreign keys pass, all 28 document files cryptographically match their stored SHA-256 hashes, and all business entity record counts match the Phase 7 baseline. However, pre-Phase 7 SHA-256 baseline manifests were not historically recorded, and active browser keepalive requests rotate refresh tokens in `contractly.db`).*
