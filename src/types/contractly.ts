export type AccountType =
  | 'INDIVIDUAL'
  | 'PERSONAL'
  | 'BUSINESS'
  | 'ENTERPRISE'
  | 'LEGAL_PROFESSIONAL'
  | 'PROFESSIONAL';

export type BusinessRole =
  | 'OWNER'
  | 'ADMIN'
  | 'LEGAL_MANAGER'
  | 'LEGAL_REVIEWER'
  | 'FINANCE'
  | 'PROCUREMENT'
  | 'HR'
  | 'SALES'
  | 'DEPT_MANAGER'
  | 'EMPLOYEE';

export type ProfessionalRole = 'LAW_FIRM_ADMIN' | 'LAWYER' | 'LEGAL_ASSISTANT';

export type ContractStatus =
  | 'DRAFT'
  | 'UNDER_REVIEW'
  | 'NEGOTIATION'
  | 'PENDING_APPROVAL'
  | 'APPROVED'
  | 'PENDING_SIGNATURE'
  | 'EXECUTED'
  | 'ACTIVE'
  | 'AT_RISK'
  | 'POTENTIAL_BREACH'
  | 'IN_RENEWAL'
  | 'EXPIRED'
  | 'TERMINATED';

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export type ObligationStatus =
  | 'NOT_STARTED'
  | 'UPCOMING'
  | 'DUE_SOON'
  | 'FULFILLED'
  | 'AT_RISK'
  | 'OVERDUE'
  | 'POTENTIAL_NON_COMPLIANCE'
  | 'RESOLVED';

export interface ClauseExplanation {
  id: string;
  clauseTitle: string;
  sectionNumber: string;
  originalText: string;
  plainLanguage: string;
  whyItMatters: string;
  potentialConcern?: string;
  suggestedAction?: string;
  riskLevel: RiskLevel;
  category: string;
}

export interface RedlineItem {
  id: string;
  clauseId: string;
  sectionTitle: string;
  originalText: string;
  suggestedText: string;
  rationale: string;
  status: 'PENDING' | 'ACCEPTED' | 'REJECTED' | 'MODIFIED';
  author: string;
  timestamp: string;
  comment?: string;
}

export interface ObligationItem {
  id: string;
  contractId: string;
  contractTitle: string;
  obligorParty: string; // Who owes the duty
  obligeeParty: string; // To whom
  title: string;
  description: string;
  dueDate: string;
  frequency: 'ONE_TIME' | 'MONTHLY' | 'QUARTERLY' | 'ANNUALLY';
  penaltyClause?: string;
  responsibleOwner: string;
  status: ObligationStatus;
  evidenceFiles?: Array<{
    fileName: string;
    uploadedAt: string;
    uploadedBy: string;
    status: 'VERIFIED' | 'UNDER_REVIEW';
  }>;
}

export interface ContractRiskItem {
  id: string;
  severity: RiskLevel | string;
  riskTitle: string;
  potentialImpact: string;
  remedyRecommendation: string;
  status: string;
}

export interface CurrentUser {
  id: string;
  email: string;
  fullName: string;
  organizationId: string;
  organizationName: string;
  role: BusinessRole;
  accountType: AccountType;
  subscriptionTier?: string;
  permissions?: string[];
  entitlements?: Record<string, any>;
  emailVerificationStatus?: string;
  isSuperAdmin?: boolean;
  platformRole?: string | null;
}

