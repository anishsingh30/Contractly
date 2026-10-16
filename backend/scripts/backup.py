#!/usr/bin/env python3
"""
Contractly Safe Backup Utility
==============================
Creates synchronized, point-in-time backups of the Contractly database
and document storage repository with cryptographic verification.

Safety & Security:
- Avoids exposing secrets or credentials in logs or command arguments.
- Creates tamper-evident backup manifests with SHA-256 checksums.
- Supports both PostgreSQL (pg_dump) and SQLite (online backup API).
- Configurable retention policy.
- Excluded from source control.
"""

import argparse
import datetime
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional, Tuple

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("contractly.backup")


def compute_file_sha256(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def backup_sqlite(source_db_path: str, destination_path: str) -> Tuple[str, int]:
    """Uses SQLite online backup API to take a crash-consistent, non-locking snapshot."""
    logger.info("Creating SQLite backup via online backup API from %s", source_db_path)
    os.makedirs(os.path.dirname(os.path.abspath(destination_path)), exist_ok=True)
    
    src_conn = sqlite3.connect(source_db_path)
    dst_conn = sqlite3.connect(destination_path)
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

    checksum = compute_file_sha256(destination_path)
    size = os.path.getsize(destination_path)
    logger.info("SQLite backup complete: %d bytes (SHA-256: %s...)", size, checksum[:8])
    return checksum, size


def backup_postgresql(database_url: str, destination_path: str) -> Tuple[str, int]:
    """Backs up PostgreSQL database using pg_dump without exposing credentials."""
    logger.info("Creating PostgreSQL backup to %s", destination_path)
    os.makedirs(os.path.dirname(os.path.abspath(destination_path)), exist_ok=True)

    # Parse URL without printing password
    # postgresql+asyncpg://user:pass@host:port/dbname
    cleaned_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    parsed = urlparse(cleaned_url)

    host = parsed.hostname or "localhost"
    port = str(parsed.port or 5432)
    user = parsed.username or "postgres"
    dbname = parsed.path.lstrip("/")
    password = parsed.password or ""

    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password

    cmd = [
        "pg_dump",
        "-h", host,
        "-p", port,
        "-U", user,
        "-F", "c",  # Custom archive format
        "-b",       # Include large objects
        "-v",
        "-f", destination_path,
        dbname
    ]

    try:
        res = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
    except FileNotFoundError:
        raise RuntimeError("pg_dump executable not found on system PATH. Install PostgreSQL client tools.")
    except subprocess.CalledProcessError as e:
        logger.error("pg_dump failed: %s", e.stderr)
        raise RuntimeError(f"pg_dump execution failed: {e.returncode}")

    checksum = compute_file_sha256(destination_path)
    size = os.path.getsize(destination_path)
    return checksum, size


def backup_documents(source_dir: str, destination_tar: str) -> Tuple[List[Dict[str, Any]], int]:
    """Archives all documents into a compressed tarball and records manifest."""
    logger.info("Archiving documents from %s to %s", source_dir, destination_tar)
    os.makedirs(os.path.dirname(os.path.abspath(destination_tar)), exist_ok=True)

    doc_entries = []
    total_size = 0

    with tarfile.open(destination_tar, "w:gz") as tar:
        if os.path.exists(source_dir):
            for root, _, files in os.walk(source_dir):
                for f in files:
                    full_path = os.path.join(root, f)
                    rel_path = os.path.relpath(full_path, source_dir).replace("\\", "/")
                    file_sha = compute_file_sha256(full_path)
                    file_size = os.path.getsize(full_path)
                    total_size += file_size

                    tar.add(full_path, arcname=rel_path)
                    doc_entries.append({
                        "relative_path": rel_path,
                        "sha256": file_sha,
                        "size_bytes": file_size,
                    })

    logger.info("Archived %d documents (%d bytes)", len(doc_entries), total_size)
    return doc_entries, total_size


def apply_retention_policy(backups_dir: str, max_backups: Optional[int], retention_days: Optional[int]) -> int:
    """Cleans up older backups based on retention policy."""
    if not os.path.exists(backups_dir):
        return 0

    removed = 0
    now = datetime.datetime.now(datetime.timezone.utc)

    # Find backup directories (format: backup_YYYYMMDD_HHMMSS)
    entries = []
    for d in os.listdir(backups_dir):
        full = os.path.join(backups_dir, d)
        if os.path.isdir(full) and d.startswith("backup_"):
            mtime = os.path.getmtime(full)
            entries.append((mtime, full))

    entries.sort(key=lambda x: x[0], reverse=True)  # Newest first

    for idx, (mtime, path) in enumerate(entries):
        age_days = (now.timestamp() - mtime) / 86400.0
        should_remove = False

        if retention_days is not None and age_days > retention_days:
            should_remove = True
        elif max_backups is not None and idx >= max_backups:
            should_remove = True

        if should_remove:
            logger.info("Applying retention: removing old backup %s", path)
            shutil.rmtree(path, ignore_errors=True)
            removed += 1

    return removed


def create_backup(
    destination_root: Optional[str] = None,
    database_url: Optional[str] = None,
    storage_dir: Optional[str] = None,
    max_backups: Optional[int] = None,
    retention_days: Optional[int] = None,
) -> Dict[str, Any]:
    """Executes a coordinated backup of database and storage documents."""
    destination_root = destination_root or os.path.join(BACKEND_DIR, "backups")
    db_url = database_url or settings.DATABASE_URL
    storage_dir = storage_dir or settings.LOCAL_STORAGE_DIR

    timestamp_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_id = f"backup_{timestamp_str}"
    target_backup_dir = os.path.join(destination_root, backup_id)
    os.makedirs(target_backup_dir, exist_ok=True)

    logger.info("=== STARTING CONTRACTLY BACKUP [%s] ===", backup_id)
    logger.info("Destination directory: %s", target_backup_dir)

    # 1. Database Backup
    db_filename = "database.sqlite3" if "sqlite" in db_url else "database.dump"
    target_db_file = os.path.join(target_backup_dir, db_filename)

    if "sqlite" in db_url:
        db_type = "sqlite"
        raw_db_path = db_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
        db_checksum, db_size = backup_sqlite(raw_db_path, target_db_file)
    else:
        db_type = "postgresql"
        db_checksum, db_size = backup_postgresql(db_url, target_db_file)

    # 2. Document Storage Backup
    target_docs_tar = os.path.join(target_backup_dir, "documents.tar.gz")
    docs_metadata, docs_total_size = backup_documents(storage_dir, target_docs_tar)
    docs_tar_checksum = compute_file_sha256(target_docs_tar)

    # 3. Create Manifest
    manifest = {
        "backup_id": backup_id,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "database": {
            "type": db_type,
            "filename": db_filename,
            "size_bytes": db_size,
            "sha256": db_checksum,
        },
        "documents": {
            "archive_filename": "documents.tar.gz",
            "archive_sha256": docs_tar_checksum,
            "document_count": len(docs_metadata),
            "uncompressed_total_bytes": docs_total_size,
            "items": docs_metadata,
        }
    }

    manifest_path = os.path.join(target_backup_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Backup manifest created at %s", manifest_path)

    # 4. Retention Policy
    if max_backups is not None or retention_days is not None:
        cleaned = apply_retention_policy(destination_root, max_backups, retention_days)
        logger.info("Cleaned up %d older backups according to retention policy.", cleaned)

    logger.info("=== BACKUP [%s] COMPLETED SUCCESSFULLY ===", backup_id)
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Contractly Backup Utility")
    parser.add_argument(
        "--backup-dir",
        type=str,
        default=None,
        help="Root directory to store backups (default: backend/backups)",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="Database URL to back up (default: from configuration)",
    )
    parser.add_argument(
        "--storage-dir",
        type=str,
        default=None,
        help="Storage directory to back up (default: from configuration)",
    )
    parser.add_argument(
        "--max-backups",
        type=int,
        default=None,
        help="Maximum number of historical backups to retain.",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=None,
        help="Maximum age of backups in days.",
    )

    args = parser.parse_args()
    create_backup(
        destination_root=args.backup_dir,
        database_url=args.db_url,
        storage_dir=args.storage_dir,
        max_backups=args.max_backups,
        retention_days=args.retention_days,
    )


if __name__ == "__main__":
    main()
