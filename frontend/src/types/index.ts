export type UserRole = 
  | 'SUPER_ADMIN' 
  | 'COMPANY_ADMIN' 
  | 'SALES_MANAGER' 
  | 'TEAM_LEADER' 
  | 'SALES_AGENT';

export type PipelineStage = 
  | 'NEW'
  | 'CONTACT_ATTEMPTED'
  | 'CONTACTED'
  | 'QUALIFIED'
  | 'INTERESTED'
  | 'VISIT_SCHEDULED'
  | 'VISIT_COMPLETED'
  | 'NEGOTIATION'
  | 'RESERVATION'
  | 'WON'
  | 'LOST'
  | 'NURTURING';

export type PriorityLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';
export type PropertyStatus = 'AVAILABLE' | 'RESERVED' | 'SOLD' | 'UNAVAILABLE' | 'ARCHIVED';
export type ActivityType = 'CALL' | 'WHATSAPP' | 'MEETING' | 'VISIT' | 'EMAIL' | 'NOTE' | 'OFFER_SENT';
export type FollowUpStatus = 'PENDING' | 'IN_PROGRESS' | 'DUE_TODAY' | 'OVERDUE' | 'COMPLETED' | 'RESCHEDULED' | 'CANCELLED';
export type TransferStatus = 'PENDING' | 'APPROVED' | 'REJECTED';
export type AppointmentStatus = 'SCHEDULED' | 'COMPLETED' | 'CANCELLED' | 'RESCHEDULED';

export interface User {
  id: number;
  company_id: number;
  company_name?: string;
  email: string;
  full_name: string;
  phone?: string;
  role: UserRole;
  is_active: boolean;
  team_id?: number;
}

export interface Lead {
  id: number;
  company_id: number;
  full_name: string;
  phone: string;
  email?: string;
  preferred_contact_method: string;
  source: string;
  team_id?: number;
  assigned_agent_id?: number;
  assigned_agent_name?: string;
  status: string;
  pipeline_stage: PipelineStage;
  budget_min: number;
  budget_max: number;
  preferred_project_id?: number;
  preferred_project_name?: string;
  preferred_location: string;
  property_type: string;
  preferred_area_range: string;
  bedrooms: number;
  down_payment_budget: number;
  purchase_timeline: string;
  notes: string;
  tags: string;
  do_not_contact: boolean;
  last_contact_date?: string;
  next_followup_date?: string;
  priority: PriorityLevel;
  score: number;
  score_factors: Array<{ factor: string; impact: number; description: string }>;
  created_at: string;
  updated_at: string;
}

export interface Property {
  id: number;
  company_id: number;
  project_id?: number | null;
  project_name?: string;
  title?: string;
  unit_number: string;
  property_type: string;
  city: string;
  location: string;
  governorate_id?: number;
  city_id?: number;
  district_id?: number;
  area: number;
  bedrooms: number;
  bathrooms: number;
  floor: number;
  view: string;
  finishing_status: string;
  delivery_date: string;
  total_price: number;
  currency: string;
  down_payment: number;
  installment_plan: string;
  installment_frequency: string;
  remaining_balance: number;
  availability_status: PropertyStatus;
  is_archived?: boolean;
  description: string;
  primary_image_url?: string;
  images?: PropertyImage[];
  videos?: PropertyVideo[];
  features?: PropertyFeature[];
}

export interface PropertyVideo {
  id: number;
  property_id: number;
  company_id: number;
  video_url: string;
  video_type: 'UPLOAD' | 'EXTERNAL';
  title?: string;
  sort_order: number;
  created_at?: string;
}

export interface PropertyImage {
  id: number;
  property_id: number;
  image_url: string;
  is_primary: boolean;
  caption?: string;
  display_order: number;
  created_at: string;
}

export interface PropertyFeature {
  id: number;
  property_id: number;
  feature_name: string;
  feature_value?: string;
}

export type PropertyOfferStatus = 'DRAFT' | 'PREPARED' | 'SHARED' | 'ACCEPTED' | 'REJECTED';

