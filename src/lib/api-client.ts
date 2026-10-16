import {
  ContractItem,
  ContractRiskItem,
  CurrentUser,
  OrganizationInfo,
  ObligationItem,
  ObligationStatus,
  VendorProfile,
  PlaybookRule,
  AuditLogEntry,
  RedlineItem,
  ContractVersionItem,
  NegotiationFindingItem,
  ContractLifecycleSummary,
  ContractIntelligenceData,
  ContractMetadata,
  ContractQAResult,
  ContractQASource,
  GeneralChatResult,
  LawyerInquiryResult,
  CalendarEventItem,
  ContractNoteItem,
  ThingToDoItem,
  NotificationItem,
  NotificationPreferences,
  AdvocateProfile,
  WorkspaceSummaryResponse,
  WorkspaceCategorySummary,
  DemoResetPreviewResponse,
  DemoResetResultResponse,
  CustomerHandoverChecklistResponse,
  HandoverChecklistItem,
  MatterMessageItem,
  ConversationItem,
  AdminConversationItem,
  AdminConversationReviewResponse,
  AdminConsultationRequestItem,
  AdminConsultationDecisionResponse,
  ActivityItem,
  ActivityListResponse,
  ActivityFilterParams,
} from '@/types/contractly';

export type {
  AdminConsultationRequestItem,
  AdminConsultationDecisionResponse,
  CalendarEventItem,
  ContractNoteItem,
  ThingToDoItem,
  NotificationItem,
  NotificationPreferences,
  LawyerInquiryResult,
  WorkspaceSummaryResponse,
  WorkspaceCategorySummary,
  DemoResetPreviewResponse,
  DemoResetResultResponse,
  CustomerHandoverChecklistResponse,
  HandoverChecklistItem
};

const rawBase = (process.env.NEXT_PUBLIC_API_URL || '').trim();
const API_BASE_URL = rawBase
  ? (rawBase.endsWith('/api/v1') ? rawBase : `${rawBase.replace(/\/+$/, '')}/api/v1`)
  : (typeof window !== 'undefined' ? '/api/v1' : 'http://127.0.0.1:8000/api/v1');


let isRefreshing = false;
let refreshSubscribers: ((success: boolean) => void)[] = [];

function onRefreshed(success: boolean) {
  refreshSubscribers.forEach((callback) => callback(success));
  refreshSubscribers = [];
}

function addRefreshSubscriber(callback: (success: boolean) => void) {
  refreshSubscribers.push(callback);
}

export interface FetchWithAuthOptions extends RequestInit {
  skipRedirect?: boolean;
}

/**
 * Core authenticated fetch wrapper that includes credentials (HttpOnly cookies)
 * and automatically executes silent refresh with a single retry upon 401 TOKEN_EXPIRED.
 */
export async function fetchWithAuth(input: string, init: FetchWithAuthOptions = {}): Promise<Response> {
  const { skipRedirect, ...fetchInit } = init;
  const headers = new Headers(fetchInit.headers || {});
  if (!headers.has('Content-Type') && !(fetchInit.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const config: RequestInit = {
    ...fetchInit,
    headers,
    credentials: 'include' // Always pass secure HttpOnly cookies
  };

  const res = await fetch(input, config);

  // If 401 Unauthorized, perform silent refresh
  if (res.status === 401) {
    if (!isRefreshing) {
      isRefreshing = true;
      let refreshSuccess = false;
      try {
        refreshSuccess = await refreshSession();
      } catch {
        refreshSuccess = false;
      } finally {
        isRefreshing = false;
        onRefreshed(refreshSuccess);
      }

      if (refreshSuccess) {
        // Retry the original request once with new cookies
        return fetch(input, config);
      } else {
        if (!skipRedirect && typeof window !== 'undefined') {
          const path = window.location.pathname;
          const isPublicOrAuthPage =
            path === '/' ||
            path === '/signin' ||
            path === '/signup' ||
            path === '/login' ||
            path === '/register' ||
            path === '/privacy' ||
            path === '/terms' ||
            path === '/forgot-password' ||
            path === '/reset-password' ||
            path === '/verify-email' ||
            path.startsWith('/invitations/accept');

          if (!isPublicOrAuthPage) {
            try {
              localStorage.clear();
              sessionStorage.clear();
            } catch {
              // Ignore potential private-mode security restrictions
            }
            window.location.replace(`/signin?returnUrl=${encodeURIComponent(path)}`);
          }
        }
        return res;
      }
    } else {
      // Wait for ongoing refresh to complete
      return new Promise((resolve) => {
        addRefreshSubscriber(async (success) => {
          if (success) {
            try {
              resolve(await fetch(input, config));
            } catch {
              resolve(res);
            }
          } else {
            resolve(res);
          }
        });
      });
    }
  }

  return res;
}

// ─────────────────────────────────────────────────────────────
// Authentication Actions
// ─────────────────────────────────────────────────────────────

export async function login(
  email: string,
  password: string
): Promise<{ success: boolean; error?: string; user?: CurrentUser }> {
  try {
    const cleanEmail = (email || '').trim().toLowerCase();
    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: cleanEmail, password }),
      credentials: 'include'
    });

    if (!res.ok) {
      let errorMsg = 'Invalid email or password';
      try {
        const err = await res.json();
        if (err && err.detail) {
          errorMsg = err.detail;
        }
      } catch {
        if (res.status >= 500) {
          errorMsg = 'Backend service is starting up or temporarily unavailable. Please retry in a moment.';
        } else {
          errorMsg = 'Authentication failed. Please verify your credentials.';
        }
      }
      return { success: false, error: errorMsg };
    }

    const data = await res.json();
    return {
      success: true,
      user: {
        id: data.user.id,
        email: data.user.email,
        fullName: data.user.full_name,
        organizationId: data.user.organization_id,
        organizationName: data.user.organization_name,
        role: data.user.role,
        accountType: data.user.account_type,
        subscriptionTier: data.user.subscription_tier,
        permissions: data.user.permissions || [],
        entitlements: data.user.entitlements,
        emailVerificationStatus: data.user.email_verification_status,
        isSuperAdmin: !!data.user.is_super_admin,
        platformRole: data.user.platform_role || null
      }
    };
  } catch (err: any) {
    return { success: false, error: err.message || 'Network error connecting to authentication server.' };
  }
}

export async function register(data: {
  email: string;
  password: string;
  fullName: string;
  organizationName?: string;
  accountType?: string;
  role?: string;
}): Promise<{ success: boolean; error?: string; user?: CurrentUser }> {
  try {
    const payload: Record<string, any> = {
      email: data.email,
      password: data.password,
      full_name: data.fullName,
      account_type: data.accountType || 'INDIVIDUAL',
    };
    if (data.organizationName && data.organizationName.trim()) {
      payload.organization_name = data.organizationName.trim();
    }

    const res = await fetch(`${API_BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      credentials: 'include'
    });

    if (!res.ok) {
      const isRateLimited = res.status === 429;
      const defaultMsg = isRateLimited
        ? 'Too many registration attempts from this address. Please wait before retrying.'
        : 'Registration failed';
      const err = await res.json().catch(() => ({ detail: defaultMsg }));
      let errorMsg = defaultMsg;
      if (typeof err.detail === 'string') {
        errorMsg = err.detail;
      } else if (Array.isArray(err.detail) && err.detail.length > 0) {
        const first = err.detail[0];
        errorMsg = (typeof first === 'string' ? first : first.msg) || 'Validation error';
        errorMsg = errorMsg.replace(/^Value error,\s*/i, '');
      } else if (typeof err.message === 'string') {
        errorMsg = err.message;
      } else if (typeof err.error === 'string') {
        errorMsg = err.error;
      }
      return { success: false, error: errorMsg };
    }

    const resData = await res.json();
    return {
      success: true,
      user: {
        id: resData.user.id,
        email: resData.user.email,
        fullName: resData.user.full_name,
        organizationId: resData.user.organization_id,
        organizationName: resData.user.organization_name,
        role: resData.user.role,
        accountType: resData.user.account_type,
        subscriptionTier: resData.user.subscription_tier,
        permissions: resData.user.permissions || [],
        entitlements: resData.user.entitlements,
        emailVerificationStatus: resData.user.email_verification_status,
        isSuperAdmin: !!resData.user.is_super_admin,
        platformRole: resData.user.platform_role || null
      }
    };
  } catch (err: any) {
    return { success: false, error: err.message || 'Network error during registration.' };
  }
}

export async function logout(): Promise<void> {
  try {
    await fetch(`${API_BASE_URL}/auth/logout`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include'
    });
  } catch (err) {
    console.warn('Logout API error:', err);
  } finally {
    // Defense-in-depth: Clear client-side accessible auth cookies
    if (typeof document !== 'undefined') {
      document.cookie = 'contractly_access_token=; path=/; max-age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT;';
      document.cookie = 'contractly_refresh_token=; path=/; max-age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT;';
    }
    // Clear any local or session storage
    if (typeof window !== 'undefined') {
      try {
        localStorage.clear();
        sessionStorage.clear();
      } catch {
        // Ignore potential private-mode security restrictions
      }
      // Replace window location to /signin to prevent Back navigation re-entry
      window.location.replace('/signin');
    }
  }
}

export async function refreshSession(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include'
    });
    return res.ok;
  } catch (err) {
    console.warn('Silent refresh error:', err);
    return false;
  }
}

export async function forgotPassword(email: string): Promise<{ success: boolean; message: string; error?: string }> {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/forgot-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    const data = await res.json();
    return { success: res.ok, message: data.message || 'If an account exists, instructions have been sent.' };
  } catch (err: any) {
    return { success: false, message: '', error: err.message || 'Network error requesting password reset.' };
  }
}

export async function resetPassword(token: string, newPassword: string): Promise<{ success: boolean; message: string; error?: string }> {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, new_password: newPassword })
    });
    const data = await res.json();
    if (!res.ok) {
      return { success: false, message: '', error: data.detail || 'Password reset failed.' };
    }
    return { success: true, message: data.message || 'Password successfully reset.' };
  } catch (err: any) {
    return { success: false, message: '', error: err.message || 'Network error resetting password.' };
  }
}

export async function verifyEmail(token: string): Promise<{ success: boolean; message: string; error?: string }> {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/verify-email`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token })
    });
    const data = await res.json();
    if (!res.ok) {
      return { success: false, message: '', error: data.detail || 'Email verification failed.' };
    }
    return { success: true, message: data.message || 'Email successfully verified.' };
  } catch (err: any) {
    return { success: false, message: '', error: err.message || 'Network error verifying email.' };
  }
}

