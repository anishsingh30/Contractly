'use client';

import React, { useState } from 'react';
import { useContractly } from '@/context/contractly-context';
import { StatusPill } from '@/components/ui/status-pill';
import { Button } from '@/components/ui/button';
import { HelpTooltip } from '@/components/ui/help-tooltip';

export function ApprovalFlow() {
  const { contracts, approveStep, rejectStep, businessRole, hasPermission } = useContractly();
  const [commentInput, setCommentInput] = useState<{ [key: string]: string }>({});

  // Filter contracts with approval workflows
  const contractsWithApprovals = contracts.filter((c) => c.approvalSteps && c.approvalSteps.length > 0);

  return (
    <div className="space-y-6">
      <div className="pb-3 border-b border-[#DED6C8]">
        <h1 className="text-xl font-serif font-bold text-[#242321]">
          Approvals
        </h1>
        <p className="text-xs text-[#6F6A61] mt-1 leading-relaxed">
          Review agreements waiting for sign-off from your department, finance, or legal team before they take effect.
        </p>
      </div>

      <div className="space-y-6">
        {contractsWithApprovals.map((contract) => (
          <div
            key={contract.id}
            className="p-5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] space-y-4"
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-[#DED6C8]">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-semibold text-[#242321]">{contract.title}</h2>
                  <span className="font-mono text-xs text-[#6F6A61]">({contract.contractId})</span>
                </div>
                <p className="text-xs text-[#6F6A61] mt-0.5">
                  With: <strong className="text-[#242321]">{contract.counterparty}</strong> • Value: ₹{(contract.value / 100000).toFixed(1)} Lakhs
                </p>
              </div>
              <div className="flex items-center gap-2">
                <StatusPill status={contract.status} showExplanation={true} />
              </div>
            </div>

            {/* Approval Steps */}
            <div className="space-y-3">
              <h3 className="text-xs font-semibold text-[#242321]">
                Sign-off Progress
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {contract.approvalSteps.map((step) => {
                  const isApproved = step.decision === 'APPROVED';
                  const isPending = step.decision === 'PENDING';
                  const canAct = isPending && (hasPermission('approvals:decide') || hasPermission('approvals:manage') || hasPermission('approvals:finance') || hasPermission('*'));

                  return (
                    <div
                      key={step.id}
                      className={`p-3.5 border rounded-[2px] flex flex-col justify-between ${
                        isApproved
                          ? 'bg-[#EDF2EC]/60 border-[#C6D8C6]'
                          : isPending
                          ? 'bg-[#F7EFE4]/50 border-[#E5D2B8]'
                          : 'bg-[#FCFAF5] border-[#DED6C8]'
                      }`}
                    >
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[11px] font-medium text-[#6F6A61]">
                            Step {step.stepOrder}
                          </span>
                          <StatusPill status={step.decision} />
                        </div>
                        <h4 className="font-semibold text-xs text-[#242321]">{step.role}</h4>
                        <p className="text-[11px] text-[#6F6A61] mt-0.5">Assigned to: {step.assignedUser}</p>

                        {step.comments && (
                          <p className="mt-2 text-[11px] text-[#242321] italic bg-[#FCFAF5] p-2 border border-[#DED6C8]/60 rounded-[2px]">
                            &quot;{step.comments}&quot;
                          </p>
                        )}
                        {step.decidedAt && (
                          <p className="mt-1 font-mono text-[10px] text-[#6F6A61]">
                            Signed off: {step.decidedAt}
                          </p>
                        )}
                      </div>

                      {canAct && (
                        <div className="mt-3 pt-3 border-t border-[#DED6C8]/60 space-y-2">
                          <input
                            type="text"
                            placeholder="Add sign-off notes (optional)..."
                            value={commentInput[step.id] || ''}
                            onChange={(e) =>
                              setCommentInput({ ...commentInput, [step.id]: e.target.value })
                            }
                            className="w-full bg-[#FCFAF5] border border-[#DED6C8] text-xs text-[#242321] p-1.5 rounded-[2px]"
                          />
                          <div className="flex gap-2">
                            <Button
                              onClick={() => {
                                approveStep(contract.id, step.id, commentInput[step.id]);
                                setCommentInput({ ...commentInput, [step.id]: '' });
                              }}
                              variant="primary"
                              size="sm"
                              className="flex-1 text-xs font-semibold"
                            >
                              ✓ Approve
                            </Button>
                            <Button
                              onClick={() => {
                                rejectStep(contract.id, step.id, commentInput[step.id]);
                                setCommentInput({ ...commentInput, [step.id]: '' });
                              }}
                              variant="outline"
                              size="sm"
                              className="flex-1 text-xs font-semibold text-[#8B3F3F] border-[#E2BDBF] hover:bg-[#FDF2F2]"
                            >
                              ✕ Reject
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        ))}

        {contractsWithApprovals.length === 0 && (
          <div className="p-8 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-center text-[#6F6A61] space-y-2">
            <h3 className="font-semibold text-sm text-[#242321]">All clear</h3>
            <p className="text-xs">No contracts are currently waiting for your sign-off.</p>
          </div>
        )}
      </div>
    </div>
  );
}
