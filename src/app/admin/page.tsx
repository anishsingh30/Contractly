'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  logout,
  previewDemoReset,
  resetDemoWorkspace,
  getCustomerHandoverChecklist,
  fetchPlatformAdvocates,
  fetchWithAuth,
  API_BASE_URL,
  DemoResetPreviewResponse,
  HandoverChecklistItem
} from '@/lib/api-client';
import { AdvocateProfile } from '@/types/contractly';
import { LawyerManagement } from '@/components/admin/lawyer-management';
import { ConversationOversight } from '@/components/admin/conversation-oversight';

interface PlatformHealth {
  status: string;
  environment: string;
  database: {
    status: string;
    engine: string;
    readiness: string;
  };
  storage: {
    provider: string;
    status: string;
  };
  scheduler: {
    enabled: boolean;
    interval_hours: number;
  };
  email?: {
    configured: boolean;
    enabled: boolean;
    provider: string;
    host?: string;
  };
  rate_limiter?: {
    backend: string;
    configured: boolean;
    connected: boolean;
    is_distributed: boolean;
    mode: string;
  };
  audited_by_user?: string;
  checked_at?: string;
}

interface PlatformMetrics {
  tenants_count: number;
  users_count: number;
  total_contracts_count: number;
  total_contract_versions_count: number;
  allocated_storage_quota_bytes: number;
  advocates_count?: number;
  pending_advocates_count?: number;
  verified_advocates_count?: number;
  matters_by_status?: Record<string, number>;
  privacy_notice: string;
}

interface AdvocateItem {
  id: string;
  user_id: string;
  full_name: string;
  email: string;
  firm_name: string;
  organization_id: string;
  bar_council_number: string;
  state_bar_council: string;
  admitted_jurisdictions: string;
  practice_areas: string[];
  experience_years: number;
  consultation_fee: string;
  verification_status: string;
  verified_at: string | null;
  rejection_reason?: string | null;
  created_at: string | null;
}

interface TenantItem {
  id: string;
  name: string;
  slug: string;
  account_type: string;
  subscription_tier: string;
  storage_quota_bytes: number;
  created_at: string | null;
  member_count: number;
  contract_count: number;
}

interface SupportStatus {
  customer_content_support_access_enabled: boolean;
  policy: string;
  description: string;
  exceptional_access_requirements: string[];
}

interface AuditLogItem {
  id: string;
  user_email: string;
  action: string;
  object_type: string;
  object_id: string;
  detail: string;
  created_at: string | null;
}

