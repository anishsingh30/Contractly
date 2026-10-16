'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useContractly } from '@/context/contractly-context';
import { BusinessRole } from '@/types/contractly';
import { Button } from '@/components/ui/button';
import { NotificationCenter } from '@/components/notifications/notification-center';
import { NotificationPreferencesModal } from '@/components/notifications/notification-preferences-modal';

interface TopBarProps {
  onRequestUpload: () => void;
  onOpenAskContractly?: () => void;
  onToggleMobileMenu?: () => void;
  isMobileMenuOpen?: boolean;
}

export function formatRoleName(role: BusinessRole | string): string {
  switch (role) {
    case 'OWNER':
      return 'Org Owner';
    case 'ADMIN':
      return 'Administrator';
    case 'LEGAL_MANAGER':
      return 'Legal Manager';
    case 'LEGAL_REVIEWER':
      return 'Legal Reviewer';
    case 'PROCUREMENT':
      return 'Procurement Lead';
    case 'FINANCE':
      return 'Finance Lead';
    case 'HR':
      return 'HR Lead';
    case 'EMPLOYEE':
      return 'Employee';
    case 'MEMBER':
      return 'Member';
    case 'VIEWER':
      return 'Viewer';
    default:
      return role ? role.replace(/_/g, ' ') : 'Member';
  }
}