export async function resendVerification(email: string): Promise<{ success: boolean; message: string; error?: string }> {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/resend-verification`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    const data = await res.json();
    if (!res.ok) {
      return { success: false, message: '', error: data.detail || 'Failed to resend verification email.' };
    }
    return { success: true, message: data.message || 'Verification link sent.' };
  } catch (err: any) {
    return { success: false, message: '', error: err.message || 'Network error resending verification.' };
  }
}

export async function getEmailVerificationStatus(): Promise<{
  emailDeliveryConfigured: boolean;
  verificationStatus: string;
  provider?: string;
  detail?: string;
}> {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/verification-status`);
    if (!res.ok) {
      return {
        emailDeliveryConfigured: false,
        verificationStatus: 'BLOCKED_UNCONFIGURED',
        detail: 'Failed to query email service status.'
      };
    }
    const data = await res.json();
    return {
      emailDeliveryConfigured: data.email_delivery_configured,
      verificationStatus: data.verification_status,
      provider: data.provider,
      detail: data.detail
    };
  } catch {
    return {
      emailDeliveryConfigured: false,
      verificationStatus: 'BLOCKED_UNCONFIGURED',
      detail: 'Network error checking email delivery readiness.'
    };
  }
}

export async function createInvitation(email: string, role: string = 'MEMBER'): Promise<{ success: boolean; data?: any; error?: string }> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/organizations/invitations`, {
      method: 'POST',
      body: JSON.stringify({ email, role })
    });
    const data = await res.json();
    if (!res.ok) {
      return { success: false, error: data.detail || 'Failed to create invitation.' };
    }
    return { success: true, data };
  } catch (err: any) {
    return { success: false, error: err.message || 'Network error creating invitation.' };
  }
}

export async function listInvitations(): Promise<{ success: boolean; data?: any[]; error?: string }> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/organizations/invitations`, {
      method: 'GET'
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      return { success: false, error: data.detail || 'Failed to list invitations.' };
    }
    const data = await res.json();
    return { success: true, data };
  } catch (err: any) {
    return { success: false, error: err.message || 'Network error listing invitations.' };
  }
}

export async function revokeInvitation(invitationId: string): Promise<{ success: boolean; message?: string; error?: string }> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/organizations/invitations/${invitationId}/revoke`, {
      method: 'POST'
    });
    const data = await res.json();
    if (!res.ok) {
      return { success: false, error: data.detail || 'Failed to revoke invitation.' };
    }
    return { success: true, message: data.message };
  } catch (err: any) {
    return { success: false, error: err.message || 'Network error revoking invitation.' };
  }
}

export async function verifyInvitationToken(token: string): Promise<{ success: boolean; data?: any; error?: string }> {
  try {
    const res = await fetch(`${API_BASE_URL}/organizations/invitations/verify?token=${encodeURIComponent(token)}`);
    const data = await res.json();
    if (!res.ok) {
      return { success: false, error: data.detail || 'Invalid invitation.' };
    }
    return { success: true, data };
  } catch (err: any) {
    return { success: false, error: err.message || 'Network error verifying invitation.' };
  }
}

export async function acceptInvitation(
  token: string,
  fullName?: string,
  password?: string
): Promise<{ success: boolean; message?: string; error?: string }> {
  try {
    const res = await fetch(`${API_BASE_URL}/organizations/invitations/accept`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, full_name: fullName, password })
    });
    const data = await res.json();
    if (!res.ok) {
      return { success: false, error: data.detail || 'Failed to accept invitation.' };
    }
    return { success: true, message: data.message };
  } catch (err: any) {
    return { success: false, error: err.message || 'Network error accepting invitation.' };
  }
}


// ─────────────────────────────────────────────────────────────
// Priority Endpoints
// ─────────────────────────────────────────────────────────────

// 1. Current Authenticated User
export async function fetchCurrentUser(): Promise<CurrentUser | null> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/auth/me`, {
      method: 'GET',
      cache: 'no-store',
      skipRedirect: true
    });
    if (!res.ok) return null;
    const data = await res.json();
    return {
      id: data.id,
      email: data.email,
      fullName: data.full_name,
      organizationId: data.organization_id,
      organizationName: data.organization_name,
      role: data.role,
      accountType: data.account_type,
      subscriptionTier: data.subscription_tier,
      permissions: data.permissions || [],
      entitlements: data.entitlements,
      emailVerificationStatus: data.email_verification_status,
      isSuperAdmin: !!data.is_super_admin,
      platformRole: data.platform_role || null
    };
  } catch (err) {
    console.warn('Backend /auth/me unavailable:', err);
    return null;
  }
}

export async function updateUserProfile(payload: { full_name: string }): Promise<CurrentUser> {
  const res = await fetchWithAuth(`${API_BASE_URL}/auth/profile`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    let msg = 'Failed to update profile';
    if (typeof err.detail === 'string') msg = err.detail;
    else if (Array.isArray(err.detail) && err.detail[0]?.msg) msg = err.detail[0].msg;
    throw new Error(msg);
  }
  const data = await res.json();
  return {
    id: data.id,
    email: data.email,
    fullName: data.full_name,
    organizationId: data.organization_id,
    organizationName: data.organization_name,
    role: data.role,
    accountType: data.account_type,
    subscriptionTier: data.subscription_tier,
    permissions: data.permissions || [],
    entitlements: data.entitlements,
    emailVerificationStatus: data.email_verification_status,
    isSuperAdmin: !!data.is_super_admin,
    platformRole: data.platform_role || null
  };
}

// 2. Organization Details
export async function fetchCurrentOrganization(): Promise<OrganizationInfo | null> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/organizations/current`, {
      method: 'GET',
      cache: 'no-store'
    });
    if (!res.ok) return null;
    const data = await res.json();
    return {
      id: data.id,
      name: data.name,
      slug: data.slug,
      accountType: data.account_type,
      subscriptionTier: data.subscription_tier,
      storageQuotaBytes: data.storage_quota_bytes,
      is_personal: data.is_personal,
      entitlements: data.entitlements
    };
  } catch (err) {
    console.warn('Backend /organizations/current unavailable:', err);
    return null;
  }
}

// 2b. My Organizations List & Switch Tenant
export async function fetchMyOrganizations(): Promise<Array<{ id: string; name: string; slug: string; account_type: string; role: string }>> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/auth/my-organizations`, {
      method: 'GET',
      cache: 'no-store'
    });
    if (!res.ok) return [];
    return await res.json();
  } catch (err) {
    console.warn('Failed to fetch user organizations:', err);
    return [];
  }
}

