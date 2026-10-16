import os
import shutil
import sqlite3
import tempfile
import pytest
from unittest.mock import MagicMock, patch
import botocore.exceptions
from botocore.stub import Stubber
import boto3

from app.config import Settings, settings
from app.services.storage.base import (
    StorageError,
    StorageNotFoundError,
    StoragePermissionError,
    compute_sha256,
)
from app.services.storage.local import LocalStorageAdapter
from app.services.storage.s3 import S3StorageAdapter
from app.services.storage import get_storage_provider, storage_client
from scripts.backup import create_backup, apply_retention_policy
from scripts.restore import execute_restore, CANONICAL_DB_PATH
from scripts.migrate_storage import run_migration


# ============================================================================
# 1. LOCAL STORAGE ADAPTER TESTS
# ============================================================================

def test_local_storage_crud_and_checksum(tmp_path):
    storage_dir = tmp_path / "uploads"
    adapter = LocalStorageAdapter(base_dir=str(storage_dir))
    tenant_id = "tenant-alpha-123"
    rel_path = f"{tenant_id}/CTR-001/v1.0/contract.pdf"
    content = b"PDF-1.4 SAMPLE CONTRACT DATA FOR TESTING"

    # Save
    saved_path = adapter.save_file(rel_path, content, tenant_id=tenant_id)
    assert os.path.exists(saved_path)
    assert adapter.file_exists(rel_path, tenant_id=tenant_id)

    # Get & Read
    read_bytes = adapter.get_file(rel_path, tenant_id=tenant_id)
    assert read_bytes == content
    assert adapter.read_file(rel_path, tenant_id=tenant_id) == content

    # Checksum
    expected_hash = compute_sha256(content)
    assert adapter.compute_sha256(content) == expected_hash

    # Delete
    assert adapter.delete_file(rel_path, tenant_id=tenant_id) is True
    assert adapter.file_exists(rel_path, tenant_id=tenant_id) is False
    assert adapter.delete_file(rel_path, tenant_id=tenant_id) is False


def test_local_storage_tenant_boundary_and_traversal(tmp_path):
    adapter = LocalStorageAdapter(base_dir=str(tmp_path))
    tenant_a = "tenant-a-111"
    tenant_b = "tenant-b-222"

    # Traversal attempt
    with pytest.raises(StoragePermissionError, match="directory traversal prohibited"):
        adapter._resolve_path("../../etc/passwd")

    with pytest.raises(StoragePermissionError, match="Cross-tenant storage access prohibited"):
        adapter.save_file(f"{tenant_a}/../sneaky.txt", b"evil", tenant_id=tenant_a)

    # Cross-tenant escape attempt
    with pytest.raises(StoragePermissionError, match="Cross-tenant storage access prohibited"):
        adapter._resolve_path(f"{tenant_b}/contract.pdf", expected_tenant_id=tenant_a)

    with pytest.raises(StoragePermissionError, match="Cross-tenant storage access prohibited"):
        adapter.get_file(f"{tenant_b}/contract.pdf", tenant_id=tenant_a)


def test_local_storage_missing_file_raises_storage_not_found(tmp_path):
    adapter = LocalStorageAdapter(base_dir=str(tmp_path))
    tenant_id = "tenant-xyz"
    with pytest.raises(StorageNotFoundError):
        adapter.get_file(f"{tenant_id}/non_existent.pdf", tenant_id=tenant_id)


# ============================================================================
# 2. S3 STORAGE ADAPTER TESTS (STUBBED / MOCKED)
# ============================================================================