export default function PlatformAdminPage() {
  const [health, setHealth] = useState<PlatformHealth | null>(null);
  const [metrics, setMetrics] = useState<PlatformMetrics | null>(null);
  const [tenants, setTenants] = useState<TenantItem[]>([]);
  const [advocates, setAdvocates] = useState<AdvocateProfile[]>([]);
  const [supportStatus, setSupportStatus] = useState<SupportStatus | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState<string>('');

  // Demo Workspace & Handover State
  const [demoPreview, setDemoPreview] = useState<DemoResetPreviewResponse | null>(null);
  const [demoResetLoading, setDemoResetLoading] = useState(false);
  const [demoResetSuccess, setDemoResetSuccess] = useState<string | null>(null);
  const [demoResetError, setDemoResetError] = useState<string | null>(null);
  const [isResetModalOpen, setIsResetModalOpen] = useState(false);
  const [resetConfirmationInput, setResetConfirmationInput] = useState('');
  const [reseedDemo, setReseedDemo] = useState(true);
  const [handoverChecklist, setHandoverChecklist] = useState<HandoverChecklistItem[]>([]);

  useEffect(() => {
    fetchAdminData();
  }, []);

  async function fetchAdminData() {
    setLoading(true);
    setErrorStatus(null);
    setErrorMessage('');

    try {
      // 1. Fetch Health
      const healthRes = await fetchWithAuth(`${API_BASE_URL}/platform/health`, {
        headers: { Accept: 'application/json' },
      });

      if (!healthRes.ok) {
        setErrorStatus(healthRes.status);
        if (healthRes.status === 401) {
          setErrorMessage('Authentication required. Please sign in to access platform administration.');
        } else if (healthRes.status === 403) {
          setErrorMessage('Access denied. Verified platform administrator credentials required.');
        } else {
          setErrorMessage(`Platform operational service returned status ${healthRes.status}.`);
        }
        setLoading(false);
        return;
      }

      const healthData = await healthRes.json();
      setHealth(healthData);

      // 2. Fetch Metrics
      const metricsRes = await fetchWithAuth(`${API_BASE_URL}/platform/metrics`);
      if (metricsRes.ok) {
        setMetrics(await metricsRes.json());
      }

      // 3. Fetch Tenants
      const tenantsRes = await fetchWithAuth(`${API_BASE_URL}/platform/tenants`);
      if (tenantsRes.ok) {
        setTenants(await tenantsRes.json());
      }

      // 4. Fetch Support Access Policy
      const supportRes = await fetchWithAuth(`${API_BASE_URL}/platform/support-access/status`);
      if (supportRes.ok) {
        setSupportStatus(await supportRes.json());
      }

      // 5. Fetch Audit Logs
      const auditRes = await fetchWithAuth(`${API_BASE_URL}/platform/audit-logs`);
      if (auditRes.ok) {
        setAuditLogs(await auditRes.json());
      }

      // 6. Fetch Advocates / Lawyers
      try {
        const advList = await fetchPlatformAdvocates();
        setAdvocates(advList);
      } catch (err) {
        console.warn('Failed to load advocate profiles:', err);
      }

      // 7. Fetch Demo Reset Preview
      try {
        const demoData = await previewDemoReset();
        setDemoPreview(demoData);
      } catch (err) {
        console.warn('Demo preview unavailable:', err);
      }

      // 8. Fetch Customer Handover Checklist
      try {
        const handoverData = await getCustomerHandoverChecklist();
        setHandoverChecklist(handoverData.checklist || []);
      } catch (err) {
        console.warn('Handover checklist unavailable:', err);
      }
    } catch (err: unknown) {
      setErrorStatus(500);
      setErrorMessage(err instanceof Error ? err.message : 'Unable to connect to platform API.');
    } finally {
      setLoading(false);
    }
  }

  async function handleExecuteResetDemo() {
    if (resetConfirmationInput.trim() !== 'RESET DEMO') {
      setDemoResetError("Confirmation mismatch. Type 'RESET DEMO' exactly.");
      return;
    }
    setDemoResetLoading(true);
    setDemoResetError(null);
    setDemoResetSuccess(null);
    try {
      const res = await resetDemoWorkspace('RESET DEMO', reseedDemo);
      setIsResetModalOpen(false);
      setResetConfirmationInput('');
      setDemoResetSuccess(
        `Demo workspace '${res.organization_name}' reset successfully. Purged ${res.deleted_counts.contracts || 0} contracts and ${res.deleted_storage_files} files. Baseline status: ${res.reseeded ? `${res.reseeded_contracts_count} baseline contracts` : 'Clean workspace'}.`
      );
      fetchAdminData();
    } catch (err: unknown) {
      setDemoResetError(err instanceof Error ? err.message : 'Demo reset failed.');
    } finally {
      setDemoResetLoading(false);
    }
  }


  // ACCESS DENIED OR UNAUTHENTICATED STATE
  if (!loading && errorStatus !== null) {
    return (
      <div className="bg-[#F7F3EA] text-[#242321] min-h-screen selection:bg-[#3F4634] selection:text-[#FCFAF5]">
        <header className="h-16 border-b border-[#DED6C8] px-6 lg:px-12 flex items-center justify-between bg-[#F7F3EA] sticky top-0 z-40">
          <div className="flex items-center gap-4">
            <Link href="/" className="font-serif tracking-widest text-lg font-bold text-[#242321]">
              CONTRACTLY
            </Link>
            <span className="text-xs font-mono text-[#6F6A61] border-l border-[#DED6C8] pl-4">
              Platform Administration
            </span>
          </div>
          <Link href="/" className="text-xs font-medium text-[#3F4634] hover:underline">
            ← Return to Workspace
          </Link>
        </header>

        <main className="max-w-3xl mx-auto px-6 py-16">
          <div className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] p-8 space-y-6 shadow-sm">
            <div className="space-y-2">
              <span className="font-mono text-[11px] uppercase tracking-wider text-[#A33B3B] font-bold">
                Security Directive • Access Restricted
              </span>
              <h1 className="text-2xl font-serif font-bold text-[#242321]">
                Platform Administrator Privilege Required
              </h1>
            </div>

            <p className="text-xs sm:text-sm text-[#6F6A61] leading-relaxed">
              {errorMessage}
            </p>

            <div className="p-4 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] text-xs space-y-2 text-[#6F6A61]">
              <span className="font-mono text-[10px] uppercase font-bold text-[#3F4634] block">
                Separation of Customer and Platform Roles
              </span>
              <p>
                In accordance with Contractly&apos;s privacy-first architecture, platform administration is strictly isolated from customer organization workspaces. Organization owners and members manage their agreements directly within their tenant dashboard and cannot access platform infrastructure controls.
              </p>
            </div>

            <div className="pt-2 flex items-center gap-4">
              <Link
                href="/login"
                className="px-4 py-2 bg-[#3F4634] text-[#FCFAF5] text-xs font-medium rounded-[2px] hover:bg-[#2C3124] transition-colors"
              >
                Sign In with Platform Credentials
              </Link>
              <Link
                href="/"
                className="px-4 py-2 bg-[#FCFAF5] border border-[#DED6C8] text-[#242321] text-xs font-medium rounded-[2px] hover:bg-[#F7F3EA] transition-colors"
              >
                Return to Customer Dashboard
              </Link>
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="bg-[#F7F3EA] text-[#242321] min-h-screen selection:bg-[#3F4634] selection:text-[#FCFAF5]">
      {/* Header */}
      <header className="h-16 border-b border-[#DED6C8] px-6 lg:px-12 flex items-center justify-between bg-[#F7F3EA]/90 sticky top-0 z-40 backdrop-blur-sm">
        <div className="flex items-center gap-4">
          <Link href="/" className="font-serif tracking-widest text-lg font-bold text-[#242321]">
            CONTRACTLY
          </Link>
          <span className="text-xs font-mono text-[#6F6A61] border-l border-[#DED6C8] pl-4">
            Platform Operational Console
          </span>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="font-mono text-[11px] text-[#3F4634] bg-[#FCFAF5] px-2 py-1 border border-[#DED6C8] rounded-[2px]">
            {health?.audited_by_user ? `Auditor: ${health.audited_by_user}` : 'Platform Admin'}
          </span>
          <a href="#lawyer-management" className="font-medium text-[#3F4634] hover:underline">
            Lawyer Management
          </a>
          <Link href="/dashboard" className="font-medium text-[#3F4634] hover:underline">
            Workspace
          </Link>
          <button
            onClick={() => logout()}
            className="px-2.5 py-1 text-xs font-semibold text-[#8B3F3F] bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] hover:bg-[#FDF2F2] transition-colors"
          >
            Sign Out
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-6xl mx-auto px-6 py-10 space-y-10">
        {/* Title Section */}
        <div className="space-y-2 border-b border-[#DED6C8] pb-6">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[11px] uppercase tracking-wider text-[#3F4634] font-bold">
              Privacy-First Platform Administration • Phase 4A
            </span>
            <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-mono font-bold bg-[#E8EFE0] text-[#3F4634] border border-[#C5D5B8] rounded-[2px]">
              System Status: {health?.status || 'Active'}
            </span>
          </div>
          <h1 className="text-3xl font-serif font-bold text-[#242321]">
            Operational Overview &amp; Tenant Integrity
          </h1>
          <p className="text-xs text-[#6F6A61] leading-relaxed max-w-3xl">
            This administrative console provides operational health, aggregate capacity, and tenant lifecycle status. Pursuant to Contractly&apos;s data protection policy, platform administrators cannot routinely read, download, or inspect customer contract contents, clauses, or AI interactions.
          </p>
        </div>

        {/* Aggregate Operational Metrics */}
        <section className="space-y-4">
          <h2 className="text-sm font-serif font-bold text-[#242321] uppercase tracking-wider">
            Aggregate Platform Metrics (Content-Excluded)
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4">
            <div className="bg-[#FCFAF5] border border-[#DED6C8] p-4 rounded-[2px]">
              <span className="text-[11px] font-mono text-[#6F6A61] uppercase block">Tenant Orgs</span>
              <span className="text-2xl font-serif font-bold text-[#242321] mt-1 block">
                {metrics ? metrics.tenants_count : '...'}
              </span>
              <span className="text-[10px] text-[#6F6A61] mt-1 block">Isolated boundaries</span>
            </div>

            <div className="bg-[#FCFAF5] border border-[#DED6C8] p-4 rounded-[2px]">
              <span className="text-[11px] font-mono text-[#6F6A61] uppercase block">Accounts</span>
              <span className="text-2xl font-serif font-bold text-[#242321] mt-1 block">
                {metrics ? metrics.users_count : '...'}
              </span>
              <span className="text-[10px] text-[#6F6A61] mt-1 block">Registered users</span>
            </div>

            <div className="bg-[#FCFAF5] border border-[#DED6C8] p-4 rounded-[2px]">
              <span className="text-[11px] font-mono text-[#6F6A61] uppercase block">Contracts</span>
              <span className="text-2xl font-serif font-bold text-[#242321] mt-1 block">
                {metrics ? metrics.total_contracts_count : '...'}
              </span>
              <span className="text-[10px] text-[#6F6A61] mt-1 block">Content excluded</span>
            </div>

            <div className="bg-[#FCFAF5] border border-[#DED6C8] p-4 rounded-[2px]">
              <span className="text-[11px] font-mono text-[#6F6A61] uppercase block">Storage Quota</span>
              <span className="text-2xl font-serif font-bold text-[#242321] mt-1 block">
                {metrics
                  ? `${(metrics.allocated_storage_quota_bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
                  : '...'}
              </span>
              <span className="text-[10px] text-[#6F6A61] mt-1 block">Allocated capacity</span>
            </div>

            <div className="bg-[#FCFAF5] border border-[#DED6C8] p-4 rounded-[2px]">
              <span className="text-[11px] font-mono text-[#6F6A61] uppercase block">Advocate Profiles</span>
              <span className="text-2xl font-serif font-bold text-[#242321] mt-1 block">
                {metrics ? metrics.advocates_count ?? 0 : '...'}
              </span>
              <span className="text-[10px] text-[#6F6A61] mt-1 block">
                {metrics?.pending_advocates_count ?? 0} pending review
              </span>
            </div>

            <div className="bg-[#FCFAF5] border border-[#DED6C8] p-4 rounded-[2px]">
              <span className="text-[11px] font-mono text-[#6F6A61] uppercase block">Legal Matters</span>
              <span className="text-2xl font-serif font-bold text-[#242321] mt-1 block">
                {metrics?.matters_by_status
                  ? Object.values(metrics.matters_by_status).reduce((a, b) => a + b, 0)
                  : 0}
              </span>
              <span className="text-[10px] text-[#6F6A61] mt-1 block">
                {metrics?.matters_by_status?.['MATTER_ACTIVE'] ?? 0} active matters
              </span>
            </div>
          </div>
        </section>

        {/* System Health Breakdown */}
        <section className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] p-6 space-y-4">
          <h2 className="text-sm font-serif font-bold text-[#242321] uppercase tracking-wider">
            Operational Infrastructure &amp; Provider Health
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-6 text-xs">
            <div className="space-y-1">
              <span className="text-[10px] font-mono uppercase text-[#6F6A61] block">Relational Database</span>
              <div className="font-medium text-[#242321]">
                {health?.database.engine.toUpperCase()} ({health?.database.status})
              </div>
              <p className="text-[11px] text-[#6F6A61]">Readiness: {health?.database.readiness}</p>
            </div>

            <div className="space-y-1">
              <span className="text-[10px] font-mono uppercase text-[#6F6A61] block">Document Object Store</span>
              <div className="font-medium text-[#242321]">
                Provider: {health?.storage.provider.toUpperCase()}
              </div>
              <p className="text-[11px] text-[#6F6A61]">Status: {health?.storage.status} (Tenant-scoped keys)</p>
            </div>

            <div className="space-y-1">
              <span className="text-[10px] font-mono uppercase text-[#6F6A61] block">Notification Engine</span>
              <div className="font-medium text-[#242321]">
                Autonomous Scheduler: {health?.scheduler.enabled ? 'ACTIVE' : 'DISABLED'}
              </div>
              <p className="text-[11px] text-[#6F6A61]">Interval: Every {health?.scheduler.interval_hours} hours</p>
            </div>

            <div className="space-y-1">
              <span className="text-[10px] font-mono uppercase text-[#6F6A61] block">Email Delivery Service</span>
              <div className="font-medium text-[#242321]">
                {health?.email?.configured ? `CONFIGURED (${health.email.provider.toUpperCase()})` : 'UNCONFIGURED (Inactive)'}
              </div>
              <p className="text-[11px] text-[#6F6A61]">
                {health?.email?.configured ? `Host: ${health.email.host || 'Relay'}` : 'Missing production SMTP'}
              </p>
            </div>

            <div className="space-y-1">
              <span className="text-[10px] font-mono uppercase text-[#6F6A61] block">Distributed Rate Limiter</span>
              <div className="font-medium text-[#242321]">
                Backend: {health?.rate_limiter?.backend.toUpperCase()}
              </div>
              <p className="text-[11px] text-[#6F6A61]">
                Mode: {health?.rate_limiter?.mode || 'local_in_memory'}
              </p>
            </div>
          </div>
        </section>

        {/* Tenant Organization Directory */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-serif font-bold text-[#242321] uppercase tracking-wider">
              Tenant Organization Directory ({tenants.length})
            </h2>
            <span className="text-xs font-mono text-[#6F6A61]">
              Strictly non-content operational listing
            </span>
          </div>

          <div className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-[#DED6C8] bg-[#F7F3EA] text-[11px] font-mono text-[#6F6A61]">
                  <th className="py-2.5 px-4 font-normal">Tenant Name</th>
                  <th className="py-2.5 px-4 font-normal">Slug</th>
                  <th className="py-2.5 px-4 font-normal">Account Type</th>
                  <th className="py-2.5 px-4 font-normal">Subscription</th>
                  <th className="py-2.5 px-4 font-normal">Storage Quota</th>
                  <th className="py-2.5 px-4 font-normal">Active Members</th>
                  <th className="py-2.5 px-4 font-normal">Contract Volume</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#DED6C8]">
                {tenants.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-6 text-center text-[#6F6A61] italic">
                      No tenant organizations registered.
                    </td>
                  </tr>
                ) : (
                  tenants.map((t) => (
                    <tr key={t.id} className="hover:bg-[#F7F3EA]/50">
                      <td className="py-3 px-4 font-medium text-[#242321]">{t.name}</td>
                      <td className="py-3 px-4 font-mono text-[11px] text-[#6F6A61]">{t.slug}</td>
                      <td className="py-3 px-4 text-[#6F6A61]">{t.account_type}</td>
                      <td className="py-3 px-4">
                        <span className="font-mono text-[10px] bg-[#F7F3EA] px-2 py-0.5 border border-[#DED6C8] rounded-[2px]">
                          {t.subscription_tier}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono text-[11px] text-[#6F6A61]">
                        {(t.storage_quota_bytes / (1024 * 1024 * 1024)).toFixed(0)} GB
                      </td>
                      <td className="py-3 px-4 font-mono text-[11px] text-[#242321]">{t.member_count}</td>
                      <td className="py-3 px-4 font-mono text-[11px] text-[#242321]">{t.contract_count}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* Demonstration Workspace Management & Safe Reset */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-serif font-bold text-[#242321] uppercase tracking-wider">
                Demonstration Workspace Management &amp; Safe Reset
              </h2>
              <p className="text-xs text-[#6F6A61] mt-0.5">
                Manage and reset the designated demonstration workspace without affecting genuine customer organizations or advocate profiles.
              </p>
            </div>
            {demoResetSuccess && (
              <span className="text-xs font-mono text-[#2E5230] bg-[#EDF2EC] px-2.5 py-1 border border-[#C6D8C6] rounded-[2px]">
                {demoResetSuccess}
              </span>
            )}
          </div>

          <div className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] p-6 space-y-5">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-[#DED6C8] pb-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="font-serif font-bold text-base text-[#242321]">
                    {demoPreview?.organization_name || 'Designated Demo Workspace'}
                  </span>
                  <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-[#FDF8EE] text-[#7A4D1A] border border-[#E8D9B5] rounded-[2px]">
                    DEMO SLUG: {demoPreview?.organization_slug || 'northstar-tech'}
                  </span>
                </div>
                <p className="text-xs text-[#6F6A61]">
                  Stable Workspace ID: <span className="font-mono text-[#242321]">{demoPreview?.organization_id || '9ed3fc91-52b5-4ed8-a3a7-9100451291cb'}</span>
                </p>
                {demoPreview?.last_reset_at && (
                  <p className="text-[11px] text-[#6F6A61] font-mono">
                    Last reset executed: {new Date(demoPreview.last_reset_at).toLocaleString()}
                  </p>
                )}
              </div>

              <button
                onClick={() => {
                  setDemoResetError(null);
                  setResetConfirmationInput('');
                  setReseedDemo(true);
                  setIsResetModalOpen(true);
                }}
                disabled={!demoPreview?.demo_org_found}
                className="px-4 py-2 bg-[#FCFAF5] border border-[#C97A7E] text-[#A33B3B] text-xs font-semibold rounded-[2px] hover:bg-[#FDF2F2] transition-colors disabled:opacity-40"
              >
                Reset Demo Workspace
              </button>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-6 gap-3 text-xs">
              <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px]">
                <span className="text-[10px] font-mono text-[#6F6A61] uppercase block">Demo Contracts</span>
                <span className="text-xl font-serif font-bold text-[#242321] mt-1 block">
                  {demoPreview?.contracts_count ?? 0}
                </span>
                <span className="text-[10px] text-[#6F6A61]">Illustrative data</span>
              </div>
              <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px]">
                <span className="text-[10px] font-mono text-[#6F6A61] uppercase block">Doc Versions</span>
                <span className="text-xl font-serif font-bold text-[#242321] mt-1 block">
                  {demoPreview?.versions_count ?? 0}
                </span>
                <span className="text-[10px] text-[#6F6A61]">File metadata</span>
              </div>
              <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px]">
                <span className="text-[10px] font-mono text-[#6F6A61] uppercase block">Obligations</span>
                <span className="text-xl font-serif font-bold text-[#242321] mt-1 block">
                  {demoPreview?.obligations_count ?? 0}
                </span>
                <span className="text-[10px] text-[#6F6A61]">Commitments</span>
              </div>
              <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px]">
                <span className="text-[10px] font-mono text-[#6F6A61] uppercase block">Stored Files</span>
                <span className="text-xl font-serif font-bold text-[#242321] mt-1 block">
                  {demoPreview?.files_count ?? 0}
                </span>
                <span className="text-[10px] text-[#6F6A61]">StorageClient files</span>
              </div>
              <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px]">
                <span className="text-[10px] font-mono text-[#6F6A61] uppercase block">Deadlines</span>
                <span className="text-xl font-serif font-bold text-[#242321] mt-1 block">
                  {demoPreview?.calendar_events_count ?? 0}
                </span>
                <span className="text-[10px] text-[#6F6A61]">Calendar events</span>
              </div>
              <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px]">
                <span className="text-[10px] font-mono text-[#6F6A61] uppercase block">Internal Notes</span>
                <span className="text-xl font-serif font-bold text-[#242321] mt-1 block">
                  {demoPreview?.notes_count ?? 0}
                </span>
                <span className="text-[10px] text-[#6F6A61]">Discussion notes</span>
              </div>
            </div>

            <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] text-xs text-[#6F6A61] space-y-1">
              <span className="font-mono text-[10px] font-bold text-[#3F4634] uppercase block">
                Safety &amp; Isolation Guarantees
              </span>
              <p>• Demo reset is cryptographically restricted to the designated demo organization (<span className="font-mono text-[#242321]">northstar-tech</span>).</p>
              <p>• Genuine customer accounts, private client contracts, registered advocates, and live legal matters are NEVER deleted or modified.</p>
              <p>• Document files are removed via the configured <span className="font-mono text-[#242321]">StorageClient</span> backend without touching raw filesystem paths.</p>
            </div>
          </div>
        </section>

        {/* Customer Onboarding & Handover Checklist */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-serif font-bold text-[#242321] uppercase tracking-wider">
                Customer Onboarding &amp; Clean Workspace Handover Checklist
              </h2>
              <p className="text-xs text-[#6F6A61] mt-0.5">
                Standard operational requirements for adopting customers to start with clean workspaces and zero demo contamination.
              </p>
            </div>
            <span className="font-mono text-[11px] text-[#2E5230] bg-[#EDF2EC] px-2.5 py-1 border border-[#C6D8C6] rounded-[2px]">
              Handover Protocol Active
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {handoverChecklist.map((item) => (
              <div key={item.id} className="bg-[#FCFAF5] border border-[#DED6C8] p-4 rounded-[2px] space-y-2 flex flex-col justify-between">
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] text-[#6F6A61]">
                      {item.category}
                    </span>
                    <span className={`text-[10px] font-mono font-bold px-2 py-0.5 border rounded-[2px] ${
                      item.status === 'COMPLETED'
                        ? 'bg-[#EDF2EC] text-[#2E5230] border-[#C6D8C6]'
                        : 'bg-[#F7EFE4] text-[#7A4D1A] border-[#E5D2B8]'
                    }`}>
                      {item.status}
                    </span>
                  </div>
                  <h3 className="font-serif font-bold text-xs text-[#242321]">{item.title}</h3>
                  <p className="text-[11px] text-[#6F6A61] leading-relaxed">{item.description}</p>
                </div>
                <div className="pt-2 border-t border-[#DED6C8] text-[10px] font-mono text-[#3F4634]">
                  ✓ Verified by Architecture Policy
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Demo Reset Safety Modal */}
        {isResetModalOpen && (
          <div className="fixed inset-0 z-50 bg-[#242321]/50 backdrop-blur-xs flex items-center justify-center p-4">
            <div className="bg-[#FCFAF5] border border-[#DED6C8] max-w-lg w-full p-6 rounded-[2px] shadow-lg space-y-4">
              <div className="border-b border-[#DED6C8] pb-3">
                <span className="font-mono text-[10px] uppercase font-bold text-[#A33B3B] block">
                  Platform Action • Demo Environment Reset
                </span>
                <h3 className="text-lg font-serif font-bold text-[#242321] mt-0.5">
                  Reset Designated Demo Workspace
                </h3>
              </div>

              <p className="text-xs text-[#6F6A61] leading-relaxed">
                This operation will delete all demo-generated contracts, versions, obligations, calendar entries, and associated storage files in <strong className="text-[#242321]">{demoPreview?.organization_name}</strong>.
              </p>

              <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] text-xs text-[#6F6A61] space-y-1">
                <span className="font-mono text-[10px] font-bold text-[#3F4634] block uppercase">
                  Safety Enforcement
                </span>
                <p>• Only records in <span className="font-mono text-[#242321]">northstar-tech</span> will be affected.</p>
                <p>• All genuine customer workspaces and advocate records are strictly preserved.</p>
                <p>• Deletion and reset execution is immutably logged in the platform audit trail.</p>
              </div>

              <div className="space-y-2 pt-1">
                <label className="flex items-center gap-2 cursor-pointer text-xs text-[#242321]">
                  <input
                    type="checkbox"
                    checked={reseedDemo}
                    onChange={(e) => setReseedDemo(e.target.checked)}
                    className="accent-[#3F4634]"
                  />
                  <span>Re-seed clean illustrative contracts after reset (CloudStack MSA and Employment Agreement)</span>
                </label>
              </div>

              {demoResetError && (
                <div className="p-2 bg-[#FDF2F2] border border-[#F2C6C6] text-[#A33B3B] text-xs rounded-[2px]">
                  {demoResetError}
                </div>
              )}

              <div className="space-y-1.5">
                <label className="text-[11px] font-mono text-[#6F6A61] block">
                  Type <strong className="text-[#A33B3B]">RESET DEMO</strong> to confirm:
                </label>
                <input
                  type="text"
                  value={resetConfirmationInput}
                  onChange={(e) => setResetConfirmationInput(e.target.value)}
                  placeholder="RESET DEMO"
                  className="w-full px-3 py-1.5 text-xs bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] font-mono text-[#242321] focus:outline-none focus:border-[#3F4634]"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  onClick={() => setIsResetModalOpen(false)}
                  disabled={demoResetLoading}
                  className="px-3 py-1.5 bg-[#FCFAF5] border border-[#DED6C8] text-[#242321] text-xs font-medium rounded-[2px] hover:bg-[#F7F3EA] transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleExecuteResetDemo}
                  disabled={demoResetLoading || resetConfirmationInput.trim() !== 'RESET DEMO'}
                  className="px-4 py-1.5 bg-[#A33B3B] text-[#FCFAF5] text-xs font-semibold rounded-[2px] hover:bg-[#8B2F2F] transition-colors disabled:opacity-40"
                >
                  {demoResetLoading ? 'Resetting Demo...' : 'Confirm Reset Demo'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Dedicated Lawyer Management & Bar Council Credential Verification */}
        <LawyerManagement initialLawyers={advocates} onRefresh={fetchAdminData} />

        {/* Platform Conversation Oversight & Audit */}
        <ConversationOversight onRefresh={fetchAdminData} />

        {/* Exceptional Support Access Policy Disclosure */}
        <section className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-[#DED6C8] pb-3">
            <h2 className="text-sm font-serif font-bold text-[#242321] uppercase tracking-wider">
              Exceptional Support Access Policy
            </h2>
            <span className="font-mono text-[10px] font-bold px-2 py-0.5 bg-[#F7EFE4] text-[#7A4D1A] border border-[#E5D2B8] rounded-[2px]">
              {supportStatus?.policy || 'DISABLED_BY_DEFAULT'}
            </span>
          </div>

          <p className="text-xs text-[#6F6A61] leading-relaxed">
            {supportStatus?.description}
          </p>

          <div className="space-y-2 pt-2">
            <span className="text-[11px] font-mono uppercase text-[#3F4634] font-bold block">
              Architectural Guardrails &amp; Prerequisites:
            </span>
            <ul className="list-disc pl-5 text-xs text-[#6F6A61] space-y-1">
              {supportStatus?.exceptional_access_requirements.map((req, idx) => (
                <li key={idx}>{req}</li>
              ))}
            </ul>
          </div>
        </section>

        {/* Platform Audit Trail */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-serif font-bold text-[#242321] uppercase tracking-wider">
              Platform Administrative Audit Trail
            </h2>
            <span className="text-xs font-mono text-[#6F6A61]">
              Privileged system events
            </span>
          </div>

          <div className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] overflow-hidden">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-[#DED6C8] bg-[#F7F3EA] text-[11px] font-mono text-[#6F6A61]">
                  <th className="py-2 px-4 font-normal">Timestamp</th>
                  <th className="py-2 px-4 font-normal">Admin User</th>
                  <th className="py-2 px-4 font-normal">Action</th>
                  <th className="py-2 px-4 font-normal">Operational Detail</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#DED6C8]">
                {auditLogs.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="py-4 text-center text-[#6F6A61] italic">
                      No administrative audit events recorded.
                    </td>
                  </tr>
                ) : (
                  auditLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-[#F7F3EA]/50">
                      <td className="py-2.5 px-4 font-mono text-[10px] text-[#6F6A61]">
                        {log.created_at ? new Date(log.created_at).toLocaleString() : 'N/A'}
                      </td>
                      <td className="py-2.5 px-4 font-medium text-[#242321]">{log.user_email}</td>
                      <td className="py-2.5 px-4 font-mono text-[10px] text-[#3F4634]">{log.action}</td>
                      <td className="py-2.5 px-4 text-[#6F6A61] text-[11px]">{log.detail}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  );
}
