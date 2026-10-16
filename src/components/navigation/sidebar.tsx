'use client';

import React from 'react';
import Link from 'next/link';
import { useContractly } from '@/context/contractly-context';
import { formatRoleName } from './top-bar';

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export function Sidebar({ isOpen = false, onClose }: SidebarProps) {
  const {
    accountType,
    businessRole,
    activeNav,
    setActiveNav,
    contracts,
    obligations,
    currentUser,
    currentOrganization,
    hasPermission,
    redlineScope,
    unreadMessagesCount
  } = useContractly();

  // Dynamic live metric derivations
  const totalContracts = contracts.length;
  const pendingApprovalsCount = contracts.reduce((acc, c) => {
    return acc + (c.approvalSteps || []).filter((s) => s.decision === 'PENDING').length;
  }, 0);

  // Active contracts set to avoid counting obligations on terminated/expired contracts
  const activeContractIds = new Set(
    contracts.filter((c) => c.status !== 'TERMINATED' && c.status !== 'EXPIRED').map((c) => c.id)
  );
  // Outstanding qualifying obligation tasks requiring tracking, evidence, or resolution (matches task cards in Things You Need to Do)
  const outstandingTasksCount = obligations.filter(
    (o) =>
      o.status !== 'FULFILLED' &&
      o.status !== 'RESOLVED' &&
      (!o.contractId || activeContractIds.has(o.contractId))
  ).length;

  // Genuine pending proposed amendments in active scope (reconciled with Edit & Compare scope)
  const scopedContractForRedlines = contracts.find((c) => c.id === redlineScope);
  const pendingRedlinesCount = scopedContractForRedlines
    ? (scopedContractForRedlines.redlines || []).filter((r) => r.status === 'PENDING').length
    : contracts.reduce((acc, c) => acc + (c.redlines || []).filter((r) => r.status === 'PENDING').length, 0);
  // Distinct accessible contracts with available health information (registered obligations or clause risks)
  const healthContractsCount = contracts.filter(
    (c) => (c.obligations && c.obligations.length > 0) || (c.risks && c.risks.length > 0)
  ).length;
  const procurementContractsCount = contracts.filter((c) => c.department === 'Procurement').length;
  const hrContractsCount = contracts.filter((c) => c.department === 'HR').length;

  const messagesBadge = unreadMessagesCount > 0 ? unreadMessagesCount : undefined;

  // Navigation Items per Account Perspective & Role
  let navSections: { label: string; id: string; badge?: number; description?: string }[] = [];

  if (accountType === 'PERSONAL' || accountType === 'INDIVIDUAL') {
    navSections = [
      { id: 'home', label: 'Home' },
      { id: 'contracts', label: 'My Contracts', badge: totalContracts > 0 ? totalContracts : undefined },
      { id: 'messages', label: 'Messages', badge: messagesBadge },
      { id: 'calendar', label: 'Calendar' },
      { id: 'tasks', label: 'Things You Need to Do', badge: outstandingTasksCount > 0 ? outstandingTasksCount : undefined },
      { id: 'watch', label: 'Contract Health', badge: healthContractsCount > 0 ? healthContractsCount : undefined },
      { id: 'redlining', label: 'Edit & Compare', badge: pendingRedlinesCount > 0 ? pendingRedlinesCount : undefined },
      { id: 'lawyers', label: 'Get Legal Help' },
    ];
  } else if (accountType === 'BUSINESS' || accountType === 'ENTERPRISE') {
    // Dynamically tailored by business role
    if (businessRole === 'EMPLOYEE') {
      navSections = [
        { id: 'home', label: 'Home' },
        { id: 'contracts', label: 'My Contracts', badge: totalContracts > 0 ? totalContracts : undefined },
        { id: 'messages', label: 'Messages', badge: messagesBadge },
        { id: 'calendar', label: 'Calendar' },
        { id: 'requests', label: 'Request a Contract' },
        { id: 'tasks', label: 'Things You Need to Do', badge: outstandingTasksCount > 0 ? outstandingTasksCount : undefined },
        { id: 'lawyers', label: 'Get Legal Help' },
      ];
    } else if (businessRole === 'PROCUREMENT') {
      navSections = [
        { id: 'home', label: 'Home' },
        { id: 'overview', label: 'Procurement Overview' },
        { id: 'contracts', label: 'Vendor Contracts', badge: procurementContractsCount > 0 ? procurementContractsCount : undefined },
        { id: 'messages', label: 'Messages', badge: messagesBadge },
        { id: 'calendar', label: 'Calendar' },
        { id: 'requests', label: 'Contract Requests' },
        { id: 'approvals', label: 'Approvals', badge: pendingApprovalsCount > 0 ? pendingApprovalsCount : undefined },
        { id: 'vendors', label: 'Vendors' },
        { id: 'watch', label: 'Contract Health', badge: healthContractsCount > 0 ? healthContractsCount : undefined },
        { id: 'lawyers', label: 'Get Legal Help' },
      ];
    } else if (businessRole === 'FINANCE') {
      navSections = [
        { id: 'home', label: 'Home' },
        { id: 'overview', label: 'Financial Overview' },
        { id: 'contracts', label: 'Committed Contracts', badge: totalContracts > 0 ? totalContracts : undefined },
        { id: 'messages', label: 'Messages', badge: messagesBadge },
        { id: 'calendar', label: 'Calendar' },
        { id: 'approvals', label: 'Finance Sign-Offs', badge: pendingApprovalsCount > 0 ? pendingApprovalsCount : undefined },
        { id: 'tasks', label: 'Payment Responsibilities', badge: outstandingTasksCount > 0 ? outstandingTasksCount : undefined },
        { id: 'reports', label: 'Spend Reports' },
        { id: 'audit', label: 'Activity' },
      ];
    } else if (businessRole === 'HR') {
      navSections = [
        { id: 'home', label: 'Home' },
        { id: 'overview', label: 'HR Overview' },
        { id: 'contracts', label: 'Employment Agreements', badge: hrContractsCount > 0 ? hrContractsCount : undefined },
        { id: 'messages', label: 'Messages', badge: messagesBadge },
        { id: 'calendar', label: 'Calendar' },
        { id: 'requests', label: 'New Hire Contracts' },
        { id: 'tasks', label: 'Probation Milestones', badge: outstandingTasksCount > 0 ? outstandingTasksCount : undefined },
        { id: 'audit', label: 'Activity' },
        { id: 'lawyers', label: 'Get Legal Help' },
      ];
    } else if (businessRole === 'LEGAL_REVIEWER') {
      navSections = [
        { id: 'home', label: 'Home' },
        { id: 'contracts', label: 'Contracts for Review', badge: totalContracts > 0 ? totalContracts : undefined },
        { id: 'messages', label: 'Messages', badge: messagesBadge },
        { id: 'calendar', label: 'Calendar' },
        { id: 'redlining', label: 'Edit & Compare (Redlines)', badge: pendingRedlinesCount > 0 ? pendingRedlinesCount : undefined },
        { id: 'watch', label: 'Contract Health', badge: healthContractsCount > 0 ? healthContractsCount : undefined },
        { id: 'playbook', label: 'Negotiation Rules' },
        { id: 'lawyers', label: 'Get Legal Help' },
      ];
    } else if (businessRole === 'LEGAL_MANAGER') {
      navSections = [
        { id: 'home', label: 'Home' },
        { id: 'overview', label: 'Legal Operations Overview' },
        { id: 'contracts', label: 'All Contracts', badge: totalContracts > 0 ? totalContracts : undefined },
        { id: 'messages', label: 'Messages', badge: messagesBadge },
        { id: 'calendar', label: 'Calendar' },
        { id: 'approvals', label: 'Legal Approvals', badge: pendingApprovalsCount > 0 ? pendingApprovalsCount : undefined },
        { id: 'redlining', label: 'Edit & Compare', badge: pendingRedlinesCount > 0 ? pendingRedlinesCount : undefined },
        { id: 'tasks', label: 'Responsibilities', badge: outstandingTasksCount > 0 ? outstandingTasksCount : undefined },
        { id: 'watch', label: 'Contract Health', badge: healthContractsCount > 0 ? healthContractsCount : undefined },
        { id: 'playbook', label: 'Negotiation Rules' },
        ...(hasPermission('org:manage') ? [{ id: 'data-management', label: 'Data Management' }] : []),
        { id: 'audit', label: 'Activity' },
        { id: 'lawyers', label: 'Get Legal Help' },
      ];
    } else {
      // Organization Owner (Full Executive View)
      navSections = [
        { id: 'home', label: 'Home' },
        { id: 'overview', label: 'Executive Overview' },
        { id: 'contracts', label: 'Contracts', badge: totalContracts > 0 ? totalContracts : undefined },
        { id: 'messages', label: 'Messages', badge: messagesBadge },
        { id: 'calendar', label: 'Calendar' },
        { id: 'requests', label: 'Requests' },
        { id: 'approvals', label: 'Approvals', badge: pendingApprovalsCount > 0 ? pendingApprovalsCount : undefined },
        { id: 'tasks', label: 'Responsibilities', badge: outstandingTasksCount > 0 ? outstandingTasksCount : undefined },
        { id: 'watch', label: 'Contract Health', badge: healthContractsCount > 0 ? healthContractsCount : undefined },
        { id: 'redlining', label: 'Edit & Compare', badge: pendingRedlinesCount > 0 ? pendingRedlinesCount : undefined },
        { id: 'vendors', label: 'Vendors' },
        { id: 'playbook', label: 'Negotiation Rules' },
        { id: 'reports', label: 'Reports' },
        ...(hasPermission('org:manage') || businessRole === 'OWNER' ? [{ id: 'data-management', label: 'Data Management' }] : []),
        { id: 'audit', label: 'Activity' },
        { id: 'lawyers', label: 'Get Legal Help' },
      ];
    }
  } else if (accountType === 'PROFESSIONAL' || accountType === 'LEGAL_PROFESSIONAL') {
    navSections = [
      { id: 'home', label: 'Home' },
      { id: 'overview', label: 'Practice Overview' },
      { id: 'contracts', label: 'Client Contracts', badge: totalContracts > 0 ? totalContracts : undefined },
      { id: 'messages', label: 'Messages', badge: messagesBadge },
      { id: 'calendar', label: 'Calendar' },
      { id: 'tasks', label: 'Matters & Deadlines', badge: outstandingTasksCount > 0 ? outstandingTasksCount : undefined },
      { id: 'watch', label: 'Contract Health', badge: healthContractsCount > 0 ? healthContractsCount : undefined },
      { id: 'redlining', label: 'Edit & Compare', badge: pendingRedlinesCount > 0 ? pendingRedlinesCount : undefined },
      { id: 'lawyers', label: 'Colleague Network' },
      { id: 'audit', label: 'Activity' },
    ];
  } else {
    navSections = [
      { id: 'home', label: 'Home' },
      { id: 'overview', label: 'System Overview' },
      { id: 'contracts', label: 'Contracts', badge: totalContracts > 0 ? totalContracts : undefined },
      { id: 'messages', label: 'Messages', badge: messagesBadge },
      { id: 'audit', label: 'Security Activity' },
    ];
  }

  return (
    <>
      {/* Mobile Backdrop Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-[#242321]/40 z-30 md:hidden backdrop-blur-[1px] transition-opacity"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={`${
          isOpen ? 'fixed inset-y-0 left-0 z-40 w-[260px] max-w-[80vw] shadow-2xl' : 'hidden'
        } md:flex md:static md:z-auto md:w-[260px] md:shadow-none bg-[#FCFAF5] border-r border-[#DED6C8] flex-col justify-between select-none shrink-0 h-full min-h-0 overflow-hidden transition-all`}
      >
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden pt-3">
          {/* Dynamic Header Area Clearly Highlighting Active Perspective & Role */}
          <div className="px-3 pb-2.5 mb-2 border-b border-[#DED6C8] space-y-1 shrink-0">
            <div className="flex items-center justify-between">
              <span
                className="text-[9px] uppercase font-mono tracking-wider text-[#6F6A61] block truncate"
                title={currentOrganization?.name || undefined}
              >
                {currentOrganization?.name ||
                  (accountType === 'BUSINESS'
                    ? 'Corporate Workspace'
                    : accountType === 'PERSONAL'
                    ? 'Personal Account'
                    : accountType === 'PROFESSIONAL'
                    ? 'Legal Practice'
                    : 'Workspace')}
              </span>
              {onClose && (
                <button
                  onClick={onClose}
                  className="md:hidden text-[#6F6A61] hover:text-[#242321] text-xs font-mono p-0.5"
                  aria-label="Close sidebar"
                >
                  ✕
                </button>
              )}
            </div>
            {accountType === 'BUSINESS' && (
              <div className="flex items-center gap-1.5 px-2 py-1 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px]">
                <span className="w-2 h-2 rounded-full bg-[#3F4634]" />
                <span className="text-xs font-semibold text-[#242321] truncate">
                  {formatRoleName(businessRole)}
                </span>
              </div>
            )}
          </div>

          {/* Navigation Links Tailored to Active Role - Independently Scrollable */}
          <nav className="flex-1 min-h-0 overflow-y-auto space-y-0.5 px-2 pb-2">
            {navSections.map((item) => {
              const isActive =
                activeNav === item.id ||
                (item.id === 'tasks' && (activeNav === 'tasks' || activeNav === 'obligations')) ||
                (item.id === 'watch' && activeNav === 'watch') ||
                (item.id === 'lawyers' && (activeNav === 'lawyers' || activeNav === 'consultations'));

              return (
                <button
                  key={item.id}
                  onClick={() => {
                    if (item.id === 'tasks') setActiveNav('tasks');
                    else if (item.id === 'lawyers') setActiveNav('lawyers');
                    else setActiveNav(item.id);
                    if (onClose) onClose();
                  }}
                  className={`w-full flex items-center justify-between px-3 py-1.5 text-xs font-medium rounded-[2px] transition-colors text-left ${
                    isActive
                      ? 'bg-[#3F4634] text-[#FCFAF5]'
                      : 'text-[#242321] hover:bg-[#F7F3EA] hover:text-[#3F4634]'
                  }`}
                >
                  <span className="truncate">{item.label}</span>
                  {item.badge !== undefined && (
                    <span
                      className={`text-[10px] font-mono px-1.5 py-0.2 rounded-[2px] ml-1 shrink-0 ${
                        isActive
                          ? 'bg-[#59604A] text-[#FCFAF5]'
                          : 'bg-[#EFECE3] text-[#6F6A61]'
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Pinned Helpful Footer Guide */}
        <div className="shrink-0 p-3 border-t border-[#DED6C8] bg-[#F7F3EA]/70 text-[11px] text-[#6F6A61] space-y-2">
          <div>
            <p className="font-semibold text-[#242321] flex items-center gap-1">
              <span>Active Role:</span>
              <span className="text-[#3F4634]">{formatRoleName(businessRole)}</span>
            </p>
            <p className="text-[10px] leading-relaxed">
              Navigation and dashboard are tailored for this role.
            </p>
          </div>

          {currentUser?.isSuperAdmin && (
            <div className="pt-1.5 border-t border-[#DED6C8]">
              <Link
                href="/admin"
                className="w-full flex items-center justify-between px-2.5 py-1.5 text-xs font-semibold bg-[#3F4634] text-[#FCFAF5] rounded-[2px] hover:bg-[#2C3124] transition-colors"
              >
                <span>Platform Operations</span>
                <span className="font-mono text-[10px]">Console →</span>
              </Link>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
