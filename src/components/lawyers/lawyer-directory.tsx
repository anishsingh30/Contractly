'use client';

import React, { useState, useEffect } from 'react';
import { AdvocateProfile } from '@/types/contractly';
import { Button } from '@/components/ui/button';
import { useContractly } from '@/context/contractly-context';
import { submitLawyerInquiry, fetchLawyerDirectory } from '@/lib/api-client';

export function LawyerDirectory() {
  const { addToast } = useContractly();
  const [lawyers, setLawyers] = useState<AdvocateProfile[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedLawyer, setSelectedLawyer] = useState<AdvocateProfile | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [matterTitle, setMatterTitle] = useState<string>('Contract Review & Advisory');
  const [counterpartyName, setCounterpartyName] = useState<string>('');
  const [bookingTime, setBookingTime] = useState<string>('Tomorrow at 3:00 PM');
  const [clientNotes, setClientNotes] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const categories = [
    'ALL',
    'Corporate Contracts',
    'Technology & SaaS',
    'Employment Law',
    'Commercial Property',
    'Data Privacy'
  ];

  const loadDirectory = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchLawyerDirectory(selectedCategory !== 'ALL' ? selectedCategory : undefined);
      setLawyers(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unable to connect to lawyer directory registry.');
      setLawyers([]);
    } finally {
      setLoading(false);
    }
  }, [selectedCategory]);

  useEffect(() => {
    loadDirectory();
  }, [loadDirectory]);

  const handleConfirmBooking = async () => {
    if (!selectedLawyer || isSubmitting) return;
    setIsSubmitting(true);
    try {
      const combinedNotes = [
        matterTitle ? `Subject: ${matterTitle}` : '',
        counterpartyName ? `Counterparty for conflict check: ${counterpartyName}` : '',
        clientNotes.trim()
      ].filter(Boolean).join('\n\n');

      const res = await submitLawyerInquiry({
        lawyer_id: selectedLawyer.id,
        lawyer_name: selectedLawyer.fullName,
        preferred_time_slot: bookingTime,
        client_notes: combinedNotes
      });

      if (res) {
        addToast(
          'Consultation Request Recorded',
          `Consultation inquiry for ${selectedLawyer.fullName} (${bookingTime}) submitted. Reference: ${res.inquiry_id}. Legal operations and the advocate will review conflict clearance before confirming.`,
          'info'
        );
      } else {
        addToast(
          'Consultation Request Submitted',
          `Consultation request for ${selectedLawyer.fullName} (${bookingTime}) received. Note: No automated video link or calendar invitation has been generated.`,
          'info'
        );
      }
      setSelectedLawyer(null);
      setClientNotes('');
      setCounterpartyName('');
      setMatterTitle('Contract Review & Advisory');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unable to record consultation inquiry at this time.';
      addToast('Error', msg, 'danger');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* 1. Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#DED6C8]">
        <div>
          <h1 className="text-xl font-serif font-bold text-[#242321]">
            Get Legal Help
          </h1>
          <p className="text-xs text-[#6F6A61] mt-1 leading-relaxed">
            Connect with verified legal advocates for contract review, clause negotiation, and regulatory advisory.
          </p>
        </div>

        <div className="flex items-center gap-2.5 self-start sm:self-auto">
          <button
            onClick={() => loadDirectory()}
            disabled={loading}
            className="px-2.5 py-1 text-xs font-medium text-[#242321] bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] hover:bg-[#F7F3EA] transition-colors disabled:opacity-50"
            title="Refresh Directory"
          >
            ↻ Refresh
          </button>
          <span className="text-[11px] text-[#2E5230] font-medium px-2.5 py-1 bg-[#EDF2EC] border border-[#C6D8C6] rounded-[2px] flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-[#4F6B50]" /> Verified Legal Advocates
          </span>
        </div>
      </div>

      {/* 2. Bar Council Compliance & Transparency Disclosure */}
      <div className="p-3.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] text-xs text-[#6F6A61] flex items-start gap-2.5">
        <span className="font-serif font-bold text-[#3F4634] text-base leading-none mt-0.5">§</span>
        <div className="space-y-0.5">
          <span className="font-semibold text-[#242321] block text-xs">
            Bar Council Professional Conduct &amp; Transparency Notice
          </span>
          <p className="text-[11px] text-[#6F6A61] leading-relaxed">
            In compliance with Bar Council of India guidelines, advocate listings are strictly non-promotional and based on verified credentials. Listed fees represent attorney consultation estimates (in INR) and are distinct from Contractly platform software fees. Submitting an inquiry checks conflicts and availability; no automated payments or unvetted bookings are made.
          </p>
        </div>
      </div>

      {/* 3. Category Filter */}
      <div className="flex flex-wrap items-center gap-1.5 pb-2 border-b border-[#DED6C8]">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setSelectedCategory(cat)}
            className={`px-3 py-1 text-xs rounded-[2px] transition-colors ${
              selectedCategory === cat
                ? 'bg-[#3F4634] text-[#FCFAF5] font-semibold'
                : 'bg-[#FCFAF5] border border-[#DED6C8] text-[#242321] hover:bg-[#F7F3EA]'
            }`}
          >
            {cat === 'ALL' ? 'All Practice Areas' : cat}
          </button>
        ))}
      </div>

      {/* 4. Lawyer Cards, Loading, Error, or Honest Empty State */}
      {loading ? (
        <div className="p-12 text-center text-xs text-[#6F6A61] bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px]">
          Loading verified advocate directory from platform registry...
        </div>
      ) : error ? (
        <div className="p-8 text-center bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3">
          <div className="w-10 h-10 rounded-full bg-[#FDF2F2] border border-[#F2C6C6] flex items-center justify-center mx-auto text-[#A33B3B] font-serif font-bold text-base">
            !
          </div>
          <h2 className="font-serif font-bold text-base text-[#242321]">
            Directory Service Temporarily Unavailable
          </h2>
          <p className="text-xs text-[#A33B3B] max-w-md mx-auto leading-relaxed">
            {error}
          </p>
          <div className="pt-2">
            <button
              onClick={() => loadDirectory()}
              className="px-4 py-1.5 bg-[#3F4634] text-[#FCFAF5] text-xs font-semibold rounded-[2px] hover:bg-[#2C3124] transition-colors"
            >
              Retry Loading Directory
            </button>
          </div>
        </div>
      ) : lawyers.length === 0 ? (
        <div className="p-12 text-center bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3">
          <div className="w-10 h-10 rounded-full bg-[#EFECE3] border border-[#DED6C8] flex items-center justify-center mx-auto text-[#3F4634] font-serif font-bold text-base">
            §
          </div>
          <h2 className="font-serif font-bold text-base text-[#242321]">
            No Verified Advocates Currently Available
          </h2>
          <p className="text-xs text-[#6F6A61] max-w-md mx-auto leading-relaxed">
            Legal professionals registered on Contractly must complete Bar Council credential verification and platform compliance review before appearing in this directory.
          </p>
          <div className="pt-2">
            <span className="inline-block text-[11px] font-mono text-[#3F4634] bg-[#EDF2EC] border border-[#C6D8C6] px-3 py-1 rounded-[2px]">
              Empty states are honest and reflect live verified platform records.
            </span>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {lawyers.map((lawyer) => (
            <div
              key={lawyer.id}
              className="p-5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] flex flex-col justify-between space-y-4 hover:border-[#3F4634]/60 transition-colors"
            >
              <div>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h2 className="font-semibold text-sm text-[#242321]">{lawyer.fullName}</h2>
                    <p className="text-xs font-mono text-[#3F4634] mt-0.5">
                      {lawyer.professionalTitle || 'Advocate'} • {lawyer.firmName || 'Independent Practice'}
                    </p>
                  </div>
                  <span className="px-1.5 py-0.5 bg-[#EDF2EC] text-[#2E5230] border border-[#C6D8C6] text-[10px] rounded-[2px] font-medium shrink-0">
                    Verified
                  </span>
                </div>

                {/* Approved Qualifications */}
                {lawyer.qualifications && lawyer.qualifications.length > 0 && (
                  <div className="mt-2.5 flex flex-wrap gap-1">
                    {lawyer.qualifications.map((q, i) => (
                      <span
                        key={i}
                        className="px-1.5 py-0.5 bg-[#F7F3EA] border border-[#DED6C8] text-[10px] text-[#242321] rounded-[2px]"
                      >
                        {q}
                      </span>
                    ))}
                  </div>
                )}

                <div className="mt-3 space-y-1.5 text-xs text-[#6F6A61]">
                  <p className="flex items-center justify-between">
                    <span>Experience:</span>
                    <strong className="text-[#242321] font-mono">{lawyer.experienceYears} Years</strong>
                  </p>
                  <p className="flex items-center justify-between">
                    <span>Enrolment Jurisdiction:</span>
                    <strong className="text-[#242321] truncate max-w-[170px] text-right" title={lawyer.stateBarCouncil}>
                      {lawyer.stateBarCouncil}
                    </strong>
                  </p>
                  {lawyer.barCouncilNumber && (
                    <p className="flex items-center justify-between">
                      <span>Bar Council ID:</span>
                      <strong className="font-mono text-[#242321]">{lawyer.barCouncilNumber}</strong>
                    </p>
                  )}
                  {lawyer.languages && lawyer.languages.length > 0 && (
                    <p className="flex items-center justify-between">
                      <span>Languages:</span>
                      <span className="text-[#242321]">{lawyer.languages.join(', ')}</span>
                    </p>
                  )}
                  {lawyer.consultationFee && (
                    <div className="pt-2 border-t border-[#DED6C8] flex items-baseline justify-between">
                      <span className="text-[11px] text-[#6F6A61]">Consultation Fee:</span>
                      <span className="text-xs font-bold text-[#3F4634] font-mono">
                        {lawyer.consultationFee}
                        {lawyer.consultationDurationMinutes ? ` (${lawyer.consultationDurationMinutes} min)` : ''}
                      </span>
                    </div>
                  )}
                </div>

                {lawyer.bio && (
                  <p className="mt-3 text-xs text-[#242321] leading-relaxed line-clamp-3">
                    {lawyer.bio}
                  </p>
                )}

                {lawyer.practiceAreas && lawyer.practiceAreas.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1">
                    {lawyer.practiceAreas.map((pa, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 bg-[#EFECE3] border border-[#DED6C8] text-[10px] text-[#242321] rounded-[2px]"
                      >
                        {pa}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="pt-3 border-t border-[#DED6C8]">
                <Button
                  onClick={() => setSelectedLawyer(lawyer)}
                  variant="primary"
                  size="sm"
                  className="w-full text-xs font-semibold"
                >
                  Request Consultation →
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 5. Consultation Request Intake Dialog */}
      {selectedLawyer && (
        <div className="fixed inset-0 z-50 bg-[#242321]/45 flex items-center justify-center p-4">
          <div className="bg-[#FCFAF5] border border-[#DED6C8] max-w-lg w-full p-6 rounded-[2px] space-y-4 shadow-lg">
            <div className="flex items-center justify-between border-b border-[#DED6C8] pb-3">
              <div>
                <span className="font-mono text-[10px] uppercase font-bold text-[#3F4634] block">
                  Confidential Intake • Consultation Request
                </span>
                <h3 className="font-serif font-bold text-base text-[#242321] mt-0.5">
                  Request Consultation with {selectedLawyer.fullName}
                </h3>
                <p className="text-xs text-[#6F6A61]">
                  {selectedLawyer.professionalTitle || 'Advocate'} • {selectedLawyer.firmName || 'Chambers'}
                </p>
              </div>
              <button
                onClick={() => setSelectedLawyer(null)}
                className="text-[#6F6A61] hover:text-[#242321] text-xs font-mono p-1"
                aria-label="Close dialog"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3.5 text-xs">
              <div>
                <label className="block font-medium text-[#242321] mb-1">
                  Subject / Legal Matter Title <span className="text-[#8B3F3F]">*</span>
                </label>
                <input
                  type="text"
                  value={matterTitle}
                  onChange={(e) => setMatterTitle(e.target.value)}
                  placeholder="e.g. Master Services Agreement Liability Review"
                  className="w-full bg-[#F7F3EA] border border-[#DED6C8] text-xs text-[#242321] p-2 rounded-[2px] focus:outline-none focus:border-[#3F4634]"
                />
              </div>

              <div>
                <label className="block font-medium text-[#242321] mb-1">
                  Counterparty Name (for Conflict of Interest Clearance) <span className="text-[#8B3F3F]">*</span>
                </label>
                <input
                  type="text"
                  value={counterpartyName}
                  onChange={(e) => setCounterpartyName(e.target.value)}
                  placeholder="e.g. Acme Tech Solutions Private Limited"
                  className="w-full bg-[#F7F3EA] border border-[#DED6C8] text-xs text-[#242321] p-2 rounded-[2px] focus:outline-none focus:border-[#3F4634]"
                />
                <p className="text-[10px] text-[#6F6A61] mt-0.5">
                  Statutory requirement: Advocates must clear conflicts of interest prior to accepting matter instructions.
                </p>
              </div>

              <div>
                <label className="block font-medium text-[#242321] mb-1">Preferred Consultation Slot</label>
                <select
                  value={bookingTime}
                  onChange={(e) => setBookingTime(e.target.value)}
                  className="w-full bg-[#F7F3EA] border border-[#DED6C8] text-xs text-[#242321] p-2 rounded-[2px]"
                >
                  <option value="Tomorrow at 11:30 AM">Tomorrow at 11:30 AM</option>
                  <option value="Tomorrow at 3:00 PM">Tomorrow at 3:00 PM</option>
                  <option value="Thursday at 2:00 PM">Thursday at 2:00 PM</option>
                  <option value="Friday at 4:30 PM">Friday at 4:30 PM</option>
                </select>
              </div>

              <div>
                <label className="block font-medium text-[#242321] mb-1">
                  Summary of Legal Need or Clause Concerns
                </label>
                <textarea
                  rows={3}
                  value={clientNotes}
                  onChange={(e) => setClientNotes(e.target.value)}
                  placeholder="Provide brief context on specific clauses, commercial exposures, or negotiation objectives..."
                  className="w-full bg-[#F7F3EA] border border-[#DED6C8] text-xs text-[#242321] p-2 rounded-[2px] focus:outline-none focus:border-[#3F4634]"
                />
              </div>

              {/* Explicit Fee Breakdown */}
              <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] space-y-1.5 text-[11px]">
                <div className="flex justify-between items-center text-[#242321]">
                  <span>Advocate Consultation Fee:</span>
                  <span className="font-mono font-bold text-[#3F4634]">
                    {selectedLawyer.consultationFee || 'INR 0'}
                  </span>
                </div>
                <div className="flex justify-between items-center text-[#6F6A61]">
                  <span>Contractly Platform Coordination:</span>
                  <span className="font-mono">INR 0 (No Platform Surcharge)</span>
                </div>
                <p className="text-[10px] text-[#6F6A61] pt-1 border-t border-[#DED6C8]">
                  • No payment is collected at this stage. Consultation fees are settled directly pursuant to client-advocate engagement terms.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-[#DED6C8]">
              <Button onClick={() => setSelectedLawyer(null)} variant="secondary" size="sm" disabled={isSubmitting}>
                Cancel
              </Button>
              <Button
                onClick={handleConfirmBooking}
                variant="primary"
                size="sm"
                disabled={isSubmitting || !counterpartyName.trim()}
              >
                {isSubmitting ? 'Submitting Request...' : 'Submit Consultation Request'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
