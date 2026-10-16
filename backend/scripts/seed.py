import asyncio
import sys
import os

# Add parent directory to path so app modules import cleanly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.future import select
from app.core.database import AsyncSessionLocal, engine, Base
from app.core.security import get_password_hash
from app.models.organization import Organization, Department
from app.models.user import User, OrganizationMember
from app.models.contract import Contract, ContractVersion, ContractClause, ContractRisk
import app.models

async def seed_database():
    print("Initializing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Check if already seeded
        res = await db.execute(select(Organization).where(Organization.slug == "northstar-tech"))
        if res.scalar_one_or_none():
            print("Database already contains Northstar Technologies organization. Skipping seed.")
            return

        print("Seeding Northstar Technologies Pvt. Ltd. organization...")
        org = Organization(
            name="Northstar Technologies Pvt. Ltd.",
            slug="northstar-tech",
            account_type="BUSINESS",
            subscription_tier="ENTERPRISE",
            storage_quota_bytes=50 * 1024 * 1024 * 1024
        )
        db.add(org)
        await db.flush()

        # Seed Departments
        dept_names = ["Legal", "Procurement", "Finance", "HR", "Operations", "Engineering"]
        for d_name in dept_names:
            dept = Department(organization_id=org.id, name=d_name, budget_currency="INR")
            db.add(dept)

        # Seed Users
        legal_user = User(
            email="legal@northstar.internal",
            password_hash=get_password_hash("Password123!"),
            full_name="Aarav Mehta (Legal Manager)",
            is_active=True
        )
        db.add(legal_user)
        await db.flush()

        member = OrganizationMember(
            organization_id=org.id,
            user_id=legal_user.id,
            role="LEGAL_MANAGER",
            status="ACTIVE"
        )
        db.add(member)

        # Seed Baseline Contract 1: CloudStack MSA
        c1 = Contract(
            organization_id=org.id,
            contract_id="CTR-2026-0842",
            title="Vendor Master Services Agreement",
            contract_type="Master Services Agreement",
            counterparty="CloudStack Infrastructure Pvt. Ltd.",
            department="Procurement",
            owner="Priya Sundaram (Procurement Lead)",
            value=12000000.0,
            currency="INR",
            start_date="2026-01-15",
            expiry_date="2027-01-14",
            renewal_date="2026-11-15",
            auto_renew=True,
            status="ACTIVE",
            composite_risk_score=68,
            risk_level="HIGH",
            version="v2.1",
            governing_law="Jurisdiction of Courts in New Delhi, India",
            tags="Cloud Infrastructure, Critical Tier-1, Auto-Renew"
        )
        db.add(c1)
        await db.flush()

        # Clauses for C1
        cl1_1 = ContractClause(
            contract_id=c1.id,
            clause_title="Limitation of Liability",
            section_number="Section 11.2",
            original_text="Neither party shall be liable for consequential damages. Service Provider liability shall remain uncapped with respect to gross negligence and breach of confidentiality obligations.",
            plain_language="Vendor damages are limited to fees paid, except for data breaches or gross misconduct which remain uncapped.",
            why_it_matters="Protects Northstar from catastrophic damages arising from cloud vendor security failures.",
            potential_concern="Vendor proposed capping total liability at 1x annual fees.",
            suggested_action="Maintain super-cap of 3x annual fees for confidentiality claims.",
            risk_level="HIGH",
            category="Liability"
        )
        db.add(cl1_1)

        rk1_1 = ContractRisk(
            contract_id=c1.id,
            severity="HIGH",
            risk_title="Potential Liability Exposure",
            potential_impact="Proposed 1x cap limits recovery in major cloud security incidents.",
            remedy_recommendation="Negotiate 36-month super-cap for data privacy breaches.",
            status="OPEN"
        )
        db.add(rk1_1)

        # Seed Baseline Contract 2: Employment Agreement with Non-Compete
        c2 = Contract(
            organization_id=org.id,
            contract_id="CTR-2026-1102",
            title="Senior Engineering Leadership Employment Agreement",
            contract_type="Employment Agreement",
            counterparty="Ananya Sharma",
            department="HR",
            owner="Rahul Deshmukh (HR VP)",
            value=6500000.0,
            currency="INR",
            start_date="2026-11-01",
            expiry_date="2029-10-31",
            renewal_date="2029-08-01",
            auto_renew=False,
            status="UNDER_REVIEW",
            composite_risk_score=76,
            risk_level="HIGH",
            version="v1.1",
            governing_law="Laws of Karnataka, India",
            tags="Executive Hiring, Non-Compete, IP Assignment"
        )
        db.add(c2)
        await db.flush()

        cl2_1 = ContractClause(
            contract_id=c2.id,
            clause_title="Post-Termination Restrictive Covenants (Non-Compete)",
            section_number="Section 9.1",
            original_text="For a period of 24 months following termination of employment for any reason, Employee agrees not to directly or indirectly be employed by any enterprise operating in enterprise software worldwide.",
            plain_language="The candidate is forbidden from working in enterprise software globally for 2 years after leaving.",
            why_it_matters="Under Section 27 of the Indian Contract Act, post-termination non-compete covenants are void and legally unenforceable.",
            potential_concern="Causes severe candidate friction and is legally invalid in Indian courts.",
            suggested_action="Replace with enforceable 12-month non-solicitation of clients and staff with trade secret protections.",
            risk_level="CRITICAL",
            category="Non-Compete"
        )
        db.add(cl2_1)

        rk2_1 = ContractRisk(
            contract_id=c2.id,
            severity="CRITICAL",
            risk_title="Unenforceable Restraint of Trade",
            potential_impact="Section 27 invalidation leaves trade secret covenants vulnerable if challenged.",
            remedy_recommendation="Redline to enforceable non-solicitation clause.",
            status="OPEN"
        )
        db.add(rk2_1)

        await db.commit()
        print("Database successfully seeded with Northstar Technologies and baseline contracts!")

if __name__ == "__main__":
    asyncio.run(seed_database())
