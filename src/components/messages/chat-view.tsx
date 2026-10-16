'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useContractly } from '@/context/contractly-context';
import { ConversationItem, MatterMessageItem } from '@/types/contractly';
import {
  fetchConversations,
  fetchMatterMessages,
  sendMatterMessage,
  markMatterNotificationsAsRead
} from '@/lib/api-client';

export function ChatView() {
  const { currentUser, accountType, addToast, setActiveNav, refreshNotifications } = useContractly();

  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [selectedMatterId, setSelectedMatterId] = useState<string | null>(null);
  const [messages, setMessages] = useState<MatterMessageItem[]>([]);
  const [hasAdminReview, setHasAdminReview] = useState(false);
  const [adminReviewDate, setAdminReviewDate] = useState<string | null>(null);
  const [adminReviewReason, setAdminReviewReason] = useState<string | null>(null);

  const [searchFilter, setSearchFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [conversationsError, setConversationsError] = useState<string | null>(null);
  const [messagesError, setMessagesError] = useState<string | null>(null);

  const [inputText, setInputText] = useState('');
  const [isInternalNote, setIsInternalNote] = useState(false);
  const [sending, setSending] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  const isLawyer = accountType === 'LEGAL_PROFESSIONAL' || accountType === 'PROFESSIONAL';

  // 1. Fetch Conversations
  const loadConversations = useCallback(async (isInitial = false) => {
    if (isInitial) setLoadingConversations(true);
    setConversationsError(null);
    try {
      const data = await fetchConversations();
      setConversations(data || []);
      // If no matter is selected and we have conversations, select the first one
      if (data && data.length > 0) {
        setSelectedMatterId((prev) => (prev ? prev : data[0].matter_id));
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unable to load conversations.';
      setConversationsError(msg);
    } finally {
      if (isInitial) setLoadingConversations(false);
    }
  }, []);

  useEffect(() => {
    loadConversations(true);
  }, [loadConversations]);

  // 2. Fetch Messages for Selected Matter
  const loadMessages = useCallback(async (matterId: string, isInitial = false) => {
    if (isInitial) setLoadingMessages(true);
    setMessagesError(null);
    try {
      const res = await fetchMatterMessages(matterId);
      setMessages(res.messages || []);
      setHasAdminReview(res.hasAdminReview);
      setAdminReviewDate(res.adminReviewDate || null);
      setAdminReviewReason(res.adminReviewReason || null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve messages.';
      setMessagesError(msg);
    } finally {
      if (isInitial) setLoadingMessages(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedMatterId) {
      setMessages([]);
      return;
    }
    loadMessages(selectedMatterId, true);

    // Automatically mark unread message notifications for this conversation as read
    markMatterNotificationsAsRead(selectedMatterId).then((ok) => {
      if (ok) {
        refreshNotifications();
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new Event('refresh-notifications'));
        }
      }
    });

    // Set up reliable polling interval (every 4 seconds)
    if (pollingRef.current) clearInterval(pollingRef.current);
    pollingRef.current = setInterval(() => {
      loadMessages(selectedMatterId, false);
      loadConversations(false);
    }, 4000);

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [selectedMatterId, loadMessages, loadConversations, refreshNotifications]);

  // Scroll to bottom when messages update
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 3. Send Message
  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!selectedMatterId) return;

    const text = inputText.trim();
    if (!text) return;
    if (text.length > 5000) {
      addToast('Message too long', 'Maximum character limit is 5,000.', 'warning');
      return;
    }

    setSending(true);
    try {
      const newMsg = await sendMatterMessage(selectedMatterId, text, isInternalNote);
      setMessages((prev) => [...prev, newMsg]);
      setInputText('');
      setIsInternalNote(false);
      loadConversations(false);
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new Event('refresh-notifications'));
      }

    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to transmit message.';
      addToast('Delivery Failed', msg, 'danger');
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Filtered conversations
  const filteredConversations = conversations.filter((c) => {
    if (statusFilter !== 'ALL' && c.status !== statusFilter) return false;
    if (!searchFilter.trim()) return true;
    const term = searchFilter.toLowerCase();
    return (
      c.matter_code.toLowerCase().includes(term) ||
      c.title.toLowerCase().includes(term) ||
      c.client_organization_name.toLowerCase().includes(term) ||
      (c.client_user_name && c.client_user_name.toLowerCase().includes(term)) ||
      c.lawyer_organization_name.toLowerCase().includes(term) ||
      (c.lawyer_user_name && c.lawyer_user_name.toLowerCase().includes(term)) ||
      (c.contract_title && c.contract_title.toLowerCase().includes(term))
    );
  });

  const selectedConv = conversations.find((c) => c.matter_id === selectedMatterId);
  const isMatterPending = selectedConv
    ? ['SUBMITTED', 'UNDER_REVIEW'].includes(selectedConv.status)
    : false;
  const isMatterClosed = selectedConv
    ? ['DECLINED', 'CANCELLED', 'RESOLVED', 'CLOSED'].includes(selectedConv.status)
    : false;

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] min-h-[580px] bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] overflow-hidden select-none">
      {/* Top Banner / Privacy & Compliance Oversight Disclosure */}
      <div className="bg-[#F7F3EA] border-b border-[#DED6C8] px-4 py-2.5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-xs">
        <div className="flex items-center gap-2 text-[#242321]">
          <span className="font-serif font-bold text-sm tracking-wide">Matter Messages</span>
          <span className="text-[11px] font-mono text-[#6F6A61] border-l border-[#DED6C8] pl-2 hidden sm:inline">
            Direct client-advocate communications
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-[#6F6A61] hidden md:inline">
            Platform administrators may review consultation communications solely for compliance and safety audit purposes.
          </span>
          <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-mono font-bold bg-[#E8EFE0] text-[#3F4634] border border-[#C5D5B8] rounded-[2px] shrink-0">
            Encrypted &amp; Audited
          </span>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Left Column: Conversation Directory */}
        <aside className="w-full sm:w-80 md:w-96 border-r border-[#DED6C8] flex flex-col bg-[#FCFAF5] shrink-0">
          {/* Search & Filter Header */}
          <div className="p-3 border-b border-[#DED6C8] space-y-2 bg-[#FCFAF5]">
            <div className="relative">
              <input
                type="text"
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                placeholder="Search by code, party, or matter..."
                className="w-full px-3 py-1.5 text-xs bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] text-[#242321] placeholder-[#6F6A61] focus:outline-none focus:border-[#3F4634]"
              />
              {searchFilter && (
                <button
                  onClick={() => setSearchFilter('')}
                  className="absolute right-2.5 top-2 text-[#6F6A61] hover:text-[#242321] text-xs"
                >
                  ✕
                </button>
              )}
            </div>

            <div className="flex items-center justify-between text-[11px] text-[#6F6A61]">
              <span>Status:</span>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] px-2 py-0.5 text-[11px] text-[#242321] focus:outline-none focus:border-[#3F4634]"
              >
                <option value="ALL">All States</option>
                <option value="ACCEPTED">Approved (Active)</option>
                <option value="SUBMITTED">Pending Approval</option>
                <option value="DECLINED">Rejected</option>
                <option value="CLOSED">Closed</option>
              </select>
            </div>
          </div>

          {/* Conversation List Body */}
          <div className="flex-1 overflow-y-auto divide-y divide-[#DED6C8]">
            {loadingConversations ? (
              <div className="p-8 text-center text-xs text-[#6F6A61] italic">
                Loading conversations...
              </div>
            ) : conversationsError ? (
              <div className="p-6 text-center space-y-2">
                <p className="text-xs text-[#A33B3B]">{conversationsError}</p>
                <button
                  onClick={() => loadConversations(true)}
                  className="px-3 py-1 bg-[#F7F3EA] border border-[#DED6C8] text-xs font-medium text-[#242321] rounded-[2px] hover:bg-[#EAE5D9]"
                >
                  Retry
                </button>
              </div>
            ) : filteredConversations.length === 0 ? (
              <div className="p-8 text-center space-y-2">
                <p className="text-xs font-serif text-[#242321] font-semibold">No conversations found</p>
                <p className="text-[11px] text-[#6F6A61] leading-relaxed">
                  {conversations.length === 0
                    ? 'Messaging is tied directly to active legal matters and consultation requests. Visit "Get Legal Help" to request an advocate review.'
                    : 'No conversations match your search filter.'}
                </p>
              </div>
            ) : (
              filteredConversations.map((conv) => {
                const isSelected = conv.matter_id === selectedMatterId;
                const otherPartyName = isLawyer
                  ? conv.client_user_name || conv.client_organization_name
                  : conv.lawyer_user_name || conv.lawyer_organization_name;

                return (
                  <button
                    key={conv.matter_id}
                    onClick={() => setSelectedMatterId(conv.matter_id)}
                    className={`w-full text-left p-3 transition-colors flex flex-col gap-1 focus:outline-none ${
                      isSelected
                        ? 'bg-[#F2ECE1] border-l-4 border-l-[#3F4634]'
                        : 'hover:bg-[#F7F3EA]/70'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-1">
                      <span className="font-mono text-[10px] font-bold text-[#3F4634]">
                        {conv.matter_code}
                      </span>
                      <span
                        className={`text-[9px] font-mono px-1.5 py-0.5 border rounded-[2px] ${
                          conv.status === 'ACCEPTED' || conv.status === 'MATTER_ACTIVE'
                            ? 'bg-[#E8EFE0] text-[#3F4634] border-[#C5D5B8]'
                            : conv.status === 'SUBMITTED' || conv.status === 'UNDER_REVIEW'
                            ? 'bg-[#FDF8EE] text-[#7A4D1A] border-[#E8D9B5]'
                            : conv.status === 'DECLINED'
                            ? 'bg-[#FDF2F2] text-[#A33B3B] border-[#F2C6C6]'
                            : 'bg-[#F0EEEA] text-[#6F6A61] border-[#DED6C8]'
                        }`}
                      >
                        {conv.status === 'SUBMITTED' || conv.status === 'UNDER_REVIEW'
                          ? 'Pending Approval'
                          : conv.status === 'ACCEPTED' || conv.status === 'MATTER_ACTIVE'
                          ? 'Approved'
                          : conv.status === 'DECLINED'
                          ? 'Rejected'
                          : conv.status.replace(/_/g, ' ')}
                      </span>
                    </div>

                    <div className="font-serif font-bold text-xs text-[#242321] truncate">
                      {conv.title}
                    </div>

                    <div className="text-[11px] text-[#6F6A61] flex items-center justify-between">
                      <span className="truncate">{otherPartyName}</span>
                      {conv.last_message_at && (
                        <span className="font-mono text-[9px] text-[#8C877D] shrink-0 ml-1">
                          {new Date(conv.last_message_at).toLocaleDateString([], {
                            month: 'short',
                            day: 'numeric'
                          })}
                        </span>
                      )}
                    </div>

                    {conv.last_message_text && (
                      <p className="text-[11px] text-[#6F6A61] line-clamp-1 italic text-left">
                        {conv.last_message_text}
                      </p>
                    )}

                    {conv.has_admin_review && (
                      <div className="mt-0.5 flex items-center gap-1 text-[9px] font-mono text-[#7A4D1A]">
                        <span>🛡️</span>
                        <span>Audited by platform</span>
                      </div>
                    )}
                  </button>
                );
              })
            )}
          </div>
        </aside>

        {/* Right Column: Active Conversation Thread */}
        <main className="flex-1 flex flex-col bg-[#FCFAF5] min-w-0">
          {selectedConv ? (
            <>
              {/* Thread Header */}
              <div className="p-3 sm:p-4 border-b border-[#DED6C8] bg-[#F7F3EA] flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div className="space-y-0.5 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] font-bold text-[#3F4634] uppercase tracking-wide">
                      {selectedConv.matter_code}
                    </span>
                    <span className="text-[10px] text-[#6F6A61]">|</span>
                    <span className="text-xs font-semibold text-[#242321] truncate">
                      {isLawyer
                        ? `Client: ${selectedConv.client_user_name || selectedConv.client_organization_name}`
                        : `Counsel: ${selectedConv.lawyer_user_name || selectedConv.lawyer_organization_name}`}
                    </span>
                  </div>
                  <h2 className="font-serif font-bold text-sm text-[#242321] truncate">
                    {selectedConv.title}
                  </h2>
                  {selectedConv.contract_title && (
                    <p className="text-[11px] text-[#6F6A61] truncate">
                      Referenced Agreement: <span className="font-medium text-[#242321]">{selectedConv.contract_title}</span>
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => selectedMatterId && loadMessages(selectedMatterId, false)}
                    className="p-1.5 text-xs text-[#6F6A61] hover:text-[#242321] bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px]"
                    title="Refresh conversation"
                  >
                    ↻ Refresh
                  </button>
                  <span
                    className={`text-[10px] font-mono font-bold px-2 py-0.5 border rounded-[2px] ${
                      selectedConv.status === 'MATTER_ACTIVE'
                        ? 'bg-[#E8EFE0] text-[#3F4634] border-[#C5D5B8]'
                        : isMatterClosed
                        ? 'bg-[#F0EEEA] text-[#6F6A61] border-[#DED6C8]'
                        : 'bg-[#FDF8EE] text-[#7A4D1A] border-[#E8D9B5]'
                    }`}
                  >
                    {selectedConv.status.replace(/_/g, ' ')}
                  </span>
                </div>
              </div>

              {/* Platform Transparency Notice Banner (Section 5) */}
              <div className="px-4 py-2 bg-[#F7F3EA] border-b border-[#DED6C8] text-[11px] text-[#6F6A61] leading-relaxed flex items-start gap-2">
                <span className="font-mono text-xs text-[#3F4634] shrink-0 font-bold">ℹ️</span>
                <p>
                  <strong>Platform Transparency Notice:</strong> Communications in this matter are transmitted securely within Contractly. Authorized platform personnel may review conversations strictly for disclosed compliance, dispute resolution, or safety oversight. Conversations are not end-to-end encrypted.
                </p>
              </div>

              {/* Administrative Oversight Audit Notice (if conversation was reviewed) */}
              {hasAdminReview && (
                <div className="px-4 py-2 bg-[#FDF8EE] border-b border-[#E8D9B5] text-[11px] text-[#7A4D1A] flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold">🛡️</span>
                    <span>
                      <strong>Administrative Notice:</strong> This conversation was accessed for platform compliance oversight
                      {adminReviewDate ? ` on ${new Date(adminReviewDate).toLocaleDateString()}` : ''}
                      {adminReviewReason ? ` (Reason: ${adminReviewReason})` : ''}.
                    </span>
                  </div>
                  <span className="font-mono text-[10px] px-1.5 py-0.5 bg-[#FCFAF5] border border-[#E8D9B5] rounded-[2px]">
                    Audited
                  </span>
                </div>
              )}

              {/* Closed Matter Banner (if no longer active for messaging) */}
              {isMatterClosed && (
                <div className="px-4 py-2 bg-[#F7EFE4] border-b border-[#E5D2B8] text-[11px] text-[#7A4D1A] flex items-center gap-2">
                  <span className="font-mono font-bold">🔒</span>
                  <span>
                    This legal matter is <strong>{selectedConv.status.toLowerCase()}</strong>. As per platform policy, active messaging has concluded. Historical records are preserved.
                  </span>
                </div>
              )}

              {/* Message History Scroll Pane */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-[#FCFAF5]">
                {loadingMessages ? (
                  <div className="p-8 text-center text-xs text-[#6F6A61] italic">
                    Loading matter messages...
                  </div>
                ) : messagesError ? (
                  <div className="p-6 text-center space-y-2">
                    <p className="text-xs text-[#A33B3B]">{messagesError}</p>
                    <button
                      onClick={() => selectedMatterId && loadMessages(selectedMatterId, true)}
                      className="px-3 py-1 bg-[#F7F3EA] border border-[#DED6C8] text-xs rounded-[2px]"
                    >
                      Retry
                    </button>
                  </div>
                ) : messages.length === 0 ? (
                  <div className="p-8 text-center space-y-2 max-w-md mx-auto text-[#6F6A61]">
                    <p className="font-serif font-bold text-sm text-[#242321]">No messages yet</p>
                    <p className="text-xs leading-relaxed">
                      Begin communication regarding this legal matter. Both parties will be notified securely within Contractly.
                    </p>
                  </div>
                ) : (
                  messages.map((msg) => {
                    const isSelf = msg.sender_user_id === currentUser?.id;
                    return (
                      <div
                        key={msg.id}
                        className={`flex flex-col max-w-[85%] sm:max-w-[70%] ${
                          isSelf ? 'ml-auto items-end' : 'mr-auto items-start'
                        }`}
                      >
                        {/* Sender Label and Timestamp */}
                        <div className="flex items-center gap-1.5 text-[10px] font-mono text-[#6F6A61] mb-1">
                          <span className="font-medium text-[#242321]">
                            {isSelf ? 'You' : msg.sender_name}
                          </span>
                          <span className="px-1 py-0.2 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] text-[9px]">
                            {msg.sender_type}
                          </span>
                          {msg.is_internal_note && (
                            <span className="px-1 py-0.2 bg-[#FDF8EE] text-[#7A4D1A] border border-[#E8D9B5] rounded-[2px] text-[9px] font-bold">
                              Chambers Internal Note
                            </span>
                          )}
                          <span>•</span>
                          <span>
                            {new Date(msg.created_at).toLocaleTimeString([], {
                              hour: '2-digit',
                              minute: '2-digit'
                            })}
                          </span>
                        </div>

                        {/* Bubble */}
                        <div
                          className={`p-3 rounded-[2px] text-xs leading-relaxed break-words whitespace-pre-wrap ${
                            msg.is_internal_note
                              ? 'bg-[#FDF8EE] border border-[#E8D9B5] text-[#7A4D1A]'
                              : isSelf
                              ? 'bg-[#3F4634] text-[#FCFAF5]'
                              : 'bg-[#F7F3EA] border border-[#DED6C8] text-[#242321]'
                          }`}
                        >
                          {msg.message_text}
                        </div>
                      </div>
                    );
                  })
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Message Input Box */}
              <div className="p-3 border-t border-[#DED6C8] bg-[#F7F3EA]">
                {isMatterPending ? (
                  <div className="p-4 bg-[#FCFAF5] border border-[#E8D9B5] rounded-[2px] text-center text-xs text-[#7A4D1A] space-y-1">
                    <div className="font-semibold text-xs text-[#7A4D1A]">
                      Consultation Request Pending Platform Administrative Approval
                    </div>
                    <p className="text-[11px] text-[#6F6A61] max-w-md mx-auto leading-relaxed">
                      Administrators and counsel are reviewing attorney availability and conflict-of-interest clearance. Interactive messaging in this consultation thread will activate immediately once approved.
                    </p>
                  </div>
                ) : isMatterClosed ? (
                  <div className="p-3 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-center text-xs text-[#6F6A61] italic">
                    Messaging is closed for this matter. New messages cannot be submitted.
                  </div>
                ) : (
                  <form onSubmit={handleSendMessage} className="space-y-2">
                    <div className="relative">
                      <textarea
                        value={inputText}
                        onChange={(e) => setInputText(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={
                          isInternalNote
                            ? 'Draft private chambers note (invisible to client)...'
                            : 'Type your message (Enter to send, Shift+Enter for new line)...'
                        }
                        rows={2}
                        maxLength={5000}
                        disabled={sending}
                        className="w-full p-2.5 text-xs bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-[#242321] placeholder-[#6F6A61] focus:outline-none focus:border-[#3F4634] resize-none"
                      />
                    </div>

                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-xs">
                      <div className="flex items-center gap-3">
                        {isLawyer && (
                          <label className="flex items-center gap-1.5 text-[11px] text-[#6F6A61] cursor-pointer">
                            <input
                              type="checkbox"
                              checked={isInternalNote}
                              onChange={(e) => setIsInternalNote(e.target.checked)}
                              className="accent-[#3F4634]"
                            />
                            <span>Chambers internal note (client cannot view)</span>
                          </label>
                        )}
                        <span className="text-[10px] font-mono text-[#8C877D]">
                          {inputText.length} / 5000
                        </span>
                      </div>

                      <div className="flex items-center gap-2 self-end sm:self-auto">
                        <button
                          type="submit"
                          disabled={sending || !inputText.trim()}
                          className="px-4 py-1.5 bg-[#3F4634] text-[#FCFAF5] text-xs font-semibold rounded-[2px] hover:bg-[#59604A] transition-colors disabled:opacity-40"
                        >
                          {sending ? 'Sending...' : 'Send Message'}
                        </button>
                      </div>
                    </div>
                  </form>
                )}
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-[#6F6A61] space-y-3">
              <span className="text-3xl font-serif text-[#3F4634]">
                {conversations.length === 0 ? '⚖️' : '💬'}
              </span>
              <h3 className="font-serif font-bold text-base text-[#242321]">
                {conversations.length === 0 ? 'No Active Conversations' : 'Select a conversation'}
              </h3>
              <p className="text-xs max-w-sm leading-relaxed text-[#6F6A61]">
                {conversations.length === 0
                  ? 'Messaging is bound directly to accepted legal consultations and client-advocate matters. Submit an inquiry through the advocate directory to begin.'
                  : 'Choose a consultation or legal matter thread from the directory to review and exchange messages with counsel or client.'}
              </p>
              {conversations.length === 0 && (
                <button
                  onClick={() => setActiveNav('lawyers')}
                  className="px-3.5 py-1.5 bg-[#3F4634] text-[#FCFAF5] text-xs font-semibold rounded-[2px] hover:bg-[#2C3124] transition-colors"
                >
                  Explore Lawyer Directory →
                </button>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