export interface PropertyOffer {
  id: number;
  company_id: number;
  lead_id: number;
  lead_name?: string;
  lead_phone?: string;
  property_id: number;
  property_unit?: string;
  property_price?: number;
  property_location?: string;
  project_name?: string;
  created_by_id: number;
  created_by_name?: string;
  status: PropertyOfferStatus;
  custom_price?: number;
  message_text: string;
  shared_via: string;
  shared_at?: string;
  customer_feedback?: string;
  feedback_recorded_at?: string;
  created_at: string;
  property_images: string[];
}

export interface PropertyMessageResponse {
  customer_id: number;
  customer_name: string;
  customer_phone: string;
  property_id: number;
  property_unit: string;
  message_text: string;
  whatsapp_url: string;
  property_images: string[];
}

export interface CustomerTimelineEvent {
  id: string;
  type: 'ACTIVITY' | 'APPOINTMENT' | 'FOLLOWUP' | 'PROPERTY_OFFER' | 'ASSIGNMENT' | string;
  subtype?: string;
  title: string;
  description?: string;
  timestamp: string;
  user_name?: string;
  status?: string;
  metadata?: Record<string, any>;
}

export interface Project {
  id: number;
  company_id: number;
  name: string;
  developer: string;
  location: string;
  governorate_id?: number;
  city_id?: number;
  district_id?: number;
  is_active?: boolean;
  is_archived?: boolean;
  description?: string;
  project_type: string;
  status: string;
  available_units: number;
}

export interface Activity {
  id: number;
  company_id: number;
  lead_id: number;
  lead_name?: string;
  property_id?: number;
  property_unit?: string;
  user_id: number;
  user_name?: string;
  activity_type: ActivityType;
  summary: string;
  outcome?: string;
  objection?: string;
  sentiment?: string;
  next_action?: string;
  next_followup_date?: string;
  created_at: string;
}

export interface FollowUp {
  id: number;
  company_id: number;
  lead_id?: number | null;
  lead_name?: string;
  lead_phone?: string;
  assigned_user_id: number;
  assigned_user_name?: string;
  created_by_id?: number | null;
  created_by_name?: string;
  team_id?: number;
  follow_up_type: string;
  purpose: string;
  due_date: string;
  priority: PriorityLevel;
  status: FollowUpStatus;
  notes: string;
  completion_outcome: string;
  created_at: string;
  completed_at?: string;
  is_overdue: boolean;
  is_due_today: boolean;
}

export interface Appointment {
  id: number;
  company_id: number;
  lead_id: number;
  lead_name?: string;
  property_id?: number;
  property_unit?: string;
  user_id: number;
  user_name?: string;
  title: string;
  appointment_type: string;
  start_time: string;
  end_time: string;
  location: string;
  notes: string;
  status: AppointmentStatus;
  created_at: string;
}

export interface TransferRequest {
  id: number;
  company_id: number;
  lead_id: number;
  lead_name?: string;
  current_owner_id?: number;
  current_owner_name?: string;
  requested_owner_id: number;
  requested_owner_name?: string;
  requested_by_id: number;
  requested_by_name?: string;
  reason: string;
  notes: string;
  status: TransferStatus;
  reviewer_id?: number;
  reviewer_name?: string;
  review_notes?: string;
  created_at: string;
  reviewed_at?: string;
}

export interface NotificationItem {
  id: number;
  title: string;
  message: string;
  link: string;
  notification_type: string;
  is_read: boolean;
  created_at: string;
}

export interface DailyBriefingData {
  greeting: string;
  summary_text: string;
  date_formatted: string;
  metrics: {
    due_today: number;
    overdue: number;
    today_visits: number;
    stalled_leads: number;
  };
  due_today_followups: Array<{ id: number; lead_id: number; lead_name: string; purpose: string; priority: string; due_date: string }>;
  overdue_followups: Array<{ id: number; lead_id: number; lead_name: string; purpose: string; priority: string; due_date: string }>;
  today_visits: Array<{ id: number; lead_id: number; lead_name: string; title: string; time: string; location: string }>;
  leads_no_next_action: Array<{ id: number; full_name: string; phone: string; pipeline_stage: string; score: number }>;
  recommendations: string[];
}

