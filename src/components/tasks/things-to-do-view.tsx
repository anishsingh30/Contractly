'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useContractly } from '@/context/contractly-context';
import { ThingToDoItem, fetchThingsToDo, updateCalendarEvent } from '@/lib/api-client';
import { Button } from '@/components/ui/button';

interface ThingsToDoViewProps {
  onOpenContract?: (contractId: string) => void;
  onNavigateTab?: (tab: string) => void;
}

export function ThingsToDoView({ onOpenContract, onNavigateTab }: ThingsToDoViewProps) {
  const { contracts, obligations, accountType, addToast } = useContractly();

  const [items, setItems] = useState<ThingToDoItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [priorityFilter, setPriorityFilter] = useState<string>('ALL');
  const [contractFilter, setContractFilter] = useState<string>('ALL');

  const [criticalCount, setCriticalCount] = useState<number>(0);
  const [importantCount, setImportantCount] = useState<number>(0);
  const [distinctContractsCount, setDistinctContractsCount] = useState<number>(0);

  const isProfessional = accountType === 'PROFESSIONAL' || accountType === 'LEGAL_PROFESSIONAL';

  const loadTasks = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await fetchThingsToDo({
        priority: priorityFilter !== 'ALL' ? priorityFilter : undefined,
        contractId: contractFilter !== 'ALL' ? contractFilter : undefined
      });
      setItems(res.items);
      setCriticalCount(res.critical_count);
      setImportantCount(res.important_count);
      setDistinctContractsCount(res.distinct_contracts_count || 0);
    } catch (err) {
      console.error('Failed to load things to do:', err);
    } finally {
      setIsLoading(false);
    }
  }, [priorityFilter, contractFilter]);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  const handleResolveAction = async (item: ThingToDoItem) => {
    if (item.action_type === 'VERIFY_DATE' && item.target_id) {
      await updateCalendarEvent(item.target_id, { is_verified: true });
      addToast('Verified', 'Milestone date has been marked as verified.', 'success');
      loadTasks();
      return;
    }

    if (item.contract_id && onOpenContract) {
      onOpenContract(item.contract_id);
      return;
    }

    if (onNavigateTab) {
      if (item.action_type === 'APPROVE_STEP') onNavigateTab('approvals');
      else if (item.action_type === 'UPLOAD_EVIDENCE') onNavigateTab('watch');
      else onNavigateTab('contracts');
    }
  };

  const getPriorityStyle = (priority: string) => {
    if (priority === 'CRITICAL') return 'bg-[#FDF2F2] text-[#8B3F3F] border-[#F5C2C2]';
    if (priority === 'IMPORTANT') return 'bg-[#FEF9EE] text-[#9A6A32] border-[#F7E5C1]';
    return 'bg-[#F7F3EA] text-[#6F6A61] border-[#DED6C8]';
  };

  const getStatusStyle = (status: string) => {
    if (status === 'OVERDUE') return 'bg-[#8B3F3F] text-[#FCFAF5]';
    if (status === 'DUE_SOON') return 'bg-[#9A6A32] text-[#FCFAF5]';
    if (status === 'IN_REVIEW') return 'bg-[#59604A] text-[#FCFAF5]';
    return 'bg-[#EFECE3] text-[#3A3835]';
  };

  return (
    <div className="space-y-6">
      {/* 1. Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#DED6C8]">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-serif font-bold text-xl text-[#242321]">
              {isProfessional ? 'Matters & Deadlines' : 'Things You Need to Do'}
            </h1>
            <span className="text-xs uppercase font-mono tracking-wider text-[#6F6A61] px-2 py-0.5 bg-[#EFECE3] border border-[#DED6C8] rounded-[2px]">
              {isProfessional ? 'Active Matters & Contract Deadlines' : 'Responsibilities & Approvals'}
            </span>
          </div>
          <p className="text-xs text-[#6F6A61] mt-1">
            {isProfessional
              ? 'Genuine outstanding client matters, compliance obligations, imminent deadlines, and review sign-offs across your practice.'
              : 'Genuine outstanding responsibilities derived from active contracts, pending approvals, imminent deadlines, and compliance milestones.'}
          </p>
        </div>

        {/* Counter Summary Pills */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs px-2.5 py-1 bg-[#F7F3EA] border border-[#DED6C8] text-[#3F4634] rounded-[2px] font-semibold">
            {distinctContractsCount} Active Contract{distinctContractsCount !== 1 ? 's' : ''} with Deadlines
          </span>
          <span className="text-xs px-2.5 py-1 bg-[#FDF2F2] border border-[#F5C2C2] text-[#8B3F3F] rounded-[2px] font-semibold">
            {criticalCount} Critical
          </span>
          <span className="text-xs px-2.5 py-1 bg-[#FEF9EE] border border-[#F7E5C1] text-[#9A6A32] rounded-[2px] font-semibold">
            {importantCount} Important
          </span>
        </div>
      </div>


      {/* 2. Filter Bar */}
      <div className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] p-3 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2">
          <span className="text-[#6F6A61] font-mono uppercase text-[11px]">Filter by:</span>
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="bg-[#F7F3EA] border border-[#DED6C8] px-2 py-1 rounded-[2px] text-[#242321]"
          >
            <option value="ALL">All Priorities</option>
            <option value="CRITICAL">Critical Only</option>
            <option value="IMPORTANT">Important Only</option>
            <option value="INFORMATIONAL">Informational Only</option>
          </select>

          <select
            value={contractFilter}
            onChange={(e) => setContractFilter(e.target.value)}
            className="bg-[#F7F3EA] border border-[#DED6C8] px-2 py-1 rounded-[2px] text-[#242321] max-w-[200px] truncate"
          >
            <option value="ALL">All Contracts ({contracts.length} uploaded)</option>
            {contracts.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))}
          </select>
        </div>

        <button
          onClick={loadTasks}
          className="text-xs text-[#3F4634] hover:underline font-medium"
        >
          ↻ Refresh Responsibilities
        </button>
      </div>

      {/* 3. Responsibility List */}
      <div className="space-y-3">
        {isLoading ? (
          <div className="p-8 text-center text-xs text-[#6F6A61] bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px]">
            Evaluating outstanding contractual responsibilities...
          </div>
        ) : items.length === 0 ? (
          <div className="p-8 text-center text-xs text-[#6F6A61] bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-2">
            <p className="font-semibold text-[#242321] text-sm">All Responsibilities Up to Date</p>
            <p>No critical obligations, pending approvals, or overdue notice windows currently require attention.</p>
          </div>
        ) : (
          items.map((item) => (
            <div
              key={item.id}
              className={`p-4 bg-[#FCFAF5] border rounded-[2px] flex flex-col md:flex-row md:items-center justify-between gap-4 transition-all shadow-sm ${
                item.priority === 'CRITICAL'
                  ? 'border-l-4 border-l-[#8B3F3F] border-[#DED6C8]'
                  : 'border-[#DED6C8]'
              }`}
            >
              <div className="space-y-1.5 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`text-[10px] font-mono uppercase font-bold px-2 py-0.5 border rounded-[2px] ${getPriorityStyle(
                      item.priority
                    )}`}
                  >
                    {item.priority}
                  </span>
                  <span
                    className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-[2px] ${getStatusStyle(
                      item.status
                    )}`}
                  >
                    {item.status}
                  </span>
                  <span className="font-serif font-bold text-sm text-[#242321]">
                    {item.title}
                  </span>
                </div>

                {item.contract_title && (
                  <p className="text-xs text-[#6F6A61]">
                    Contract: <strong>{item.contract_title}</strong> {item.counterparty ? `• ${item.counterparty}` : ''}
                  </p>
                )}

                <p className="text-xs text-[#3A3835] leading-relaxed max-w-3xl">
                  {item.reason}
                </p>

                <div className="flex flex-wrap items-center gap-4 text-[11px] text-[#6F6A61] pt-1">
                  {item.due_date && (
                    <span>
                      Target Date: <strong className="font-mono text-[#242321]">{item.due_date}</strong>
                    </span>
                  )}
                  {item.responsible_role && (
                    <span>
                      Responsible Role: <strong className="text-[#242321]">{item.responsible_role}</strong>
                    </span>
                  )}
                </div>
              </div>

              {/* Action Button */}
              <div className="md:text-right shrink-0">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => handleResolveAction(item)}
                  className="text-xs font-semibold"
                >
                  {item.action_type === 'VERIFY_DATE'
                    ? 'Confirm Date ✓'
                    : item.action_type === 'APPROVE_STEP'
                    ? 'Review & Sign-Off →'
                    : item.action_type === 'UPLOAD_EVIDENCE'
                    ? 'Upload Evidence →'
                    : 'Open Details →'}
                </Button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