def test_s3_storage_upload_and_download_stubbed():
    boto_client = boto3.client("s3", region_name="us-east-1")
    stubber = Stubber(boto_client)

    adapter = S3StorageAdapter(
        bucket_name="test-contractly-bucket",
        region_name="us-east-1",
        sse_algorithm="AES256",
        boto3_client=boto_client,
    )

    tenant_id = "tenant-100"
    rel_path = f"{tenant_id}/CTR-002/v1.0/agreement.pdf"
    content = b"S3 TEST AGREEMENT CONTENT"
    content_hash = compute_sha256(content)

    # 1. Stub put_object
    expected_put_params = {
        "Bucket": "test-contractly-bucket",
        "Key": rel_path,
        "Body": content,
        "ServerSideEncryption": "AES256",
        "Metadata": {
            "sha256": content_hash,
            "size": str(len(content)),
        },
    }
    stubber.add_response("put_object", {}, expected_put_params)

    # 2. Stub get_object
    from io import BytesIO
    body_stream = BytesIO(content)
    expected_get_params = {
        "Bucket": "test-contractly-bucket",
        "Key": rel_path,
    }
    stubber.add_response("get_object", {"Body": body_stream}, expected_get_params)

    # 3. Stub head_object
    stubber.add_response("head_object", {"ContentLength": len(content)}, {"Bucket": "test-contractly-bucket", "Key": rel_path})

    # 4. Stub delete_object
    stubber.add_response("delete_object", {}, {"Bucket": "test-contractly-bucket", "Key": rel_path})

    stubber.activate()
    try:
        # Save
        key = adapter.save_file(rel_path, content, tenant_id=tenant_id)
        assert key == rel_path

        # Get
        retrieved = adapter.get_file(rel_path, tenant_id=tenant_id)
        assert retrieved == content

        # Exists
        assert adapter.file_exists(rel_path, tenant_id=tenant_id) is True

        # Delete
        assert adapter.delete_file(rel_path, tenant_id=tenant_id) is True

        stubber.assert_no_pending_responses()
    finally:
        stubber.deactivate()


def test_s3_storage_missing_key_raises_storage_not_found():
    boto_client = boto3.client("s3", region_name="us-east-1")
    stubber = Stubber(boto_client)

    adapter = S3StorageAdapter(
        bucket_name="test-contractly-bucket",
        boto3_client=boto_client,
    )

    tenant_id = "tenant-100"
    rel_path = f"{tenant_id}/CTR-002/v1.0/missing.pdf"

    stubber.add_client_error(
        "get_object",
        service_error_code="NoSuchKey",
        service_message="The specified key does not exist.",
        expected_params={"Bucket": "test-contractly-bucket", "Key": rel_path},
    )

    stubber.activate()
    try:
        with pytest.raises(StorageNotFoundError, match="Storage object not found"):
            adapter.get_file(rel_path, tenant_id=tenant_id)
    finally:
        stubber.deactivate()


def test_s3_storage_network_error_raises_storage_error_without_silent_local_fallback():
    boto_client = boto3.client("s3", region_name="us-east-1")
    stubber = Stubber(boto_client)

    adapter = S3StorageAdapter(
        bucket_name="test-contractly-bucket",
        boto3_client=boto_client,
    )

    tenant_id = "tenant-100"
    rel_path = f"{tenant_id}/CTR-002/v1.0/contract.pdf"

    # Simulate network timeout or service unavailable error
    stubber.add_client_error(
        "put_object",
        service_error_code="ServiceUnavailable",
        service_message="Service is temporarily unavailable.",
    )

    stubber.activate()
    try:
        # Must raise StorageError and NEVER fall back to local disk
        with pytest.raises(StorageError) as exc_info:
            adapter.save_file(rel_path, b"content", tenant_id=tenant_id)
        assert "ServiceUnavailable" in str(exc_info.value) or "ClientError" in str(exc_info.value)
    finally:
        stubber.deactivate()


def test_s3_storage_tenant_boundary_and_traversal():
    adapter = S3StorageAdapter(bucket_name="test-bucket")
    tenant_a = "tenant-a"
    tenant_b = "tenant-b"

    # Empty path
    with pytest.raises(StoragePermissionError):
        adapter._resolve_key("", expected_tenant_id=tenant_a)

    # Traversal attempt
    with pytest.raises(StoragePermissionError, match="directory traversal prohibited"):
        adapter._resolve_key(f"{tenant_a}/../secrets.env", expected_tenant_id=tenant_a)

    with pytest.raises(StoragePermissionError, match="directory traversal prohibited"):
        adapter._resolve_key(f"{tenant_a}/./contract.pdf", expected_tenant_id=tenant_a)

    # Cross-tenant escape attempt
    with pytest.raises(StoragePermissionError, match="Cross-tenant storage access prohibited"):
        adapter._resolve_key(f"{tenant_b}/contract.pdf", expected_tenant_id=tenant_a)


def test_s3_presigned_download_url():
    mock_boto = MagicMock()
    mock_boto.generate_presigned_url.return_value = "https://s3.amazonaws.com/test-bucket/url?signature=mocked"

    adapter = S3StorageAdapter(
        bucket_name="test-bucket",
        boto3_client=mock_boto,
        presigned_expiration_seconds=600,
    )

    tenant_id = "tenant-alpha"
    rel_path = f"{tenant_id}/contracts/v1.pdf"
    url = adapter.get_download_url(rel_path, tenant_id=tenant_id, expires_in=300)

    assert url == "https://s3.amazonaws.com/test-bucket/url?signature=mocked"
    mock_boto.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "test-bucket", "Key": rel_path},
        ExpiresIn=300,
    )


