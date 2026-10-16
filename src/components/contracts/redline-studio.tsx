'use client';

import React, { useState, useEffect } from 'react';
import { useContractly } from '@/context/contractly-context';
import { StatusPill } from '@/components/ui/status-pill';
import { Button } from '@/components/ui/button';
import { fetchNegotiationAnalysisFromBackend, exportRedlinesDocx } from '@/lib/api-client';
import { NegotiationFindingItem } from '@/types/contractly';

interface RedlineStudioProps {
  onBack: () => void;
}

export function RedlineStudio({ onBack }: RedlineStudioProps) {
  const {
    contracts,
    activeContract,
    setActiveContractId,
    acceptRedline,
    rejectRedline,
    addRedlineComment,
    generateRedlines,
    addToast,
    redlineScope,
    setRedlineScope
  } = useContractly();

  const selectedContractId = redlineScope || activeContract?.id || (contracts.length > 0 ? contracts[0].id : 'ALL');
  const setSelectedContractId = (newScope: string) => {
    setRedlineScope(newScope);
    if (newScope !== 'ALL') {
      setActiveContractId(newScope);
    }
  };

  const [statusFilter, setStatusFilter] = useState<'ALL' | 'PENDING' | 'ACCEPTED' | 'REJECTED'>('ALL');
  const [viewMode, setViewMode] = useState<'inline' | 'split'>('inline');
  const [commentText, setCommentText] = useState<{ [key: string]: string }>({});
  const [negotiationFindings, setNegotiationFindings] = useState<NegotiationFindingItem[]>([]);
  const [isLoadingFindings, setIsLoadingFindings] = useState<boolean>(false);
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [hasRunGeneration, setHasRunGeneration] = useState<boolean>(false);

  const currentContract = contracts.find((c) => c.id === selectedContractId) || activeContract || contracts[0];

  useEffect(() => {
    if (currentContract?.id) {
      setIsLoadingFindings(true);
      fetchNegotiationAnalysisFromBackend(currentContract.id)
        .then((findings) => {
          setNegotiationFindings(findings);
          setIsLoadingFindings(false);
        })
        .catch(() => setIsLoadingFindings(false));
    }
  }, [currentContract?.id]);

  // Derived scope redlines
  type ScopedRedline = (typeof contracts)[0]['redlines'][0] & { contractId: string; contractTitle: string };

  const allScopedRedlines: ScopedRedline[] =
    selectedContractId === 'ALL'
      ? contracts.flatMap((c) => (c.redlines || []).map((r) => ({ ...r, contractId: c.id, contractTitle: c.title })))
      : currentContract
      ? (currentContract.redlines || []).map((r) => ({ ...r, contractId: currentContract.id, contractTitle: currentContract.title }))
      : [];

  const pendingInScope = allScopedRedlines.filter((r) => r.status === 'PENDING').length;
  const acceptedInScope = allScopedRedlines.filter((r) => r.status === 'ACCEPTED').length;
  const rejectedInScope = allScopedRedlines.filter((r) => r.status === 'REJECTED').length;
  const totalInScope = allScopedRedlines.length;

  const workspacePendingCount = contracts.reduce(
    (acc, c) => acc + (c.redlines || []).filter((r) => r.status === 'PENDING').length,
    0
  );

  const displayedRedlines = allScopedRedlines.filter((r) => {
    if (statusFilter === 'ALL') return true;
    return r.status === statusFilter;
  });

  if (!currentContract && contracts.length === 0) {
    return (
      <div className="p-8 text-center text-[#6F6A61] bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3">
        <p className="font-semibold text-[#242321]">No contracts available in this workspace.</p>
        <Button onClick={onBack} variant="primary" size="sm">
          ← Return to My Contracts
        </Button>
      </div>
    );
  }

  const handleGenerateRevisions = async () => {
    if (!currentContract?.id || isGenerating) return;
    setIsGenerating(true);
    setGenerationError(null);
    try {
      const ok = await generateRedlines(currentContract.id);
      setHasRunGeneration(true);
      if (!ok) {
        setGenerationError('Failed to generate proposed revisions. Please try again.');
      }
    } catch (err: any) {
      setGenerationError(err.message || 'AI redline generation service error.');
      setHasRunGeneration(true);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleExportDocx = async () => {
    if (!currentContract?.id) return;
    setIsExporting(true);
    try {
      const { blob, filename } = await exportRedlinesDocx(currentContract.id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      addToast(
        'Export Complete',
        `Downloaded proposed revisions document (${filename}).`,
        'success'
      );
    } catch (err: any) {
      addToast(
        'Export Failed',
        err.message || 'Failed to download proposed revisions document.',
        'danger'
      );
    } finally {
      setIsExporting(false);
    }
  };

  const handleSaveComment = async (targetContractId: string, redlineId: string) => {
    const text = commentText[redlineId]?.trim();
    if (!text) return;
    await addRedlineComment(targetContractId, redlineId, text);
    setCommentText((prev) => ({ ...prev, [redlineId]: '' }));
  };

  const isBaselinePlaybook = negotiationFindings.some((f) => f.ruleId.startsWith('baseline-'));

  const getPriorityBadge = (rationale: string, comment?: string) => {
    const combined = `${rationale} ${comment || ''}`.toUpperCase();
    if (combined.includes('MANDATORY')) {
      return (
        <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded-sm bg-[#F7EDED] text-[#8B3F3F] border border-[#E2BDBF]">
          Mandatory
        </span>
      );
    }
    if (combined.includes('RECOMMENDED')) {
      return (
        <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded-sm bg-[#FDF6E2] text-[#8B6414] border border-[#E2D2A4]">
          Recommended
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded-sm bg-[#F7F3EA] text-[#6F6A61] border border-[#DED6C8]">
        Optional
      </span>
    );
  };


  return (
    <div className="space-y-5">
      {/* 1. Header with Actions and Scope Selector */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-3 border-b border-[#DED6C8]">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={onBack} variant="secondary" size="sm">
              ← Document View
            </Button>
            <h1 className="text-xl font-serif font-bold text-[#242321]">
              Edit & Compare
            </h1>
            <span className="px-2 py-0.5 text-xs font-mono font-bold bg-[#EFECE3] border border-[#DED6C8] text-[#3F4634] rounded-[2px]">
              {pendingInScope} Pending Review
            </span>

            {/* Scope / Contract Selector */}
            <div className="flex items-center gap-1.5 ml-1">
              <span className="text-xs text-[#6F6A61] font-mono uppercase">Scope:</span>
              <select
                value={selectedContractId}
                onChange={(e) => {
                  setSelectedContractId(e.target.value);
                  if (e.target.value !== 'ALL') {
                    setActiveContractId(e.target.value);
                  }
                }}
                className="bg-[#F7F3EA] border border-[#DED6C8] text-xs text-[#242321] px-2.5 py-1 rounded-[2px] max-w-[260px] truncate focus:border-[#3F4634]"
              >
                <option value="ALL">All Contracts ({workspacePendingCount} pending across workspace)</option>
                {contracts.map((c) => {
                  const pCount = (c.redlines || []).filter((r) => r.status === 'PENDING').length;
                  return (
                    <option key={c.id} value={c.id}>
                      {c.title} ({pCount} pending)
                    </option>
                  );
                })}
              </select>
            </div>
          </div>
          <p className="text-xs text-[#6F6A61] mt-1.5">
            {selectedContractId === 'ALL' ? (
              <>Reviewing genuine proposed amendments requiring a decision across <strong>all workspace contracts</strong> ({workspacePendingCount} pending decisions).</>
            ) : currentContract ? (
              <>Review proposed changes to <strong>{currentContract.title}</strong> ({currentContract.contractId} &middot; {currentContract.version}).</>
            ) : (
              <>Review proposed amendments across your agreements.</>
            )}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* View Toggle */}
          <div className="bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] p-0.5 text-xs font-medium flex items-center">
            <button
              onClick={() => setViewMode('inline')}
              className={`px-2.5 py-1 rounded-[2px] transition-colors ${
                viewMode === 'inline' ? 'bg-[#3F4634] text-[#FCFAF5]' : 'text-[#6F6A61]'
              }`}
            >
              Inline Changes
            </button>
            <button
              onClick={() => setViewMode('split')}
              className={`px-2.5 py-1 rounded-[2px] transition-colors ${
                viewMode === 'split' ? 'bg-[#3F4634] text-[#FCFAF5]' : 'text-[#6F6A61]'
              }`}
            >
              Side-by-Side Compare
            </button>
          </div>

          {/* Generate / Regenerate Action (Available when a specific contract is selected) */}
          <Button
            onClick={handleGenerateRevisions}
            variant={totalInScope === 0 ? 'primary' : 'secondary'}
            size="sm"
            disabled={isGenerating || isExporting || selectedContractId === 'ALL'}
            title={selectedContractId === 'ALL' ? 'Select a specific contract to generate revisions' : undefined}
          >
            {isGenerating ? 'Generating Revisions...' : totalInScope === 0 ? '⚡ Generate Proposed Revisions' : '↻ Regenerate Revisions'}
          </Button>

          {/* Export Action */}
          <Button
            onClick={handleExportDocx}
            variant="secondary"
            size="sm"
            disabled={isExporting || isGenerating || totalInScope === 0 || selectedContractId === 'ALL'}
            title={selectedContractId === 'ALL' ? 'Select a specific contract to export DOCX' : undefined}
          >
            {isExporting ? 'Exporting...' : 'Export Proposed Revisions (.docx)'}
          </Button>
        </div>
      </div>

      {/* 2. Educational Plain-Language Notice */}
      <div className="p-3 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] flex flex-col md:flex-row md:items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-2">
          <span className="w-4 h-4 rounded-full bg-[#3F4634] text-[#FCFAF5] inline-flex items-center justify-center text-[10px] font-bold">i</span>
          <span className="text-[#6F6A61]">
            <strong className="text-[#242321]">Redline = proposed contract changes.</strong> We highlight text suggested to be removed or added so you can evaluate key negotiation points before signing.
          </span>
        </div>
        <div className="flex items-center gap-3 text-[11px] font-medium shrink-0">
          <span className="flex items-center gap-1 text-[#8B3F3F]">
            <span className="w-2 h-2 rounded-full bg-[#8B3F3F]" /> Removed text
          </span>
          <span className="flex items-center gap-1 text-[#2E5230]">
            <span className="w-2 h-2 rounded-full bg-[#4F6B50]" /> Added text
          </span>
        </div>
      </div>

      {/* 3. Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left Column: Proposed Changes List */}
        <div className="lg:col-span-8 space-y-4">
          {/* A. Loading State during generation */}
          {isGenerating && (
            <div className="p-8 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-center space-y-3">
              <div className="inline-block w-6 h-6 border-2 border-[#3F4634] border-t-transparent rounded-full animate-spin" />
              <p className="text-sm font-semibold text-[#242321]">
                Generating Proposed Revisions with Gemini AI...
              </p>
              <p className="text-xs text-[#6F6A61] max-w-md mx-auto">
                Reading extracted clauses, analyzing negotiation standards, and formulating contract-grounded redlines.
              </p>
            </div>
          )}

          {/* B. Error Banner if Generation Failed */}
          {!isGenerating && generationError && (
            <div className="p-4 bg-[#F7EDED] border border-[#E2BDBF] rounded-[2px] text-xs text-[#8B3F3F] space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold">Revision Generation Failed</span>
                <Button onClick={handleGenerateRevisions} variant="secondary" size="sm" className="text-xs h-7">
                  Retry Generation
                </Button>
              </div>
              <p>{generationError}</p>
            </div>
          )}

          {/* C. Proposed Revisions List & Filter Tabs */}
          {!isGenerating && allScopedRedlines.length > 0 && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-[#6F6A61] px-1 pb-1 border-b border-[#DED6C8]">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-[#242321] font-mono text-sm">
                    {pendingInScope} Pending Decision{pendingInScope !== 1 ? 's' : ''}
                  </span>
                  <span className="text-[#DED6C8]">&middot;</span>
                  <span>{acceptedInScope} Accepted</span>
                  <span className="text-[#DED6C8]">&middot;</span>
                  <span>{rejectedInScope} Rejected</span>
                </div>

                {/* Filter Tabs */}
                <div className="flex items-center gap-1 bg-[#F7F3EA] border border-[#DED6C8] p-0.5 rounded-[2px] text-[11px]">
                  <button
                    onClick={() => setStatusFilter('ALL')}
                    className={`px-2 py-0.5 rounded-[2px] transition-colors ${
                      statusFilter === 'ALL' ? 'bg-[#3F4634] text-[#FCFAF5] font-semibold' : 'text-[#6F6A61] hover:text-[#242321]'
                    }`}
                  >
                    All ({totalInScope})
                  </button>
                  <button
                    onClick={() => setStatusFilter('PENDING')}
                    className={`px-2 py-0.5 rounded-[2px] transition-colors ${
                      statusFilter === 'PENDING' ? 'bg-[#3F4634] text-[#FCFAF5] font-semibold' : 'text-[#6F6A61] hover:text-[#242321]'
                    }`}
                  >
                    Pending ({pendingInScope})
                  </button>
                  <button
                    onClick={() => setStatusFilter('ACCEPTED')}
                    className={`px-2 py-0.5 rounded-[2px] transition-colors ${
                      statusFilter === 'ACCEPTED' ? 'bg-[#3F4634] text-[#FCFAF5] font-semibold' : 'text-[#6F6A61] hover:text-[#242321]'
                    }`}
                  >
                    Accepted ({acceptedInScope})
                  </button>
                  <button
                    onClick={() => setStatusFilter('REJECTED')}
                    className={`px-2 py-0.5 rounded-[2px] transition-colors ${
                      statusFilter === 'REJECTED' ? 'bg-[#3F4634] text-[#FCFAF5] font-semibold' : 'text-[#6F6A61] hover:text-[#242321]'
                    }`}
                  >
                    Rejected ({rejectedInScope})
                  </button>
                </div>
              </div>

              {displayedRedlines.length === 0 ? (
                <div className="p-8 text-center text-xs text-[#6F6A61] bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-2">
                  <p className="font-semibold text-[#242321] text-sm">
                    No {statusFilter.toLowerCase()} amendments in this view.
                  </p>
                  {statusFilter === 'PENDING' && (
                    <p>All proposed changes in this scope have been accepted or rejected.</p>
                  )}
                  <Button onClick={() => setStatusFilter('ALL')} variant="secondary" size="sm">
                    View All Amendments ({totalInScope})
                  </Button>
                </div>
              ) : (
                displayedRedlines.map((redline) => (
                  <div
                    key={redline.id}
                    className="p-5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3.5"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-[#DED6C8]">
                      <div className="flex flex-wrap items-center gap-2">
                        {selectedContractId === 'ALL' && (
                          <span className="text-[10px] font-mono font-semibold text-[#3F4634] px-1.5 py-0.5 bg-[#EFECE3] border border-[#DED6C8] rounded-[2px]">
                            {redline.contractTitle}
                          </span>
                        )}
                        <h3 className="font-semibold text-xs text-[#242321]">{redline.sectionTitle}</h3>
                        {getPriorityBadge(redline.rationale, redline.comment)}
                        <StatusPill status={redline.status} />
                      </div>
                      <div className="text-[11px] text-[#6F6A61]">
                        Suggested by {redline.author}
                      </div>
                    </div>

                    {/* View Mode: Inline Changes */}
                    {viewMode === 'inline' ? (
                      <div className="p-4 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] font-serif text-xs leading-relaxed text-[#242321]">
                        <span className="font-sans font-semibold text-[10px] uppercase text-[#6F6A61] block mb-1">Proposed Wording:</span>
                        <span className="redline-del line-through text-[#8B3F3F] bg-[#F7EDED] px-1.5 py-0.5 rounded-sm mx-1">
                          {redline.originalText}
                        </span>{' '}
                        <span className="redline-ins font-semibold text-[#274C25] bg-[#EDF2EC] px-1.5 py-0.5 rounded-sm mx-1">
                          {redline.suggestedText}
                        </span>
                      </div>
                    ) : (
                      /* View Mode: Side by Side */
                      <div className="grid grid-cols-2 gap-3 text-xs leading-relaxed">
                        <div className="p-3 bg-[#F7EDED]/60 border border-[#E2BDBF] rounded-[2px]">
                          <div className="text-[10px] text-[#8B3F3F] font-bold uppercase mb-1">
                            Original Text (Current Clause)
                          </div>
                          <p className="text-[#8B3F3F] font-serif line-through">&quot;{redline.originalText}&quot;</p>
                        </div>
                        <div className="p-3 bg-[#EDF2EC]/70 border border-[#C6D8C6] rounded-[2px]">
                          <div className="text-[10px] text-[#2E5230] font-bold uppercase mb-1">
                            Proposed Revision (Amended Language)
                          </div>
                          <p className="text-[#274C25] font-serif font-medium">&quot;{redline.suggestedText}&quot;</p>
                        </div>
                      </div>
                    )}

                    {/* Plain-Language Rationale */}
                    <div className="p-3 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-xs">
                      <span className="text-[10px] uppercase font-bold text-[#6F6A61] block mb-1">
                        Why this change was suggested:
                      </span>
                      <p className="text-[#242321] leading-relaxed">{redline.rationale}</p>
                      {redline.comment && (
                        <p className="mt-2 pt-2 border-t border-[#DED6C8]/60 text-[#6F6A61] text-[11px]">
                          <strong>Internal Note:</strong> {redline.comment}
                        </p>
                      )}
                    </div>

                    {/* Action Buttons: Accept / Reject / Add Comment */}
                    <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-[#DED6C8]/60">
                      <div className="flex items-center gap-2">
                        <Button
                          onClick={() => acceptRedline(redline.contractId, redline.id)}
                          variant="primary"
                          size="sm"
                          disabled={redline.status === 'ACCEPTED'}
                        >
                          {redline.status === 'ACCEPTED' ? '✓ Change Accepted' : 'Accept Change'}
                        </Button>
                        <Button
                          onClick={() => rejectRedline(redline.contractId, redline.id)}
                          variant="secondary"
                          size="sm"
                          disabled={redline.status === 'REJECTED'}
                        >
                          {redline.status === 'REJECTED' ? 'Change Rejected' : 'Reject Change'}
                        </Button>
                      </div>

                      <div className="flex items-center gap-2">
                        <input
                          type="text"
                          value={commentText[redline.id] || ''}
                          onChange={(e) =>
                            setCommentText({ ...commentText, [redline.id]: e.target.value })
                          }
                          placeholder="Add discussion note..."
                          className="bg-[#F7F3EA] border border-[#DED6C8] text-xs text-[#242321] px-2.5 py-1 rounded-[2px] w-52"
                        />
                        <Button
                          onClick={() => handleSaveComment(redline.contractId, redline.id)}
                          variant="ghost"
                          size="sm"
                        >
                          Add Note
                        </Button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* D. Empty States when redlines count is 0 */}
          {!isGenerating && allScopedRedlines.length === 0 && (
            <div className="p-10 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-center text-[#6F6A61] space-y-3">
              <div className="w-10 h-10 mx-auto rounded-full bg-[#F7F3EA] border border-[#DED6C8] flex items-center justify-center text-lg">
                📝
              </div>
              <div>
                <p className="text-sm font-semibold text-[#242321]">
                  {hasRunGeneration ? 'No Proposed Changes Justified' : 'Revisions Not Yet Generated'}
                </p>
                <p className="text-xs max-w-md mx-auto mt-1 leading-relaxed">
                  {hasRunGeneration
                    ? 'All extracted clauses in this contract version conform to balanced market positions. No amendments are recommended at this time.'
                    : 'This contract has completed clause extraction. Click below to analyze clauses against negotiation benchmarks and generate grounded redlines.'}
                </p>
              </div>
              {selectedContractId !== 'ALL' && (
                <div className="pt-2">
                  <Button
                    onClick={handleGenerateRevisions}
                    variant="primary"
                    size="sm"
                    disabled={isGenerating}
                  >
                    ⚡ Generate Proposed Revisions
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>


        {/* Right Column: Negotiation Guidance & Playbook Rule Matching */}
        <div className="lg:col-span-4 space-y-4">
          <div className="p-4 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3">
            <div className="flex items-center justify-between border-b border-[#DED6C8] pb-2">
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-[#242321] font-mono">
                  Playbook Negotiation Findings
                </h3>
              </div>
              <span className="text-[10px] text-[#6F6A61] font-mono">
                {negotiationFindings.length} Checked
              </span>
            </div>

            {/* Standard Baseline vs Custom Playbook Notice */}
            {isBaselinePlaybook && (
              <div className="p-2.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] text-[11px] text-[#6F6A61] space-y-0.5">
                <p className="font-semibold text-[#242321]">Standard Commercial Baseline Active</p>
                <p className="leading-relaxed">
                  No custom tenant playbook rules configured. Contract evaluated against standard commercial CLM negotiation benchmarks.
                </p>
              </div>
            )}

            {isLoadingFindings ? (
              <div className="p-4 text-center text-xs text-[#6F6A61] animate-pulse">
                Evaluating negotiation standards against contract clauses...
              </div>
            ) : negotiationFindings.length > 0 ? (
              <div className="space-y-3 max-h-[520px] overflow-y-auto pr-1">
                {negotiationFindings.map((finding, idx) => (
                  <div
                    key={finding.ruleId || idx}
                    className={`p-3 rounded-[2px] border text-xs space-y-1.5 ${
                      finding.status === 'Rule Match'
                        ? 'bg-[#EDF2EC]/60 border-[#C6D8C6]'
                        : 'bg-[#FDF6E2]/70 border-[#E2D2A4]'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-1">
                      <span className="font-semibold text-[#242321]">{finding.category}</span>
                      <span
                        className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded-sm ${
                          finding.status === 'Rule Match'
                            ? 'text-[#2E5230] bg-[#DDE9DC]'
                            : 'text-[#8B6414] bg-[#F7EAC4]'
                        }`}
                      >
                        {finding.status}
                      </span>
                    </div>

                    <p className="text-[#242321] text-[11px] leading-relaxed">
                      {finding.findingSummary}
                    </p>

                    {finding.guidance && (
                      <p className="text-[11px] text-[#6F6A61] italic pt-1 border-t border-[#DED6C8]/60">
                        <strong>Guidance:</strong> {finding.guidance}
                      </p>
                    )}

                    {finding.suggestedAction && (
                      <div className="pt-1.5 flex items-center justify-between gap-2">
                        <Button
                          onClick={() => {
                            navigator.clipboard?.writeText(finding.suggestedAction || '');
                            addToast('Copied', 'Recommended position copied to clipboard.', 'info');
                          }}
                          variant="ghost"
                          size="sm"
                          className="text-[10px] h-6 px-2 py-0"
                        >
                          Copy Recommended Action
                        </Button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-4 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] text-xs text-[#6F6A61] space-y-1">
                <p className="font-medium text-[#242321]">No Playbook Issues Found</p>
                <p>All evaluated contract clauses align with standard positions.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
