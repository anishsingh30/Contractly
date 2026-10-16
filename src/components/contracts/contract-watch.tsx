'use client';

import React, { useState } from 'react';
import { useContractly } from '@/context/contractly-context';
import { StatusPill } from '@/components/ui/status-pill';
import { Button } from '@/components/ui/button';
import { HelpTooltip } from '@/components/ui/help-tooltip';
import { ContractNotesPanel } from '@/components/contracts/contract-notes-panel';

interface ContractWatchProps {
  onBack?: () => void;
  onOpenDocument?: (contractId: string) => void;
}

export function ContractWatch({ onBack, onOpenDocument }: ContractWatchProps) {
  const {
    activeContract,
    uploadObligationEvidence,
    contracts,
    setActiveContractId,
    setActiveNav,
    hasPermission
  } = useContractly();

  const [selectedObligationId, setSelectedObligationId] = useState<string | null>(null);
  const [uploadFileName, setUploadFileName] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'UPCOMING' | 'ATTENTION' | 'PROBLEM'>('ALL');

  const contract = activeContract || contracts[0];

  const handleDocumentView = () => {
    if (contract?.id) {
      if (onOpenDocument) {
        onOpenDocument(contract.id);
      } else {
        setActiveContractId(contract.id);
        setActiveNav('contracts');
      }
    } else if (onBack) {
      onBack();
    }
  };

  if (!contract) {
    return (
      <div className="p-8 text-center text-[#6F6A61] bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3">
        <p className="font-semibold text-[#242321]">No contract available.</p>
        <p className="text-xs text-[#6F6A61]">Upload or select a contract to inspect contract health.</p>
        <Button
          onClick={() => {
            if (onBack) onBack();
            else setActiveNav('contracts');
          }}
          variant="primary"
          size="sm"
        >
          ← Return to My Contracts
        </Button>
      </div>
    );
  }

  const handleAttachEvidence = async (obligationId: string) => {
    if (!uploadFileName.trim()) return;
    await uploadObligationEvidence(obligationId, uploadFileName, selectedFile || undefined);
    setUploadFileName('');
    setSelectedFile(null);
    setSelectedObligationId(null);
  };

  const obligations = contract.obligations || [];

  const upcomingCount = obligations.filter((o) => o.status === 'UPCOMING' || o.status === 'DUE_SOON').length;
  const problemCount = obligations.filter((o) => o.status === 'POTENTIAL_NON_COMPLIANCE' || o.status === 'OVERDUE').length;
  const completedCount = obligations.filter((o) => o.status === 'FULFILLED' || o.status === 'RESOLVED').length;

  const filteredObligations = obligations.filter((o) => {
    if (statusFilter === 'UPCOMING') return o.status === 'UPCOMING' || o.status === 'DUE_SOON';
    if (statusFilter === 'PROBLEM') return o.status === 'POTENTIAL_NON_COMPLIANCE' || o.status === 'OVERDUE';
    if (statusFilter === 'ATTENTION') return o.status === 'DUE_SOON' || o.status === 'AT_RISK';
    return true;
  });

  return (
    <div className="space-y-6">
      {/* 1. Header with Document View Navigation & Contract Scope */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#DED6C8]">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              onClick={handleDocumentView}
              variant="secondary"
              size="sm"
              title={`View document for ${contract.title}`}
            >
              ← Document View
            </Button>
            <h1 className="text-xl font-serif font-bold text-[#242321]">
              Contract Health
            </h1>
            {contracts.length > 1 && (
              <div className="flex items-center gap-1.5 ml-2">
                <span className="text-[11px] text-[#6F6A61]">Scope:</span>
                <select
                  value={contract.id}
                  onChange={(e) => {
                    const sel = contracts.find((c) => c.id === e.target.value);
                    if (sel) {
                      setActiveContractId(sel.id);
                    }
                  }}
                  className="bg-[#F7F3EA] border border-[#DED6C8] text-xs font-semibold text-[#242321] px-2 py-0.5 rounded-[2px] focus:outline-none focus:border-[#3F4634]"
                >
                  {contracts.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.title}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
          <p className="text-xs text-[#6F6A61] mt-1">
            Keep track of deadlines, responsibilities, renewals, and potential problems for <strong>{contract.title}</strong>.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-[#6F6A61]">Next Important Date:</span>
          <span className="font-mono text-xs font-semibold text-[#9A6A32] px-2 py-0.5 bg-[#F7EFE4] border border-[#E5D2B8] rounded-[2px]">
            {contract.renewalDate || contract.expiryDate || 'No date set'}
          </span>
        </div>
      </div>

      {/* 2. Contract Health Status & KPI Cards */}
      {obligations.length === 0 && (!contract.risks || contract.risks.length === 0) ? (
        <div className="p-6 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-center text-[#6F6A61] space-y-1">
          <span className="text-[11px] font-mono font-medium px-2 py-0.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] text-[#6F6A61]">
            STATUS: NOT ENOUGH INFORMATION
          </span>
          <p className="text-xs text-[#242321] font-semibold mt-2">Not enough information to calculate health status</p>
          <p className="text-[11px] text-[#6F6A61]">
            No obligations or risk items have been registered for this contract yet. Health metrics will appear here once obligations or clause risks are added.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          {/* Good */}
          <div
            onClick={() => setStatusFilter(statusFilter === 'ALL' ? 'ALL' : 'ALL')}
            className="p-4 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] cursor-pointer hover:border-[#4F6B50] transition-colors"
          >
            <div className="flex items-center justify-between">
              <span className="w-2.5 h-2.5 rounded-full bg-[#4F6B50]" />
              <span className="text-[10px] font-mono font-medium text-[#4F6B50]">HEALTH: GOOD</span>
            </div>
            <div className="text-base font-semibold text-[#242321] mt-2">
              {completedCount > 0 ? `${completedCount} Completed` : problemCount === 0 ? 'On Track' : 'In Review'}
            </div>
            <p className="text-[11px] text-[#6F6A61] mt-1 leading-relaxed">
              {completedCount > 0 ? `${completedCount} deliverables verified.` : 'No critical issues detected.'}
            </p>
          </div>

          {/* Needs Attention */}
          <div
            onClick={() => setStatusFilter(statusFilter === 'ATTENTION' ? 'ALL' : 'ATTENTION')}
            className={`p-4 bg-[#FCFAF5] border rounded-[2px] cursor-pointer transition-colors ${
              statusFilter === 'ATTENTION' ? 'border-[#9A6A32] ring-1 ring-[#9A6A32]' : 'border-[#DED6C8] hover:border-[#9A6A32]'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="w-2.5 h-2.5 rounded-full bg-[#9A6A32]" />
              <span className="text-[10px] font-mono font-medium text-[#9A6A32]">ATTENTION</span>
            </div>
            <div className="text-base font-semibold text-[#242321] mt-2">
              {upcomingCount} Upcoming
            </div>
            <p className="text-[11px] text-[#6F6A61] mt-1 leading-relaxed">
              Deadlines or renewals requiring verification soon.
            </p>
          </div>

          {/* Potential Problems */}
          <div
            onClick={() => setStatusFilter(statusFilter === 'PROBLEM' ? 'ALL' : 'PROBLEM')}
            className={`p-4 bg-[#FCFAF5] border rounded-[2px] cursor-pointer transition-colors ${
              statusFilter === 'PROBLEM' ? 'border-[#8B3F3F] ring-1 ring-[#8B3F3F]' : 'border-[#DED6C8] hover:border-[#8B3F3F]'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="w-2.5 h-2.5 rounded-full bg-[#8B3F3F]" />
              <span className="text-[10px] font-mono font-medium text-[#8B3F3F]">PROBLEM</span>
            </div>
            <div className="text-base font-semibold text-[#242321] mt-2">
              {problemCount} Issues
            </div>
            <p className="text-[11px] text-[#6F6A61] mt-1 leading-relaxed">
              {problemCount > 0 ? 'Delinquent or breached obligations.' : 'Zero overdue items recorded.'}
            </p>
          </div>

          {/* Risk Level */}
          <div className="p-4 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px]">
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase font-mono tracking-wider text-[#6F6A61]">OVERALL RISK</span>
              <StatusPill status={contract.riskLevel} />
            </div>
            <div className="text-base font-semibold text-[#242321] mt-2">
              {contract.riskLevel} Risk Profile
            </div>
            <p className="text-[11px] text-[#6F6A61] mt-1 leading-relaxed">
              Derived from automated clause analysis &amp; contract terms.
            </p>
          </div>
        </div>
      )}

      {/* 3. Action Required & Obligations Table */}
      <div className="p-4 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-xs uppercase font-mono tracking-wider text-[#6F6A61]">
              Contract Obligations ({filteredObligations.length})
            </h2>
            <HelpTooltip text="Track operational obligations, deliverables, service levels, and renewal deadlines." />
          </div>

          <div className="flex gap-2">
            {(['ALL', 'UPCOMING', 'ATTENTION', 'PROBLEM'] as const).map((filter) => (
              <button
                key={filter}
                onClick={() => setStatusFilter(filter)}
                className={`px-2 py-0.5 rounded-[2px] text-xs font-mono transition-colors ${
                  statusFilter === filter
                    ? 'bg-[#3F4634] text-[#FCFAF5]'
                    : 'bg-[#F7F3EA] text-[#6F6A61] hover:text-[#242321]'
                }`}
              >
                {filter}
              </button>
            ))}
          </div>
        </div>

        {filteredObligations.length === 0 ? (
          <div className="p-6 text-center text-[#6F6A61] text-xs">
            No obligations matching the selected filter.
          </div>
        ) : (
          <div className="divide-y divide-[#DED6C8] border-t border-[#DED6C8]">
            {filteredObligations.map((ob) => (
              <div key={ob.id} className="py-3 flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <StatusPill status={ob.status} />
                    <span className="font-semibold text-xs text-[#242321]">{ob.title}</span>
                  </div>
                  <p className="text-xs text-[#6F6A61] leading-relaxed">{ob.description}</p>
                  <div className="flex gap-4 text-[11px] text-[#6F6A61] pt-1">
                    <span>Due: <strong>{ob.dueDate}</strong></span>
                    <span>Responsible: <strong>{ob.responsibleOwner || ob.obligorParty || 'Assigned Lead'}</strong></span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {hasPermission('obligations:update') && (
                    <Button
                      onClick={() => setSelectedObligationId(selectedObligationId === ob.id ? null : ob.id)}
                      variant="outline"
                      size="sm"
                    >
                      {selectedObligationId === ob.id ? 'Cancel' : 'Attach Proof'}
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 4. Attach Proof Modal / Expanded Row */}
      {selectedObligationId && (
        <div className="p-4 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] space-y-3">
          <h3 className="font-serif font-bold text-sm text-[#242321]">
            Attach Compliance Evidence
          </h3>
          <p className="text-xs text-[#6F6A61]">
            Provide documented verification or upload a supporting file (e.g. receipt, certificate, or milestone confirmation).
          </p>
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              type="text"
              placeholder="Evidence file title or description..."
              value={uploadFileName}
              onChange={(e) => setUploadFileName(e.target.value)}
              className="flex-1 bg-[#FCFAF5] border border-[#DED6C8] text-xs px-3 py-1.5 rounded-[2px] focus:outline-none focus:border-[#3F4634]"
            />
            <input
              type="file"
              onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
              className="text-xs text-[#6F6A61] file:mr-2 file:py-1 file:px-2 file:rounded-[2px] file:border file:border-[#DED6C8] file:text-xs file:bg-[#FCFAF5] file:text-[#242321]"
            />
            <Button
              onClick={() => handleAttachEvidence(selectedObligationId)}
              variant="primary"
              size="sm"
              disabled={!uploadFileName.trim()}
            >
              Submit Evidence
            </Button>
          </div>
        </div>
      )}

      {/* 5. Notes & Collaboration Panel */}
      <ContractNotesPanel contractId={contract.id} />
    </div>
  );
}
