import React from 'react';
import Link from 'next/link';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Terms of Service — Contractly Legal Operations',
  description: 'Operating terms, service scope, AI assistance boundaries, and non-adjudicative disclaimers for the Contractly platform.',
};

export default function TermsOfServicePage() {
  return (
    <div className="bg-[#F7F3EA] text-[#242321] min-h-screen selection:bg-[#3F4634] selection:text-[#FCFAF5]">
      {/* Header */}
      <header className="h-16 border-b border-[#DED6C8] px-6 lg:px-12 flex items-center justify-between bg-[#F7F3EA]/90 sticky top-0 z-40 backdrop-blur-sm">
        <div className="flex items-center gap-4">
          <Link href="/" className="font-serif tracking-widest text-lg font-bold text-[#242321]">
            CONTRACTLY
          </Link>
          <span className="text-xs font-mono text-[#6F6A61] border-l border-[#DED6C8] pl-4">
            Master Platform Terms
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
            Terms of Service • Version 1.0 (October 2026)
          </span>
          <h1 className="text-3xl sm:text-4xl font-serif font-bold text-[#242321]">
            Platform Terms & Operating Conditions
          </h1>
          <p className="text-xs sm:text-sm text-[#6F6A61] leading-relaxed">
            Please read these terms carefully before accessing or utilizing Contractly services, workflows, and automated intelligence tools.
          </p>
        </div>

        <section className="space-y-4 text-xs sm:text-sm leading-relaxed text-[#242321]">
          <h2 className="text-lg font-serif font-bold text-[#242321] border-b border-[#DED6C8] pb-1">
            1. Scope of Service & Non-Adjudicative Disclaimer
          </h2>
          <div className="p-4 bg-[#F7EFE4]/80 border border-[#E5D2B8] rounded-[2px] text-xs space-y-2">
            <strong className="text-[#7A4D1A] uppercase tracking-wide font-mono block">
              Notice Regarding Legal Advice
            </strong>
            <p className="text-[#242321]">
              Contractly is an operational software platform designed to organize, extract, redline, and monitor agreements. <strong>Contractly is not a law firm, does not provide formal legal counsel, and does not establish an attorney-client relationship.</strong>
            </p>
            <p className="text-[#6F6A61]">
              Automated clause analyses, risk assessments, and playbook recommendations are informational aids intended to facilitate human legal review. Users must consult qualified independent legal counsel for definitive legal advice and contractual enforceability determinations.
            </p>
          </div>
        </section>

        <section className="space-y-4 text-xs sm:text-sm leading-relaxed text-[#242321]">
          <h2 className="text-lg font-serif font-bold text-[#242321] border-b border-[#DED6C8] pb-1">
            2. AI Assistance & Document Intelligence Limitations
          </h2>
          <p>
            Automated features—including clause categorization, risk scoring, obligation candidates, and natural language Q&amp;A—are probabilistic and deterministic tools:
          </p>
          <ul className="list-disc pl-5 space-y-1.5 text-[#6F6A61]">
            <li>Scanned documents, complex graphical layouts, or unsearchable PDFs may yield incomplete text extraction.</li>
            <li>Calculated contract health percentages and risk rankings reflect modeled heuristics and should not be construed as statutory compliance guarantees.</li>
            <li>Users remain solely responsible for verifying the accuracy of extracted milestone dates, amounts, and party obligations prior to signing or reliance.</li>
          </ul>
        </section>

        <section className="space-y-4 text-xs sm:text-sm leading-relaxed text-[#242321]">
          <h2 className="text-lg font-serif font-bold text-[#242321] border-b border-[#DED6C8] pb-1">
            3. Account Responsibilities & Role-Based Access
          </h2>
          <p>
            Users are responsible for safeguarding account credentials, API keys, and session tokens. Organizational administrators are responsible for configuring appropriate role-based permissions (e.g. Legal Reviewer, Legal Manager, Finance, HR, Employee) and revoking access for departed personnel.
          </p>
        </section>

        <section className="space-y-4 text-xs sm:text-sm leading-relaxed text-[#242321]">
          <h2 className="text-lg font-serif font-bold text-[#242321] border-b border-[#DED6C8] pb-1">
            4. Platform Operations &amp; Customer Data Separation
          </h2>
          <p>
            Contractly personnel and platform administrators operate Contractly infrastructure without routine inspection of customer agreements:
          </p>
          <ul className="list-disc pl-5 space-y-1.5 text-[#6F6A61]">
            <li>Customer organizations retain exclusive ownership and administrative control over contract contents, uploaded evidence, and redline drafts.</li>
            <li>Contractly administrators monitor aggregate service availability, storage utilization, and infrastructure metrics, but are restricted from browsing or querying customer contract repositories.</li>
            <li>Support assistance requiring document inspection will occur only upon explicit written authorization by the customer organization Owner with an enforced expiration period.</li>
          </ul>
        </section>

        <section className="space-y-4 text-xs sm:text-sm leading-relaxed text-[#242321]">
          <h2 className="text-lg font-serif font-bold text-[#242321] border-b border-[#DED6C8] pb-1">
            5. External Legal Network &amp; Directory Disclosures
          </h2>
          <p>
            The verified lawyer directory provides contact coordination with independent practitioners. Submitting an inquiry creates a record in your organization audit trail for coordination purposes. Inquiries do not constitute automated appointment confirmations, immediate engagement, or retention of counsel.
          </p>
        </section>

        <section className="p-4 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-2 text-xs">
          <span className="font-mono text-[10px] uppercase font-bold text-[#3F4634]">
            Counsel Confirmation Note
          </span>
          <p className="text-[#6F6A61]">
            Formal service level agreements (SLAs), enterprise indemnity caps, governing law selections, and dispute resolution venues are established under enterprise order forms and require confirmation from designated company counsel before execution.
          </p>
        </section>
      </main>

      {/* Footer */}
      <footer className="py-8 border-t border-[#DED6C8] bg-[#F7F3EA] text-xs text-[#6F6A61]">
        <div className="max-w-4xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-[11px]">
          <div>© 2026 Contractly Systems. All rights reserved.</div>
          <div className="flex items-center gap-4">
            <Link href="/terms" className="hover:underline font-semibold text-[#242321]">Terms of Service</Link>
            <Link href="/privacy" className="hover:underline">Privacy Policy</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
