"""
Controlled, safe, idempotent backfill script for Contractly contract financial values.
Preserves existing contracts, users, and audit data.
"""
import sys
import os
import sqlite3

# Ensure backend directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings, CANONICAL_DB_PATH
from app.services.intelligence.financial_extractor import extract_contract_financials


def run_backfill(db_path: str = None) -> int:
    if not db_path:
        # Normalize file path for SQLite connection
        db_path = CANONICAL_DB_PATH.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")

    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}. Skipping backfill.")
        return 0

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Verify / ensure columns exist
    cols = [r[1] for r in cur.execute("PRAGMA table_info(contracts)").fetchall()]
    if "value_basis" not in cols:
        cur.execute("ALTER TABLE contracts ADD COLUMN value_basis VARCHAR(50) DEFAULT 'NOT_SPECIFIED'")
    if "calculation_explanation" not in cols:
        cur.execute("ALTER TABLE contracts ADD COLUMN calculation_explanation TEXT DEFAULT NULL")
    conn.commit()

    rows = cur.execute("""
        SELECT c.id, c.contract_id, c.title, c.value, c.currency, c.start_date, c.expiry_date,
               (SELECT cv.raw_text FROM contract_versions cv WHERE cv.contract_id = c.id ORDER BY cv.created_at DESC LIMIT 1) as raw_text
        FROM contracts c
    """).fetchall()

    print(f"Found {len(rows)} contracts to evaluate in {db_path}...")
    updated_count = 0

    for row in rows:
        cid, code, title, val, curr, sdate, edate, text = row
        fin = extract_contract_financials(text or "", contract_start_date=sdate, contract_expiry_date=edate)

        if fin["is_verified"]:
            new_val = fin["value"]
            new_curr = fin["currency"]
            new_basis = fin["value_basis"]
            new_expl = fin["calculation_explanation"]
        elif val is not None and float(val) > 0:
            # Keep manual value
            new_val = float(val)
            new_curr = curr or "INR"
            new_basis = "MANUALLY_ENTERED"
            new_expl = f"Manual contract value of {new_curr} {new_val:,.0f}"
        else:
            # Unknown / unspecified
            new_val = None
            new_curr = curr or "INR"
            new_basis = "NOT_SPECIFIED"
            new_expl = "No committed monetary amount identified in agreement terms"

        cur.execute("""
            UPDATE contracts
            SET value = ?, currency = ?, value_basis = ?, calculation_explanation = ?
            WHERE id = ?
        """, (new_val, new_curr, new_basis, new_expl, cid))
        updated_count += 1
        print(f"  [{code}] {title[:32]}: value={new_val} {new_curr} ({new_basis})")

    conn.commit()
    conn.close()
    print(f"Successfully evaluated and backfilled {updated_count} contracts.")
    return updated_count


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    run_backfill(target)
