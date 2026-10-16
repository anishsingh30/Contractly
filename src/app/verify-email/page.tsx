'use client';

import React, { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { verifyEmail, resendVerification } from '@/lib/api-client';
import { Button } from '@/components/ui/button';

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get('token') || '';

  const [status, setStatus] = useState<'IDLE' | 'VERIFYING' | 'SUCCESS' | 'ERROR'>('IDLE');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [resendEmail, setResendEmail] = useState('');
  const [resendStatus, setResendStatus] = useState<string | null>(null);
  const [isResending, setIsResending] = useState(false);

  useEffect(() => {
    if (token) {
      handleVerification(token);
    }
  }, [token]);

  const handleVerification = async (tok: string) => {
    setStatus('VERIFYING');
    setErrorMessage(null);
    try {
      const res = await verifyEmail(tok);
      if (res.success) {
        setStatus('SUCCESS');
      } else {
        setStatus('ERROR');
        setErrorMessage(res.error || 'The verification link is invalid or has expired.');
      }
    } catch {
      setStatus('ERROR');
      setErrorMessage('A network error occurred while verifying your email address.');
    }
  };

  const handleResend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resendEmail) return;

    setIsResending(true);
    setResendStatus(null);
    try {
      const res = await resendVerification(resendEmail);
      if (res.success) {
        setResendStatus(res.message);
      } else {
        setResendStatus(res.error || 'Could not dispatch verification email.');
      }
    } catch {
      setResendStatus('Failed to resend verification email.');
    } finally {
      setIsResending(false);
    }
  };

  return (
    <div className="w-full max-w-md bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] shadow-sm p-8">
      <div className="border-b border-[#DED6C8] pb-4 mb-6">
        <h1 className="text-xl font-serif font-bold text-[#242321]">Email Verification</h1>
        <p className="text-xs text-[#6F6A61] mt-1">
          Confirm your account email address to protect workspace communications.
        </p>
      </div>

      {status === 'VERIFYING' && (
        <div className="text-center py-6">
          <div className="text-xs font-mono uppercase text-[#3F4634] mb-2 animate-pulse">
            Verifying Token...
          </div>
          <p className="text-xs text-[#6F6A61]">Please wait while we confirm your email address.</p>
        </div>
      )}

      {status === 'SUCCESS' && (
        <div className="space-y-4">
          <div className="p-3 bg-[#F2F6ED] border border-[#CDE0B8] text-[#3F4634] text-xs rounded-[2px] flex items-start gap-2">
            <span className="font-bold">Verified:</span>
            <span>Your email address has been successfully confirmed.</span>
          </div>
          <p className="text-xs text-[#6F6A61]">
            Your account verification status is now updated. You can proceed to access your workspace.
          </p>
          <div className="pt-2">
            <Link href="/login">
              <Button variant="primary" size="md" className="w-full">
                Proceed to Sign In
              </Button>
            </Link>
          </div>
        </div>
      )}

      {status === 'ERROR' && (
        <div className="space-y-5">
          <div className="p-3 bg-[#FDF2F2] border border-[#F5C2C2] text-[#8B3F3F] text-xs rounded-[2px] flex items-start gap-2">
            <span className="font-bold">Verification Failed:</span>
            <span>{errorMessage}</span>
          </div>

          <div className="border-t border-[#DED6C8] pt-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#242321] mb-2">
              Request a New Verification Link
            </h2>
            <form onSubmit={handleResend} className="space-y-3">
              <input
                type="email"
                value={resendEmail}
                onChange={(e) => setResendEmail(e.target.value)}
                placeholder="counsel@company.internal"
                required
                className="w-full bg-[#FCFAF5] border border-[#DED6C8] text-sm text-[#242321] px-3 py-2 rounded-[2px] focus:outline-none focus:border-[#3F4634]"
              />
              <Button
                type="submit"
                variant="outline"
                size="sm"
                disabled={isResending}
                className="w-full"
              >
                {isResending ? 'Sending...' : 'Resend Verification Link'}
              </Button>
            </form>
            {resendStatus && (
              <p className="text-xs text-[#3F4634] mt-2 font-mono">{resendStatus}</p>
            )}
          </div>
        </div>
      )}

      {status === 'IDLE' && !token && (
        <div className="space-y-5">
          <p className="text-xs text-[#6F6A61]">
            No verification token was detected in your URL. If you need a verification link sent, enter your work email below:
          </p>
          <form onSubmit={handleResend} className="space-y-3">
            <input
              type="email"
              value={resendEmail}
              onChange={(e) => setResendEmail(e.target.value)}
              placeholder="counsel@company.internal"
              required
              className="w-full bg-[#FCFAF5] border border-[#DED6C8] text-sm text-[#242321] px-3 py-2 rounded-[2px] focus:outline-none focus:border-[#3F4634]"
            />
            <Button
              type="submit"
              variant="primary"
              size="md"
              disabled={isResending}
              className="w-full"
            >
              {isResending ? 'Sending...' : 'Send Verification Email'}
            </Button>
          </form>
          {resendStatus && (
            <p className="text-xs text-[#3F4634] font-mono">{resendStatus}</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <div className="min-h-screen bg-[#F7F3EA] flex flex-col justify-center items-center p-4">
      <div className="mb-8 text-center">
        <span className="font-serif tracking-widest text-2xl font-bold text-[#242321] block">
          CONTRACTLY
        </span>
        <span className="text-xs uppercase font-mono tracking-wider text-[#6F6A61] mt-1 block">
          Identity & Account Security
        </span>
      </div>

      <Suspense fallback={<div className="text-xs text-[#6F6A61]">Loading verification token...</div>}>
        <VerifyEmailContent />
      </Suspense>
    </div>
  );
}