export async function switchTenantInBackend(organizationId: string): Promise<{ success: boolean; user?: CurrentUser; error?: string }> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/auth/switch-tenant`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ organization_id: organizationId })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to switch organization' }));
      return { success: false, error: err.detail || 'Failed to switch organization' };
    }
    const data = await res.json();
    return {
      success: true,
      user: {
        id: data.user.id,
        email: data.user.email,
        fullName: data.user.full_name,
        organizationId: data.user.organization_id,
        organizationName: data.user.organization_name,
        role: data.user.role,
        accountType: data.user.account_type,
        permissions: data.user.permissions || [],
        isSuperAdmin: !!data.user.is_super_admin,
        platformRole: data.user.platform_role || null
      }
    };
  } catch (err: any) {
    return { success: false, error: err.message || 'Network error while switching organization' };
  }
}

export function mapBackendContractToFrontend(c: any): ContractItem {
  return {
    id: c.id,
    contractId: c.contract_id,
    title: c.title,
    contractType: c.contract_type,
    counterparty: c.counterparty,
    department: c.department || 'Legal',
    owner: c.owner || 'Aarav Mehta',
    value: c.value || 0,
    currency: c.currency || 'INR',
    startDate: c.start_date || '2026-01-01',
    expiryDate: c.expiry_date || '2027-01-01',
    renewalDate: c.renewal_date || '2026-11-01',
    autoRenew: c.auto_renew || false,
    renewalNoticeDays: c.renewal_notice_days,
    terminationNoticeDays: c.termination_notice_days,
    terminationDate: c.termination_date,
    terminationReason: c.termination_reason,
    status: c.status || 'UNDER_REVIEW',
    compositeRiskScore: c.composite_risk_score || 0,
    riskLevel: c.risk_level || 'LOW',
    version: c.version || 'v1.0',
    governingLaw: c.governing_law || 'Laws of India',
    tags: c.tags || [],
    lastModified: 'Synced with Live Database',
    clauses: (c.clauses || []).map((cl: any) => ({
      id: cl.id,
      clauseTitle: cl.clause_title,
      sectionNumber: cl.section_number,
      originalText: cl.original_text,
      plainLanguage: cl.plain_language,
      whyItMatters: cl.why_it_matters,
      potentialConcern: cl.potential_concern,
      suggestedAction: cl.suggested_action,
      riskLevel: cl.risk_level,
      category: cl.category
    })),
    risks: (c.risks || []).map((rk: any) => ({
      id: rk.id,
      severity: rk.severity,
      riskTitle: rk.risk_title,
      potentialImpact: rk.potential_impact,
      remedyRecommendation: rk.remedy_recommendation,
      status: rk.status || 'OPEN'
    })),
    redlines: (c.redlines || []).map((rd: any) => ({
      id: rd.id,
      clauseId: rd.clause_id || '',
      sectionTitle: rd.section_title,
      originalText: rd.original_text,
      suggestedText: rd.suggested_text,
      rationale: rd.rationale || '',
      status: rd.status || 'PENDING',
      author: rd.author || 'Analysis Engine',
      timestamp: rd.created_at ? rd.created_at.substring(0, 16).replace('T', ' ') : 'Recently',
      comment: rd.comment || undefined
    })),
    obligations: (c.obligations || []).map((o: any) => ({
      id: o.id,
      contractId: o.contract_id,
      contractTitle: c.title || 'Linked Contract',
      obligorParty: o.obligor_party,
      obligeeParty: o.obligee_party,
      title: o.title,
      description: o.description,
      dueDate: o.due_date || '2026-12-31',
      frequency: o.frequency || 'ONE_TIME',
      penaltyClause: o.penalty_clause || undefined,
      responsibleOwner: o.responsible_owner || 'Contract Manager',
      status: o.status || 'UPCOMING'
    })),
    approvalSteps: (c.approval_steps || []).map((st: any) => ({
      id: st.id,
      stepOrder: st.step_order,
      role: st.role,
      assignedUser: st.assigned_user,
      decision: st.decision,
      decidedAt: st.decided_at,
      comments: st.comments
    })),
    versions: (c.versions || []).map((v: any) => ({
      id: v.id,
      versionNumber: v.version_number,
      fileStoragePath: v.file_storage_path,
      fileMimeType: v.file_mime_type,
      fileByteSize: v.file_byte_size,
      sha256Checksum: v.sha256_checksum,
      changeSummary: v.change_summary,
      createdBy: v.created_by,
      createdAt: v.created_at ? v.created_at.substring(0, 16).replace('T', ' ') : 'Initial'
    }))
  };
}

// 3. Contracts List
export async function fetchContractsFromBackend(): Promise<ContractItem[]> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/contracts`, {
      method: 'GET',
      cache: 'no-store'
    });

    if (!res.ok) {
      console.warn('Backend returned non-200 status for contracts list.');
      return [];
    }

    const data = await res.json();
    if (!Array.isArray(data)) {
      return [];
    }

    return data.map(mapBackendContractToFrontend);
  } catch (err) {
    console.warn('Backend connection failed, returning empty contracts array.', err);
    return [];
  }
}


// 4. Contract Details
export async function fetchContractDetailsFromBackend(contractId: string): Promise<ContractItem | null> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/contracts/${contractId}`, {
      method: 'GET',
      cache: 'no-store'
    });
    if (!res.ok) return null;
    const c = await res.json();
    return mapBackendContractToFrontend(c);

  } catch (err) {
    console.warn(`Failed to fetch details for contract ${contractId}:`, err);
    return null;
  }
}

// 5. Contract Deletion
export async function deleteContractFromBackend(contractId: string): Promise<boolean> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/contracts/${contractId}`, {
      method: 'DELETE'
    });
    return res.ok;
  } catch (err) {
    console.error(`Failed to delete contract ${contractId}:`, err);
    return false;
  }
}

// 6. Obligations & Compliance Tracking
export async function fetchObligationsFromBackend(): Promise<ObligationItem[]> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/obligations`, {
      method: 'GET',
      cache: 'no-store'
    });
    if (!res.ok) return [];
    const data = await res.json();
    if (!Array.isArray(data)) return [];

    return data.map((o: any) => ({
      id: o.id,
      contractId: o.contract_id,
      contractTitle: o.contract_title || 'Linked Contract',
      obligorParty: o.obligor_party,
      obligeeParty: o.obligee_party,
      title: o.title,
      description: o.description,
      dueDate: o.due_date || '2026-12-31',
      frequency: o.frequency || 'ONE_TIME',
      penaltyClause: o.penalty_clause || undefined,
      responsibleOwner: o.responsible_owner || 'Contract Manager',
      status: o.status || 'UPCOMING',
      evidenceFiles: (o.evidence || []).map((e: any) => ({
        fileName: e.file_name,
        uploadedAt: e.created_at ? e.created_at.substring(0, 16).replace('T', ' ') : 'Recently',
        uploadedBy: e.uploaded_by || 'Current User',
        status: (e.status === 'VERIFIED' ? 'VERIFIED' : 'UNDER_REVIEW') as 'VERIFIED' | 'UNDER_REVIEW'
      }))
    }));
  } catch (err) {
    console.warn('Backend /obligations unavailable:', err);
    return [];
  }
}

export async function fetchContractObligationsFromBackend(contractId: string): Promise<ObligationItem[]> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/contracts/${contractId}/obligations`, {
      method: 'GET',
      cache: 'no-store'
    });
    if (!res.ok) return [];
    const data = await res.json();
    if (!Array.isArray(data)) return [];

    return data.map((o: any) => ({
      id: o.id,
      contractId: o.contract_id,
      contractTitle: 'Linked Contract',
      obligorParty: o.obligor_party,
      obligeeParty: o.obligee_party,
      title: o.title,
      description: o.description,
      dueDate: o.due_date || '2026-12-31',
      frequency: o.frequency || 'ONE_TIME',
      penaltyClause: o.penalty_clause || undefined,
      responsibleOwner: o.responsible_owner || 'Contract Manager',
      status: o.status || 'UPCOMING',
      evidenceFiles: (o.evidence || []).map((e: any) => ({
        fileName: e.file_name,
        uploadedAt: e.created_at ? e.created_at.substring(0, 16).replace('T', ' ') : 'Recently',
        uploadedBy: e.uploaded_by || 'Current User',
        status: (e.status === 'VERIFIED' ? 'VERIFIED' : 'UNDER_REVIEW') as 'VERIFIED' | 'UNDER_REVIEW'
      }))
    }));
  } catch (err) {
    console.warn(`Failed to fetch obligations for contract ${contractId}:`, err);
    return [];
  }
}

export async function updateObligationStatusInBackend(
  obligationId: string,
  status: ObligationStatus
): Promise<boolean> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/obligations/${obligationId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status })
    });
    return res.ok;
  } catch (err) {
    console.error(`Failed to update obligation ${obligationId} status:`, err);
    return false;
  }
}