export interface AdvocateProfile {
  id: string;
  userId: string;
  fullName: string;
  professionalTitle?: string;
  email?: string;
  phoneNumber?: string;
  firmName: string;
  organizationId: string;
  barCouncilNumber?: string;
  stateBarCouncil: string;
  admittedJurisdictions: string;
  practiceAreas: string[];
  qualifications?: string[];
  languages?: string[];
  experienceYears: number;
  consultationFee: string;
  consultationDurationMinutes?: number;
  bio?: string;
  internalNotes?: string;
  credentialDocuments?: Array<{ id: string; name: string; url?: string; uploadedAt?: string }>;
  isPublished?: boolean;
  isAvailableForInquiries: boolean;
  verificationStatus: 'PENDING_REVIEW' | 'VERIFIED' | 'REJECTED' | 'SUSPENDED';
  verifiedAt?: string | null;
  rejectionReason?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface OrganizationInfo {
  id: string;
  name: string;
  slug: string;
  accountType: AccountType;
  subscriptionTier: string;
  storageQuotaBytes: number;
  is_personal?: boolean;
  entitlements?: Record<string, any>;
}

export interface ApprovalStep {
  id: string;
  stepOrder: number;
  role: string;
  assignedUser: string;
  decision: 'PENDING' | 'APPROVED' | 'REJECTED';
  decidedAt?: string;
  comments?: string;
}

export interface ContractVersionItem {
  id: string;
  versionNumber: string;
  fileStoragePath?: string;
  fileMimeType: string;
  fileByteSize: number;
  sha256Checksum: string;
  changeSummary?: string;
  createdBy?: string;
  createdAt: string;
}

export interface NegotiationFindingItem {
  ruleId: string;
  category: string;
  status: 'Rule Match' | 'Potential Negotiation Issue';
  targetClause?: string;
  clauseTitle?: string;
  findingSummary: string;
  guidance: string;
  suggestedAction?: string;
}

export interface ContractLifecycleSummary {
  currentStatus: string;
  allowedTransitions: string[];
  healthStatus: 'GOOD' | 'NEEDS ATTENTION' | 'UPCOMING' | 'POTENTIAL PROBLEM' | 'Not enough information';
  healthReason: string;
  renewalStatus: string;
  daysUntilExpiry?: number;
  inNoticeWindow: boolean;
  openRisksCount: number;
  overdueObligationsCount: number;
  pendingApprovalStepsCount: number;
}

export interface ContractItem {
  id: string;
  contractId: string; // e.g. "CTR-2026-0842"
  title: string;
  contractType: string;
  counterparty: string;
  department: string;
  owner: string;
  value: number | null;
  currency: string;
  valueBasis?: string;
  calculationExplanation?: string;
  startDate: string;
  expiryDate: string;
  renewalDate: string;
  autoRenew: boolean;
  renewalNoticeDays?: number;
  terminationNoticeDays?: number;
  terminationDate?: string;
  terminationReason?: string;
  status: ContractStatus;
  compositeRiskScore: number; // 0-100
  riskLevel: RiskLevel;
  version: string;
  clauses: ClauseExplanation[];
  risks?: ContractRiskItem[];
  redlines: RedlineItem[];
  obligations: ObligationItem[];
  approvalSteps: ApprovalStep[];
  versions?: ContractVersionItem[];
  governingLaw: string;
  tags: string[];
  lastModified: string;
}

export interface PlaybookRule {
  id: string;
  category: string;
  preferredStandard: string;
  fallbackAcceptable: string;
  prohibitedTerms: string[];
  negotiationGuidance: string;
  lastUpdated: string;
}

export interface VendorProfile {
  id: string;
  name: string;
  contactEmail: string;
  contractCount: number;
  totalContractValue: number;
  riskRating: RiskLevel;
  complianceRating: number; // 0-100%
  slaPerformance: string;
  openObligations: number;
  criticalIssues: number;
  soc2Certified: boolean;
  gdprCompliant: boolean;
}

export interface LawyerProfile {
  id: string;
  name: string;
  firmName: string;
  practiceAreas: string[];
  experienceYears: number;
  jurisdiction: string;
  consultationFee: string;
  availability: string;
  verified: boolean;
  bio: string;
}

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  user: string;
  action: string;
  objectType: string;
  objectId: string;
  detail: string;
  ipAddress: string;
}

export interface ActivityItem {
  id: string;
  timestamp: string;
  formatted_time: string;
  actor_email: string;
  actor_name: string;
  action: string;
  action_label: string;
  object_type: string;
  object_id: string;
  item_reference: string;
  item_link?: string | null;
  summary: string;
  detail: string;
  status: 'COMPLETED' | 'FAILED' | 'PENDING' | string;
  scope: 'personal' | 'organization' | string;
}

export interface ActivityListResponse {
  items: ActivityItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  current_scope: 'personal' | 'organization';
  can_view_organization_activity: boolean;
  available_action_types: string[];
}

export interface ActivityFilterParams {
  scope?: 'personal' | 'organization';
  action_type?: string;
  start_date?: string;
  end_date?: string;
  team_member?: string;
  page?: number;
  page_size?: number;
}

export interface ExtractedPartyItem {
  name: string;
  role: string;
  source?: string;
}

export interface ExtractedDateCandidateItem {
  date_type: string;
  date_str: string;
  section_number?: string;
  section_title?: string;
  excerpt?: string;
}

