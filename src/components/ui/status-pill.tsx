'use client';

import React from 'react';
import { ContractStatus, ObligationStatus, RiskLevel } from '@/types/contractly';

interface StatusPillProps {
  status: ContractStatus | ObligationStatus | RiskLevel | string;
  className?: string;
  showExplanation?: boolean;
}

export function StatusPill({ status, className = '', showExplanation = false }: StatusPillProps) {
  let dotColor = '#6F6A61';
  let bgColor = '#EFECE3';
  let textColor = '#242321';
  let borderColor = '#DED6C8';

  let displayLabel = status.replace(/_/g, ' ');
  let explanation = '';

  switch (status) {
    case 'ACTIVE':
      dotColor = '#4F6B50';
      bgColor = '#EDF2EC';
      textColor = '#2E5230';
      borderColor = '#C6D8C6';
      displayLabel = 'Active';
      explanation = 'Currently in effect';
      break;

    case 'APPROVED':
    case 'EXECUTED':
      dotColor = '#4F6B50';
      bgColor = '#EDF2EC';
      textColor = '#2E5230';
      borderColor = '#C6D8C6';
      displayLabel = 'Approved';
      explanation = 'All sign-offs completed';
      break;

    case 'FULFILLED':
    case 'RESOLVED':
      dotColor = '#4F6B50';
      bgColor = '#EDF2EC';
      textColor = '#2E5230';
      borderColor = '#C6D8C6';
      displayLabel = 'Completed';
      explanation = 'Obligation satisfied';
      break;

    case 'LOW':
      dotColor = '#4F6B50';
      bgColor = '#EDF2EC';
      textColor = '#2E5230';
      borderColor = '#C6D8C6';
      displayLabel = 'Low Concern';
      explanation = 'Standard, balanced terms';
      break;

    case 'UNDER_REVIEW':
      dotColor = '#9A6A32';
      bgColor = '#F7EFE4';
      textColor = '#7A4D1A';
      borderColor = '#E5D2B8';
      displayLabel = 'Needs Review';
      explanation = 'Someone needs to review this contract';
      break;

    case 'PENDING_APPROVAL':
      dotColor = '#9A6A32';
      bgColor = '#F7EFE4';
      textColor = '#7A4D1A';
      borderColor = '#E5D2B8';
      displayLabel = 'Waiting for Approval';
      explanation = 'Waiting for team sign-off';
      break;

    case 'NEGOTIATION':
      dotColor = '#9A6A32';
      bgColor = '#F7EFE4';
      textColor = '#7A4D1A';
      borderColor = '#E5D2B8';
      displayLabel = 'Being Negotiated';
      explanation = 'Changes are being discussed';
      break;

    case 'IN_RENEWAL':
    case 'DUE_SOON':
      dotColor = '#9A6A32';
      bgColor = '#F7EFE4';
      textColor = '#7A4D1A';
      borderColor = '#E5D2B8';
      displayLabel = 'Expiring Soon';
      explanation = 'Important deadline coming up';
      break;

    case 'MEDIUM':
      dotColor = '#9A6A32';
      bgColor = '#F7EFE4';
      textColor = '#7A4D1A';
      borderColor = '#E5D2B8';
      displayLabel = 'Needs Attention';
      explanation = 'Contains terms to look over';
      break;

    case 'POTENTIAL_BREACH':
    case 'POTENTIAL_NON_COMPLIANCE':
    case 'OVERDUE':
      dotColor = '#8B3F3F';
      bgColor = '#F7EDED';
      textColor = '#8B3F3F';
      borderColor = '#E2BDBF';
      displayLabel = 'Potential Problem';
      explanation = 'Contractly found something that may need attention';
      break;

    case 'HIGH':
      dotColor = '#8B3F3F';
      bgColor = '#F7EDED';
      textColor = '#8B3F3F';
      borderColor = '#E2BDBF';
      displayLabel = 'High Concern';
      explanation = 'Review terms before agreeing';
      break;

    case 'CRITICAL':
      dotColor = '#8B3F3F';
      bgColor = '#F7EDED';
      textColor = '#8B3F3F';
      borderColor = '#E2BDBF';
      displayLabel = 'Important Concern';
      explanation = 'Immediate human review recommended';
      break;

    case 'DRAFT':
      dotColor = '#6F6A61';
      bgColor = '#EFECE3';
      textColor = '#242321';
      borderColor = '#DED6C8';
      displayLabel = 'Draft';
      explanation = 'Not yet sent or finalized';
      break;

    default:
      dotColor = '#6F6A61';
      bgColor = '#EFECE3';
      textColor = '#242321';
      borderColor = '#DED6C8';
      displayLabel = status.replace(/_/g, ' ');
      explanation = '';
      break;
  }

  return (
    <span
      title={explanation ? `${displayLabel} — ${explanation}` : displayLabel}
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium border rounded-[2px] transition-colors ${className}`}
      style={{
        backgroundColor: bgColor,
        color: textColor,
        borderColor: borderColor,
      }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full flex-shrink-0"
        style={{ backgroundColor: dotColor }}
        aria-hidden="true"
      />
      <span className="font-medium">{displayLabel}</span>
      {showExplanation && explanation && (
        <span className="text-[10px] opacity-80 border-l pl-1.5 ml-0.5" style={{ borderColor }}>
          {explanation}
        </span>
      )}
    </span>
  );
}
