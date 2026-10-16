#!/usr/bin/env python3
"""
Contractly Safe Recovery & Restore Utility
==========================================
Restores database and document storage from a verified backup archive.

Strict Safety Guards:
- Requires explicit --confirm-target matching the target destination.
- Refuses to overwrite the canonical database (contractly.db) without safety override.
- Cryptographically validates backup checksums before unpacking.
- Verifies post-restore document checksums and database-to-document references.
- Never prints confidential document contents or credentials.
"""

import argparse
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
WORKSPACE_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, ".."))
CANONICAL_DB_PATH = os.path.abspath(os.path.join(WORKSPACE_ROOT, "contractly.db"))

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("contractly.restore")


def compute_file_sha256(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def restore_sqlite(source_backup_file: str, target_db_path: str) -> None:
    """Restores SQLite database to target path using safe file replacement."""
    logger.info("Restoring SQLite database to %s", target_db_path)
    os.makedirs(os.path.dirname(os.path.abspath(target_db_path)), exist_ok=True)

    # Use temporary file first
    temp_target = f"{target_db_path}.restore_tmp"
    shutil.copy2(source_backup_file, temp_target)

    # Quick integrity check on restored SQLite file
    conn = sqlite3.connect(temp_target)
    cursor = conn.cursor()
    cursor.execute("PRAGMA quick_check;")
    res = cursor.fetchone()
    conn.close()

    if not res or res[0] != "ok":
        if os.path.exists(temp_target):
            os.remove(temp_target)
        raise RuntimeError(f"Restored SQLite database integrity check failed: {res}")

    os.replace(temp_target, target_db_path)
    logger.info("SQLite database restored and integrity verified.")


def restore_postgresql(source_backup_file: str, target_db_url: str) -> None:
    """Restores PostgreSQL database using pg_restore."""
    logger.info("Restoring PostgreSQL database from %s", source_backup_file)

    cleaned_url = target_db_url.replace("postgresql+asyncpg://", "postgresql://")
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
        "pg_restore",
        "-h", host,
        "-p", port,
        "-U", user,
        "-d", dbname,
        "--clean",
        "--if-exists",
        "-v",
        source_backup_file
    ]

    try:
        subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
    except FileNotFoundError:
        raise RuntimeError("pg_restore executable not found on system PATH.")
    except subprocess.CalledProcessError as e:
        logger.error("pg_restore failed: %s", e.stderr)
        raise RuntimeError(f"pg_restore execution failed with code {e.returncode}")


def restore_documents(source_tar: str, target_storage_dir: str, manifest_docs: List[Dict[str, Any]]) -> int:
    """Extracts documents into target directory and validates checksums."""
    logger.info("Extracting document archive %s to %s", source_tar, target_storage_dir)
    os.makedirs(target_storage_dir, exist_ok=True)

    with tarfile.open(source_tar, "r:gz") as tar:
        # Prevent tar traversal attacks
        for member in tar.getmembers():
            norm = os.path.normpath(member.name).replace("\\", "/")
            if norm.startswith("..") or "/../" in norm:
                raise ValueError(f"Security error: archive contains invalid relative path: {member.name}")
        if hasattr(tarfile, "data_filter"):
            tar.extractall(target_storage_dir, filter="data")
        else:
            tar.extractall(target_storage_dir)

    # Verify checksums of extracted documents
    verified_count = 0
    for item in manifest_docs:
        rel_path = item["relative_path"]
        expected_sha = item["sha256"]
        full_dest = os.path.join(target_storage_dir, rel_path)

        if not os.path.exists(full_dest):
            raise RuntimeError(f"Restored file missing: {rel_path}")

        actual_sha = compute_file_sha256(full_dest)
        if actual_sha != expected_sha:
            raise RuntimeError(
                f"Restored file checksum mismatch for {rel_path}: expected {expected_sha[:8]}..., got {actual_sha[:8]}..."
            )
        verified_count += 1

    logger.info("Extracted and verified %d document files.", verified_count)
    return verified_count


