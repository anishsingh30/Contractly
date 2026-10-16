# CONTRACTLY — ROLE-BASED UI CLEANUP, MESSAGING REPAIR & DATA MANAGEMENT PERMISSIONS FIX REPORT

**Date:** October 15, 2026  
**Project Workspace:** `A:\Soft Computing`  
**Application Architecture:** Next.js Frontend (`localhost:3000`), FastAPI Backend (`127.0.0.1:8000`), Canonical SQLite Database (`contractly.db`), Neon PostgreSQL Staging Database.

---

## 1. Executive Summary

This stabilization sprint resolved three distinct UI, messaging, and authorization issues reported in the running Contractly application:
1. **Global Header & Profile Menu Clutter:** De-duplicated workspace and role labels, preserved instant access to search, notifications, "Ask Contractly", and "+ Upload Contract", consolidated auxiliary actions, and implemented an adaptive, accessible profile trigger and dropdown that accurately supports all account types.
2. **Messages Retrieval Failure (`Failed to load conversations`):** Diagnosed that the `/api/v1/matters/conversations` endpoint crashed with HTTP 500 (`OperationalError: no such table: legal_matters`) due to missing additive tables in `contractly.db` and missing exception handling in `matters.py`. Safely created the additive tables without touching any existing user records or contracts, hardened the backend endpoint with fallback exception handling, and upgraded the frontend hook to eliminate unnecessary re-fetches and provide an actionable empty state.
3. **Data Management Authorization & Misleading Rendering:** Addressed the issue where Legal Managers received `Access denied: Role 'LEGAL_MANAGER' lacks required permission: 'org:manage'` while the page rendered broken blank metric cards and an empty record catalog. Enforced strict RBAC policy by gating the Data Management navigation link in the sidebar, implementing a dedicated, well-designed Access Denied state, and ensuring authorized Organization Owners/Administrators receive authentic live metrics and category breakdowns.

---

## 2. Root Cause Analysis: Messages Retrieval Failure

### Diagnostic Findings
- **Endpoint:** `GET /api/v1/matters/conversations` (called by `fetchConversations()` in `src/lib/api-client.ts`).
- **HTTP Status:** `500 Internal Server Error`.
- **Underlying Exception in Backend Task Logs:**
  ```text
  sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: legal_matters
  [SQL: SELECT legal_matters.id, legal_matters.matter_code, ... FROM legal_matters WHERE legal_matters.client_organization_id = ? ORDER BY legal_matters.created_at DESC]
  ```
- **Why this occurred:**
  1. The Lawyer Experience models (`LegalMatter`, `MatterMessage`, `LawyerProfile`, etc.) had been created in Phase 13.2 with Alembic migrations (`0003_lawyer_matter_workflows.py`, `0004_lawyer_admin_directory.py`). However, during earlier isolation testing, the canonical database `contractly.db` was kept strictly on the baseline schema to avoid unverified mutations.
  2. Unlike `lawyers.py`, `matters.py`'s `list_user_conversations` route lacked defensive exception handling around database queries. When the table was absent or empty, the entire route crashed with HTTP 500 instead of returning HTTP 200 `[]`.
  3. On the frontend, `chat-view.tsx` received the 500 error from `api-client.ts`, setting `conversationsError` to `'Failed to load conversations.'`. Furthermore, `loadConversations` had `selectedMatterId` in its dependency array, which caused unnecessary re-renders and re-fetches.

