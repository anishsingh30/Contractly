# Contractly Backup and Recovery Runbook

This runbook documents the disaster recovery, backup procedures, document migration, and safe cutover policies for Contractly's relational databases and document storage providers.

---

## 1. Architecture and Consistency Model

Contractly manages two complementary data domains:
1. **Relational Database (`contractly.db` / PostgreSQL):** Stores tenants, users, contracts, clauses, approval workflows, obligation records, and audit logs. Document references (`file_storage_path`, `sha256_checksum`, `file_byte_size`) reside here.
2. **Object / Document Store (`storage/uploads` / S3 bucket):** Stores encrypted binary contract files, versions, redlines, and obligation evidence.

### Point-in-Time Synchronization Principle
A database record that points to a non-existent document file produces a broken user experience and violates audit integrity. Therefore:
- Backups coordinate database snapshots with document snapshots.
- Restoration operations verify both the relational schema and the cryptographic SHA-256 checksums of every restored document before marking recovery successful.
- Deletions are soft-deleted or append-only; source documents are never deleted during migration or backup.

---

## 2. Automated Backup Execution

Contractly provides an automated, non-destructive backup utility at [`backend/scripts/backup.py`](file:///a:/Soft%20Computing/backend/scripts/backup.py).

### Commands

#### SQLite Development / Staging Backup
```bash
python backend/scripts/backup.py \
  --backup-dir backend/backups \
  --max-backups 10 \
  --retention-days 14
```

#### PostgreSQL Production Backup
```bash
# Secrets are supplied via environment variables, NEVER passed as CLI arguments
export PGPASSWORD="<db-password>"
python backend/scripts/backup.py \
  --backup-dir /var/backups/contractly \
  --db-url "postgresql://app_user@db.internal:5432/contractly_prod" \
  --storage-dir /var/contractly/storage/uploads \
  --max-backups 30 \
  --retention-days 30
```

### Manifest Structure
Each backup creates a timestamped subdirectory (`backup_YYYYMMDD_HHMMSS/`) containing:
- `manifest.json`: Tamper-evident record of backup metadata, database checksum, and individual document SHA-256 hashes.
- `database.dump` or `database.sqlite3`: Crash-consistent database snapshot.
- `documents.tar.gz`: Gzip-compressed archive of all tenant documents with directory structures preserved.

---

## 3. Safe Recovery and Restore Procedure

Contractly provides a guarded recovery utility at [`backend/scripts/restore.py`](file:///a:/Soft%20Computing/backend/scripts/restore.py).

### Strict Safety Guards
1. **Target Confirmation Required:** The `--confirm-target` argument must match `--target-db` character-for-character to prevent accidental restoration into active databases.
2. **Canonical Database Protection:** Restoration into the canonical workspace database (`contractly.db`) is blocked by default to prevent catastrophic data loss.
3. **Pre-Restoration Checksum Validation:** The restore utility verifies the SHA-256 checksum of both the database dump and the document archive against `manifest.json` before unpacking.
4. **Post-Restoration Integrity Verification:** Restored documents are verified on disk for SHA-256 matching.

### Recovery Execution Example
```bash
python backend/scripts/restore.py \
  --backup-path backend/backups/backup_20261013_120000 \
  --target-db backend/backups/disposable_restore_test.db \
  --target-storage-dir backend/backups/disposable_storage \
  --confirm-target backend/backups/disposable_restore_test.db
```

---

## 4. Document Migration and Cloud Cutover Plan

When migrating from local disk storage to cloud S3 storage, execute the dry-run-first migration utility [`backend/scripts/migrate_storage.py`](file:///a:/Soft%20Computing/backend/scripts/migrate_storage.py).

### Phase 1: Dry-Run Assessment (Non-destructive)
1. Run the migration script in dry-run mode (the default):
   ```bash
   python backend/scripts/migrate_storage.py --dry-run
   ```
2. Inspect the generated `storage_migration_manifest_<timestamp>.json`:
   - Verify `dry_run_count` matches the total document count.
   - Confirm `missing_count == 0` and `failed_count == 0`.
   - Review any `unreferenced_files` on disk.

### Phase 2: Copy and Verification (Non-destructive)
1. Execute migration with explicit `--apply` flag:
   ```bash
   python backend/scripts/migrate_storage.py --apply
   ```
2. The utility copies files to S3, calculates destination SHA-256, and records `VERIFIED` in the manifest.
3. Local source files remain intact on disk.

### Phase 3: Final Verification
1. Run verification against the destination:
   ```bash
   python backend/scripts/migrate_storage.py --verify-only
   ```
2. Confirm all records are marked `VERIFIED`.

### Phase 4: Production Cutover (Maintenance Window)
1. Set the application to read-only or brief maintenance mode.
2. Run any incremental document sync with `--apply`.
3. Update environment configuration:
   ```env
   STORAGE_PROVIDER=s3
   S3_BUCKET_NAME=contractly-documents-prod
   S3_REGION_NAME=us-east-1
   ```
4. Restart application instances.
5. Verify document upload and download routes using smoke tests.
6. **Rollback Plan:** If any issue arises, revert `STORAGE_PROVIDER=local` and restart the application immediately. Local files remain available and unaltered.

---

## 5. Security and Secret Handling

- Backups must be stored in encrypted storage volumes (e.g., AWS S3 SSE-KMS or encrypted EBS).
- Database credentials must never appear in command-line arguments, scripts, or commit history.
- Backup directories (`backend/backups/`) and manifest files are excluded from Git via `.gitignore`.
- S3 buckets storing contracts must have Public Access Blocked, Default Server-Side Encryption enabled, and Versioning enabled.