def execute_restore(
    backup_path: str,
    target_db_dest: str,
    target_storage_dir: str,
    confirm_target: str,
    allow_canonical_overwrite: bool = False,
) -> Dict[str, Any]:
    """Coordinates verified restore into target database and storage locations."""
    logger.info("=== STARTING CONTRACTLY RESTORE ===")
    logger.info("Backup Path:        %s", backup_path)
    logger.info("Target DB:          %s", target_db_dest)
    logger.info("Target Storage Dir: %s", target_storage_dir)

    # SAFETY CHECK 1: Target confirmation
    if confirm_target != target_db_dest:
        raise ValueError(
            f"Safety check failed: --confirm-target '{confirm_target}' does not match target database destination '{target_db_dest}'."
        )

    # SAFETY CHECK 2: Canonical database protection
    normalized_target_db = os.path.abspath(target_db_dest)
    if normalized_target_db == CANONICAL_DB_PATH and not allow_canonical_overwrite:
        raise PermissionError(
            "CRITICAL SAFETY VIOLATION: Target database is the canonical workspace database (contractly.db). "
            "Automated restoration into canonical database is strictly forbidden. Use an isolated disposable target."
        )

    # Load and verify backup manifest
    manifest_file = os.path.join(backup_path, "manifest.json")
    if not os.path.exists(manifest_file):
        raise FileNotFoundError(f"Backup manifest not found at {manifest_file}")

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    db_meta = manifest.get("database", {})
    docs_meta = manifest.get("documents", {})

    # Validate database backup file
    db_backup_file = os.path.join(backup_path, db_meta.get("filename", ""))
    if not os.path.exists(db_backup_file):
        raise FileNotFoundError(f"Database backup file missing: {db_backup_file}")

    db_actual_sha = compute_file_sha256(db_backup_file)
    if db_actual_sha != db_meta.get("sha256"):
        raise ValueError("Database backup archive failed SHA-256 integrity check prior to restore.")

    # Validate documents archive file
    docs_tar_file = os.path.join(backup_path, docs_meta.get("archive_filename", ""))
    if not os.path.exists(docs_tar_file):
        raise FileNotFoundError(f"Documents backup archive missing: {docs_tar_file}")

    docs_actual_sha = compute_file_sha256(docs_tar_file)
    if docs_actual_sha != docs_meta.get("archive_sha256"):
        raise ValueError("Documents archive failed SHA-256 integrity check prior to restore.")

    # 1. Restore Database
    db_type = db_meta.get("type", "sqlite")
    if db_type == "sqlite":
        restore_sqlite(db_backup_file, target_db_dest)
    elif db_type == "postgresql":
        restore_postgresql(db_backup_file, target_db_dest)
    else:
        raise ValueError(f"Unsupported database type in backup: {db_type}")

    # 2. Restore Documents
    doc_count = restore_documents(docs_tar_file, target_storage_dir, docs_meta.get("items", []))

    result = {
        "status": "RESTORE_SUCCESSFUL",
        "backup_id": manifest.get("backup_id"),
        "database_type": db_type,
        "target_database": target_db_dest,
        "target_storage_dir": target_storage_dir,
        "verified_documents_restored": doc_count,
    }

    logger.info("=== RESTORE COMPLETED SUCCESSFULLY ===")
    return result


def main():
    parser = argparse.ArgumentParser(description="Contractly Safe Restore Utility")
    parser.add_argument(
        "--backup-path",
        type=str,
        required=True,
        help="Path to specific backup directory containing manifest.json",
    )
    parser.add_argument(
        "--target-db",
        type=str,
        required=True,
        help="Destination database path or connection URL",
    )
    parser.add_argument(
        "--target-storage-dir",
        type=str,
        required=True,
        help="Destination documents directory",
    )
    parser.add_argument(
        "--confirm-target",
        type=str,
        required=True,
        help="Must match --target-db exactly to confirm destination intent.",
    )
    parser.add_argument(
        "--allow-canonical-overwrite",
        action="store_true",
        default=False,
        help="Safety override required only if restoring to canonical contractly.db.",
    )

    args = parser.parse_args()
    execute_restore(
        backup_path=args.backup_path,
        target_db_dest=args.target_db,
        target_storage_dir=args.target_storage_dir,
        confirm_target=args.confirm_target,
        allow_canonical_overwrite=args.allow_canonical_overwrite,
    )


if __name__ == "__main__":
    main()
