import React from 'react';
import Link from 'next/link';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Privacy Policy — Contractly Legal Operations',
  description: 'Verified data handling, storage isolation, AI processing boundaries, and privacy disclosures for the Contractly platform.',
};

export default function PrivacyPolicyPage() {
  return (
    <div className="bg-[#F7F3EA] text-[#242321] min-h-screen selection:bg-[#3F4634] selection:text-[#FCFAF5]">
      {/* Header */}
      <header className="h-16 border-b border-[#DED6C8] px-6 lg:px-12 flex items-center justify-between bg-[#F7F3EA]/90 sticky top-0 z-40 backdrop-blur-sm">
        <div className="flex items-center gap-4">
          <Link href="/" className="font-serif tracking-widest text-lg font-bold text-[#242321]">
            CONTRACTLY
          </Link>
          <span className="text-xs font-mono text-[#6F6A61] border-l border-[#DED6C8] pl-4">
            Legal & Privacy Architecture
          </span>
        </div>
        <Link
          href="/"
          className="text-xs font-medium text-[#3F4634] hover:underline"
        >
          ← Return to Contractly
        </Link>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-6 py-12 lg:py-16 space-y-10">
        <div className="space-y-3 border-b border-[#DED6C8] pb-6">
          <span className="font-mono text-[11px] uppercase tracking-wider text-[#3F4634] font-bold">
            Policy Disclosure • Version 1.0 (October 2026)
          </span>
          <h1 className="text-3xl sm:text-4xl font-serif font-bold text-[#242321]">
            Privacy Policy & Data Handling
          </h1>
          <p className="text-xs sm:text-sm text-[#6F6A61] leading-relaxed">
            This policy outlines how the Contractly Legal Operations Platform collects, processes, isolates, and retains data within active multi-tenant environments.
          </p>
        </div>

        <section className="space-y-4 text-xs sm:text-sm leading-relaxed text-[#242321]">
          <h2 className="text-lg font-serif font-bold text-[#242321] border-b border-[#DED6C8] pb-1">
            1. Multi-Tenant Architecture & Data Isolation
          </h2>
          <p>
            Contractly is architected around strict organizational tenant isolation. Every contract, version, clause, risk extraction, calendar reminder, obligation record, and redline is assigned an immutable <code>organization_id</code> foreign key.
          </p>
          <p className="text-[#6F6A61]">
            Database queries and file system access require authenticated tenant authorization. Users belonging to Organization A cannot view, query, modify, or download agreements, obligation evidence, or audit records belonging to Organization B.
          </p>
        </section>

        <section className="space-y-4 text-xs sm:text-sm leading-relaxed text-[#242321]">
          <h2 className="text-lg font-serif font-bold text-[#242321] border-b border-[#DED6C8] pb-1">
            2. Ingested Documents & Extracted Metadata
          </h2>
          <p>
            When you upload documents (PDF, DOCX, TXT) to Contractly:
          </p>
          <ul className="list-disc pl-5 space-y-1.5 text-[#6F6A61]">
            <li>Documents are stored in tenant-segregated directories within local storage or customer-configured storage volumes.</li>
            <li>Deterministic parsers extract text solely to identify contract parties, effective dates, renewal milestones, payment terms, and risk candidates.</li>
            <li>SHA-256 cryptographic checksums are computed upon upload to ensure version integrity and detect tampering.</li>
          </ul>
        </section>

        <section className="space-y-4 text-xs sm:text-sm leading-relaxed text-[#242321]">
          <h2 className="text-lg font-serif font-bold text-[#242321] border-b border-[#DED6C8] pb-1">
            3. AI Provider Processing & Confidentiality
          </h2>
          <p>
            Contractly integrates with upstream Large Language Model providers (Google Gemini API) to perform natural language contract Q&amp;A and general legal education:
          </p>
          <ul className="list-disc pl-5 space-y-1.5 text-[#6F6A61]">
            <li><strong>Zero Training on Customer Contracts:</strong> Requests dispatched to the API provider use commercial API agreements configured to not use customer prompts or document excerpts to train foundational models.</li>
            <li><strong>Minimal Context Retrieval:</strong> The Contract Q&amp;A service does not transmit your entire contract indiscriminately; it queries retrieved database clauses matching the user&apos;s specific inquiry.</li>
            <li><strong>Server-Side Credentials:</strong> All provider credentials remain strictly within server-side environments and are never exposed to browser clients.</li>
          </ul>
        </section>

        <section className="space-y-4 text-xs sm:text-sm leading-relaxed text-[#242321]">
          <h2 className="text-lg font-serif font-bold text-[#242321] border-b border-[#DED6C8] pb-1">
            4. Platform Administration &amp; Customer Content Isolation
          </h2>
          <p>
            Contractly enforces a strict separation between customer tenant workspaces and platform operational administration:
          </p>
          <ul className="list-disc pl-5 space-y-1.5 text-[#6F6A61]">
            <li><strong>No Routine Contract Content Access:</strong> Platform administrators manage system uptime, service health, storage quotas, and aggregate metrics. Platform console routes do not provide universal contract inspection or raw document download capabilities.</li>
            <li><strong>Exceptional Support Access Disabled by Default:</strong> Personnel cannot access customer contract documents under routine support tickets. Any emergency or exceptional content access requires explicit prior customer organization Owner consent, narrowly scoped justification, and hard time-bound expiration.</li>
            <li><strong>Audited Privileged Actions:</strong> All platform-level administrative inquiries and operational checks are recorded in a tamper-evident administrative audit log.</li>
          </ul>
        </section>

        <section className="space-y-4 text-xs sm:text-sm leading-relaxed text-[#242321]">
          <h2 className="text-lg font-serif font-bold text-[#242321] border-b border-[#DED6C8] pb-1">
            5. Immutable Audit Logging
          </h2>
          <p>
            To support compliance and operational accountability, Contractly records administrative and lifecycle activities in an organization-scoped audit log. Recorded fields include timestamp, acting user email, action identifier, object type, and operational details. Audit records are read-only and restricted to authorized tenant administrators.
          </p>
        </section>

        <section className="space-y-4 text-xs sm:text-sm leading-relaxed text-[#242321]">
          <h2 className="text-lg font-serif font-bold text-[#242321] border-b border-[#DED6C8] pb-1">
            6. Data Retention, Backups &amp; Account Closure
          </h2>
          <p>
            Customer contract documents, versions, and metadata remain associated with your organization until deleted by an authorized administrator or upon account termination:
          </p>
          <ul className="list-disc pl-5 space-y-1.5 text-[#6F6A61]">
            <li><strong>Encrypted Backups:</strong> Point-in-time disaster recovery snapshots are encrypted and retained pursuant to configurable retention schedules (e.g. 14–30 days) before automated cryptographic purging.</li>
            <li><strong>Infrastructure Limitations:</strong> While application-level access controls prevent unauthorized access across tenants and by platform administrators, users should understand that personnel with physical infrastructure or database storage control may possess theoretical hardware-level access; hence, Contractly maintains defense-in-depth with server-side encryption and strict access logging.</li>
          </ul>
        </section>

        <section className="space-y-4 text-xs sm:text-sm leading-relaxed text-[#242321]">
          <h2 className="text-lg font-serif font-bold text-[#242321] border-b border-[#DED6C8] pb-1">
            7. Notification &amp; Email Transports
          </h2>
          <p>
            Transactional notifications and calendar notices are dispatched only to confirmed account email addresses according to configured notification preferences. When email delivery is disabled by system configuration, delivery is bypassed and recorded truthfully without sending data to external relays.
          </p>
        </section>

        <section className="p-4 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-2 text-xs">
          <span className="font-mono text-[10px] uppercase font-bold text-[#3F4634]">
            Counsel Confirmation Note
          </span>
          <p className="text-[#6F6A61]">
            Final enterprise data retention durations, sub-processor schedules, data residency hosting locations, and GDPR/DPDPA Data Processing Addendums (DPAs) are finalized pursuant to individual master service agreements and require formal validation by designated corporate legal counsel prior to enterprise contract execution. Contractly does not claim unverified statutory certifications (e.g. SOC 2, ISO 27001, HIPAA) without formal independent audit attestation.
          </p>
        </section>
      </main>

      {/* Footer */}
      <footer className="py-8 border-t border-[#DED6C8] bg-[#F7F3EA] text-xs text-[#6F6A61]">
        <div className="max-w-4xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-[11px]">
          <div>© 2026 Contractly Systems. All rights reserved.</div>
          <div className="flex items-center gap-4">
            <Link href="/terms" className="hover:underline">Terms of Service</Link>
            <Link href="/privacy" className="hover:underline font-semibold text-[#242321]">Privacy Policy</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
