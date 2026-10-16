import { ContractItem } from '@/types/contractly';

/**
 * Standardizes currency formatting across all Contractly views.
 * Supports INR (Indian Numbering format: ₹12,00,000 or ₹3.5 Lakhs), USD ($), EUR (€), GBP (£).
 */
export function formatCurrency(
  val: number | null | undefined,
  currency: string = 'INR',
  options?: { maximumFractionDigits?: number; compact?: boolean }
): string {
  if (val === null || val === undefined || isNaN(val)) {
    return 'Not specified';
  }

  const curr = (currency || 'INR').toUpperCase();
  const digits = options?.maximumFractionDigits ?? 0;

  // Compact Indian notation for lakhs/crores if requested
  if (options?.compact && curr === 'INR') {
    if (Math.abs(val) >= 10_000_000) {
      return `₹${(val / 10_000_000).toFixed(2)} Cr`;
    }
    if (Math.abs(val) >= 100_000) {
      return `₹${(val / 100_000).toFixed(1)} Lakhs`;
    }
  }

  try {
    const locale = curr === 'INR' ? 'en-IN' : curr === 'USD' ? 'en-US' : curr === 'GBP' ? 'en-GB' : 'de-DE';
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: curr,
      maximumFractionDigits: digits
    }).format(val);
  } catch {
    const sym = curr === 'INR' ? '₹' : curr === 'USD' ? '$' : curr === 'EUR' ? '€' : curr === 'GBP' ? '£' : `${curr} `;
    return `${sym}${val.toLocaleString()}`;
  }
}

/**
 * Authoritative contract value display string.
 * Distinguishes genuine zero from unknown/unspecified and unverified values.
 */
export function formatContractValue(
  value: number | null | undefined,
  currency: string = 'INR',
  valueBasis?: string,
  options?: { compact?: boolean }
): string {
  if (valueBasis === 'NEEDS_VERIFICATION') {
    return 'Needs verification';
  }
  if (valueBasis === 'NOT_SPECIFIED' || value === null || value === undefined || isNaN(value)) {
    return 'Not specified';
  }
  if (value === 0 && valueBasis === 'GENUINE_ZERO') {
    const curr = (currency || 'INR').toUpperCase();
    return curr === 'USD' ? '$0 (No fee)' : '₹0 (No fee)';
  }
  return formatCurrency(value, currency, options);
}

/**
 * Calculates committed value totals across eligible agreements:
 * 1. Filters eligible contracts (active / legally binding agreements).
 * 2. Deduplicates multiple versions of the same contract (avoiding double-counting).
 * 3. Segregates totals by currency so distinct currencies are never silently summed.
 */
export function calculateCommittedTotals(
  contracts: ContractItem[],
  options?: { eligibleStatusesOnly?: boolean }
): {
  totalsByCurrency: Record<string, number>;
  primaryFormatted: string;
  secondaryFormatted: string | null;
  activeEligibleCount: number;
  unspecifiedCount: number;
  hasCommittedValue: boolean;
} {
  // Deduplicate by contractId to ensure multiple versions of the same contract are not double-counted
  const seenContractCodes = new Set<string>();
  const uniqueContracts: ContractItem[] = [];

  for (const c of contracts) {
    const code = c.contractId || c.id;
    if (!seenContractCodes.has(code)) {
      seenContractCodes.add(code);
      uniqueContracts.push(c);
    }
  }

  // Filter eligible contracts: Active / Approved agreements (or non-terminated if filter disabled)
  const eligibleContracts = options?.eligibleStatusesOnly === false
    ? uniqueContracts.filter((c) => c.status !== 'TERMINATED' && c.status !== 'EXPIRED')
    : uniqueContracts.filter((c) => c.status === 'ACTIVE' || c.status === 'APPROVED');

  const totalsByCurrency: Record<string, number> = {};
  let unspecifiedCount = 0;

  for (const c of eligibleContracts) {
    if (c.value === null || c.value === undefined || c.valueBasis === 'NOT_SPECIFIED' || c.valueBasis === 'NEEDS_VERIFICATION') {
      unspecifiedCount++;
      continue;
    }
    const curr = (c.currency || 'INR').toUpperCase();
    totalsByCurrency[curr] = (totalsByCurrency[curr] || 0) + Number(c.value);
  }

  const currencies = Object.keys(totalsByCurrency);
  const hasCommittedValue = currencies.length > 0 && currencies.some((k) => totalsByCurrency[k] > 0);

  if (!hasCommittedValue) {
    return {
      totalsByCurrency,
      primaryFormatted: unspecifiedCount > 0 ? 'Needs verification' : formatCurrency(0, 'INR'),
      secondaryFormatted: null,
      activeEligibleCount: eligibleContracts.length,
      unspecifiedCount,
      hasCommittedValue: false
    };
  }

  // Primary currency is INR if present, or first currency with value
  const primaryCurr = totalsByCurrency['INR'] !== undefined ? 'INR' : currencies[0];
  const primaryVal = totalsByCurrency[primaryCurr];
  const primaryFormatted = formatCurrency(primaryVal, primaryCurr);

  // Other currencies shown as secondary breakdown rather than silently mixed
  const otherCurrencies = currencies.filter((k) => k !== primaryCurr && totalsByCurrency[k] > 0);
  const secondaryFormatted = otherCurrencies.length > 0
    ? otherCurrencies.map((k) => formatCurrency(totalsByCurrency[k], k)).join(' + ')
    : null;

  return {
    totalsByCurrency,
    primaryFormatted,
    secondaryFormatted,
    activeEligibleCount: eligibleContracts.length,
    unspecifiedCount,
    hasCommittedValue: true
  };
}
