'use client';

import React, { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { verifyInvitationToken, acceptInvitation } from '@/lib/api-client';
import { Button } from '@/components/ui/button';

function AcceptInvitationContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get('token') || '';

  const [loading, setLoading] = useState(true);
  const [inviteData, setInviteData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [accepted, setAccepted] = useState(false);

  useEffect(() => {
    if (token) {
      loadInvitation(token);
    } else {
      setLoading(false);
      setError('No invitation token was provided.');
    }
  }, [token]);

  const loadInvitation = async (tok: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await verifyInvitationToken(tok);
      if (res.success && res.data) {
        setInviteData(res.data);
        if (!res.data.valid) {
          setError(`This invitation is ${res.data.status.toLowerCase()}. Please contact the administrator.`);
        }
      } else {
        setError(res.error || 'The invitation link is invalid or has expired.');
      }
    } catch {
      setError('Failed to load invitation details.');
    } finally {
      setLoading(false);
    }
  };

  const handleAccept = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;

    setIsSubmitting(true);
    setError(null);
    try {
      const res = await acceptInvitation(token, fullName || undefined, password || undefined);
      if (res.success) {
        setAccepted(true);
      } else {
        setError(res.error || 'Failed to accept invitation.');
      }
    } catch {
      setError('A network error occurred while accepting the invitation.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="w-full max-w-md bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] shadow-sm p-8 text-center">
        <p className="text-xs font-mono uppercase text-[#3F4634] animate-pulse">Loading invitation details...</p>
      </div>
    );
  }

  if (accepted) {
    return (
      <div className="w-full max-w-md bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] shadow-sm p-8">
        <div className="border-b border-[#DED6C8] pb-4 mb-6">
          <h1 className="text-xl font-serif font-bold text-[#242321]">Welcome to the Workspace</h1>
          <p className="text-xs text-[#6F6A61] mt-1">
            You have successfully joined {inviteData?.organization_name || 'the organization'}.
          </p>
        </div>
        <div className="p-3 bg-[#F2F6ED] border border-[#CDE0B8] text-[#3F4634] text-xs rounded-[2px] mb-6">
          <span className="font-bold">Active Member:</span> Your membership is established with role{' '}
          <span className="font-mono">{inviteData?.role || 'MEMBER'}</span>.
        </div>
        <Link href="/login">
          <Button variant="primary" size="md" className="w-full">
            Proceed to Sign In
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="w-full max-w-md bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] shadow-sm p-8">
      <div className="border-b border-[#DED6C8] pb-4 mb-6">
        <h1 className="text-xl font-serif font-bold text-[#242321]">Workspace Invitation</h1>
        <p className="text-xs text-[#6F6A61] mt-1">
          You have been invited to join <strong className="text-[#242321]">{inviteData?.organization_name || 'an organization'}</strong>.
        </p>
      </div>

      {error && (
        <div className="mb-5 p-3 bg-[#FDF2F2] border border-[#F5C2C2] text-[#8B3F3F] text-xs rounded-[2px] flex items-start gap-2">
          <span className="font-bold">Error:</span>
          <span>{error}</span>
        </div>
      )}

      {inviteData && inviteData.valid && (
        <form onSubmit={handleAccept} className="space-y-4">
          <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] text-xs space-y-1.5 font-mono">
            <div><span className="text-[#6F6A61]">Recipient:</span> {inviteData.invitee_email}</div>
            <div><span className="text-[#6F6A61]">Assigned Role:</span> {inviteData.role}</div>
            <div><span className="text-[#6F6A61]">Organization:</span> {inviteData.organization_name}</div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-[#242321] mb-1.5">
              Full Name (Optional)
            </label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Your full name"
              className="w-full bg-[#FCFAF5] border border-[#DED6C8] text-sm text-[#242321] px-3 py-2 rounded-[2px] focus:outline-none focus:border-[#3F4634]"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-[#242321] mb-1.5">
              Account Password (If new account)
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              minLength={8}
              className="w-full bg-[#FCFAF5] border border-[#DED6C8] text-sm text-[#242321] px-3 py-2 rounded-[2px] focus:outline-none focus:border-[#3F4634]"
            />
            <span className="text-[11px] text-[#6F6A61] mt-1 block">
              Required if you do not already possess a Contractly account.
            </span>
          </div>

          <div className="pt-2">
            <Button
              type="submit"
              variant="primary"
              size="md"
              disabled={isSubmitting}
              className="w-full"
            >
              {isSubmitting ? 'Joining Organization...' : 'Accept Invitation & Join'}
            </Button>
          </div>
        </form>
      )}

      {!inviteData?.valid && error && (
        <div className="pt-2">
          <Link href="/login">
            <Button variant="outline" size="md" className="w-full">
              Return to Sign In
            </Button>
          </Link>
        </div>
      )}
    </div>
  );
}

export default function AcceptInvitationPage() {
  return (
    <div className="min-h-screen bg-[#F7F3EA] flex flex-col justify-center items-center p-4">
      <div className="mb-8 text-center">
        <span className="font-serif tracking-widest text-2xl font-bold text-[#242321] block">
          CONTRACTLY
        </span>
        <span className="text-xs uppercase font-mono tracking-wider text-[#6F6A61] mt-1 block">
          Enterprise Workspace Onboarding
        </span>
      </div>

      <Suspense fallback={<div className="text-xs text-[#6F6A61]">Loading invitation...</div>}>
        <AcceptInvitationContent />
      </Suspense>
    </div>
  );
}