export async function uploadObligationEvidenceToBackend(
  obligationId: string,
  file: File
): Promise<{ fileName: string; status: string } | null> {
  try {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetchWithAuth(`${API_BASE_URL}/obligations/${obligationId}/evidence`, {
      method: 'POST',
      body: formData
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Evidence upload failed: ${errText}`);
    }

    const data = await res.json();
    return {
      fileName: data.file_name,
      status: data.status
    };
  } catch (err) {
    console.error(`Failed to upload evidence for obligation ${obligationId}:`, err);
    return null;
  }
}

// 7. Contract Ingestion Pipeline
export async function uploadContractToBackend(formData: FormData): Promise<ContractItem | null> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/contracts/upload`, {
      method: 'POST',
      body: formData
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Upload failed: ${errText}`);
    }

    const c = await res.json();
    return mapBackendContractToFrontend(c);

  } catch (err) {
    console.error('Failed to upload contract to backend:', err);
    throw err;
  }
}

// 8. Contract Grounded Q&A
export async function askContractQABackend(
  contractId: string,
  question: string
): Promise<ContractQAResult | null> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/contracts/${contractId}/qa`, {
      method: 'POST',
      body: JSON.stringify({ question })
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => null);
      const detail = errData?.detail;
      const errorMsg = typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ')
          : `Contract Q&A service returned error status ${res.status}.`;
      return {
        answer: '',
        confidence: 'error',
        sources: [],
        error: errorMsg,
        status_code: res.status
      };
    }
    return await res.json();
  } catch (err: any) {
    return {
      answer: '',
      confidence: 'error',
      sources: [],
      error: err?.message || 'Network error connecting to contract Q&A service.',
      status_code: 0
    };
  }
}

// 8c. Lawyer Consultation Inquiries
export async function submitLawyerInquiry(data: {
  lawyer_id: string;
  lawyer_name: string;
  preferred_time_slot: string;
  client_notes?: string;
}): Promise<LawyerInquiryResult> {
  const res = await fetchWithAuth(`${API_BASE_URL}/lawyers/inquiries`, {
    method: 'POST',
    body: JSON.stringify(data)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to submit consultation inquiry.');
  }
  return await res.json();
}

// 8d. Public / Client Verified Lawyer Directory
export async function fetchLawyerDirectory(practiceArea?: string): Promise<AdvocateProfile[]> {
  const url = practiceArea && practiceArea !== 'ALL'
    ? `${API_BASE_URL}/lawyers/directory?practice_area=${encodeURIComponent(practiceArea)}`
    : `${API_BASE_URL}/lawyers/directory`;
  const res = await fetchWithAuth(url, {
    method: 'GET',
    cache: 'no-store'
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to fetch lawyer directory (Status ${res.status}).`);
  }
  const data = await res.json();
  return (data || []).map((p: any) => ({
    id: p.id,
    userId: p.user_id,
    fullName: p.full_name,
    professionalTitle: p.professional_title || 'Advocate',
    firmName: p.firm_name,
    organizationId: p.organization_id,
    barCouncilNumber: p.bar_council_number,
    stateBarCouncil: p.state_bar_council,
    admittedJurisdictions: p.admitted_jurisdictions,
    practiceAreas: p.practice_areas || [],
    qualifications: p.qualifications || [],
    languages: p.languages || [],
    experienceYears: p.experience_years,
    consultationFee: p.consultation_fee || 'INR 0',
    consultationDurationMinutes: p.consultation_duration_minutes || 30,
    bio: p.bio,
    isAvailableForInquiries: p.is_available_for_inquiries,
    verificationStatus: p.verification_status,
    verifiedAt: p.verified_at
  }));
}

// 8d2. Platform Admin Consultation Requests Queue
export async function fetchPlatformConsultationRequests(status?: string): Promise<AdminConsultationRequestItem[]> {
  const url = status && status !== 'ALL'
    ? `${API_BASE_URL}/platform/consultation-requests?status_filter=${encodeURIComponent(status)}`
    : `${API_BASE_URL}/platform/consultation-requests`;
  const res = await fetchWithAuth(url, {
    cache: 'no-store'
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to load consultation requests.');
  }
  return await res.json();
}

export async function decidePlatformConsultationRequest(
  matterId: string,
  decision: 'APPROVE' | 'REJECT',
  reason?: string
): Promise<AdminConsultationDecisionResponse> {
  const res = await fetchWithAuth(`${API_BASE_URL}/platform/consultation-requests/${matterId}/decision`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision, reason })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to ${decision.toLowerCase()} consultation request.`);
  }
  return await res.json();
}

// 8e. Platform Admin Advocate Credentials & Profile Management
export async function fetchPlatformAdvocates(status?: string): Promise<AdvocateProfile[]> {
  try {
    const url = status
      ? `${API_BASE_URL}/platform/advocates?status=${encodeURIComponent(status)}`
      : `${API_BASE_URL}/platform/advocates`;
    const res = await fetchWithAuth(url, {
      method: 'GET',
      cache: 'no-store'
    });
    if (!res.ok) return [];
    const data = await res.json();
    return (data || []).map((p: any) => ({
      id: p.id,
      userId: p.user_id,
      fullName: p.full_name,
      email: p.email,
      phoneNumber: p.phone_number,
      professionalTitle: p.professional_title || 'Advocate',
      firmName: p.firm_name,
      organizationId: p.organization_id,
      barCouncilNumber: p.bar_council_number,
      stateBarCouncil: p.state_bar_council,
      admittedJurisdictions: p.admitted_jurisdictions,
      practiceAreas: p.practice_areas || [],
      qualifications: p.qualifications || [],
      languages: p.languages || [],
      experienceYears: p.experience_years,
      consultationFee: p.consultation_fee,
      consultationDurationMinutes: p.consultation_duration_minutes || 30,
      bio: p.bio,
      internalNotes: p.internal_notes,
      credentialDocuments: p.credential_documents || [],
      isPublished: p.is_published,
      isAvailableForInquiries: p.is_available_for_inquiries,
      verificationStatus: p.verification_status,
      verifiedAt: p.verified_at,
      rejectionReason: p.rejection_reason,
      createdAt: p.created_at,
      updatedAt: p.updated_at
    }));
  } catch (err) {
    console.warn('Failed to fetch platform advocates:', err);
    return [];
  }
}

export async function createAdminLawyer(payload: {
  full_name: string;
  email: string;
  phone_number?: string;
  professional_title?: string;
  firm_name?: string;
  bar_council_number: string;
  state_bar_council: string;
  admitted_jurisdictions: string;
  practice_areas: string[];
  qualifications?: string[];
  languages?: string[];
  experience_years: number;
  consultation_fee?: string;
  consultation_duration_minutes?: number;
  bio?: string;
  internal_notes?: string;
  is_available_for_inquiries?: boolean;
}): Promise<{ success: boolean; profile?: AdvocateProfile; error?: string }> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/platform/lawyers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to create lawyer profile' }));
      return { success: false, error: err.detail || 'Creation failed' };
    }
    const p = await res.json();
    return {
      success: true,
      profile: {
        id: p.id,
        userId: p.user_id,
        fullName: p.full_name,
        email: p.email,
        phoneNumber: p.phone_number,
        professionalTitle: p.professional_title,
        firmName: p.firm_name,
        organizationId: p.organization_id,
        barCouncilNumber: p.bar_council_number,
        stateBarCouncil: p.state_bar_council,
        admittedJurisdictions: p.admitted_jurisdictions,
        practiceAreas: p.practice_areas || [],
        qualifications: p.qualifications || [],
        languages: p.languages || [],
        experienceYears: p.experience_years,
        consultationFee: p.consultation_fee,
        consultationDurationMinutes: p.consultation_duration_minutes,
        bio: p.bio,
        internalNotes: p.internal_notes,
        isPublished: p.is_published,
        isAvailableForInquiries: p.is_available_for_inquiries,
        verificationStatus: p.verification_status,
        verifiedAt: p.verified_at
      }
    };
  } catch (err: any) {
    return { success: false, error: err.message || 'Network error creating lawyer' };
  }
}

export async function updateAdminLawyer(
  profileId: string,
  payload: any
): Promise<{ success: boolean; profile?: AdvocateProfile; error?: string }> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/platform/lawyers/${profileId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to update lawyer profile' }));
      return { success: false, error: err.detail || 'Update failed' };
    }
    const p = await res.json();
    return { success: true, profile: p };
  } catch (err: any) {
    return { success: false, error: err.message || 'Network error updating lawyer' };
  }
}

export async function publishAdminLawyer(
  profileId: string,
  isPublished: boolean
): Promise<{ success: boolean; error?: string }> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/platform/lawyers/${profileId}/publish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_published: isPublished })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to change publication status' }));
      return { success: false, error: err.detail || 'Action failed' };
    }
    return { success: true };
  } catch (err: any) {
    return { success: false, error: err.message || 'Network error' };
  }
}

export async function setAdminLawyerAvailability(
  profileId: string,
  isAvailable: boolean
): Promise<{ success: boolean; error?: string }> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/platform/lawyers/${profileId}/availability`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_available_for_inquiries: isAvailable })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to update availability' }));
      return { success: false, error: err.detail || 'Action failed' };
    }
    return { success: true };
  } catch (err: any) {
    return { success: false, error: err.message || 'Network error' };
  }
}

export async function deleteAdminLawyer(
  profileId: string
): Promise<{ success: boolean; error?: string }> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/platform/lawyers/${profileId}`, {
      method: 'DELETE'
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to remove lawyer profile' }));
      return { success: false, error: err.detail || 'Delete failed' };
    }
    return { success: true };
  } catch (err: any) {
    return { success: false, error: err.message || 'Network error' };
  }
}

