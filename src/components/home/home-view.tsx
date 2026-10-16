'use client';

import React from 'react';
import { useContractly } from '@/context/contractly-context';
import { StatusPill } from '@/components/ui/status-pill';
import { Button } from '@/components/ui/button';
import { formatRoleName } from '@/components/navigation/top-bar';
import { Lightbulb, FileText } from 'lucide-react';

interface HomeViewProps {
  onOpenContract: (id: string) => void;
  onRequestUpload: () => void;
  onNavigate: (tab: string) => void;
}

export function HomeView({ onOpenContract, onRequestUpload, onNavigate }: HomeViewProps) {
  const { contracts, obligations, currentUser, currentOrganization, businessRole, accountType } = useContractly();

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0
    }).format(val);
  };

  // Deterministic derivations from live backend data
  const attentionContracts = contracts.filter(
    (c) => c.riskLevel === 'HIGH' || c.riskLevel === 'CRITICAL' || c.status === 'UNDER_REVIEW'
  );
  const upcomingObligations = obligations.filter(
    (o) => o.status === 'UPCOMING' || o.status === 'DUE_SOON' || o.status === 'POTENTIAL_NON_COMPLIANCE'
  );
  const renewingContracts = contracts.filter(
    (c) => Boolean(c.renewalDate || c.expiryDate)
  );
  const pendingApprovalsCount = contracts.reduce((acc, c) => {
    const pendingSteps = (c.approvalSteps || []).filter((s) => s.decision === 'PENDING');
    return acc + pendingSteps.length;
  }, 0);
  const totalValue = contracts.reduce((acc, c) => acc + (c.value || 0), 0);

  const greetingName = currentUser?.fullName || (currentUser?.isSuperAdmin ? 'Administrator' : 'Team Member');
  const orgName = currentOrganization?.name || 'Your Organization';
  const greetingTitle = `Good day, ${greetingName}`;
  const greetingSubtitle = `${orgName} • ${contracts.length} ${contracts.length === 1 ? 'agreement' : 'agreements'} actively managed.`;

  // Default Action Cards derived from actual state
  let card1 = {
    tag: 'Action Required',
    tagColor: 'text-[#8B3F3F]',
    dotColor: 'bg-[#8B3F3F]',
    title: `${attentionContracts.length} ${attentionContracts.length === 1 ? 'contract needs' : 'contracts need'} attention`,
    desc: contracts.length === 0
      ? 'No contracts registered yet. Upload a contract to begin automated analysis.'
      : attentionContracts.length > 0
      ? 'Agreements with flagged risk terms, under review status, or pending analysis.'
      : 'All agreements are currently in good standing with low risk levels.',
    btnText: contracts.length === 0 ? '+ Upload Contract' : 'Review Contracts →',
    action: contracts.length === 0 ? onRequestUpload : () => onNavigate('contracts')
  };

  let card2 = {
    tag: 'Schedule',
    tagColor: 'text-[#9A6A32]',
    dotColor: 'bg-[#9A6A32]',
    title: `${upcomingObligations.length} ${upcomingObligations.length === 1 ? 'deadline' : 'deadlines'} coming up`,
    desc: upcomingObligations.length > 0
      ? 'Pending deliverables, compliance reports, and key obligation dates.'
      : 'No upcoming obligation deadlines pending at this time.',
    btnText: 'View Deadlines →',
    action: () => onNavigate('tasks')
  };

  let card3 = {
    tag: 'Notice Window',
    tagColor: 'text-[#3F4634]',
    dotColor: 'bg-[#3F4634]',
    title: `${renewingContracts.length} ${renewingContracts.length === 1 ? 'renewal date' : 'renewal dates'} tracked`,
    desc: renewingContracts.length > 0
      ? 'Agreements with upcoming renewal or expiration windows.'
      : 'No upcoming renewal or expiry dates on file.',
    btnText: 'View Watchlist →',
    action: () => onNavigate('watch')
  };

  // Role customization using deterministic live data
  if (accountType === 'BUSINESS') {
    if (businessRole === 'PROCUREMENT') {
      const procurementContracts = contracts.filter((c) => c.department === 'Procurement');
      card1 = {
        tag: 'Suppliers Active',
        tagColor: 'text-[#3F4634]',
        dotColor: 'bg-[#3F4634]',
        title: `${procurementContracts.length} supplier agreements`,
        desc: procurementContracts.length > 0
          ? 'Procurement vendor agreements and commercial service levels.'
          : 'No procurement agreements registered yet.',
        btnText: 'View Vendors →',
        action: () => onNavigate('vendors')
      };
      card2 = {
        tag: 'Deliverables',
        tagColor: 'text-[#9A6A32]',
        dotColor: 'bg-[#9A6A32]',
        title: `${upcomingObligations.length} deadlines scheduled`,
        desc: upcomingObligations.length > 0
          ? 'Upcoming vendor SLA audit deliverables and notice dates.'
          : 'No vendor deliverable deadlines currently due.',
        btnText: 'View Deadlines →',
        action: () => onNavigate('tasks')
      };
      card3 = {
        tag: 'Renewals',
        tagColor: 'text-[#8B3F3F]',
        dotColor: 'bg-[#8B3F3F]',
        title: `${renewingContracts.length} contracts with renewal dates`,
        desc: renewingContracts.length > 0
          ? 'Agreements with upcoming notice or expiration milestones.'
          : 'No renewal dates flagged.',
        btnText: 'View Renewal →',
        action: () => onNavigate('watch')
      };
    } else if (businessRole === 'FINANCE') {
      card1 = {
        tag: 'Committed Spend',
        tagColor: 'text-[#3F4634]',
        dotColor: 'bg-[#3F4634]',
        title: `${formatCurrency(totalValue)} total committed contract value`,
        desc: contracts.length > 0
          ? `Aggregated across ${contracts.length} active agreements on file.`
          : 'No active contract spend commitments registered yet.',
        btnText: 'View Spend Breakdown →',
        action: () => onNavigate('reports')
      };
      card2 = {
        tag: 'Obligations',
        tagColor: 'text-[#8B3F3F]',
        dotColor: 'bg-[#8B3F3F]',
        title: `${upcomingObligations.length} payment & audit deadlines`,
        desc: upcomingObligations.length > 0
          ? 'Financial disbursements and audit deliverables scheduled.'
          : 'No financial deadlines pending at this time.',
        btnText: 'View Payment Details →',
        action: () => onNavigate('tasks')
      };
      card3 = {
        tag: 'Finance Gate',
        tagColor: 'text-[#9A6A32]',
        dotColor: 'bg-[#9A6A32]',
        title: `${pendingApprovalsCount} sign-offs waiting for authorization`,
        desc: pendingApprovalsCount > 0
          ? 'Agreements pending departmental or executive sign-off.'
          : 'All contracts currently signed off.',
        btnText: 'Sign Off Now →',
        action: () => onNavigate('approvals')
      };
    } else if (businessRole === 'HR') {
      const hrContracts = contracts.filter((c) => c.department === 'HR');
      card1 = {
        tag: 'People Contracts',
        tagColor: 'text-[#3F4634]',
        dotColor: 'bg-[#3F4634]',
        title: `${hrContracts.length} HR & people agreements`,
        desc: hrContracts.length > 0
          ? 'Employment covenants, confidentiality terms, and offer schedules.'
          : 'No HR agreements on file.',
        btnText: 'View Agreements →',
        action: () => onNavigate('contracts')
      };
      card2 = {
        tag: 'Milestones',
        tagColor: 'text-[#9A6A32]',
        dotColor: 'bg-[#9A6A32]',
        title: `${upcomingObligations.length} milestones pending`,
        desc: upcomingObligations.length > 0
          ? 'Review windows and verification deliverables on record.'
          : 'No pending HR milestones.',
        btnText: 'View Milestones →',
        action: () => onNavigate('tasks')
      };
      card3 = {
        tag: 'Attention',
        tagColor: 'text-[#4F6B50]',
        dotColor: 'bg-[#4F6B50]',
        title: `${attentionContracts.length} agreements needing attention`,
        desc: attentionContracts.length > 0
          ? 'Agreements with flagged covenants requiring review.'
          : 'All agreements in good standing.',
        btnText: 'Review Agreements →',
        action: () => onNavigate('contracts')
      };
    } else if (businessRole === 'EMPLOYEE') {
      card1 = {
        tag: 'Submit Agreement',
        tagColor: 'text-[#3F4634]',
        dotColor: 'bg-[#3F4634]',
        title: 'Upload a contract for review',
        desc: 'Send a draft agreement to the Legal team for plain-language review and approval.',
        btnText: '+ Upload Contract Now',
        action: onRequestUpload
      };
      card2 = {
        tag: 'In Progress',
        tagColor: 'text-[#9A6A32]',
        dotColor: 'bg-[#9A6A32]',
        title: `${attentionContracts.length} agreements in progress`,
        desc: attentionContracts.length > 0
          ? 'Contracts currently undergoing clause parsing and legal review.'
          : 'No agreements currently undergoing review.',
        btnText: 'Check Review Status →',
        action: () => onNavigate('contracts')
      };
      card3 = {
        tag: 'Questions?',
        tagColor: 'text-[#4F6B50]',
        dotColor: 'bg-[#4F6B50]',
        title: 'Ask a question about any agreement',
        desc: 'Contractly explains confusing clauses in plain English before you commit.',
        btnText: 'Get Legal Help →',
        action: () => onNavigate('lawyers')
      };
    }
  }

  // Recommended step dynamically determined from actual database state
  let recommendedStep = {
    title: 'Upload your first contract to get started.',
    desc: 'Upload a PDF, Word document, or text file to extract plain-language explanations, spot risks, and track key dates.',
    action: onRequestUpload
  };

  if (contracts.length === 0) {
    recommendedStep = {
      title: 'Upload your first contract to get started.',
      desc: 'Upload a PDF, Word document, or text file to extract plain-language explanations, spot risks, and track key dates.',
      action: onRequestUpload
    };
  } else if (attentionContracts.length > 0) {
    const target = attentionContracts[0];
    recommendedStep = {
      title: `Review ${target.title} (${target.contractId})`,
      desc: `Flagged as ${target.riskLevel} risk level with status ${target.status.replace(/_/g, ' ')}. Review plain-language summary.`,
      action: () => onOpenContract(target.id)
    };
  } else if (upcomingObligations.length > 0) {
    const obl = upcomingObligations[0];
    recommendedStep = {
      title: `Fulfill upcoming obligation: ${obl.title}`,
      desc: `Due on ${obl.dueDate}. Upload verification evidence to complete.`,
      action: () => onNavigate('tasks')
    };
  } else {
    recommendedStep = {
      title: 'All agreements are current and in good standing.',
      desc: 'No urgent actions required across your active agreements.',
      action: () => onNavigate('contracts')
    };
  }

  // Filter or sort contracts based on role
  let displayContracts = contracts;
  if (businessRole === 'PROCUREMENT') {
    displayContracts = [...contracts].sort((a, b) => (b.department === 'Procurement' ? 1 : 0) - (a.department === 'Procurement' ? 1 : 0));
  } else if (businessRole === 'HR') {
    displayContracts = [...contracts].sort((a, b) => (b.department === 'HR' ? 1 : 0) - (a.department === 'HR' ? 1 : 0));
  }

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      {/* 1. Welcoming Hero Section */}
      <section className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] p-6 sm:p-8 md:py-8 md:px-10 text-center space-y-4 shadow-sm">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] text-xs text-[#3F4634] font-medium">
          <span>Contracts, handled with clarity</span>
          {accountType === 'BUSINESS' && (
            <span className="border-l border-[#DED6C8] pl-1.5 text-[#6F6A61] font-mono text-[11px]">
              Viewing as: {formatRoleName(businessRole)}
            </span>
          )}
        </div>

        <h1 className="text-3xl sm:text-4xl md:text-5xl font-serif font-bold text-[#242321] tracking-tight max-w-3xl mx-auto leading-tight">
          Your contracts, made easier.
        </h1>

        <p className="text-sm sm:text-base text-[#6F6A61] max-w-2xl mx-auto leading-relaxed">
          Upload a contract to understand important terms, spot potential risks, keep track of deadlines, and know what needs your attention — in plain, everyday language.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <Button onClick={onRequestUpload} variant="primary" size="lg" className="px-6 py-2.5 text-sm font-semibold">
            + Upload a Contract
          </Button>
          <Button onClick={() => onNavigate('contracts')} variant="secondary" size="lg" className="px-6 py-2.5 text-sm">
            View My Contracts
          </Button>
          <Button onClick={() => onNavigate('lawyers')} variant="outline" size="lg" className="px-6 py-2.5 text-sm">
            Get Legal Help
          </Button>
        </div>
      </section>

      {/* 2. Role-Tailored Attention Section */}
      <section className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 pb-1">
          <div>
            <h2 className="text-lg font-serif font-bold text-[#242321]">
              {greetingTitle}
            </h2>
            <p className="text-xs text-[#6F6A61] mt-0.5">
              {greetingSubtitle}
            </p>
          </div>
          {accountType === 'BUSINESS' && (
            <span className="text-[11px] text-[#3F4634] px-2 py-0.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] self-start sm:self-auto font-medium">
              Role: {formatRoleName(businessRole)}
            </span>
          )}
        </div>

        {/* 3 Action Cards (Deterministically derived from live data) */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-5 items-stretch">
          <div className="p-5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] flex flex-col h-full hover:border-[#3F4634]/50 transition-colors">
            <div className="flex-1 flex flex-col">
              <div className="flex items-center justify-between">
                <span className={`w-2 h-2 rounded-full ${card1.dotColor}`} />
                <span className={`text-[11px] font-mono font-medium ${card1.tagColor}`}>{card1.tag}</span>
              </div>
              <h3 className="text-base font-semibold text-[#242321] mt-2">
                {card1.title}
              </h3>
              <p className="text-xs text-[#6F6A61] mt-1.5 leading-relaxed">
                {card1.desc}
              </p>
            </div>
            <div className="pt-4 mt-auto">
              <Button
                onClick={card1.action}
                variant="primary"
                size="sm"
                className="w-full text-xs font-semibold"
              >
                {card1.btnText}
              </Button>
            </div>
          </div>

          <div className="p-5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] flex flex-col h-full hover:border-[#3F4634]/50 transition-colors">
            <div className="flex-1 flex flex-col">
              <div className="flex items-center justify-between">
                <span className={`w-2 h-2 rounded-full ${card2.dotColor}`} />
                <span className={`text-[11px] font-mono font-medium ${card2.tagColor}`}>{card2.tag}</span>
              </div>
              <h3 className="text-base font-semibold text-[#242321] mt-2">
                {card2.title}
              </h3>
              <p className="text-xs text-[#6F6A61] mt-1.5 leading-relaxed">
                {card2.desc}
              </p>
            </div>
            <div className="pt-4 mt-auto">
              <Button
                onClick={card2.action}
                variant="secondary"
                size="sm"
                className="w-full text-xs font-semibold"
              >
                {card2.btnText}
              </Button>
            </div>
          </div>

          <div className="p-5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] flex flex-col h-full hover:border-[#3F4634]/50 transition-colors">
            <div className="flex-1 flex flex-col">
              <div className="flex items-center justify-between">
                <span className={`w-2 h-2 rounded-full ${card3.dotColor}`} />
                <span className={`text-[11px] font-mono font-medium ${card3.tagColor}`}>{card3.tag}</span>
              </div>
              <h3 className="text-base font-semibold text-[#242321] mt-2">
                {card3.title}
              </h3>
              <p className="text-xs text-[#6F6A61] mt-1.5 leading-relaxed">
                {card3.desc}
              </p>
            </div>
            <div className="pt-4 mt-auto">
              <Button
                onClick={card3.action}
                variant="secondary"
                size="sm"
                className="w-full text-xs font-semibold"
              >
                {card3.btnText}
              </Button>
            </div>
          </div>
        </div>

        {/* Recommended Next Step Banner */}
        <div className="p-4 bg-[#F7EFE4]/80 border border-[#E5D2B8] rounded-[2px] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-start gap-3">
            <Lightbulb className="w-5 h-5 text-[#9A6A32] flex-shrink-0 mt-0.5" />
            <div>
              <span className="text-xs font-bold text-[#7A4D1A] uppercase tracking-wide">
                Recommended next step for {formatRoleName(businessRole)}
              </span>
              <p className="text-xs text-[#242321] font-medium mt-0.5">
                {recommendedStep.title}
              </p>
              <p className="text-[11px] text-[#6F6A61] mt-0.5">
                {recommendedStep.desc}
              </p>
            </div>
          </div>
          <Button
            onClick={recommendedStep.action}
            variant="primary"
            size="sm"
            className="shrink-0"
          >
            Take Action →
          </Button>
        </div>
      </section>

      {/* 3. First-Time User Experience: "How Contractly helps you" */}
      <section className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] p-6 space-y-5">
        <div className="border-b border-[#DED6C8] pb-3">
          <h2 className="text-base font-serif font-bold text-[#242321]">
            How Contractly helps you
          </h2>
          <p className="text-xs text-[#6F6A61] mt-0.5">
            Four simple steps to take full control of your contracts without legal headaches.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
          <div className="p-4 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] space-y-2">
            <div className="w-6 h-6 rounded-full bg-[#3F4634] text-[#FCFAF5] flex items-center justify-center font-mono font-bold text-xs">
              1
            </div>
            <h3 className="font-semibold text-sm text-[#242321]">Upload your contract</h3>
            <p className="text-[#6F6A61] leading-relaxed">
              Upload a PDF, Word document, or text file. It stays private and secure in your account.
            </p>
          </div>

          <div className="p-4 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] space-y-2">
            <div className="w-6 h-6 rounded-full bg-[#3F4634] text-[#FCFAF5] flex items-center justify-center font-mono font-bold text-xs">
              2
            </div>
            <h3 className="font-semibold text-sm text-[#242321]">Understand it</h3>
            <p className="text-[#6F6A61] leading-relaxed">
              We explain important terms in plain language and highlight potential concerns before you sign.
            </p>
          </div>

          <div className="p-4 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] space-y-2">
            <div className="w-6 h-6 rounded-full bg-[#3F4634] text-[#FCFAF5] flex items-center justify-center font-mono font-bold text-xs">
              3
            </div>
            <h3 className="font-semibold text-sm text-[#242321]">Stay on top of it</h3>
            <p className="text-[#6F6A61] leading-relaxed">
              We remind you about deadlines, renewals, and things you need to do so nothing slips through.
            </p>
          </div>

          <div className="p-4 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] space-y-2">
            <div className="w-6 h-6 rounded-full bg-[#3F4634] text-[#FCFAF5] flex items-center justify-center font-mono font-bold text-xs">
              4
            </div>
            <h3 className="font-semibold text-sm text-[#242321]">Take action</h3>
            <p className="text-[#6F6A61] leading-relaxed">
              Review suggested changes, request team approval, or talk to a verified lawyer when needed.
            </p>
          </div>
        </div>
      </section>

      {/* 4. Recent Contracts Section */}
      <section className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-[#DED6C8] pb-3">
          <div>
            <h2 className="text-base font-serif font-bold text-[#242321]">
              My Contracts
            </h2>
            <p className="text-xs text-[#6F6A61] mt-0.5">
              Click any agreement to view its plain-English summary, key dates, and important terms.
            </p>
          </div>
          <Button onClick={() => onNavigate('contracts')} variant="secondary" size="sm">
            View All Contracts ({contracts.length}) →
          </Button>
        </div>

        {displayContracts.length === 0 ? (
          <div className="p-8 text-center text-[#6F6A61] space-y-3">
            <div className="w-10 h-10 rounded-full bg-[#F7F3EA] border border-[#DED6C8] flex items-center justify-center mx-auto text-[#3F4634]">
              <FileText className="w-5 h-5 text-[#3F4634]" />
            </div>
            <div className="space-y-1">
              <h3 className="font-semibold text-sm text-[#242321]">You don&apos;t have any contracts yet</h3>
              <p className="text-xs max-w-sm mx-auto">
                Upload your first agreement to generate plain-language summaries, spot potential risks, and track key deadlines.
              </p>
            </div>
            <Button onClick={onRequestUpload} variant="primary" size="sm">
              + Upload a Contract
            </Button>
          </div>
        ) : (
          <div className="divide-y divide-[#DED6C8]">
            {displayContracts.slice(0, 4).map((contract) => (
              <div
                key={contract.id}
                onClick={() => onOpenContract(contract.id)}
                className="py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-[#F7F3EA] px-2 rounded-[2px] cursor-pointer transition-colors group"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-xs text-[#242321] group-hover:text-[#3F4634] transition-colors">
                      {contract.title}
                    </span>
                    <span className="text-[11px] font-mono text-[#6F6A61]">
                      ({contract.contractId})
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-xs text-[#6F6A61]">
                    <span>With: <strong className="text-[#242321]">{contract.counterparty}</strong></span>
                    <span>•</span>
                    <span>Dept: <strong className="text-[#242321]">{contract.department}</strong></span>
                    <span>•</span>
                    <span>Ends: <span className="font-mono">{contract.expiryDate}</span></span>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <div className="text-right hidden md:block">
                    <span className="text-[11px] block">
                      {contract.riskLevel === 'HIGH' || contract.riskLevel === 'CRITICAL' ? (
                        <span className="text-[#8B3F3F] font-medium">⚠️ Potential Concern</span>
                      ) : contract.riskLevel === 'MEDIUM' ? (
                        <span className="text-[#9A6A32] font-medium">Needs Attention</span>
                      ) : (
                        <span className="text-[#4F6B50] font-medium">Looks Good</span>
                      )}
                    </span>
                  </div>

                  <StatusPill status={contract.status} showExplanation={false} />
                  <Button
                    onClick={(e) => {
                      e.stopPropagation();
                      onOpenContract(contract.id);
                    }}
                    variant="secondary"
                    size="sm"
                  >
                    View
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* 5. Need Professional Advice Banner */}
      <section className="p-5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h3 className="font-serif font-bold text-sm text-[#242321]">
            Need help understanding or negotiating a contract?
          </h3>
          <p className="text-xs text-[#6F6A61] mt-0.5">
            Talk to a qualified, verified legal professional. Book a 45-minute consultation to review clauses, negotiate liability, or ask questions.
          </p>
        </div>
        <Button onClick={() => onNavigate('lawyers')} variant="primary" size="sm" className="shrink-0">
          Find a Lawyer →
        </Button>
      </section>
    </div>
  );
}
