'use client';

import React from 'react';
import { useContractly } from '@/context/contractly-context';
import { StatusPill } from '@/components/ui/status-pill';
import { Button } from '@/components/ui/button';

interface OverviewDashboardProps {
  onOpenContract: (id: string) => void;
  onRequestNew: () => void;
  onNavigateTab: (tab: string) => void;
}

export function OverviewDashboard({
  onOpenContract,
  onRequestNew,
  onNavigateTab
}: OverviewDashboardProps) {
  const { contracts, obligations, accountType } = useContractly();

  const totalValue = contracts.reduce((acc, c) => acc + c.value, 0);
  const activeCount = contracts.filter((c) => c.status === 'ACTIVE').length;
  const underReviewCount = contracts.filter((c) => c.status === 'UNDER_REVIEW' || c.status === 'NEGOTIATION').length;
  const pendingApprovalsCount = contracts.filter((c) => c.status === 'PENDING_APPROVAL').length;
  const attentionCount = contracts.filter((c) => c.riskLevel === 'HIGH' || c.riskLevel === 'CRITICAL').length;

  // Real upcoming obligations and deadlines
  const pendingObligations = obligations.filter(
    (o) => o.status !== 'FULFILLED' && o.status !== 'RESOLVED'
  );
  const nextDueObligation = [...pendingObligations].sort((a, b) =>
    (a.dueDate || '').localeCompare(b.dueDate || '')
  )[0];

  // Dynamic contract health distribution
  const totalContracts = contracts.length;
  const lowConcernCount = contracts.filter((c) => c.riskLevel === 'LOW').length;
  const mediumConcernCount = contracts.filter((c) => c.riskLevel === 'MEDIUM').length;
  const highConcernCount = contracts.filter((c) => c.riskLevel === 'HIGH' || c.riskLevel === 'CRITICAL').length;

  const lowPct = totalContracts > 0 ? Math.round((lowConcernCount / totalContracts) * 100) : 0;
  const medPct = totalContracts > 0 ? Math.round((mediumConcernCount / totalContracts) * 100) : 0;
  const highPct = totalContracts > 0 ? Math.round((highConcernCount / totalContracts) * 100) : 0;

  // Real upcoming milestone entries
  const upcomingMilestones: Array<{
    id: string;
    title: string;
    detail: string;
    date: string;
    badge: string;
    isOverdue: boolean;
  }> = [];

  for (const ob of pendingObligations.slice(0, 4)) {
    const isOverdue = ob.status === 'OVERDUE';
    upcomingMilestones.push({
      id: `ob-${ob.id}`,
      title: ob.title,
      detail: `${ob.obligeeParty || ob.contractTitle || 'Active Agreement'} • ${ob.obligorParty || 'Obligation'}`,
      date: ob.dueDate || 'Date Pending',
      badge: isOverdue ? 'Overdue' : 'Due Soon',
      isOverdue
    });
  }

  for (const c of contracts.filter((c) => Boolean(c.renewalDate || c.expiryDate)).slice(0, 2)) {
    const targetDate = c.renewalDate || c.expiryDate || '';
    upcomingMilestones.push({
      id: `c-${c.id}`,
      title: `${c.title} (Expiration / Renewal)`,
      detail: `With ${c.counterparty} • Notice Window: ${c.renewalNoticeDays || 30} days`,
      date: targetDate,
      badge: 'Milestone',
      isOverdue: false
    });
  }

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0
    }).format(val);
  };

  return (
    <div className="space-y-6">
      {/* Top Banner (Instruction 1 & 23) */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#DED6C8]">
        <div>
          <h1 className="text-xl font-serif font-bold text-[#242321]">
            Overview
          </h1>
          <p className="text-xs text-[#6F6A61] mt-1">
            Summary of active agreements, upcoming deadlines, and contracts that need your attention.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button onClick={onRequestNew} variant="primary" size="sm">
            + Upload Contract
          </Button>
        </div>
      </div>

      {/* KPI Blocks (Instruction 6: human-friendly, no DAG jargon) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px]">
          <span className="text-[10px] uppercase font-mono tracking-wider text-[#6F6A61]">
            Total Contracts
          </span>
          <div className="text-2xl font-serif font-bold text-[#242321] mt-1">{contracts.length}</div>
          <p className="text-[11px] text-[#6F6A61] mt-1">
            {activeCount} Active • {underReviewCount} Needs Review
          </p>
        </div>

        {accountType === 'BUSINESS' ? (
          <div className="p-4 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px]">
            <span className="text-[10px] uppercase font-mono tracking-wider text-[#6F6A61]">
              Committed Value
            </span>
            <div className="text-xl font-mono font-bold text-[#242321] mt-1">
              {formatCurrency(totalValue)}
            </div>
            <p className="text-[11px] text-[#6F6A61] mt-1">Across active agreements</p>
          </div>
        ) : (
          <div className="p-4 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px]">
            <span className="text-[10px] uppercase font-mono tracking-wider text-[#6F6A61]">
              Upcoming Tasks
            </span>
            <div className="text-2xl font-serif font-bold text-[#9A6A32] mt-1">
              {pendingObligations.length} {pendingObligations.length === 1 ? 'Deadline' : 'Deadlines'}
            </div>
            <p className="text-[11px] text-[#6F6A61] mt-1">
              {nextDueObligation?.dueDate
                ? `Next due: ${nextDueObligation.dueDate}`
                : 'No upcoming deadlines'}
            </p>
          </div>
        )}

        <div className="p-4 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px]">
          <span className="text-[10px] uppercase font-mono tracking-wider text-[#6F6A61]">
            Needs Attention
          </span>
          <div className="text-2xl font-serif font-bold text-[#9A6A32] mt-1">{attentionCount}</div>
          <p className="text-[11px] text-[#6F6A61] mt-1">Clauses to review</p>
        </div>

        <div className="p-4 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px]">
          <span className="text-[10px] uppercase font-mono tracking-wider text-[#6F6A61]">
            Waiting for Sign-Off
          </span>
          <div className="text-2xl font-serif font-bold text-[#3F4634] mt-1">
            {pendingApprovalsCount}
          </div>
          <p className="text-[11px] text-[#6F6A61] mt-1">Pending review steps</p>
        </div>
      </div>

      {/* Two Column Layout: Active Items & Guidance */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Contracts Requiring Attention */}
        <div className="lg:col-span-7 space-y-4">
          <div className="p-4 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-[#DED6C8]">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-[#242321] font-mono">
                Agreements Requiring Attention
              </h2>
              <button
                onClick={() => onNavigateTab('contracts')}
                className="text-xs text-[#3F4634] hover:underline font-medium"
              >
                View all →
              </button>
            </div>

            <div className="divide-y divide-[#DED6C8]">
              {contracts.length === 0 ? (
                <div className="py-6 text-center text-xs text-[#6F6A61]">
                  No contracts uploaded yet. Click &quot;+ Upload Contract&quot; to begin.
                </div>
              ) : contracts.filter((c) => c.riskLevel === 'HIGH' || c.riskLevel === 'CRITICAL' || c.status === 'UNDER_REVIEW').length === 0 ? (
                <div className="py-6 text-center text-xs text-[#2E5230]">
                  All active agreements are currently in good standing.
                </div>
              ) : (
                contracts
                  .filter((c) => c.riskLevel === 'HIGH' || c.riskLevel === 'CRITICAL' || c.status === 'UNDER_REVIEW')
                  .slice(0, 4)
                  .map((contract) => (
                    <div
                      key={contract.id}
                      onClick={() => onOpenContract(contract.id)}
                      className="py-3 flex items-center justify-between gap-3 hover:bg-[#F7F3EA]/70 transition-colors cursor-pointer px-1 rounded-[2px]"
                    >
                      <div>
                        <div className="font-semibold text-xs text-[#242321] hover:text-[#3F4634]">
                          {contract.title}
                        </div>
                        <div className="text-[11px] text-[#6F6A61] mt-0.5">
                          With: {contract.counterparty} • {contract.contractType}
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <StatusPill status={contract.status} />
                      </div>
                    </div>
                  ))
              )}
            </div>
          </div>

          {/* Upcoming Dates & Milestones */}
          <div className="p-4 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-[#DED6C8]">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-[#242321] font-mono">
                Upcoming Deadlines & Notice Dates
              </h2>
              <button
                onClick={() => onNavigateTab('watch')}
                className="text-xs text-[#3F4634] hover:underline font-medium"
              >
                Contract Health →
              </button>
            </div>

            <div className="space-y-2 text-xs">
              {upcomingMilestones.length === 0 ? (
                <div className="p-6 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-center text-xs text-[#6F6A61]">
                  <p className="font-semibold text-[#242321]">No upcoming deadlines recorded</p>
                  <p className="text-[11px] text-[#6F6A61] mt-1">
                    Obligations, delivery milestones, and renewal notice dates for your agreements will appear here.
                  </p>
                </div>
              ) : (
                upcomingMilestones.map((m) => (
                  <div
                    key={m.id}
                    className={`p-3 rounded-[2px] border flex items-start justify-between ${
                      m.isOverdue
                        ? 'bg-[#F7EDED]/60 border-[#E2BDBF]'
                        : 'bg-[#F7EFE4]/60 border-[#E5D2B8]'
                    }`}
                  >
                    <div>
                      <span className={`font-semibold ${m.isOverdue ? 'text-[#8B3F3F]' : 'text-[#9A6A32]'}`}>
                        {m.title}
                      </span>
                      <p className="text-[11px] text-[#6F6A61] mt-0.5">
                        {m.detail}
                      </p>
                    </div>
                    <span
                      className={`font-mono text-xs font-semibold shrink-0 ml-2 ${
                        m.isOverdue ? 'text-[#8B3F3F]' : 'text-[#9A6A32]'
                      }`}
                    >
                      {m.isOverdue ? 'Overdue' : m.date}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right: Contract Risk Summary & Quick Actions */}
        <div className="lg:col-span-5 space-y-4">
          <div className="p-4 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#242321] font-mono border-b border-[#DED6C8] pb-2">
              Contract Health Overview
            </h2>

            {totalContracts === 0 ? (
              <div className="py-4 text-center text-xs text-[#6F6A61]">
                No contracts recorded yet. Health distribution displays when contracts are uploaded.
              </div>
            ) : (
              <div className="space-y-3 text-xs">
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span className="text-[#2E5230] font-medium">Standard & Low Concern</span>
                    <span className="font-mono text-[#6F6A61]">
                      {lowPct}% ({lowConcernCount} {lowConcernCount === 1 ? 'contract' : 'contracts'})
                    </span>
                  </div>
                  <div className="h-2 bg-[#EFECE3] rounded-[1px] overflow-hidden">
                    <div className="h-full bg-[#4F6B50]" style={{ width: `${lowPct}%` }} />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span className="text-[#9A6A32] font-medium">Items Needing Review</span>
                    <span className="font-mono text-[#6F6A61]">
                      {medPct}% ({mediumConcernCount} {mediumConcernCount === 1 ? 'contract' : 'contracts'})
                    </span>
                  </div>
                  <div className="h-2 bg-[#EFECE3] rounded-[1px] overflow-hidden">
                    <div className="h-full bg-[#9A6A32]" style={{ width: `${medPct}%` }} />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span className="text-[#8B3F3F] font-medium">Potential Concerns Flagged</span>
                    <span className="font-mono text-[#6F6A61]">
                      {highPct}% ({highConcernCount} {highConcernCount === 1 ? 'contract' : 'contracts'})
                    </span>
                  </div>
                  <div className="h-2 bg-[#EFECE3] rounded-[1px] overflow-hidden">
                    <div className="h-full bg-[#8B3F3F]" style={{ width: `${highPct}%` }} />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Quick Shortcuts */}
          <div className="p-4 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-2">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#242321] font-mono border-b border-[#DED6C8] pb-2">
              Helpful Shortcuts
            </h2>
            <div className="space-y-1.5">
              <Button
                onClick={() => onNavigateTab('redlining')}
                variant="secondary"
                size="sm"
                className="w-full justify-start text-xs"
              >
                Inspect Proposed Changes (Edit & Compare)
              </Button>
              <Button
                onClick={() => onNavigateTab('playbook')}
                variant="secondary"
                size="sm"
                className="w-full justify-start text-xs"
              >
                Review Negotiation Rules
              </Button>
              <Button
                onClick={() => onNavigateTab('vendors')}
                variant="secondary"
                size="sm"
                className="w-full justify-start text-xs"
              >
                Check Vendor Status
              </Button>
              <Button
                onClick={() => onNavigateTab('lawyers')}
                variant="outline"
                size="sm"
                className="w-full justify-start text-xs"
              >
                Get Legal Help from a Verified Lawyer
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