export async function verifyAdvocateProfile(
  profileId: string,
  decision: 'VERIFY' | 'REJECT',
  reason?: string
): Promise<{ success: boolean; profile?: AdvocateProfile; error?: string }> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/platform/lawyers/${profileId}/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision, reason: reason || null })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Verification failed' }));
      return { success: false, error: err.detail || 'Verification request failed' };
    }
    const p = await res.json();
    return {
      success: true,
      profile: {
        id: p.id,
        userId: p.user_id,
        fullName: p.full_name,
        professionalTitle: p.professional_title,
        firmName: p.firm_name,
        organizationId: p.organization_id,
        barCouncilNumber: p.bar_council_number,
        stateBarCouncil: p.state_bar_council,
        admittedJurisdictions: p.admitted_jurisdictions,
        practiceAreas: p.practice_areas || [],
        qualifications: p.qualifications || [],
        languages: p.languages || [],
        experienceYears: p.experience_years,
        consultationFee: p.consultation_fee,
        consultationDurationMinutes: p.consultation_duration_minutes,
        bio: p.bio,
        isPublished: p.is_published,
        isAvailableForInquiries: p.is_available_for_inquiries,
        verificationStatus: p.verification_status,
        verifiedAt: p.verified_at
      }
    };
  } catch (err: any) {
    return { success: false, error: err.message || 'Network error verifying advocate' };
  }
}

// 8b. General Contractly Educational Assistant
export async function askContractlyChatBackend(
  message: string,
  history?: Array<{ role: string; content: string }>
): Promise<GeneralChatResult> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/ai/chat`, {
      method: 'POST',
      body: JSON.stringify({ message, history })
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => null);
      const detail = errData?.detail;
      const errorMsg = typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ')
          : `AI service returned error status ${res.status}.`;
      return {
        reply: '',
        disclaimer: 'System Notice: Upstream AI service configuration or connectivity issue.',
        error: errorMsg,
        status_code: res.status
      };
    }
    return await res.json();
  } catch (err: any) {
    return {
      reply: '',
      disclaimer: 'System Notice: Upstream AI service configuration or connectivity issue.',
      error: err?.message || 'Network error connecting to Contractly AI service.',
      status_code: 0
    };
  }
}

// 9. Activity History / Audit Logs
export async function fetchActivityHistoryFromBackend(
  params?: ActivityFilterParams
): Promise<ActivityListResponse> {
  try {
    const q = new URLSearchParams();
    if (params?.scope) q.set('scope', params.scope);
    if (params?.action_type) q.set('action_type', params.action_type);
    if (params?.start_date) q.set('start_date', params.start_date);
    if (params?.end_date) q.set('end_date', params.end_date);
    if (params?.team_member) q.set('team_member', params.team_member);
    if (params?.page) q.set('page', String(params.page));
    if (params?.page_size) q.set('page_size', String(params.page_size));

    const queryStr = q.toString() ? `?${q.toString()}` : '';
    const res = await fetchWithAuth(`${API_BASE_URL}/activity${queryStr}`, {
      method: 'GET',
      cache: 'no-store'
    });

    if (!res.ok) {
      if (res.status === 403) {
        throw new Error('Access denied: You do not have permission to view organization activity history.');
      }
      throw new Error(`Failed to load activity history (status ${res.status}).`);
    }

    return await res.json();
  } catch (err: any) {
    console.warn('Backend /activity endpoint error:', err);
    throw err;
  }
}

export async function fetchActivityDetailFromBackend(id: string): Promise<ActivityItem | null> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/activity/${encodeURIComponent(id)}`, {
      method: 'GET',
      cache: 'no-store'
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.warn('Backend /activity/:id unavailable:', err);
    return null;
  }
}

export async function fetchAuditLogsFromBackend(): Promise<AuditLogEntry[]> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/organizations/audit-logs`, {
      method: 'GET',
      cache: 'no-store'
    });
    if (!res.ok) return [];
    const data = await res.json();
    if (!Array.isArray(data)) return [];
    return data.map((log: any) => ({
      id: log.id,
      timestamp: log.created_at ? log.created_at.replace('T', ' ').substring(0, 19) : 'Recently',
      user: log.user_email || 'Authenticated User',
      action: log.action,
      objectType: log.object_type,
      objectId: log.object_id,
      detail: log.detail,
      ipAddress: 'Internal System'
    }));
  } catch (err) {
    console.warn('Backend /organizations/audit-logs unavailable:', err);
    return [];
  }
}

// 10. Vendors
export async function fetchVendorsFromBackend(): Promise<VendorProfile[]> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/vendors`, {
      method: 'GET',
      cache: 'no-store'
    });
    if (!res.ok) return [];
    const data = await res.json();
    if (!Array.isArray(data)) return [];
    return data.map((v: any) => ({
      id: v.id,
      name: v.name,
      contactEmail: v.contact_email,
      contractCount: v.contract_count || 0,
      totalContractValue: v.total_contract_value || 0,
      riskRating: v.risk_rating || 'LOW',
      complianceRating: v.compliance_rating || 100,
      slaPerformance: v.sla_performance || 'Target Met',
      openObligations: v.open_obligations || 0,
      criticalIssues: v.critical_issues || 0,
      soc2Certified: Boolean(v.soc2_certified),
      gdprCompliant: Boolean(v.gdpr_compliant)
    }));
  } catch (err) {
    console.warn('Backend /vendors unavailable:', err);
    return [];
  }
}

export async function createVendorInBackend(payload: {
  name: string;
  contactEmail: string;
  contractCount?: number;
  totalContractValue?: number;
  riskRating?: string;
  complianceRating?: number;
  slaPerformance?: string;
  openObligations?: number;
  criticalIssues?: number;
  soc2Certified?: boolean;
  gdprCompliant?: boolean;
}): Promise<VendorProfile | null> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/vendors`, {
      method: 'POST',
      body: JSON.stringify({
        name: payload.name,
        contact_email: payload.contactEmail,
        contract_count: payload.contractCount || 0,
        total_contract_value: payload.totalContractValue || 0,
        risk_rating: payload.riskRating || 'LOW',
        compliance_rating: payload.complianceRating || 100,
        sla_performance: payload.slaPerformance || '100% Target Met',
        open_obligations: payload.openObligations || 0,
        critical_issues: payload.criticalIssues || 0,
        soc2_certified: payload.soc2Certified || false,
        gdpr_compliant: payload.gdprCompliant || false
      })
    });
    if (!res.ok) return null;
    const v = await res.json();
    return {
      id: v.id,
      name: v.name,
      contactEmail: v.contact_email,
      contractCount: v.contract_count || 0,
      totalContractValue: v.total_contract_value || 0,
      riskRating: v.risk_rating || 'LOW',
      complianceRating: v.compliance_rating || 100,
      slaPerformance: v.sla_performance || 'Target Met',
      openObligations: v.open_obligations || 0,
      criticalIssues: v.critical_issues || 0,
      soc2Certified: Boolean(v.soc2_certified),
      gdprCompliant: Boolean(v.gdpr_compliant)
    };
  } catch (err) {
    console.error('Failed to create vendor in backend:', err);
    return null;
  }
}

// 11. Playbook Rules
export async function fetchPlaybookRulesFromBackend(): Promise<PlaybookRule[]> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/playbook`, {
      method: 'GET',
      cache: 'no-store'
    });
    if (!res.ok) return [];
    const data = await res.json();
    if (!Array.isArray(data)) return [];
    return data.map((r: any) => ({
      id: r.id,
      category: r.category,
      preferredStandard: r.preferred_standard,
      fallbackAcceptable: r.fallback_acceptable,
      prohibitedTerms: r.prohibited_terms || [],
      negotiationGuidance: r.negotiation_guidance,
      lastUpdated: r.created_at ? r.created_at.substring(0, 10) : 'Active'
    }));
  } catch (err) {
    console.warn('Backend /playbook unavailable:', err);
    return [];
  }
}

export async function createPlaybookRuleInBackend(payload: {
  category: string;
  preferredStandard: string;
  fallbackAcceptable: string;
  prohibitedTerms: string[];
  negotiationGuidance: string;
}): Promise<PlaybookRule | null> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/playbook`, {
      method: 'POST',
      body: JSON.stringify({
        category: payload.category,
        preferred_standard: payload.preferredStandard,
        fallback_acceptable: payload.fallbackAcceptable,
        prohibited_terms: payload.prohibitedTerms,
        negotiation_guidance: payload.negotiationGuidance
      })
    });
    if (!res.ok) return null;
    const r = await res.json();
    return {
      id: r.id,
      category: r.category,
      preferredStandard: r.preferred_standard,
      fallbackAcceptable: r.fallback_acceptable,
      prohibitedTerms: r.prohibited_terms || [],
      negotiationGuidance: r.negotiation_guidance,
      lastUpdated: r.created_at ? r.created_at.substring(0, 10) : 'Active'
    };
  } catch (err) {
    console.error('Failed to create playbook rule in backend:', err);
    return null;
  }
}

// 12. Approval Decision
export async function submitApprovalDecisionInBackend(
  contractId: string,
  stepId: string,
  decision: 'APPROVED' | 'REJECTED',
  comments?: string
): Promise<boolean> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/contracts/${contractId}/approvals/${stepId}/decision`, {
      method: 'POST',
      body: JSON.stringify({ decision, comments })
    });
    return res.ok;
  } catch (err) {
    console.error(`Failed to submit approval decision on ${contractId} step ${stepId}:`, err);
    return false;
  }
}

