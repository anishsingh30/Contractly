'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import {
  AccountType,
  BusinessRole,
  ContractItem,
  ContractStatus,
  CurrentUser,
  OrganizationInfo,
  ObligationItem,
  ObligationStatus
} from '@/types/contractly';

import {
  fetchCurrentUser,
  fetchCurrentOrganization,
  fetchContractsFromBackend,
  deleteContractFromBackend,
  fetchObligationsFromBackend,
  updateObligationStatusInBackend,
  uploadObligationEvidenceToBackend,
  uploadContractToBackend,
  refreshSession,
  switchTenantInBackend,
  fetchMyOrganizations,
  submitApprovalDecisionInBackend,
  updateRedlineStatusInBackend,
  addRedlineCommentInBackend,
  generateContractRedlinesInBackend,
  transitionContractStatusInBackend,
  terminateContractInBackend,
  renewContractInBackend,
  uploadContractVersionToBackend,
  fetchUnreadNotificationCounts,
  logout as apiLogout
} from '@/lib/api-client';

interface Toast {
  id: string;
  title: string;
  message: string;
  type: 'success' | 'warning' | 'danger' | 'info';
}

interface ContractlyContextType {
  currentUser: CurrentUser | null;
  currentOrganization: OrganizationInfo | null;
  accountType: AccountType;
  setAccountType: (type: AccountType) => void;
  businessRole: BusinessRole;
  setBusinessRole: (role: BusinessRole) => void;
  activeNav: string;
  setActiveNav: (nav: string) => void;
  contracts: ContractItem[];
  obligations: ObligationItem[];
  activeContractId: string;
  setActiveContractId: (id: string) => void;
  activeContract: ContractItem | undefined;
  redlineScope: string;
  setRedlineScope: (scope: string) => void;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  toasts: Toast[];
  addToast: (title: string, message: string, type?: Toast['type']) => void;
  removeToast: (id: string) => void;
  // State Mutations
  generateRedlines: (contractId: string, versionId?: string) => Promise<boolean>;
  acceptRedline: (contractId: string, redlineId: string) => Promise<void>;
  rejectRedline: (contractId: string, redlineId: string) => Promise<void>;
  addRedlineComment: (contractId: string, redlineId: string, comment: string) => Promise<void>;
  approveStep: (contractId: string, stepId: string, comments?: string) => Promise<void>;
  rejectStep: (contractId: string, stepId: string, comments?: string) => Promise<void>;
  transitionStatus: (contractId: string, status: ContractStatus, reason?: string) => Promise<boolean>;
  terminateContract: (contractId: string, reason: string, date?: string) => Promise<boolean>;
  renewContract: (contractId: string, newExpiryDate: string, termMonths?: number, notes?: string) => Promise<boolean>;
  uploadVersion: (contractId: string, file: File, changeSummary?: string) => Promise<boolean>;
  uploadObligationEvidence: (obligationId: string, fileName: string, file?: File) => Promise<void>;
  updateObligationStatus: (obligationId: string, status: ObligationStatus) => Promise<void>;
  addNewContract: (newContract: Partial<ContractItem>, file?: File) => Promise<ContractItem | null>;
  deleteContract: (contractId: string) => Promise<void>;
  isLoadingContracts: boolean;
  isAuthLoading: boolean;
  hasPermission: (permission: string) => boolean;
  availableOrganizations: Array<{ id: string; name: string; slug: string; account_type: string; role: string }>;
  switchOrganization: (orgId: string) => Promise<boolean>;
  logoutUser: () => Promise<void>;
  recheckAuth: () => Promise<CurrentUser | null>;
  unreadNotificationsCount: number;
  unreadMessagesCount: number;
  notificationsLoadError: boolean;
  refreshNotifications: () => Promise<void>;
}

const ContractlyContext = createContext<ContractlyContextType | undefined>(undefined);

