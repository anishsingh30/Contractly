# Contractly Staging Deployment & Operations Runbook

**Workspace:** `A:\Soft Computing`  
**Purpose:** Operational guidance for provisioning, deploying, and maintaining the Contractly staging environment.

---

## 1. Staging Environment Architecture

The staging environment replicates production architecture in an isolated boundary:
- **Web & API Instances:** Containerized Next.js frontend and multi-worker FastAPI backend.
- **Relational Database:** Managed PostgreSQL (version 15 or 16) with connection pooling and SSL mode enforced. Never connect staging to canonical local databases.
- **Distributed Cache:** Managed Redis (version 7+) for atomic, cross-worker rate limiting and abuse prevention.
- **Document Object Store:** Dedicated AWS S3 bucket (`contractly-staging-documents`) with server-side encryption (`AES256` or AWS KMS) and 15-minute presigned download URLs.
- **Email Delivery:** SMTP relay (e.g. Amazon SES in sandbox mode or SendGrid) restricted to authorized test domain recipients.
- **AI Engine:** Google Gemini REST API (`gemini-flash-lite-latest`) with configured rate quotas and cost alert thresholds.

---

## 2. Infrastructure Requirements & Configuration

### 2.1 Staging PostgreSQL Database
1. Provision a dedicated PostgreSQL database instance (e.g., AWS RDS PostgreSQL or Supabase Staging).
2. Create an isolated application database `contractly_staging` and dedicated role:
   ```sql
   CREATE DATABASE contractly_staging;
   CREATE USER contractly_staging_user WITH ENCRYPTED PASSWORD '<generated-staging-password>';
   GRANT ALL PRIVILEGES ON DATABASE contractly_staging TO contractly_staging_user;
   ```
3. Execute Alembic migrations to apply canonical schema without manual SQL hacks:
   ```bash
   export ALEMBIC_DATABASE_URL="postgresql+asyncpg://contractly_staging_user:<password>@<staging-host>:5432/contractly_staging"
   alembic -c backend/alembic.ini upgrade head
   ```
4. Verify all 22 tables are present: `organizations`, `departments`, `users`, `organization_members`, `contracts`, `contract_versions`, `contract_clauses`, `contract_risks`, `contract_approval_steps`, `contract_redlines`, `refresh_tokens`, `account_tokens`, `organization_invitations`, `audit_logs`, `obligations`, `obligation_evidence`, `calendar_events`, `contract_notes`, `vendors`, `playbook_rules`, `notifications`, `user_notification_preferences`.

### 2.2 Staging Redis Cache
1. Provision a Redis cluster or standalone instance (e.g., AWS ElastiCache Redis or Redis Cloud).
2. Configure connection URL in `.env`:
   ```bash
   REDIS_URL="redis://:<password>@<redis-staging-host>:6379/0"
   REDIS_REQUIRED="true"
   ```
3. Test connectivity safely:
   ```bash
   redis-cli -h <redis-staging-host> -a <password> PING
   ```

### 2.3 Cloud Document Storage (S3)
1. Create a dedicated private bucket `contractly-staging-documents`.
2. Apply bucket security policy:
   - Block all public access: **Enabled**.
   - Server-side default encryption: **AES256**.
   - CORS policy allowing staging origin:
     ```json
     [
       {
         "AllowedHeaders": ["*"],
         "AllowedMethods": ["GET"],
         "AllowedOrigins": ["https://staging.contractly.internal"],
         "ExposeHeaders": ["ETag"],
         "MaxAgeSeconds": 3600
       }
     ]
     ```
3. Create an IAM policy granting least-privilege bucket access (`s3:GetObject`, `s3:PutObject`, `s3:ListBucket`).

### 2.4 Transactional Email Delivery
1. Set up an SMTP relay account with a verified staging subdomain (e.g. `staging.contractly.internal`).
2. Add DNS records on the staging subdomain:
   - **SPF:** `v=spf1 include:sendgrid.net ~all`
   - **DKIM:** Configured via CNAME records provided by the relay provider.
   - **DMARC:** `v=DMARC1; p=none; rua=mailto:dmarc-reports@staging.contractly.internal`
3. Restrict sending to an internal testing recipient list during initial staging verification.

### 2.5 Google Gemini API Configuration
1. Generate an API key in a dedicated Google Cloud staging project.
2. Configure API quotas:
   - Set maximum requests per minute cap (e.g. 60 RPM).
   - Set monthly budget alert at $50 USD to prevent runaway testing costs.
3. Verify that `GEMINI_API_KEY` is supplied only through server-side environment variables.

---

## 3. Secret Management and Rotation Policies

1. **Storage of Secrets:** Store staging credentials in a secure secrets manager (AWS Secrets Manager, HashiCorp Vault, or Doppler), injected as runtime environment variables. Never commit credentials to version control or paste into chat prompts.
2. **Key Lengths:**
   - `SECRET_KEY`: Minimum 32 random characters (generated via `openssl rand -hex 32`).
3. **Rotation Schedule:**
   - JWT Secret: Rotate every 90 days.
   - Database Passwords: Rotate every 180 days with zero-downtime dual-user rotation.
   - S3 IAM Credentials: Rotate every 90 days.
   - SMTP Credentials: Rotate every 180 days.

---

## 4. Health and Readiness Diagnostics

Contractly provides multi-layer diagnostic readiness checks that verify operational connectivity without exposing credentials or message contents:

1. **System Health Check (`GET /health`):**
   - Public endpoint reporting dependency health (`database`, `storage`, `ai`, `scheduler`, `email`, `rate_limiter`).
   - Returns HTTP 200 when database connectivity is healthy; returns HTTP 503 if database connectivity is unavailable.
2. **Platform Operational Health (`GET /api/v1/platform/health`):**
   - Protected endpoint requiring `PLATFORM_SUPER_ADMIN` or `PLATFORM_SUPPORT` authorization.
   - Details:
     - Relational database status and engine.
     - Document storage provider and tenant prefixing.
     - Autonomous scheduler status and execution interval.
     - Email service provider status and missing configuration flags.
     - Rate-limiter backend mode (`distributed` vs `degraded_in_memory_fallback`) and sanitized endpoint.

---

## 5. Rollback and Disaster Recovery Procedures

### 5.1 Database Rollback
If a staging migration introduces unexpected behavior:
1. Revert to previous Alembic revision:
   ```bash
   alembic -c backend/alembic.ini downgrade -1
   ```
2. Or restore from the most recent staging snapshot using the guarded restore utility:
   ```bash
   python backend/scripts/restore.py \
     --backup-path /var/backups/contractly/staging_backup_<timestamp> \
     --target-db postgresql://... \
     --confirm-target postgresql://...
   ```

### 5.2 Application Version Rollback
1. Re-tag the prior stable container image as `:staging`.
2. Redeploy the API and Next.js services.
3. Validate operational recovery via `GET /health`.
