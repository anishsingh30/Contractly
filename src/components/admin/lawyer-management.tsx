'use client';

import React, { useState } from 'react';
import { AdvocateProfile } from '@/types/contractly';
import {
  createAdminLawyer,
  updateAdminLawyer,
  verifyAdvocateProfile,
  publishAdminLawyer,
  setAdminLawyerAvailability,
  deleteAdminLawyer
} from '@/lib/api-client';

interface LawyerManagementProps {
  initialLawyers: AdvocateProfile[];
  onRefresh: () => void;
}

export function LawyerManagement({ initialLawyers, onRefresh }: LawyerManagementProps) {
  const [lawyers, setLawyers] = useState<AdvocateProfile[]>(initialLawyers);
  const [search, setSearch] = useState('');
  const [practiceAreaFilter, setPracticeAreaFilter] = useState('ALL');
  const [verificationFilter, setVerificationFilter] = useState('ALL');
  const [publicationFilter, setPublicationFilter] = useState('ALL');

  // Modal States
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [editingLawyer, setEditingLawyer] = useState<AdvocateProfile | null>(null);
  const [confirmModal, setConfirmModal] = useState<{
    action: 'VERIFY' | 'REJECT' | 'PUBLISH' | 'UNPUBLISH' | 'DELETE' | 'TOGGLE_AVAILABILITY';
    lawyer: AdvocateProfile;
    rejectionReason?: string;
  } | null>(null);

  const [actionLoading, setActionLoading] = useState(false);
  const [actionFeedback, setActionFeedback] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Form State for Add / Edit
  const [formData, setFormData] = useState({
    fullName: '',
    email: '',
    phoneNumber: '',
    professionalTitle: 'Advocate',
    firmName: '',
    barCouncilNumber: '',
    stateBarCouncil: 'Bar Council of Delhi',
    admittedJurisdictions: 'Supreme Court of India, Delhi High Court',
    practiceAreas: 'Corporate Contracts, Technology & SaaS',
    qualifications: 'LL.B., NLSIU',
    languages: 'English, Hindi',
    experienceYears: 10,
    consultationFee: 'INR 5,000 / 30 mins',
    consultationDurationMinutes: 30,
    bio: '',
    internalNotes: '',
    isAvailableForInquiries: true
  });

  // Sync internal state when parent refreshes
  React.useEffect(() => {
    setLawyers(initialLawyers);
  }, [initialLawyers]);

  const practiceAreaOptions = [
    'ALL',
    'Corporate Contracts',
    'Technology & SaaS',
    'Employment Law',
    'Commercial Property',
    'Data Privacy'
  ];

  const filteredLawyers = lawyers.filter((l) => {
    if (practiceAreaFilter !== 'ALL') {
      const areas = (l.practiceAreas || []).map((a) => a.toLowerCase());
      if (!areas.some((a) => a.includes(practiceAreaFilter.toLowerCase()))) return false;
    }
    if (verificationFilter !== 'ALL' && l.verificationStatus !== verificationFilter) return false;
    if (publicationFilter !== 'ALL') {
      const isPub = l.isPublished === true;
      if (publicationFilter === 'PUBLISHED' && !isPub) return false;
      if (publicationFilter === 'UNPUBLISHED' && isPub) return false;
    }
    if (search.trim()) {
      const q = search.toLowerCase().trim();
      const matchName = (l.fullName || '').toLowerCase().includes(q);
      const matchEmail = (l.email || '').toLowerCase().includes(q);
      const matchFirm = (l.firmName || '').toLowerCase().includes(q);
      const matchBC = (l.barCouncilNumber || '').toLowerCase().includes(q);
      if (!matchName && !matchEmail && !matchFirm && !matchBC) return false;
    }
    return true;
  });

  const openCreateModal = () => {
    setFormData({
      fullName: '',
      email: '',
      phoneNumber: '',
      professionalTitle: 'Advocate',
      firmName: '',
      barCouncilNumber: '',
      stateBarCouncil: 'Bar Council of Delhi',
      admittedJurisdictions: 'Supreme Court of India, Delhi High Court',
      practiceAreas: 'Corporate Contracts, Technology & SaaS',
      qualifications: 'LL.B., NLSIU',
      languages: 'English, Hindi',
      experienceYears: 10,
      consultationFee: 'INR 5,000 / 30 mins',
      consultationDurationMinutes: 30,
      bio: '',
      internalNotes: '',
      isAvailableForInquiries: true
    });
    setEditingLawyer(null);
    setIsAddModalOpen(true);
  };

  const openEditModal = (lawyer: AdvocateProfile) => {
    setFormData({
      fullName: lawyer.fullName,
      email: lawyer.email || '',
      phoneNumber: lawyer.phoneNumber || '',
      professionalTitle: lawyer.professionalTitle || 'Advocate',
      firmName: lawyer.firmName || '',
      barCouncilNumber: lawyer.barCouncilNumber || '',
      stateBarCouncil: lawyer.stateBarCouncil || '',
      admittedJurisdictions: lawyer.admittedJurisdictions || '',
      practiceAreas: (lawyer.practiceAreas || []).join(', '),
      qualifications: (lawyer.qualifications || []).join(', '),
      languages: (lawyer.languages || []).join(', '),
      experienceYears: lawyer.experienceYears || 0,
      consultationFee: lawyer.consultationFee || 'INR 0',
      consultationDurationMinutes: lawyer.consultationDurationMinutes || 30,
      bio: lawyer.bio || '',
      internalNotes: lawyer.internalNotes || '',
      isAvailableForInquiries: lawyer.isAvailableForInquiries !== false
    });
    setEditingLawyer(lawyer);
    setIsAddModalOpen(true);
  };

  const handleSaveLawyer = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionFeedback(null);

    // Frontend validation of mandatory model fields
    if (!formData.fullName.trim()) {
      setActionFeedback({ message: 'Full legal name is required.', type: 'error' });
      return;
    }
    if (!formData.email.trim()) {
      setActionFeedback({ message: 'A valid email address is required for private contact.', type: 'error' });
      return;
    }
    if (!formData.barCouncilNumber.trim()) {
      setActionFeedback({ message: 'Bar Council enrolment number is required.', type: 'error' });
      return;
    }
    if (!formData.stateBarCouncil.trim()) {
      setActionFeedback({ message: 'State Bar Council is required.', type: 'error' });
      return;
    }
    if (!formData.admittedJurisdictions.trim()) {
      setActionFeedback({ message: 'Admitted jurisdictions are required.', type: 'error' });
      return;
    }
    const practiceAreasList = formData.practiceAreas.split(',').map((s) => s.trim()).filter(Boolean);
    if (practiceAreasList.length === 0) {
      setActionFeedback({ message: 'At least one practice area is required.', type: 'error' });
      return;
    }

    setActionLoading(true);

    const payload = {
      full_name: formData.fullName.trim(),
      email: formData.email.trim(),
      phone_number: formData.phoneNumber.trim() || undefined,
      professional_title: formData.professionalTitle.trim() || 'Advocate',
      firm_name: formData.firmName.trim() || undefined,
      bar_council_number: formData.barCouncilNumber.trim(),
      state_bar_council: formData.stateBarCouncil.trim(),
      admitted_jurisdictions: formData.admittedJurisdictions.trim(),
      practice_areas: practiceAreasList,
      qualifications: formData.qualifications.split(',').map((s) => s.trim()).filter(Boolean),
      languages: formData.languages.split(',').map((s) => s.trim()).filter(Boolean),
      experience_years: Number(formData.experienceYears) || 0,
      consultation_fee: formData.consultationFee.trim() || 'INR 0',
      consultation_duration_minutes: Number(formData.consultationDurationMinutes) || 30,
      bio: formData.bio.trim() || undefined,
      internal_notes: formData.internalNotes.trim() || undefined,
      is_available_for_inquiries: formData.isAvailableForInquiries
    };

    if (editingLawyer) {
      const res = await updateAdminLawyer(editingLawyer.id, payload);
      setActionLoading(false);
      if (res.success) {
        setActionFeedback({ message: `Lawyer profile for ${payload.full_name} updated successfully.`, type: 'success' });
        setIsAddModalOpen(false);
        onRefresh();
      } else {
        setActionFeedback({ message: res.error || 'Failed to update lawyer profile.', type: 'error' });
      }
    } else {
      const res = await createAdminLawyer(payload);
      setActionLoading(false);
      if (res.success) {
        setActionFeedback({ message: `Lawyer profile for ${payload.full_name} registered successfully. Profile is pending credential review.`, type: 'success' });
        setIsAddModalOpen(false);
        onRefresh();
      } else {
        setActionFeedback({ message: res.error || 'Failed to create lawyer profile.', type: 'error' });
      }
    }
  };

  const executeConfirmAction = async () => {
    if (!confirmModal) return;
    setActionLoading(true);
    setActionFeedback(null);

    const { action, lawyer, rejectionReason } = confirmModal;

    try {
      if (action === 'VERIFY') {
        const res = await verifyAdvocateProfile(lawyer.id, 'VERIFY');
        if (res.success) {
          setActionFeedback({ message: `Credentials for ${lawyer.fullName} verified successfully.`, type: 'success' });
        } else {
          setActionFeedback({ message: res.error || 'Verification failed.', type: 'error' });
        }
      } else if (action === 'REJECT') {
        const res = await verifyAdvocateProfile(lawyer.id, 'REJECT', rejectionReason);
        if (res.success) {
          setActionFeedback({ message: `Credentials for ${lawyer.fullName} marked as rejected.`, type: 'success' });
        } else {
          setActionFeedback({ message: res.error || 'Rejection failed.', type: 'error' });
        }
      } else if (action === 'PUBLISH') {
        const res = await publishAdminLawyer(lawyer.id, true);
        if (res.success) {
          setActionFeedback({ message: `Profile for ${lawyer.fullName} published to public directory.`, type: 'success' });
        } else {
          setActionFeedback({ message: res.error || 'Failed to publish profile.', type: 'error' });
        }
      } else if (action === 'UNPUBLISH') {
        const res = await publishAdminLawyer(lawyer.id, false);
        if (res.success) {
          setActionFeedback({ message: `Profile for ${lawyer.fullName} unpublished from public directory.`, type: 'success' });
        } else {
          setActionFeedback({ message: res.error || 'Failed to unpublish profile.', type: 'error' });
        }
      } else if (action === 'TOGGLE_AVAILABILITY') {
        const target = !(lawyer.isAvailableForInquiries !== false);
        const res = await setAdminLawyerAvailability(lawyer.id, target);
        if (res.success) {
          setActionFeedback({ message: `Inquiry availability for ${lawyer.fullName} set to ${target ? 'Active' : 'Inactive'}.`, type: 'success' });
        } else {
          setActionFeedback({ message: res.error || 'Failed to update availability.', type: 'error' });
        }
      } else if (action === 'DELETE') {
        const res = await deleteAdminLawyer(lawyer.id);
        if (res.success) {
          setActionFeedback({ message: `Lawyer profile for ${lawyer.fullName} removed from registry.`, type: 'success' });
        } else {
          setActionFeedback({ message: res.error || 'Failed to delete lawyer profile.', type: 'error' });
        }
      }
    } finally {
      setActionLoading(false);
      setConfirmModal(null);
      onRefresh();
    }
  };

  return (
    <section id="lawyer-management" className="space-y-4">
      {/* 1. Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#DED6C8] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-serif font-bold text-[#242321] uppercase tracking-wider">
              Lawyer Management &amp; Credential Registry
            </h2>
            <span className="px-2 py-0.5 bg-[#EDF2EC] text-[#2E5230] border border-[#C6D8C6] text-[10px] font-mono font-bold rounded-[2px]">
              {lawyers.length} Registered
            </span>
          </div>
          <p className="text-xs text-[#6F6A61] mt-0.5">
            Admin console for onboarding lawyers, verifying credentials, publishing to public directory, and managing private contact details.
          </p>
        </div>

        <button
          onClick={openCreateModal}
          id="add-lawyer-btn"
          className="px-3.5 py-1.5 bg-[#3F4634] text-[#FCFAF5] text-xs font-semibold rounded-[2px] hover:bg-[#2C3124] transition-colors self-start sm:self-auto shrink-0 flex items-center gap-1.5 shadow-sm"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add Lawyer
        </button>
      </div>

      {/* 2. Feedback Notification */}
      {actionFeedback && (
        <div
          className={`p-3 text-xs border rounded-[2px] flex items-center justify-between ${
            actionFeedback.type === 'success'
              ? 'bg-[#EDF2EC] text-[#2E5230] border-[#C6D8C6]'
              : 'bg-[#FDF2F2] text-[#A33B3B] border-[#F2C6C6]'
          }`}
        >
          <span>{actionFeedback.message}</span>
          <button
            onClick={() => setActionFeedback(null)}
            className="text-[10px] font-mono font-bold px-1"
          >
            ✕
          </button>
        </div>
      )}

      {/* 3. Search & Filter Bar */}
      <div className="p-3 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] flex flex-wrap items-center gap-3 text-xs">
        <div className="flex-1 min-w-[200px]">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, email, Bar Council ID, chambers..."
            className="w-full px-3 py-1.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] text-xs text-[#242321] placeholder-[#6F6A61] focus:outline-none focus:border-[#3F4634]"
          />
        </div>

        <div className="flex items-center gap-2">
          <label className="text-[11px] font-mono text-[#6F6A61]">Practice Area:</label>
          <select
            value={practiceAreaFilter}
            onChange={(e) => setPracticeAreaFilter(e.target.value)}
            className="bg-[#F7F3EA] border border-[#DED6C8] px-2 py-1.5 rounded-[2px] text-xs text-[#242321]"
          >
            {practiceAreaOptions.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-[11px] font-mono text-[#6F6A61]">Verification:</label>
          <select
            value={verificationFilter}
            onChange={(e) => setVerificationFilter(e.target.value)}
            className="bg-[#F7F3EA] border border-[#DED6C8] px-2 py-1.5 rounded-[2px] text-xs text-[#242321]"
          >
            <option value="ALL">All Statuses</option>
            <option value="PENDING_REVIEW">Pending Review</option>
            <option value="VERIFIED">Verified</option>
            <option value="REJECTED">Rejected</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-[11px] font-mono text-[#6F6A61]">Directory:</label>
          <select
            value={publicationFilter}
            onChange={(e) => setPublicationFilter(e.target.value)}
            className="bg-[#F7F3EA] border border-[#DED6C8] px-2 py-1.5 rounded-[2px] text-xs text-[#242321]"
          >
            <option value="ALL">All Profiles</option>
            <option value="PUBLISHED">Published</option>
            <option value="UNPUBLISHED">Unpublished</option>
          </select>
        </div>
      </div>

      {/* 4. Lawyer Registry Table */}
      <div className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-[#DED6C8] bg-[#F7F3EA] text-[11px] font-mono text-[#6F6A61]">
              <th className="py-2.5 px-4 font-normal">Advocate &amp; Private Contact</th>
              <th className="py-2.5 px-4 font-normal">Bar Council Enrolment</th>
              <th className="py-2.5 px-4 font-normal">Practice &amp; Experience</th>
              <th className="py-2.5 px-4 font-normal">Consultation Fee (INR)</th>
              <th className="py-2.5 px-4 font-normal">Verification Status</th>
              <th className="py-2.5 px-4 font-normal">Directory Status</th>
              <th className="py-2.5 px-4 font-normal">Admin Controls</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#DED6C8]">
            {filteredLawyers.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-8 text-center text-[#6F6A61] italic">
                  No advocate profiles match the selected filter criteria.
                </td>
              </tr>
            ) : (
              filteredLawyers.map((adv) => (
                <tr key={adv.id} className="hover:bg-[#F7F3EA]/50">
                  {/* Advocate & Private Contact (Admin view only) */}
                  <td className="py-3 px-4 font-medium text-[#242321]">
                    <div className="flex items-baseline gap-1.5">
                      <span className="font-semibold">{adv.fullName}</span>
                      <span className="text-[10px] text-[#3F4634] font-mono">({adv.professionalTitle || 'Advocate'})</span>
                    </div>
                    <div className="text-[10px] text-[#6F6A61] mt-0.5">{adv.firmName || 'Independent Practice'}</div>
                    <div className="mt-1 pt-1 border-t border-[#EFECE3] space-y-0.5">
                      <div className="text-[10px] font-mono text-[#242321] flex items-center gap-1">
                        <span className="text-[#6F6A61]">Email:</span> {adv.email || 'N/A'}
                      </div>
                      {adv.phoneNumber && (
                        <div className="text-[10px] font-mono text-[#242321] flex items-center gap-1">
                          <span className="text-[#6F6A61]">Phone:</span> {adv.phoneNumber}
                        </div>
                      )}
                    </div>
                  </td>

                  {/* Bar Council & Qualifications */}
                  <td className="py-3 px-4 text-[#6F6A61]">
                    <div className="font-mono text-[11px] text-[#242321] font-semibold">
                      {adv.barCouncilNumber || 'Unspecified'}
                    </div>
                    <div className="text-[11px] text-[#6F6A61]">{adv.stateBarCouncil}</div>
                    <div className="text-[10px] text-[#6F6A61] truncate max-w-[140px]" title={adv.admittedJurisdictions}>
                      {adv.admittedJurisdictions}
                    </div>
                    {adv.qualifications && adv.qualifications.length > 0 && (
                      <div className="text-[10px] text-[#3F4634] mt-0.5">
                        {adv.qualifications.join(', ')}
                      </div>
                    )}
                  </td>

                  {/* Practice & Experience */}
                  <td className="py-3 px-4 text-[#6F6A61]">
                    <div className="font-mono text-[11px] text-[#242321]">
                      {adv.experienceYears} Years
                    </div>
                    <div className="flex flex-wrap gap-1 mt-1 max-w-[180px]">
                      {(adv.practiceAreas || []).map((pa, i) => (
                        <span
                          key={i}
                          className="px-1.5 py-0.2 text-[9px] bg-[#EFECE3] border border-[#DED6C8] rounded-[2px] text-[#242321]"
                        >
                          {pa}
                        </span>
                      ))}
                    </div>
                  </td>

                  {/* Consultation Fee */}
                  <td className="py-3 px-4 font-mono text-[11px]">
                    <div className="text-[#3F4634] font-semibold">{adv.consultationFee || 'INR 0'}</div>
                    <div className="text-[10px] text-[#6F6A61]">
                      {adv.consultationDurationMinutes ? `${adv.consultationDurationMinutes} min slot` : 'Standard slot'}
                    </div>
                  </td>

                  {/* Verification Status */}
                  <td className="py-3 px-4">
                    <span
                      className={`font-mono text-[10px] px-2 py-0.5 border rounded-[2px] block w-fit ${
                        adv.verificationStatus === 'VERIFIED'
                          ? 'bg-[#EDF2EC] text-[#2E5230] border-[#C6D8C6]'
                          : adv.verificationStatus === 'REJECTED'
                          ? 'bg-[#FDF2F2] text-[#A33B3B] border-[#F2C6C6]'
                          : 'bg-[#FDF8EE] text-[#7A4D1A] border-[#E8D9B5]'
                      }`}
                    >
                      {adv.verificationStatus}
                    </span>
                    {adv.verifiedAt && (
                      <span className="text-[10px] text-[#6F6A61] font-mono block mt-0.5">
                        {new Date(adv.verifiedAt).toLocaleDateString()}
                      </span>
                    )}
                    {adv.rejectionReason && (
                      <span className="text-[10px] text-[#A33B3B] block mt-0.5 max-w-[120px] truncate" title={adv.rejectionReason}>
                        {adv.rejectionReason}
                      </span>
                    )}
                  </td>

                  {/* Directory Status */}
                  <td className="py-3 px-4">
                    <span
                      className={`font-mono text-[10px] px-2 py-0.5 border rounded-[2px] block w-fit ${
                        adv.isPublished
                          ? 'bg-[#EDF2EC] text-[#2E5230] border-[#C6D8C6]'
                          : 'bg-[#F7F3EA] text-[#6F6A61] border-[#DED6C8]'
                      }`}
                    >
                      {adv.isPublished ? '● Published' : '○ Unpublished'}
                    </span>
                    <button
                      onClick={() => setConfirmModal({ action: 'TOGGLE_AVAILABILITY', lawyer: adv })}
                      className="text-[10px] text-[#3F4634] hover:underline font-mono mt-1 block"
                      title="Click to toggle intake availability"
                    >
                      {adv.isAvailableForInquiries !== false ? 'Accepting Inquiries' : 'Unavailable'}
                    </button>
                  </td>

                  {/* Admin Actions */}
                  <td className="py-3 px-4">
                    <div className="flex flex-col gap-1">
                      {adv.verificationStatus === 'PENDING_REVIEW' ? (
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => setConfirmModal({ action: 'VERIFY', lawyer: adv })}
                            className="px-2 py-1 bg-[#3F4634] text-[#FCFAF5] text-[10px] font-semibold rounded-[2px] hover:bg-[#2C3124]"
                          >
                            Verify
                          </button>
                          <button
                            onClick={() => setConfirmModal({ action: 'REJECT', lawyer: adv, rejectionReason: '' })}
                            className="px-2 py-1 bg-[#FCFAF5] border border-[#DED6C8] text-[#8B3F3F] text-[10px] font-semibold rounded-[2px] hover:bg-[#FDF2F2]"
                          >
                            Reject
                          </button>
                        </div>
                      ) : adv.verificationStatus === 'VERIFIED' ? (
                        <div className="flex items-center gap-1">
                          {adv.isPublished ? (
                            <button
                              onClick={() => setConfirmModal({ action: 'UNPUBLISH', lawyer: adv })}
                              className="px-2 py-0.5 bg-[#FCFAF5] border border-[#DED6C8] text-[#6F6A61] text-[10px] font-medium rounded-[2px] hover:bg-[#F7F3EA]"
                            >
                              Unpublish
                            </button>
                          ) : (
                            <button
                              onClick={() => setConfirmModal({ action: 'PUBLISH', lawyer: adv })}
                              className="px-2 py-0.5 bg-[#EDF2EC] border border-[#C6D8C6] text-[#2E5230] text-[10px] font-semibold rounded-[2px] hover:bg-[#E2EBE1]"
                            >
                              Publish
                            </button>
                          )}
                        </div>
                      ) : null}

                      <div className="flex items-center gap-1 pt-0.5">
                        <button
                          onClick={() => openEditModal(adv)}
                          className="text-[10px] text-[#3F4634] hover:underline"
                        >
                          Edit Profile
                        </button>
                        <span className="text-[#DED6C8]">|</span>
                        <button
                          onClick={() => setConfirmModal({ action: 'DELETE', lawyer: adv })}
                          className="text-[10px] text-[#8B3F3F] hover:underline"
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* 5. Add / Edit Lawyer Profile Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 bg-[#242321]/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-[#FCFAF5] border border-[#DED6C8] max-w-2xl w-full p-6 rounded-[2px] shadow-xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[#DED6C8] pb-3">
              <div>
                <span className="font-mono text-[10px] uppercase font-bold text-[#3F4634] block">
                  Platform Admin • Lawyer Directory Management
                </span>
                <h3 className="font-serif font-bold text-base text-[#242321] mt-0.5">
                  {editingLawyer ? `Edit Lawyer Profile: ${editingLawyer.fullName}` : 'Add Lawyer Profile'}
                </h3>
              </div>
              <button
                onClick={() => setIsAddModalOpen(false)}
                className="text-[#6F6A61] hover:text-[#242321] text-xs font-mono p-1"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSaveLawyer} className="space-y-4 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-[#242321] mb-1">
                    Full Legal Name <span className="text-[#8B3F3F]">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.fullName}
                    onChange={(e) => setFormData({ ...formData, fullName: e.target.value })}
                    placeholder="Advocate Radhika Swaminathan"
                    className="w-full px-2.5 py-1.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] focus:outline-none focus:border-[#3F4634]"
                  />
                </div>

                <div>
                  <label className="block font-medium text-[#242321] mb-1">
                    Professional Title
                  </label>
                  <input
                    type="text"
                    value={formData.professionalTitle}
                    onChange={(e) => setFormData({ ...formData, professionalTitle: e.target.value })}
                    placeholder="Advocate / Senior Counsel / Partner"
                    className="w-full px-2.5 py-1.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] focus:outline-none focus:border-[#3F4634]"
                  />
                </div>
              </div>

              {/* Private Contact Fields */}
              <div className="p-3 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] space-y-3">
                <span className="font-mono text-[10px] font-bold uppercase text-[#3F4634] block">
                  🔒 Private Administrative Contact (Never Disclosed to Clients)
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block font-medium text-[#242321] mb-1">
                      Email Address <span className="text-[#8B3F3F]">*</span>
                    </label>
                    <input
                      type="email"
                      required
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      placeholder="advocate@chambers.internal"
                      className="w-full px-2.5 py-1.5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] focus:outline-none focus:border-[#3F4634]"
                    />
                  </div>

                  <div>
                    <label className="block font-medium text-[#242321] mb-1">
                      Phone Number
                    </label>
                    <input
                      type="text"
                      value={formData.phoneNumber}
                      onChange={(e) => setFormData({ ...formData, phoneNumber: e.target.value })}
                      placeholder="+91 98765 43210"
                      className="w-full px-2.5 py-1.5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] focus:outline-none focus:border-[#3F4634]"
                    />
                  </div>
                </div>

                <div>
                  <label className="block font-medium text-[#242321] mb-1">
                    Internal Verification Notes
                  </label>
                  <input
                    type="text"
                    value={formData.internalNotes}
                    onChange={(e) => setFormData({ ...formData, internalNotes: e.target.value })}
                    placeholder="Verification check details, certificate verification date, or bar council confirmation ID..."
                    className="w-full px-2.5 py-1.5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] focus:outline-none focus:border-[#3F4634]"
                  />
                </div>
              </div>

              {/* Chambers & Enrolment */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-[#242321] mb-1">
                    Chambers / Law Firm
                  </label>
                  <input
                    type="text"
                    value={formData.firmName}
                    onChange={(e) => setFormData({ ...formData, firmName: e.target.value })}
                    placeholder="Swaminathan & Partners Chambers"
                    className="w-full px-2.5 py-1.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] focus:outline-none focus:border-[#3F4634]"
                  />
                </div>

                <div>
                  <label className="block font-medium text-[#242321] mb-1">
                    Bar Council Enrolment Number <span className="text-[#8B3F3F]">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.barCouncilNumber}
                    onChange={(e) => setFormData({ ...formData, barCouncilNumber: e.target.value })}
                    placeholder="D/1429/2012"
                    className="w-full px-2.5 py-1.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] focus:outline-none focus:border-[#3F4634]"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-[#242321] mb-1">
                    State Bar Council <span className="text-[#8B3F3F]">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.stateBarCouncil}
                    onChange={(e) => setFormData({ ...formData, stateBarCouncil: e.target.value })}
                    placeholder="Bar Council of Delhi"
                    className="w-full px-2.5 py-1.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] focus:outline-none focus:border-[#3F4634]"
                  />
                </div>

                <div>
                  <label className="block font-medium text-[#242321] mb-1">
                    Admitted Jurisdictions <span className="text-[#8B3F3F]">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.admittedJurisdictions}
                    onChange={(e) => setFormData({ ...formData, admittedJurisdictions: e.target.value })}
                    placeholder="Supreme Court of India, Delhi High Court"
                    className="w-full px-2.5 py-1.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] focus:outline-none focus:border-[#3F4634]"
                  />
                </div>
              </div>

              {/* Qualifications, Practice & Languages */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block font-medium text-[#242321] mb-1">
                    Approved Qualifications
                  </label>
                  <input
                    type="text"
                    value={formData.qualifications}
                    onChange={(e) => setFormData({ ...formData, qualifications: e.target.value })}
                    placeholder="B.A. LL.B. (Hons.), LL.M."
                    className="w-full px-2.5 py-1.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] focus:outline-none focus:border-[#3F4634]"
                  />
                </div>

                <div>
                  <label className="block font-medium text-[#242321] mb-1">
                    Practice Areas (comma-separated) <span className="text-[#8B3F3F]">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.practiceAreas}
                    onChange={(e) => setFormData({ ...formData, practiceAreas: e.target.value })}
                    placeholder="Corporate Contracts, Technology & SaaS"
                    className="w-full px-2.5 py-1.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] focus:outline-none focus:border-[#3F4634]"
                  />
                </div>

                <div>
                  <label className="block font-medium text-[#242321] mb-1">
                    Languages (comma-separated)
                  </label>
                  <input
                    type="text"
                    value={formData.languages}
                    onChange={(e) => setFormData({ ...formData, languages: e.target.value })}
                    placeholder="English, Hindi, Bengali"
                    className="w-full px-2.5 py-1.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] focus:outline-none focus:border-[#3F4634]"
                  />
                </div>
              </div>

              {/* Experience, Languages & Pricing */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block font-medium text-[#242321] mb-1">
                    Years Experience
                  </label>
                  <input
                    type="number"
                    min={0}
                    max={70}
                    value={formData.experienceYears}
                    onChange={(e) => setFormData({ ...formData, experienceYears: Number(e.target.value) })}
                    className="w-full px-2.5 py-1.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] focus:outline-none focus:border-[#3F4634]"
                  />
                </div>

                <div>
                  <label className="block font-medium text-[#242321] mb-1">
                    Consultation Fee (INR)
                  </label>
                  <input
                    type="text"
                    value={formData.consultationFee}
                    onChange={(e) => setFormData({ ...formData, consultationFee: e.target.value })}
                    placeholder="INR 5,000 / 30 mins"
                    className="w-full px-2.5 py-1.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] focus:outline-none focus:border-[#3F4634]"
                  />
                </div>

                <div>
                  <label className="block font-medium text-[#242321] mb-1">
                    Duration (Minutes)
                  </label>
                  <input
                    type="number"
                    min={15}
                    max={180}
                    value={formData.consultationDurationMinutes}
                    onChange={(e) => setFormData({ ...formData, consultationDurationMinutes: Number(e.target.value) })}
                    className="w-full px-2.5 py-1.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] focus:outline-none focus:border-[#3F4634]"
                  />
                </div>
              </div>

              <div>
                <label className="block font-medium text-[#242321] mb-1">
                  Professional Biography
                </label>
                <textarea
                  rows={2}
                  value={formData.bio}
                  onChange={(e) => setFormData({ ...formData, bio: e.target.value })}
                  placeholder="Specialist in cross-border software agreements and corporate risk..."
                  className="w-full px-2.5 py-1.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] focus:outline-none focus:border-[#3F4634]"
                />
              </div>

              <div className="pt-2 flex items-center justify-between border-t border-[#DED6C8]">
                <label className="flex items-center gap-2 cursor-pointer text-xs text-[#242321]">
                  <input
                    type="checkbox"
                    checked={formData.isAvailableForInquiries}
                    onChange={(e) => setFormData({ ...formData, isAvailableForInquiries: e.target.checked })}
                    className="accent-[#3F4634]"
                  />
                  <span>Mark as currently available for client consultation inquiries</span>
                </label>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setIsAddModalOpen(false)}
                    className="px-3 py-1.5 bg-[#FCFAF5] border border-[#DED6C8] text-[#242321] text-xs font-medium rounded-[2px] hover:bg-[#F7F3EA]"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={actionLoading}
                    className="px-4 py-1.5 bg-[#3F4634] text-[#FCFAF5] text-xs font-semibold rounded-[2px] hover:bg-[#2C3124] disabled:opacity-50"
                  >
                    {actionLoading ? 'Saving...' : editingLawyer ? 'Update Profile' : 'Save & Onboard'}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 6. Confirmation Action Dialog Modal */}
      {confirmModal && (
        <div className="fixed inset-0 z-50 bg-[#242321]/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-[#FCFAF5] border border-[#DED6C8] max-w-md w-full p-5 rounded-[2px] shadow-lg space-y-3.5">
            <div className="border-b border-[#DED6C8] pb-2">
              <span className="font-mono text-[10px] uppercase font-bold text-[#3F4634] block">
                Administrative Confirmation
              </span>
              <h3 className="font-serif font-bold text-base text-[#242321] mt-0.5">
                {confirmModal.action === 'VERIFY' && `Verify Advocate Credentials`}
                {confirmModal.action === 'REJECT' && `Reject Advocate Credentials`}
                {confirmModal.action === 'PUBLISH' && `Publish to Client Directory`}
                {confirmModal.action === 'UNPUBLISH' && `Unpublish from Client Directory`}
                {confirmModal.action === 'TOGGLE_AVAILABILITY' && `Toggle Inquiry Availability`}
                {confirmModal.action === 'DELETE' && `Remove Advocate Profile`}
              </h3>
            </div>

            <p className="text-xs text-[#6F6A61] leading-relaxed">
              {confirmModal.action === 'VERIFY' && (
                <>You are certifying that the Bar Council enrolment number <strong className="text-[#242321]">{confirmModal.lawyer.barCouncilNumber}</strong> for <strong className="text-[#242321]">{confirmModal.lawyer.fullName}</strong> has been verified against the official Bar Council registry.</>
              )}
              {confirmModal.action === 'REJECT' && (
                <>You are marking the credentials for <strong className="text-[#242321]">{confirmModal.lawyer.fullName}</strong> as rejected. This advocate will be blocked from receiving client inquiries.</>
              )}
              {confirmModal.action === 'PUBLISH' && (
                <>Publishing <strong className="text-[#242321]">{confirmModal.lawyer.fullName}</strong> will make their verified qualifications visible in the client &quot;Get Legal Help&quot; directory.</>
              )}
              {confirmModal.action === 'UNPUBLISH' && (
                <>Unpublishing will immediately remove <strong className="text-[#242321]">{confirmModal.lawyer.fullName}</strong> from client view. Existing consultation inquiries will remain unaffected.</>
              )}
              {confirmModal.action === 'TOGGLE_AVAILABILITY' && (
                <>Change inquiry intake availability status for <strong className="text-[#242321]">{confirmModal.lawyer.fullName}</strong>.</>
              )}
              {confirmModal.action === 'DELETE' && (
                <>Permanently remove the profile for <strong className="text-[#242321]">{confirmModal.lawyer.fullName}</strong> (Bar ID: {confirmModal.lawyer.barCouncilNumber}) from the platform registry. This action is irreversible.</>
              )}
            </p>

            {confirmModal.action === 'REJECT' && (
              <div>
                <label className="block text-[11px] font-mono text-[#6F6A61] mb-1">
                  Reason for Rejection:
                </label>
                <input
                  type="text"
                  value={confirmModal.rejectionReason || ''}
                  onChange={(e) => setConfirmModal({ ...confirmModal, rejectionReason: e.target.value })}
                  placeholder="e.g. Bar Council enrollment record not active in State Bar ledger"
                  className="w-full px-2.5 py-1.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px] text-xs text-[#242321] focus:outline-none focus:border-[#3F4634]"
                />
              </div>
            )}

            <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-[#DED6C8]">
              <button
                onClick={() => setConfirmModal(null)}
                className="px-3 py-1.5 bg-[#FCFAF5] border border-[#DED6C8] text-[#242321] text-xs font-medium rounded-[2px] hover:bg-[#F7F3EA]"
              >
                Cancel
              </button>
              <button
                onClick={executeConfirmAction}
                disabled={actionLoading}
                className={`px-4 py-1.5 text-xs font-semibold rounded-[2px] text-[#FCFAF5] transition-colors disabled:opacity-50 ${
                  confirmModal.action === 'DELETE' || confirmModal.action === 'REJECT'
                    ? 'bg-[#A33B3B] hover:bg-[#8B2F2F]'
                    : 'bg-[#3F4634] hover:bg-[#2C3124]'
                }`}
              >
                {actionLoading ? 'Processing...' : 'Confirm Action'}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