# ============================================================================
# 3. STORAGE FACTORY AND RUNTIME SWITCHING
# ============================================================================

def test_storage_factory_selection():
    local_cfg = Settings(STORAGE_PROVIDER="local")
    local_prov = get_storage_provider(local_cfg)
    assert isinstance(local_prov, LocalStorageAdapter)

    s3_cfg = Settings(STORAGE_PROVIDER="s3", S3_BUCKET_NAME="my-contracts-bucket")
    s3_prov = get_storage_provider(s3_cfg)
    assert isinstance(s3_prov, S3StorageAdapter)
    assert s3_prov.bucket_name == "my-contracts-bucket"


def test_storage_client_proxy_delegation(tmp_path):
    # Test that storage_client proxy responds dynamically to active provider
    test_adapter = LocalStorageAdapter(base_dir=str(tmp_path))
    with patch("app.services.storage.get_storage_provider", return_value=test_adapter):
        tenant_id = "proxy-tenant"
        rel_path = f"{tenant_id}/test.txt"
        saved = storage_client.save_file(rel_path, b"proxy data", tenant_id=tenant_id)
        assert os.path.exists(saved)
        assert storage_client.get_file(rel_path, tenant_id=tenant_id) == b"proxy data"


# ============================================================================
# 4. MIGRATION TOOL TESTS (DRY-RUN, APPLY, CHECKSUMS)
# ============================================================================

