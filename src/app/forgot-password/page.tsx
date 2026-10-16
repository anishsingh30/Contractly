'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { forgotPassword } from '@/lib/api-client';
import { Button } from '@/components/ui/button';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage(null);
    setError(null);

    if (!email) {
      setError('Please provide your work email address.');
      return;
    }

    setIsLoading(true);
    try {
      const res = await forgotPassword(email);
      if (res.success) {
        setMessage(res.message);
      } else {
        setError(res.error || 'Failed to submit password reset request.');
      }
    } catch {
      setError('An unexpected error occurred. Please try again later.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F7F3EA] flex flex-col justify-center items-center p-4">
      {/* Brand Header */}
      <div className="mb-8 text-center">
        <span className="font-serif tracking-widest text-2xl font-bold text-[#242321] block">
          CONTRACTLY
        </span>
        <span className="text-xs uppercase font-mono tracking-wider text-[#6F6A61] mt-1 block">
          Secure Account Recovery
        </span>
      </div>

      {/* Forgot Password Card */}
      <div className="w-full max-w-md bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] shadow-sm p-8">
        <div className="border-b border-[#DED6C8] pb-4 mb-6">
          <h1 className="text-xl font-serif font-bold text-[#242321]">Reset Password</h1>
          <p className="text-xs text-[#6F6A61] mt-1">
            Enter your work email and we will send you secure instructions to reset your password.
          </p>
        </div>

        {error && (
          <div className="mb-5 p-3 bg-[#FDF2F2] border border-[#F5C2C2] text-[#8B3F3F] text-xs rounded-[2px] flex items-start gap-2">
            <span className="font-bold">Error:</span>
            <span>{error}</span>
          </div>
        )}

        {message ? (
          <div className="space-y-4">
            <div className="p-3 bg-[#F2F6ED] border border-[#CDE0B8] text-[#3F4634] text-xs rounded-[2px] flex items-start gap-2">
              <span className="font-bold">Sent:</span>
              <span>{message}</span>
            </div>
            <p className="text-xs text-[#6F6A61] leading-relaxed">
              If an account is associated with this email, you will receive a single-use reset link shortly.
              The link expires in 60 minutes.
            </p>
            <div className="pt-2">
              <Link href="/login">
                <Button variant="outline" size="md" className="w-full">
                  Return to Sign In
                </Button>
              </Link>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#242321] mb-1.5">
                Work Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="counsel@company.internal"
                required
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
                {isLoading ? 'Sending Instructions...' : 'Send Reset Instructions'}
              </Button>
            </div>
          </form>
        )}

        <div className="mt-6 pt-4 border-t border-[#DED6C8] text-center text-xs text-[#6F6A61]">
          <span>Remember your password? </span>
          <Link
            href="/login"
            className="text-[#3F4634] font-medium hover:underline ml-1"
          >
            Sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
