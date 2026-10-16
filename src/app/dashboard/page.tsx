'use client';

import React, { useState, useEffect } from 'react';
import { useContractly } from '@/context/contractly-context';
import { TopBar } from '@/components/navigation/top-bar';
import { Sidebar } from '@/components/navigation/sidebar';
import { HomeView } from '@/components/home/home-view';
import { ContractTable } from '@/components/contracts/contract-table';
import { DocumentViewer } from '@/components/contracts/document-viewer';
import { RedlineStudio } from '@/components/contracts/redline-studio';
import { ContractWatch } from '@/components/contracts/contract-watch';
import { ApprovalFlow } from '@/components/contracts/approval-flow';
import { OverviewDashboard } from '@/components/overview/overview-dashboard';
import { VendorGrid } from '@/components/vendors/vendor-grid';
import { PlaybookView } from '@/components/playbook/playbook-view';
import { LawyerDirectory } from '@/components/lawyers/lawyer-directory';
import { AuditTrailView } from '@/components/audit/audit-trail-view';
import { RequestModal } from '@/components/contracts/request-modal';
import { AskContractlyModal } from '@/components/assistant/ask-contractly-modal';
import { CalendarView } from '@/components/calendar/calendar-view';
import { ThingsToDoView } from '@/components/tasks/things-to-do-view';
import { DataManagementView } from '@/components/data-management/data-management-view';
import { ProfileView } from '@/components/profile/profile-view';
import { ChatView } from '@/components/messages/chat-view';

