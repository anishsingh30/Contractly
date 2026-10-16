'use client';

import React, { useState } from 'react';
import { useContractly } from '@/context/contractly-context';
import { StatusPill } from '@/components/ui/status-pill';
import { Button } from '@/components/ui/button';
import { HelpTooltip } from '@/components/ui/help-tooltip';
import { formatRoleName } from '@/components/navigation/top-bar';

interface ContractTableProps {
  onOpenContract: (id: string) => void;
  onRequestNew: () => void;
}

export function ContractTable({ onOpenContract, onRequestNew }: ContractTableProps) {
  const { contracts, searchQuery, accountType, businessRole, hasPermission } = useContractly();
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [departmentFilter, setDepartmentFilter] = useState<string>('ALL');

  const filteredContracts = contracts.filter((c) => {
    const matchesSearch =
      searchQuery === '' ||
      c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.counterparty.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.contractId.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.contractType.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesStatus = statusFilter === 'ALL' || c.status === statusFilter;
    const matchesDept = departmentFilter === 'ALL' || c.department === departmentFilter;

    return matchesSearch && matchesStatus && matchesDept;
  });

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0
    }).format(val);
  };

  return (
    <div className="space-y-5">
      {/* 1. Clear Page Header answering: Where am I? What does this page do? (Instruction 1 & 23) */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#DED6C8]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-serif font-bold text-[#242321]">
              My Contracts
            </h1>
            <span className="text-xs font-mono text-[#6F6A61] px-2 py-0.5 bg-[#EFECE3] border border-[#DED6C8] rounded-[2px]">
              {contracts.length} agreements
            </span>
            {accountType === 'BUSINESS' && (
              <span className="text-xs text-[#3F4634] font-medium px-2 py-0.5 bg-[#F7F3EA] border border-[#DED6C8] rounded-[2px]">
                Role: {formatRoleName(businessRole)}
              </span>
            )}
          </div>
          <p className="text-xs text-[#6F6A61] mt-1 leading-relaxed">
            All your agreements in one place. Click any contract to read plain-English explanations, check for potential problems, and view upcoming dates.
          </p>
        </div>

        {hasPermission('contracts:create') && (
          <div className="flex items-center gap-2 shrink-0">
            <Button onClick={onRequestNew} variant="primary" size="sm" className="font-semibold text-xs">
              + Upload Contract
            </Button>
          </div>
        )}
      </div>

      {/* 2. Plain-Language Filter Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-[#FCFAF5] p-3 border border-[#DED6C8] rounded-[2px]">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5">
            <label className="text-xs text-[#6F6A61] font-medium" htmlFor="status-filter">
              Filter by Status:
            </label>
            <select
              id="status-filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-[#F7F3EA] border border-[#DED6C8] text-xs text-[#242321] px-2 py-1 rounded-[2px]"
            >
              <option value="ALL">All Statuses</option>
              <option value="ACTIVE">Active (In effect)</option>
              <option value="UNDER_REVIEW">Needs Review</option>
              <option value="NEGOTIATION">Being Negotiated</option>
              <option value="PENDING_APPROVAL">Waiting for Approval</option>
            </select>
          </div>

          {accountType === 'BUSINESS' && (
            <div className="flex items-center gap-1.5">
              <label className="text-xs text-[#6F6A61] font-medium" htmlFor="dept-filter">
                Department:
              </label>
              <select
                id="dept-filter"
                value={departmentFilter}
                onChange={(e) => setDepartmentFilter(e.target.value)}
                className="bg-[#F7F3EA] border border-[#DED6C8] text-xs text-[#242321] px-2 py-1 rounded-[2px]"
              >
                <option value="ALL">All Departments</option>
                <option value="Procurement">Procurement</option>
                <option value="Legal">Legal</option>
                <option value="HR">HR</option>
                <option value="Operations">Operations</option>
                <option value="Engineering">Engineering</option>
              </select>
            </div>
          )}
        </div>

        <div className="text-xs text-[#6F6A61]">
          Showing <strong>{filteredContracts.length}</strong> of {contracts.length} contracts
        </div>
      </div>

      {/* 3. Responsive Table / Card Container */}
      <div className="bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] overflow-hidden">
        {/* Desktop View Table */}
        <div className="hidden md:block overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-[#F7F3EA] text-[#6F6A61] border-b border-[#DED6C8] font-medium text-[11px]">
                <th className="py-2.5 px-3">Contract Title</th>
                <th className="py-2.5 px-3">
                  Other Party
                  <HelpTooltip term="Other Party (Counterparty)" text="The company or person you are signing this contract with." />
                </th>
                <th className="py-2.5 px-3">
                  Status
                  <HelpTooltip term="Status" text="Whether the contract is active, waiting for review, or being negotiated." />
                </th>
                <th className="py-2.5 px-3">
                  Health & Concerns
                  <HelpTooltip term="Potential Concerns" text="Contractly checks for one-sided liability, strict cancellation clauses, or unusual terms." />
                </th>
                <th className="py-2.5 px-3">Ends On</th>
                <th className="py-2.5 px-3">Annual Amount</th>
                <th className="py-2.5 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#DED6C8]">
              {filteredContracts.map((contract) => (
                <tr
                  key={contract.id}
                  className="hover:bg-[#F7F3EA]/70 transition-colors cursor-pointer group"
                  onClick={() => onOpenContract(contract.id)}
                >
                  <td className="py-3 px-3">
                    <div className="font-semibold text-[#242321] group-hover:text-[#3F4634] transition-colors">
                      {contract.title}
                    </div>
                    <div className="text-[11px] text-[#6F6A61] mt-0.5 font-mono">
                      {contract.contractType} • {contract.contractId}
                    </div>
                  </td>
                  <td className="py-3 px-3 text-[#242321] font-medium">{contract.counterparty}</td>
                  <td className="py-3 px-3">
                    <StatusPill status={contract.status} />
                  </td>
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-2">
                      {contract.riskLevel === 'HIGH' || contract.riskLevel === 'CRITICAL' ? (
                        <span className="text-[11px] text-[#8B3F3F] font-medium inline-flex items-center gap-1">
                          ⚠️ Potential Concern
                        </span>
                      ) : contract.riskLevel === 'MEDIUM' ? (
                        <span className="text-[11px] text-[#9A6A32] font-medium">Needs Attention</span>
                      ) : (
                        <span className="text-[11px] text-[#4F6B50] font-medium">Looks Good</span>
                      )}
                      <span className="text-[10px] text-[#6F6A61] font-mono" title="Risk score details">
                        ({contract.compositeRiskScore}/100)
                      </span>
                    </div>
                  </td>
                  <td className="py-3 px-3 text-[#6F6A61] font-mono">{contract.expiryDate}</td>
                  <td className="py-3 px-3 font-mono font-medium text-[#242321]">
                    {formatCurrency(contract.value)}
                  </td>
                  <td className="py-3 px-3 text-right">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        onOpenContract(contract.id);
                      }}
                    >
                      View Details →
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Mobile View: Clean Readable Cards (Instruction 26) */}
        <div className="md:hidden divide-y divide-[#DED6C8]">
          {filteredContracts.map((contract) => (
            <div
              key={contract.id}
              onClick={() => onOpenContract(contract.id)}
              className="p-4 space-y-2.5 hover:bg-[#F7F3EA] transition-colors cursor-pointer"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h3 className="font-semibold text-xs text-[#242321]">{contract.title}</h3>
                  <p className="text-[11px] text-[#6F6A61] mt-0.5">{contract.counterparty}</p>
                </div>
                <StatusPill status={contract.status} />
              </div>

              <div className="flex flex-wrap items-center justify-between text-xs text-[#6F6A61] pt-1">
                <span>Ends: <strong className="text-[#242321] font-mono">{contract.expiryDate}</strong></span>
                <span className="font-mono text-[#242321] font-medium">{formatCurrency(contract.value)}</span>
              </div>

              <div className="pt-2 border-t border-[#DED6C8]/60 flex items-center justify-between">
                <span className="text-[11px]">
                  {contract.riskLevel === 'HIGH' || contract.riskLevel === 'CRITICAL' ? (
                    <span className="text-[#8B3F3F] font-medium">⚠️ Potential Concern</span>
                  ) : contract.riskLevel === 'MEDIUM' ? (
                    <span className="text-[#9A6A32] font-medium">Needs Attention</span>
                  ) : (
                    <span className="text-[#4F6B50] font-medium">Looks Good</span>
                  )}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    onOpenContract(contract.id);
                  }}
                >
                  View Details →
                </Button>
              </div>
            </div>
          ))}
        </div>

        {/* Empty State (Instruction 21) */}
        {filteredContracts.length === 0 && (
          <div className="py-12 px-4 text-center space-y-3">
            <h3 className="text-base font-serif font-bold text-[#242321]">No contracts found</h3>
            <p className="text-xs text-[#6F6A61] max-w-md mx-auto leading-relaxed">
              Upload your first contract and Contractly will help you understand it, find potential concerns, and keep track of important dates.
            </p>
            <Button onClick={onRequestNew} variant="primary" size="sm" className="mt-2">
              + Upload Contract
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
