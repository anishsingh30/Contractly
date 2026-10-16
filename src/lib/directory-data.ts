import { LawyerProfile } from '@/types/contractly';

/**
 * Verified Lawyer Directory Copy (UI Static Marketplace Directory Data - Class B)
 * These represent certified external legal professionals for advisory consultation.
 * They are not tenant-specific internal business data.
 */
export const VERIFIED_LAWYERS: LawyerProfile[] = [
  {
    id: 'law-01',
    name: 'Advocate Radhika Swaminathan',
    firmName: 'Swaminathan & Chambers, Advocates',
    practiceAreas: ['Corporate Contracts', 'Technology & SaaS', 'Data Privacy (DPDPA)'],
    experienceYears: 14,
    jurisdiction: 'Supreme Court of India & High Court of Delhi',
    consultationFee: '₹7,500 / 45 min',
    availability: 'Next available: Tomorrow at 3:00 PM',
    verified: true,
    bio: 'Specializes in venture-backed tech contracts, cross-border intellectual property licensing, and cloud vendor dispute resolutions.'
  },
  {
    id: 'law-02',
    name: 'Advocate Vikramaditya Sen',
    firmName: 'Sen Legal Partners',
    practiceAreas: ['Employment Law', 'Executive Severance', 'Non-Compete Disputes'],
    experienceYears: 18,
    jurisdiction: 'High Court of Karnataka, Bengaluru',
    consultationFee: '₹9,000 / 45 min',
    availability: 'Next available: Friday at 11:00 AM',
    verified: true,
    bio: 'Advises startup founders, CXOs, and enterprises on Section 27 non-compete enforceability, ESOP agreements, and executive transitions.'
  },
  {
    id: 'law-03',
    name: 'Advocate Meera Nair',
    firmName: 'Nair Commercial Law Advisory',
    practiceAreas: ['Commercial Property', 'Lease Disputes', 'Procurement Agreements'],
    experienceYears: 11,
    jurisdiction: 'High Court of Bombay, Mumbai',
    consultationFee: '₹6,000 / 45 min',
    availability: 'Next available: Thursday at 4:30 PM',
    verified: true,
    bio: 'Focused on commercial lease structuring, security deposit dispute arbitration, and vendor supply chain compliance.'
  }
];