export interface ObligationCandidateItem {
  title: string;
  clause_id?: string;
  section_number?: string;
  section_title?: string;
  source_text: string;
  responsible_party: string;
  category: string;
  frequency: string;
  confidence: string;
}

export interface RiskScoreBreakdown {
  composite_risk_score: number;
  risk_level: RiskLevel;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  explanation: string;
}

export interface ContractIntelligenceData {
  contract_id: string;
  version_id?: string;
  parser_status: 'UPLOADED' | 'PARSING' | 'ANALYZING' | 'COMPLETED' | 'FAILED';
  page_count: number;
  char_count: number;
  word_count: number;
  processing_started_at?: string;
  processing_completed_at?: string;
  processing_error?: string;
  parties: ExtractedPartyItem[];
  candidate_dates: ExtractedDateCandidateItem[];
  renewal_info: Record<string, any>;
  clauses: ClauseExplanation[];
  risks: any[];
  obligation_candidates: ObligationCandidateItem[];
  risk_score_breakdown: RiskScoreBreakdown;
}

export interface ContractMetadata {
  contract_id: string;
  title: string;
  counterparty: string;
  status: string;
  current_version: string;
  versions: ContractVersionItem[];
  total_clauses: number;
  total_risks: number;
  total_obligations: number;
}

export interface ContractQASource {
  clause_id?: string;
  section?: string;
  title?: string;
  page?: number;
  excerpt?: string;
}

export interface ContractQAResult {
  answer: string;
  confidence: string;
  sources: ContractQASource[];
  error?: string;
  status_code?: number;
}

export interface LawyerInquiryResult {
  inquiry_id: string;
  status: string;
  lawyer_name: string;
  preferred_time_slot: string;
  message: string;
  limitations_notice: string;
}

export interface GeneralChatResult {
  reply: string;
  disclaimer: string;
  error?: string;
  status_code?: number;
}

// ─────────────────────────────────────────────────────────────
// Phase I Types: Calendar, Notes, Things To Do & Notifications
// ─────────────────────────────────────────────────────────────