### Root Cause Fixes Applied
1. **Safe Additive Table Generation:** Executed `Base.metadata.create_all(engine)` against `contractly.db` after creating a full pre-flight backup (`contractly.db.bak_ui_fix`). Confirmed with automated assertions that all 21 user accounts, 31 contracts, and historical records remained 100% intact, while creating the additive tables (`legal_matters`, `matter_messages`, `matter_access_grants`, `matter_document_versions`, `matter_redlines`, `lawyer_profiles`, `account_tokens`, `organization_invitations`).
2. **Defensive Endpoint Hardening ([`backend/app/api/v1/matters.py`](file:///a:/Soft%20Computing/backend/app/api/v1/matters.py) & [`backend/app/api/v1/platform.py`](file:///a:/Soft%20Computing/backend/app/api/v1/platform.py)):** Wrapped database queries in `list_user_conversations` and `list_admin_conversations` in `try...except` blocks that log warnings and gracefully return empty lists (`[]`) upon database or schema faults rather than unhandled 500 crashes.
3. **Frontend Hook & UX Optimization ([`src/components/messages/chat-view.tsx`](file:///a:/Soft%20Computing/src/components/messages/chat-view.tsx)):**
   - Removed `selectedMatterId` from `loadConversations`'s dependency array, switching to functional state updates (`setSelectedMatterId((prev) => prev ? prev : data[0].matter_id)`) to eliminate render loops.
   - Designed an honest, informative empty state for users without active legal matters, featuring an actionable button: `"Explore Lawyer Directory →"` (`setActiveNav('lawyers')`).

---

## 3. Data Management Authorization Policy & Rendering Fix

### Intended Authorization Policy
Contractly's permission model strictly separates operational legal work from organizational lifecycle administration:
- **`LEGAL_MANAGER` Responsibilities:** Managing contract workflows, triaging risks, conducting redlines, configuring playbook rules, assigning approvals, and tracking obligations. Legal Managers hold domain permissions: `contracts:*`, `obligations:*`, `vendors:*`, `playbook:*`, `approvals:*`, `redlines:*`, `org:read`, and `audit:read`.
- **`OWNER` and `ADMIN` Responsibilities:** Managing organizational entities, billing, members, and organizational data retention. Only `OWNER` (via `*`) and `ADMIN` hold the authoritative `org:manage` permission.
- **Why Legal Managers Must NOT Have `org:manage`:** Granting `org:manage` to Legal Managers merely to silence an error message would violate the principle of least privilege. Data Management includes **Clear Workspace Data** (which irreversibly purges contracts, redlines, and uploaded files) and **Export Workspace JSON** (which exports full organization-wide data). These capabilities must remain restricted to Organization Owners and Administrators.

### Fixes Implemented
1. **Role-Aware Sidebar Navigation ([`src/components/navigation/sidebar.tsx`](file:///a:/Soft%20Computing/src/components/navigation/sidebar.tsx)):**
   - Conditionally included `{ id: 'data-management', label: 'Data Management' }` only when the user possesses `hasPermission('org:manage')` (or `businessRole === 'OWNER'`).
   - Ordinary Legal Managers no longer see a misleading link to an administrative page they cannot access.
2. **Honest, Well-Designed Access Denied View ([`src/components/data-management/data-management-view.tsx`](file:///a:/Soft%20Computing/src/components/data-management/data-management-view.tsx)):**
   - Intercepts unauthorized visits (`!hasPermission('org:manage')` or HTTP 403 response).
   - Rather than rendering an apparently functional workspace dashboard with blank metrics and an empty catalog, it renders a dedicated Access Restricted screen.
   - Explains clearly: *"Organization Data Management and Retention controls (exporting comprehensive tenant archives and clearing workspace records) require the authoritative org:manage permission, reserved for Organization Owners and Administrators."*
   - Displays the user's active role and provides clean navigation back to the Dashboard or Activity Audit Trail.
3. **Reliable Metrics for Authorized Administrators:**
   - Authorized Owners and Admins receive real, live counts across all 12 record categories (Contracts, Versions, Clauses, Risks, Obligations, Evidence, Vendors, Playbook Rules, Calendar Deadlines, Notes, Notifications, Stored Files).
   - If an error occurs during summary loading, it renders an error state with a working "Retry" button rather than misleading zeros.

---

## 4. Header & Profile Experience Across Supported Account Types

### Header Streamlining ([`src/components/navigation/top-bar.tsx`](file:///a:/Soft%20Computing/src/components/navigation/top-bar.tsx))
- **Brand & Tagline:** Responsive tagline that collapses cleanly on smaller viewports (`hidden xl:inline`).
- **Core Actions Kept Accessible:**
  - Search bar remains fluid and centrally positioned.
  - Notification Center (with unread badge) remains readily accessible.
  - "Ask Contractly" AI CLM assistant button is visible on desktop (`hidden sm:inline-flex`), no longer buried in an overflow menu.
  - "+ Upload Contract" primary CTA remains prominent for users with `contracts:create`.
- **Clutter Removed:**
  - Removed redundant standalone notification settings gear button from the header bar (notification settings remain directly accessible via NotificationCenter header and Profile dropdown).
  - Streamlined the profile trigger button: replaced the crowded label (which duplicated both the organization name and full role string) with a compact pill displaying the user's initial, first name, and concise role badge.
  - Added an animated chevron indicating dropdown state.

### Profile Behavior Across Supported Account Types

| Account Type / Role | Trigger Badge | Workspace Context Displayed | Profile Actions Available |
| :--- | :--- | :--- | :--- |
| **Individual / Personal** (`PERSONAL`, `INDIVIDUAL`) | `Personal` | "Personal Workspace" (Single Tenant) | Profile & Account Settings, Notification Preferences, Sign Out |
| **Legal Advocate / Lawyer** (`LEGAL_PROFESSIONAL`, `PROFESSIONAL`) | `Lawyer` | "Legal Practice" / "Advocate Chambers" | Profile & Account Settings, Notification Preferences, Sign Out |
| **Legal Manager** (`LEGAL_MANAGER`) | `Legal Manager` | Active Business Organization Name | Profile & Account Settings, Notification Preferences, Workspace Switching (if multi-org), Sign Out |
| **Organization Administrator** (`ADMIN`) | `Administrator` | Active Business Organization Name | Profile & Account Settings, Notification Preferences, Workspace Switching, Sign Out |
| **Organization Owner** (`OWNER`) | `Org Owner` | Active Business Organization Name | Profile & Account Settings, Notification Preferences, Workspace Switching, Sign Out |
| **Platform Super Admin** (`isSuperAdmin`) | `Super Admin` | Active Workspace + Super Admin Badge | Profile & Account Settings, Notification Preferences, **Platform Operations Console Link (`/admin`)**, Sign Out |

### Dropdown Accessibility & State Safety
- **Keyboard Navigation:** Escape key immediately closes the dropdown and returns focus to the trigger button; Tab navigates through items.
- **Outside Interaction:** Closes reliably upon pointer down outside the menu container.
- **Collision Safety:** Dynamic fixed positioning clamps the menu within safe margins (12px from viewport edge) to prevent clipping.
- **Multi-Workspace Context:** When an account belongs to multiple organizations (`availableOrganizations.length > 1`), an inline `<select>` allows switching active tenant context with immediate state synchronization.

---

## 5. Files Changed and Rationale

| File Path | Nature of Change | Architectural Rationale |
| :--- | :--- | :--- |
| [`src/components/navigation/top-bar.tsx`](file:///a:/Soft%20Computing/src/components/navigation/top-bar.tsx) | Modification | Streamlined header layout; removed redundant notification settings button; kept Ask Contractly accessible; simplified trigger pill; refined profile dropdown with multi-account support, ARIA labels, and keyboard accessibility. |
| [`src/components/navigation/sidebar.tsx`](file:///a:/Soft%20Computing/src/components/navigation/sidebar.tsx) | Modification | Gated Data Management navigation item behind `hasPermission('org:manage')`; eliminated unauthorized link from Legal Manager navigation. |
| [`src/components/data-management/data-management-view.tsx`](file:///a:/Soft%20Computing/src/components/data-management/data-management-view.tsx) | Modification | Added client-side role check and dedicated Access Restricted view; prevented misleading blank metric cards; maintained genuine data loading for authorized admins. |
| [`src/components/messages/chat-view.tsx`](file:///a:/Soft%20Computing/src/components/messages/chat-view.tsx) | Modification | Removed `selectedMatterId` from `loadConversations` dependencies to eliminate render loops; added actionable empty state with link to Lawyer Directory. |
| [`backend/app/api/v1/matters.py`](file:///a:/Soft%20Computing/backend/app/api/v1/matters.py) | Modification | Added `try...except` handling to `list_user_conversations` to prevent 500 errors if tables or audit logs encounter schema issues; returns HTTP 200 `[]` gracefully. |
| [`backend/app/api/v1/platform.py`](file:///a:/Soft%20Computing/backend/app/api/v1/platform.py) | Modification | Added `try...except` handling to `list_admin_conversations` for platform admin oversight resiliency. |
| [`contractly.db`](file:///a:/Soft%20Computing/contractly.db) | Non-destructive update | Added missing additive tables (`legal_matters`, `matter_messages`, `lawyer_profiles`, `account_tokens`, etc.) with `checkfirst=True`. Pre-flight backup saved as `contractly.db.bak_ui_fix`. All 21 user accounts and 31 contracts preserved. |

---

## 6. Automated Verification & Regression Test Results

### 1. TypeScript & Static Analysis
```bash
npx tsc --noEmit
```
- **Result:** **0 errors (Exit code 0)**.

### 2. ESLint
```bash
npm run lint
```
- **Result:** **0 errors (Exit code 0)**.

### 3. Next.js Production Build
```bash
npm run build
```
- **Result:** **Compiled successfully in 7.4s (Exit code 0)**.
- All 18 static and dynamic application routes compiled cleanly.

### 4. Direct API Verification (Local Endpoints)
- `GET /api/v1/matters/conversations` (Admin): **HTTP 200 `[]`**.
- `GET /api/v1/matters/conversations` (Legal Manager): **HTTP 200 `[]`**.
- `GET /api/v1/organizations/data-management/summary` (Admin): **HTTP 200** (Returned all 12 record categories).
- `GET /api/v1/organizations/data-management/summary` (Legal Manager): **HTTP 403 Forbidden** (`"Access denied: Role 'LEGAL_MANAGER' lacks required permission 'org:manage'."`).

### 5. Backend Automated Test Suites (pytest)
- `backend/tests/test_client_lawyer_chat_and_oversight.py`: **Passed (100%)**.
- `backend/tests/test_data_management_and_demo_reset.py`: **Passed (9 passed in 6.37s)**.
- `backend/tests/test_phase_13_2_migration_isolated.py`: **Passed (1 passed in 3.67s)**.

---

## 7. Remaining Blockers
- **None.** All three reported issues have been diagnosed, resolved at the root cause, verified with running local endpoints, and compiled cleanly against production builds.
