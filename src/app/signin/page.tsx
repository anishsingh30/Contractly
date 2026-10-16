'use client';

import React, { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { login } from '@/lib/api-client';
import { useContractly } from '@/context/contractly-context';
import { Button } from '@/components/ui/button';

function SignInContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const returnUrlParam = searchParams.get('returnUrl');

  const { currentUser, isAuthLoading } = useContractly();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // If already authenticated, redirect to destination or dashboard
  useEffect(() => {
    if (!isAuthLoading && currentUser) {
      let dest = '/dashboard';
      if (returnUrlParam && returnUrlParam.startsWith('/') && !returnUrlParam.startsWith('//')) {
        dest = returnUrlParam;
      }
      window.location.replace(dest);
    }
  }, [currentUser, isAuthLoading, returnUrlParam]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email || !password) {
      setError('Please provide both your work email and password.');
      return;
    }

    setIsLoading(true);
    try {
      const res = await login(email, password);
      if (res.success && res.user) {
        let dest = '/dashboard';
        if (returnUrlParam && returnUrlParam.startsWith('/') && !returnUrlParam.startsWith('//')) {
          dest = returnUrlParam;
        }
        // Force full page navigation to ensure browser registers newly set HttpOnly session cookies
        window.location.href = dest;
      } else {
        setError(res.error || 'Invalid credentials. Please verify your email and password.');
      }
    } catch {
      setError('An unexpected network error occurred while signing in. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F7F3EA] flex flex-col justify-center items-center p-4">
      {/* Brand Header */}
      <div className="mb-8 text-center">
        <Link href="/" className="inline-block focus-visible:outline-none">
          <span className="font-serif tracking-widest text-2xl font-bold text-[#242321] block hover:text-[#3F4634] transition-colors">
            CONTRACTLY
          </span>
        </Link>
        <span className="text-xs uppercase font-mono tracking-wider text-[#6F6A61] mt-1 block">
          Contracts, handled with clarity
        </span>
      </div>

      {/* Sign In Card */}
      <div className="w-full max-w-md bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] shadow-sm p-8">
        <div className="border-b border-[#DED6C8] pb-4 mb-6">
          <h1 className="text-xl font-serif font-bold text-[#242321]">Sign In</h1>
          <p className="text-xs text-[#6F6A61] mt-1">
            Access your organization&apos;s contracts, obligations, and legal workflows.
          </p>
        </div>

        {error && (
          <div className="mb-5 p-3 bg-[#FDF2F2] border border-[#F5C2C2] text-[#8B3F3F] text-xs rounded-[2px] flex items-start gap-2">
            <span className="font-bold">Error:</span>
            <span>{error}</span>
          </div>
        )}

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

          <div>
            <div className="flex justify-between items-baseline mb-1.5">
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#242321]">
                Password
              </label>
              <Link
                href="/forgot-password"
                className="text-[11px] text-[#3F4634] hover:underline"
              >
                Forgot password?
              </Link>
            </div>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              required
              className="w-full bg-[#FCFAF5] border border-[#DED6C8] text-sm text-[#242321] px-3 py-2 rounded-[2px] focus:outline-none focus:border-[#3F4634] transition-colors"
            />
          </div>

          <Button
            type="submit"
            disabled={isLoading}
            className="w-full bg-[#3F4634] text-[#FCFAF5] hover:bg-[#59604A] text-xs py-2.5 rounded-[2px] font-semibold mt-2 transition-colors disabled:opacity-50"
          >
            {isLoading ? 'Signing In...' : 'Sign In to Workspace'}
          </Button>
        </form>

        <div className="mt-6 pt-6 border-t border-[#DED6C8] text-center">
          <p className="text-xs text-[#6F6A61]">
            Need a Contractly workspace?{' '}
            <Link
              href="/signup"
              className="text-[#3F4634] font-semibold hover:underline"
            >
              Create Account
            </Link>
          </p>
        </div>
      </div>

      <div className="mt-8 text-center text-xs text-[#6F6A61] space-x-4">
        <Link href="/" className="hover:underline">
          Public Home
        </Link>
        <span>•</span>
        <Link href="/privacy" className="hover:underline">
          Privacy Policy
        </Link>
        <span>•</span>
        <Link href="/terms" className="hover:underline">
          Terms of Service
        </Link>
      </div>
    </div>
  );
}

export default function SignInPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[#F7F3EA] flex items-center justify-center">
          <span className="font-serif tracking-widest text-xl font-bold text-[#242321]">
            CONTRACTLY
          </span>
        </div>
      }
    >
      <SignInContent />
    </Suspense>
  );
}
