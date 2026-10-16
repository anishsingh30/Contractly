'use client';

import React, { useState, useEffect } from 'react';
import { useContractly } from '@/context/contractly-context';
import {
  NotificationPreferences,
  fetchNotificationPreferences,
  updateNotificationPreferences,
  sendTestNotificationEmail
} from '@/lib/api-client';
import { Button } from '@/components/ui/button';

interface NotificationPreferencesModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function NotificationPreferencesModal({ isOpen, onClose }: NotificationPreferencesModalProps) {
  const { addToast } = useContractly();

  const [prefs, setPrefs] = useState<NotificationPreferences | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTestingEmail, setIsTestingEmail] = useState(false);

  // Form State
  const [emailEnabled, setEmailEnabled] = useState(false);
  const [renewalReminders, setRenewalReminders] = useState(true);
  const [noticeReminders, setNoticeReminders] = useState(true);
  const [obligationReminders, setObligationReminders] = useState(true);
  const [approvalReminders, setApprovalReminders] = useState(true);
  const [criticalEnabled, setCriticalEnabled] = useState(true);
  const [dailyLimit, setDailyLimit] = useState<number | ''>(10);
  const [quietHoursEnabled, setQuietHoursEnabled] = useState(false);
  const [quietHoursStart, setQuietHoursStart] = useState('22:00');
  const [quietHoursEnd, setQuietHoursEnd] = useState('08:00');
  const [preferredEmail, setPreferredEmail] = useState('');

  useEffect(() => {
    if (isOpen) {
      loadPreferences();
    }
  }, [isOpen]);

  const loadPreferences = async () => {
    setIsLoading(true);
    try {
      const data = await fetchNotificationPreferences();
      if (data) {
        setPrefs(data);
        setEmailEnabled(data.email_notifications_enabled);
        setRenewalReminders(data.renewal_reminders);
        setNoticeReminders(data.notice_deadline_reminders);
        setObligationReminders(data.obligation_reminders);
        setApprovalReminders(data.approval_reminders);
        setCriticalEnabled(data.critical_events_enabled);
        setDailyLimit(data.daily_notification_limit);
        setQuietHoursEnabled(data.quiet_hours_enabled);
        setQuietHoursStart(data.quiet_hours_start);
        setQuietHoursEnd(data.quiet_hours_end);
        setPreferredEmail(data.preferred_notification_email || '');
      }
    } catch (err) {
      console.error('Failed to load preferences:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      const res = await updateNotificationPreferences({
        email_notifications_enabled: emailEnabled,
        renewal_reminders: renewalReminders,
        notice_deadline_reminders: noticeReminders,
        obligation_reminders: obligationReminders,
        approval_reminders: approvalReminders,
        critical_events_enabled: criticalEnabled,
        daily_notification_limit: typeof dailyLimit === 'number' ? dailyLimit : 10,
        quiet_hours_enabled: quietHoursEnabled,
        quiet_hours_start: quietHoursStart,
        quiet_hours_end: quietHoursEnd,
        preferred_notification_email: preferredEmail.trim() ? preferredEmail.trim() : null
      });
      if (res) {
        setPrefs(res);
        addToast('Settings Saved', 'Your notification preferences have been updated.', 'success');
        onClose();
      } else {
        addToast('Error', 'Failed to update preferences.', 'danger');
      }
    } catch (err: any) {
      addToast('Error', err?.message || 'An error occurred while saving.', 'danger');
    } finally {
      setIsSaving(false);
    }
  };

  const handleTestEmail = async () => {
    setIsTestingEmail(true);
    try {
      const res = await sendTestNotificationEmail(preferredEmail.trim() || undefined);
      if (res.success) {
        addToast('Verification Notification Sent', res.message, 'success');
      } else {
        addToast('Email Dispatch Result', res.message, 'warning');
      }
    } catch (err: any) {
      addToast('Error', err.message || 'Failed to trigger verification notification.', 'danger');
    } finally {
      setIsTestingEmail(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-[#242321]/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] max-w-xl w-full p-6 space-y-4 shadow-xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-start justify-between border-b border-[#DED6C8] pb-3">
          <div>
            <h2 className="text-base font-serif font-bold text-[#242321]">
              Notification & Alert Settings
            </h2>
            <p className="text-xs text-[#6F6A61] mt-0.5">
              Control when Contractly notifies you. Informational events remain in-app; critical deadlines trigger emails when enabled.
            </p>
          </div>
          <button onClick={onClose} className="text-xs text-[#6F6A61] hover:text-[#242321] font-bold">
            ✕
          </button>
        </div>

        {isLoading ? (
          <div className="py-8 text-center text-xs text-[#6F6A61]">Loading preferences...</div>
        ) : (
          <form onSubmit={handleSave} className="space-y-4 text-xs">
            {/* Server Email Transport Status Banner */}
            {prefs && (
              <div
                className={`p-2.5 rounded-[2px] border flex items-center justify-between text-[11px] ${
                  prefs.email_service_enabled
                    ? 'bg-[#F2F5EF] border-[#A6B296] text-[#3F4634]'
                    : 'bg-[#FAF6EE] border-[#DED6C8] text-[#6F6A61]'
                }`}
              >
                <div>
                  <span className="font-semibold text-[#242321] block">
                    Backend Transport:{' '}
                    <span className={prefs.email_service_enabled ? 'text-[#3F4634]' : 'text-[#8B3F3F]'}>
                      {prefs.email_service_enabled ? 'Available' : 'Disabled'}
                    </span>
                  </span>
                  <span className="text-[10px]">
                    {prefs.email_service_enabled
                      ? `Provider: ${prefs.email_provider_status}`
                      : 'Outbound emails disabled via EMAIL_ENABLED=false in backend environment. In-app alerts remain active.'}
                  </span>
                </div>
                <span
                  className={`font-mono text-[9px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wider ${
                    prefs.email_service_enabled
                      ? 'bg-[#3F4634] text-[#FCFAF5]'
                      : 'bg-[#EFECE3] text-[#6F6A61] border border-[#DED6C8]'
                  }`}
                >
                  {prefs.email_service_enabled ? 'Active' : 'Disabled'}
                </span>
              </div>
            )}

            {/* 1. Global Email Delivery Toggle */}
            <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] flex items-center justify-between">
              <div>
                <span className="font-semibold text-xs text-[#242321] block">
                  Email Notifications
                </span>
                <span className="text-[11px] text-[#6F6A61]">
                  Receive high-priority and critical contract alerts in your inbox.
                </span>
              </div>
              <input
                type="checkbox"
                checked={emailEnabled}
                onChange={(e) => setEmailEnabled(e.target.checked)}
                className="w-4 h-4 rounded text-[#3F4634]"
              />
            </div>

            {/* Preferred Email Input */}
            <div>
              <label className="block text-[11px] font-mono uppercase text-[#6F6A61] mb-1">
                Preferred Notification Email
              </label>
              <input
                type="email"
                value={preferredEmail}
                onChange={(e) => setPreferredEmail(e.target.value)}
                placeholder="defaults to your account login email"
                className="w-full bg-[#FCFAF5] border border-[#DED6C8] px-3 py-1.5 rounded-[2px] text-xs text-[#242321]"
              />
            </div>

            {/* 2. Notification Category Toggles */}
            <div className="space-y-2 border-t border-[#DED6C8] pt-3">
              <span className="font-serif font-bold text-xs text-[#242321] block">
                Category Preferences
              </span>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                <label className="flex items-center gap-2 p-2 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={renewalReminders}
                    onChange={(e) => setRenewalReminders(e.target.checked)}
                    className="rounded text-[#3F4634]"
                  />
                  <span>Renewal Reminders (30d, 7d)</span>
                </label>

                <label className="flex items-center gap-2 p-2 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={noticeReminders}
                    onChange={(e) => setNoticeReminders(e.target.checked)}
                    className="rounded text-[#3F4634]"
                  />
                  <span>Notice Deadline Reminders</span>
                </label>

                <label className="flex items-center gap-2 p-2 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={obligationReminders}
                    onChange={(e) => setObligationReminders(e.target.checked)}
                    className="rounded text-[#3F4634]"
                  />
                  <span>Obligation & Compliance Alerts</span>
                </label>

                <label className="flex items-center gap-2 p-2 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={approvalReminders}
                    onChange={(e) => setApprovalReminders(e.target.checked)}
                    className="rounded text-[#3F4634]"
                  />
                  <span>Approval & Signature Gates</span>
                </label>
              </div>
            </div>

            {/* 3. Delivery Guardrails & Rate Limits */}
            <div className="space-y-3 border-t border-[#DED6C8] pt-3">
              <span className="font-serif font-bold text-xs text-[#242321] block">
                Delivery Controls & Guardrails
              </span>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-mono uppercase text-[#6F6A61] mb-1">
                    Daily Email Limit
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={dailyLimit}
                    onChange={(e) => {
                      const val = e.target.value;
                      if (val === '') {
                        setDailyLimit('');
                      } else {
                        const parsed = parseInt(val, 10);
                        if (!isNaN(parsed)) {
                          setDailyLimit(parsed);
                        }
                      }
                    }}
                    onBlur={() => {
                      if (dailyLimit === '' || dailyLimit < 1) {
                        setDailyLimit(1);
                      } else if (dailyLimit > 100) {
                        setDailyLimit(100);
                      }
                    }}
                    className="w-full bg-[#FCFAF5] border border-[#DED6C8] px-2 py-1 rounded-[2px] text-xs text-[#242321]"
                  />
                </div>

                <div className="pt-5">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={quietHoursEnabled}
                      onChange={(e) => setQuietHoursEnabled(e.target.checked)}
                      className="rounded text-[#3F4634]"
                    />
                    <span>Enable Quiet Hours</span>
                  </label>
                </div>
              </div>

              {quietHoursEnabled && (
                <div className="grid grid-cols-2 gap-3 bg-[#F7F3EA] p-2.5 rounded-[2px] border border-[#DED6C8]">
                  <div>
                    <label className="block text-[10px] font-mono text-[#6F6A61] mb-1">Start Time</label>
                    <input
                      type="time"
                      value={quietHoursStart}
                      onChange={(e) => setQuietHoursStart(e.target.value)}
                      className="w-full bg-[#FCFAF5] border border-[#DED6C8] px-2 py-0.5 rounded-[2px] text-xs"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-mono text-[#6F6A61] mb-1">End Time</label>
                    <input
                      type="time"
                      value={quietHoursEnd}
                      onChange={(e) => setQuietHoursEnd(e.target.value)}
                      className="w-full bg-[#FCFAF5] border border-[#DED6C8] px-2 py-0.5 rounded-[2px] text-xs"
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Test Email Section */}
            <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] flex items-center justify-between">
              <div>
                <span className="font-semibold text-xs text-[#242321] block">Transport Check</span>
                <span className="text-[11px] text-[#6F6A61]">
                  Verify whether backend email delivery is operational.
                </span>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleTestEmail}
                disabled={isTestingEmail}
                className="text-xs"
              >
                {isTestingEmail ? 'Sending...' : 'Send Verification Notification'}
              </Button>
            </div>

            {/* Modal Actions */}
            <div className="pt-3 border-t border-[#DED6C8] flex items-center justify-end gap-2">
              <Button type="button" variant="outline" size="sm" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" size="sm" disabled={isSaving}>
                {isSaving ? 'Saving...' : 'Save Preferences'}
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