export type ConversationChannel = 'WHATSAPP' | 'FACEBOOK' | 'INSTAGRAM' | 'VOICE' | 'WEB' | 'SMS';
export type ConversationStatus = 'OPEN' | 'WAITING_CLIENT' | 'WAITING_AGENT' | 'RESOLVED' | 'CLOSED';
export type MessageSenderType = 'CUSTOMER' | 'AGENT' | 'AI' | 'SYSTEM';
export type MessageType = 'TEXT' | 'VOICE' | 'IMAGE' | 'NOTE';

export interface ConversationMessage {
  id: number;
  conversation_id: number;
  company_id: number;
  sender_type: MessageSenderType;
  sender_id?: number;
  sender_name?: string;
  message_type: MessageType;
  content: string;
  audio_url?: string;
  audio_duration?: number;
  is_internal_note: boolean;
  is_read: boolean;
  created_at: string;
}

export interface Conversation {
  id: number;
  company_id: number;
  lead_id?: number;
  lead_name?: string;
  assigned_agent_id?: number;
  assigned_agent_name?: string;
  team_id?: number;
  team_name?: string;
  channel: ConversationChannel;
  status: ConversationStatus;
  customer_name: string;
  customer_phone?: string;
  customer_identifier?: string;
  unread_count: number;
  ai_enabled: boolean;
  human_takeover: boolean;
  last_message_text: string;
  last_message_time: string;
  ai_summary?: string;
  created_at: string;
  updated_at: string;
  messages?: ConversationMessage[];
}

export interface SalesAgentProfile {
  id: number;
  user_id: number;
  company_id: number;
  personality_prompt: string;
  preferred_voice: string;
  speaking_rate: string;
  working_hours_start: string;
  working_hours_end: string;
  max_active_leads: number;
  is_accepting_leads: boolean;
  monthly_target_sales: number;
  target_visits_per_month: number;
  created_at: string;
}

export interface AgentWithStats {
  id: number;
  company_id: number;
  email: string;
  full_name: string;
  phone?: string;
  role: UserRole;
  is_active: boolean;
  team_id?: number;
  team_name?: string;
  profile?: SalesAgentProfile;
  total_assigned_leads: number;
  active_leads: number;
  won_leads: number;
  conversion_rate: number;
  completed_visits: number;
  overdue_followups: number;
}

export interface VoiceAnalyticsData {
  period_days: number;
  total_turns: number;
  stt: {
    success_rate: number;
    avg_latency_ms: number;
    total_requests: number;
    failed_requests: number;
  };
  llm: {
    success_rate: number;
    avg_latency_ms: number;
    total_requests: number;
    failed_requests: number;
  };
  tts: {
    success_rate: number;
    avg_latency_ms: number;
    total_requests: number;
    failed_requests: number;
  };
  e2e: {
    avg_latency_ms: number;
    interrupted_count: number;
  };
  estimated_cost_usd: number;
  providers_used: string[];
}

// -------------------------------------------------------------------------
// Location Management Hierarchy
// -------------------------------------------------------------------------

export interface Governorate {
  id: number;
  name_ar: string;
  name_en: string;
  is_active: boolean;
  created_at: string;
  cities_count?: number;
  properties_count?: number;
}

export interface City {
  id: number;
  governorate_id: number;
  name_ar: string;
  name_en: string;
  is_active: boolean;
  created_at: string;
  districts_count?: number;
  properties_count?: number;
}

export interface District {
  id: number;
  city_id: number;
  name_ar: string;
  name_en: string;
  is_active: boolean;
  created_at: string;
  projects_count?: number;
  properties_count?: number;
}

export interface HierarchyDistrict {
  id: number;
  name_ar: string;
  name_en: string;
  is_active: boolean;
  projects_count: number;
  properties_count: number;
}

export interface HierarchyCity {
  id: number;
  name_ar: string;
  name_en: string;
  is_active: boolean;
  districts: HierarchyDistrict[];
}