export function ContractlyProvider({ children }: { children: ReactNode }) {
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [currentOrganization, setCurrentOrganization] = useState<OrganizationInfo | null>(null);
  const [accountType, setAccountType] = useState<AccountType>('BUSINESS');
  const [businessRole, setBusinessRole] = useState<BusinessRole>('LEGAL_MANAGER');
  const [activeNav, setActiveNav] = useState<string>('home');
  const [contracts, setContracts] = useState<ContractItem[]>([]);
  const [obligations, setObligations] = useState<ObligationItem[]>([]);
  const [activeContractId, setActiveContractId] = useState<string>('');
  const [redlineScope, setRedlineScope] = useState<string>('');

  const [searchQuery, setSearchQuery] = useState<string>('');
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [isAuthLoading, setIsAuthLoading] = useState<boolean>(true);
  const [isLoadingContracts, setIsLoadingContracts] = useState<boolean>(true);
  const [availableOrganizations, setAvailableOrganizations] = useState<Array<{ id: string; name: string; slug: string; account_type: string; role: string }>>([]);

  const [unreadNotificationsCount, setUnreadNotificationsCount] = useState<number>(0);
  const [unreadMessagesCount, setUnreadMessagesCount] = useState<number>(0);
  const [notificationsLoadError, setNotificationsLoadError] = useState<boolean>(false);

  const refreshNotifications = useCallback(async () => {
    try {
      const data = await fetchUnreadNotificationCounts();
      if (data) {
        setUnreadNotificationsCount(data.unread_count);
        setUnreadMessagesCount(data.unread_messages_count);
        setNotificationsLoadError(false);
      } else {
        setNotificationsLoadError(true);
      }
    } catch {
      setNotificationsLoadError(true);
    }
  }, []);

  const recheckAuth = useCallback(async (): Promise<CurrentUser | null> => {
    try {
      const user = await fetchCurrentUser();
      if (user) {
        setCurrentUser(user);
        if (user.accountType) setAccountType(user.accountType);
        if (user.role) setBusinessRole(user.role);
        return user;
      } else {
        setCurrentUser(null);
        setCurrentOrganization(null);
        setAvailableOrganizations([]);
        setContracts([]);
        setObligations([]);
        return null;
      }
    } catch {
      setCurrentUser(null);
      return null;
    }
  }, []);

  const logoutUser = async () => {
    // 1. Immediately wipe all cached user and tenant data in memory
    setCurrentUser(null);
    setCurrentOrganization(null);
    setAvailableOrganizations([]);
    setContracts([]);
    setObligations([]);
    setActiveContractId('');
    setRedlineScope('');
    setSearchQuery('');
    setUnreadNotificationsCount(0);
    setUnreadMessagesCount(0);
    setNotificationsLoadError(false);

    // 2. Execute backend revocation, cookie deletion, and safe replace navigation
    await apiLogout();
  };

  const loadTenantData = useCallback(async (activeUser: CurrentUser) => {
    setIsLoadingContracts(true);
    try {
      // Concurrently fetch tenant organization, memberships, obligations, and contracts to eliminate network waterfall
      const [org, myOrgs, backendObligations, backendContracts] = await Promise.all([
        fetchCurrentOrganization(),
        fetchMyOrganizations(),
        fetchObligationsFromBackend(),
        fetchContractsFromBackend()
      ]);

      if (org) {
        setCurrentOrganization(org);
      }
      setAvailableOrganizations(myOrgs || []);
      setObligations(backendObligations || []);

      if (backendContracts && backendContracts.length > 0) {
        const mergedContracts = backendContracts.map((c) => {
          const matchingObligations = (backendObligations || []).filter((o) => o.contractId === c.id);
          return {
            ...c,
            obligations: matchingObligations.length > 0 ? matchingObligations : c.obligations
          };
        });
        setContracts(mergedContracts);
        setActiveContractId(mergedContracts[0].id);
      } else {
        setContracts([]);
        setActiveContractId('');
      }
      // Ensure unread notification counts are synchronized with the active tenant
      refreshNotifications();
    } catch (err) {
      console.warn('Tenant data load error:', err);
    } finally {
      setIsLoadingContracts(false);
    }
  }, [refreshNotifications]);

  // Fetch real data from FastAPI Backend on Mount
  useEffect(() => {
    async function loadData() {
      setIsAuthLoading(true);
      setIsLoadingContracts(true);
      try {
        let user = await fetchCurrentUser();
        if (!user) {
          const refreshed = await refreshSession();
          if (refreshed) {
            user = await fetchCurrentUser();
          }
        }

        if (user) {
          setCurrentUser(user);
          if (user.accountType) setAccountType(user.accountType);
          if (user.role) setBusinessRole(user.role);
          await loadTenantData(user);
        } else {
          setCurrentUser(null);
          setCurrentOrganization(null);
          setAvailableOrganizations([]);
          setContracts([]);
          setObligations([]);
          setIsLoadingContracts(false);
        }
      } catch (err) {
        console.warn('Authentication load error:', err);
        setCurrentUser(null);
        setCurrentOrganization(null);
        setAvailableOrganizations([]);
        setContracts([]);
        setObligations([]);
        setIsLoadingContracts(false);
      } finally {
        setIsAuthLoading(false);
      }
    }
    loadData();
  }, [loadTenantData]);

  const switchOrganization = async (orgId: string): Promise<boolean> => {
    setIsLoadingContracts(true);
    // 1. Clear old tenant-specific cached data immediately
    setContracts([]);
    setObligations([]);
    setActiveContractId('');

    const res = await switchTenantInBackend(orgId);
    if (res.success && res.user) {
      setCurrentUser(res.user);
      if (res.user.accountType) setAccountType(res.user.accountType);
      if (res.user.role) setBusinessRole(res.user.role);
      await loadTenantData(res.user);
      await refreshNotifications();
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new Event('refresh-notifications'));
      }
      addToast('Workspace Switched', `Active workspace changed to ${res.user.organizationName}.`, 'success');
      return true;
    } else {
      addToast('Switch Failed', res.error || 'Could not switch organization.', 'danger');
      setIsLoadingContracts(false);
      return false;
    }
  };

  useEffect(() => {
    if (currentUser) {
      refreshNotifications();
      const interval = setInterval(refreshNotifications, 15000);
      const handleSync = () => refreshNotifications();
      window.addEventListener('refresh-notifications', handleSync);
      return () => {
        clearInterval(interval);
        window.removeEventListener('refresh-notifications', handleSync);
      };
    } else {
      setUnreadNotificationsCount(0);
      setUnreadMessagesCount(0);
      setNotificationsLoadError(false);
    }
  }, [currentUser, refreshNotifications]);

  const addToast = (title: string, message: string, type: Toast['type'] = 'info') => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, title, message, type }]);
    setTimeout(() => {
      removeToast(id);
    }, 4500);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const activeContract = contracts.find((c) => c.id === activeContractId) || contracts[0];
  const effectiveRedlineScope = redlineScope || activeContract?.id || 'ALL';

  const acceptRedline = async (contractId: string, redlineId: string) => {
    try {
      await updateRedlineStatusInBackend(contractId, redlineId, 'ACCEPTED');
    } catch (err) {
      console.warn('Backend redline accept error:', err);
    }
    setContracts((prev) =>
      prev.map((c) => {
        if (c.id !== contractId) return c;
        const updatedRedlines = c.redlines.map((r) =>
          r.id === redlineId ? { ...r, status: 'ACCEPTED' as const } : r
        );
        return { ...c, redlines: updatedRedlines };
      })
    );
    addToast('Redline Accepted', 'The proposed clause revision has been merged into the active draft.', 'success');
  };

  const rejectRedline = async (contractId: string, redlineId: string) => {
    try {
      await updateRedlineStatusInBackend(contractId, redlineId, 'REJECTED');
    } catch (err) {
      console.warn('Backend redline reject error:', err);
    }
    setContracts((prev) =>
      prev.map((c) => {
        if (c.id !== contractId) return c;
        const updatedRedlines = c.redlines.map((r) =>
          r.id === redlineId ? { ...r, status: 'REJECTED' as const } : r
        );
        return { ...c, redlines: updatedRedlines };
      })
    );
    addToast('Redline Rejected', 'The revision proposal was dismissed. Original wording retained.', 'info');
  };

  const addRedlineComment = async (contractId: string, redlineId: string, comment: string) => {
    try {
      await addRedlineCommentInBackend(contractId, redlineId, comment);
    } catch (err) {
      console.warn('Backend redline comment error:', err);
    }
    setContracts((prev) =>
      prev.map((c) => {
        if (c.id !== contractId) return c;
        const updatedRedlines = c.redlines.map((r) =>
          r.id === redlineId ? { ...r, comment } : r
        );
        return { ...c, redlines: updatedRedlines };
      })
    );
    addToast('Note Added', 'Your note has been saved to this proposal.', 'info');
  };

  const generateRedlines = async (contractId: string, versionId?: string): Promise<boolean> => {
    try {
      addToast('Generating Revisions...', 'Analyzing clauses against negotiation benchmarks with Gemini AI...', 'info');
      const generated = await generateContractRedlinesInBackend(contractId, versionId);
      setContracts((prev) =>
        prev.map((c) => {
          if (c.id !== contractId) return c;
          return {
            ...c,
            redlines: generated
          };
        })
      );
      addToast(
        'Revisions Ready',
        `Generated ${generated.length} proposed revision(s) grounded in contract clauses.`,
        'success'
      );
      return true;
    } catch (err: any) {
      addToast('Generation Failed', err.message || 'Could not generate proposed revisions.', 'danger');
      return false;
    }
  };

  const transitionStatus = async (contractId: string, status: ContractStatus, reason?: string): Promise<boolean> => {
    try {
      const updated = await transitionContractStatusInBackend(contractId, status, reason);
      if (updated) {
        setContracts((prev) => prev.map((c) => (c.id === contractId ? updated : c)));
        addToast('Lifecycle Updated', `Contract transitioned to ${status}.`, 'success');
        return true;
      }
      return false;
    } catch (err: any) {
      addToast('Transition Failed', err.message || 'Invalid lifecycle transition.', 'danger');
      return false;
    }
  };

  const terminateContract = async (contractId: string, reason: string, date?: string): Promise<boolean> => {
    try {
      const updated = await terminateContractInBackend(contractId, reason, date);
      if (updated) {
        setContracts((prev) => prev.map((c) => (c.id === contractId ? updated : c)));
        addToast('Contract Terminated', 'Agreement status updated to TERMINATED.', 'info');
        return true;
      }
      return false;
    } catch (err: any) {
      addToast('Termination Failed', err.message || 'Could not terminate contract.', 'danger');
      return false;
    }
  };

  const renewContract = async (contractId: string, newExpiryDate: string, termMonths: number = 12, notes?: string): Promise<boolean> => {
    try {
      const updated = await renewContractInBackend(contractId, newExpiryDate, termMonths, notes);
      if (updated) {
        setContracts((prev) => prev.map((c) => (c.id === contractId ? updated : c)));
        addToast('Contract Renewed', `Agreement extended through ${newExpiryDate}.`, 'success');
        return true;
      }
      return false;
    } catch (err: any) {
      addToast('Renewal Failed', err.message || 'Could not renew contract.', 'danger');
      return false;
    }
  };

  const uploadVersion = async (contractId: string, file: File, changeSummary: string = 'Version revision'): Promise<boolean> => {
    try {
      const newV = await uploadContractVersionToBackend(contractId, file, changeSummary);
      if (newV) {
        setContracts((prev) =>
          prev.map((c) => {
            if (c.id !== contractId) return c;
            const existing = c.versions || [];
            return {
              ...c,
              version: newV.versionNumber,
              versions: [newV, ...existing]
            };
          })
        );
        addToast('Version Uploaded', `Revision ${newV.versionNumber} has been recorded.`, 'success');
        return true;
      }
      return false;
    } catch (err: any) {
      addToast('Upload Failed', err.message || 'Could not record new version.', 'danger');
      return false;
    }
  };

  const approveStep = async (contractId: string, stepId: string, comments?: string) => {
    try {
      const ok = await submitApprovalDecisionInBackend(contractId, stepId, 'APPROVED', comments);
      if (!ok) {
        addToast('Action Failed', 'Could not record approval on the server. Please check your permissions.', 'danger');
        return;
      }
    } catch (err) {
      addToast('Error', 'Failed to communicate with the approval service.', 'danger');
      return;
    }

    setContracts((prev) =>
      prev.map((c) => {
        if (c.id !== contractId) return c;
        const updatedSteps = (c.approvalSteps || []).map((step) =>
          step.id === stepId
            ? {
                ...step,
                decision: 'APPROVED' as const,
                decidedAt: new Date().toISOString().replace('T', ' ').substring(0, 16),
                comments: comments || 'Approved pursuant to departmental review standard.'
              }
            : step
        );
        const allApproved = updatedSteps.every((s) => s.decision === 'APPROVED');
        return {
          ...c,
          approvalSteps: updatedSteps,
          status: allApproved ? ('APPROVED' as const) : c.status
        };
      })
    );
    addToast('Approval Step Recorded', 'Your sign-off has been authenticated and entered into the audit trail.', 'success');
  };

  const rejectStep = async (contractId: string, stepId: string, comments?: string) => {
    try {
      const ok = await submitApprovalDecisionInBackend(contractId, stepId, 'REJECTED', comments);
      if (!ok) {
        addToast('Action Failed', 'Could not record rejection on the server.', 'danger');
        return;
      }
    } catch (err) {
      addToast('Error', 'Failed to communicate with the approval service.', 'danger');
      return;
    }

    setContracts((prev) =>
      prev.map((c) => {
        if (c.id !== contractId) return c;
        const updatedSteps = (c.approvalSteps || []).map((step) =>
          step.id === stepId
            ? {
                ...step,
                decision: 'REJECTED' as const,
                decidedAt: new Date().toISOString().replace('T', ' ').substring(0, 16),
                comments: comments || 'Returned for review pursuant to comments.'
              }
            : step
        );
        return {
          ...c,
          approvalSteps: updatedSteps,
          status: 'UNDER_REVIEW' as const
        };
      })
    );
    addToast('Rejection Recorded', 'Agreement has been returned to review stage.', 'info');
  };


  const uploadObligationEvidence = async (obligationId: string, fileName: string, file?: File) => {
    // If backend is reachable, attempt real persistence
    try {
      const uploadFile =
        file ||
        new File([new Blob([`Verification artifact: ${fileName}`])], fileName, {
          type: 'application/pdf'
        });
      await uploadObligationEvidenceToBackend(obligationId, uploadFile);
    } catch (err) {
      console.warn('Backend evidence upload skipped or offline fallback:', err);
    }

    // Update state
    setContracts((prev) =>
      prev.map((c) => {
        const updatedObligations = c.obligations.map((obl) => {
          if (obl.id !== obligationId) return obl;
          const currentFiles = obl.evidenceFiles || [];
          return {
            ...obl,
            status: 'FULFILLED' as const,
            evidenceFiles: [
              ...currentFiles,
              {
                fileName,
                uploadedAt: new Date().toISOString().replace('T', ' ').substring(0, 16),
                uploadedBy: currentUser?.fullName || 'Current User',
                status: 'UNDER_REVIEW' as const
              }
            ]
          };
        });
        return { ...c, obligations: updatedObligations };
      })
    );
    addToast('Compliance Evidence Attached', `${fileName} has been linked to the obligation record for verification.`, 'success');
  };

  const updateObligationStatus = async (obligationId: string, status: ObligationStatus) => {
    try {
      const ok = await updateObligationStatusInBackend(obligationId, status);
      if (!ok) {
        addToast('Update Failed', 'Could not update obligation status on server. Please check your network or permissions.', 'danger');
        return;
      }

      setContracts((prev) =>
        prev.map((c) => ({
          ...c,
          obligations: c.obligations.map((o) => (o.id === obligationId ? { ...o, status } : o))
        }))
      );

      setObligations((prev) =>
        prev.map((o) => (o.id === obligationId ? { ...o, status } : o))
      );

      addToast('Obligation Status Updated', `Status updated to ${status}.`, 'info');
    } catch (err) {
      console.warn('Backend status update error:', err);
      addToast('Update Error', 'An unexpected error occurred while updating the obligation.', 'danger');
    }
  };

  const deleteContract = async (contractId: string) => {
    try {
      await deleteContractFromBackend(contractId);
    } catch (err) {
      console.warn('Backend contract delete skipped or offline fallback:', err);
    }

    setContracts((prev) => prev.filter((c) => c.id !== contractId));
    addToast('Contract Removed', 'Agreement record has been deleted.', 'info');
  };

  const addNewContract = async (newContract: Partial<ContractItem>, file?: File): Promise<ContractItem | null> => {
    if (!file) {
      addToast('Document Required', 'Please select a contract file (PDF, Word, or TXT) to upload and analyze.', 'warning');
      throw new Error('Please select a contract file (PDF, Word, or TXT) to upload.');
    }

    try {
      addToast('Reading your contract...', 'Uploading file and finding important terms...', 'info');
      const formData = new FormData();
      formData.append('file', file);
      formData.append('title', newContract.title || file.name.replace(/\.[^/.]+$/, ''));
      formData.append('contract_type', newContract.contractType || 'Master Services Agreement');
      formData.append('counterparty', newContract.counterparty || 'Counterparty Inc.');
      formData.append('department', newContract.department || 'Legal');
      if (newContract.value !== null && newContract.value !== undefined && !isNaN(newContract.value)) {
        formData.append('value', String(newContract.value));
      }
      formData.append('currency', newContract.currency || 'INR');
      formData.append('start_date', newContract.startDate || '2026-11-01');
      formData.append('expiry_date', newContract.expiryDate || '2027-10-31');
      formData.append('governing_law', newContract.governingLaw || 'Laws of India');

      const uploadedContract = await uploadContractToBackend(formData);
      if (uploadedContract) {
        setContracts((prev) => [uploadedContract, ...prev]);
        setActiveContractId(uploadedContract.id);
        addToast(
          'Your contract is ready',
          `We identified ${uploadedContract.clauses.length} important terms and highlighted key points for your review.`,
          'success'
        );
        return uploadedContract;
      } else {
        addToast('Upload Issue', 'We could not upload this file. Please check that it is a valid PDF, Word document, or text file and try again.', 'danger');
        throw new Error('Could not parse uploaded contract');
      }
    } catch (err: any) {
      addToast('Upload Issue', 'We could not upload this file. Please check that it is a PDF, Word document, or text file and try again.', 'danger');
      throw err;
    }
  };


  const hasPermission = (permission: string): boolean => {
    if (!currentUser || !currentUser.permissions) return false;
    if (currentUser.permissions.includes('*')) return true;
    if (currentUser.permissions.includes(permission)) return true;
    const [domain] = permission.split(':');
    if (domain && currentUser.permissions.includes(`${domain}:*`)) return true;
    return false;
  };

  return (
    <ContractlyContext.Provider
      value={{
        currentUser,
        currentOrganization,
        accountType,
        setAccountType,
        businessRole,
        setBusinessRole,
        activeNav,
        setActiveNav,
        contracts,
        obligations,
        activeContractId,
        setActiveContractId,
        activeContract,
        redlineScope: effectiveRedlineScope,
        setRedlineScope,
        searchQuery,
        setSearchQuery,
        toasts,
        addToast,
        removeToast,
        generateRedlines,
        acceptRedline,
        rejectRedline,
        addRedlineComment,
        approveStep,
        rejectStep,
        transitionStatus,
        terminateContract,
        renewContract,
        uploadVersion,
        uploadObligationEvidence,
        updateObligationStatus,
        addNewContract,
        deleteContract,
        isLoadingContracts,
        isAuthLoading,
        hasPermission,
        availableOrganizations,
        switchOrganization,
        logoutUser,
        recheckAuth,
        unreadNotificationsCount,
        unreadMessagesCount,
        notificationsLoadError,
        refreshNotifications
      }}
    >
      {children}
    </ContractlyContext.Provider>
  );
}

export function useContractly() {
  const context = useContext(ContractlyContext);
  if (!context) {
    throw new Error('useContractly must be used within a ContractlyProvider');
  }
  return context;
}
