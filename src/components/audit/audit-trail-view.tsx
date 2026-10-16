'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { ActivityItem, ActivityListResponse } from '@/types/contractly';
import { fetchActivityHistoryFromBackend } from '@/lib/api-client';
import { useContractly } from '@/context/contractly-context';

export function AuditTrailView() {
  const { setActiveNav, setActiveContractId, contracts } = useContractly();

  const [scope, setScope] = useState<'personal' | 'organization'>('personal');
  const [actionType, setActionType] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [teamMember, setTeamMember] = useState<string>('');
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(25);

  const [activityData, setActivityData] = useState<ActivityListResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedItem, setSelectedItem] = useState<ActivityItem | null>(null);

  const loadActivity = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchActivityHistoryFromBackend({
        scope,
        action_type: actionType || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        team_member: (scope === 'organization' && teamMember.trim()) ? teamMember.trim() : undefined,
        page,
        page_size: pageSize,
      });
      setActivityData(data);
    } catch (err: any) {
      console.error('Failed to load activity history:', err);
      setError(err?.message || 'We could not load your activity history. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [scope, actionType, startDate, endDate, teamMember, page, pageSize]);

  useEffect(() => {
    loadActivity();
  }, [loadActivity]);

  const handleScopeChange = (newScope: 'personal' | 'organization') => {
    if (newScope === scope) return;
    setScope(newScope);
    setPage(1);
    setTeamMember('');
  };

  const handleClearFilters = () => {
    setActionType('');
    setStartDate('');
    setEndDate('');
    setTeamMember('');
    setPage(1);
  };

  const handleResourceClick = (item: ActivityItem, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!item.item_link) return;

    if (item.object_type === 'Contract') {
      setActiveContractId(item.object_id);
      setActiveNav('contracts');
    } else if (item.object_type === 'LegalMatter' || item.object_type === 'MatterMessage') {
      setActiveNav('messages');
    } else if (item.object_type === 'ContractRedline') {
      setActiveNav('redline');
    } else if (item.object_type === 'ContractObligation') {
      setActiveNav('calendar');
    }
  };

  const canViewOrg = activityData?.can_view_organization_activity ?? false;
  const items = activityData?.items || [];
  const total = activityData?.total || 0;
  const totalPages = activityData?.total_pages || 1;

  const hasActiveFilters = Boolean(actionType || startDate || endDate || teamMember);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="pb-4 border-b border-[#DED6C8] flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-xl font-serif font-bold text-[#242321]">
            Activity History
          </h1>
          <p className="text-xs text-[#6F6A61] mt-1 leading-relaxed">
            An immutable audit trail of contract reviews, sign-offs, legal consultations, and administrative events.
          </p>
        </div>

        {/* Scope Selector */}
        <div className="flex items-center gap-2 self-start md:self-auto">
          <div className="bg-[#EFECE3] p-0.5 rounded-[2px] border border-[#DED6C8] flex">
            <button
              type="button"
              onClick={() => handleScopeChange('personal')}
              className={`px-3 py-1.5 text-xs font-medium rounded-[2px] transition-colors ${
                scope === 'personal'
                  ? 'bg-[#3F4634] text-[#FDFCFA] shadow-xs'
                  : 'text-[#6F6A61] hover:text-[#242321]'
              }`}
            >
              My Activity
            </button>
            {canViewOrg && (
              <button
                type="button"
                onClick={() => handleScopeChange('organization')}
                className={`px-3 py-1.5 text-xs font-medium rounded-[2px] transition-colors ${
                  scope === 'organization'
                    ? 'bg-[#3F4634] text-[#FDFCFA] shadow-xs'
                    : 'text-[#6F6A61] hover:text-[#242321]'
                }`}
              >
                Organization Activity
              </button>
            )}
          </div>
          <span className="text-[11px] px-2 py-1 bg-[#F7F3EA] border border-[#DED6C8] text-[#3F4634] rounded-[2px] font-medium hidden sm:inline-block">
            {scope === 'personal' ? 'Personal Scope' : 'Organization Scope'}
          </span>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="p-3.5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
          {/* Action Type Filter */}
          <div>
            <label className="block text-[11px] font-medium text-[#6F6A61] mb-1">
              Event Action
            </label>
            <select
              value={actionType}
              onChange={(e) => {
                setActionType(e.target.value);
                setPage(1);
              }}
              className="w-full bg-[#FDFCFA] border border-[#DED6C8] rounded-[2px] px-2.5 py-1.5 text-xs text-[#242321] focus:outline-hidden focus:border-[#3F4634]"
            >
              <option value="">All Event Actions</option>
              {(activityData?.available_action_types || []).map((act) => (
                <option key={act} value={act}>
                  {act.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </div>

          {/* Start Date */}
          <div>
            <label className="block text-[11px] font-medium text-[#6F6A61] mb-1">
              From Date
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value);
                setPage(1);
              }}
              className="w-full bg-[#FDFCFA] border border-[#DED6C8] rounded-[2px] px-2.5 py-1 text-xs text-[#242321] focus:outline-hidden focus:border-[#3F4634]"
            />
          </div>

          {/* End Date */}
          <div>
            <label className="block text-[11px] font-medium text-[#6F6A61] mb-1">
              To Date
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => {
                setEndDate(e.target.value);
                setPage(1);
              }}
              className="w-full bg-[#FDFCFA] border border-[#DED6C8] rounded-[2px] px-2.5 py-1 text-xs text-[#242321] focus:outline-hidden focus:border-[#3F4634]"
            />
          </div>

          {/* Team Member Filter (Org Scope Only) */}
          {scope === 'organization' ? (
            <div>
              <label className="block text-[11px] font-medium text-[#6F6A61] mb-1">
                Team Member (Email)
              </label>
              <input
                type="text"
                placeholder="Search user email..."
                value={teamMember}
                onChange={(e) => {
                  setTeamMember(e.target.value);
                  setPage(1);
                }}
                className="w-full bg-[#FDFCFA] border border-[#DED6C8] rounded-[2px] px-2.5 py-1.5 text-xs text-[#242321] focus:outline-hidden focus:border-[#3F4634]"
              />
            </div>
          ) : (
            <div className="flex items-end">
              <span className="text-[11px] text-[#6F6A61] italic pb-2">
                Showing your authenticated actions &amp; consultations.
              </span>
            </div>
          )}
        </div>

        {hasActiveFilters && (
          <div className="flex items-center justify-between pt-2 border-t border-[#DED6C8]/60 text-xs">
            <span className="text-[11px] text-[#6F6A61]">
              Filtered results active
            </span>
            <button
              type="button"
              onClick={handleClearFilters}
              className="text-[11px] text-[#8B3F3F] hover:underline font-medium"
            >
              Reset All Filters
            </button>
          </div>
        )}
      </div>

      {/* Loading State */}
      {loading && (
        <div className="p-10 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-center text-[#6F6A61] text-xs space-y-2">
          <div className="inline-block w-5 h-5 border-2 border-[#3F4634] border-t-transparent rounded-full animate-spin"></div>
          <div>Loading activity history records...</div>
        </div>
      )}

      {/* Error State */}
      {error && !loading && (
        <div className="p-8 bg-[#FDF5F5] border border-[#E2BDBF] rounded-[2px] text-center text-xs space-y-3">
          <p className="text-[#8B3F3F] font-medium">{error}</p>
          <button
            type="button"
            onClick={loadActivity}
            className="px-3 py-1 bg-[#8B3F3F] text-white rounded-[2px] text-xs hover:bg-[#723232] transition-colors"
          >
            Retry Request
          </button>
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && items.length === 0 && (
        <div className="p-10 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-center text-[#6F6A61] space-y-2">
          <h2 className="font-semibold text-sm text-[#242321]">
            No activity records found
          </h2>
          <p className="text-xs max-w-md mx-auto">
            {hasActiveFilters
              ? 'No activity matches your active filters. Try expanding the date range or clearing filters.'
              : scope === 'personal'
              ? 'You have not performed any audited actions yet. Contract reviews, approvals, and message dispatches will appear here.'
              : 'No organization events recorded yet for this workspace.'}
          </p>
          {hasActiveFilters && (
            <div className="pt-2">
              <button
                type="button"
                onClick={handleClearFilters}
                className="px-3 py-1 bg-[#3F4634] text-white rounded-[2px] text-xs hover:bg-[#2D3226]"
              >
                Clear Filters
              </button>
            </div>
          )}
        </div>
      )}

      {/* Activity Table */}
      {!loading && !error && items.length > 0 && (
        <div className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-[#F7F3EA] text-[#6F6A61] border-b border-[#DED6C8] font-medium text-[11px]">
                  <th className="py-2.5 px-3 whitespace-nowrap">Date &amp; Time</th>
                  <th className="py-2.5 px-3">Actor</th>
                  <th className="py-2.5 px-3">Action</th>
                  <th className="py-2.5 px-3">Resource Reference</th>
                  <th className="py-2.5 px-3">Summary</th>
                  <th className="py-2.5 px-3 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#DED6C8]">
                {items.map((item) => (
                  <tr
                    key={item.id}
                    onClick={() => setSelectedItem(item)}
                    className="hover:bg-[#F7F3EA]/70 transition-colors cursor-pointer"
                  >
                    <td className="py-3 px-3 font-mono text-[#6F6A61] text-[11px] whitespace-nowrap">
                      {item.formatted_time}
                    </td>
                    <td className="py-3 px-3">
                      <div className="font-medium text-[#242321]">{item.actor_name}</div>
                      <div className="text-[10px] text-[#6F6A61]">{item.actor_email}</div>
                    </td>
                    <td className="py-3 px-3">
                      <span className="text-[11px] px-1.5 py-0.5 bg-[#EFECE3] border border-[#DED6C8] rounded-[2px] text-[#242321] font-medium whitespace-nowrap">
                        {item.action_label}
                      </span>
                    </td>
                    <td className="py-3 px-3 font-medium text-[11px]">
                      {item.item_link ? (
                        <button
                          type="button"
                          onClick={(e) => handleResourceClick(item, e)}
                          className="text-[#3F4634] hover:underline font-medium text-left"
                        >
                          {item.item_reference}
                        </button>
                      ) : (
                        <span className="text-[#6F6A61]">{item.item_reference}</span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-[#242321] text-xs max-w-sm truncate" title={item.summary}>
                      {item.summary}
                    </td>
                    <td className="py-3 px-3 text-right">
                      {item.status === 'FAILED' ? (
                        <span className="text-[10px] px-1.5 py-0.5 bg-[#FDF5F5] border border-[#E2BDBF] text-[#8B3F3F] rounded-[2px] font-semibold">
                          Failed
                        </span>
                      ) : item.status === 'PENDING' ? (
                        <span className="text-[10px] px-1.5 py-0.5 bg-[#FBF8F0] border border-[#E6DEC8] text-[#7A622A] rounded-[2px] font-semibold">
                          Pending
                        </span>
                      ) : (
                        <span className="text-[10px] px-1.5 py-0.5 bg-[#EFECE3] border border-[#DED6C8] text-[#3F4634] rounded-[2px] font-semibold">
                          Completed
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls */}
          <div className="px-4 py-3 bg-[#F7F3EA] border-t border-[#DED6C8] flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-[#6F6A61]">
            <div>
              Showing <span className="font-medium text-[#242321]">{(page - 1) * pageSize + 1}</span> to{' '}
              <span className="font-medium text-[#242321]">
                {Math.min(page * pageSize, total)}
              </span>{' '}
              of <span className="font-medium text-[#242321]">{total}</span> events
            </div>

            <div className="flex items-center gap-2">
              <label className="text-[11px]">Rows per page:</label>
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setPage(1);
                }}
                className="bg-[#FDFCFA] border border-[#DED6C8] rounded-[2px] px-2 py-0.5 text-xs text-[#242321]"
              >
                <option value={15}>15</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
              </select>

              <div className="flex gap-1 ml-2">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="px-2.5 py-1 bg-[#FDFCFA] border border-[#DED6C8] rounded-[2px] text-xs font-medium disabled:opacity-40 hover:bg-[#EFECE3] transition-colors"
                >
                  Previous
                </button>
                <span className="px-2 py-1 text-xs font-mono">
                  {page} / {totalPages}
                </span>
                <button
                  type="button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  className="px-2.5 py-1 bg-[#FDFCFA] border border-[#DED6C8] rounded-[2px] text-xs font-medium disabled:opacity-40 hover:bg-[#EFECE3] transition-colors"
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Details Slide-Over / Modal */}
      {selectedItem && (
        <div className="fixed inset-0 z-50 bg-[#242321]/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-[#FDFCFA] border border-[#DED6C8] rounded-[2px] max-w-lg w-full p-6 space-y-4 shadow-xl">
            <div className="flex items-start justify-between border-b border-[#DED6C8] pb-3">
              <div>
                <h3 className="text-base font-serif font-bold text-[#242321]">
                  Activity Event Details
                </h3>
                <p className="text-[11px] text-[#6F6A61] font-mono mt-0.5">
                  ID: {selectedItem.id}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedItem(null)}
                className="text-[#6F6A61] hover:text-[#242321] text-sm font-bold px-2 py-0.5"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <span className="text-[11px] text-[#6F6A61] block">Timestamp</span>
                  <span className="font-mono text-[#242321] font-medium">
                    {selectedItem.formatted_time}
                  </span>
                </div>
                <div>
                  <span className="text-[11px] text-[#6F6A61] block">Status Outcome</span>
                  <span
                    className={`inline-block px-1.5 py-0.5 rounded-[2px] text-[10px] font-semibold ${
                      selectedItem.status === 'FAILED'
                        ? 'bg-[#FDF5F5] border border-[#E2BDBF] text-[#8B3F3F]'
                        : selectedItem.status === 'PENDING'
                        ? 'bg-[#FBF8F0] border border-[#E6DEC8] text-[#7A622A]'
                        : 'bg-[#EFECE3] border border-[#DED6C8] text-[#3F4634]'
                    }`}
                  >
                    {selectedItem.status}
                  </span>
                </div>
              </div>

              <div>
                <span className="text-[11px] text-[#6F6A61] block">Actor</span>
                <span className="font-medium text-[#242321]">
                  {selectedItem.actor_name} ({selectedItem.actor_email})
                </span>
              </div>

              <div>
                <span className="text-[11px] text-[#6F6A61] block">Action Category</span>
                <span className="px-2 py-0.5 bg-[#EFECE3] border border-[#DED6C8] text-[#242321] rounded-[2px] text-[11px] font-medium inline-block">
                  {selectedItem.action_label}
                </span>
              </div>

              <div>
                <span className="text-[11px] text-[#6F6A61] block">Associated Resource</span>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="font-medium text-[#242321]">
                    {selectedItem.item_reference}
                  </span>
                  {selectedItem.item_link && (
                    <button
                      type="button"
                      onClick={(e) => {
                        handleResourceClick(selectedItem, e);
                        setSelectedItem(null);
                      }}
                      className="text-[11px] text-[#3F4634] hover:underline font-semibold"
                    >
                      Open Resource &rarr;
                    </button>
                  )}
                </div>
              </div>

              <div>
                <span className="text-[11px] text-[#6F6A61] block">Event Description</span>
                <p className="mt-1 p-3 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-[#242321] leading-relaxed whitespace-pre-wrap">
                  {selectedItem.detail}
                </p>
              </div>
            </div>

            <div className="pt-3 border-t border-[#DED6C8] flex justify-end">
              <button
                type="button"
                onClick={() => setSelectedItem(null)}
                className="px-4 py-1.5 bg-[#3F4634] text-white rounded-[2px] text-xs hover:bg-[#2D3226] font-medium transition-colors"
              >
                Close Details
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