export interface CalendarEventItem {
  id: string;
  organization_id: string;
  contract_id?: string | null;
  contract_title?: string | null;
  counterparty?: string | null;
  obligation_id?: string | null;
  title: string;
  description?: string | null;
  event_type: string;
  event_date: string;
  priority: 'CRITICAL' | 'IMPORTANT' | 'INFORMATIONAL';
  status: 'UPCOMING' | 'DUE_SOON' | 'OVERDUE' | 'COMPLETED' | 'CANCELLED';
  source_type: string;
  is_verified: boolean;
  is_important: boolean;
  is_custom: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface ContractNoteItem {
  id: string;
  organization_id: string;
  contract_id: string;
  author_user_id: string;
  author_name: string;
  title?: string | null;
  content: string;
  reminder_date?: string | null;
  is_important: boolean;
  calendar_event_id?: string | null;
  obligation_id?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface ThingToDoItem {
  id: string;
  task_type: string;
  title: string;
  contract_id?: string | null;
  contract_title?: string | null;
  counterparty?: string | null;
  due_date?: string | null;
  priority: 'CRITICAL' | 'IMPORTANT' | 'INFORMATIONAL';
  status: 'PENDING' | 'DUE_SOON' | 'OVERDUE' | 'IN_REVIEW';
  responsible_role?: string | null;
  reason: string;
  action_type: string;
  target_id?: string | null;
}

export interface NotificationItem {
  id: string;
  organization_id: string;
  user_id: string;
  contract_id?: string | null;
  obligation_id?: string | null;
  calendar_event_id?: string | null;
  event_type: string;
  priority: 'CRITICAL' | 'IMPORTANT' | 'INFORMATIONAL';
  title: string;
  message: string;
  scheduled_at?: string | null;
  sent_at?: string | null;
  delivery_channel: string;
  delivery_status: string;
  is_read: boolean;
  read_at?: string | null;
  retry_count: number;
  last_error?: string | null;
  created_at?: string;
}

export interface NotificationPreferences {
  id: string;
  organization_id: string;
  user_id: string;
  email_notifications_enabled: boolean;
  renewal_reminders: boolean;
  notice_deadline_reminders: boolean;
  obligation_reminders: boolean;
  approval_reminders: boolean;
  critical_events_enabled: boolean;
  reminder_intervals: number[];
  daily_notification_limit: number;
  quiet_hours_enabled: boolean;
  quiet_hours_start: string;
  quiet_hours_end: string;
  preferred_notification_email?: string | null;
  email_service_enabled?: boolean;
  email_provider_status?: string;
}

export interface WorkspaceCategorySummary {
  category: string;
  count: number;
  description: string;
}

export interface WorkspaceSummaryResponse {
  organization_id: string;
  organization_name: string;
  organization_slug: string;
  is_demo: boolean;
  categories: WorkspaceCategorySummary[];
  total_records: number;
  legal_hold_count: number;
  storage_files_count: number;
  can_clear_workspace: boolean;
  blocking_reasons: string[];
}

export interface DemoResetPreviewResponse {
  demo_org_found: boolean;
  organization_id?: string;
  organization_name?: string;
  organization_slug?: string;
  contracts_count: number;
  versions_count: number;
  obligations_count: number;
  files_count: number;
  calendar_events_count: number;
  notes_count: number;
  required_confirmation: string;
  last_reset_at?: string | null;
}

export interface DemoResetResultResponse {
  status: string;
  message: string;
  organization_id: string;
  organization_name: string;
  deleted_counts: Record<string, number>;
  deleted_storage_files: number;
  reseeded: boolean;
  reseeded_contracts_count: number;
  timestamp: string;
}

export interface HandoverChecklistItem {
  id: string;
  title: string;
  description: string;
  status: string;
  category: string;
}

export interface CustomerHandoverChecklistResponse {
  checklist: HandoverChecklistItem[];
  generated_at: string;
}

export interface MatterMessageItem {
  id: string;
  matter_id: string;
  sender_user_id: string;
  sender_name: string;
  sender_type: 'CLIENT' | 'LAWYER';
  message_text: string;
  is_internal_note: boolean;
  attachments: Array<Record<string, any>>;
  created_at: string;
}

export interface ConversationItem {
  matter_id: string;
  matter_code: string;
  title: string;
  status: string;
  client_organization_name: string;
  client_user_name?: string | null;
  lawyer_organization_name: string;
  lawyer_user_name?: string | null;
  contract_title?: string | null;
  last_message_text?: string | null;
  last_message_at?: string | null;
  last_message_sender_type?: 'CLIENT' | 'LAWYER' | null;
  message_count: number;
  has_admin_review: boolean;
  last_admin_review_at?: string | null;
  admin_review_reason?: string | null;
  is_active_for_messaging: boolean;
  created_at: string;
}

export interface AdminConversationItem {
  matter_id: string;
  matter_code: string;
  title: string;
  status: string;
  client_organization_id: string;
  client_organization_name: string;
  client_user_email?: string | null;
  client_user_name?: string | null;
  lawyer_organization_name: string;
  lawyer_user_email?: string | null;
  lawyer_user_name?: string | null;
  message_count: number;
  last_message_at?: string | null;
  last_message_preview?: string | null;
  review_status: 'REVIEWED' | 'UNREVIEWED';
  last_reviewed_at?: string | null;
  last_reviewed_by?: string | null;
  last_review_reason?: string | null;
  created_at: string;
}

export interface AdminConversationReviewResponse {
  matter_id: string;
  matter_code: string;
  title: string;
  status: string;
  review_status: string;
  reviewed_at: string;
  reviewed_by: string;
  review_reason: string;
  messages: MatterMessageItem[];
  audit_history: Array<{
    id: string;
    action: string;
    admin_email: string;
    detail: string;
    timestamp?: string | null;
  }>;
  admin_notes: Array<{
    id: string;
    action: string;
    admin_email: string;
    detail: string;
    timestamp?: string | null;
  }>;
}

export interface AdminConsultationRequestItem {
  matter_id: string;
  matter_code: string;
  title: string;
  status: string;
  client_organization_id: string;
  client_organization_name: string;
  client_user_id?: string | null;
  client_user_name?: string | null;
  client_user_email?: string | null;
  lawyer_organization_id: string;
  lawyer_organization_name: string;
  lawyer_user_id?: string | null;
  lawyer_user_name?: string | null;
  lawyer_user_email?: string | null;
  counterparty_name: string;
  preferred_time_slot?: string | null;
  client_notes?: string | null;
  initial_message?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface AdminConsultationDecisionResponse {
  success: boolean;
  matter_id: string;
  matter_code: string;
  status: string;
  message: string;
}

