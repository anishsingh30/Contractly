'use client';

import React, { useState, useEffect } from 'react';
import { VendorProfile } from '@/types/contractly';
import { fetchVendorsFromBackend, createVendorInBackend } from '@/lib/api-client';
import { StatusPill } from '@/components/ui/status-pill';
import { Button } from '@/components/ui/button';
import { HelpTooltip } from '@/components/ui/help-tooltip';
import { useContractly } from '@/context/contractly-context';
import { formatCurrency } from '@/lib/currency-formatter';

export function VendorGrid() {
  const { addToast, hasPermission } = useContractly();
  const [vendors, setVendors] = useState<VendorProfile[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [newVendorName, setNewVendorName] = useState<string>('');
  const [newVendorEmail, setNewVendorEmail] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const loadVendors = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchVendorsFromBackend();
      setVendors(data);
    } catch (err) {
      setError('We could not load your vendors. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadVendors();
  }, []);

  const handleCreateVendor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newVendorName.trim() || !newVendorEmail.trim()) {
      addToast('Missing Details', 'Please provide a vendor name and contact email.', 'warning');
      return;
    }
    setIsSubmitting(true);
    try {
      const created = await createVendorInBackend({
        name: newVendorName.trim(),
        contactEmail: newVendorEmail.trim(),
        contractCount: 0,
        totalContractValue: 0,
        riskRating: 'LOW'
      });
      if (created) {
        addToast('Vendor Added', `Vendor profile for ${created.name} was successfully created.`, 'success');
        setNewVendorName('');
        setNewVendorEmail('');
        setShowAddModal(false);
        await loadVendors();
      } else {
        addToast('Action Failed', 'Could not create vendor. Please check permissions.', 'danger');
      }
    } catch (err) {
      addToast('Error', 'An error occurred while creating the vendor profile.', 'danger');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#DED6C8]">
        <div>
          <h1 className="text-xl font-serif font-bold text-[#242321]">
            Vendors
          </h1>
          <p className="text-xs text-[#6F6A61] mt-1 leading-relaxed">
            Keep track of the companies you work with, what you pay them, and how reliable they are.
          </p>
        </div>

        {(hasPermission('vendors:manage') || hasPermission('*')) && (
          <Button onClick={() => setShowAddModal(true)} variant="primary" size="sm">
            + Add Vendor
          </Button>
        )}
      </div>

      {/* Add Vendor Modal */}
      {showAddModal && (
        <div className="p-4 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3">
          <div className="flex items-center justify-between border-b border-[#DED6C8] pb-2">
            <h2 className="text-sm font-semibold text-[#242321]">New Vendor Profile</h2>
            <button
              onClick={() => setShowAddModal(false)}
              className="text-xs text-[#6F6A61] hover:text-[#242321]"
            >
              ✕ Cancel
            </button>
          </div>
          <form onSubmit={handleCreateVendor} className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div>
                <label className="block text-[#6F6A61] mb-1">Company / Vendor Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Acme Cloud Services Pvt. Ltd."
                  value={newVendorName}
                  onChange={(e) => setNewVendorName(e.target.value)}
                  className="w-full bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] p-2 text-xs text-[#242321]"
                />
              </div>
              <div>
                <label className="block text-[#6F6A61] mb-1">Contact Email</label>
                <input
                  type="email"
                  required
                  placeholder="e.g. legal-notices@acme.com"
                  value={newVendorEmail}
                  onChange={(e) => setNewVendorEmail(e.target.value)}
                  className="w-full bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] p-2 text-xs text-[#242321]"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" onClick={() => setShowAddModal(false)} variant="secondary" size="sm">
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting} variant="primary" size="sm">
                {isSubmitting ? 'Saving...' : 'Save Vendor Profile'}
              </Button>
            </div>
          </form>
        </div>
      )}

      {loading && (
        <div className="p-8 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-center text-[#6F6A61] text-xs">
          Loading your vendor profiles...
        </div>
      )}

      {error && !loading && (
        <div className="p-8 bg-[#FDF5F5] border border-[#E2BDBF] rounded-[2px] text-center text-[#8B3F3F] text-xs">
          {error}
        </div>
      )}

      {!loading && !error && vendors.length === 0 && (
        <div className="p-8 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-center text-[#6F6A61] space-y-2">
          <h2 className="font-semibold text-sm text-[#242321]">No vendors registered yet</h2>
          <p className="text-xs">Add your first vendor profile to track agreements, committed spend, and compliance reliability.</p>
          {(hasPermission('vendors:manage') || hasPermission('*')) && (
            <div className="pt-2">
              <Button onClick={() => setShowAddModal(true)} variant="primary" size="sm">
                + Add Your First Vendor
              </Button>
            </div>
          )}
        </div>
      )}

      {!loading && !error && vendors.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {vendors.map((vendor) => (
            <div
              key={vendor.id}
              className="p-5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-4"
            >
              <div className="flex items-start justify-between pb-3 border-b border-[#DED6C8]">
                <div>
                  <h2 className="font-semibold text-sm text-[#242321]">{vendor.name}</h2>
                  <p className="text-xs text-[#6F6A61] mt-0.5 font-mono">{vendor.contactEmail}</p>
                </div>
                <StatusPill status={vendor.riskRating} />
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-2.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px]">
                  <span className="text-[10px] uppercase font-mono text-[#6F6A61] block">
                    Active Agreements
                  </span>
                  <span className="font-bold text-sm text-[#242321] mt-0.5 block">
                    {vendor.contractCount}
                  </span>
                </div>

                <div className="p-2.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px]">
                  <span className="text-[10px] uppercase font-mono text-[#6F6A61] block">
                    Total Committed Value
                  </span>
                  <span className="font-bold text-xs font-mono text-[#242321] mt-0.5 block">
                    {formatCurrency(vendor.totalContractValue)}
                  </span>
                </div>
              </div>

              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between py-1 border-b border-[#DED6C8]/60">
                  <span className="text-[#6F6A61]">
                    Reliability Track Record:
                    <HelpTooltip term="SLA Reliability" text="How often this vendor meets their guaranteed service availability." />
                  </span>
                  <span className="font-medium text-[#242321]">{vendor.slaPerformance}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-[#DED6C8]/60">
                  <span className="text-[#6F6A61]">Compliance Score:</span>
                  <span className="font-mono font-medium text-[#2E5230]">
                    {vendor.complianceRating}%
                  </span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-[#6F6A61]">Security Standards:</span>
                  <div className="flex items-center gap-1.5 font-mono text-[10px]">
                    {vendor.soc2Certified && (
                      <span className="px-1.5 py-0.2 bg-[#EDF2EC] text-[#2E5230] border border-[#C6D8C6] rounded-[2px]">
                        SOC2 Certified
                      </span>
                    )}
                    {vendor.gdprCompliant && (
                      <span className="px-1.5 py-0.2 bg-[#EDF2EC] text-[#2E5230] border border-[#C6D8C6] rounded-[2px]">
                        Privacy Verified
                      </span>
                    )}
                    {!vendor.soc2Certified && !vendor.gdprCompliant && (
                      <span className="text-[#6F6A61] italic">Standard</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