// 13. Lifecycle State Transition
export async function transitionContractStatusInBackend(
  contractId: string,
  status: string,
  reason?: string
): Promise<ContractItem | null> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/contracts/${contractId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status, reason })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed transition' }));
      throw new Error(err.detail || 'Failed to update contract status');
    }
    const data = await res.json();
    return mapBackendContractToFrontend(data);
  } catch (err) {
    console.error('Failed to transition contract status:', err);
    throw err;
  }
}

// 14. Contract Termination
export async function terminateContractInBackend(
  contractId: string,
  reason: string,
  date?: string
): Promise<ContractItem | null> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/contracts/${contractId}/terminate`, {
      method: 'POST',
      body: JSON.stringify({ termination_reason: reason, termination_date: date })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed termination' }));
      throw new Error(err.detail || 'Failed to terminate contract');
    }
    const data = await res.json();
    return mapBackendContractToFrontend(data);
  } catch (err) {
    console.error('Failed to terminate contract:', err);
    throw err;
  }
}

// 15. Contract Renewal
export async function renewContractInBackend(
  contractId: string,
  newExpiryDate: string,
  renewalTermMonths: number = 12,
  notes?: string
): Promise<ContractItem | null> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/contracts/${contractId}/renew`, {
      method: 'POST',
      body: JSON.stringify({ new_expiry_date: newExpiryDate, renewal_term_months: renewalTermMonths, notes })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed renewal' }));
      throw new Error(err.detail || 'Failed to renew contract');
    }
    const data = await res.json();
    return mapBackendContractToFrontend(data);
  } catch (err) {
    console.error('Failed to renew contract:', err);
    throw err;
  }
}

// 16. Contract Versions
export async function fetchContractVersionsFromBackend(contractId: string): Promise<ContractVersionItem[]> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/contracts/${contractId}/versions`, {
      method: 'GET',
      cache: 'no-store'
    });
    if (!res.ok) return [];
    const data = await res.json();
    return (data || []).map((v: any) => ({
      id: v.id,
      versionNumber: v.version_number,
      fileStoragePath: v.file_storage_path,
      fileMimeType: v.file_mime_type,
      fileByteSize: v.file_byte_size,
      sha256Checksum: v.sha256_checksum,
      changeSummary: v.change_summary,
      createdBy: v.created_by,
      createdAt: v.created_at ? v.created_at.substring(0, 16).replace('T', ' ') : 'Recently'
    }));
  } catch (err) {
    console.warn(`Failed to fetch versions for contract ${contractId}:`, err);
    return [];
  }
}

export async function uploadContractVersionToBackend(
  contractId: string,
  file: File,
  changeSummary: string = 'Version revision'
): Promise<ContractVersionItem | null> {
  try {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('change_summary', changeSummary);

    const res = await fetchWithAuth(`${API_BASE_URL}/contracts/${contractId}/versions`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) return null;
    const v = await res.json();
    return {
      id: v.id,
      versionNumber: v.version_number,
      fileStoragePath: v.file_storage_path,
      fileMimeType: v.file_mime_type,
      fileByteSize: v.file_byte_size,
      sha256Checksum: v.sha256_checksum,
      changeSummary: v.change_summary,
      createdBy: v.created_by,
      createdAt: v.created_at ? v.created_at.substring(0, 16).replace('T', ' ') : 'Recently'
    };
  } catch (err) {
    console.error(`Failed to upload version for contract ${contractId}:`, err);
    return null;
  }
}

// 17. Redlines & Negotiation Markup
export async function fetchContractRedlinesFromBackend(contractId: string, versionId?: string): Promise<RedlineItem[]> {
  try {
    const url = versionId
      ? `${API_BASE_URL}/contracts/${contractId}/redlines?version_id=${encodeURIComponent(versionId)}`
      : `${API_BASE_URL}/contracts/${contractId}/redlines`;
    const res = await fetchWithAuth(url, {
      method: 'GET',
      cache: 'no-store'
    });
    if (!res.ok) return [];
    const data = await res.json();
    return (data || []).map((rd: any) => ({
      id: rd.id,
      clauseId: rd.clause_id || '',
      sectionTitle: rd.section_title,
      originalText: rd.original_text,
      suggestedText: rd.suggested_text,
      rationale: rd.rationale || '',
      status: rd.status || 'PENDING',
      author: rd.author || 'Analysis Engine',
      timestamp: rd.created_at ? rd.created_at.substring(0, 16).replace('T', ' ') : 'Recently',
      comment: rd.comment || undefined
    }));
  } catch (err) {
    console.warn(`Failed to fetch redlines for contract ${contractId}:`, err);
    return [];
  }
}

export async function generateContractRedlinesInBackend(
  contractId: string,
  versionId?: string
): Promise<RedlineItem[]> {
  const url = versionId
    ? `${API_BASE_URL}/contracts/${contractId}/generate-redlines?version_id=${encodeURIComponent(versionId)}`
    : `${API_BASE_URL}/contracts/${contractId}/generate-redlines`;

  const res = await fetchWithAuth(url, {
    method: 'POST'
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    throw new Error(errData?.detail || 'Failed to generate contract redlines.');
  }

  const data = await res.json();
  return (data || []).map((rd: any) => ({
    id: rd.id,
    clauseId: rd.clause_id || '',
    sectionTitle: rd.section_title,
    originalText: rd.original_text,
    suggestedText: rd.suggested_text,
    rationale: rd.rationale || '',
    status: rd.status || 'PENDING',
    author: rd.author || 'Contractly AI Reviewer',
    timestamp: rd.created_at ? rd.created_at.substring(0, 16).replace('T', ' ') : 'Recently',
    comment: rd.comment || undefined
  }));
}


export async function createContractRedlineInBackend(
  contractId: string,
  redline: { clauseId?: string; sectionTitle: string; originalText: string; suggestedText: string; rationale?: string }
): Promise<RedlineItem | null> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/contracts/${contractId}/redlines`, {
      method: 'POST',
      body: JSON.stringify({
        clause_id: redline.clauseId,
        section_title: redline.sectionTitle,
        original_text: redline.originalText,
        suggested_text: redline.suggestedText,
        rationale: redline.rationale
      })
    });
    if (!res.ok) return null;
    const rd = await res.json();
    return {
      id: rd.id,
      clauseId: rd.clause_id || '',
      sectionTitle: rd.section_title,
      originalText: rd.original_text,
      suggestedText: rd.suggested_text,
      rationale: rd.rationale || '',
      status: rd.status || 'PENDING',
      author: rd.author || 'User',
      timestamp: rd.created_at ? rd.created_at.substring(0, 16).replace('T', ' ') : 'Recently',
      comment: rd.comment || undefined
    };
  } catch (err) {
    console.error('Failed to create redline:', err);
    return null;
  }
}

export async function updateRedlineStatusInBackend(
  contractId: string,
  redlineId: string,
  status: 'ACCEPTED' | 'REJECTED' | 'MODIFIED'
): Promise<boolean> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/contracts/${contractId}/redlines/${redlineId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status })
    });
    return res.ok;
  } catch (err) {
    console.error(`Failed to update redline status:`, err);
    return false;
  }
}

export async function addRedlineCommentInBackend(
  contractId: string,
  redlineId: string,
  comment: string
): Promise<boolean> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/contracts/${contractId}/redlines/${redlineId}/comment`, {
      method: 'POST',
      body: JSON.stringify({ comment })
    });
    return res.ok;
  } catch (err) {
    console.error(`Failed to comment on redline:`, err);
    return false;
  }
}

// 18. Negotiation Analysis & Playbook
export async function fetchNegotiationAnalysisFromBackend(
  contractId: string
): Promise<NegotiationFindingItem[]> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/contracts/${contractId}/negotiation-analysis`, {
      method: 'GET',
      cache: 'no-store'
    });
    if (!res.ok) return [];
    const data = await res.json();
    return (data || []).map((f: any) => ({
      ruleId: f.rule_id,
      category: f.category,
      status: f.status,
      targetClause: f.target_clause,
      clauseTitle: f.clause_title,
      findingSummary: f.finding_summary,
      guidance: f.guidance,
      suggestedAction: f.suggested_action
    }));
  } catch (err) {
    console.warn(`Failed to fetch negotiation analysis for ${contractId}:`, err);
    return [];
  }
}