export function TopBar({
  onRequestUpload,
  onOpenAskContractly,
  onToggleMobileMenu,
  isMobileMenuOpen,
}: TopBarProps) {
  const {
    activeNav,
    setActiveNav,
    searchQuery,
    setSearchQuery,
    accountType,
    businessRole,
    currentUser,
    currentOrganization,
    addToast,
    hasPermission,
    availableOrganizations,
    switchOrganization,
    setActiveContractId,
    logoutUser,
  } = useContractly();

  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isNotifPrefsOpen, setIsNotifPrefsOpen] = useState(false);

  const accountButtonRef = useRef<HTMLButtonElement>(null);
  const accountDropdownRef = useRef<HTMLDivElement>(null);
  const [dropdownPosition, setDropdownPosition] = useState<{
    top: number;
    right: number;
    maxWidth: number;
  } | null>(null);

  const updateDropdownPosition = useCallback(() => {
    if (!accountButtonRef.current) return;
    const rect = accountButtonRef.current.getBoundingClientRect();
    const safeMargin = 12; // 12px safe margin from viewport edge
    const rightOffset = Math.max(safeMargin, window.innerWidth - rect.right);
    const maxWidth = Math.min(320, window.innerWidth - safeMargin * 2);

    setDropdownPosition({
      top: rect.bottom + 6,
      right: rightOffset,
      maxWidth,
    });
  }, []);

  useEffect(() => {
    if (!isSettingsOpen) return;
    updateDropdownPosition();

    const handlePointerDown = (e: MouseEvent | TouchEvent) => {
      if (
        accountDropdownRef.current &&
        !accountDropdownRef.current.contains(e.target as Node) &&
        accountButtonRef.current &&
        !accountButtonRef.current.contains(e.target as Node)
      ) {
        setIsSettingsOpen(false);
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsSettingsOpen(false);
        accountButtonRef.current?.focus();
      }
    };

    const handleWindowChange = () => {
      updateDropdownPosition();
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('touchstart', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    window.addEventListener('resize', handleWindowChange);
    window.addEventListener('scroll', handleWindowChange, true);

    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('touchstart', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('resize', handleWindowChange);
      window.removeEventListener('scroll', handleWindowChange, true);
    };
  }, [isSettingsOpen, updateDropdownPosition]);

  const handleLogout = async () => {
    setIsSettingsOpen(false);
    addToast('Signing Out', 'Revoking session and securely logging out...', 'info');
    await logoutUser();
  };

  // Determine user-friendly account role/type label
  const getDisplayBadge = () => {
    if (currentUser?.isSuperAdmin) return 'Platform Admin';
    if (accountType === 'PERSONAL' || accountType === 'INDIVIDUAL') return 'Personal';
    if (accountType === 'PROFESSIONAL' || accountType === 'LEGAL_PROFESSIONAL') return 'Lawyer';
    if (accountType === 'ENTERPRISE') return 'Enterprise';
    return formatRoleName(currentUser?.role || businessRole);
  };

  return (
    <header className="h-14 bg-[#FCFAF5] border-b border-[#DED6C8] px-3 sm:px-4 md:px-6 flex items-center justify-between z-30 select-none sticky top-0 shrink-0 w-full max-w-full">
      {/* Left: Mobile Menu Toggle & Brand Logo */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        {onToggleMobileMenu && (
          <button
            onClick={onToggleMobileMenu}
            className="md:hidden p-1.5 text-[#242321] hover:bg-[#F7F3EA] rounded-[2px] border border-[#DED6C8] transition-colors focus:outline-none focus:ring-1 focus:ring-[#3F4634]"
            title="Toggle navigation sidebar"
            aria-label="Toggle navigation sidebar"
          >
            <svg className="w-4 h-4 text-[#242321]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        )}

        <button
          onClick={() => setActiveNav('home')}
          className="text-left group flex items-baseline gap-2 focus-visible:outline-none whitespace-nowrap"
        >
          <span className="font-serif tracking-widest text-base sm:text-lg font-bold text-[#242321] group-hover:text-[#3F4634] transition-colors leading-none">
            CONTRACTLY
          </span>
          <span className="text-[10px] uppercase font-mono tracking-wider text-[#6F6A61] border-l border-[#DED6C8] pl-2 hidden xl:inline leading-none whitespace-nowrap">
            Contracts, handled with clarity
          </span>
        </button>
      </div>

      {/* Center: Search Bar */}
      <div className="flex-1 min-w-[120px] sm:min-w-[160px] max-w-xs md:max-w-sm mx-2 sm:mx-3 md:mx-4">
        <div className="relative w-full flex items-center">
          <svg
            className="w-3.5 h-3.5 text-[#6F6A61] absolute left-2.5 pointer-events-none"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search contracts, terms, vendors..."
            className="w-full bg-[#F7F3EA] border border-[#DED6C8] text-xs text-[#242321] placeholder-[#6F6A61] pl-8 pr-7 py-1.5 rounded-[2px] focus:bg-[#FCFAF5] focus:border-[#3F4634] focus:ring-1 focus:ring-[#3F4634] transition-all"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 text-xs text-[#6F6A61] hover:text-[#242321] p-0.5"
              title="Clear search"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Right Controls: Notifications, Ask Contractly, Upload Contract, and Clean Profile Menu */}
      <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
        {/* Notification Bell Center */}
        <NotificationCenter
          onOpenContract={(cid) => {
            setActiveContractId(cid);
            setActiveNav('contracts');
          }}
          onOpenConversation={(cid) => {
            if (cid) setActiveContractId(cid);
            setActiveNav('messages');
          }}
          onOpenPreferences={() => setIsNotifPrefsOpen(true)}
        />


        {/* Ask Contractly Assistant CTA */}
        {onOpenAskContractly && (
          <button
            onClick={onOpenAskContractly}
            className="hidden sm:inline-flex px-2.5 py-1 text-xs font-medium text-[#3F4634] bg-[#F7F3EA] hover:bg-[#EFECE3] border border-[#DED6C8] rounded-[2px] transition-colors items-center gap-1.5 whitespace-nowrap"
            title="Ask Contractly AI CLM assistant"
          >
            <span className="font-serif font-semibold">Ask Contractly</span>
          </button>
        )}

        {/* Primary Upload CTA */}
        {hasPermission('contracts:create') && (
          <Button
            onClick={onRequestUpload}
            variant="primary"
            size="sm"
            className="font-semibold text-xs whitespace-nowrap px-2.5 py-1"
          >
            + Upload
          </Button>
        )}

        {/* Streamlined Profile Trigger Button */}
        <div className="relative">
          <button
            ref={accountButtonRef}
            onClick={() => setIsSettingsOpen(!isSettingsOpen)}
            aria-expanded={isSettingsOpen}
            aria-haspopup="menu"
            aria-label="User account and profile menu"
            className={`flex items-center gap-1.5 sm:gap-2 px-2 py-1 bg-[#F7F3EA] border rounded-[2px] text-xs transition-colors shrink-0 ${
              isSettingsOpen ? 'border-[#3F4634] bg-[#EFECE3]' : 'border-[#DED6C8] hover:border-[#3F4634]'
            }`}
            title="Account & Profile Settings"
          >
            <span className="w-5 h-5 rounded-full bg-[#3F4634] text-[#FCFAF5] flex items-center justify-center font-mono text-[10px] font-bold shrink-0">
              {currentUser?.fullName
                ? currentUser.fullName.charAt(0).toUpperCase()
                : (currentUser?.isSuperAdmin ? 'A' : 'U')}
            </span>
            <div className="flex items-center gap-1.5 text-left">
              <span className="text-[#242321] font-medium text-xs hidden sm:inline truncate max-w-[110px]">
                {currentUser?.fullName?.split(' ')[0] || (
                  currentUser?.isSuperAdmin
                    ? 'Administrator'
                    : currentOrganization?.name || (
                      accountType === 'PERSONAL' || accountType === 'INDIVIDUAL'
                        ? 'Personal'
                        : accountType === 'PROFESSIONAL' || accountType === 'LEGAL_PROFESSIONAL'
                        ? 'Lawyer'
                        : 'Account'
                    )
                )}
              </span>
              <span className="text-[10px] px-1.5 py-0.2 bg-[#EFECE3] border border-[#DED6C8] rounded-[2px] text-[#3F4634] font-medium shrink-0 whitespace-nowrap hidden md:inline">
                {getDisplayBadge()}
              </span>
            </div>
            <svg
              className={`w-3 h-3 text-[#6F6A61] transition-transform ${isSettingsOpen ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {/* Authenticated User Profile Dropdown */}
          {isSettingsOpen && dropdownPosition && (
            <div
              ref={accountDropdownRef}
              role="menu"
              aria-label="User profile options"
              style={{
                position: 'fixed',
                top: `${dropdownPosition.top}px`,
                right: `${dropdownPosition.right}px`,
                maxWidth: `${dropdownPosition.maxWidth}px`,
                width: '19.5rem',
                zIndex: 9999,
              }}
              className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] shadow-xl p-4 text-xs space-y-3.5 select-text"
            >
              {/* User Identity Header */}
              <div className="border-b border-[#DED6C8] pb-3">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-full bg-[#3F4634] text-[#FCFAF5] flex items-center justify-center font-serif text-sm font-bold shrink-0">
                    {currentUser?.fullName
                      ? currentUser.fullName.charAt(0).toUpperCase()
                      : (currentUser?.isSuperAdmin ? 'A' : 'U')}
                  </div>
                  <div className="min-w-0 flex-1">
                    <span className="font-semibold text-sm text-[#242321] block truncate">
                      {currentUser?.fullName || (currentUser?.isSuperAdmin ? 'Administrator' : 'User')}
                    </span>
                    <span className="text-[11px] text-[#6F6A61] block font-mono truncate">
                      {currentUser?.email || 'admin@contractly.com'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Workspace Context & Multi-Tenant Switcher */}
              <div className="space-y-3">
                {currentUser?.isSuperAdmin && (
                  <div className="p-2.5 bg-[#EDF2EC] border border-[#C6D8C6] rounded-[2px] space-y-1">
                    <span className="text-[10px] uppercase font-mono tracking-wider text-[#2E5230] font-bold block">
                      Platform Administration
                    </span>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span className="inline-block px-2 py-0.5 bg-[#3F4634] text-[#FCFAF5] font-semibold text-[10px] rounded-[2px]">
                        Platform Administrator
                      </span>
                      <span className="inline-block px-1.5 py-0.5 bg-[#FCFAF5] border border-[#C6D8C6] text-[#2E5230] font-mono text-[10px] rounded-[2px]">
                        Super Admin
                      </span>
                    </div>
                  </div>
                )}

                <div>
                  <span className="text-[10px] uppercase font-mono tracking-wider text-[#6F6A61] block mb-1">
                    Active Workspace
                  </span>
                  {availableOrganizations && availableOrganizations.length > 1 ? (
                    <select
                      value={currentOrganization?.id || currentUser?.organizationId || ''}
                      onChange={async (e) => {
                        const newOrgId = e.target.value;
                        if (newOrgId && newOrgId !== currentOrganization?.id) {
                          await switchOrganization(newOrgId);
                        }
                      }}
                      className="w-full bg-[#F7F3EA] border border-[#DED6C8] text-xs font-semibold text-[#242321] p-1.5 rounded-[2px] focus:outline-none focus:border-[#3F4634]"
                    >
                      {availableOrganizations.map((o) => (
                        <option key={o.id} value={o.id}>
                          {o.name} ({o.account_type || 'Workspace'} - {formatRoleName(o.role as BusinessRole)})
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span className="text-xs font-semibold text-[#242321] block truncate">
                      {currentOrganization?.name || currentUser?.organizationName || 'Personal Workspace'}
                    </span>
                  )}
                </div>

                <div>
                  <span className="text-[10px] uppercase font-mono tracking-wider text-[#6F6A61] block">
                    Organization Role &amp; Tier
                  </span>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className="inline-block px-2 py-0.5 bg-[#EFECE3] border border-[#DED6C8] text-[#3F4634] font-semibold text-[11px] rounded-[2px]">
                      {formatRoleName(currentUser?.role || businessRole)}
                    </span>
                    {currentUser?.subscriptionTier && (
                      <span className="inline-block px-1.5 py-0.5 bg-[#FCFAF5] border border-[#DED6C8] text-[#6F6A61] font-mono text-[10px] rounded-[2px]">
                        {currentUser.subscriptionTier}
                      </span>
                    )}
                  </div>
                </div>

                {/* Primary Action Links */}
                <div className="pt-2 border-t border-[#DED6C8] space-y-1">
                  <Link
                    href="/profile"
                    role="menuitem"
                    onClick={() => {
                      setIsSettingsOpen(false);
                      setActiveNav('profile');
                    }}
                    className="w-full text-left px-2 py-1.5 rounded-[2px] text-xs font-medium text-[#242321] hover:bg-[#F7F3EA] hover:text-[#3F4634] flex items-center justify-between transition-colors group"
                  >
                    <span className="font-medium text-[#242321] group-hover:text-[#3F4634]">
                      My Profile &amp; Account Settings
                    </span>
                    <span className="text-[#6F6A61] text-xs">→</span>
                  </Link>

                  <button
                    role="menuitem"
                    onClick={() => {
                      setIsSettingsOpen(false);
                      setIsNotifPrefsOpen(true);
                    }}
                    className="w-full text-left px-2 py-1.5 rounded-[2px] text-xs font-medium text-[#242321] hover:bg-[#F7F3EA] hover:text-[#3F4634] flex items-center justify-between transition-colors"
                  >
                    <span>Notification Preferences</span>
                    <span className="text-[#6F6A61]">⚙</span>
                  </button>

                  {currentUser?.isSuperAdmin && (
                    <Link
                      href="/admin"
                      role="menuitem"
                      onClick={() => setIsSettingsOpen(false)}
                      className="w-full text-left px-2 py-1.5 rounded-[2px] text-xs font-semibold text-[#3F4634] hover:bg-[#EDF2EC] flex items-center justify-between transition-colors border-t border-[#DED6C8] mt-1 pt-1.5"
                    >
                      <span>Platform Operations</span>
                      <span className="font-mono text-[10px] bg-[#E8EFE0] px-1.5 py-0.5 border border-[#C5D5B8] rounded-[2px]">
                        Console →
                      </span>
                    </Link>
                  )}
                </div>
              </div>

              {/* Dropdown Footer */}
              <div className="pt-3 border-t border-[#DED6C8] flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setIsSettingsOpen(false)}
                  className="text-xs text-[#6F6A61] hover:text-[#242321] px-1 py-0.5 rounded-[2px]"
                >
                  Close
                </button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleLogout}
                  className="text-[#8B3F3F] border-[#DED6C8] hover:bg-[#FDF2F2] hover:border-[#8B3F3F]"
                >
                  Sign Out
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>

      <NotificationPreferencesModal
        isOpen={isNotifPrefsOpen}
        onClose={() => setIsNotifPrefsOpen(false)}
      />
    </header>
  );
}
