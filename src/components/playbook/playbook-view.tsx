'use client';

import React, { useState, useEffect } from 'react';
import { PlaybookRule } from '@/types/contractly';
import { fetchPlaybookRulesFromBackend, createPlaybookRuleInBackend } from '@/lib/api-client';
import { Button } from '@/components/ui/button';
import { useContractly } from '@/context/contractly-context';

export function PlaybookView() {
  const { hasPermission, addToast } = useContractly();
  const [rules, setRules] = useState<PlaybookRule[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [category, setCategory] = useState<string>('');
  const [preferredStandard, setPreferredStandard] = useState<string>('');
  const [fallbackAcceptable, setFallbackAcceptable] = useState<string>('');
  const [prohibitedTerms, setProhibitedTerms] = useState<string>('');
  const [guidance, setGuidance] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const loadRules = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchPlaybookRulesFromBackend();
      setRules(data);
    } catch (err) {
      setError('We could not load your negotiation playbook rules. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRules();
  }, []);

  const handleCreateRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!category.trim() || !preferredStandard.trim() || !fallbackAcceptable.trim()) {
      addToast('Missing Details', 'Please complete the category, standard, and fallback fields.', 'warning');
      return;
    }
    setIsSubmitting(true);
    try {
      const termsList = prohibitedTerms.split(',').map((t) => t.trim()).filter(Boolean);
      const created = await createPlaybookRuleInBackend({
        category: category.trim(),
        preferredStandard: preferredStandard.trim(),
        fallbackAcceptable: fallbackAcceptable.trim(),
        prohibitedTerms: termsList,
        negotiationGuidance: guidance.trim() || 'Review against standard organizational positions.'
      });
      if (created) {
        addToast('Rule Created', `Negotiation rule for ${created.category} saved.`, 'success');
        setCategory('');
        setPreferredStandard('');
        setFallbackAcceptable('');
        setProhibitedTerms('');
        setGuidance('');
        setShowAddModal(false);
        await loadRules();
      } else {
        addToast('Action Failed', 'Could not create rule. Check permissions.', 'danger');
      }
    } catch (err) {
      addToast('Error', 'An error occurred while creating the negotiation rule.', 'danger');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#DED6C8]">
        <div>
          <h1 className="text-xl font-serif font-bold text-[#242321]">
            Negotiation Rules
          </h1>
          <p className="text-xs text-[#6F6A61] mt-1 leading-relaxed">
            Guidelines for what terms your team can agree to when reviewing and negotiating contracts.
          </p>
        </div>

        {(hasPermission('playbook:manage') || hasPermission('*')) && (
          <Button onClick={() => setShowAddModal(true)} variant="primary" size="sm">
            + Add Negotiation Rule
          </Button>
        )}
      </div>

      {/* Add Rule Form */}
      {showAddModal && (
        <div className="p-4 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-3">
          <div className="flex items-center justify-between border-b border-[#DED6C8] pb-2">
            <h2 className="text-sm font-semibold text-[#242321]">New Negotiation Playbook Rule</h2>
            <button
              onClick={() => setShowAddModal(false)}
              className="text-xs text-[#6F6A61] hover:text-[#242321]"
            >
              ✕ Cancel
            </button>
          </div>
          <form onSubmit={handleCreateRule} className="space-y-3 text-xs">
            <div>
              <label className="block text-[#6F6A61] mb-1">Clause Category</label>
              <input
                type="text"
                required
                placeholder="e.g. Limitation of Liability, Payment Terms, Data Privacy"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] p-2 text-xs text-[#242321]"
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[#6F6A61] mb-1">Preferred Standard (Target Stance)</label>
                <textarea
                  required
                  rows={3}
                  placeholder="e.g. Aggregate liability capped at 12 months fees paid."
                  value={preferredStandard}
                  onChange={(e) => setPreferredStandard(e.target.value)}
                  className="w-full bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] p-2 text-xs text-[#242321]"
                />
              </div>
              <div>
                <label className="block text-[#6F6A61] mb-1">Acceptable Alternative (Fallback)</label>
                <textarea
                  required
                  rows={3}
                  placeholder="e.g. 1.5x annual fees with mutual exclusions for breach of confidentiality."
                  value={fallbackAcceptable}
                  onChange={(e) => setFallbackAcceptable(e.target.value)}
                  className="w-full bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] p-2 text-xs text-[#242321]"
                />
              </div>
            </div>
            <div>
              <label className="block text-[#6F6A61] mb-1">Prohibited Terms (comma-separated)</label>
              <input
                type="text"
                placeholder="e.g. uncapped liability, waiver of gross negligence"
                value={prohibitedTerms}
                onChange={(e) => setProhibitedTerms(e.target.value)}
                className="w-full bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] p-2 text-xs text-[#242321]"
              />
            </div>
            <div>
              <label className="block text-[#6F6A61] mb-1">Negotiation Guidance / Helpful Tips</label>
              <input
                type="text"
                placeholder="e.g. If counterparty pushes back, insist on reciprocal indemnification."
                value={guidance}
                onChange={(e) => setGuidance(e.target.value)}
                className="w-full bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] p-2 text-xs text-[#242321]"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2 border-t border-[#DED6C8]">
              <Button type="button" onClick={() => setShowAddModal(false)} variant="secondary" size="sm">
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting} variant="primary" size="sm">
                {isSubmitting ? 'Saving...' : 'Save Playbook Rule'}
              </Button>
            </div>
          </form>
        </div>
      )}

      {loading && (
        <div className="p-8 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-center text-[#6F6A61] text-xs">
          Loading your negotiation rules...
        </div>
      )}

      {error && !loading && (
        <div className="p-8 bg-[#FDF5F5] border border-[#E2BDBF] rounded-[2px] text-center text-[#8B3F3F] text-xs">
          {error}
        </div>
      )}

      {!loading && !error && rules.length === 0 && (
        <div className="p-8 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-center text-[#6F6A61] space-y-2">
          <h2 className="font-semibold text-sm text-[#242321]">No negotiation rules configured yet</h2>
          <p className="text-xs">Establish company-specific standards for liability caps, indemnification, and payment terms to guide team reviews.</p>
          {(hasPermission('playbook:manage') || hasPermission('*')) && (
            <div className="pt-2">
              <Button onClick={() => setShowAddModal(true)} variant="primary" size="sm">
                + Add Your First Negotiation Rule
              </Button>
            </div>
          )}
        </div>
      )}

      {!loading && !error && rules.length > 0 && (
        <div className="space-y-4">
          {rules.map((rule) => (
            <div
              key={rule.id}
              className="p-5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-4"
            >
              <div className="flex items-center justify-between pb-2 border-b border-[#DED6C8]">
                <h2 className="font-semibold text-sm text-[#242321]">{rule.category}</h2>
                <span className="font-mono text-[11px] text-[#6F6A61]">
                  Updated: {rule.lastUpdated}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                {/* Preferred Standard */}
                <div className="p-3.5 bg-[#EDF2EC]/60 border border-[#C6D8C6] rounded-[2px] space-y-1">
                  <span className="text-[10px] uppercase font-bold text-[#2E5230] block">
                    Preferred Standard (Goal)
                  </span>
                  <p className="text-[#242321] font-serif leading-relaxed italic">
                    &quot;{rule.preferredStandard}&quot;
                  </p>
                </div>

                {/* Acceptable Fallback */}
                <div className="p-3.5 bg-[#F7EFE4]/60 border border-[#E5D2B8] rounded-[2px] space-y-1">
                  <span className="text-[10px] uppercase font-bold text-[#7A4D1A] block">
                    Acceptable Alternative
                  </span>
                  <p className="text-[#242321] font-serif leading-relaxed italic">
                    &quot;{rule.fallbackAcceptable}&quot;
                  </p>
                </div>
              </div>

              {/* Prohibited Terms */}
              {rule.prohibitedTerms && rule.prohibitedTerms.length > 0 && (
                <div className="p-3 bg-[#F7EDED]/60 border border-[#E2BDBF] rounded-[2px] text-xs">
                  <span className="text-[10px] uppercase font-bold text-[#8B3F3F] block mb-1">
                    Terms to Avoid (May Require Lawyer Review)
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {rule.prohibitedTerms.map((term, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 bg-[#FCFAF5] border border-[#E2BDBF] text-[#8B3F3F] font-mono text-[11px] rounded-[2px]"
                      >
                        ⚠️ &quot;{term}&quot;
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Negotiation Guidance */}
              {rule.negotiationGuidance && (
                <div className="text-xs text-[#6F6A61] pt-1">
                  <strong className="text-[#242321]">Helpful Tips:</strong> {rule.negotiationGuidance}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
