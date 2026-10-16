'use client';

import React, { useState, Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { resetPassword } from '@/lib/api-client';
import { Button } from '@/components/ui/button';

function ResetPasswordContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get('token') || '';

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);

    if (!token) {
      setError('Missing reset token. Please request a new password reset link.');
      return;
    }

    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match. Please re-enter.');
      return;
    }

    setIsLoading(true);
    try {
      const res = await resetPassword(token, newPassword);
      if (res.success) {
        setSuccessMessage(res.message);
      } else {
        setError(res.error || 'Failed to reset password. The link may have expired.');
      }
    } catch {
      setError('An unexpected error occurred. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="w-full max-w-md bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] shadow-sm p-8 text-center">
        <h1 className="text-xl font-serif font-bold text-[#242321] mb-2">Invalid Reset Link</h1>
        <p className="text-xs text-[#6F6A61] mb-6">
          No password reset token was provided in the URL. Please request a new reset link.
        </p>
        <Link href="/forgot-password">
          <Button variant="primary" size="md" className="w-full">
            Request Password Reset
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="w-full max-w-md bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] shadow-sm p-8">
      <div className="border-b border-[#DED6C8] pb-4 mb-6">
        <h1 className="text-xl font-serif font-bold text-[#242321]">Set New Password</h1>
        <p className="text-xs text-[#6F6A61] mt-1">
          Choose a secure password for your Contractly account.
        </p>
      </div>

      {error && (
        <div className="mb-5 p-3 bg-[#FDF2F2] border border-[#F5C2C2] text-[#8B3F3F] text-xs rounded-[2px] flex items-start gap-2">
          <span className="font-bold">Error:</span>
          <span>{error}</span>
        </div>
      )}

      {successMessage ? (
        <div className="space-y-4">
          <div className="p-3 bg-[#F2F6ED] border border-[#CDE0B8] text-[#3F4634] text-xs rounded-[2px] flex items-start gap-2">
            <span className="font-bold">Success:</span>
            <span>{successMessage}</span>
          </div>
          <p className="text-xs text-[#6F6A61]">
            All previous active sessions have been revoked for your security. Please sign in with your new credentials.
          </p>
          <div className="pt-2">
            <Link href="/login">
              <Button variant="primary" size="md" className="w-full">
                Sign In to Account
              </Button>
            </Link>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-[#242321] mb-1.5">
              New Password
            </label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="••••••••••••"
              required
              minLength={8}
              className="w-full bg-[#FCFAF5] border border-[#DED6C8] text-sm text-[#242321] px-3 py-2 rounded-[2px] focus:outline-none focus:border-[#3F4634] transition-colors"
            />
            <span className="text-[11px] text-[#6F6A61] mt-1 block">
              Must contain at least 8 characters, with letters and numbers.
            </span>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-[#242321] mb-1.5">
              Confirm Password
            </label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="••••••••••••"
              required
              minLength={8}
              className="w-full bg-[#FCFAF5] border border-[#DED6C8] text-sm text-[#242321] px-3 py-2 rounded-[2px] focus:outline-none focus:border-[#3F4634] transition-colors"
            />
          </div>

          <div className="pt-2">
            <Button
              type="submit"
              variant="primary"
              size="md"
              disabled={isLoading}
              className="w-full"
            >
              {isLoading ? 'Updating Password...' : 'Save New Password'}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="min-h-screen bg-[#F7F3EA] flex flex-col justify-center items-center p-4">
      {/* Brand Header */}
      <div className="mb-8 text-center">
        <span className="font-serif tracking-widest text-2xl font-bold text-[#242321] block">
          CONTRACTLY
        </span>
        <span className="text-xs uppercase font-mono tracking-wider text-[#6F6A61] mt-1 block">
          Credential Security
        </span>
      </div>

      <Suspense fallback={<div className="text-xs text-[#6F6A61]">Loading verification token...</div>}>
        <ResetPasswordContent />
      </Suspense>
    </div>
  );
}
