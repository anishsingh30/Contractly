import React from 'react';
import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="min-h-screen bg-[#F7F3EA] text-[#242321] flex flex-col justify-between selection:bg-[#3F4634] selection:text-[#FCFAF5]">
      {/* Header */}
      <header className="h-16 border-b border-[#DED6C8] px-6 lg:px-12 flex items-center justify-between bg-[#F7F3EA]/90">
        <Link href="/" className="font-serif tracking-widest text-lg font-bold text-[#242321]">
          CONTRACTLY
        </Link>
        <span className="text-xs font-mono text-[#6F6A61]">
          Error 404 • Page Not Found
        </span>
      </header>

      {/* Main Content */}
      <main className="max-w-lg mx-auto px-6 py-20 text-center space-y-6">
        <div className="w-12 h-12 rounded-[2px] bg-[#FCFAF5] border border-[#DED6C8] flex items-center justify-center mx-auto text-[#3F4634] font-mono font-bold text-sm">
          404
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl sm:text-3xl font-serif font-bold text-[#242321]">
            Document or Route Not Found
          </h1>
          <p className="text-xs sm:text-sm text-[#6F6A61] leading-relaxed">
            The page or operational view you requested does not exist or may have been moved.
          </p>
        </div>

        <div className="pt-2 flex items-center justify-center gap-3">
          <Link
            href="/"
            className="px-4 py-2 bg-[#3F4634] text-[#FCFAF5] text-xs font-semibold rounded-[2px] hover:bg-[#59604A] transition-colors"
          >
            ← Return to Dashboard
          </Link>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-6 border-t border-[#DED6C8] bg-[#F7F3EA] text-center text-xs text-[#6F6A61] font-mono">
        © 2026 Contractly Systems. All rights reserved.
      </footer>
    </div>
  );
}
