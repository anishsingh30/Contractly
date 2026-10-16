'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useContractly } from '@/context/contractly-context';
import { formatRoleName } from '@/components/navigation/top-bar';
import { updateUserProfile } from '@/lib/api-client';
import { Button } from '@/components/ui/button';

interface ProfileViewProps {
  onBack?: () => void;
}

export function ProfileView({ onBack }: ProfileViewProps) {
  const {
    currentUser,
    currentOrganization,
    businessRole,
    accountType,
    availableOrganizations,
    switchOrganization,
    recheckAuth,
    addToast,
    logoutUser
  } = useContractly();

  const [fullName, setFullName] = useState(currentUser?.fullName || '');
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (currentUser?.fullName) {
      setFullName(currentUser.fullName);
    }
  }, [currentUser?.fullName]);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim()) {
      setSaveError('Full name cannot be empty.');
      return;
    }

    setIsSaving(true);
    setSaveSuccess(null);
    setSaveError(null);

    try {
      await updateUserProfile({ full_name: fullName.trim() });
      await recheckAuth();
      setSaveSuccess('Your account profile was successfully updated.');
      addToast('Profile Updated', 'Your full name has been updated across all workspace records.', 'success');
    } catch (err: any) {
      setSaveError(err.message || 'Failed to update account profile.');
      addToast('Update Failed', err.message || 'Could not save profile changes.', 'danger');
    } finally {
      setIsSaving(false);
    }
  };

  const isNameChanged = fullName.trim() !== (currentUser?.fullName || '');
  const isPlatformAdmin = Boolean(
    currentUser?.isSuperAdmin ||
    (currentUser?.email && currentUser.email.toLowerCase() === 'admin@contractly.com')
  );

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* 1. Header & Breadcrumbs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#DED6C8]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            {onBack ? (
              <button
                onClick={onBack}
                className="text-xs text-[#3F4634] hover:underline flex items-center gap-1 font-medium"
              >
                ← Return to Dashboard
              </button>
            ) : (
              <Link
                href="/dashboard"
                className="text-xs text-[#3F4634] hover:underline flex items-center gap-1 font-medium"
              >
                ← Return to Dashboard
              </Link>
            )}
          </div>
          <h1 className="text-xl font-serif font-bold text-[#242321]">
            Account &amp; Profile Settings
          </h1>
          <p className="text-xs text-[#6F6A61] mt-0.5">
            Manage your personal credentials, organizational workspace, and active platform permissions.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {isPlatformAdmin && (
            <span className="font-mono text-[10px] px-2.5 py-1 bg-[#3F4634] text-[#FCFAF5] border border-[#3F4634] rounded-[2px] font-semibold">
              Platform Administrator
            </span>
          )}
          <span className="font-mono text-[10px] px-2.5 py-1 bg-[#EFECE3] text-[#3F4634] border border-[#DED6C8] rounded-[2px]">
            Org Role: {formatRoleName(currentUser?.role || businessRole)}
          </span>
        </div>
      </div>

      {/* 2. Notifications & Status Messages */}
      {saveSuccess && (
        <div className="p-3 bg-[#EDF2EC] border border-[#C6D8C6] text-[#2E5230] text-xs rounded-[2px] flex items-center justify-between">
          <span>{saveSuccess}</span>
          <button
            onClick={() => setSaveSuccess(null)}
            className="text-xs text-[#2E5230] hover:underline ml-3 font-mono"
          >
            ✕
          </button>
        </div>
      )}

      {saveError && (
        <div className="p-3 bg-[#FDF2F2] border border-[#F2C6C6] text-[#A33B3B] text-xs rounded-[2px] flex items-center justify-between">
          <span>{saveError}</span>
          <button
            onClick={() => setSaveError(null)}
            className="text-xs text-[#A33B3B] hover:underline ml-3 font-mono"
          >
            ✕
          </button>
        </div>
      )}

      {/* 3. Personal Profile Information */}
      <section className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] p-6 space-y-6 shadow-sm">
        <div className="flex items-center gap-4 border-b border-[#DED6C8] pb-5">
          <div className="w-14 h-14 rounded-full bg-[#3F4634] text-[#FCFAF5] flex items-center justify-center font-serif text-xl font-bold shrink-0">
            {currentUser?.fullName
              ? currentUser.fullName.charAt(0).toUpperCase()
              : (isPlatformAdmin ? 'A' : 'U')}
          </div>
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-[#242321] truncate">
              {currentUser?.fullName || (isPlatformAdmin ? 'Administrator' : 'User')}
            </h2>
            <p className="text-xs text-[#6F6A61] font-mono truncate">
              {currentUser?.email || 'admin@contractly.com'}
            </p>
            <div className="flex items-center gap-2 mt-1">
              <span
                className={`text-[10px] font-mono px-2 py-0.5 rounded-[2px] border ${
                  currentUser?.emailVerificationStatus === 'VERIFIED'
                    ? 'bg-[#EDF2EC] text-[#2E5230] border-[#C6D8C6]'
                    : 'bg-[#FDF8EE] text-[#7A4D1A] border-[#E8D9B5]'
                }`}
              >
                {currentUser?.emailVerificationStatus === 'VERIFIED'
                  ? 'Verified Account'
                  : 'Pending Email Verification'}
              </span>
              <span className="text-[10px] text-[#6F6A61] font-mono">
                ID: {currentUser?.id ? currentUser.id.substring(0, 12) + '...' : 'Unknown'}
              </span>
            </div>
          </div>
        </div>

        <form onSubmit={handleSaveProfile} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[#242321] mb-1">
                Full Name
              </label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Enter your professional full name"
                className="w-full bg-[#F7F3EA] border border-[#DED6C8] text-xs text-[#242321] px-3 py-2 rounded-[2px] focus:bg-[#FCFAF5] focus:border-[#3F4634] focus:outline-none focus:ring-1 focus:ring-[#3F4634]"
              />
              <p className="text-[11px] text-[#6F6A61] mt-1">
                This name is displayed on contract audits, approvals, and shared reviews.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#242321] mb-1">
                Email Address (Primary Identity)
              </label>
              <input
                type="email"
                value={currentUser?.email || ''}
                disabled
                className="w-full bg-[#EFECE3] border border-[#DED6C8] text-xs text-[#6F6A61] px-3 py-2 rounded-[2px] cursor-not-allowed font-mono"
              />
              <p className="text-[11px] text-[#6F6A61] mt-1">
                Your email address is your verified tenant identifier and cannot be modified directly.
              </p>
            </div>
          </div>

          <div className="pt-2 flex items-center justify-end gap-3">
            <button
              type="submit"
              disabled={isSaving || !isNameChanged}
              className="px-4 py-2 bg-[#3F4634] text-[#FCFAF5] text-xs font-semibold rounded-[2px] hover:bg-[#2C3124] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {isSaving ? 'Saving Profile...' : 'Save Profile Changes'}
            </button>
          </div>
        </form>
      </section>

      {/* 4. Organizational Workspace Context */}
      <section className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] p-6 space-y-5 shadow-sm">
        <div className="border-b border-[#DED6C8] pb-3">
          <h2 className="text-sm font-serif font-bold text-[#242321] uppercase tracking-wider">
            Workspace &amp; Organization Context
          </h2>
          <p className="text-xs text-[#6F6A61] mt-0.5">
            Your access permissions, data segregation, and audit records are bound to your active workspace.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px]">
            <span className="text-[10px] uppercase font-mono tracking-wider text-[#6F6A61] block mb-1">
              Active Organization
            </span>
            <span className="font-semibold text-[#242321] text-sm block truncate">
              {currentOrganization?.name || currentUser?.organizationName || 'Personal Workspace'}
            </span>
          </div>

          <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px]">
            <span className="text-[10px] uppercase font-mono tracking-wider text-[#6F6A61] block mb-1">
              Assigned Role
            </span>
            <span className="font-semibold text-[#3F4634] text-sm block">
              {formatRoleName(currentUser?.role || businessRole)}
            </span>
          </div>

          <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px]">
            <span className="text-[10px] uppercase font-mono tracking-wider text-[#6F6A61] block mb-1">
              Account Architecture
            </span>
            <span className="font-semibold text-[#242321] text-sm block">
              {accountType === 'PERSONAL' || accountType === 'INDIVIDUAL'
                ? 'Individual Tenant'
                : accountType === 'LEGAL_PROFESSIONAL' || accountType === 'PROFESSIONAL'
                ? 'Legal Chambers'
                : 'Business Organization'}
            </span>
          </div>

          <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px]">
            <span className="text-[10px] uppercase font-mono tracking-wider text-[#6F6A61] block mb-1">
              Subscription Tier
            </span>
            <span className="font-semibold text-[#242321] text-sm block font-mono">
              {currentUser?.subscriptionTier || currentOrganization?.subscriptionTier || 'COMMUNITY'}
            </span>
          </div>
        </div>

        {/* Workspace Switcher if user belongs to multiple organizations */}
        {availableOrganizations && availableOrganizations.length > 1 && (
          <div className="p-4 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] space-y-2">
            <span className="text-xs font-semibold text-[#242321] block">
              Switch Active Workspace
            </span>
            <p className="text-[11px] text-[#6F6A61]">
              You have access to multiple Contractly workspaces. Select an organization to switch context:
            </p>
            <div className="max-w-md">
              <select
                value={currentOrganization?.id || currentUser?.organizationId || ''}
                onChange={async (e) => {
                  const targetOrg = e.target.value;
                  if (targetOrg && targetOrg !== currentOrganization?.id) {
                    await switchOrganization(targetOrg);
                  }
                }}
                className="w-full bg-[#FCFAF5] border border-[#DED6C8] text-xs font-semibold text-[#242321] p-2 rounded-[2px] focus:outline-none focus:border-[#3F4634]"
              >
                {availableOrganizations.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name} ({o.account_type || 'Workspace'} - {formatRoleName(o.role as any)})
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}
      </section>

      {/* 5. Active Role Permissions */}
      {currentUser?.permissions && currentUser.permissions.length > 0 && (
        <section className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] p-6 space-y-4 shadow-sm">
          <div className="border-b border-[#DED6C8] pb-3">
            <h2 className="text-sm font-serif font-bold text-[#242321] uppercase tracking-wider">
              Authoritative Workspace Permissions
            </h2>
            <p className="text-xs text-[#6F6A61] mt-0.5">
              Permissions enforced server-side for your role in this tenant.
            </p>
          </div>

          <div className="flex flex-wrap gap-1.5">
            {currentUser.permissions.map((perm) => (
              <span
                key={perm}
                className="px-2 py-0.5 bg-[#F7F3EA] border border-[#DED6C8] font-mono text-[10px] text-[#3F4634] rounded-[2px]"
              >
                {perm}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* 6. Session Security & Sign Out */}
      <section className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] p-6 space-y-4 shadow-sm">
        <div className="border-b border-[#DED6C8] pb-3 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-serif font-bold text-[#242321] uppercase tracking-wider">
              Session &amp; Security Controls
            </h2>
            <p className="text-xs text-[#6F6A61] mt-0.5">
              Securely revoke your active authenticated session across this browser.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={logoutUser}
            className="text-[#8B3F3F] border-[#DED6C8] hover:bg-[#FDF2F2] hover:border-[#8B3F3F]"
          >
            Sign Out of Contractly
          </Button>
        </div>
      </section>
    </div>
  );
}
