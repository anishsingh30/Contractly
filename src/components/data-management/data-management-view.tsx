'use client';

import React, { useState, useEffect } from 'react';
import { useContractly } from '@/context/contractly-context';
import { formatRoleName } from '@/components/navigation/top-bar';
import {
  getWorkspaceDataSummary,
  exportWorkspaceData,
  clearWorkspaceData,
  WorkspaceSummaryResponse,
  WorkspaceCategorySummary
} from '@/lib/api-client';

export function DataManagementView() {
  const {
    currentUser,
    currentOrganization,
    businessRole,
    hasPermission,
    setActiveNav
  } = useContractly();

  const isOrgAdmin = businessRole === 'OWNER' || hasPermission('org:manage');

  const [summary, setSummary] = useState<WorkspaceSummaryResponse | null>(null);
  const [loading, setLoading] = useState(isOrgAdmin);
  const [error, setError] = useState<string | null>(null);
  const [isAccessDenied, setIsAccessDenied] = useState(!isOrgAdmin);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Clear modal state
  const [isClearModalOpen, setIsClearModalOpen] = useState(false);
  const [clearConfirmationInput, setClearConfirmationInput] = useState('');
  const [clearing, setClearing] = useState(false);
  const [clearError, setClearError] = useState<string | null>(null);

  // Export state
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (isOrgAdmin) {
      loadSummary();
    } else {
      setIsAccessDenied(true);
      setLoading(false);
    }
  }, [isOrgAdmin]);

  async function loadSummary() {
    setLoading(true);
    setError(null);
    setIsAccessDenied(false);
    try {
      const data = await getWorkspaceDataSummary();
      setSummary(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load workspace data summary.';
      if (
        msg.includes('Access denied') ||
        msg.includes('403') ||
        msg.includes('lacks required permission') ||
        msg.includes('org:manage')
      ) {
        setIsAccessDenied(true);
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleExport() {
    setExporting(true);
    setActionSuccess(null);
    try {
      const data = await exportWorkspaceData();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${summary?.organization_slug || 'workspace'}_export_${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setActionSuccess('Workspace data successfully exported as JSON archive.');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Export failed.');
    } finally {
      setExporting(false);
    }
  }

  async function handleExecuteClear() {
    if (clearConfirmationInput.trim() !== 'CLEAR WORKSPACE') {
      setClearError('Confirmation mismatch. Type CLEAR WORKSPACE exactly.');
      return;
    }

    setClearing(true);
    setClearError(null);
    try {
      const res = await clearWorkspaceData('CLEAR WORKSPACE');
      setIsClearModalOpen(false);
      setClearConfirmationInput('');
      setActionSuccess(
        `Workspace business data cleared successfully. Removed ${res.contracts_deleted} contract(s) and ${res.storage_files_deleted} storage file(s). Organization accounts preserved.`
      );
      loadSummary();
    } catch (err: unknown) {
      setClearError(err instanceof Error ? err.message : 'Failed to clear workspace data.');
    } finally {
      setClearing(false);
    }
  }

  // 1. Explicit Access Denied Screen (Strictly prevents misleading rendering of empty tables)
  if (isAccessDenied) {
    return (
      <div className="max-w-2xl mx-auto my-8 p-8 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] shadow-sm text-center space-y-5 select-none">
        <div className="w-12 h-12 mx-auto rounded-full bg-[#F7F3EA] border border-[#DED6C8] flex items-center justify-center text-[#3F4634]">
          <svg className="w-6 h-6 text-[#3F4634]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        </div>

        <div className="space-y-1.5">
          <span className="font-mono text-[10px] uppercase tracking-wider text-[#A33B3B] font-bold px-2 py-0.5 bg-[#FDF2F2] border border-[#F2C6C6] rounded-[2px] inline-block">
            Access Restricted
          </span>
          <h1 className="text-xl font-serif font-bold text-[#242321]">
            Organization Administration Required
          </h1>
          <p className="text-xs text-[#6F6A61] max-w-md mx-auto leading-relaxed">
            Organization Data Management and Retention controls (exporting comprehensive tenant archives and clearing workspace records) require the authoritative <code className="font-mono text-[#242321] bg-[#F7F3EA] px-1 py-0.5 border border-[#DED6C8] rounded-[2px]">org:manage</code> permission, reserved for Organization Owners and Administrators.
          </p>
        </div>

        <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] text-xs max-w-md mx-auto flex items-center justify-between">
          <span className="text-[#6F6A61]">Your Current Role:</span>
          <span className="font-semibold text-[#3F4634] font-mono">
            {formatRoleName(currentUser?.role || businessRole)}
          </span>
        </div>

        <div className="pt-2 flex items-center justify-center gap-3">
          <button
            onClick={() => setActiveNav('home')}
            className="px-4 py-2 bg-[#3F4634] text-[#FCFAF5] text-xs font-semibold rounded-[2px] hover:bg-[#2C3124] transition-colors"
          >
            ← Return to Dashboard
          </button>
          {hasPermission('audit:read') && (
            <button
              onClick={() => setActiveNav('audit')}
              className="px-4 py-2 bg-[#FCFAF5] border border-[#DED6C8] text-[#242321] text-xs font-medium rounded-[2px] hover:bg-[#F7F3EA] transition-colors"
            >
              View Activity Trail
            </button>
          )}
        </div>
      </div>
    );
  }

  // 2. Loading State
  if (loading) {
    return (
      <div className="p-12 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-center space-y-3">
        <div className="w-8 h-8 mx-auto border-2 border-[#3F4634] border-t-transparent rounded-full animate-spin" />
        <div className="font-mono text-xs text-[#6F6A61]">Loading organization data catalog...</div>
      </div>
    );
  }

  // 3. Network or Server Error State (without fake zero-valued dashboards)
  if (error && !summary) {
    return (
      <div className="max-w-xl mx-auto my-8 p-6 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-center space-y-4">
        <div className="p-3 bg-[#FDF2F2] border border-[#F2C6C6] text-[#A33B3B] text-xs rounded-[2px]">
          {error}
        </div>
        <p className="text-xs text-[#6F6A61]">
          Unable to retrieve organizational data summary. Please verify your connection or database status.
        </p>
        <button
          onClick={loadSummary}
          className="px-4 py-1.5 bg-[#3F4634] text-[#FCFAF5] text-xs font-semibold rounded-[2px] hover:bg-[#2C3124] transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  // 4. Authorized Organization Admin Dashboard View
  return (
    <div className="space-y-6">
      {/* Top Banner & Header */}
      <div className="bg-[#FCFAF5] border border-[#DED6C8] p-6 rounded-[2px] space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-[#DED6C8] pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-[11px] uppercase tracking-wider text-[#3F4634] font-bold">
                Organization Data Management &amp; Retention
              </span>
            </div>
            <h1 className="text-xl font-serif font-bold text-[#242321] mt-1">
              {summary?.organization_name || currentOrganization?.name || 'Organization Workspace'}
            </h1>
            <p className="text-xs text-[#6F6A61] mt-0.5">
              Slug: <span className="font-mono text-[#242321]">{summary?.organization_slug || currentOrganization?.slug}</span> • Dedicated Tenant Boundary
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleExport}
              disabled={exporting}
              className="px-3 py-1.5 bg-[#FCFAF5] border border-[#DED6C8] text-[#242321] text-xs font-medium rounded-[2px] hover:bg-[#F7F3EA] transition-colors disabled:opacity-50"
            >
              {exporting ? 'Exporting...' : '↓ Export Workspace JSON'}
            </button>
            <button
              onClick={() => {
                setClearError(null);
                setClearConfirmationInput('');
                setIsClearModalOpen(true);
              }}
              disabled={!summary?.can_clear_workspace}
              className="px-3 py-1.5 bg-[#FCFAF5] border border-[#C97A7E] text-[#A33B3B] text-xs font-semibold rounded-[2px] hover:bg-[#FDF2F2] transition-colors disabled:opacity-40 disabled:border-[#DED6C8] disabled:text-[#6F6A61]"
            >
              Clear Workspace Data
            </button>
          </div>
        </div>

        {actionSuccess && (
          <div className="p-3 bg-[#EDF2EC] border border-[#C6D8C6] text-[#2E5230] text-xs rounded-[2px]">
            {actionSuccess}
          </div>
        )}

        {error && (
          <div className="p-3 bg-[#FDF2F2] border border-[#F2C6C6] text-[#A33B3B] text-xs rounded-[2px]">
            {error}
          </div>
        )}

        {summary && summary.legal_hold_count > 0 && (
          <div className="p-4 bg-[#FDF8EE] border border-[#E8D9B5] text-[#7A4D1A] text-xs rounded-[2px] space-y-1">
            <div className="font-bold uppercase tracking-wider font-mono text-[10px]">
              Active Legal Hold Enforcement
            </div>
            <p>
              Destructive data clearing is disabled because {summary.legal_hold_count} contract(s) are protected by a legal hold or retention lock.
            </p>
            {summary.blocking_reasons.map((reason, idx) => (
              <p key={idx} className="font-mono text-[11px] text-[#242321]">
                • {reason}
              </p>
            ))}
          </div>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2 text-xs">
          <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px]">
            <span className="font-mono text-[10px] text-[#6F6A61] uppercase block">Total Business Records</span>
            <span className="text-xl font-serif font-bold text-[#242321] mt-0.5 block">{summary?.total_records}</span>
          </div>
          <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px]">
            <span className="font-mono text-[10px] text-[#6F6A61] uppercase block">Document Storage Files</span>
            <span className="text-xl font-serif font-bold text-[#242321] mt-0.5 block">{summary?.storage_files_count}</span>
          </div>
          <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px]">
            <span className="font-mono text-[10px] text-[#6F6A61] uppercase block">Legal Holds Active</span>
            <span className="text-xl font-serif font-bold text-[#242321] mt-0.5 block">{summary?.legal_hold_count}</span>
          </div>
          <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px]">
            <span className="font-mono text-[10px] text-[#6F6A61] uppercase block">Clear Eligibility</span>
            <span className={`text-xs font-bold mt-1.5 block ${summary?.can_clear_workspace ? 'text-[#2E5230]' : 'text-[#A33B3B]'}`}>
              {summary?.can_clear_workspace ? 'ELIGIBLE' : 'BLOCKED (HOLDS)'}
            </span>
          </div>
        </div>
      </div>

      {/* Record Categories Table */}
      <div className="space-y-3">
        <h2 className="text-sm font-serif font-bold text-[#242321] uppercase tracking-wider">
          Record Catalog Breakdown by Category
        </h2>
        <div className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] overflow-hidden">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-[#DED6C8] bg-[#F7F3EA] text-[11px] font-mono text-[#6F6A61]">
                <th className="py-2.5 px-4 font-normal">Data Category</th>
                <th className="py-2.5 px-4 font-normal">Scope &amp; Description</th>
                <th className="py-2.5 px-4 font-normal text-right">Active Count</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#DED6C8]">
              {summary?.categories && summary.categories.length > 0 ? (
                summary.categories.map((cat: WorkspaceCategorySummary) => (
                  <tr key={cat.category} className="hover:bg-[#F7F3EA]/50">
                    <td className="py-3 px-4 font-medium text-[#242321]">{cat.category}</td>
                    <td className="py-3 px-4 text-[#6F6A61]">{cat.description}</td>
                    <td className="py-3 px-4 text-right font-mono font-bold text-[#242321]">
                      {cat.count}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={3} className="py-6 text-center text-[#6F6A61] italic">
                    No categorized records found in current organization.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Clear Workspace Modal */}
      {isClearModalOpen && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] max-w-md w-full p-6 space-y-4 shadow-xl">
            <div className="space-y-1">
              <span className="font-mono text-[10px] text-[#A33B3B] uppercase tracking-wider font-bold">
                Irreversible Tenant Action
              </span>
              <h2 className="text-lg font-serif font-bold text-[#242321]">
                Clear Workspace Business Data
              </h2>
            </div>

            <p className="text-xs text-[#6F6A61] leading-relaxed">
              This action will permanently delete contracts, redlines, extracted clauses, obligations, and uploaded files for{' '}
              <strong className="text-[#242321] font-semibold">{summary?.organization_name}</strong>. User accounts, organization memberships, and organizational entities are preserved.
            </p>

            <div className="p-3 bg-[#FDF8EE] border border-[#E8D9B5] text-[#7A4D1A] text-xs rounded-[2px]">
              To confirm, type <span className="font-mono font-bold select-all">CLEAR WORKSPACE</span> below:
            </div>

            <input
              type="text"
              value={clearConfirmationInput}
              onChange={(e) => setClearConfirmationInput(e.target.value)}
              placeholder="CLEAR WORKSPACE"
              className="w-full bg-[#F7F3EA] border border-[#DED6C8] px-3 py-2 text-xs rounded-[2px] font-mono focus:bg-[#FCFAF5] focus:border-[#3F4634] focus:outline-none"
            />

            {clearError && (
              <div className="p-2.5 bg-[#FDF2F2] border border-[#F2C6C6] text-[#A33B3B] text-xs rounded-[2px]">
                {clearError}
              </div>
            )}

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => {
                  setIsClearModalOpen(false);
                  setClearConfirmationInput('');
                  setClearError(null);
                }}
                className="px-3.5 py-1.5 bg-[#FCFAF5] border border-[#DED6C8] text-[#242321] text-xs font-medium rounded-[2px] hover:bg-[#F7F3EA]"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleExecuteClear}
                disabled={clearing || clearConfirmationInput.trim() !== 'CLEAR WORKSPACE'}
                className="px-3.5 py-1.5 bg-[#A33B3B] text-[#FCFAF5] text-xs font-semibold rounded-[2px] hover:bg-[#852C2C] disabled:opacity-40"
              >
                {clearing ? 'Clearing Data...' : 'Permanently Clear Data'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