// 19. Lifecycle Summary & Deterministic Health
export async function fetchContractLifecycleSummaryFromBackend(
  contractId: string
): Promise<ContractLifecycleSummary | null> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/contracts/${contractId}/lifecycle-summary`, {
      method: 'GET',
      cache: 'no-store'
    });
    if (!res.ok) return null;
    const data = await res.json();
    return {
      currentStatus: data.current_status,
      allowedTransitions: data.allowed_transitions || [],
      healthStatus: data.health_status,
      healthReason: data.health_reason,
      renewalStatus: data.renewal_status,
      daysUntilExpiry: data.days_until_expiry,
      inNoticeWindow: data.in_notice_window,
      openRisksCount: data.open_risks_count,
      overdueObligationsCount: data.overdue_obligations_count,
      pendingApprovalStepsCount: data.pending_approval_steps_count
    };
  } catch (err) {
    console.warn(`Failed to fetch lifecycle summary for ${contractId}:`, err);
    return null;
  }
}

// 20. Contract Intelligence
export async function fetchContractIntelligenceFromBackend(
  contractId: string,
  versionId?: string
): Promise<ContractIntelligenceData | null> {
  try {
    const url = versionId
      ? `${API_BASE_URL}/contracts/${contractId}/intelligence?version_id=${versionId}`
      : `${API_BASE_URL}/contracts/${contractId}/intelligence`;
    const res = await fetchWithAuth(url, { method: 'GET', cache: 'no-store' });
    if (!res.ok) return null;
    const d = await res.json();
    return {
      contract_id: d.contract_id,
      version_id: d.version_id,
      parser_status: d.parser_status,
      page_count: d.page_count,
      char_count: d.char_count,
      word_count: d.word_count,
      processing_started_at: d.processing_started_at,
      processing_completed_at: d.processing_completed_at,
      processing_error: d.processing_error,
      parties: d.parties || [],
      candidate_dates: d.candidate_dates || [],
      renewal_info: d.renewal_info || {},
      clauses: (d.clauses || []).map((cl: any) => ({
        id: cl.id,
        clauseTitle: cl.clause_title,
        sectionNumber: cl.section_number,
        originalText: cl.original_text,
        plainLanguage: cl.plain_language,
        whyItMatters: cl.why_it_matters,
        potentialConcern: cl.potential_concern,
        suggestedAction: cl.suggested_action,
        riskLevel: cl.risk_level,
        category: cl.category
      })),
      risks: d.risks || [],
      obligation_candidates: d.obligation_candidates || [],
      risk_score_breakdown: d.risk_score_breakdown
    };
  } catch (err) {
    console.warn(`Failed to fetch intelligence for ${contractId}:`, err);
    return null;
  }
}

export async function fetchContractMetadataFromBackend(
  contractId: string
): Promise<ContractMetadata | null> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/contracts/${contractId}/metadata`, { method: 'GET', cache: 'no-store' });
    if (!res.ok) return null;
    const d = await res.json();
    return {
      contract_id: d.contract_id,
      title: d.title,
      counterparty: d.counterparty,
      status: d.status,
      current_version: d.current_version,
      versions: (d.versions || []).map((v: any) => ({
        id: v.id,
        versionNumber: v.version_number,
        fileStoragePath: v.file_storage_path,
        fileMimeType: v.file_mime_type,
        fileByteSize: v.file_byte_size,
        sha256Checksum: v.sha256_checksum,
        changeSummary: v.change_summary,
        createdBy: v.created_by,
        createdAt: v.created_at ? v.created_at.substring(0, 16).replace('T', ' ') : 'Initial'
      })),
      total_clauses: d.total_clauses,
      total_risks: d.total_risks,
      total_obligations: d.total_obligations
    };
  } catch (err) {
    console.warn(`Failed to fetch metadata for ${contractId}:`, err);
    return null;
  }
}

export async function reprocessContractInBackend(
  contractId: string,
  versionId?: string
): Promise<boolean> {
  try {
    const url = versionId
      ? `${API_BASE_URL}/contracts/${contractId}/reprocess?version_id=${versionId}`
      : `${API_BASE_URL}/contracts/${contractId}/reprocess`;
    const res = await fetchWithAuth(url, { method: 'POST' });
    return res.ok;
  } catch (err) {
    console.error(`Failed to reprocess contract intelligence:`, err);
    return false;
  }
}

// ─────────────────────────────────────────────────────────────
// Phase I: Contract Calendar Actions
// ─────────────────────────────────────────────────────────────

export async function fetchCalendarEvents(params?: {
  startDate?: string;
  endDate?: string;
  contractId?: string;
  category?: string;
  priority?: string;
}): Promise<CalendarEventItem[]> {
  try {
    const query = new URLSearchParams();
    if (params?.startDate) query.set('start_date', params.startDate);
    if (params?.endDate) query.set('end_date', params.endDate);
    if (params?.contractId) query.set('contract_id', params.contractId);
    if (params?.category) query.set('category', params.category);
    if (params?.priority) query.set('priority', params.priority);

    const qs = query.toString() ? `?${query.toString()}` : '';
    const res = await fetchWithAuth(`${API_BASE_URL}/calendar/events${qs}`);
    if (!res.ok) return [];
    return await res.json();
  } catch (err) {
    console.error('Failed to fetch calendar events:', err);
    return [];
  }
}

export async function createCalendarEvent(data: {
  contract_id?: string | null;
  obligation_id?: string | null;
  title: string;
  description?: string;
  event_type: string;
  event_date: string;
  priority?: string;
  is_important?: boolean;
}): Promise<CalendarEventItem | null> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/calendar/events`, {
      method: 'POST',
      body: JSON.stringify(data)
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error('Failed to create calendar event:', err);
    return null;
  }
}

export async function updateCalendarEvent(
  eventId: string,
  data: Partial<CalendarEventItem>
): Promise<CalendarEventItem | null> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/calendar/events/${eventId}`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error(`Failed to update calendar event ${eventId}:`, err);
    return null;
  }
}

export async function deleteCalendarEvent(eventId: string): Promise<boolean> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/calendar/events/${eventId}`, {
      method: 'DELETE'
    });
    return res.ok;
  } catch (err) {
    console.error(`Failed to delete calendar event ${eventId}:`, err);
    return false;
  }
}

// ─────────────────────────────────────────────────────────────
// Phase I: Contract Notes Actions
// ─────────────────────────────────────────────────────────────

export async function fetchContractNotes(contractId: string): Promise<ContractNoteItem[]> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/contracts/${contractId}/notes`);
    if (!res.ok) return [];
    return await res.json();
  } catch (err) {
    console.error(`Failed to fetch notes for ${contractId}:`, err);
    return [];
  }
}

export async function createContractNote(
  contractId: string,
  data: {
    title?: string;
    content: string;
    reminder_date?: string;
    is_important?: boolean;
    calendar_event_id?: string;
    obligation_id?: string;
  }
): Promise<ContractNoteItem | null> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/contracts/${contractId}/notes`, {
      method: 'POST',
      body: JSON.stringify(data)
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error(`Failed to create note on ${contractId}:`, err);
    return null;
  }
}

export async function updateContractNote(
  contractId: string,
  noteId: string,
  data: Partial<ContractNoteItem>
): Promise<ContractNoteItem | null> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/contracts/${contractId}/notes/${noteId}`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error(`Failed to update note ${noteId}:`, err);
    return null;
  }
}

export async function deleteContractNote(contractId: string, noteId: string): Promise<boolean> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/contracts/${contractId}/notes/${noteId}`, {
      method: 'DELETE'
    });
    return res.ok;
  } catch (err) {
    console.error(`Failed to delete note ${noteId}:`, err);
    return false;
  }
}

// ─────────────────────────────────────────────────────────────
// Phase I: Things You Need to Do (Responsibilities)
// ─────────────────────────────────────────────────────────────

export async function fetchThingsToDo(params?: {
  priority?: string;
  contractId?: string;
  status?: string;
}): Promise<{
  items: ThingToDoItem[];
  total_count: number;
  critical_count: number;
  important_count: number;
  distinct_contracts_count: number;
}> {
  try {
    const query = new URLSearchParams();
    if (params?.priority) query.set('priority', params.priority);
    if (params?.contractId) query.set('contract_id', params.contractId);
    if (params?.status) query.set('status', params.status);

    const qs = query.toString() ? `?${query.toString()}` : '';
    const res = await fetchWithAuth(`${API_BASE_URL}/tasks/things-to-do${qs}`);
    if (!res.ok) return { items: [], total_count: 0, critical_count: 0, important_count: 0, distinct_contracts_count: 0 };
    return await res.json();
  } catch (err) {
    console.error('Failed to fetch things to do:', err);
    return { items: [], total_count: 0, critical_count: 0, important_count: 0, distinct_contracts_count: 0 };
  }
}


// ─────────────────────────────────────────────────────────────
// Phase I: Notifications & Preferences Actions
// ─────────────────────────────────────────────────────────────

export async function fetchNotifications(params?: {
  isRead?: boolean;
  priority?: string;
  limit?: number;
  offset?: number;
}): Promise<{
  items: NotificationItem[];
  unread_count: number;
  total_count: number;
}> {
  try {
    const query = new URLSearchParams();
    if (params?.isRead !== undefined) query.set('is_read', String(params.isRead));
    if (params?.priority) query.set('priority', params.priority);
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));

    const qs = query.toString() ? `?${query.toString()}` : '';
    const res = await fetchWithAuth(`${API_BASE_URL}/notifications${qs}`);
    if (!res.ok) return { items: [], unread_count: 0, total_count: 0 };
    return await res.json();
  } catch (err) {
    console.error('Failed to fetch notifications:', err);
    return { items: [], unread_count: 0, total_count: 0 };
  }
}

export interface UnreadCountsData {
  unread_count: number;
  unread_messages_count: number;
}

export async function fetchUnreadNotificationCounts(): Promise<UnreadCountsData | null> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/notifications/unread-count`);
    if (!res.ok) return null;
    const data = await res.json();
    return {
      unread_count: typeof data.unread_count === 'number' ? data.unread_count : 0,
      unread_messages_count: typeof data.unread_messages_count === 'number' ? data.unread_messages_count : 0
    };
  } catch (err) {
    console.error('Failed to fetch unread notification counts:', err);
    return null;
  }
}

