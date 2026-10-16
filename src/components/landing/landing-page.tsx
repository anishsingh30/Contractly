'use client';

import React from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { StatusPill } from '@/components/ui/status-pill';

interface LandingPageProps {
  onEnterApp: () => void;
}

export function LandingPage({ onEnterApp }: LandingPageProps) {
  return (
    <div className="bg-[#F7F3EA] text-[#242321] min-h-screen selection:bg-[#3F4634] selection:text-[#FCFAF5]">
      {/* Marketing Header */}
      <header className="h-16 border-b border-[#DED6C8] px-6 lg:px-12 flex items-center justify-between bg-[#F7F3EA]/90 sticky top-0 z-40 backdrop-blur-sm">
        <div className="flex items-center gap-8">
          <span className="font-serif tracking-widest text-lg font-bold text-[#242321]">
            CONTRACTLY
          </span>
          <nav className="hidden md:flex items-center gap-6 text-xs font-medium text-[#6F6A61]">
            <a href="#lifecycle" className="hover:text-[#242321] transition-colors">Platform</a>
            <a href="#solutions" className="hover:text-[#242321] transition-colors">Solutions</a>
            <a href="#intelligence" className="hover:text-[#242321] transition-colors">Intelligence</a>
            <a href="#compliance" className="hover:text-[#242321] transition-colors">Contract Health</a>
            <a href="#pricing" className="hover:text-[#242321] transition-colors">Pricing</a>
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={onEnterApp}
            className="text-xs text-[#6F6A61] hover:text-[#242321] font-medium px-3 py-1.5"
          >
            Sign in
          </button>
          <Button onClick={onEnterApp} variant="primary" size="sm">
            Open Contractly
          </Button>
        </div>
      </header>

      {/* Hero Section */}
      <section className="py-20 lg:py-28 px-6 lg:px-12 max-w-6xl mx-auto text-center space-y-6">
        <div className="inline-flex items-center gap-2 px-3 py-1 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-xs text-[#3F4634] font-medium">
          <span>Intelligent Contract Lifecycle & Legal Operations</span>
        </div>

        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-serif font-bold text-[#242321] tracking-tight max-w-4xl mx-auto leading-[1.15]">
          Contracts, handled with clarity.
        </h1>

        <p className="text-base sm:text-lg text-[#6F6A61] max-w-2xl mx-auto leading-relaxed">
          Contractly is an intelligent legal operations platform that helps individuals and organizations create, review, negotiate, monitor, and manage contracts throughout their entire lifecycle.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-3 pt-4">
          <Button onClick={onEnterApp} variant="primary" size="lg">
            Get started
          </Button>
          <Button onClick={onEnterApp} variant="secondary" size="lg">
            Explore the platform
          </Button>
        </div>

        {/* Realistic Application Preview (Section 51: Authentic product interface preview, not cartoonish graphics) */}
        <div className="pt-12 max-w-5xl mx-auto">
          <div className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] shadow-sm text-left overflow-hidden">
            {/* Window Topbar */}
            <div className="h-9 bg-[#F7F3EA] border-b border-[#DED6C8] px-4 flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[#DED6C8]" />
                <span className="w-2.5 h-2.5 rounded-full bg-[#DED6C8]" />
                <span className="w-2.5 h-2.5 rounded-full bg-[#DED6C8]" />
                <span className="ml-3 font-mono text-[11px] text-[#6F6A61]">
                  CONTRACTLY • VENDOR_MSA_v2.1_EXECUTED.PDF
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-[#6F6A61]">Status:</span>
                <StatusPill status="ACTIVE" />
                <StatusPill status="HIGH" />
              </div>
            </div>

            {/* Split Screen UI inside Hero */}
            <div className="grid grid-cols-1 md:grid-cols-12 divide-y md:divide-y-0 md:divide-x divide-[#DED6C8] p-4 gap-4 bg-[#FCFAF5]">
              {/* Left Pane: Legal Text */}
              <div className="md:col-span-7 space-y-3 font-sans text-xs">
                <div className="border-b border-[#DED6C8] pb-2 flex justify-between items-center">
                  <span className="font-semibold text-[#242321]">
                    Section 11.2: Limitation of Liability
                  </span>
                  <span className="font-mono text-[10px] text-[#8B3F3F]">High Exposure</span>
                </div>
                <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] font-serif italic text-[#242321] leading-relaxed">
                  &quot;Vendor aggregate liability shall be capped at twelve (12) months fees, provided that claims arising under Section 8 (Confidentiality & Data Protection) shall remain uncapped.&quot;
                </div>
                <div className="text-[11px] text-[#6F6A61] leading-relaxed">
                  Tracked revision proposed against Enterprise Playbook Rule 4.1.
                </div>
              </div>

              {/* Right Pane: Plain Language Analysis */}
              <div className="md:col-span-5 space-y-2 text-xs">
                <div className="border-b border-[#DED6C8] pb-2">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-[#6F6A61]">
                    Plain-Language Analysis
                  </span>
                </div>
                <div className="p-2.5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px]">
                  <strong className="text-[#242321] block mb-0.5">What it means:</strong>
                  <p className="text-[#6F6A61] text-[11px] leading-relaxed">
                    General errors are capped at 1 year of fees, but security or data breach claims have no cap.
                  </p>
                </div>
                <div className="p-2.5 bg-[#EDF2EC] border border-[#C6D8C6] rounded-[2px]">
                  <strong className="text-[#4F6B50] block mb-0.5">Suggested action:</strong>
                  <p className="text-[#4F6B50] text-[11px]">
                    Accept revision: matches enterprise fallback standard.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Section 2: Complete Contract Lifecycle Pipeline */}
      <section id="lifecycle" className="py-20 border-t border-[#DED6C8] bg-[#FCFAF5]">
        <div className="max-w-6xl mx-auto px-6 lg:px-12 space-y-12">
          <div className="text-center max-w-2xl mx-auto space-y-3">
            <h2 className="text-2xl sm:text-3xl font-serif font-bold text-[#242321]">
              The Full Contract Lifecycle
            </h2>
            <p className="text-xs sm:text-sm text-[#6F6A61] leading-relaxed">
              From initial departmental intake to post-execution compliance monitoring. Contractly orchestrates every stage without breaking workflow continuity.
            </p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2 text-center text-xs">
            {[
              { step: '01', title: 'Request', desc: 'Intake form' },
              { step: '02', title: 'Draft', desc: 'Templates' },
              { step: '03', title: 'Review', desc: 'Risk extraction' },
              { step: '04', title: 'Redline', desc: 'Tracked changes' },
              { step: '05', title: 'Approve', desc: 'Multi-stage approval' },
              { step: '06', title: 'Sign', desc: 'Execution' },
              { step: '07', title: 'Monitor', desc: 'Contract Health' },
              { step: '08', title: 'Renew', desc: 'Notice pipeline' },
            ].map((item) => (
              <div
                key={item.step}
                className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] flex flex-col justify-between"
              >
                <span className="font-mono text-[10px] text-[#6F6A61] block mb-1">{item.step}</span>
                <span className="font-bold text-xs text-[#242321] block">{item.title}</span>
                <span className="text-[10px] text-[#6F6A61] mt-1">{item.desc}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Section 3: Redline Studio with Real Tracked Changes */}
      <section id="intelligence" className="py-20 border-t border-[#DED6C8] bg-[#F7F3EA]">
        <div className="max-w-6xl mx-auto px-6 lg:px-12 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          <div className="lg:col-span-6 space-y-4">
            <span className="font-mono text-[11px] uppercase tracking-wider text-[#3F4634] font-bold">
              Precision Legal Redlining
            </span>
            <h2 className="text-3xl font-serif font-bold text-[#242321] leading-snug">
              Negotiate with confidence. Not with chatbots.
            </h2>
            <p className="text-xs sm:text-sm text-[#6F6A61] leading-relaxed">
              Contractly’s Redline Studio compares incoming counterparty drafts directly against your corporate negotiation playbook. It suggests balanced revisions, explains commercial impact, and exports directly to Microsoft Word with native OpenXML tracked changes.
            </p>
            <ul className="space-y-2 text-xs text-[#242321] pt-2">
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-[#3F4634]" />
                Direct Word OpenXML compatibility (`&lt;w:ins&gt;` and `&lt;w:del&gt;`)
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-[#3F4634]" />
                Automated Playbook fallback clause suggestions
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-[#3F4634]" />
                Human-in-the-loop review: 1-click Accept, Reject, or Modify
              </li>
            </ul>
          </div>

          <div className="lg:col-span-6">
            <div className="p-5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3 shadow-sm">
              <div className="flex items-center justify-between pb-2 border-b border-[#DED6C8]">
                <span className="font-semibold text-xs text-[#242321]">
                  Section 9.1: Restrictive Covenants
                </span>
                <StatusPill status="HIGH" />
              </div>
              <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] text-xs font-serif leading-relaxed">
                <span>Employee agrees that </span>
                <span className="redline-del">for 24 months Employee shall not engage in any software business worldwide</span>{' '}
                <span className="redline-ins">for 12 months Employee shall not solicit Company clients or personnel</span>.
              </div>
              <p className="text-[11px] text-[#6F6A61]">
                <strong>Rationale:</strong> Replaces void non-compete with enforceable non-solicitation under Section 27 standards.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Section 4: Contract Health & Compliance Engine */}
      <section id="compliance" className="py-20 border-t border-[#DED6C8] bg-[#FCFAF5]">
        <div className="max-w-6xl mx-auto px-6 lg:px-12 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          <div className="lg:col-span-6 order-2 lg:order-1">
            <div className="p-5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-[#DED6C8]">
                <span className="font-mono text-xs font-semibold text-[#242321]">
                  CONTRACT WATCH • ACTIVE
                </span>
                <StatusPill status="POTENTIAL_NON_COMPLIANCE" />
              </div>
              <div className="p-3 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-1.5 text-xs">
                <span className="font-semibold text-[#242321]">
                  SOC2 Type II Report Delivery Requirement
                </span>
                <p className="text-[11px] text-[#6F6A61]">
                  Vendor: CloudStack Infrastructure • Deadline: Oct 15
                </p>
                <div className="text-[10px] font-mono text-[#8B3F3F]">
                  Current Status: Missing Verification Artifact
                </div>
              </div>
              <div className="text-[11px] text-[#6F6A61] pt-1">
                Automated escalation queued for Legal & Procurement Leads.
              </div>
            </div>
          </div>

          <div className="lg:col-span-6 order-1 lg:order-2 space-y-4">
            <span className="font-mono text-[11px] uppercase tracking-wider text-[#3F4634] font-bold">
              Post-Execution Intelligence
            </span>
            <h2 className="text-3xl font-serif font-bold text-[#242321] leading-snug">
              Contracts don’t end at signature. That’s where Contract Health begins.
            </h2>
            <p className="text-xs sm:text-sm text-[#6F6A61] leading-relaxed">
              Signed contracts are continuously monitored for contractual covenants, SLA milestones, payment triggers, and renewal windows. When evidence is overdue, Contractly alerts responsible owners before penalties accrue.
            </p>
            <ul className="space-y-2 text-xs text-[#242321] pt-2">
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-[#3F4634]" />
                Automated obligation and deadline extraction
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-[#3F4634]" />
                Evidence management: attach proof receipts & audit logs
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-[#3F4634]" />
                Calibrated legal safety: non-adjudicative alert framing
              </li>
            </ul>
          </div>
        </div>
      </section>

      {/* Section 5: Solutions for 3 Distinct Tiers (Personal, Business, Professional) */}
      <section id="solutions" className="py-20 border-t border-[#DED6C8] bg-[#F7F3EA]">
        <div className="max-w-6xl mx-auto px-6 lg:px-12 space-y-12">
          <div className="text-center max-w-2xl mx-auto space-y-3">
            <h2 className="text-2xl sm:text-3xl font-serif font-bold text-[#242321]">
              Engineered for Every Tier of Legal Operations
            </h2>
            <p className="text-xs sm:text-sm text-[#6F6A61] leading-relaxed">
              Whether you are an individual reviewing an employment offer, a scaling business managing 100+ vendor agreements, or a law firm managing client matters.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Personal Card */}
            <div className="p-6 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] flex flex-col justify-between space-y-4">
              <div className="space-y-3">
                <span className="font-mono text-[10px] uppercase tracking-wider text-[#6F6A61]">
                  Personal Contracts
                </span>
                <h3 className="font-serif font-bold text-lg text-[#242321]">
                  For Individuals & Freelancers
                </h3>
                <p className="text-xs text-[#6F6A61] leading-relaxed">
                  Understand what you are signing before putting pen to paper. Plain-language clause breakdowns, rental notice trackers, and direct 1-click consultation bookings with verified advocates.
                </p>
                <div className="pt-3 border-t border-[#DED6C8] space-y-1.5 text-xs text-[#242321]">
                  <p>• Plain-language risk explanations</p>
                  <p>• Lease & employment notice tracking</p>
                  <p>• Verified advocate directory</p>
                </div>
              </div>

              <Button onClick={onEnterApp} variant="secondary" size="sm" className="w-full">
                Explore Personal Tier
              </Button>
            </div>

            {/* Business Card */}
            <div className="p-6 bg-[#FCFAF5] border border-[#3F4634] rounded-[2px] flex flex-col justify-between space-y-4 relative">
              <div className="space-y-3">
                <span className="font-mono text-[10px] uppercase tracking-wider text-[#3F4634] font-bold">
                  Business & Enterprise
                </span>
                <h3 className="font-serif font-bold text-lg text-[#242321]">
                  For Companies & Legal Teams
                </h3>
                <p className="text-xs text-[#6F6A61] leading-relaxed">
                  Full-scale CLM with departmental intake requests, multi-tier approvals, vendor health risk profiles, and corporate negotiation playbook enforcement.
                </p>
                <div className="pt-3 border-t border-[#DED6C8] space-y-1.5 text-xs text-[#242321]">
                  <p>• Multi-stage approval workflows</p>
                  <p>• Playbook-driven redline studio</p>
                  <p>• Post-execution Contract Health</p>
                </div>
              </div>

              <Button onClick={onEnterApp} variant="primary" size="sm" className="w-full">
                Explore Business Tier
              </Button>
            </div>

            {/* Professional Card */}
            <div className="p-6 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] flex flex-col justify-between space-y-4">
              <div className="space-y-3">
                <span className="font-mono text-[10px] uppercase tracking-wider text-[#6F6A61]">
                  For Lawyers
                </span>
                <h3 className="font-serif font-bold text-lg text-[#242321]">
                  For Law Firms & Practitioners
                </h3>
                <p className="text-xs text-[#6F6A61] leading-relaxed">
                  Complete client matter isolation, multi-document cross-referencing, tracked changes export, consultation scheduling, and secure evidence discovery vaults.
                </p>
                <div className="pt-3 border-t border-[#DED6C8] space-y-1.5 text-xs text-[#242321]">
                  <p>• Client & matter data isolation</p>
                  <p>• Professional Word .docx redlines</p>
                  <p>• Verified marketplace listing</p>
                </div>
              </div>

              <Button onClick={onEnterApp} variant="secondary" size="sm" className="w-full">
                Explore Professional Tier
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Section 6: Security, Cryptography & Privacy Principles */}
      <section className="py-20 border-t border-[#DED6C8] bg-[#FCFAF5]">
        <div className="max-w-6xl mx-auto px-6 lg:px-12 space-y-8">
          <div className="text-center max-w-2xl mx-auto space-y-3">
            <h2 className="text-2xl sm:text-3xl font-serif font-bold text-[#242321]">
              Security & Data Governance Principles
            </h2>
            <p className="text-xs sm:text-sm text-[#6F6A61]">
              Built strictly around data isolation, non-adjudicative legal safety, and enterprise privacy guarantees.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-xs leading-relaxed">
            <div className="p-5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] space-y-2">
              <h4 className="font-bold text-sm text-[#242321]">Zero Data Contamination</h4>
              <p className="text-[#6F6A61]">
                Customer agreements and documents are never utilized for model training. Documents reside strictly in tenant-isolated encrypted storage vaults.
              </p>
            </div>

            <div className="p-5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] space-y-2">
              <h4 className="font-bold text-sm text-[#242321]">Non-Adjudicative Safety</h4>
              <p className="text-[#6F6A61]">
                Contractly provides decision support and flags risk conditions, reserving legal conclusions and final determinations for qualified human operators.
              </p>
            </div>

            <div className="p-5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] space-y-2">
              <h4 className="font-bold text-sm text-[#242321]">Immutable Audit Trail</h4>
              <p className="text-[#6F6A61]">
                Every clause edit, approval sign-off, redline acceptance, and evidence upload is recorded with cryptographic checksums and user attribution.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Section 7: Pricing Architecture */}
      <section id="pricing" className="py-20 border-t border-[#DED6C8] bg-[#F7F3EA]">
        <div className="max-w-5xl mx-auto px-6 lg:px-12 space-y-12">
          <div className="text-center max-w-xl mx-auto space-y-2">
            <h2 className="text-2xl sm:text-3xl font-serif font-bold text-[#242321]">
              Transparent SaaS Tiers
            </h2>
            <p className="text-xs text-[#6F6A61]">
              Scalable pricing plans tailored to personal needs and growing organizations.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-xs">
            {/* Personal Plan */}
            <div className="p-6 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-4 flex flex-col justify-between">
              <div className="space-y-3">
                <span className="font-mono text-[10px] text-[#6F6A61] uppercase">Personal</span>
                <div className="text-2xl font-serif font-bold text-[#242321]">₹499 <span className="text-xs font-normal text-[#6F6A61]">/ month</span></div>
                <p className="text-[#6F6A61]">For individuals managing personal leases, employment covenants, and loans.</p>
                <div className="pt-3 border-t border-[#DED6C8] space-y-1.5 text-[#242321]">
                  <p>• Up to 10 active vaulted contracts</p>
                  <p>• Plain-language clause analysis</p>
                  <p>• Calendar & deadline alerts</p>
                </div>
              </div>
              <Button onClick={onEnterApp} variant="secondary" size="sm" className="w-full">
                Select Personal
              </Button>
            </div>

            {/* Business Plan */}
            <div className="p-6 bg-[#FCFAF5] border border-[#3F4634] rounded-[2px] space-y-4 flex flex-col justify-between">
              <div className="space-y-3">
                <span className="font-mono text-[10px] text-[#3F4634] uppercase font-bold">Business</span>
                <div className="text-2xl font-serif font-bold text-[#242321]">₹8,999 <span className="text-xs font-normal text-[#6F6A61]">/ month</span></div>
                <p className="text-[#6F6A61]">For growing companies needing departmental workflows and playbooks.</p>
                <div className="pt-3 border-t border-[#DED6C8] space-y-1.5 text-[#242321]">
                  <p>• Unlimited contracts & versioning</p>
                  <p>• Multi-stage approvals</p>
                  <p>• Redline Studio & Word export</p>
                  <p>• Post-execution Contract Health</p>
                </div>
              </div>
              <Button onClick={onEnterApp} variant="primary" size="sm" className="w-full">
                Select Business
              </Button>
            </div>

            {/* Professional Plan */}
            <div className="p-6 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-4 flex flex-col justify-between">
              <div className="space-y-3">
                <span className="font-mono text-[10px] text-[#6F6A61] uppercase">Professional</span>
                <div className="text-2xl font-serif font-bold text-[#242321]">₹14,999 <span className="text-xs font-normal text-[#6F6A61]">/ month</span></div>
                <p className="text-[#6F6A61]">For independent advocates and law firms managing client matters.</p>
                <div className="pt-3 border-t border-[#DED6C8] space-y-1.5 text-[#242321]">
                  <p>• Client & matter data isolation</p>
                  <p>• Verified advocate directory listing</p>
                  <p>• Consultation scheduling & notes</p>
                </div>
              </div>
              <Button onClick={onEnterApp} variant="secondary" size="sm" className="w-full">
                Select Professional
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-20 border-t border-[#DED6C8] bg-[#FCFAF5] text-center">
        <div className="max-w-3xl mx-auto px-6 space-y-6">
          <h2 className="text-3xl sm:text-4xl font-serif font-bold text-[#242321]">
            Bring your contracts into one place.
          </h2>
          <p className="text-xs sm:text-sm text-[#6F6A61] max-w-lg mx-auto leading-relaxed">
            Experience intelligent contract lifecycle management with zero clutter, zero AI clichés, and complete operational clarity.
          </p>
          <div className="pt-2">
            <Button onClick={onEnterApp} variant="primary" size="lg">
              Open Contractly
            </Button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-10 border-t border-[#DED6C8] bg-[#F7F3EA] text-xs text-[#6F6A61]">
        <div className="max-w-6xl mx-auto px-6 lg:px-12 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-serif font-bold text-sm text-[#242321]">CONTRACTLY</span>
            <span>• Legal Operations Platform</span>
          </div>
          <div className="flex items-center gap-6 text-[11px]">
            <Link href="/terms" className="hover:text-[#242321] transition-colors">
              Terms of Service
            </Link>
            <Link href="/privacy" className="hover:text-[#242321] transition-colors">
              Privacy Policy
            </Link>
            <span className="font-mono text-[#6F6A61]">
              © 2026 Contractly Systems. All rights reserved.
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
