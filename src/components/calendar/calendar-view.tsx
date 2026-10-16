'use client';

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useContractly } from '@/context/contractly-context';
import {
  CalendarEventItem,
  fetchCalendarEvents,
  createCalendarEvent,
  updateCalendarEvent,
  deleteCalendarEvent
} from '@/lib/api-client';
import { Button } from '@/components/ui/button';

interface CalendarViewProps {
  onOpenContract?: (contractId: string) => void;
  onNavigateTab?: (tab: string) => void;
}

export function CalendarView({ onOpenContract, onNavigateTab }: CalendarViewProps) {
  const { contracts, addToast } = useContractly();

  const [currentDate, setCurrentDate] = useState<Date>(new Date());
  const [viewMode, setViewMode] = useState<'month' | 'agenda'>('month');
  const [events, setEvents] = useState<CalendarEventItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Filters
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [selectedPriority, setSelectedPriority] = useState<string>('ALL');
  const [selectedContractId, setSelectedContractId] = useState<string>('ALL');

  // Selected event modal
  const [selectedEvent, setSelectedEvent] = useState<CalendarEventItem | null>(null);
  // Selected day events modal for high-density dates
  const [selectedDayEvents, setSelectedDayEvents] = useState<{ date: string; events: CalendarEventItem[] } | null>(null);

  // Add custom event modal
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newDate, setNewDate] = useState('');
  const [newType, setNewType] = useState('CUSTOM_DATE');
  const [newPriority, setNewPriority] = useState<'CRITICAL' | 'IMPORTANT' | 'INFORMATIONAL'>('IMPORTANT');
  const [newContractId, setNewContractId] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [newIsImportant, setNewIsImportant] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadEvents = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await fetchCalendarEvents({
        category: selectedCategory !== 'ALL' ? selectedCategory : undefined,
        priority: selectedPriority !== 'ALL' ? selectedPriority : undefined,
        contractId: selectedContractId !== 'ALL' ? selectedContractId : undefined
      });
      setEvents(data);
    } catch (err) {
      console.error('Error loading events:', err);
    } finally {
      setIsLoading(false);
    }
  }, [selectedCategory, selectedPriority, selectedContractId]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  // Calendar calculations
  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  const firstDayOfMonth = new Date(year, month, 1);
  const startingDayOfWeek = firstDayOfMonth.getDay(); // 0 is Sunday
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  const handlePrev = () => {
    setCurrentDate(new Date(year, month - 1, 1));
  };

  const handleNext = () => {
    setCurrentDate(new Date(year, month + 1, 1));
  };

  const handleToday = () => {
    setCurrentDate(new Date());
  };

  // Group events by day string 'YYYY-MM-DD'
  const eventsByDate = useMemo(() => {
    const map: Record<string, CalendarEventItem[]> = {};
    for (const ev of events) {
      const d = ev.event_date.split('T')[0];
      if (!map[d]) map[d] = [];
      map[d].push(ev);
    }
    return map;
  }, [events]);

  // Sort events per day so key contract milestones appear first
  const sortedDayEvents = useMemo(() => {
    const map: Record<string, CalendarEventItem[]> = {};
    const catOrder: Record<string, number> = {
      CONTRACT_EXPIRY: 0,
      CONTRACT_RENEWAL: 1,
      RENEWAL_NOTICE: 2,
      TERMINATION_NOTICE: 3,
      CONTRACT_TERMINATION: 4,
      CONTRACT_EFFECTIVE: 5,
      SIGNATURE_DEADLINE: 6,
      APPROVAL_DEADLINE: 7,
      PAYMENT_DEADLINE: 8,
      OBLIGATION_DUE: 9,
      CUSTOM_DATE: 10
    };
    const pOrder: Record<string, number> = { CRITICAL: 0, IMPORTANT: 1, INFORMATIONAL: 2 };

    for (const [dateKey, dayItems] of Object.entries(eventsByDate)) {
      map[dateKey] = [...dayItems].sort((a, b) => {
        // Contract End Date / Expiry strictly first
        if (a.event_type === 'CONTRACT_EXPIRY' && b.event_type !== 'CONTRACT_EXPIRY') return -1;
        if (b.event_type === 'CONTRACT_EXPIRY' && a.event_type !== 'CONTRACT_EXPIRY') return 1;

        const ca = catOrder[a.event_type] ?? 50;
        const cb = catOrder[b.event_type] ?? 50;
        if (ca !== cb) return ca - cb;

        const pa = pOrder[a.priority] ?? 5;
        const pb = pOrder[b.priority] ?? 5;
        if (pa !== pb) return pa - pb;

        return a.title.localeCompare(b.title);
      });
    }
    return map;
  }, [eventsByDate]);

  const handleCreateCustomEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || !newDate) {
      addToast('Validation Error', 'Title and date are required.', 'warning');
      return;
    }
    setIsSubmitting(true);
    try {
      const res = await createCalendarEvent({
        title: newTitle.trim(),
        event_date: newDate,
        event_type: newType,
        priority: newPriority,
        contract_id: newContractId || null,
        description: newDescription.trim() || undefined,
        is_important: newIsImportant
      });
      if (res) {
        addToast('Event Created', `Successfully scheduled "${newTitle}"`, 'success');
        setIsAddModalOpen(false);
        setNewTitle('');
        setNewDate('');
        setNewDescription('');
        setNewIsImportant(false);
        loadEvents();
      } else {
        addToast('Error', 'Failed to create calendar event.', 'danger');
      }
    } catch (err) {
      addToast('Error', 'An unexpected error occurred.', 'danger');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCompleteEvent = async (ev: CalendarEventItem) => {
    const res = await updateCalendarEvent(ev.id, { status: 'COMPLETED' });
    if (res) {
      addToast('Event Completed', `Marked "${ev.title}" as completed.`, 'success');
      setSelectedEvent(null);
      loadEvents();
    }
  };

  const handleDeleteEvent = async (ev: CalendarEventItem) => {
    if (!window.confirm(`Are you sure you want to remove "${ev.title}"?`)) return;
    const ok = await deleteCalendarEvent(ev.id);
    if (ok) {
      addToast('Event Removed', 'Event was deleted from the calendar.', 'info');
      setSelectedEvent(null);
      loadEvents();
    }
  };

  const getPriorityBadgeClass = (priority: string) => {
    if (priority === 'CRITICAL') return 'bg-[#FDF2F2] text-[#8B3F3F] border-[#F5C2C2]';
    if (priority === 'IMPORTANT') return 'bg-[#FEF9EE] text-[#9A6A32] border-[#F7E5C1]';
    return 'bg-[#F7F3EA] text-[#6F6A61] border-[#DED6C8]';
  };

  const getStatusBadgeClass = (status: string) => {
    if (status === 'OVERDUE') return 'bg-[#8B3F3F] text-[#FCFAF5]';
    if (status === 'DUE_SOON') return 'bg-[#9A6A32] text-[#FCFAF5]';
    if (status === 'COMPLETED') return 'bg-[#3F4634] text-[#FCFAF5]';
    return 'bg-[#EFECE3] text-[#3A3835]';
  };

  return (
    <div className="space-y-6">
      {/* 1. Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#DED6C8]">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-serif font-bold text-xl text-[#242321]">Contract Calendar</span>
            <span className="text-xs uppercase font-mono tracking-wider text-[#6F6A61] px-2 py-0.5 bg-[#EFECE3] border border-[#DED6C8] rounded-[2px]">
              Obligations & Deadlines
            </span>
          </div>
          <p className="text-xs text-[#6F6A61] mt-1">
            Proactively monitor contractual renewal windows, notice cutoffs, payment milestones, and compliance dates.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setViewMode(viewMode === 'month' ? 'agenda' : 'month')}
            className="text-xs"
          >
            {viewMode === 'month' ? 'Agenda View' : 'Month View'}
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsAddModalOpen(true)}
            className="text-xs font-semibold"
          >
            + Add Custom Date
          </Button>
        </div>
      </div>

      {/* 2. Navigation & Filter Bar */}
      <div className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] p-3 flex flex-wrap items-center justify-between gap-3">
        {/* Month Navigation */}
        <div className="flex items-center gap-2">
          <button
            onClick={handlePrev}
            className="px-2.5 py-1 text-xs border border-[#DED6C8] rounded-[2px] bg-[#F7F3EA] text-[#242321] hover:bg-[#EFECE3]"
            title="Previous Period"
          >
            ‹ Prev
          </button>
          <button
            onClick={handleToday}
            className="px-2.5 py-1 text-xs border border-[#DED6C8] rounded-[2px] bg-[#F7F3EA] text-[#242321] hover:bg-[#EFECE3] font-medium"
          >
            Today
          </button>
          <button
            onClick={handleNext}
            className="px-2.5 py-1 text-xs border border-[#DED6C8] rounded-[2px] bg-[#F7F3EA] text-[#242321] hover:bg-[#EFECE3]"
            title="Next Period"
          >
            Next ›
          </button>
          <span className="font-serif font-bold text-base text-[#242321] ml-2">
            {monthNames[month]} {year}
          </span>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {/* Category Filter */}
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="bg-[#F7F3EA] border border-[#DED6C8] px-2 py-1 rounded-[2px] text-[#242321]"
          >
            <option value="ALL">All Categories</option>
            <option value="CONTRACT_EXPIRY">Contract Expiration / End Date</option>
            <option value="CONTRACT_RENEWAL">Renewal Date</option>
            <option value="RENEWAL_NOTICE">Renewal Notice</option>
            <option value="TERMINATION_NOTICE">Termination Notice</option>
            <option value="CONTRACT_TERMINATION">Contract Termination</option>
            <option value="CONTRACT_EFFECTIVE">Contract Effective Date</option>
            <option value="OBLIGATION_DUE">Obligation Due</option>
            <option value="PAYMENT_DEADLINE">Payment Deadline</option>
            <option value="APPROVAL_DEADLINE">Approval Deadline</option>
            <option value="SIGNATURE_DEADLINE">Signature Deadline</option>
            <option value="CUSTOM_DATE">Custom Dates</option>
          </select>

          {/* Priority Filter */}
          <select
            value={selectedPriority}
            onChange={(e) => setSelectedPriority(e.target.value)}
            className="bg-[#F7F3EA] border border-[#DED6C8] px-2 py-1 rounded-[2px] text-[#242321]"
          >
            <option value="ALL">All Priorities</option>
            <option value="CRITICAL">Critical</option>
            <option value="IMPORTANT">Important</option>
            <option value="INFORMATIONAL">Informational</option>
          </select>

          {/* Contract Filter */}
          <select
            value={selectedContractId}
            onChange={(e) => setSelectedContractId(e.target.value)}
            className="bg-[#F7F3EA] border border-[#DED6C8] px-2 py-1 rounded-[2px] text-[#242321] max-w-[180px] truncate"
          >
            <option value="ALL">All Contracts</option>
            {contracts.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* 3. Monthly Grid View */}
      {viewMode === 'month' && (
        <div className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] overflow-hidden shadow-sm">
          {/* Day Headers */}
          <div className="grid grid-cols-7 border-b border-[#DED6C8] bg-[#F7F3EA] text-center text-[11px] font-mono font-semibold uppercase tracking-wider text-[#6F6A61] py-2">
            <div>Sun</div>
            <div>Mon</div>
            <div>Tue</div>
            <div>Wed</div>
            <div>Thu</div>
            <div>Fri</div>
            <div>Sat</div>
          </div>

          {/* Calendar Day Cells */}
          <div className="grid grid-cols-7 auto-rows-fr divide-x divide-y divide-[#DED6C8]">
            {/* Blank leading days */}
            {Array.from({ length: startingDayOfWeek }).map((_, i) => (
              <div key={`blank-${i}`} className="min-h-[105px] bg-[#F7F3EA]/30 p-1.5" />
            ))}

            {/* Days of Current Month */}
            {Array.from({ length: daysInMonth }).map((_, i) => {
              const dayNum = i + 1;
              const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(dayNum).padStart(2, '0')}`;
              const dayEvents = sortedDayEvents[dateStr] || [];
              const isToday =
                new Date().toISOString().split('T')[0] === dateStr;

              return (
                <div
                  key={`day-${dayNum}`}
                  className={`min-h-[105px] p-1.5 flex flex-col justify-between transition-colors ${
                    isToday ? 'bg-[#FCFAF5] ring-2 ring-inset ring-[#3F4634]' : 'bg-[#FCFAF5] hover:bg-[#F7F3EA]/40'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <button
                      type="button"
                      onClick={() => {
                        if (dayEvents.length > 0) {
                          setSelectedDayEvents({ date: dateStr, events: dayEvents });
                        }
                      }}
                      className={`text-xs font-mono font-bold hover:underline ${
                        isToday ? 'text-[#3F4634] px-1.5 py-0.5 bg-[#EFECE3] rounded-full' : 'text-[#6F6A61]'
                      }`}
                      title={dayEvents.length > 0 ? `View all ${dayEvents.length} events for ${dateStr}` : dateStr}
                    >
                      {dayNum}
                    </button>
                    {dayEvents.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setSelectedDayEvents({ date: dateStr, events: dayEvents })}
                        className="text-[10px] text-[#6F6A61] hover:text-[#242321] font-mono hover:underline"
                        title="View all events on this date"
                      >
                        {dayEvents.length} event{dayEvents.length > 1 ? 's' : ''}
                      </button>
                    )}
                  </div>

                  {/* Event Pills */}
                  <div className="space-y-1 overflow-y-auto max-h-[85px]">
                    {dayEvents.slice(0, 3).map((ev) => (
                      <button
                        key={ev.id}
                        onClick={() => setSelectedEvent(ev)}
                        className={`w-full text-left px-1.5 py-0.5 rounded-[2px] text-[10px] font-medium border truncate block transition-transform hover:scale-[1.02] ${getPriorityBadgeClass(
                          ev.priority
                        )}`}
                        title={ev.title}
                      >
                        {ev.priority === 'CRITICAL' && '⚠️ '}
                        {ev.title}
                      </button>
                    ))}
                    {dayEvents.length > 3 && (
                      <button
                        onClick={() => setSelectedDayEvents({ date: dateStr, events: dayEvents })}
                        className="text-[10px] text-[#3F4634] font-semibold hover:underline block text-left pl-1"
                        title="Click to view all events on this day"
                      >
                        +{dayEvents.length - 3} more
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 4. Agenda List View */}
      {viewMode === 'agenda' && (
        <div className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] p-4 divide-y divide-[#DED6C8]">
          <h2 className="text-sm font-serif font-bold text-[#242321] mb-3">
            Chronological Deadlines & Responsibilities
          </h2>
          {events.length === 0 ? (
            <div className="py-8 text-center text-xs text-[#6F6A61]">
              No upcoming events match the current filter criteria.
            </div>
          ) : (
            events.map((ev) => (
              <div
                key={ev.id}
                onClick={() => setSelectedEvent(ev)}
                className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-[#F7F3EA] px-2 rounded-[2px] cursor-pointer transition-colors"
              >
                <div className="flex items-start gap-3">
                  <div className="min-w-[85px] font-mono text-xs font-semibold text-[#242321] pt-0.5">
                    {ev.event_date}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-xs text-[#242321]">{ev.title}</span>
                      <span className={`text-[9px] px-1.5 py-0.2 border rounded-[2px] uppercase font-mono ${getPriorityBadgeClass(ev.priority)}`}>
                        {ev.priority}
                      </span>
                      <span className={`text-[9px] px-1.5 py-0.2 rounded-[2px] uppercase font-mono ${getStatusBadgeClass(ev.status)}`}>
                        {ev.status}
                      </span>
                    </div>
                    {ev.contract_title && (
                      <span className="text-[11px] text-[#6F6A61] block mt-0.5">
                        Contract: <strong>{ev.contract_title}</strong> {ev.counterparty ? `• ${ev.counterparty}` : ''}
                      </span>
                    )}
                  </div>
                </div>

                <div className="text-right sm:min-w-[120px]">
                  <span className="text-[10px] text-[#6F6A61] uppercase font-mono tracking-wider">
                    {ev.event_type.replace(/_/g, ' ')}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* 5. Event Detail Modal */}
      {selectedEvent && (
        <div className="fixed inset-0 bg-[#242321]/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] max-w-lg w-full p-6 space-y-4 shadow-xl">
            <div className="flex items-start justify-between border-b border-[#DED6C8] pb-3">
              <div>
                <span className={`text-[10px] px-2 py-0.5 border rounded-[2px] uppercase font-mono font-bold ${getPriorityBadgeClass(selectedEvent.priority)}`}>
                  {selectedEvent.priority} DEADLINE
                </span>
                <h2 className="text-base font-serif font-bold text-[#242321] mt-2">
                  {selectedEvent.title}
                </h2>
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                className="text-xs text-[#6F6A61] hover:text-[#242321] font-bold"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3 bg-[#F7F3EA] p-3 rounded-[2px] border border-[#DED6C8]">
                <div>
                  <span className="text-[10px] uppercase font-mono text-[#6F6A61] block">Target Date</span>
                  <span className="font-mono font-bold text-sm text-[#242321]">{selectedEvent.event_date}</span>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-mono text-[#6F6A61] block">Status</span>
                  <span className={`inline-block mt-0.5 text-[10px] px-2 py-0.5 rounded-[2px] font-mono ${getStatusBadgeClass(selectedEvent.status)}`}>
                    {selectedEvent.status}
                  </span>
                </div>
              </div>

              {selectedEvent.contract_title && (
                <div>
                  <span className="text-[10px] uppercase font-mono text-[#6F6A61] block">Associated Agreement</span>
                  <span className="text-xs font-semibold text-[#242321]">{selectedEvent.contract_title}</span>
                  {selectedEvent.counterparty && (
                    <span className="text-[11px] text-[#6F6A61] block">Counterparty: {selectedEvent.counterparty}</span>
                  )}
                </div>
              )}

              {selectedEvent.description && (
                <div>
                  <span className="text-[10px] uppercase font-mono text-[#6F6A61] block">Context / Obligation Details</span>
                  <p className="text-xs text-[#3A3835] leading-relaxed mt-0.5 bg-[#FCFAF5] p-2 border border-[#DED6C8] rounded-[2px]">
                    {selectedEvent.description}
                  </p>
                </div>
              )}

              <div className="flex items-center gap-2 pt-1">
                <span className="text-[10px] font-mono text-[#6F6A61]">Source Type:</span>
                <span className="text-[10px] font-mono font-medium text-[#242321]">{selectedEvent.source_type}</span>
                {selectedEvent.is_verified ? (
                  <span className="text-[10px] text-[#3F4634] font-medium font-mono">✓ Confirmed</span>
                ) : (
                  <span className="text-[10px] text-[#9A6A32] font-medium font-mono">⚠ Needs Verification</span>
                )}
              </div>
            </div>

            {/* Modal Actions */}
            <div className="pt-3 border-t border-[#DED6C8] flex items-center justify-between">
              <div className="flex items-center gap-2">
                {selectedEvent.status !== 'COMPLETED' && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleCompleteEvent(selectedEvent)}
                    className="text-xs border-[#3F4634] text-[#3F4634]"
                  >
                    Mark as Done
                  </Button>
                )}
                {selectedEvent.is_custom && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleDeleteEvent(selectedEvent)}
                    className="text-xs text-[#8B3F3F] border-[#F5C2C2] hover:bg-[#FDF2F2]"
                  >
                    Delete Event
                  </Button>
                )}
              </div>

              <div className="flex items-center gap-2">
                {selectedEvent.contract_id && onOpenContract && (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => {
                      onOpenContract(selectedEvent.contract_id!);
                      setSelectedEvent(null);
                    }}
                    className="text-xs"
                  >
                    Open Contract →
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 5b. All Day Events Modal for High-Density Dates */}
      {selectedDayEvents && (
        <div className="fixed inset-0 bg-[#242321]/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] max-w-xl w-full p-6 space-y-4 shadow-xl max-h-[85vh] flex flex-col">
            <div className="flex items-start justify-between border-b border-[#DED6C8] pb-3">
              <div>
                <h2 className="text-base font-serif font-bold text-[#242321]">
                  Schedule for {selectedDayEvents.date}
                </h2>
                <p className="text-xs text-[#6F6A61] mt-0.5">
                  Showing {selectedDayEvents.events.length} milestone{selectedDayEvents.events.length > 1 ? 's' : ''} and deadline{selectedDayEvents.events.length > 1 ? 's' : ''} scheduled on this day.
                </p>
              </div>
              <button
                onClick={() => setSelectedDayEvents(null)}
                className="text-xs text-[#6F6A61] hover:text-[#242321] font-bold p-1"
                aria-label="Close day events modal"
              >
                ✕
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              {selectedDayEvents.events.map((ev) => (
                <div
                  key={ev.id}
                  className="p-3 bg-[#F7F3EA] border border-[#DED6C8] hover:border-[#3F4634] rounded-[2px] transition-colors"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded-[2px] border ${getPriorityBadgeClass(ev.priority)}`}>
                          {ev.priority}
                        </span>
                        <span className="text-[10px] font-mono uppercase text-[#6F6A61]">
                          {ev.event_type.replace(/_/g, ' ')}
                        </span>
                        {ev.is_verified ? (
                          <span className="text-[10px] text-[#3F4634] font-mono font-medium">✓ Verified</span>
                        ) : (
                          <span className="text-[10px] text-[#9A6A32] font-mono font-medium">⚠ Needs Verification</span>
                        )}
                      </div>
                      <h3 className="text-xs font-bold text-[#242321]">{ev.title}</h3>
                      {ev.contract_title && (
                        <p className="text-[11px] text-[#6F6A61]">
                          Contract: <strong className="text-[#242321]">{ev.contract_title}</strong>
                        </p>
                      )}
                      {ev.description && (
                        <p className="text-[11px] text-[#6F6A61] line-clamp-2">{ev.description}</p>
                      )}
                    </div>
                    <div className="flex flex-col gap-1 items-end shrink-0">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setSelectedEvent(ev);
                          setSelectedDayEvents(null);
                        }}
                        className="text-[11px] py-0.5 px-2"
                      >
                        Details
                      </Button>
                      {ev.contract_id && onOpenContract && (
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => {
                            onOpenContract(ev.contract_id!);
                            setSelectedDayEvents(null);
                          }}
                          className="text-[11px] py-0.5 px-2"
                        >
                          Contract →
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="pt-3 border-t border-[#DED6C8] flex justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedDayEvents(null)}
                className="text-xs"
              >
                Close
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* 6. Add Custom Date Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 bg-[#242321]/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] max-w-md w-full p-6 space-y-4 shadow-xl">
            <div className="flex items-start justify-between border-b border-[#DED6C8] pb-3">
              <div>
                <h2 className="text-base font-serif font-bold text-[#242321]">
                  Add Custom Contract Date
                </h2>
                <p className="text-xs text-[#6F6A61] mt-0.5">
                  Record a custom legal cutoff, compliance date, or reminder milestone.
                </p>
              </div>
              <button
                onClick={() => setIsAddModalOpen(false)}
                className="text-xs text-[#6F6A61] hover:text-[#242321] font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateCustomEvent} className="space-y-3 text-xs">
              <div>
                <label className="block text-[11px] font-semibold uppercase font-mono text-[#242321] mb-1">
                  Event Title *
                </label>
                <input
                  type="text"
                  required
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. Counterparty Security Audit Due"
                  className="w-full bg-[#F7F3EA] border border-[#DED6C8] px-3 py-1.5 rounded-[2px] text-xs text-[#242321]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold uppercase font-mono text-[#242321] mb-1">
                    Event Date *
                  </label>
                  <input
                    type="date"
                    required
                    value={newDate}
                    onChange={(e) => setNewDate(e.target.value)}
                    className="w-full bg-[#F7F3EA] border border-[#DED6C8] px-3 py-1.5 rounded-[2px] text-xs text-[#242321]"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold uppercase font-mono text-[#242321] mb-1">
                    Category
                  </label>
                  <select
                    value={newType}
                    onChange={(e) => setNewType(e.target.value)}
                    className="w-full bg-[#F7F3EA] border border-[#DED6C8] px-2 py-1.5 rounded-[2px] text-xs text-[#242321]"
                  >
                    <option value="CUSTOM_DATE">Custom Date</option>
                    <option value="RENEWAL_NOTICE">Renewal Notice</option>
                    <option value="TERMINATION_NOTICE">Termination Notice</option>
                    <option value="PAYMENT_DEADLINE">Payment Deadline</option>
                    <option value="APPROVAL_DEADLINE">Approval Deadline</option>
                    <option value="SIGNATURE_DEADLINE">Signature Deadline</option>
                    <option value="OBLIGATION_DUE">Obligation Due</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold uppercase font-mono text-[#242321] mb-1">
                    Priority
                  </label>
                  <select
                    value={newPriority}
                    onChange={(e) => setNewPriority(e.target.value as any)}
                    className="w-full bg-[#F7F3EA] border border-[#DED6C8] px-2 py-1.5 rounded-[2px] text-xs text-[#242321]"
                  >
                    <option value="IMPORTANT">Important</option>
                    <option value="CRITICAL">Critical</option>
                    <option value="INFORMATIONAL">Informational</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] font-semibold uppercase font-mono text-[#242321] mb-1">
                    Linked Contract
                  </label>
                  <select
                    value={newContractId}
                    onChange={(e) => setNewContractId(e.target.value)}
                    className="w-full bg-[#F7F3EA] border border-[#DED6C8] px-2 py-1.5 rounded-[2px] text-xs text-[#242321] truncate"
                  >
                    <option value="">General / None</option>
                    {contracts.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.title}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold uppercase font-mono text-[#242321] mb-1">
                  Description / Instructions
                </label>
                <textarea
                  rows={3}
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  placeholder="Specify actionable notes, required deliverables, or context..."
                  className="w-full bg-[#F7F3EA] border border-[#DED6C8] p-2 rounded-[2px] text-xs text-[#242321]"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="mark-important"
                  checked={newIsImportant}
                  onChange={(e) => setNewIsImportant(e.target.checked)}
                  className="rounded text-[#3F4634]"
                />
                <label htmlFor="mark-important" className="text-xs text-[#242321] select-none">
                  Mark as Important (elevate in reminders)
                </label>
              </div>

              <div className="pt-3 border-t border-[#DED6C8] flex items-center justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setIsAddModalOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? 'Saving...' : 'Save Calendar Event'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
