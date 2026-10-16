'use client';

import React, { useEffect } from 'react';
import { useContractly } from '@/context/contractly-context';
import { TopBar } from '@/components/navigation/top-bar';
import { Sidebar } from '@/components/navigation/sidebar';
import { ProfileView } from '@/components/profile/profile-view';
import { RequestModal } from '@/components/contracts/request-modal';
import { AskContractlyModal } from '@/components/assistant/ask-contractly-modal';

export default function ProfilePage() {
  const { currentUser, isAuthLoading } = useContractly();
  const [isRequestModalOpen, setIsRequestModalOpen] = React.useState(false);
  const [isAskContractlyOpen, setIsAskContractlyOpen] = React.useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = React.useState(false);

  useEffect(() => {
    if (!isAuthLoading && !currentUser) {
      window.location.replace('/signin?returnUrl=/profile');
    }
  }, [isAuthLoading, currentUser]);

  if (isAuthLoading) {
    return (
      <div className="min-h-screen bg-[#F7F3EA] flex flex-col items-center justify-center p-6 text-center select-none">
        <div className="space-y-3">
          <span className="font-serif tracking-widest text-2xl font-bold text-[#242321] block">
            CONTRACTLY
          </span>
          <p className="text-xs font-mono text-[#6F6A61] tracking-wider animate-pulse">
            Verifying authenticated credentials...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen h-dvh max-h-screen flex flex-col overflow-hidden bg-[#F7F3EA]">
      <TopBar
        onRequestUpload={() => setIsRequestModalOpen(true)}
        onOpenAskContractly={() => setIsAskContractlyOpen(true)}
        onToggleMobileMenu={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
        isMobileMenuOpen={isMobileMenuOpen}
      />

      <div className="flex-1 flex min-h-0 overflow-hidden">
        <Sidebar
          isOpen={isMobileMenuOpen}
          onClose={() => setIsMobileMenuOpen(false)}
        />
        <main
          id="main-content"
          className="flex-1 min-h-0 min-w-0 overflow-y-auto overflow-x-hidden p-4 md:p-6 lg:p-8 pb-16 md:pb-24"
        >
          <ProfileView />
        </main>
      </div>

      <RequestModal
        isOpen={isRequestModalOpen}
        onClose={() => setIsRequestModalOpen(false)}
      />

      <AskContractlyModal
        isOpen={isAskContractlyOpen}
        onClose={() => setIsAskContractlyOpen(false)}
      />
    </div>
  );
}
