'use client';

import React from 'react';
import Link from 'next/link';
import { useContractly } from '@/context/contractly-context';
import {
  FileText,
  ShieldCheck,
  Calendar,
  GitCompare,
  HelpCircle,
  UploadCloud,
  CheckCircle2,
  Lock,
  ArrowRight
} from 'lucide-react';

export default function LandingPage() {
  const { currentUser, isAuthLoading } = useContractly();

  return (
    <div className="min-h-screen bg-[#F7F3EA] text-[#242321] selection:bg-[#3F4634] selection:text-[#FCFAF5]">
      {/* ─────────────────────────────────────────────────────────────
          1. NAVIGATION
      ───────────────────────────────────────────────────────────── */}
      <header className="h-16 border-b border-[#DED6C8] px-4 sm:px-6 lg:px-12 flex items-center justify-between bg-[#F7F3EA] sticky top-0 z-40">
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-baseline gap-2.5 focus-visible:outline-none">
            <span className="font-serif tracking-widest text-xl sm:text-2xl font-bold text-[#242321]">
              CONTRACTLY
            </span>
            <span className="text-[11px] uppercase font-mono tracking-wider text-[#6F6A61] border-l border-[#DED6C8] pl-2.5 hidden md:inline">
              Contracts, handled with clarity
            </span>
          </Link>
        </div>

        <nav className="hidden md:flex items-center gap-6 text-xs font-medium text-[#6F6A61]">
          <a href="#capabilities" className="hover:text-[#242321] transition-colors">
            Capabilities
          </a>
          <a href="#how-it-works" className="hover:text-[#242321] transition-colors">
            How It Works
          </a>
          <a href="#security" className="hover:text-[#242321] transition-colors">
            Security &amp; Trust
          </a>
          <Link href="/privacy" className="hover:text-[#242321] transition-colors">
            Privacy
          </Link>
          <Link href="/terms" className="hover:text-[#242321] transition-colors">
            Terms
          </Link>
        </nav>

        <div className="flex items-center gap-3">
          {!isAuthLoading && currentUser ? (
            <Link
              href="/dashboard"
              className="px-4 py-2 bg-[#3F4634] text-[#FCFAF5] hover:bg-[#59604A] text-xs font-semibold rounded-[2px] transition-colors inline-flex items-center gap-1.5"
            >
              <span>Go to Workspace</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          ) : (
            <>
              <Link
                href="/signin"
                className="px-3.5 py-1.5 text-xs font-semibold text-[#242321] hover:text-[#3F4634] transition-colors"
              >
                Sign In
              </Link>
              <Link
                href="/signup"
                className="px-4 py-2 bg-[#3F4634] text-[#FCFAF5] hover:bg-[#59604A] text-xs font-semibold rounded-[2px] transition-colors"
              >
                Get Started
              </Link>
            </>
          )}
        </div>
      </header>

      {/* ─────────────────────────────────────────────────────────────
          2. HERO SECTION
      ───────────────────────────────────────────────────────────── */}
      <section className="px-4 sm:px-6 lg:px-12 pt-12 pb-16 lg:pt-20 lg:pb-24 border-b border-[#DED6C8]">
        <div className="max-w-5xl mx-auto text-center space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-[11px] font-mono uppercase tracking-wider text-[#3F4634]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#3F4634]"></span>
            <span>Contract Lifecycle &amp; Legal Operations</span>
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-serif font-bold text-[#242321] tracking-tight leading-[1.15]">
            Your contracts, made easier.
          </h1>

          <p className="text-base sm:text-lg text-[#6F6A61] max-w-2xl mx-auto leading-relaxed">
            Understand contract terms in plain language, review important dates, compare proposed changes, and keep track of obligations in one organized workspace.
          </p>

          <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              href="/signup"
              className="w-full sm:w-auto px-6 py-3 bg-[#3F4634] text-[#FCFAF5] hover:bg-[#59604A] text-xs font-semibold rounded-[2px] transition-colors text-center"
            >
              Get Started with Contractly
            </Link>
            <Link
              href="/signin"
              className="w-full sm:w-auto px-6 py-3 bg-[#FCFAF5] border border-[#DED6C8] text-[#242321] hover:bg-[#F7F3EA] text-xs font-semibold rounded-[2px] transition-colors text-center"
            >
              Sign In to Existing Account
            </Link>
          </div>
        </div>

        {/* Authentic Product Preview Card */}
        <div className="max-w-5xl mx-auto mt-12 sm:mt-16 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] shadow-sm overflow-hidden">
          {/* Document Interface Preview */}
          <div className="bg-[#EFECE3] border-b border-[#DED6C8] px-4 py-2.5 flex items-center justify-between text-xs font-mono text-[#6F6A61]">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-[#DED6C8]"></span>
              <span className="w-2.5 h-2.5 rounded-full bg-[#DED6C8]"></span>
              <span className="w-2.5 h-2.5 rounded-full bg-[#DED6C8]"></span>
              <span className="ml-2 font-semibold text-[#242321] text-[11px]">
                Contractly Workspace / Document Analysis
              </span>
            </div>
            <span className="text-[10px] hidden sm:inline">Active Contract: MSA-2026-CLOUD</span>
          </div>

          {/* Document Header Metadata */}
          <div className="p-4 sm:p-6 border-b border-[#DED6C8] bg-[#FCFAF5] flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <span className="text-[10px] font-mono uppercase tracking-wider text-[#6F6A61] block">
                Master Agreement • Version 1.0 (PDF)
              </span>
              <h2 className="text-lg font-serif font-bold text-[#242321] mt-0.5">
                Master Cloud Services Agreement
              </h2>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="px-2.5 py-1 bg-[#E8EFE0] text-[#3F4634] border border-[#C5D5B8] rounded-[2px] font-mono text-[11px] font-semibold">
                Status: Under Review
              </span>
              <span className="px-2.5 py-1 bg-[#FCFAF5] text-[#6F6A61] border border-[#DED6C8] rounded-[2px] font-mono text-[11px]">
                Counterparty: Adverse Cloud Ltd
              </span>
              <span className="px-2.5 py-1 bg-[#FCFAF5] text-[#6F6A61] border border-[#DED6C8] rounded-[2px] font-mono text-[11px]">
                Governing Law: Laws of India
              </span>
            </div>
          </div>

          {/* Interactive Document Review Simulation */}
          <div className="grid grid-cols-1 lg:grid-cols-12 divide-y lg:divide-y-0 lg:divide-x divide-[#DED6C8] text-xs">
            {/* Left Column: Clause Extraction & Plain-Language Explanation */}
            <div className="lg:col-span-7 p-4 sm:p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-[#DED6C8] pb-2">
                <span className="font-serif font-bold text-[#242321] uppercase tracking-wider text-[11px]">
                  Extracted Clauses &amp; Risk Insights
                </span>
                <span className="text-[10px] font-mono text-[#6F6A61]">2 Clauses Analyzed</span>
              </div>

              {/* Clause Item 1 */}
              <div className="bg-[#FCFAF5] border border-[#DED6C8] p-3.5 rounded-[2px] space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-[#242321]">
                    Section 11.0: Limitation of Liability
                  </span>
                  <span className="px-2 py-0.5 bg-[#FDF2F2] border border-[#F5C2C2] text-[#8B3F3F] text-[10px] font-semibold rounded-[2px]">
                    High Risk
                  </span>
                </div>
                <div className="p-2 bg-[#F7F3EA] border border-[#DED6C8] text-[11px] font-mono text-[#242321] leading-relaxed">
                  &ldquo;Neither party shall be liable for consequential damages. Service Provider liability shall remain uncapped with respect to confidentiality breaches.&rdquo;
                </div>
                <div className="text-[11px] text-[#6F6A61] leading-relaxed">
                  <strong className="text-[#242321]">Plain Language:</strong> While indirect damages are excluded, there is no aggregate financial limit on liability for confidentiality or data claims.
                </div>
              </div>

              {/* Clause Item 2 */}
              <div className="bg-[#FCFAF5] border border-[#DED6C8] p-3.5 rounded-[2px] space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-[#242321]">
                    Section 14.2: Termination for Convenience
                  </span>
                  <span className="px-2 py-0.5 bg-[#E8EFE0] border border-[#C5D5B8] text-[#3F4634] text-[10px] font-semibold rounded-[2px]">
                    Standard
                  </span>
                </div>
                <div className="p-2 bg-[#F7F3EA] border border-[#DED6C8] text-[11px] font-mono text-[#242321] leading-relaxed">
                  &ldquo;Either party may terminate this agreement upon providing sixty (60) days advance written notice.&rdquo;
                </div>
                <div className="text-[11px] text-[#6F6A61] leading-relaxed">
                  <strong className="text-[#242321]">Plain Language:</strong> Either party can exit without penalty by providing 60 days written notice.
                </div>
              </div>
            </div>

            {/* Right Column: Proposed Changes & Tracked Obligations */}
            <div className="lg:col-span-5 p-4 sm:p-6 space-y-4 bg-[#FCFAF5]">
              <div className="flex items-center justify-between border-b border-[#DED6C8] pb-2">
                <span className="font-serif font-bold text-[#242321] uppercase tracking-wider text-[11px]">
                  Tracked Redlines &amp; Obligations
                </span>
                <span className="text-[10px] font-mono text-[#6F6A61]">Workflow Active</span>
              </div>

              {/* Redline Proposal */}
              <div className="p-3.5 border border-[#DED6C8] bg-[#FCFAF5] rounded-[2px] space-y-2">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="font-bold text-[#242321]">Proposed Redline (Section 11.2)</span>
                  <span className="text-[10px] font-mono text-[#6F6A61]">Legal Reviewer</span>
                </div>
                <div className="text-[11px] space-y-1">
                  <div className="text-[#8B3F3F] line-through bg-[#FDF2F2] p-1 border border-[#F5C2C2] rounded-[2px]">
                    ...shall remain uncapped without limitation.
                  </div>
                  <div className="text-[#3F4634] bg-[#E8EFE0] p-1 border border-[#C5D5B8] rounded-[2px]">
                    ...subject to an aggregate ceiling of 2x total contract value.
                  </div>
                </div>
                <div className="flex items-center gap-2 pt-1 text-[10px]">
                  <span className="px-2 py-0.5 bg-[#3F4634] text-[#FCFAF5] font-semibold rounded-[2px]">
                    Accept
                  </span>
                  <span className="px-2 py-0.5 border border-[#DED6C8] text-[#6F6A61] rounded-[2px]">
                    Decline
                  </span>
                </div>
              </div>

              {/* Obligation Milestone */}
              <div className="p-3.5 border border-[#DED6C8] bg-[#F7F3EA] rounded-[2px] space-y-1.5">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="font-bold text-[#242321]">Renewal Notice Milestone</span>
                  <span className="text-[10px] font-mono text-[#3F4634] font-semibold">45 Days Left</span>
                </div>
                <p className="text-[11px] text-[#6F6A61]">
                  Written non-renewal notice must be dispatched before October 31, 2026.
                </p>
                <div className="text-[10px] font-mono text-[#6F6A61] pt-1">
                  Assigned: Procurement &bull; Auto-reminder scheduled
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          3. PRODUCT CAPABILITIES (Factual, Codebase-Verified)
      ───────────────────────────────────────────────────────────── */}
      <section id="capabilities" className="px-4 sm:px-6 lg:px-12 py-16 lg:py-24 border-b border-[#DED6C8] bg-[#FCFAF5]">
        <div className="max-w-5xl mx-auto space-y-12">
          <div className="space-y-2 text-center max-w-2xl mx-auto">
            <span className="text-[11px] font-mono uppercase tracking-wider text-[#3F4634] font-bold block">
              Core Capabilities
            </span>
            <h2 className="text-3xl font-serif font-bold text-[#242321]">
              Built for clarity across the contract lifecycle.
            </h2>
            <p className="text-xs sm:text-sm text-[#6F6A61] leading-relaxed">
              Contractly provides verified operations tools to organize, review, redline, and monitor organizational agreements.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Capability 1 */}
            <div className="p-6 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3">
              <div className="w-8 h-8 rounded-[2px] bg-[#F7F3EA] border border-[#DED6C8] flex items-center justify-center text-[#3F4634]">
                <FileText className="w-4 h-4" />
              </div>
              <h3 className="text-sm font-serif font-bold text-[#242321]">
                Understand contracts in plain language
              </h3>
              <p className="text-xs text-[#6F6A61] leading-relaxed">
                Ingest PDF and Word documents to extract structured parties, execution dates, governing law, and key clauses into plain language summaries.
              </p>
            </div>

            {/* Capability 2 */}
            <div className="p-6 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3">
              <div className="w-8 h-8 rounded-[2px] bg-[#F7F3EA] border border-[#DED6C8] flex items-center justify-center text-[#3F4634]">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <h3 className="text-sm font-serif font-bold text-[#242321]">
                Review clauses and potential risks
              </h3>
              <p className="text-xs text-[#6F6A61] leading-relaxed">
                Inspect high-exposure terms such as non-standard indemnity, uncapped liability, restrictive covenants, and unilateral termination clauses.
              </p>
            </div>

            {/* Capability 3 */}
            <div className="p-6 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3">
              <div className="w-8 h-8 rounded-[2px] bg-[#F7F3EA] border border-[#DED6C8] flex items-center justify-center text-[#3F4634]">
                <GitCompare className="w-4 h-4" />
              </div>
              <h3 className="text-sm font-serif font-bold text-[#242321]">
                Compare proposed changes and redlines
              </h3>
              <p className="text-xs text-[#6F6A61] leading-relaxed">
                Track version-by-version redlines, compare suggested clause language, and record formal acceptance or rejection decisions.
              </p>
            </div>

            {/* Capability 4 */}
            <div className="p-6 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3">
              <div className="w-8 h-8 rounded-[2px] bg-[#F7F3EA] border border-[#DED6C8] flex items-center justify-center text-[#3F4634]">
                <Calendar className="w-4 h-4" />
              </div>
              <h3 className="text-sm font-serif font-bold text-[#242321]">
                Track important dates and obligations
              </h3>
              <p className="text-xs text-[#6F6A61] leading-relaxed">
                Schedule calendar milestones for auto-renewals, notice deadlines, compliance filings, and attach fulfillment verification records.
              </p>
            </div>

            {/* Capability 5 */}
            <div className="p-6 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3">
              <div className="w-8 h-8 rounded-[2px] bg-[#F7F3EA] border border-[#DED6C8] flex items-center justify-center text-[#3F4634]">
                <HelpCircle className="w-4 h-4" />
              </div>
              <h3 className="text-sm font-serif font-bold text-[#242321]">
                Ask questions about an uploaded contract
              </h3>
              <p className="text-xs text-[#6F6A61] leading-relaxed">
                Execute grounded document inquiries that answer specific questions directly from verified contract text with clear source citations.
              </p>
            </div>

            {/* Capability 6 */}
            <div className="p-6 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3">
              <div className="w-8 h-8 rounded-[2px] bg-[#F7F3EA] border border-[#DED6C8] flex items-center justify-center text-[#3F4634]">
                <Lock className="w-4 h-4" />
              </div>
              <h3 className="text-sm font-serif font-bold text-[#242321]">
                Verified advocate directory &amp; matters
              </h3>
              <p className="text-xs text-[#6F6A61] leading-relaxed">
                Submit legal inquiries to verified independent advocates with explicit conflict check clearance and controlled document access grants.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          4. HOW IT WORKS
      ───────────────────────────────────────────────────────────── */}
      <section id="how-it-works" className="px-4 sm:px-6 lg:px-12 py-16 lg:py-24 border-b border-[#DED6C8]">
        <div className="max-w-5xl mx-auto space-y-12">
          <div className="space-y-2 text-center max-w-2xl mx-auto">
            <span className="text-[11px] font-mono uppercase tracking-wider text-[#3F4634] font-bold block">
              Workflow
            </span>
            <h2 className="text-3xl font-serif font-bold text-[#242321]">
              How Contractly works in practice.
            </h2>
            <p className="text-xs sm:text-sm text-[#6F6A61] leading-relaxed">
              A systematic workflow designed to help teams review agreements without getting lost in legal jargon.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Step 1 */}
            <div className="p-5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3">
              <span className="font-mono text-xs font-bold text-[#3F4634] block">Step 01</span>
              <h3 className="text-sm font-serif font-bold text-[#242321]">Upload a contract</h3>
              <p className="text-xs text-[#6F6A61] leading-relaxed">
                Add PDF, Word, or plain text agreements to your isolated organization repository.
              </p>
            </div>

            {/* Step 2 */}
            <div className="p-5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3">
              <span className="font-mono text-xs font-bold text-[#3F4634] block">Step 02</span>
              <h3 className="text-sm font-serif font-bold text-[#242321]">Understand important terms</h3>
              <p className="text-xs text-[#6F6A61] leading-relaxed">
                Automated clause extraction surfaces key provisions, potential risks, and governing law.
              </p>
            </div>

            {/* Step 3 */}
            <div className="p-5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3">
              <span className="font-mono text-xs font-bold text-[#3F4634] block">Step 03</span>
              <h3 className="text-sm font-serif font-bold text-[#242321]">Review changes &amp; obligations</h3>
              <p className="text-xs text-[#6F6A61] leading-relaxed">
                Propose collaborative redlines, assign reviewers, and schedule renewal milestones.
              </p>
            </div>

            {/* Step 4 */}
            <div className="p-5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3">
              <span className="font-mono text-xs font-bold text-[#3F4634] block">Step 04</span>
              <h3 className="text-sm font-serif font-bold text-[#242321]">Track what needs attention</h3>
              <p className="text-xs text-[#6F6A61] leading-relaxed">
                Receive proactive reminders for impending deadlines, approval gates, and compliance filings.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          5. TRUST, SECURITY & LEGAL LIMITATIONS
      ───────────────────────────────────────────────────────────── */}
      <section id="security" className="px-4 sm:px-6 lg:px-12 py-16 lg:py-24 border-b border-[#DED6C8] bg-[#FCFAF5]">
        <div className="max-w-4xl mx-auto space-y-10">
          <div className="space-y-2 text-center">
            <span className="text-[11px] font-mono uppercase tracking-wider text-[#3F4634] font-bold block">
              Integrity &amp; Disclosures
            </span>
            <h2 className="text-3xl font-serif font-bold text-[#242321]">
              Architectural trust and verifiable security.
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs leading-relaxed">
            <div className="p-5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-2">
              <h3 className="font-serif font-bold text-[#242321] text-sm">
                Multi-Tenant Boundary Isolation
              </h3>
              <p className="text-[#6F6A61]">
                Every contract, clause, redline, and audit log is partitioned by an immutable organization foreign key. Database queries and document storage paths enforce strict tenant authorization on every request.
              </p>
            </div>

            <div className="p-5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-2">
              <h3 className="font-serif font-bold text-[#242321] text-sm">
                Private Document Storage
              </h3>
              <p className="text-[#6F6A61]">
                Document versions are stored under private, tenant-scoped paths with SHA-256 cryptographic checksums for tamper detection. Downloads require active authenticated grants.
              </p>
            </div>
          </div>

          {/* Explicit Legal Disclaimer */}
          <div className="p-5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] space-y-2 text-xs leading-relaxed">
            <span className="font-mono text-[10px] uppercase font-bold text-[#3F4634] block">
              Important Informational Notice
            </span>
            <p className="text-[#242321]">
              Contractly is legal operations software. AI-generated analyses, clause summaries, and risk indicators are provided strictly for informational and workflow purposes. Contractly is not a law firm, does not provide legal advice, and does not guarantee legal compliance or risk identification. Consult a licensed attorney for binding legal counsel.
            </p>
          </div>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          6. FOOTER
      ───────────────────────────────────────────────────────────── */}
      <footer className="px-4 sm:px-6 lg:px-12 py-12 bg-[#F7F3EA] text-xs">
        <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-baseline justify-between gap-6 pb-8 border-b border-[#DED6C8]">
          <div className="space-y-1">
            <span className="font-serif tracking-widest text-lg font-bold text-[#242321] block">
              CONTRACTLY
            </span>
            <p className="text-[#6F6A61] text-[11px]">
              Contracts, handled with clarity.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-6 text-[#6F6A61] font-medium">
            <Link href="/signin" className="hover:text-[#242321] transition-colors">
              Sign In
            </Link>
            <Link href="/signup" className="hover:text-[#242321] transition-colors">
              Create Account
            </Link>
            <Link href="/privacy" className="hover:text-[#242321] transition-colors">
              Privacy Policy
            </Link>
            <Link href="/terms" className="hover:text-[#242321] transition-colors">
              Terms of Service
            </Link>
          </div>
        </div>

        <div className="max-w-5xl mx-auto pt-6 flex flex-col sm:flex-row items-center justify-between gap-3 text-[11px] text-[#6F6A61]">
          <span>&copy; {new Date().getFullYear()} Contractly. All rights reserved.</span>
          <span>Legal Operations &bull; Multi-Tenant Architecture</span>
        </div>
      </footer>
    </div>
  );
}