export async function fetchUnreadNotificationCount(): Promise<number> {
  const counts = await fetchUnreadNotificationCounts();
  return counts ? counts.unread_count : 0;
}

export async function markNotificationAsRead(notificationId: string): Promise<boolean> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/notifications/${notificationId}/read`, {
      method: 'PATCH'
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function markAllNotificationsAsRead(): Promise<boolean> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/notifications/mark-all-read`, {
      method: 'POST'
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function fetchNotificationPreferences(): Promise<NotificationPreferences | null> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/notifications/preferences`);
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error('Failed to fetch notification preferences:', err);
    return null;
  }
}

export async function updateNotificationPreferences(
  data: Partial<NotificationPreferences>
): Promise<NotificationPreferences> {
  const res = await fetchWithAuth(`${API_BASE_URL}/notifications/preferences`, {
    method: 'PUT',
    body: JSON.stringify(data)
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    const detail = errData?.detail;
    let msg = 'Failed to update preferences.';
    if (typeof detail === 'string') {
      msg = detail;
    } else if (Array.isArray(detail) && detail.length > 0) {
      msg = detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ');
    }
    throw new Error(msg);
  }
  return await res.json();
}

export async function sendTestNotificationEmail(
  recipientEmail?: string
): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/notifications/test-email`, {
      method: 'POST',
      body: JSON.stringify({ recipient_email: recipientEmail || undefined })
    });
    return await res.json();
  } catch (err: any) {
    return { success: false, message: err.message || 'Failed to trigger test email.' };
  }
}

export async function triggerWorkerEvaluation(): Promise<boolean> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/notifications/evaluate-and-dispatch`, {
      method: 'POST'
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function exportRedlinesDocx(contractId: string): Promise<{ blob: Blob; filename: string }> {
  const res = await fetchWithAuth(`${API_BASE_URL}/contracts/${contractId}/export/docx`);
  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    const detail = errData?.detail;
    let msg = 'Failed to export proposed revisions.';
    if (typeof detail === 'string') {
      msg = detail;
    } else if (Array.isArray(detail) && detail.length > 0) {
      msg = detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ');
    }
    throw new Error(msg);
  }

  const contentDisposition = res.headers.get('content-disposition');
  let filename = `contract_${contractId}_revisions.docx`;
  if (contentDisposition) {
    const match = contentDisposition.match(/filename="?([^"]+)"?/);
    if (match && match[1]) {
      filename = match[1];
    }
  }

  const blob = await res.blob();
  return { blob, filename };
}

export async function downloadContractVersionFile(
  contractId: string,
  versionId: string
): Promise<{ blob: Blob; filename: string }> {
  const res = await fetchWithAuth(`${API_BASE_URL}/contracts/${contractId}/versions/${versionId}/download`);
  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    const detail = errData?.detail;
    let msg = 'Failed to download contract document.';
    if (typeof detail === 'string') {
      msg = detail;
    } else if (Array.isArray(detail) && detail.length > 0) {
      msg = detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ');
    }
    throw new Error(msg);
  }

  const contentDisposition = res.headers.get('content-disposition');
  let filename = `contract_${contractId}_document.pdf`;
  if (contentDisposition) {
    const match = contentDisposition.match(/filename="?([^"]+)"?/);
    if (match && match[1]) {
      filename = match[1];
    }
  }

  const blob = await res.blob();
  return { blob, filename };
}

// =====================================================================
// Data Management & Demo Operations API Client Functions
// =====================================================================

export async function getWorkspaceDataSummary(): Promise<WorkspaceSummaryResponse> {
  const res = await fetchWithAuth(`${API_BASE_URL}/organizations/data-management/summary`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to fetch workspace data summary.');
  }
  return await res.json();
}

export async function exportWorkspaceData(): Promise<any> {
  const res = await fetchWithAuth(`${API_BASE_URL}/organizations/data-management/export`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to export workspace data.');
  }
  return await res.json();
}

export async function clearWorkspaceData(confirmation: string): Promise<{
  status: string;
  message: string;
  contracts_deleted: number;
  storage_files_deleted: number;
  cleared_at: string;
}> {
  const res = await fetchWithAuth(`${API_BASE_URL}/organizations/data-management/clear-workspace`, {
    method: 'POST',
    body: JSON.stringify({ confirmation })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to clear workspace data.');
  }
  return await res.json();
}

export async function previewDemoReset(): Promise<DemoResetPreviewResponse> {
  const res = await fetchWithAuth(`${API_BASE_URL}/platform/data-management/demo-workspace/preview`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to preview demo workspace status.');
  }
  return await res.json();
}

export async function resetDemoWorkspace(
  confirmation: string,
  reseed: boolean = true
): Promise<DemoResetResultResponse> {
  const res = await fetchWithAuth(`${API_BASE_URL}/platform/data-management/demo-workspace/reset`, {
    method: 'POST',
    body: JSON.stringify({ confirmation, reseed })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to execute demo workspace reset.');
  }
  return await res.json();
}

export async function getCustomerHandoverChecklist(): Promise<CustomerHandoverChecklistResponse> {
  const res = await fetchWithAuth(`${API_BASE_URL}/platform/data-management/customer-handover-checklist`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to fetch customer handover checklist.');
  }
  return await res.json();
}

// ============================================================================
// Client & Lawyer Messaging APIs
// ============================================================================

export async function fetchConversations(): Promise<ConversationItem[]> {
  const res = await fetchWithAuth(`${API_BASE_URL}/matters/conversations`, {
    cache: 'no-store'
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to load conversations.');
  }
  return await res.json();
}

export async function fetchMatterMessages(matterId: string): Promise<{
  messages: MatterMessageItem[];
  hasAdminReview: boolean;
  adminReviewDate?: string | null;
  adminReviewReason?: string | null;
}> {
  const res = await fetchWithAuth(`${API_BASE_URL}/matters/${matterId}/messages`, {
    cache: 'no-store'
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to load matter messages.');
  }
  const messages = await res.json();
  const hasAdminReview = res.headers.get('x-admin-reviewed') === 'true';
  const adminReviewDate = res.headers.get('x-admin-review-date');
  const adminReviewReason = res.headers.get('x-admin-review-reason');

  return {
    messages,
    hasAdminReview,
    adminReviewDate,
    adminReviewReason
  };
}

export async function sendMatterMessage(
  matterId: string,
  messageText: string,
  isInternalNote: boolean = false
): Promise<MatterMessageItem> {
  const res = await fetchWithAuth(`${API_BASE_URL}/matters/${matterId}/messages`, {
    method: 'POST',
    body: JSON.stringify({
      message_text: messageText,
      is_internal_note: isInternalNote
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to send message.');
  }
  return await res.json();
}

export async function markMatterNotificationsAsRead(matterId: string): Promise<boolean> {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/matters/${matterId}/read`, {
      method: 'PATCH'
    });
    return res.ok;
  } catch (err) {
    console.error(`Failed to mark notifications read for matter ${matterId}:`, err);
    return false;
  }
}

// ============================================================================
// Platform Admin Conversation Oversight APIs
// ============================================================================

export async function fetchAdminConversations(params?: {
  status?: string;
  review_status?: string;
  search?: string;
}): Promise<AdminConversationItem[]> {
  const query = new URLSearchParams();
  if (params?.status && params.status !== 'ALL') query.set('status_filter', params.status);
  if (params?.review_status && params.review_status !== 'ALL') query.set('review_status', params.review_status);
  if (params?.search) query.set('search', params.search);

  const url = `${API_BASE_URL}/platform/conversations${query.toString() ? '?' + query.toString() : ''}`;
  const res = await fetchWithAuth(url, {
    cache: 'no-store'
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to load conversations for platform oversight.');
  }
  return await res.json();
}

export async function reviewAdminConversation(
  matterId: string,
  reviewReason: string,
  notes?: string
): Promise<AdminConversationReviewResponse> {
  const res = await fetchWithAuth(`${API_BASE_URL}/platform/conversations/${matterId}/review`, {
    method: 'POST',
    body: JSON.stringify({
      review_reason: reviewReason,
      notes: notes || undefined
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to authorize conversation review.');
  }
  return await res.json();
}

export async function addAdminConversationNote(
  matterId: string,
  noteText: string
): Promise<{ success: boolean; note_id: string; matter_id: string; admin_email: string; created_at: string }> {
  const res = await fetchWithAuth(`${API_BASE_URL}/platform/conversations/${matterId}/notes`, {
    method: 'POST',
    body: JSON.stringify({
      note_text: noteText
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to record administrative note.');
  }
  return await res.json();
}