export interface HierarchyGovernorate {
  id: number;
  name_ar: string;
  name_en: string;
  is_active: boolean;
  cities: HierarchyCity[];
}

// -------------------------------------------------------------------------
// Unified Calendar & Daily Briefing
// -------------------------------------------------------------------------

export interface UnifiedCalendarEvent {
  id: string;
  original_id: number;
  source_type: 'APPOINTMENT' | 'TASK';
  event_type: 'Task' | 'Phone Call' | 'Office Meeting' | 'Property Visit' | 'Client Meeting';
  title: string;
  description?: string;
  start_time: string;
  end_time: string;
  lead_id?: number | null;
  lead_name?: string | null;
  lead_phone?: string | null;
  assigned_user_id: number;
  assigned_user_name: string;
  location?: string | null;
  priority?: PriorityLevel | null;
  status: string;
  has_conflict: boolean;
  conflict_notes?: string | null;
  color: string;
}

export interface CalendarDailyBriefing {
  cairo_greeting: string;
  selected_date: string;
  total_events: number;
  appointments_count: number;
  tasks_count: number;
  overdue_count: number;
  due_today_count: number;
  earliest_event_time?: string | null;
  conflicts_count: number;
  summary_text: string;
  attention_items: string[];
}

// -------------------------------------------------------------------------
// Tasks Stats & Personal Daily Briefing
// -------------------------------------------------------------------------

export interface FollowUpStats {
  total: number;
  overdue: number;
  due_today: number;
  upcoming: number;
  completed: number;
}

export interface FollowUpBriefing {
  greeting: string;
  cairo_time: string;
  overdue_count: number;
  due_today_count: number;
  earliest_task_time?: string | null;
  attention_summary: string;
  actionable_items: string[];
}

// -------------------------------------------------------------------------
// AI Marketing Studio Types
// -------------------------------------------------------------------------

export type MarketingGenerationStatus = 'PENDING' | 'GENERATING' | 'COMPLETED' | 'FAILED';
export type MarketingPublishingStatus = 'DRAFT' | 'SCHEDULED' | 'PUBLISHING' | 'PUBLISHED' | 'FAILED';
export type MarketingLogStatus = 'SUCCESS' | 'ERROR' | 'INFO';

export interface MarketingPost {
  id: number;
  company_id: number;
  topic: string;
  headline: string;
  caption: string;
  image_prompt: string;
  image_path?: string | null;
  raw_image_path?: string | null;
  generation_provider: string;
  generation_model: string;
  image_provider: string;
  image_model: string;
  generation_status: MarketingGenerationStatus;
  publishing_status: MarketingPublishingStatus;
  facebook_post_id?: string | null;
  facebook_permalink_url?: string | null;
  scheduled_at?: string | null;
  published_at?: string | null;
  post_date: string;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MarketingSetting {
  id: number;
  company_id: number;
  auto_generation_enabled: boolean;
  auto_publishing_enabled: boolean;
  generation_time: string;
  publishing_time: string;
  timezone: string;
  text_provider: string;
  text_model: string;
  image_provider: string;
  image_model: string;
  facebook_page_id?: string | null;
  facebook_page_name?: string | null;
  has_facebook_token: boolean;
  created_at: string;
  updated_at: string;
}

export interface MarketingDashboardStats {
  total_posts: number;
  published_posts: number;
  scheduled_posts: number;
  failed_posts: number;
  draft_posts: number;
  next_scheduled_post?: string | null;
  last_published_at?: string | null;
  auto_publishing_enabled: boolean;
  auto_generation_enabled: boolean;
  facebook_connected: boolean;
  facebook_page_name?: string | null;
}

export interface MarketingLog {
  id: number;
  company_id: number;
  post_id?: number | null;
  action: string;
  status: MarketingLogStatus;
  error_message?: string | null;
  details?: Record<string, any> | null;
  created_at: string;
}

export interface FacebookConnectionTestResponse {
  connected: boolean;
  page_id?: string | null;
  page_name?: string | null;
  message: string;
  permissions: string[];
}

