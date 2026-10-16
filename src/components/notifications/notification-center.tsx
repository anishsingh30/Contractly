'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Bell, AlertTriangle } from 'lucide-react';
import { useContractly } from '@/context/contractly-context';
import {
  NotificationItem,
  fetchNotifications,
  markNotificationAsRead,
  markAllNotificationsAsRead
} from '@/lib/api-client';

interface NotificationCenterProps {
  onOpenContract?: (contractId: string) => void;
  onOpenConversation?: (contractId?: string | null) => void;
  onOpenPreferences?: () => void;
}

export function NotificationCenter({ onOpenContract, onOpenConversation, onOpenPreferences }: NotificationCenterProps) {
  const { unreadNotificationsCount, notificationsLoadError, refreshNotifications } = useContractly();
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [listError, setListError] = useState<boolean>(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const loadNotifications = async () => {
    setIsLoading(true);
    setListError(false);
    try {
      const res = await fetchNotifications({ limit: 20 });
      setNotifications(res.items);
    } catch (err) {
      console.error('Failed to load notifications list:', err);
      setListError(true);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadNotifications();
    }
  }, [isOpen]);

  // Click outside to close dropdown
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const handleMarkAsRead = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const ok = await markNotificationAsRead(id);
    if (ok) {
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      await refreshNotifications();
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new Event('refresh-notifications'));
      }
    }
  };

  const handleMarkAllAsRead = async () => {
    const ok = await markAllNotificationsAsRead();
    if (ok) {
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      await refreshNotifications();
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new Event('refresh-notifications'));
      }
    }
  };

  const getPriorityStyle = (priority: string) => {
    if (priority === 'CRITICAL') return 'bg-[#FDF2F2] text-[#8B3F3F] border-[#F5C2C2]';
    if (priority === 'IMPORTANT') return 'bg-[#FEF9EE] text-[#9A6A32] border-[#F7E5C1]';
    return 'bg-[#F7F3EA] text-[#6F6A61] border-[#DED6C8]';
  };

  const displayCount = unreadNotificationsCount;

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell Button (40x40px touch target) */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative w-10 h-10 min-w-[40px] min-h-[40px] rounded-[2px] text-[#6F6A61] hover:text-[#242321] hover:bg-[#F7F3EA] border border-[#DED6C8] hover:border-[#3F4634] transition-colors flex items-center justify-center focus:outline-none focus:ring-2 focus:ring-[#3F4634]"
        title={notificationsLoadError ? "Notifications (connection warning)" : "Notification Center"}
        aria-label="Notification Center"
      >
        <Bell className="w-4 h-4 text-[#3F4634]" />
        {displayCount > 0 && (
          <span className="absolute top-1 right-1 px-1.5 py-0.2 bg-[#8B3F3F] text-[#FCFAF5] font-mono text-[9px] font-bold rounded-full">
            {displayCount > 9 ? '9+' : displayCount}
          </span>
        )}
        {displayCount === 0 && notificationsLoadError && (
          <span className="absolute top-1 right-1 w-2 h-2 bg-[#9A6A32] rounded-full" title="Notification sync alert" />
        )}
      </button>

      {/* Popover Dropdown */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 sm:w-96 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] shadow-xl z-50 text-xs overflow-hidden">
          {/* Popover Header */}
          <div className="p-3 border-b border-[#DED6C8] flex items-center justify-between bg-[#F7F3EA]">
            <div className="flex items-center gap-2">
              <span className="font-serif font-bold text-xs text-[#242321]">Notifications</span>
              {displayCount > 0 && (
                <span className="text-[10px] px-1.5 py-0.2 bg-[#EFECE3] border border-[#DED6C8] rounded-[2px] font-mono font-bold text-[#3F4634]">
                  {displayCount} unread
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {displayCount > 0 && (
                <button
                  onClick={handleMarkAllAsRead}
                  className="text-[11px] text-[#3F4634] hover:underline font-medium"
                >
                  Mark all read
                </button>
              )}
              {onOpenPreferences && (
                <button
                  onClick={() => {
                    setIsOpen(false);
                    onOpenPreferences();
                  }}
                  className="h-8 px-2.5 flex items-center gap-1.5 text-xs font-medium text-[#242321] bg-[#FCFAF5] hover:bg-[#EFECE3] border border-[#DED6C8] hover:border-[#3F4634] rounded-[2px] transition-colors focus:outline-none focus:ring-2 focus:ring-[#3F4634]"
                  title="Notification settings"
                  aria-label="Notification settings"
                >
                  <svg className="w-3.5 h-3.5 text-[#3F4634]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <span>Settings</span>
                </button>
              )}
            </div>
          </div>

          {/* Notification Items List */}
          <div className="max-h-80 overflow-y-auto divide-y divide-[#DED6C8]">
            {isLoading ? (
              <div className="p-6 text-center text-xs text-[#6F6A61]">Loading notifications...</div>
            ) : listError || (notificationsLoadError && notifications.length === 0) ? (
              <div className="p-6 text-center text-xs text-[#8B3F3F] bg-[#FDF2F2] flex flex-col items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-[#8B3F3F]" />
                <span>Unable to load notifications. Please check your workspace connection.</span>
                <button
                  onClick={() => loadNotifications()}
                  className="px-2.5 py-1 text-[11px] bg-[#FCFAF5] border border-[#DED6C8] hover:border-[#3F4634] rounded-[2px] text-[#242321]"
                >
                  Retry
                </button>
              </div>
            ) : notifications.length === 0 ? (
              <div className="p-6 text-center text-xs text-[#6F6A61]">
                No notifications recorded yet.
              </div>
            ) : (
              notifications.map((n) => (
                <div
                  key={n.id}
                  onClick={async () => {
                    if (!n.is_read) {
                      markNotificationAsRead(n.id);
                      setNotifications((prev) =>
                        prev.map((item) => (item.id === n.id ? { ...item, is_read: true } : item))
                      );
                      await refreshNotifications();
                      if (typeof window !== 'undefined') {
                        window.dispatchEvent(new Event('refresh-notifications'));
                      }
                    }
                    if (n.event_type === 'MATTER_MESSAGE_RECEIVED') {
                      if (onOpenConversation) {
                        onOpenConversation(n.contract_id);
                      } else if (n.contract_id && onOpenContract) {
                        onOpenContract(n.contract_id);
                      }
                      setIsOpen(false);
                    } else if (n.contract_id && onOpenContract) {
                      onOpenContract(n.contract_id);
                      setIsOpen(false);
                    }
                  }}

                  className={`p-3 space-y-1 transition-colors cursor-pointer hover:bg-[#F7F3EA] ${
                    !n.is_read ? 'bg-[#FCFAF5] font-medium' : 'bg-[#F7F3EA]/30 text-[#6F6A61]'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-1.5">
                      <span className={`text-[9px] font-mono font-bold px-1.5 py-0.2 border rounded-[2px] uppercase ${getPriorityStyle(n.priority)}`}>
                        {n.priority}
                      </span>
                      <span className="font-semibold text-xs text-[#242321]">{n.title}</span>
                    </div>

                    {!n.is_read && (
                      <button
                        onClick={(e) => handleMarkAsRead(n.id, e)}
                        className="text-[10px] text-[#3F4634] hover:underline shrink-0"
                        title="Mark as read"
                      >
                        ✓
                      </button>
                    )}
                  </div>

                  <p className="text-[11px] text-[#3A3835] leading-relaxed line-clamp-2">
                    {n.message}
                  </p>

                  <div className="flex items-center justify-between text-[10px] text-[#6F6A61] pt-0.5">
                    <span className="font-mono">
                      {n.sent_at ? n.sent_at.substring(0, 16).replace('T', ' ') : 'Scheduled'}
                    </span>
                    <span className="uppercase font-mono text-[9px]">
                      {n.delivery_channel}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
