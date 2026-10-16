'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { register } from '@/lib/api-client';
import { useContractly } from '@/context/contractly-context';
import { Button } from '@/components/ui/button';

type AccountTypeOption = 'INDIVIDUAL' | 'BUSINESS' | 'ENTERPRISE' | 'LEGAL_PROFESSIONAL';

interface AccountTypeConfig {
  id: AccountTypeOption;
  label: string;
  tagline: string;
  description: string;
}

const ACCOUNT_OPTIONS: AccountTypeConfig[] = [
  {
    id: 'INDIVIDUAL',
    label: 'Individual',
    tagline: 'Personal Workspace',
    description: 'For individuals managing personal agreements, deadlines, and contract-grounded inquiries.'
  },
  {
    id: 'BUSINESS',
    label: 'Business',
    tagline: 'Team Workspace',
    description: 'For corporate teams managing vendor agreements, shared repositories, and approval workflows.'
  },
  {
    id: 'ENTERPRISE',
    label: 'Enterprise',
    tagline: 'Organization Workspace',
    description: 'For organizations requiring department isolation, role-based controls, and audit trails.'
  },
  {
    id: 'LEGAL_PROFESSIONAL',
    label: 'Legal Professional',
    tagline: 'Practice Workspace',
    description: 'For advocates and legal chambers managing external client matters and contract reviews.'
  }
];

export default function SignUpPage() {
  const router = useRouter();
  const { currentUser, isAuthLoading } = useContractly();

  const [accountType, setAccountType] = useState<AccountTypeOption>('BUSINESS');
  const [organizationName, setOrganizationName] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // If already authenticated, redirect to dashboard
  useEffect(() => {
    if (!isAuthLoading && currentUser) {
      window.location.replace('/dashboard');
    }
  }, [currentUser, isAuthLoading]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!fullName.trim() || !email.trim() || !password) {
      setError('Please provide your full name, work email, and password.');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match. Please re-enter your password.');
      return;
    }

    if (password.length < 8) {
      setError('Password must contain at least 8 characters.');
      return;
    }

    if (!/\d/.test(password)) {
      setError('Password must contain at least one number.');
      return;
    }

    if (!/[!@#$%^&*(),.?":{}|<>\-_\\/+=;~`\[\]]/.test(password)) {
      setError('Password must contain at least one special character (!@#$%^&*...).');
      return;
    }

    setIsLoading(true);
    try {
      const res = await register({
        organizationName: organizationName.trim() || undefined,
        fullName: fullName.trim(),
        email: email.trim(),
        password,
        accountType
      });

      if (res.success && res.user) {
        // Force full page navigation to register newly issued HttpOnly session cookies
        window.location.href = '/dashboard';
      } else {
        setError(res.error || 'Failed to create workspace. Please verify your details.');
      }
    } catch {
      setError('An unexpected network error occurred during registration. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F7F3EA] flex flex-col justify-center items-center p-4 py-12">
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

      {/* Registration Card */}
      <div className="w-full max-w-lg bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] shadow-sm p-8">
        <div className="border-b border-[#DED6C8] pb-4 mb-6">
          <h1 className="text-xl font-serif font-bold text-[#242321]">Create Your Workspace</h1>
          <p className="text-xs text-[#6F6A61] mt-1">
            Set up an isolated contract operations workspace for your organization or practice.
          </p>
        </div>

        {error && (
          <div className="mb-5 p-3 bg-[#FDF2F2] border border-[#F5C2C2] text-[#8B3F3F] text-xs rounded-[2px] flex items-start gap-2">
            <span className="font-bold">Error:</span>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Workspace / Account Type Selector */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-[#242321] mb-2">
              Select Workspace Type
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {ACCOUNT_OPTIONS.map((opt) => {
                const isSelected = accountType === opt.id;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setAccountType(opt.id)}
                    className={`p-3 text-left border rounded-[2px] transition-colors ${
                      isSelected
                        ? 'border-[#3F4634] bg-[#F7F3EA]'
                        : 'border-[#DED6C8] bg-[#FCFAF5] hover:border-[#6F6A61]'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-[#242321]">{opt.label}</span>
                      {isSelected && (
                        <span className="w-2 h-2 rounded-full bg-[#3F4634]"></span>
                      )}
                    </div>
                    <span className="text-[11px] text-[#6F6A61] mt-0.5 block leading-tight">
                      {opt.tagline}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Organization Name (if non-individual) */}
          {accountType !== 'INDIVIDUAL' && (
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#242321] mb-1.5">
                {accountType === 'LEGAL_PROFESSIONAL' ? 'Practice / Chambers Name' : 'Organization / Company Name'}
              </label>
              <input
                type="text"
                value={organizationName}
                onChange={(e) => setOrganizationName(e.target.value)}
                placeholder={accountType === 'LEGAL_PROFESSIONAL' ? 'e.g. Apex Legal Chambers' : 'e.g. Acme Corp Ltd'}
                required
                className="w-full bg-[#FCFAF5] border border-[#DED6C8] text-sm text-[#242321] px-3 py-2 rounded-[2px] focus:outline-none focus:border-[#3F4634] transition-colors"
              />
            </div>
          )}

          {/* Full Name */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-[#242321] mb-1.5">
              Full Name
            </label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Alice Vance"
              required
              className="w-full bg-[#FCFAF5] border border-[#DED6C8] text-sm text-[#242321] px-3 py-2 rounded-[2px] focus:outline-none focus:border-[#3F4634] transition-colors"
            />
          </div>

          {/* Work Email */}
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

          {/* Password & Confirm Password */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#242321] mb-1.5">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Min 8 chars, 1 number, 1 symbol"
                required
                className="w-full bg-[#FCFAF5] border border-[#DED6C8] text-sm text-[#242321] px-3 py-2 rounded-[2px] focus:outline-none focus:border-[#3F4634] transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#242321] mb-1.5">
                Confirm Password
              </label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter password"
                required
                className="w-full bg-[#FCFAF5] border border-[#DED6C8] text-sm text-[#242321] px-3 py-2 rounded-[2px] focus:outline-none focus:border-[#3F4634] transition-colors"
              />
            </div>
          </div>

          <div className="text-[11px] text-[#6F6A61] leading-relaxed">
            By creating a workspace, you agree to Contractly&apos;s{' '}
            <Link href="/terms" className="text-[#3F4634] underline">
              Terms of Service
            </Link>{' '}
            and acknowledge the{' '}
            <Link href="/privacy" className="text-[#3F4634] underline">
              Privacy Policy
            </Link>
            .
          </div>

          <Button
            type="submit"
            disabled={isLoading}
            className="w-full bg-[#3F4634] text-[#FCFAF5] hover:bg-[#59604A] text-xs py-2.5 rounded-[2px] font-semibold transition-colors disabled:opacity-50"
          >
            {isLoading ? 'Creating Workspace...' : 'Create Contractly Workspace'}
          </Button>
        </form>

        <div className="mt-6 pt-6 border-t border-[#DED6C8] text-center">
          <p className="text-xs text-[#6F6A61]">
            Already have an active account?{' '}
            <Link
              href="/signin"
              className="text-[#3F4634] font-semibold hover:underline"
            >
              Sign In
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
