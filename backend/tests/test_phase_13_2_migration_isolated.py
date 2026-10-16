import os
import tempfile
import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic import command


def test_migration_0003_upgrade_and_downgrade_isolated():
    """
    Migration safety verification:
    Executes Alembic upgrade and downgrade exclusively against a newly created,
    isolated, disposable SQLite database in a temporary directory.
    Strictly isolates this test from canonical 'contractly.db' and Neon staging.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        disposable_db_path = os.path.join(temp_dir, "disposable_migration_test.db").replace("\\", "/")
        disposable_sync_url = f"sqlite:///{disposable_db_path}"
        disposable_async_url = f"sqlite+aiosqlite:///{disposable_db_path}"

        # 1. Prepare Alembic configuration pointing strictly to disposable DB
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        ini_path = os.path.join(backend_dir, "alembic.ini")

        alembic_cfg = Config(ini_path)
        alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
        # Force ALEMBIC_DATABASE_URL environment variable to take precedence in env.py
        orig_env_url = os.environ.get("ALEMBIC_DATABASE_URL")
        os.environ["ALEMBIC_DATABASE_URL"] = disposable_async_url

        try:
            # 2. Upgrade from base to head (through 0001, 0002, 0003)
            command.upgrade(alembic_cfg, "head")

            # 3. Inspect schema on disposable database
            engine = sa.create_engine(disposable_sync_url)
            inspector = sa.inspect(engine)
            tables = set(inspector.get_table_names())

            # Verify all 5 new tables exist in upgraded schema
            expected_new_tables = {
                "lawyer_profiles",
                "legal_matters",
                "matter_access_grants",
                "matter_messages",
                "lawyer_availability",
            }
            assert expected_new_tables.issubset(tables), f"Missing tables: {expected_new_tables - tables}"

            # Verify baseline tables still exist
            assert "organizations" in tables
            assert "users" in tables
            assert "contracts" in tables
            assert "account_tokens" in tables

            # Verify specific column details on legal_matters
            matter_cols = {c["name"] for c in inspector.get_columns("legal_matters")}
            assert "conflict_cleared" in matter_cols
            assert "conflict_cleared_at" in matter_cols
            assert "conflict_cleared_by_user_id" in matter_cols
            assert "client_consent_given" in matter_cols
            assert "client_consent_at" in matter_cols
            assert "client_consent_by_user_id" in matter_cols
            assert "status" in matter_cols

            # Verify specific column details on matter_messages
            msg_cols = {c["name"] for c in inspector.get_columns("matter_messages")}
            assert "is_internal_note" in msg_cols
            assert "attachments_json" in msg_cols

            # 4. Downgrade back to revision 0002_email_security_workflows
            command.downgrade(alembic_cfg, "0002_email_security_workflows")

            # 5. Inspect schema on downgraded database
            inspector_after = sa.inspect(engine)
            tables_after = set(inspector_after.get_table_names())

            # Verify all 5 new tables were cleanly dropped
            for table_name in expected_new_tables:
                assert table_name not in tables_after, f"Table '{table_name}' should have been dropped on downgrade"

            # Verify revision 0002 and 0001 tables are preserved
            assert "account_tokens" in tables_after
            assert "organization_invitations" in tables_after
            assert "organizations" in tables_after
            assert "contracts" in tables_after

            # 6. Re-upgrade to head to verify idempotency and bidirectional cleanliness
            command.upgrade(alembic_cfg, "0003_lawyer_matter_workflows")
            inspector_reup = sa.inspect(engine)
            tables_reup = set(inspector_reup.get_table_names())
            assert expected_new_tables.issubset(tables_reup)

            engine.dispose()

        finally:
            # Restore environment variable
            if orig_env_url is not None:
                os.environ["ALEMBIC_DATABASE_URL"] = orig_env_url
            else:
                os.environ.pop("ALEMBIC_DATABASE_URL", None)