@pytest.mark.asyncio
async def test_migration_dry_run_and_apply(tmp_path):
    # 1. Setup synthetic source directory with documents
    source_dir = tmp_path / "source_uploads"
    tenant_id = "tenant-mig-1"
    contract_dir = source_dir / tenant_id / "CTR-TEST" / "v1.0"
    contract_dir.mkdir(parents=True)
    doc_content = b"SYNTHETIC DOCUMENT FOR MIGRATION TESTING"
    doc_file = contract_dir / "agreement.pdf"
    doc_file.write_bytes(doc_content)
    doc_sha = compute_sha256(doc_content)
    rel_path = f"{tenant_id}/CTR-TEST/v1.0/agreement.pdf"

    # 2. Setup synthetic SQLite test DB with matching record
    test_db_path = str(tmp_path / "synthetic_test.db")
    test_db_url = f"sqlite+aiosqlite:///{test_db_path.replace('\\', '/')}"

    conn = sqlite3.connect(test_db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE contracts (
            id VARCHAR(36) PRIMARY KEY,
            organization_id VARCHAR(36) NOT NULL,
            title VARCHAR(255)
        );
    """)
    cur.execute("""
        CREATE TABLE contract_versions (
            id VARCHAR(36) PRIMARY KEY,
            contract_id VARCHAR(36) NOT NULL,
            version_number VARCHAR(20) NOT NULL,
            filename VARCHAR(255),
            file_storage_path VARCHAR(500) NOT NULL,
            file_mime_type VARCHAR(100) NOT NULL,
            file_byte_size INTEGER NOT NULL,
            sha256_checksum VARCHAR(64) NOT NULL
        );
    """)
    cur.execute("""
        CREATE TABLE obligations (id VARCHAR(36) PRIMARY KEY, contract_id VARCHAR(36) NOT NULL);
    """)
    cur.execute("""
        CREATE TABLE obligation_evidence (
            id VARCHAR(36) PRIMARY KEY,
            obligation_id VARCHAR(36) NOT NULL,
            file_name VARCHAR(255) NOT NULL,
            file_storage_path VARCHAR(500) NOT NULL
        );
    """)

    cur.execute("INSERT INTO contracts (id, organization_id, title) VALUES ('c1', 'tenant-mig-1', 'Test Contract');")
    cur.execute(f"""
        INSERT INTO contract_versions (id, contract_id, version_number, filename, file_storage_path, file_mime_type, file_byte_size, sha256_checksum)
        VALUES ('v1', 'c1', 'v1.0', 'agreement.pdf', '{rel_path}', 'application/pdf', {len(doc_content)}, '{doc_sha}');
    """)
    conn.commit()
    conn.close()

    manifest_dry = str(tmp_path / "manifest_dry.json")

    # TEST DRY-RUN
    manifest_res = await run_migration(
        apply_changes=False,
        manifest_path=manifest_dry,
        source_dir=str(source_dir),
        db_url=test_db_url,
    )
    assert manifest_res["metadata"]["dry_run_count"] == 1
    assert manifest_res["metadata"]["verified_count"] == 0
    assert manifest_res["metadata"]["missing_count"] == 0
    assert manifest_res["records"]["contract_version:v1"]["status"] == "DRY_RUN_OK"
    assert manifest_res["records"]["contract_version:v1"]["source_sha256"] == doc_sha

    # TEST APPLY with synthetic target provider
    target_storage_dir = tmp_path / "target_uploads"
    target_adapter = LocalStorageAdapter(base_dir=str(target_storage_dir))
    manifest_apply = str(tmp_path / "manifest_apply.json")

    apply_res = await run_migration(
        apply_changes=True,
        manifest_path=manifest_apply,
        source_dir=str(source_dir),
        db_url=test_db_url,
        target_provider=target_adapter,
    )
    assert apply_res["metadata"]["verified_count"] == 1
    assert apply_res["metadata"]["failed_count"] == 0
    assert apply_res["records"]["contract_version:v1"]["status"] == "VERIFIED"
    assert target_adapter.file_exists(rel_path, tenant_id=tenant_id)
    assert target_adapter.get_file(rel_path, tenant_id=tenant_id) == doc_content

    # Original source file must NOT be deleted
    assert doc_file.exists()


@pytest.mark.asyncio
async def test_migration_detects_missing_file_and_checksum_mismatch(tmp_path):
    test_db_path = str(tmp_path / "synthetic_test_err.db")
    test_db_url = f"sqlite+aiosqlite:///{test_db_path.replace('\\', '/')}"

    conn = sqlite3.connect(test_db_path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE contracts (id VARCHAR(36) PRIMARY KEY, organization_id VARCHAR(36) NOT NULL);")
    cur.execute("""
        CREATE TABLE contract_versions (
            id VARCHAR(36) PRIMARY KEY,
            contract_id VARCHAR(36) NOT NULL,
            file_storage_path VARCHAR(500) NOT NULL,
            filename VARCHAR(255),
            file_byte_size INTEGER,
            sha256_checksum VARCHAR(64)
        );
    """)
    cur.execute("CREATE TABLE obligations (id VARCHAR(36) PRIMARY KEY, contract_id VARCHAR(36) NOT NULL);")
    cur.execute("CREATE TABLE obligation_evidence (id VARCHAR(36) PRIMARY KEY, obligation_id VARCHAR(36), file_name VARCHAR(255), file_storage_path VARCHAR(500));")

    cur.execute("INSERT INTO contracts VALUES ('c1', 'tenant-err');")
    # v1: Missing from disk
    cur.execute("INSERT INTO contract_versions VALUES ('v1', 'c1', 'tenant-err/missing.pdf', 'missing.pdf', 10, 'abc');")
    # v2: Checksum mismatch
    cur.execute("INSERT INTO contract_versions VALUES ('v2', 'c1', 'tenant-err/mismatch.pdf', 'mismatch.pdf', 10, '0000000000000000000000000000000000000000000000000000000000000000');")
    conn.commit()
    conn.close()

    source_dir = tmp_path / "source_err"
    source_dir.mkdir()
    tenant_dir = source_dir / "tenant-err"
    tenant_dir.mkdir()
    # Create mismatch file with different content
    (tenant_dir / "mismatch.pdf").write_bytes(b"ACTUAL FILE CONTENT")

    manifest_path = str(tmp_path / "manifest_err.json")
    res = await run_migration(
        apply_changes=False,
        manifest_path=manifest_path,
        source_dir=str(source_dir),
        db_url=test_db_url,
    )

    assert res["records"]["contract_version:v1"]["status"] == "MISSING_SOURCE"
    assert res["records"]["contract_version:v2"]["status"] == "CHECKSUM_MISMATCH"
    assert res["metadata"]["missing_count"] == 1
    assert res["metadata"]["failed_count"] == 1


# ============================================================================
# 5. BACKUP AND RESTORE TESTS (DISPOSABLE SYNTHETIC TARGETS)
# ============================================================================

def test_backup_and_restore_cycle_disposable_target(tmp_path):
    # 1. Create synthetic database
    source_db_file = tmp_path / "source_db.sqlite3"
    conn = sqlite3.connect(str(source_db_file))
    cur = conn.cursor()
    cur.execute("CREATE TABLE test_data (id INTEGER PRIMARY KEY, note TEXT);")
    cur.execute("INSERT INTO test_data (id, note) VALUES (1, 'Important record');")
    conn.commit()
    conn.close()

    # 2. Create synthetic documents
    source_docs_dir = tmp_path / "source_docs"
    tenant_dir = source_docs_dir / "tenant-test"
    tenant_dir.mkdir(parents=True)
    (tenant_dir / "sample.pdf").write_bytes(b"AUTHENTIC DOCUMENT CONTENT")

    # 3. Create Backup
    backup_root = tmp_path / "backups"
    backup_manifest = create_backup(
        destination_root=str(backup_root),
        database_url=f"sqlite:///{str(source_db_file).replace('\\', '/')}",
        storage_dir=str(source_docs_dir),
    )

    assert backup_manifest["database"]["type"] == "sqlite"
    assert backup_manifest["documents"]["document_count"] == 1
    backup_id = backup_manifest["backup_id"]
    backup_folder = backup_root / backup_id

    # 4. Restore into disposable targets
    target_restored_db = tmp_path / "restored_disposable.sqlite3"
    target_restored_storage = tmp_path / "restored_storage"

    restore_res = execute_restore(
        backup_path=str(backup_folder),
        target_db_dest=str(target_restored_db),
        target_storage_dir=str(target_restored_storage),
        confirm_target=str(target_restored_db),
    )

    assert restore_res["status"] == "RESTORE_SUCCESSFUL"
    assert restore_res["verified_documents_restored"] == 1

    # Verify restored SQLite data
    r_conn = sqlite3.connect(str(target_restored_db))
    r_cur = r_conn.cursor()
    r_cur.execute("SELECT note FROM test_data WHERE id=1;")
    assert r_cur.fetchone()[0] == "Important record"
    r_conn.close()

    # Verify restored document
    restored_doc = target_restored_storage / "tenant-test" / "sample.pdf"
    assert restored_doc.exists()
    assert restored_doc.read_bytes() == b"AUTHENTIC DOCUMENT CONTENT"


def test_restore_confirmation_guard_and_canonical_db_protection(tmp_path):
    backup_folder = tmp_path / "mock_backup"
    backup_folder.mkdir()

    # Confirmation guard failure
    with pytest.raises(ValueError, match="Safety check failed: --confirm-target"):
        execute_restore(
            backup_path=str(backup_folder),
            target_db_dest=str(tmp_path / "db.sqlite3"),
            target_storage_dir=str(tmp_path / "storage"),
            confirm_target="wrong_confirmation_string",
        )

    # Canonical database protection
    with pytest.raises(PermissionError, match="CRITICAL SAFETY VIOLATION"):
        execute_restore(
            backup_path=str(backup_folder),
            target_db_dest=CANONICAL_DB_PATH,
            target_storage_dir=str(tmp_path / "storage"),
            confirm_target=CANONICAL_DB_PATH,
            allow_canonical_overwrite=False,
        )


def test_backup_retention_policy(tmp_path):
    backups_dir = tmp_path / "retention_test"
    backups_dir.mkdir()

    # Create 4 dummy backup directories
    for i in range(4):
        bdir = backups_dir / f"backup_2026101{i}_000000"
        bdir.mkdir()

    # Apply max_backups = 2
    removed = apply_retention_policy(str(backups_dir), max_backups=2, retention_days=None)
    assert removed == 2
    remaining = [d for d in os.listdir(str(backups_dir)) if d.startswith("backup_")]
    assert len(remaining) == 2


# ============================================================================
# 6. STARTUP CONFIGURATION AND PREVENTION OF AUTO-MIGRATION
# ============================================================================

def test_startup_prevents_automatic_migration_and_defaults_to_local():
    # Storage provider default must be "local"
    assert settings.STORAGE_PROVIDER == "local"

    # Verify that importing app.main does not trigger any document migration
    with patch("scripts.migrate_storage.run_migration") as mock_migrate:
        import app.main  # noqa: F401
        mock_migrate.assert_not_called()


def test_s3_storage_requires_bucket_name_configuration():
    adapter = S3StorageAdapter(bucket_name="")
    with pytest.raises(StorageError, match="S3_BUCKET_NAME is required"):
        adapter.save_file("tenant-1/file.pdf", b"data", tenant_id="tenant-1")

