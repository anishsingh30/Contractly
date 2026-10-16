'use client';

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useContractly } from '@/context/contractly-context';
import { StatusPill } from '@/components/ui/status-pill';
import { Button } from '@/components/ui/button';
import { HelpTooltip } from '@/components/ui/help-tooltip';
import { formatContractValue } from '@/lib/currency-formatter';
import {
  ClauseExplanation,
  ContractLifecycleSummary,
  ContractStatus,
  ContractIntelligenceData,
  ContractQASource,
  ContractQAResult
} from '@/types/contractly';
import {
  askContractQABackend,
  fetchContractLifecycleSummaryFromBackend,
  fetchContractIntelligenceFromBackend,
  reprocessContractInBackend,
  downloadContractVersionFile
} from '@/lib/api-client';

interface DocumentViewerProps {
  onBack: () => void;
  onOpenRedline: () => void;
  onOpenWatch: () => void;
}

export function DocumentViewer({ onBack, onOpenRedline, onOpenWatch }: DocumentViewerProps) {
  const {
    activeContract,
    deleteContract,
    hasPermission,
    transitionStatus,
    terminateContract,
    renewContract,
    uploadVersion,
    addToast
  } = useContractly();

  interface QAMessageItem {
    sender: 'user' | 'assistant';
    text: string;
    sources?: ContractQASource[];
    confidence?: string;
  }

  const [selectedClauseId, setSelectedClauseId] = useState<string>(
    activeContract?.clauses?.[0]?.id || ''
  );
  const [highlightedClauseId, setHighlightedClauseId] = useState<string | null>(null);
  const [filterFlaggedOnly, setFilterFlaggedOnly] = useState<boolean>(false);

  const flaggedSectionRef = useRef<HTMLDivElement>(null);
  const sectionsContainerRef = useRef<HTMLDivElement>(null);

  const [activeRightTab, setActiveRightTab] = useState<'intelligence' | 'understand' | 'lifecycle' | 'versions' | 'qa' | 'details'>(
    'intelligence'
  );

  const [qaQuery, setQaQuery] = useState('');
  const [isQaLoading, setIsQaLoading] = useState(false);
  const [qaMessages, setQaMessages] = useState<Array<QAMessageItem>>([
    {
      sender: 'assistant',
      text: activeContract ? `Hello! You can ask questions about "${activeContract.title}". Answers are strictly grounded in this contract's verified sections and terms.` : 'Hello! Ask questions about your contract.',
      sources: []
    }
  ]);

  // Intelligence State
  const [intelligenceData, setIntelligenceData] = useState<ContractIntelligenceData | null>(null);
  const [isLoadingIntelligence, setIsLoadingIntelligence] = useState(false);
  const [isReprocessing, setIsReprocessing] = useState(false);

  // Lifecycle Summary & Operations state
  const [lifecycleSummary, setLifecycleSummary] = useState<ContractLifecycleSummary | null>(null);
  const [isLoadingSummary, setIsLoadingSummary] = useState(false);
  const [isTerminating, setIsTerminating] = useState(false);
  const [terminationReason, setTerminationReason] = useState('');
  const [isRenewing, setIsRenewing] = useState(false);
  const [newExpiryInput, setNewExpiryInput] = useState(activeContract?.expiryDate || '');
  const [renewalNotes, setRenewalNotes] = useState('');

  // Version Upload state
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [versionSummaryText, setVersionSummaryText] = useState('');
  const [isUploadingVersion, setIsUploadingVersion] = useState(false);
  const [isDownloadingDoc, setIsDownloadingDoc] = useState(false);

  const handleDownloadVersion = async (versionId?: string, fallbackFilename?: string) => {
    if (!activeContract?.id) return;
    const targetVersionId = versionId || activeContract.versions?.[0]?.id;
    if (!targetVersionId) {
      addToast('Download Unavailable', 'No stored document version found for this contract.', 'warning');
      return;
    }
    setIsDownloadingDoc(true);
    try {
      const { blob, filename } = await downloadContractVersionFile(activeContract.id, targetVersionId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename || fallbackFilename || `${activeContract.contractId}_document.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      addToast('Download Started', `Downloading ${filename || 'contract document'}...`, 'success');
    } catch (err: unknown) {
      addToast('Download Failed', err instanceof Error ? err.message : 'Failed to download contract document.', 'danger');
    } finally {
      setIsDownloadingDoc(false);
    }
  };

  useEffect(() => {
    if (activeContract?.id) {
      setIsLoadingIntelligence(true);
      fetchContractIntelligenceFromBackend(activeContract.id)
        .then((res) => {
          setIntelligenceData(res);
          setIsLoadingIntelligence(false);
        })
        .catch(() => setIsLoadingIntelligence(false));
    }
  }, [activeContract?.id, activeContract?.version]);

  useEffect(() => {
    if (activeRightTab === 'lifecycle' && activeContract?.id) {
      setIsLoadingSummary(true);
      fetchContractLifecycleSummaryFromBackend(activeContract.id)
        .then((res) => {
          setLifecycleSummary(res);
          setIsLoadingSummary(false);
        })
        .catch(() => setIsLoadingSummary(false));
    }
  }, [activeRightTab, activeContract?.id, activeContract?.status]);

  const flaggedClauses = useMemo(() => {
    if (!activeContract?.clauses) return [];
    return activeContract.clauses.filter((c) => {
      if (c.potentialConcern && c.potentialConcern.trim().length > 0) return true;
      if (
        activeContract.risks &&
        activeContract.risks.some(
          (r: any) =>
            (r.clause_id && r.clause_id === c.id) ||
            (r.clauseId && r.clauseId === c.id) ||
            (r.section_number && r.section_number === c.sectionNumber) ||
            (r.sectionNumber && r.sectionNumber === c.sectionNumber)
        )
      ) {
        return true;
      }
      return false;
    });
  }, [activeContract]);

  const potentialConcernsCount = flaggedClauses.length;

  if (!activeContract) {
    return (
      <div className="p-8 text-center text-[#6F6A61] bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3">
        <p className="font-semibold text-[#242321]">No contract selected.</p>
        <p className="text-xs">Please choose an agreement from your contracts list.</p>
        <Button onClick={onBack} variant="primary" size="sm">
          ← Back to My Contracts
        </Button>
      </div>
    );
  }

  const selectedClause: ClauseExplanation | undefined =
    activeContract.clauses.find((c) => c.id === selectedClauseId) || activeContract.clauses[0];

  const scrollToClauseInContainer = (clauseId: string) => {
    const el = document.getElementById(`clause-${clauseId}`);
    const container = sectionsContainerRef.current;
    if (el && container) {
      const containerRect = container.getBoundingClientRect();
      const elRect = el.getBoundingClientRect();
      const relativeTop = elRect.top - containerRect.top + container.scrollTop;
      container.scrollTo({
        top: Math.max(0, relativeTop - 16),
        behavior: 'smooth'
      });
    }
  };

  const handleNavigateToFlaggedItems = () => {
    if (potentialConcernsCount === 0 || flaggedClauses.length === 0) return;

    // 1. Scroll the outer page to the Flagged Items section
    if (flaggedSectionRef.current) {
      flaggedSectionRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // 2. Select and highlight the first flagged clause
    const firstFlagged = flaggedClauses[0];
    if (firstFlagged) {
      setSelectedClauseId(firstFlagged.id);
      setHighlightedClauseId(firstFlagged.id);
      setTimeout(() => setHighlightedClauseId(null), 3000);

      // 3. Scroll the nested scrollable contract sections container to this clause
      setTimeout(() => {
        scrollToClauseInContainer(firstFlagged.id);
      }, 150);
    }
  };

  const handleSelectFlaggedItem = (clauseId: string) => {
    setSelectedClauseId(clauseId);
    setHighlightedClauseId(clauseId);
    setTimeout(() => setHighlightedClauseId(null), 3000);

    // Scroll nested container to clause
    scrollToClauseInContainer(clauseId);

    // Also bring the clause details tab into view on the right
    setActiveRightTab('understand');
  };

  const handleAskQuestion = async (prefilled?: string) => {
    const q = prefilled || qaQuery;
    if (!q.trim() || isQaLoading) return;

    const userMsg: QAMessageItem = { sender: 'user', text: q };
    setQaMessages((prev) => [...prev, userMsg]);
    setQaQuery('');
    setIsQaLoading(true);

    try {
      const backendResult = await askContractQABackend(activeContract.id, q);
      if (backendResult && !backendResult.error && backendResult.answer) {
        setQaMessages((prev) => [
          ...prev,
          {
            sender: 'assistant',
            text: backendResult.answer,
            sources: backendResult.sources || [],
            confidence: backendResult.confidence
          }
        ]);
      } else {
        const errorText = backendResult?.error || "I couldn't retrieve an answer at this time. Please ensure the backend AI service is running and configured.";
        setQaMessages((prev) => [
          ...prev,
          {
            sender: 'assistant',
            text: errorText,
            sources: []
          }
        ]);
      }
    } catch {
      setQaMessages((prev) => [
        ...prev,
        {
          sender: 'assistant',
          text: "An error occurred while communicating with the contract Q&A service.",
          sources: []
        }
      ]);
    } finally {
      setIsQaLoading(false);
    }
  };

  const handleExecuteTransition = async (targetStatus: string) => {
    await transitionStatus(activeContract.id, targetStatus as ContractStatus);
  };

  const handleExecuteTermination = async () => {
    if (!terminationReason.trim()) {
      addToast('Reason Required', 'Please enter a valid termination reason.', 'warning');
      return;
    }
    const ok = await terminateContract(activeContract.id, terminationReason.trim());
    if (ok) {
      setIsTerminating(false);
      setTerminationReason('');
    }
  };

  const handleExecuteRenewal = async () => {
    if (!newExpiryInput.trim()) {
      addToast('Date Required', 'Please provide the new expiration date.', 'warning');
      return;
    }
    const ok = await renewContract(activeContract.id, newExpiryInput.trim(), 12, renewalNotes);
    if (ok) {
      setIsRenewing(false);
      setRenewalNotes('');
    }
  };

  const handleExecuteVersionUpload = async () => {
    if (!uploadFile) {
      addToast('File Required', 'Please select a document file to upload.', 'warning');
      return;
    }
    setIsUploadingVersion(true);
    const ok = await uploadVersion(activeContract.id, uploadFile, versionSummaryText.trim() || 'Version revision');
    setIsUploadingVersion(false);
    if (ok) {
      setUploadFile(null);
      setVersionSummaryText('');
    }
  };

  const handleReprocessIntelligence = async () => {
    setIsReprocessing(true);
    const ok = await reprocessContractInBackend(activeContract.id);
    setIsReprocessing(false);
    if (ok) {
      addToast('Analysis Updated', 'Contract intelligence re-evaluated successfully.', 'success');
      const refreshed = await fetchContractIntelligenceFromBackend(activeContract.id);
      setIntelligenceData(refreshed);
    } else {
      addToast('Reprocess Failed', 'Could not reprocess contract intelligence.', 'danger');
    }
  };

  return (
    <div className="space-y-5">
      {/* 1. Header with Breadcrumb & Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#DED6C8]">
        <div className="flex items-center gap-3">
          <Button onClick={onBack} variant="secondary" size="sm">
            ← My Contracts
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-serif font-bold text-[#242321]">{activeContract.title}</h1>
              <span className="font-mono text-xs text-[#6F6A61]">({activeContract.contractId})</span>
            </div>
            <div className="flex items-center gap-2 mt-0.5 text-xs text-[#6F6A61]">
              <span>With: <strong className="text-[#242321]">{activeContract.counterparty}</strong></span>
              <span>•</span>
              <StatusPill status={activeContract.status} showExplanation={true} />
              <span>•</span>
              <span className="font-mono text-[11px] text-[#3F4634] font-semibold">{activeContract.version}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {hasPermission('contracts:delete') && (
            <Button
              onClick={async () => {
                if (window.confirm(`Are you sure you want to delete "${activeContract.title}"?`)) {
                  await deleteContract(activeContract.id);
                  onBack();
                }
              }}
              variant="outline"
              size="sm"
              className="text-[#8B3F3F] border-[#E2BDBF] hover:bg-[#FDF2F2]"
            >
              Delete Contract
            </Button>
          )}
          {activeContract.versions && activeContract.versions.length > 0 && (
            <Button
              onClick={() => handleDownloadVersion()}
              disabled={isDownloadingDoc}
              variant="outline"
              size="sm"
              title="Download original document file"
            >
              {isDownloadingDoc ? 'Downloading...' : '↓ Original Document'}
            </Button>
          )}
          <Button onClick={onOpenRedline} variant="secondary" size="sm">
            Edit & Compare ({activeContract.redlines.length})
          </Button>
          <Button onClick={onOpenWatch} variant="primary" size="sm">
            Contract Health ({activeContract.obligations.length})
          </Button>
        </div>
      </div>

      {/* 2. Plain-Language Summary Box */}
      <div className="p-4 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3">
        <div>
          <span className="text-[10px] uppercase font-mono tracking-wider text-[#6F6A61] block mb-1">
            What this contract is about
          </span>
          <p className="text-xs text-[#242321] leading-relaxed">
            This is a <strong>{activeContract.contractType}</strong> with <strong>{activeContract.counterparty}</strong> covering enterprise services. It establishes deliverables, payment commitments, renewal terms, and operational obligations.
          </p>
        </div>

        {/* IMPORTANT THINGS TO KNOW CARDS */}
        <div>
          <span className="text-[10px] uppercase font-mono tracking-wider text-[#3F4634] font-bold block mb-2">
            Important things to know
          </span>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs">
            <div className="p-2.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px]">
              <span className="text-[10px] text-[#6F6A61] block">Committed Value</span>
              <strong className="text-[#242321] text-xs mt-0.5 block font-mono">
                {formatContractValue(activeContract.value, activeContract.currency, activeContract.valueBasis)}
              </strong>
              <span className="text-[10px] text-[#6F6A61] truncate block" title={activeContract.calculationExplanation || undefined}>
                {activeContract.calculationExplanation || (activeContract.valueBasis === 'NOT_SPECIFIED' ? 'Not specified' : 'Contract term basis')}
              </span>
            </div>

            <div className="p-2.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px]">
              <span className="text-[10px] text-[#6F6A61] block">Active Stage</span>
              <strong className="text-[#242321] text-xs mt-0.5 block">{activeContract.status}</strong>
              <span className="text-[10px] text-[#6F6A61]">Version {activeContract.version}</span>
            </div>

            <div className="p-2.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px]">
              <span className="text-[10px] text-[#6F6A61] block">Contract Expiry</span>
              <strong className="text-[#242321] text-xs mt-0.5 block font-mono">{activeContract.expiryDate || 'Not specified'}</strong>
              <span className="text-[10px] text-[#6F6A61]">{activeContract.autoRenew ? 'Auto-renews unless notified' : 'Fixed end date'}</span>
            </div>

            <div className="p-2.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px]">
              <span className="text-[10px] text-[#6F6A61] block">Notice Window</span>
              <strong className="text-[#242321] text-xs mt-0.5 block font-mono">{activeContract.renewalDate || '30 days prior'}</strong>
              <span className="text-[10px] text-[#6F6A61]">{activeContract.renewalNoticeDays || 30} days notice required</span>
            </div>

            <div
              id="potential-concerns-card"
              role={potentialConcernsCount > 0 ? 'button' : undefined}
              tabIndex={potentialConcernsCount > 0 ? 0 : undefined}
              onClick={potentialConcernsCount > 0 ? handleNavigateToFlaggedItems : undefined}
              onKeyDown={(e) => {
                if ((e.key === 'Enter' || e.key === ' ') && potentialConcernsCount > 0) {
                  e.preventDefault();
                  handleNavigateToFlaggedItems();
                }
              }}
              className={`p-2.5 bg-[#F7EDED]/70 border border-[#E2BDBF] rounded-[2px] transition-all select-none ${
                potentialConcernsCount > 0
                  ? 'cursor-pointer hover:bg-[#F7EDED] hover:border-[#8B3F3F] hover:shadow-sm focus:outline-none focus:ring-2 focus:ring-[#8B3F3F]/50 focus:border-[#8B3F3F]'
                  : 'cursor-default'
              }`}
              title={
                potentialConcernsCount > 0
                  ? `Click to navigate to all ${potentialConcernsCount} flagged clauses`
                  : 'No potential concerns flagged'
              }
              aria-label={
                potentialConcernsCount > 0
                  ? `Potential concerns: ${potentialConcernsCount} ${
                      potentialConcernsCount === 1 ? 'item' : 'items'
                    } flagged. Click to view all flagged clauses.`
                  : 'Potential concerns: 0 items flagged'
              }
            >
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-[#8B3F3F] block font-medium">Potential concerns</span>
                {potentialConcernsCount > 0 && (
                  <span className="text-[10px] text-[#8B3F3F] font-mono underline">
                    View all ({potentialConcernsCount}) ↓
                  </span>
                )}
              </div>
              <strong className="text-[#8B3F3F] text-xs mt-0.5 block">
                {potentialConcernsCount} {potentialConcernsCount === 1 ? 'item' : 'items'} flagged
              </strong>
              <span className="text-[10px] text-[#8B3F3F]">
                {activeContract.riskLevel} Risk Profile
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* DEDICATED FLAGGED ITEMS SECTION */}
      {potentialConcernsCount > 0 ? (
        <div
          id="flagged-items-section"
          ref={flaggedSectionRef}
          tabIndex={-1}
          className="p-4 bg-[#FCFAF5] border border-[#E2BDBF] rounded-[2px] space-y-3 scroll-mt-6 focus:outline-none focus:ring-1 focus:ring-[#8B3F3F]/40"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2.5 border-b border-[#E2BDBF]">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-[#8B3F3F] inline-block" />
              <h2 className="text-sm font-bold text-[#8B3F3F]">
                Flagged Items ({potentialConcernsCount})
              </h2>
            </div>
            <span className="text-[11px] text-[#6F6A61]">
              {activeContract.riskLevel} Risk Profile · Click any flagged clause below to view and highlight its section in the agreement
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {flaggedClauses.map((clause) => {
              const isSelected = clause.id === selectedClauseId;
              const isHighlighted = clause.id === highlightedClauseId;
              return (
                <div
                  key={clause.id}
                  id={`flagged-summary-${clause.id}`}
                  role="button"
                  tabIndex={0}
                  onClick={() => handleSelectFlaggedItem(clause.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleSelectFlaggedItem(clause.id);
                    }
                  }}
                  className={`p-3 rounded-[2px] border cursor-pointer transition-all text-xs text-left ${
                    isHighlighted || isSelected
                      ? 'bg-[#F7EDED] border-[#8B3F3F] ring-1 ring-[#8B3F3F] shadow-sm'
                      : 'bg-[#FCFAF5] border-[#E2BDBF] hover:bg-[#FDF6F6] hover:border-[#8B3F3F]'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="font-mono text-xs font-bold text-[#242321] shrink-0">
                        {clause.sectionNumber}
                      </span>
                      <span className="font-semibold text-[#242321] truncate">
                        {clause.clauseTitle}
                      </span>
                    </div>
                    <StatusPill status={clause.riskLevel} />
                  </div>

                  <p className="text-[11px] text-[#6F6A61] line-clamp-2 font-serif italic mb-2 leading-relaxed">
                    &quot;{clause.originalText}&quot;
                  </p>

                  {clause.potentialConcern && (
                    <div className="text-[11px] text-[#8B3F3F] bg-[#F7EDED]/90 border border-[#E2BDBF]/60 p-2 rounded-[2px] leading-relaxed">
                      <span className="font-semibold block mb-0.5">Warning / Concern:</span>
                      <span>{clause.potentialConcern}</span>
                    </div>
                  )}

                  <div className="mt-2.5 flex items-center justify-between text-[11px]">
                    <span className="text-[#3F4634] font-medium hover:underline">
                      View in Contract Sections →
                    </span>
                    <span className="text-[#6F6A61] font-mono text-[10px]">
                      {clause.category}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <div
          id="flagged-items-empty-state"
          className="p-3 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] flex items-center justify-between text-xs text-[#6F6A61]"
        >
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#4F6B50]" />
            <span className="font-semibold text-[#242321]">No Flagged Items</span>
            <span>— All sections have standard or low concern ratings.</span>
          </div>
          <span className="text-[11px] text-[#4F6B50] font-medium">Standard Compliance</span>
        </div>
      )}

      {/* 3. Main Split View: Left Document Clauses, Right Insights & Operations */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 min-h-[500px]">
        {/* Left Pane: Document Text & Clauses */}
        <div className="lg:col-span-7 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] flex flex-col overflow-hidden">
          <div className="p-3 bg-[#F7F3EA] border-b border-[#DED6C8] flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-[#242321]">
                Contract Sections ({activeContract.clauses.length} identified)
              </span>
              {potentialConcernsCount > 0 && (
                <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-[#F7EDED] text-[#8B3F3F] border border-[#E2BDBF]">
                  {potentialConcernsCount} flagged
                </span>
              )}
            </div>
            <div className="flex items-center gap-1 text-[11px]">
              <button
                type="button"
                onClick={() => setFilterFlaggedOnly(false)}
                className={`px-2 py-0.5 rounded-[2px] transition-colors ${
                  !filterFlaggedOnly
                    ? 'bg-[#3F4634] text-[#FCFAF5] font-medium'
                    : 'text-[#6F6A61] hover:text-[#242321] hover:bg-[#EDE6D8]'
                }`}
              >
                All ({activeContract.clauses.length})
              </button>
              {potentialConcernsCount > 0 && (
                <button
                  type="button"
                  onClick={() => setFilterFlaggedOnly(true)}
                  className={`px-2 py-0.5 rounded-[2px] transition-colors ${
                    filterFlaggedOnly
                      ? 'bg-[#8B3F3F] text-[#FCFAF5] font-medium'
                      : 'text-[#8B3F3F] hover:bg-[#F7EDED]'
                  }`}
                >
                  Flagged Only ({potentialConcernsCount})
                </button>
              )}
            </div>
          </div>

          <div ref={sectionsContainerRef} className="flex-1 p-4 overflow-y-auto space-y-3 max-h-[540px]">
            {(filterFlaggedOnly ? flaggedClauses : activeContract.clauses).map((clause) => {
              const isSelected = clause.id === selectedClauseId;
              const isHighlighted = clause.id === highlightedClauseId;
              const hasRisk = clause.riskLevel === 'HIGH' || clause.riskLevel === 'CRITICAL' || !!clause.potentialConcern;
              return (
                <div
                  key={clause.id}
                  id={`clause-${clause.id}`}
                  onClick={() => setSelectedClauseId(clause.id)}
                  className={`p-3.5 rounded-[2px] border cursor-pointer transition-all ${
                    isSelected
                      ? 'bg-[#F7F3EA] border-[#3F4634] shadow-sm'
                      : isHighlighted
                      ? 'bg-[#F7EDED] border-[#8B3F3F] ring-2 ring-[#8B3F3F] shadow-sm'
                      : hasRisk
                      ? 'bg-[#FCFAF5] border-[#E2BDBF] hover:bg-[#FDF6F6]'
                      : 'bg-[#FCFAF5] border-[#DED6C8] hover:bg-[#F7F3EA]/50'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-[#242321]">
                        {clause.sectionNumber}
                      </span>
                      <span className="text-xs font-semibold text-[#242321]">
                        {clause.clauseTitle}
                      </span>
                    </div>
                    <StatusPill status={clause.riskLevel} />
                  </div>

                  <p className="text-xs text-[#6F6A61] line-clamp-2 font-serif leading-relaxed">
                    &quot;{clause.originalText}&quot;
                  </p>

                  {clause.potentialConcern && (
                    <div className="mt-2 text-[11px] text-[#8B3F3F] bg-[#F7EDED] border border-[#E2BDBF]/60 p-2 rounded-[2px] flex items-start gap-1.5 leading-relaxed">
                      <span className="font-bold text-[10px] uppercase tracking-wider shrink-0 mt-0.5">Warning:</span>
                      <span className="line-clamp-2">{clause.potentialConcern}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Pane: Multi-Tab Insights & Operations */}
        <div className="lg:col-span-5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] flex flex-col overflow-hidden">
          {/* Tabs */}
          <div className="flex border-b border-[#DED6C8] bg-[#F7F3EA] overflow-x-auto">
            <button
              onClick={() => setActiveRightTab('intelligence')}
              className={`py-2 px-3 text-xs font-medium text-center border-b-2 whitespace-nowrap transition-colors ${
                activeRightTab === 'intelligence'
                  ? 'border-[#3F4634] text-[#3F4634] bg-[#FCFAF5]'
                  : 'border-transparent text-[#6F6A61] hover:text-[#242321]'
              }`}
            >
              Intelligence
            </button>
            <button
              onClick={() => setActiveRightTab('understand')}
              className={`py-2 px-3 text-xs font-medium text-center border-b-2 whitespace-nowrap transition-colors ${
                activeRightTab === 'understand'
                  ? 'border-[#3F4634] text-[#3F4634] bg-[#FCFAF5]'
                  : 'border-transparent text-[#6F6A61] hover:text-[#242321]'
              }`}
            >
              Clause Terms
            </button>
            <button
              onClick={() => setActiveRightTab('lifecycle')}
              className={`py-2 px-3 text-xs font-medium text-center border-b-2 whitespace-nowrap transition-colors ${
                activeRightTab === 'lifecycle'
                  ? 'border-[#3F4634] text-[#3F4634] bg-[#FCFAF5]'
                  : 'border-transparent text-[#6F6A61] hover:text-[#242321]'
              }`}
            >
              Lifecycle & State
            </button>
            <button
              onClick={() => setActiveRightTab('versions')}
              className={`py-2 px-3 text-xs font-medium text-center border-b-2 whitespace-nowrap transition-colors ${
                activeRightTab === 'versions'
                  ? 'border-[#3F4634] text-[#3F4634] bg-[#FCFAF5]'
                  : 'border-transparent text-[#6F6A61] hover:text-[#242321]'
              }`}
            >
              Versions ({activeContract.versions?.length || 1})
            </button>
            <button
              onClick={() => setActiveRightTab('qa')}
              className={`py-2 px-3 text-xs font-medium text-center border-b-2 whitespace-nowrap transition-colors ${
                activeRightTab === 'qa'
                  ? 'border-[#3F4634] text-[#3F4634] bg-[#FCFAF5]'
                  : 'border-transparent text-[#6F6A61] hover:text-[#242321]'
              }`}
            >
              Q&A
            </button>
            <button
              onClick={() => setActiveRightTab('details')}
              className={`py-2 px-3 text-xs font-medium text-center border-b-2 whitespace-nowrap transition-colors ${
                activeRightTab === 'details'
                  ? 'border-[#3F4634] text-[#3F4634] bg-[#FCFAF5]'
                  : 'border-transparent text-[#6F6A61] hover:text-[#242321]'
              }`}
            >
              Details
            </button>
          </div>

          {/* Right Pane Content */}
          <div className="flex-1 p-4 overflow-y-auto">
            {/* TAB: Contract Intelligence & Overview */}
            {activeRightTab === 'intelligence' && (
              <div className="space-y-4 text-xs">
                {/* Processing Status Banner */}
                <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-[#242321]">
                        {isLoadingIntelligence
                          ? 'Analyzing contract...'
                          : intelligenceData?.parser_status === 'COMPLETED'
                          ? 'Analysis complete.'
                          : intelligenceData?.parser_status === 'FAILED'
                          ? "We couldn't analyze this document."
                          : 'Not enough information.'}
                      </span>
                      {intelligenceData?.parser_status && (
                        <span className="font-mono text-[10px] px-1.5 py-0.5 bg-[#EDE6D8] rounded text-[#242321]">
                          {intelligenceData.parser_status}
                        </span>
                      )}
                    </div>
                    {intelligenceData && (
                      <p className="text-[11px] text-[#6F6A61] mt-0.5">
                        {intelligenceData.page_count} {intelligenceData.page_count === 1 ? 'page' : 'pages'} · {intelligenceData.word_count.toLocaleString()} words · {intelligenceData.clauses?.length || 0} structured clauses
                      </p>
                    )}
                  </div>
                  <Button
                    onClick={handleReprocessIntelligence}
                    disabled={isReprocessing || isLoadingIntelligence}
                    variant="secondary"
                    size="sm"
                  >
                    {isReprocessing ? 'Processing...' : '↻ Reprocess'}
                  </Button>
                </div>

                {intelligenceData?.processing_error && (
                  <div className="p-2.5 bg-[#F7EDED] border border-[#E2BDBF] rounded-[2px] text-[#8B3F3F] text-[11px]">
                    <strong>Processing Note:</strong> {intelligenceData.processing_error}
                  </div>
                )}

                {/* Risk Score Breakdown */}
                <div className="p-3 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-[#242321]">Risk Profile Breakdown</span>
                    {intelligenceData?.risk_score_breakdown && (
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono font-bold text-xs">
                          {intelligenceData.risk_score_breakdown.composite_risk_score}/100
                        </span>
                        <StatusPill status={intelligenceData.risk_score_breakdown.risk_level} />
                      </div>
                    )}
                  </div>
                  <p className="text-[11px] text-[#6F6A61] leading-relaxed">
                    {intelligenceData?.risk_score_breakdown?.explanation ||
                      (activeContract.risks?.length === 0 ? 'No potential issues detected.' : 'Not enough information.')}
                  </p>
                </div>

                {/* Identified Parties */}
                <div className="space-y-1.5">
                  <span className="font-semibold text-[#242321] block">Identified Contract Parties</span>
                  {intelligenceData?.parties && intelligenceData.parties.length > 0 ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {intelligenceData.parties.map((p, idx) => (
                        <div key={idx} className="p-2 bg-[#F7F3EA]/70 border border-[#DED6C8] rounded-[2px]">
                          <span className="text-[10px] text-[#6F6A61] uppercase block">{p.role}</span>
                          <strong className="text-xs text-[#242321] block mt-0.5">{p.name}</strong>
                          {p.source && <span className="text-[9px] text-[#8C8275]">{p.source}</span>}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[#6F6A61] italic text-[11px]">Not enough information to identify parties deterministically.</p>
                  )}
                </div>

                {/* Important Dates */}
                <div className="space-y-1.5">
                  <span className="font-semibold text-[#242321] block">Important Dates & Milestones</span>
                  {intelligenceData?.candidate_dates && intelligenceData.candidate_dates.length > 0 ? (
                    <div className="space-y-1.5 max-h-36 overflow-y-auto">
                      {intelligenceData.candidate_dates.map((d, idx) => (
                        <div key={idx} className="p-2 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] flex items-center justify-between">
                          <div>
                            <span className="font-mono text-xs font-bold text-[#242321]">{d.date_str}</span>
                            <span className="text-[10px] text-[#6F6A61] ml-2">({d.date_type.replace('_', ' ')})</span>
                          </div>
                          {d.section_number && (
                            <span className="font-mono text-[10px] text-[#3F4634]">{d.section_number}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[#6F6A61] italic text-[11px]">No specific dates identified in document text.</p>
                  )}
                </div>

                {/* Actionable Obligations Detected */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-[#242321]">Obligation Candidates</span>
                    <span className="text-[10px] text-[#6F6A61]">
                      {intelligenceData?.obligation_candidates?.length || 0} candidate(s)
                    </span>
                  </div>
                  {intelligenceData?.obligation_candidates && intelligenceData.obligation_candidates.length > 0 ? (
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      {intelligenceData.obligation_candidates.map((ob, idx) => (
                        <div key={idx} className="p-2.5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-1">
                          <div className="flex items-center justify-between">
                            <span className="font-medium text-[#242321]">{ob.title}</span>
                            <span className="text-[9px] px-1.5 py-0.5 bg-[#F7F3EA] rounded border border-[#DED6C8] text-[#6F6A61]">
                              {ob.responsible_party}
                            </span>
                          </div>
                          <p className="text-[11px] text-[#6F6A61] font-serif leading-relaxed line-clamp-2">
                            &quot;{ob.source_text}&quot;
                          </p>
                          {ob.section_number && (
                            <div className="flex items-center justify-between text-[10px] text-[#8C8275] pt-0.5">
                              <span>Source: {ob.section_number}</span>
                              <span className="font-mono">{ob.frequency}</span>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[#6F6A61] italic text-[11px]">No actionable imperative commitments detected.</p>
                  )}
                </div>
              </div>
            )}

            {/* TAB 1: Clause Explanation */}
            {activeRightTab === 'understand' && selectedClause && (
              <div className="space-y-4 text-xs">
                <div className="border-b border-[#DED6C8] pb-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[10px] text-[#6F6A61] uppercase">
                      {selectedClause.category} Terms
                    </span>
                    <StatusPill status={selectedClause.riskLevel} />
                  </div>
                  <h3 className="text-sm font-semibold text-[#242321] mt-1">
                    {selectedClause.sectionNumber}: {selectedClause.clauseTitle}
                  </h3>
                </div>

                <div>
                  <h4 className="text-[11px] font-medium text-[#6F6A61] uppercase tracking-wide mb-1">
                    Original wording in contract
                  </h4>
                  <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] font-serif italic text-xs leading-relaxed text-[#242321]">
                    &quot;{selectedClause.originalText}&quot;
                  </div>
                </div>

                <div>
                  <h4 className="text-[11px] font-medium text-[#3F4634] uppercase tracking-wide mb-1 font-bold">
                    Plain-English explanation
                  </h4>
                  <p className="p-3 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-xs text-[#242321] leading-relaxed">
                    {selectedClause.plainLanguage}
                  </p>
                </div>

                <div>
                  <h4 className="text-[11px] font-medium text-[#6F6A61] uppercase tracking-wide mb-1">
                    Why this matters
                  </h4>
                  <p className="p-3 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-xs text-[#242321] leading-relaxed">
                    {selectedClause.whyItMatters}
                  </p>
                </div>

                {selectedClause.potentialConcern && (
                  <div>
                    <h4 className="text-[11px] font-medium text-[#8B3F3F] uppercase tracking-wide mb-1 font-bold">
                      Potential concern identified
                    </h4>
                    <div className="p-3 bg-[#F7EDED] border border-[#E2BDBF] rounded-[2px] text-xs text-[#8B3F3F] leading-relaxed">
                      {selectedClause.potentialConcern}
                    </div>
                  </div>
                )}

                <div className="pt-2 border-t border-[#DED6C8]">
                  <h4 className="text-[11px] font-medium text-[#242321] uppercase tracking-wide mb-2 font-bold">
                    What you can do
                  </h4>
                  {selectedClause.suggestedAction && (
                    <p className="text-xs text-[#6F6A61] mb-2 leading-relaxed">
                      {selectedClause.suggestedAction}
                    </p>
                  )}
                  <div className="flex gap-2">
                    <Button onClick={onOpenRedline} variant="primary" size="sm" className="text-xs">
                      Suggest a Change
                    </Button>
                    <Button onClick={() => setActiveRightTab('qa')} variant="secondary" size="sm" className="text-xs">
                      Ask About This
                    </Button>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: Lifecycle State Machine & Summary */}
            {activeRightTab === 'lifecycle' && (
              <div className="space-y-4 text-xs">
                <div className="border-b border-[#DED6C8] pb-2">
                  <span className="text-[10px] font-mono uppercase text-[#6F6A61]">
                    Where is this contract now?
                  </span>
                  <div className="flex items-center justify-between mt-1">
                    <h3 className="text-sm font-bold text-[#242321]">{activeContract.status}</h3>
                    <StatusPill status={activeContract.status} />
                  </div>
                </div>

                {/* Health & Renewal Assessment */}
                <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-[#242321]">Contract Health</span>
                    <span className="font-mono font-bold text-[11px] text-[#3F4634]">
                      {lifecycleSummary?.healthStatus || 'EVALUATING'}
                    </span>
                  </div>
                  <p className="text-[#6F6A61] text-[11px] leading-relaxed">
                    {lifecycleSummary?.healthReason || 'Assessment derived from live risk levels and obligations.'}
                  </p>

                  <div className="pt-2 border-t border-[#DED6C8] flex items-center justify-between">
                    <span className="text-[#6F6A61]">Renewal Status</span>
                    <span className="font-mono text-[#9A6A32] font-semibold">
                      {lifecycleSummary?.renewalStatus || 'Renewal information unavailable'}
                    </span>
                  </div>
                  {lifecycleSummary?.daysUntilExpiry !== null && lifecycleSummary?.daysUntilExpiry !== undefined && (
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-[#6F6A61]">Days until expiration:</span>
                      <span className="font-mono font-bold text-[#242321]">{lifecycleSummary.daysUntilExpiry} days</span>
                    </div>
                  )}
                </div>

                {/* Next Permitted Lifecycle Transitions */}
                <div className="space-y-2 pt-1 border-t border-[#DED6C8]">
                  <span className="text-[10px] font-mono uppercase text-[#6F6A61] block">
                    What needs to happen next?
                  </span>
                  {hasPermission('contracts:transition') ? (
                    <div className="flex flex-wrap gap-2">
                      {(lifecycleSummary?.allowedTransitions || []).map((st) => (
                        <Button
                          key={st}
                          onClick={() => handleExecuteTransition(st)}
                          variant="secondary"
                          size="sm"
                          className="text-xs"
                        >
                          → Transition to {st}
                        </Button>
                      ))}
                      {(lifecycleSummary?.allowedTransitions || []).length === 0 && (
                        <p className="text-[#6F6A61] text-xs italic">
                          Contract has reached a terminal or locked state ({activeContract.status}).
                        </p>
                      )}
                    </div>
                  ) : (
                    <p className="text-[#6F6A61] text-xs italic">
                      You do not have permission to transition lifecycle status.
                    </p>
                  )}
                </div>

                {/* Renewal & Termination Operations */}
                <div className="pt-3 border-t border-[#DED6C8] space-y-3">
                  <span className="text-[10px] font-mono uppercase text-[#6F6A61] block">
                    Lifecycle Actions
                  </span>
                  <div className="flex gap-2">
                    {hasPermission('contracts:renew') && (
                      <Button
                        onClick={() => setIsRenewing(!isRenewing)}
                        variant="primary"
                        size="sm"
                        className="text-xs flex-1"
                        disabled={activeContract.status === 'TERMINATED'}
                      >
                        {isRenewing ? 'Cancel Renewal' : 'Renew Agreement'}
                      </Button>
                    )}
                    {hasPermission('contracts:terminate') && (
                      <Button
                        onClick={() => setIsTerminating(!isTerminating)}
                        variant="outline"
                        size="sm"
                        className="text-xs flex-1 text-[#8B3F3F] border-[#E2BDBF]"
                        disabled={activeContract.status === 'TERMINATED'}
                      >
                        {isTerminating ? 'Cancel' : 'Terminate'}
                      </Button>
                    )}
                  </div>

                  {/* Renewal Form */}
                  {isRenewing && (
                    <div className="p-3 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-2">
                      <h4 className="font-semibold text-xs text-[#242321]">Execute Contract Renewal</h4>
                      <div>
                        <label className="text-[10px] text-[#6F6A61] block mb-1">New Expiration Date (YYYY-MM-DD):</label>
                        <input
                          type="date"
                          value={newExpiryInput}
                          onChange={(e) => setNewExpiryInput(e.target.value)}
                          className="w-full bg-[#F7F3EA] border border-[#DED6C8] px-2 py-1 rounded-[2px] text-xs"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-[#6F6A61] block mb-1">Renewal Notes:</label>
                        <input
                          type="text"
                          value={renewalNotes}
                          onChange={(e) => setRenewalNotes(e.target.value)}
                          placeholder="e.g. Executed 12-month standard extension"
                          className="w-full bg-[#F7F3EA] border border-[#DED6C8] px-2 py-1 rounded-[2px] text-xs"
                        />
                      </div>
                      <Button onClick={handleExecuteRenewal} variant="primary" size="sm" className="w-full text-xs">
                        Confirm Renewal
                      </Button>
                    </div>
                  )}

                  {/* Termination Form */}
                  {isTerminating && (
                    <div className="p-3 bg-[#F7EDED] border border-[#E2BDBF] rounded-[2px] space-y-2">
                      <h4 className="font-semibold text-xs text-[#8B3F3F]">Controlled Contract Termination</h4>
                      <div>
                        <label className="text-[10px] text-[#8B3F3F] block mb-1">Termination Reason (Mandatory):</label>
                        <textarea
                          rows={2}
                          value={terminationReason}
                          onChange={(e) => setTerminationReason(e.target.value)}
                          placeholder="State the legal or commercial basis for termination..."
                          className="w-full bg-[#FCFAF5] border border-[#E2BDBF] px-2 py-1 rounded-[2px] text-xs text-[#242321]"
                        />
                      </div>
                      <Button onClick={handleExecuteTermination} variant="primary" size="sm" className="w-full text-xs bg-[#8B3F3F] hover:bg-[#6E3030]">
                        Confirm Termination
                      </Button>
                    </div>
                  )}
                </div>

                {/* Display Termination Info if Terminated */}
                {activeContract.status === 'TERMINATED' && (
                  <div className="p-3 bg-[#F7EDED] border border-[#E2BDBF] rounded-[2px] text-xs space-y-1">
                    <span className="font-bold text-[#8B3F3F]">Contract is Terminated</span>
                    <p className="text-[#8B3F3F]">Effective: {activeContract.terminationDate || 'Recorded'}</p>
                    <p className="text-[#6F6A61] italic">Reason: {activeContract.terminationReason || 'Not stated'}</p>
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: Versions & Revision History */}
            {activeRightTab === 'versions' && (
              <div className="space-y-4 text-xs">
                <div className="flex items-center justify-between border-b border-[#DED6C8] pb-2">
                  <h3 className="font-semibold text-xs text-[#242321]">
                    Document Version History
                  </h3>
                  <span className="text-[11px] font-mono text-[#6F6A61]">
                    Current: {activeContract.version}
                  </span>
                </div>

                {/* Versions List */}
                <div className="space-y-2.5">
                  {(activeContract.versions || []).map((v) => (
                    <div
                      key={v.id}
                      className="p-3 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-bold text-xs text-[#242321]">
                          {v.versionNumber}
                        </span>
                        <span className="text-[10px] text-[#6F6A61]">{v.createdAt}</span>
                      </div>
                      <p className="text-[#242321] text-[11px]">{v.changeSummary || 'Version record'}</p>
                      <div className="flex items-center justify-between pt-1 border-t border-[#DED6C8]/60 text-[10px] text-[#6F6A61] font-mono">
                        <span>SHA: {v.sha256Checksum?.substring(0, 12)}...</span>
                        <div className="flex items-center gap-2">
                          <span>{Math.round(v.fileByteSize / 1024)} KB</span>
                          <button
                            type="button"
                            onClick={() => handleDownloadVersion(v.id)}
                            className="text-[#3F4634] hover:underline font-semibold"
                            title="Download document file"
                          >
                            ↓ Download
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}

                  {(!activeContract.versions || activeContract.versions.length === 0) && (
                    <div className="p-3 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-1">
                      <span className="font-mono font-bold text-xs text-[#242321]">v1.0 (Initial Ingestion)</span>
                      <p className="text-[11px] text-[#6F6A61]">Initial automated parsing and clause extraction.</p>
                    </div>
                  )}
                </div>

                {/* Upload Revised Version Form */}
                {hasPermission('contracts:create') && (
                  <div className="pt-3 border-t border-[#DED6C8] space-y-2">
                    <span className="text-[10px] font-mono uppercase text-[#6F6A61] block">
                      + Upload Revised Version
                    </span>
                    <input
                      type="file"
                      accept=".pdf,.docx,.txt"
                      onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                      className="text-xs file:mr-2 file:py-1 file:px-2 file:rounded-[2px] file:border file:border-[#DED6C8] file:bg-[#F7F3EA] file:text-xs"
                    />
                    <input
                      type="text"
                      value={versionSummaryText}
                      onChange={(e) => setVersionSummaryText(e.target.value)}
                      placeholder="Summary of changes (e.g. Post-negotiation redline draft)"
                      className="w-full bg-[#F7F3EA] border border-[#DED6C8] px-2.5 py-1 text-xs rounded-[2px]"
                    />
                    <Button
                      onClick={handleExecuteVersionUpload}
                      disabled={isUploadingVersion || !uploadFile}
                      variant="primary"
                      size="sm"
                      className="w-full text-xs"
                    >
                      {isUploadingVersion ? 'Uploading...' : 'Save New Version'}
                    </Button>
                  </div>
                )}
              </div>
            )}

            {/* TAB 4: Ask About This Contract */}
            {activeRightTab === 'qa' && (
              <div className="flex flex-col h-full space-y-3">
                <div className="border-b border-[#DED6C8] pb-2 flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-xs text-[#242321]">
                      Ask about this contract
                    </h3>
                    <p className="text-[11px] text-[#6F6A61]">
                      Grounded Q&amp;A based exclusively on this contract&apos;s verified clauses and terms.
                    </p>
                  </div>
                  <span className="text-[10px] font-mono bg-[#E8EFE6] text-[#3F4634] border border-[#CCDBC8] px-1.5 py-0.5 rounded-[2px]">
                    Strictly Grounded
                  </span>
                </div>

                <div className="flex-1 overflow-y-auto space-y-2.5 pr-1 max-h-80">
                  {qaMessages.map((msg, i) => (
                    <div
                      key={i}
                      className={`p-3 rounded-[2px] text-xs ${
                        msg.sender === 'user'
                          ? 'bg-[#EFECE3] text-[#242321] ml-4 border border-[#DED6C8]'
                          : 'bg-[#FCFAF5] text-[#242321] mr-2 border border-[#DED6C8]'
                      }`}
                    >
                      <p className="leading-relaxed whitespace-pre-wrap">{msg.text}</p>
                      
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="mt-2.5 pt-2 border-t border-[#DED6C8]/60 space-y-1.5">
                          <span className="text-[10px] uppercase font-mono tracking-wider text-[#6F6A61] block font-semibold">
                            Verified Sources ({msg.sources.length}):
                          </span>
                          <div className="space-y-1">
                            {msg.sources.map((src, srcIdx) => (
                              <button
                                key={srcIdx}
                                type="button"
                                onClick={() => {
                                  if (src.clause_id) {
                                    setSelectedClauseId(src.clause_id);
                                    addToast(
                                      `Navigated to ${src.section || 'Clause'}`,
                                      `Viewing: ${src.title || 'Clause Details'}`,
                                      'info'
                                    );
                                  }
                                }}
                                className="w-full text-left p-1.5 bg-[#F7F3EA] hover:bg-[#EFECE3] border border-[#DED6C8] rounded-[2px] transition-colors group cursor-pointer"
                              >
                                <div className="flex items-center justify-between">
                                  <span className="font-semibold text-[11px] text-[#3F4634] group-hover:underline">
                                    Based on {src.section ? `${src.section} — ` : ''}{src.title || 'Clause'}
                                  </span>
                                  {src.page && (
                                    <span className="text-[10px] font-mono text-[#6F6A61]">
                                      Page {src.page}
                                    </span>
                                  )}
                                </div>
                                {src.excerpt && (
                                  <p className="text-[10px] text-[#6F6A61] mt-0.5 line-clamp-2 italic">
                                    &quot;{src.excerpt}&quot;
                                  </p>
                                )}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}

                  {isQaLoading && (
                    <div className="p-3 bg-[#FCFAF5] text-[#6F6A61] border border-[#DED6C8] rounded-[2px] text-xs mr-2 flex items-center gap-2">
                      <span className="inline-block w-2 h-2 rounded-full bg-[#3F4634] animate-pulse" />
                      <span>Analyzing relevant sections...</span>
                    </div>
                  )}
                </div>

                <div className="pt-2 border-t border-[#DED6C8]">
                  <p className="text-[10px] text-[#6F6A61] font-medium mb-1.5 uppercase">
                    Suggested Questions:
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {[
                      'Can the vendor terminate this agreement?',
                      'When does this contract expire?',
                      'What are the liability limits?',
                      'Are there non-compete restrictions?'
                    ].map((q) => (
                      <button
                        key={q}
                        disabled={isQaLoading}
                        onClick={() => handleAskQuestion(q)}
                        className="text-[11px] bg-[#F7F3EA] hover:bg-[#EFECE3] disabled:opacity-50 text-[#3F4634] border border-[#DED6C8] px-2 py-1 rounded-[2px] text-left transition-colors"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex gap-2 pt-2">
                  <input
                    type="text"
                    value={qaQuery}
                    disabled={isQaLoading}
                    onChange={(e) => setQaQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleAskQuestion()}
                    placeholder="Ask about clauses, dates, or obligations in this agreement..."
                    className="flex-1 bg-[#F7F3EA] border border-[#DED6C8] text-xs text-[#242321] px-3 py-1.5 rounded-[2px] focus:bg-[#FCFAF5] focus:border-[#3F4634] disabled:opacity-60"
                  />
                  <Button
                    onClick={() => handleAskQuestion()}
                    disabled={isQaLoading || !qaQuery.trim()}
                    variant="primary"
                    size="sm"
                  >
                    {isQaLoading ? 'Analyzing...' : 'Ask'}
                  </Button>
                </div>
              </div>
            )}

            {/* TAB 5: Key Details & Dates */}
            {activeRightTab === 'details' && (
              <div className="space-y-3 text-xs">
                <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] space-y-2">
                  <div className="flex justify-between py-1 border-b border-[#DED6C8]">
                    <span className="text-[#6F6A61]">Other Party</span>
                    <span className="font-semibold text-[#242321]">{activeContract.counterparty}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[#DED6C8]">
                    <span className="text-[#6F6A61]">Agreement Type</span>
                    <span className="text-[#242321]">{activeContract.contractType}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[#DED6C8]">
                    <span className="text-[#6F6A61]">Start & End Dates</span>
                    <span className="font-mono text-[#242321]">{activeContract.startDate} → {activeContract.expiryDate}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[#DED6C8]">
                    <span className="text-[#6F6A61]">
                      Renewal Notice Deadline
                      <HelpTooltip text="The date by which you must notify the other party if you do not want this contract to renew automatically." />
                    </span>
                    <span className="font-mono font-medium text-[#9A6A32]">{activeContract.renewalDate}</span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span className="text-[#6F6A61]">
                      Governing Law
                      <HelpTooltip text="The country's or state's laws that this contract says should apply if there is ever a dispute." />
                    </span>
                    <span className="text-[#242321] font-medium text-right max-w-xs">{activeContract.governingLaw}</span>
                  </div>
                </div>

                <div className="p-3 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px]">
                  <h4 className="font-semibold text-[#242321] text-xs mb-1.5">Tags</h4>
                  <div className="flex flex-wrap gap-1.5">
                    {activeContract.tags.map((t) => (
                      <span key={t} className="px-2 py-0.5 bg-[#EFECE3] border border-[#DED6C8] text-[10px] text-[#242321] rounded-[2px]">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
