'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  AdminConversationItem,
  AdminConversationReviewResponse,
  AdminConsultationRequestItem,
} from '@/types/contractly';
import {
  fetchAdminConversations,
  reviewAdminConversation,
  addAdminConversationNote,
  fetchPlatformConsultationRequests,
  decidePlatformConsultationRequest,
} from '@/lib/api-client';

interface ConversationOversightProps {
  onRefresh?: () => void;
}

export function ConversationOversight({ onRefresh }: ConversationOversightProps) {
  const [activeTab, setActiveTab] = useState<'REQUESTS' | 'CONVERSATIONS'>('REQUESTS');

  // Consultation Requests Queue State
  const [requests, setRequests] = useState<AdminConsultationRequestItem[]>([]);
  const [loadingRequests, setLoadingRequests] = useState(true);
  const [requestsError, setRequestsError] = useState<string | null>(null);
  const [requestsFilter, setRequestsFilter] = useState('ALL');
  const [decisionModal, setDecisionModal] = useState<{
    request: AdminConsultationRequestItem;
    action: 'APPROVE' | 'REJECT';
    reason: string;
  } | null>(null);
  const [decisionLoading, setDecisionLoading] = useState(false);
  const [decisionFeedback, setDecisionFeedback] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Conversations Oversight State
  const [conversations, setConversations] = useState<AdminConversationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [reviewStatusFilter, setReviewStatusFilter] = useState('ALL');
  const [searchTerm, setSearchTerm] = useState('');

  // Selected Conversation for Review Modal
  const [selectedMatter, setSelectedMatter] = useState<AdminConversationItem | null>(null);
  const [isReviewModalOpen, setIsReviewModalOpen] = useState(false);
  const [reviewReason, setReviewReason] = useState('COMPLIANCE_REVIEW');
  const [customReason, setCustomReason] = useState('');
  const [reviewNotes, setReviewNotes] = useState('');
  const [authorizingReview, setAuthorizingReview] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);

  // Active Review Data
  const [activeReviewData, setActiveReviewData] = useState<AdminConversationReviewResponse | null>(null);

  // Add Note within active review
  const [newAdminNote, setNewAdminNote] = useState('');
  const [submittingNote, setSubmittingNote] = useState(false);
  const [noteSuccess, setNoteSuccess] = useState<string | null>(null);

  const loadRequests = useCallback(async () => {
    setLoadingRequests(true);
    setRequestsError(null);
    try {
      const data = await fetchPlatformConsultationRequests(requestsFilter);
      setRequests(data || []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve consultation requests.';
      setRequestsError(msg);
    } finally {
      setLoadingRequests(false);
    }
  }, [requestsFilter]);

  const loadConversations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAdminConversations({
        status: statusFilter,
        review_status: reviewStatusFilter,
        search: searchTerm.trim() || undefined
      });
      setConversations(data || []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve oversight conversations.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, reviewStatusFilter, searchTerm]);

  useEffect(() => {
    loadRequests();
  }, [loadRequests]);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const handleExecuteDecision = async () => {
    if (!decisionModal) return;
    setDecisionLoading(true);
    setDecisionFeedback(null);
    try {
      const { request, action, reason } = decisionModal;
      const res = await decidePlatformConsultationRequest(request.matter_id, action, reason);
      setDecisionFeedback({ message: res.message, type: 'success' });
      setDecisionModal(null);
      loadRequests();
      loadConversations();
      if (onRefresh) onRefresh();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to process decision.';
      setDecisionFeedback({ message: msg, type: 'error' });
    } finally {
      setDecisionLoading(false);
    }
  };

  const handleOpenReviewGate = (matter: AdminConversationItem) => {
    setSelectedMatter(matter);
    setActiveReviewData(null);
    setReviewReason('COMPLIANCE_REVIEW');
    setCustomReason('');
    setReviewNotes('');
    setReviewError(null);
    setNewAdminNote('');
    setNoteSuccess(null);
    setIsReviewModalOpen(true);
  };

  const handleExecuteOversightReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedMatter) return;

    const finalReason = reviewReason === 'OTHER' ? customReason.trim() : reviewReason;
    if (!finalReason) {
      setReviewError('You must specify a documented legitimate operational or compliance purpose.');
      return;
    }

    setAuthorizingReview(true);
    setReviewError(null);
    try {
      const res = await reviewAdminConversation(selectedMatter.matter_id, finalReason, reviewNotes);
      setActiveReviewData(res);
      // Refresh conversation list to update review status
      loadConversations();
      if (onRefresh) onRefresh();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Authorization failed.';
      setReviewError(msg);
    } finally {
      setAuthorizingReview(false);
    }
  };

  const handleAddInternalNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeReviewData) return;
    const note = newAdminNote.trim();
    if (!note) return;

    setSubmittingNote(true);
    setNoteSuccess(null);
    try {
      const res = await addAdminConversationNote(activeReviewData.matter_id, note);
      setNoteSuccess('Internal administrative note recorded in AuditLog.');
      setNewAdminNote('');
      // Append to local note list
      setActiveReviewData((prev) => {
        if (!prev) return null;
        return {
          ...prev,
          admin_notes: [
            {
              id: res.note_id,
              action: 'CONVERSATION_OVERSIGHT_NOTE',
              admin_email: res.admin_email,
              detail: `Admin Note: ${note}`,
              timestamp: res.created_at
            },
            ...prev.admin_notes
          ]
        };
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to save admin note.';
      setReviewError(msg);
    } finally {
      setSubmittingNote(false);
    }
  };

  return (
    <section className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-[#DED6C8] pb-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-serif font-bold text-[#242321] uppercase tracking-wider">
              Platform Consultation Queue &amp; Conversation Oversight
            </h2>
            <span className="font-mono text-[10px] font-bold px-2 py-0.5 bg-[#E8EFE0] text-[#3F4634] border border-[#C5D5B8] rounded-[2px]">
              Audited &amp; Permission-Controlled
            </span>
          </div>
          <p className="text-xs text-[#6F6A61] mt-0.5 leading-relaxed">
            Review incoming client consultation requests, approve or decline advocate engagements, and inspect conversations solely for compliance and platform safety.
          </p>
        </div>

        <button
          onClick={() => {
            loadRequests();
            loadConversations();
          }}
          className="self-start sm:self-auto px-3 py-1.5 bg-[#FCFAF5] border border-[#DED6C8] text-xs font-medium text-[#242321] rounded-[2px] hover:bg-[#F7F3EA] transition-colors"
        >
          ↻ Refresh All
        </button>
      </div>

      {/* Decision Feedback Banner */}
      {decisionFeedback && (
        <div
          className={`p-3 rounded-[2px] text-xs border ${
            decisionFeedback.type === 'success'
              ? 'bg-[#EDF2EC] border-[#C6D8C6] text-[#2E5230]'
              : 'bg-[#FDF2F2] border-[#F2C6C6] text-[#A33B3B]'
          }`}
        >
          {decisionFeedback.message}
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-[#DED6C8] pb-2 text-xs">
        <button
          onClick={() => setActiveTab('REQUESTS')}
          className={`px-3 py-1.5 font-semibold rounded-[2px] flex items-center gap-2 transition-colors ${
            activeTab === 'REQUESTS'
              ? 'bg-[#3F4634] text-[#FCFAF5]'
              : 'bg-[#FCFAF5] border border-[#DED6C8] text-[#242321] hover:bg-[#F7F3EA]'
          }`}
        >
          <span>Consultation Intake Approval Queue</span>
          {requests.filter((r) => r.status === 'SUBMITTED').length > 0 && (
            <span className="px-1.5 py-0.2 bg-[#FDF8EE] text-[#7A4D1A] border border-[#E8D9B5] text-[10px] rounded-full font-mono font-bold">
              {requests.filter((r) => r.status === 'SUBMITTED').length} Pending
            </span>
          )}
        </button>
        <button
          onClick={() => setActiveTab('CONVERSATIONS')}
          className={`px-3 py-1.5 font-semibold rounded-[2px] flex items-center gap-2 transition-colors ${
            activeTab === 'CONVERSATIONS'
              ? 'bg-[#3F4634] text-[#FCFAF5]'
              : 'bg-[#FCFAF5] border border-[#DED6C8] text-[#242321] hover:bg-[#F7F3EA]'
          }`}
        >
          <span>Conversation Oversight &amp; Audit</span>
          <span className="font-mono text-[10px] text-[#6F6A61]">
            ({conversations.length})
          </span>
        </button>
      </div>

      {/* ───────────────────────────────────────────────────────────── */}
      {/* TAB 1: CONSULTATION INTAKE QUEUE */}
      {/* ───────────────────────────────────────────────────────────── */}
      {activeTab === 'REQUESTS' && (
        <div className="space-y-3">
          {/* Requests Filter Bar */}
          <div className="bg-[#FCFAF5] border border-[#DED6C8] p-3 rounded-[2px] flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <span className="text-[#6F6A61]">Intake Filter:</span>
              <select
                value={requestsFilter}
                onChange={(e) => setRequestsFilter(e.target.value)}
                className="bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] px-2 py-1 text-xs text-[#242321] focus:outline-none focus:border-[#3F4634]"
              >
                <option value="ALL">All Consultation Requests</option>
                <option value="SUBMITTED">Pending Approval Only</option>
                <option value="ACCEPTED">Approved Only</option>
                <option value="DECLINED">Rejected Only</option>
              </select>
            </div>
            <span className="text-[11px] text-[#6F6A61] font-mono">
              Total Requests: {requests.length}
            </span>
          </div>

          {/* Requests Table */}
          <div className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] overflow-hidden">
            {loadingRequests ? (
              <div className="p-8 text-center text-xs text-[#6F6A61] italic">
                Loading consultation intake queue...
              </div>
            ) : requestsError ? (
              <div className="p-6 text-center space-y-2">
                <p className="text-xs text-[#A33B3B]">{requestsError}</p>
                <button
                  onClick={loadRequests}
                  className="px-3 py-1 bg-[#F7F3EA] border border-[#DED6C8] text-xs rounded-[2px]"
                >
                  Retry
                </button>
              </div>
            ) : requests.length === 0 ? (
              <div className="p-8 text-center text-xs text-[#6F6A61] italic">
                No consultation requests currently in this view.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-[#DED6C8] bg-[#F7F3EA] text-[11px] font-mono text-[#6F6A61]">
                      <th className="py-2.5 px-4 font-normal">Reference &amp; Subject</th>
                      <th className="py-2.5 px-4 font-normal">Client Org / Email</th>
                      <th className="py-2.5 px-4 font-normal">Selected Advocate</th>
                      <th className="py-2.5 px-4 font-normal">Conflict Check Party</th>
                      <th className="py-2.5 px-4 font-normal">Preferred Slot &amp; Message</th>
                      <th className="py-2.5 px-4 font-normal">Status</th>
                      <th className="py-2.5 px-4 font-normal text-right">Approval Decision</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#DED6C8]">
                    {requests.map((r) => (
                      <tr key={r.matter_id} className="hover:bg-[#F7F3EA]/50">
                        <td className="py-3 px-4">
                          <div className="font-mono text-[11px] font-bold text-[#3F4634]">
                            {r.matter_code}
                          </div>
                          <div className="font-serif font-bold text-xs text-[#242321] line-clamp-1">
                            {r.title}
                          </div>
                          <div className="text-[10px] text-[#8C877D] font-mono mt-0.5">
                            {new Date(r.created_at).toLocaleString()}
                          </div>
                        </td>

                        <td className="py-3 px-4">
                          <div className="font-medium text-[#242321]">{r.client_organization_name}</div>
                          <div className="text-[10px] text-[#6F6A61] font-mono">
                            {r.client_user_email || r.client_user_name || 'Client'}
                          </div>
                        </td>

                        <td className="py-3 px-4">
                          <div className="font-medium text-[#242321]">
                            {r.lawyer_user_name || 'Advocate'}
                          </div>
                          <div className="text-[10px] text-[#6F6A61]">{r.lawyer_organization_name}</div>
                        </td>

                        <td className="py-3 px-4">
                          <div className="font-medium text-[#242321]">{r.counterparty_name}</div>
                          <div className="text-[10px] text-[#6F6A61]">Conflict check target</div>
                        </td>

                        <td className="py-3 px-4 max-w-xs">
                          {r.preferred_time_slot && (
                            <div className="text-[10px] font-mono text-[#3F4634] font-semibold mb-0.5">
                              Slot: {r.preferred_time_slot}
                            </div>
                          )}
                          <div className="text-[11px] text-[#6F6A61] line-clamp-2" title={r.initial_message || r.client_notes || ''}>
                            {r.initial_message || r.client_notes || 'No message provided'}
                          </div>
                        </td>

                        <td className="py-3 px-4">
                          <span
                            className={`font-mono text-[10px] px-2 py-0.5 border rounded-[2px] block w-fit ${
                              r.status === 'ACCEPTED' || r.status === 'MATTER_ACTIVE'
                                ? 'bg-[#EDF2EC] text-[#2E5230] border-[#C6D8C6]'
                                : r.status === 'DECLINED'
                                ? 'bg-[#FDF2F2] text-[#A33B3B] border-[#F2C6C6]'
                                : 'bg-[#FDF8EE] text-[#7A4D1A] border-[#E8D9B5]'
                            }`}
                          >
                            {r.status === 'SUBMITTED' ? 'Pending Approval' : r.status === 'ACCEPTED' ? 'Approved' : r.status}
                          </span>
                        </td>

                        <td className="py-3 px-4 text-right">
                          {r.status === 'SUBMITTED' ? (
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                onClick={() =>
                                  setDecisionModal({
                                    request: r,
                                    action: 'APPROVE',
                                    reason: 'Intake and conflict check verified by platform administration.',
                                  })
                                }
                                className="px-2.5 py-1 bg-[#3F4634] text-[#FCFAF5] text-[10px] font-semibold rounded-[2px] hover:bg-[#2C3124] transition-colors"
                              >
                                Approve
                              </button>
                              <button
                                onClick={() =>
                                  setDecisionModal({
                                    request: r,
                                    action: 'REJECT',
                                    reason: '',
                                  })
                                }
                                className="px-2.5 py-1 bg-[#FCFAF5] border border-[#DED6C8] text-[#8B3F3F] text-[10px] font-semibold rounded-[2px] hover:bg-[#FDF2F2] transition-colors"
                              >
                                Reject
                              </button>
                            </div>
                          ) : r.status === 'ACCEPTED' || r.status === 'MATTER_ACTIVE' ? (
                            <span className="text-[10px] font-mono text-[#2E5230]">
                              ✓ Conversation Active
                            </span>
                          ) : (
                            <span className="text-[10px] font-mono text-[#8B3F3F]">
                              ✗ Request Declined
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ───────────────────────────────────────────────────────────── */}
      {/* TAB 2: ACTIVE & HISTORICAL CONVERSATIONS OVERSIGHT */}
      {/* ───────────────────────────────────────────────────────────── */}
      {activeTab === 'CONVERSATIONS' && (
        <div className="space-y-3">
          {/* Filters Bar */}
          <div className="bg-[#FCFAF5] border border-[#DED6C8] p-3 rounded-[2px] flex flex-col sm:flex-row sm:items-center gap-3 text-xs">
            <div className="flex-1">
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search by matter code, party, client email, or lawyer..."
                className="w-full px-3 py-1.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] text-[#242321] placeholder-[#6F6A61] focus:outline-none focus:border-[#3F4634]"
              />
            </div>

        <div className="flex items-center gap-2">
          <span className="text-[#6F6A61] shrink-0">Matter Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] px-2 py-1 text-xs text-[#242321] focus:outline-none focus:border-[#3F4634]"
          >
            <option value="ALL">All States</option>
            <option value="MATTER_ACTIVE">Active Matters</option>
            <option value="SUBMITTED">Submitted</option>
            <option value="ACCEPTED">Accepted</option>
            <option value="RESOLVED">Resolved</option>
            <option value="CLOSED">Closed</option>
            <option value="DECLINED">Declined</option>
            <option value="CANCELLED">Cancelled</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[#6F6A61] shrink-0">Review Status:</span>
          <select
            value={reviewStatusFilter}
            onChange={(e) => setReviewStatusFilter(e.target.value)}
            className="bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] px-2 py-1 text-xs text-[#242321] focus:outline-none focus:border-[#3F4634]"
          >
            <option value="ALL">All Reviews</option>
            <option value="UNREVIEWED">Unreviewed</option>
            <option value="REVIEWED">Previously Reviewed</option>
          </select>
        </div>
      </div>

      {/* Conversations Table */}
      <div className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-xs text-[#6F6A61] italic">
            Querying platform legal conversations...
          </div>
        ) : error ? (
          <div className="p-6 text-center space-y-2">
            <p className="text-xs text-[#A33B3B]">{error}</p>
            <button
              onClick={loadConversations}
              className="px-3 py-1 bg-[#F7F3EA] border border-[#DED6C8] text-xs rounded-[2px]"
            >
              Retry
            </button>
          </div>
        ) : conversations.length === 0 ? (
          <div className="p-8 text-center text-xs text-[#6F6A61] italic">
            No legal matter conversations match your criteria.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-[#DED6C8] bg-[#F7F3EA] text-[11px] font-mono text-[#6F6A61]">
                  <th className="py-2.5 px-4 font-normal">Matter Reference</th>
                  <th className="py-2.5 px-4 font-normal">Client Org / User</th>
                  <th className="py-2.5 px-4 font-normal">Assigned Counsel</th>
                  <th className="py-2.5 px-4 font-normal">Status</th>
                  <th className="py-2.5 px-4 font-normal">Messages</th>
                  <th className="py-2.5 px-4 font-normal">Oversight Status</th>
                  <th className="py-2.5 px-4 font-normal text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#DED6C8]">
                {conversations.map((c) => (
                  <tr key={c.matter_id} className="hover:bg-[#F7F3EA]/50">
                    <td className="py-3 px-4">
                      <div className="font-mono text-[11px] font-bold text-[#3F4634]">
                        {c.matter_code}
                      </div>
                      <div className="font-serif font-bold text-xs text-[#242321] line-clamp-1">
                        {c.title}
                      </div>
                    </td>

                    <td className="py-3 px-4">
                      <div className="font-medium text-[#242321]">{c.client_organization_name}</div>
                      <div className="text-[10px] text-[#6F6A61] font-mono">
                        {c.client_user_email || c.client_user_name || 'N/A'}
                      </div>
                    </td>

                    <td className="py-3 px-4">
                      <div className="font-medium text-[#242321]">
                        {c.lawyer_user_name || 'Assigned Counsel'}
                      </div>
                      <div className="text-[10px] text-[#6F6A61]">{c.lawyer_organization_name}</div>
                    </td>

                    <td className="py-3 px-4">
                      <span
                        className={`text-[9px] font-mono px-1.5 py-0.5 border rounded-[2px] ${
                          c.status === 'MATTER_ACTIVE'
                            ? 'bg-[#E8EFE0] text-[#3F4634] border-[#C5D5B8]'
                            : c.status === 'RESOLVED' || c.status === 'CLOSED'
                            ? 'bg-[#F0EEEA] text-[#6F6A61] border-[#DED6C8]'
                            : 'bg-[#FDF8EE] text-[#7A4D1A] border-[#E8D9B5]'
                        }`}
                      >
                        {c.status.replace(/_/g, ' ')}
                      </span>
                    </td>

                    <td className="py-3 px-4">
                      <div className="font-mono text-xs text-[#242321]">{c.message_count} msgs</div>
                      {c.last_message_at && (
                        <div className="text-[10px] text-[#8C877D] font-mono">
                          {new Date(c.last_message_at).toLocaleDateString()}
                        </div>
                      )}
                    </td>

                    <td className="py-3 px-4">
                      {c.review_status === 'REVIEWED' ? (
                        <div className="space-y-0.5">
                          <span className="inline-flex items-center px-2 py-0.5 text-[9px] font-mono font-bold bg-[#EDF2EC] text-[#2E5230] border border-[#C6D8C6] rounded-[2px]">
                            ✓ REVIEWED
                          </span>
                          {c.last_reviewed_by && (
                            <div className="text-[9px] font-mono text-[#6F6A61] truncate max-w-[140px]">
                              By: {c.last_reviewed_by}
                            </div>
                          )}
                        </div>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 text-[9px] font-mono text-[#8C877D] bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px]">
                          UNREVIEWED
                        </span>
                      )}
                    </td>

                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => handleOpenReviewGate(c)}
                        className="px-3 py-1 bg-[#FCFAF5] border border-[#3F4634] text-[#3F4634] hover:bg-[#3F4634] hover:text-[#FCFAF5] rounded-[2px] font-semibold text-xs transition-colors"
                      >
                        {c.review_status === 'REVIEWED' ? 'Inspect History' : 'Review Matter'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Documented Oversight Review Modal (Safeguard Gate) */}
      {isReviewModalOpen && selectedMatter && (
        <div className="fixed inset-0 z-50 bg-[#242321]/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-[#FCFAF5] border border-[#DED6C8] max-w-3xl w-full p-6 rounded-[2px] shadow-xl space-y-4 max-h-[90vh] flex flex-col">
            {/* Modal Header */}
            <div className="border-b border-[#DED6C8] pb-3 flex items-start justify-between">
              <div>
                <span className="font-mono text-[10px] font-bold uppercase text-[#3F4634] block">
                  Platform Oversight Safeguard • Controlled Conversation Review
                </span>
                <h3 className="text-base font-serif font-bold text-[#242321] mt-0.5">
                  Matter {selectedMatter.matter_code}: {selectedMatter.title}
                </h3>
                <p className="text-[11px] text-[#6F6A61] mt-0.5">
                  Client: <strong>{selectedMatter.client_organization_name}</strong> | Counsel: <strong>{selectedMatter.lawyer_user_name || 'Assigned Counsel'}</strong>
                </p>
              </div>
              <button
                onClick={() => setIsReviewModalOpen(false)}
                className="text-xs font-mono text-[#6F6A61] hover:text-[#242321] p-1"
              >
                ✕ Close
              </button>
            </div>

            {/* If NOT authorized yet: Justification Gate */}
            {!activeReviewData ? (
              <form onSubmit={handleExecuteOversightReview} className="space-y-4 py-2 overflow-y-auto">
                <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] text-xs text-[#6F6A61] space-y-1.5 leading-relaxed">
                  <span className="font-mono text-[10px] font-bold uppercase text-[#7A4D1A] block">
                    Legal &amp; Compliance Requirement
                  </span>
                  <p>
                    Client-lawyer communications are confidential. Unrestricted or invisible administrative backdoors are prohibited.
                  </p>
                  <p>
                    To inspect conversation contents, you must provide a legitimate operational, compliance, safety, or dispute-resolution justification.
                  </p>
                  <p className="font-semibold text-[#242321]">
                    This access action, your identity, and your stated purpose will be permanently logged in Contractly&apos;s append-only audit trail.
                  </p>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-serif font-bold text-[#242321] block">
                    Review Reason (Mandatory):
                  </label>
                  <select
                    value={reviewReason}
                    onChange={(e) => setReviewReason(e.target.value)}
                    className="w-full p-2 text-xs bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-[#242321] focus:outline-none focus:border-[#3F4634]"
                  >
                    <option value="COMPLIANCE_REVIEW">Platform Compliance &amp; Ethical Standards Review</option>
                    <option value="SAFETY_FLAG">Platform Safety &amp; Abuse Prevention</option>
                    <option value="DISPUTE_RESOLUTION">Client-Lawyer Fee or Scope Dispute Resolution</option>
                    <option value="USER_SUPPORT_ESCALATION">Client Support Ticket Escalation</option>
                    <option value="REGULATORY_AUDIT">Regulatory or Bar Council Inquiry</option>
                    <option value="OTHER">Other Specific Operational Reason</option>
                  </select>
                </div>

                {reviewReason === 'OTHER' && (
                  <div className="space-y-1.5">
                    <label className="text-xs font-mono text-[#6F6A61] block">
                      Specific Justification Description:
                    </label>
                    <input
                      type="text"
                      value={customReason}
                      onChange={(e) => setCustomReason(e.target.value)}
                      placeholder="Specify detailed operational reason..."
                      className="w-full p-2 text-xs bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-[#242321] focus:outline-none focus:border-[#3F4634]"
                    />
                  </div>
                )}

                <div className="space-y-1.5">
                  <label className="text-xs font-mono text-[#6F6A61] block">
                    Administrative Review Notes (Optional):
                  </label>
                  <textarea
                    value={reviewNotes}
                    onChange={(e) => setReviewNotes(e.target.value)}
                    placeholder="Provide case number, ticket reference, or preliminary context..."
                    rows={2}
                    className="w-full p-2 text-xs bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-[#242321] focus:outline-none focus:border-[#3F4634]"
                  />
                </div>

                {reviewError && (
                  <div className="p-2.5 bg-[#FDF2F2] border border-[#F2C6C6] text-[#A33B3B] text-xs rounded-[2px]">
                    {reviewError}
                  </div>
                )}

                <div className="flex items-center justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsReviewModalOpen(false)}
                    className="px-4 py-2 bg-[#FCFAF5] border border-[#DED6C8] text-xs text-[#242321] rounded-[2px] hover:bg-[#F7F3EA]"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={authorizingReview}
                    className="px-5 py-2 bg-[#3F4634] text-[#FCFAF5] text-xs font-bold rounded-[2px] hover:bg-[#59604A] transition-colors disabled:opacity-40"
                  >
                    {authorizingReview ? 'Authorizing & Logging...' : 'Authorize & Review Messages'}
                  </button>
                </div>
              </form>
            ) : (
              /* Review Authorized: Display Messages & Internal Notes */
              <div className="flex-1 overflow-y-auto space-y-4 py-2">
                {/* Audit Record Summary */}
                <div className="p-3 bg-[#E8EFE0] border border-[#C5D5B8] rounded-[2px] flex items-center justify-between text-xs text-[#3F4634]">
                  <div>
                    <span className="font-mono text-[10px] uppercase font-bold block">
                      Audit Record Appended
                    </span>
                    <span>
                      Reviewed by <strong>{activeReviewData.reviewed_by}</strong> for <strong>{activeReviewData.review_reason}</strong>.
                    </span>
                  </div>
                  <span className="font-mono text-[10px] text-[#3F4634]">
                    {new Date(activeReviewData.reviewed_at).toLocaleTimeString()}
                  </span>
                </div>

                {/* Read-Only Message Log */}
                <div className="space-y-2">
                  <h4 className="font-serif font-bold text-xs uppercase tracking-wider text-[#242321]">
                    Client-Lawyer Message History ({activeReviewData.messages.length} messages)
                  </h4>
                  <p className="text-[11px] text-[#6F6A61] italic">
                    Administrative Oversight Mode (Read-Only). Impersonation, message insertion, or history tampering is strictly prohibited.
                  </p>

                  <div className="bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] p-3 max-h-60 overflow-y-auto space-y-3">
                    {activeReviewData.messages.length === 0 ? (
                      <div className="text-center py-6 text-xs text-[#6F6A61] italic">
                        No messages have been exchanged in this matter thread yet.
                      </div>
                    ) : (
                      activeReviewData.messages.map((m) => (
                        <div key={m.id} className="p-2.5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-1">
                          <div className="flex items-center justify-between text-[10px] font-mono text-[#6F6A61]">
                            <span className="font-bold text-[#242321]">
                              {m.sender_name} ({m.sender_type})
                            </span>
                            <span>{new Date(m.created_at).toLocaleString()}</span>
                          </div>
                          <p className="text-xs text-[#242321] whitespace-pre-wrap leading-relaxed">
                            {m.message_text}
                          </p>
                          {m.is_internal_note && (
                            <span className="text-[9px] font-mono text-[#7A4D1A] bg-[#FDF8EE] px-1.5 py-0.2 border border-[#E8D9B5] rounded-[2px]">
                              Chambers Internal Note
                            </span>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {/* Internal Admin Notes (Strictly in AuditLog) */}
                <div className="space-y-2 pt-2 border-t border-[#DED6C8]">
                  <h4 className="font-serif font-bold text-xs uppercase tracking-wider text-[#242321]">
                    Internal Administrative Notes
                  </h4>
                  <p className="text-[11px] text-[#6F6A61]">
                    Notes recorded here are stored securely in AuditLog and are NEVER visible to the client or lawyer.
                  </p>

                  {/* Add Note Form */}
                  <form onSubmit={handleAddInternalNote} className="space-y-2">
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={newAdminNote}
                        onChange={(e) => setNewAdminNote(e.target.value)}
                        placeholder="Add compliance assessment, dispute determination, or investigation note..."
                        className="flex-1 p-2 text-xs bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-[#242321] focus:outline-none focus:border-[#3F4634]"
                      />
                      <button
                        type="submit"
                        disabled={submittingNote || !newAdminNote.trim()}
                        className="px-4 py-2 bg-[#3F4634] text-[#FCFAF5] text-xs font-semibold rounded-[2px] hover:bg-[#59604A] disabled:opacity-40"
                      >
                        {submittingNote ? 'Saving...' : 'Add Note'}
                      </button>
                    </div>
                    {noteSuccess && (
                      <p className="text-[11px] font-mono text-[#2E5230]">{noteSuccess}</p>
                    )}
                  </form>

                  {/* Existing Notes List */}
                  {activeReviewData.admin_notes.length > 0 && (
                    <div className="space-y-1.5 max-h-36 overflow-y-auto">
                      {activeReviewData.admin_notes.map((n) => (
                        <div key={n.id} className="p-2 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] text-[11px]">
                          <div className="flex items-center justify-between font-mono text-[9px] text-[#6F6A61] mb-0.5">
                            <span>Admin: {n.admin_email}</span>
                            <span>{n.timestamp ? new Date(n.timestamp).toLocaleString() : ''}</span>
                          </div>
                          <p className="text-[#242321]">{n.detail}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Audit History of Previous Reviews */}
                {activeReviewData.audit_history.length > 0 && (
                  <div className="space-y-1.5 pt-2 border-t border-[#DED6C8]">
                    <h5 className="font-mono text-[10px] uppercase font-bold text-[#6F6A61]">
                      Previous Oversight Audits for this Matter
                    </h5>
                    <div className="space-y-1">
                      {activeReviewData.audit_history.map((a) => (
                        <div key={a.id} className="p-1.5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-[10px] font-mono text-[#6F6A61] flex items-center justify-between">
                          <span>{a.detail}</span>
                          <span>{a.timestamp ? new Date(a.timestamp).toLocaleDateString() : ''}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )}

      {/* Consultation Approval / Rejection Modal */}
      {decisionModal && (
        <div className="fixed inset-0 z-50 bg-[#242321]/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-[#FCFAF5] border border-[#DED6C8] max-w-lg w-full p-6 rounded-[2px] shadow-xl space-y-4">
            <div className="border-b border-[#DED6C8] pb-3">
              <span className="font-mono text-[10px] uppercase font-bold text-[#3F4634] block">
                Platform Action • Consultation Intake Decision
              </span>
              <h3 className="text-base font-serif font-bold text-[#242321] mt-0.5">
                {decisionModal.action === 'APPROVE'
                  ? `Approve Consultation Request (${decisionModal.request.matter_code})`
                  : `Reject Consultation Request (${decisionModal.request.matter_code})`}
              </h3>
            </div>

            <div className="space-y-2 text-xs text-[#6F6A61] bg-[#F7F3EA] p-3 border border-[#DED6C8] rounded-[2px]">
              <div>
                <strong className="text-[#242321]">Subject:</strong> {decisionModal.request.title}
              </div>
              <div>
                <strong className="text-[#242321]">Client:</strong> {decisionModal.request.client_organization_name} (
                {decisionModal.request.client_user_email || decisionModal.request.client_user_name})
              </div>
              <div>
                <strong className="text-[#242321]">Designated Advocate:</strong> {decisionModal.request.lawyer_user_name} (
                {decisionModal.request.lawyer_organization_name})
              </div>
              <div>
                <strong className="text-[#242321]">Conflict Check Target:</strong> {decisionModal.request.counterparty_name}
              </div>
              {decisionModal.request.preferred_time_slot && (
                <div>
                  <strong className="text-[#242321]">Requested Slot:</strong> {decisionModal.request.preferred_time_slot}
                </div>
              )}
            </div>

            <div className="space-y-1.5 text-xs">
              <label className="block font-medium text-[#242321]">
                {decisionModal.action === 'APPROVE'
                  ? 'Approval Justification / Operational Notes'
                  : 'Rejection Reason (Required for ethical & audit compliance)'}
              </label>
              <textarea
                rows={3}
                value={decisionModal.reason}
                onChange={(e) =>
                  setDecisionModal({ ...decisionModal, reason: e.target.value })
                }
                placeholder={
                  decisionModal.action === 'APPROVE'
                    ? 'e.g. Conflict check confirmed and attorney availability verified.'
                    : 'e.g. Schedule conflicts or jurisdictional practice constraint.'
                }
                className="w-full p-2 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-[#242321] focus:outline-none focus:border-[#3F4634]"
              />
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-[#DED6C8]">
              <button
                onClick={() => setDecisionModal(null)}
                disabled={decisionLoading}
                className="px-3 py-1.5 bg-[#FCFAF5] border border-[#DED6C8] text-xs font-medium text-[#242321] rounded-[2px] hover:bg-[#F7F3EA] transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleExecuteDecision}
                disabled={
                  decisionLoading ||
                  (decisionModal.action === 'REJECT' && !decisionModal.reason.trim())
                }
                className={`px-4 py-1.5 text-xs font-semibold text-[#FCFAF5] rounded-[2px] transition-colors disabled:opacity-40 ${
                  decisionModal.action === 'APPROVE'
                    ? 'bg-[#3F4634] hover:bg-[#2C3124]'
                    : 'bg-[#A33B3B] hover:bg-[#8B2F2F]'
                }`}
              >
                {decisionLoading
                  ? 'Processing...'
                  : decisionModal.action === 'APPROVE'
                  ? 'Confirm Approval & Activate Chat'
                  : 'Confirm Rejection'}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
