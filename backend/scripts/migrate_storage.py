#!/usr/bin/env python3
"""
Contractly Storage Migration Tool
=================================
Safe, dry-run-first document migration utility to copy documents from local
filesystem storage to an S3-compatible object store or secondary target.

Strict Safety Rules:
- Defaults to --dry-run; requires --apply to copy any documents.
- Never deletes or modifies source documents.
- Never modifies canonical database records during migration or dry-run.
- Computes and verifies SHA-256 checksums at every step.
- Generates a resumable manifest JSON.
- Never prints confidential document contents or credentials.
"""

import argparse
import asyncio
import datetime
import hashlib
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

# Ensure backend directory is in python path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.models.contract import Contract, ContractVersion
from app.models.obligation import Obligation, ObligationEvidence
from app.services.storage.base import StorageError, StorageNotFoundError, compute_sha256
from app.services.storage.local import LocalStorageAdapter
from app.services.storage.s3 import S3StorageAdapter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("contractly.migrate_storage")


def calculate_file_sha256(filepath: str) -> Tuple[str, int]:
    """Calculates SHA-256 and byte size for a local file."""
    hasher = hashlib.sha256()
    size = 0
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
            size += len(chunk)
    return hasher.hexdigest(), size


async def inventory_database_documents(
    session: AsyncSession,
    tenant_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Inventories all document references from the database.
    Validates tenant and contract ownership.
    """
    items = []

    # 1. Contract Versions
    q_versions = select(
        ContractVersion.id,
        ContractVersion.contract_id,
        ContractVersion.file_storage_path,
        ContractVersion.filename,
        ContractVersion.sha256_checksum,
        ContractVersion.file_byte_size,
        Contract.organization_id.label("tenant_id"),
    ).join(Contract, ContractVersion.contract_id == Contract.id)
    if tenant_filter:
        q_versions = q_versions.where(Contract.organization_id == tenant_filter)
    
    res_versions = await session.execute(q_versions)
    for row in res_versions.all():
        items.append({
            "record_type": "contract_version",
            "record_id": row.id,
            "contract_id": row.contract_id,
            "tenant_id": row.tenant_id,
            "file_storage_path": row.file_storage_path,
            "filename": row.filename,
            "db_sha256": row.sha256_checksum,
            "db_byte_size": row.file_byte_size,
        })

    # 2. Obligation Evidence
    q_evidence = (
        select(
            ObligationEvidence.id,
            ObligationEvidence.file_storage_path,
            ObligationEvidence.file_name,
            Contract.id.label("contract_id"),
            Contract.organization_id.label("tenant_id"),
        )
        .join(Obligation, ObligationEvidence.obligation_id == Obligation.id)
        .join(Contract, Obligation.contract_id == Contract.id)
    )
    if tenant_filter:
        q_evidence = q_evidence.where(Contract.organization_id == tenant_filter)

    res_evidence = await session.execute(q_evidence)
    for row in res_evidence.all():
        items.append({
            "record_type": "obligation_evidence",
            "record_id": row.id,
            "contract_id": row.contract_id,
            "tenant_id": row.tenant_id,
            "file_storage_path": row.file_storage_path,
            "filename": row.file_name,
            "db_sha256": None,
            "db_byte_size": None,
        })

    return items


def scan_source_directory(source_dir: str) -> List[str]:
    """Scans the source directory and returns relative normalized file paths."""
    relative_paths = []
    if not os.path.exists(source_dir):
        return relative_paths

    for root, _, files in os.walk(source_dir):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, source_dir).replace("\\", "/")
            relative_paths.append(rel)
    return relative_paths


def load_manifest(manifest_path: str) -> Dict[str, Any]:
    """Loads existing manifest for resume capability."""
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Could not read existing manifest file %s: %s", manifest_path, e)
    return {
        "metadata": {
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "total_records": 0,
            "verified_count": 0,
            "failed_count": 0,
            "missing_count": 0,
            "dry_run_count": 0,
        },
        "records": {},
        "unreferenced_files": []
    }


def save_manifest(manifest_path: str, manifest: Dict[str, Any]) -> None:
    """Safely saves manifest JSON."""
    manifest["metadata"]["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    os.makedirs(os.path.dirname(os.path.abspath(manifest_path)), exist_ok=True)
    temp_path = f"{manifest_path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    os.replace(temp_path, manifest_path)


async def run_migration(
    apply_changes: bool,
    manifest_path: str,
    source_dir: Optional[str] = None,
    db_url: Optional[str] = None,
    tenant_filter: Optional[str] = None,
    verify_only: bool = False,
    target_provider: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Main migration logic.
    """
    source_dir = os.path.abspath(source_dir or settings.LOCAL_STORAGE_DIR)
    db_url = db_url or settings.DATABASE_URL
    mode = "APPLY" if apply_changes else "DRY-RUN"
    logger.info("=== CONTRACTLY STORAGE MIGRATION ===")
    logger.info("Mode: %s", mode)
    logger.info("Source directory: %s", source_dir)
    logger.info("Manifest file: %s", manifest_path)

    # Initialize target provider if apply
    if apply_changes and not target_provider:
        target_provider = S3StorageAdapter()

    # Load or initialize manifest
    manifest = load_manifest(manifest_path)
    records_manifest = manifest.setdefault("records", {})

    # Create isolated DB engine
    engine_kwargs = {}
    if db_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_async_engine(db_url, echo=False, **engine_kwargs)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as session:
            db_items = await inventory_database_documents(session, tenant_filter=tenant_filter)
    finally:
        await engine.dispose()

    logger.info("Found %d document references in database.", len(db_items))

    # Scan on-disk files
    on_disk_files = set(scan_source_directory(source_dir))
    logger.info("Found %d physical files in source directory.", len(on_disk_files))

    db_paths_seen = set()
    verified_count = 0
    failed_count = 0
    missing_count = 0
    dry_run_count = 0

    for item in db_items:
        record_key = f"{item['record_type']}:{item['record_id']}"
        rel_path = item["file_storage_path"].replace("\\", "/").strip().lstrip("/")
        db_paths_seen.add(rel_path)

        existing_entry = records_manifest.get(record_key, {})
        if existing_entry.get("status") == "VERIFIED" and not verify_only:
            logger.info("[SKIP] Record %s already verified in manifest.", record_key)
            verified_count += 1
            continue

        entry: Dict[str, Any] = {
            "record_type": item["record_type"],
            "record_id": item["record_id"],
            "contract_id": item["contract_id"],
            "tenant_id": item["tenant_id"],
            "relative_path": rel_path,
            "filename": item["filename"],
            "expected_db_sha256": item["db_sha256"],
            "expected_db_size": item["db_byte_size"],
            "source_sha256": None,
            "source_size": None,
            "destination_sha256": None,
            "status": "PENDING",
            "error_message": None,
        }

        # Validate tenant scoping: path must start with tenant_id/
        expected_prefix = item["tenant_id"] + "/"
        if not rel_path.startswith(expected_prefix):
            entry["status"] = "UNEXPECTED_PATH"
            entry["error_message"] = (
                f"Path '{rel_path}' does not conform to tenant prefix '{expected_prefix}'."
            )
            failed_count += 1
            records_manifest[record_key] = entry
            continue

        # Check physical existence on disk
        source_full_path = os.path.join(source_dir, rel_path)
        if not os.path.exists(source_full_path):
            entry["status"] = "MISSING_SOURCE"
            entry["error_message"] = f"File missing on disk at source: {rel_path}"
            missing_count += 1
            records_manifest[record_key] = entry
            continue

        # Compute source checksum
        try:
            src_sha256, src_size = calculate_file_sha256(source_full_path)
            entry["source_sha256"] = src_sha256
            entry["source_size"] = src_size

            # Verify checksum against DB if present
            if item["db_sha256"] and item["db_sha256"] != src_sha256:
                entry["status"] = "CHECKSUM_MISMATCH"
                entry["error_message"] = (
                    f"Source disk checksum {src_sha256[:8]}... does not match DB checksum {item['db_sha256'][:8]}..."
                )
                failed_count += 1
                records_manifest[record_key] = entry
                continue

        except Exception as e:
            entry["status"] = "FAILED"
            entry["error_message"] = f"Failed to compute source hash: {e}"
            failed_count += 1
            records_manifest[record_key] = entry
            continue

        # Mode: DRY RUN
        if not apply_changes and not verify_only:
            entry["status"] = "DRY_RUN_OK"
            dry_run_count += 1
            records_manifest[record_key] = entry
            continue

        # Mode: VERIFY-ONLY
        if verify_only:
            try:
                dest_exists = target_provider.file_exists(rel_path, tenant_id=item["tenant_id"])
                if not dest_exists:
                    entry["status"] = "FAILED"
                    entry["error_message"] = "Object does not exist at destination."
                    failed_count += 1
                else:
                    dest_bytes = target_provider.get_file(rel_path, tenant_id=item["tenant_id"])
                    dest_sha = compute_sha256(dest_bytes)
                    entry["destination_sha256"] = dest_sha
                    if dest_sha == src_sha256:
                        entry["status"] = "VERIFIED"
                        verified_count += 1
                    else:
                        entry["status"] = "CHECKSUM_MISMATCH"
                        entry["error_message"] = "Destination SHA-256 does not match source."
                        failed_count += 1
            except Exception as e:
                entry["status"] = "FAILED"
                entry["error_message"] = f"Verification failed: {e}"
                failed_count += 1
            records_manifest[record_key] = entry
            continue

        # Mode: APPLY (copy)
        try:
            with open(source_full_path, "rb") as f:
                content = f.read()

            target_provider.save_file(rel_path, content, tenant_id=item["tenant_id"])

            # Verify immediately after save
            dest_bytes = target_provider.get_file(rel_path, tenant_id=item["tenant_id"])
            dest_sha = compute_sha256(dest_bytes)
            entry["destination_sha256"] = dest_sha

            if dest_sha != src_sha256:
                entry["status"] = "CHECKSUM_MISMATCH"
                entry["error_message"] = "Destination copy checksum mismatch after upload."
                failed_count += 1
            else:
                entry["status"] = "VERIFIED"
                verified_count += 1
                logger.info("[COPIED & VERIFIED] %s (%d bytes)", rel_path, src_size)

        except Exception as e:
            entry["status"] = "FAILED"
            entry["error_message"] = f"Upload to destination failed: {e}"
            failed_count += 1
            logger.error("[ERROR] Failed copying %s: %s", rel_path, e)

        records_manifest[record_key] = entry

        # Save manifest after each item for resume safety
        save_manifest(manifest_path, manifest)

    # Detect unreferenced physical files
    unreferenced = sorted(list(on_disk_files - db_paths_seen))
    manifest["unreferenced_files"] = unreferenced
    if unreferenced:
        logger.warning(
            "Detected %d unreferenced physical files on disk not associated with active DB records.",
            len(unreferenced)
        )

    # Update summary metadata
    manifest["metadata"]["total_records"] = len(db_items)
    manifest["metadata"]["verified_count"] = verified_count
    manifest["metadata"]["failed_count"] = failed_count
    manifest["metadata"]["missing_count"] = missing_count
    manifest["metadata"]["dry_run_count"] = dry_run_count
    manifest["metadata"]["unreferenced_file_count"] = len(unreferenced)
    manifest["metadata"]["mode"] = mode

    save_manifest(manifest_path, manifest)

    logger.info("=== MIGRATION SUMMARY (%s) ===", mode)
    logger.info("Total Database Records: %d", len(db_items))
    logger.info("Dry-Run OK:            %d", dry_run_count)
    logger.info("Verified Copied:        %d", verified_count)
    logger.info("Missing Source Files:   %d", missing_count)
    logger.info("Failed / Mismatches:    %d", failed_count)
    logger.info("Unreferenced on Disk:   %d", len(unreferenced))
    logger.info("Manifest Written To:    %s", manifest_path)

    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="Contractly Safe Document Migration Tool (Dry-run by default)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute actual copying to destination. (Default is dry-run)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Simulate and validate migration without copying. (Default: True)",
    )
    parser.add_argument(
        "--manifest-path",
        type=str,
        default=None,
        help="Path to manifest JSON file. Defaults to migration_manifest_<timestamp>.json",
    )
    parser.add_argument(
        "--tenant-id",
        type=str,
        default=None,
        help="Filter migration to a specific tenant ID.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify destination files against manifest without re-copying.",
    )
    parser.add_argument(
        "--source-dir",
        type=str,
        default=None,
        help="Override source storage directory.",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="Override database URL.",
    )

    args = parser.parse_args()

    apply_flag = args.apply
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    manifest_path = args.manifest_path or os.path.join(
        BACKEND_DIR, f"storage_migration_manifest_{timestamp}.json"
    )

    asyncio.run(
        run_migration(
            apply_changes=apply_flag,
            manifest_path=manifest_path,
            source_dir=args.source_dir,
            db_url=args.db_url,
            tenant_filter=args.tenant_id,
            verify_only=args.verify_only,
        )
    )


if __name__ == "__main__":
    main()