export default function DashboardPage() {
  const [contractSubView, setContractSubView] = useState<'table' | 'document' | 'redline' | 'watch'>('table');
  const [isRequestModalOpen, setIsRequestModalOpen] = useState(false);
  const [isAskContractlyOpen, setIsAskContractlyOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const {
    currentUser,
    isAuthLoading,
    recheckAuth,
    activeNav,
    setActiveNav,
    setActiveContractId
  } = useContractly();

  useEffect(() => {
    if (!isAuthLoading && !currentUser) {
      window.location.replace('/signin?returnUrl=/dashboard');
      return;
    }

    // Revalidate on Back/Forward cache restore or tab refocus
    const handlePageShow = (e: PageTransitionEvent) => {
      if (e.persisted) {
        recheckAuth().then((u) => {
          if (!u) {
            window.location.replace('/signin?returnUrl=/dashboard');
          }
        });
      }
    };

    const handleFocus = () => {
      if (currentUser) {
        recheckAuth().then((u) => {
          if (!u) {
            window.location.replace('/signin?returnUrl=/dashboard');
          }
        });
      }
    };

    window.addEventListener('pageshow', handlePageShow);
    window.addEventListener('focus', handleFocus);
    return () => {
      window.removeEventListener('pageshow', handlePageShow);
      window.removeEventListener('focus', handleFocus);
    };
  }, [isAuthLoading, currentUser, recheckAuth]);

  // Loading gate: never flash protected contract content before session is verified
  if (isAuthLoading) {
    return (
      <div className="min-h-screen bg-[#F7F3EA] flex flex-col items-center justify-center p-6 text-center select-none">
        <div className="space-y-3">
          <span className="font-serif tracking-widest text-2xl font-bold text-[#242321] block">
            CONTRACTLY
          </span>
          <p className="text-xs font-mono text-[#6F6A61]">
            Authenticating workspace session...
          </p>
        </div>
      </div>
    );
  }

  // Fallback while redirecting unauthenticated visitor
  if (!currentUser) {
    return (
      <div className="min-h-screen bg-[#F7F3EA] flex flex-col items-center justify-center p-6 text-center select-none">
        <div className="space-y-3">
          <span className="font-serif tracking-widest text-2xl font-bold text-[#242321] block">
            CONTRACTLY
          </span>
          <p className="text-xs font-mono text-[#6F6A61]">
            Redirecting to sign-in...
          </p>
        </div>
      </div>
    );
  }

  const handleOpenContract = (id: string) => {
    setActiveContractId(id);
    setContractSubView('document');
    setActiveNav('contracts');
  };

  const renderMainContent = () => {
    // 1. Home View
    if (activeNav === 'home') {
      return (
        <HomeView
          onOpenContract={handleOpenContract}
          onRequestUpload={() => setIsRequestModalOpen(true)}
          onNavigate={(tab) => {
            setActiveNav(tab);
            setContractSubView('table');
          }}
        />
      );
    }

    // 2. Contracts View & Subviews (Document Viewer, Redline Studio, Contract Health)
    if (activeNav === 'contracts') {
      if (contractSubView === 'document') {
        return (
          <DocumentViewer
            onBack={() => setContractSubView('table')}
            onOpenRedline={() => setContractSubView('redline')}
            onOpenWatch={() => setContractSubView('watch')}
          />
        );
      }
      if (contractSubView === 'redline') {
        return <RedlineStudio onBack={() => setContractSubView('document')} />;
      }
      if (contractSubView === 'watch') {
        return (
          <ContractWatch
            onBack={() => setContractSubView('document')}
            onOpenDocument={handleOpenContract}
          />
        );
      }
      return (
        <ContractTable
          onOpenContract={handleOpenContract}
          onRequestNew={() => setIsRequestModalOpen(true)}
        />
      );
    }

    // 3. Overview Dashboard (for business users / managers)
    if (activeNav === 'overview' || activeNav === 'reports' || activeNav === 'analytics') {
      return (
        <OverviewDashboard
          onOpenContract={handleOpenContract}
          onRequestNew={() => setIsRequestModalOpen(true)}
          onNavigateTab={(tab) => {
            setActiveNav(tab);
            setContractSubView('table');
          }}
        />
      );
    }

    // 4. Edit & Compare (Redline Studio)
    if (activeNav === 'redlining') {
      return <RedlineStudio onBack={() => setContractSubView('table')} />;
    }

    // 5. Contract Calendar
    if (activeNav === 'calendar') {
      return (
        <CalendarView
          onOpenContract={handleOpenContract}
          onNavigateTab={(tab) => {
            setActiveNav(tab);
            setContractSubView('table');
          }}
        />
      );
    }

    // 6. Things You Need to Do (Responsibilities)
    if (activeNav === 'tasks' || activeNav === 'responsibilities') {
      return (
        <ThingsToDoView
          onOpenContract={handleOpenContract}
          onNavigateTab={(tab) => {
            setActiveNav(tab);
            setContractSubView('table');
          }}
        />
      );
    }

    // 7. Contract Health & Obligations Watch
    if (activeNav === 'watch' || activeNav === 'obligations' || activeNav === 'alerts') {
      return (
        <ContractWatch
          onBack={() => {
            setActiveNav('contracts');
            setContractSubView('table');
          }}
          onOpenDocument={handleOpenContract}
        />
      );
    }

    // 8. Requests Intake
    if (activeNav === 'requests') {
      return (
        <div className="space-y-4">
          <div className="p-6 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-center space-y-3">
            <h2 className="text-lg font-serif font-bold text-[#242321]">Upload or Request a Contract</h2>
            <p className="text-xs text-[#6F6A61] max-w-md mx-auto leading-relaxed">
              Upload a PDF, Word document, or text file to have Contractly identify key terms, highlight potential concerns, and schedule reminders.
            </p>
            <button
              onClick={() => setIsRequestModalOpen(true)}
              className="px-4 py-2 bg-[#3F4634] text-[#FCFAF5] rounded-[2px] text-xs font-semibold hover:bg-[#59604A] transition-colors"
            >
              + Upload Contract Now
            </button>
          </div>
          <ContractTable
            onOpenContract={handleOpenContract}
            onRequestNew={() => setIsRequestModalOpen(true)}
          />
        </div>
      );
    }

    // 9. Approvals
    if (activeNav === 'approvals') {
      return <ApprovalFlow />;
    }

    // 10. Vendors
    if (activeNav === 'vendors') {
      return <VendorGrid />;
    }

    // 11. Negotiation Rules (Legal Playbook)
    if (activeNav === 'playbook' || activeNav === 'clause-library') {
      return <PlaybookView />;
    }

    // 12. Get Legal Help (Lawyer Directory)
    if (activeNav === 'lawyers' || activeNav === 'consultations' || activeNav === 'help') {
      return <LawyerDirectory />;
    }

    // 12b. Matter Messages & Communications
    if (activeNav === 'messages') {
      return <ChatView />;
    }

    // 13. Activity History (Audit Trail)
    if (activeNav === 'audit') {
      return <AuditTrailView />;
    }

    // 14. Organization Data Management
    if (activeNav === 'data-management' || activeNav === 'workspace-data') {
      return <DataManagementView />;
    }

    // 15. User Profile & Account Settings
    if (activeNav === 'profile' || activeNav === 'account' || activeNav === 'settings') {
      return (
        <ProfileView
          onBack={() => {
            setActiveNav('home');
            setContractSubView('table');
          }}
        />
      );
    }

    // Default honest fallback
    return (
      <div className="p-8 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-center space-y-3">
        <h2 className="text-base font-serif font-bold text-[#242321] capitalize">
          {activeNav.replace(/-/g, ' ')}
        </h2>
        <p className="text-xs text-[#6F6A61] max-w-md mx-auto leading-relaxed">
          This section is not currently available. Please select an active operational view from the navigation menu.
        </p>
        <button
          onClick={() => {
            setActiveNav('home');
            setContractSubView('table');
          }}
          className="text-xs text-[#3F4634] hover:underline font-medium inline-block mt-2"
        >
          ← Return to Home
        </button>
      </div>
    );
  };

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
          <div className="max-w-7xl mx-auto">{renderMainContent()}</div>
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
