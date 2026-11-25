import enum
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Float, ForeignKey, 
    Text, Enum as SAEnum, JSON, Index
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    COMPANY_ADMIN = "COMPANY_ADMIN"
    SALES_MANAGER = "SALES_MANAGER"
    TEAM_LEADER = "TEAM_LEADER"
    SALES_AGENT = "SALES_AGENT"


class PipelineStage(str, enum.Enum):
    NEW = "NEW"
    CONTACT_ATTEMPTED = "CONTACT_ATTEMPTED"
    CONTACTED = "CONTACTED"
    QUALIFIED = "QUALIFIED"
    INTERESTED = "INTERESTED"
    VISIT_SCHEDULED = "VISIT_SCHEDULED"
    VISIT_COMPLETED = "VISIT_COMPLETED"
    NEGOTIATION = "NEGOTIATION"
    RESERVATION = "RESERVATION"
    WON = "WON"
    LOST = "LOST"
    NURTURING = "NURTURING"


class PriorityLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class PropertyStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    SOLD = "SOLD"
    UNAVAILABLE = "UNAVAILABLE"
    ARCHIVED = "ARCHIVED"


class ActivityType(str, enum.Enum):
    CALL = "CALL"
    WHATSAPP = "WHATSAPP"
    MEETING = "MEETING"
    VISIT = "VISIT"
    EMAIL = "EMAIL"
    NOTE = "NOTE"
    OFFER_SENT = "OFFER_SENT"


class FollowUpStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    DUE_TODAY = "DUE_TODAY"
    OVERDUE = "OVERDUE"
    COMPLETED = "COMPLETED"
    RESCHEDULED = "RESCHEDULED"
    CANCELLED = "CANCELLED"


class TransferStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AppointmentStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    RESCHEDULED = "RESCHEDULED"


class ConversationChannel(str, enum.Enum):
    WHATSAPP = "WHATSAPP"
    FACEBOOK = "FACEBOOK"
    INSTAGRAM = "INSTAGRAM"
    VOICE = "VOICE"
    WEB = "WEB"
    SMS = "SMS"


class ConversationStatus(str, enum.Enum):
    OPEN = "OPEN"
    WAITING_CLIENT = "WAITING_CLIENT"
    WAITING_AGENT = "WAITING_AGENT"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class MessageSenderType(str, enum.Enum):
    CUSTOMER = "CUSTOMER"
    AGENT = "AGENT"
    AI = "AI"
    SYSTEM = "SYSTEM"


class MessageType(str, enum.Enum):
    TEXT = "TEXT"
    VOICE = "VOICE"
    IMAGE = "IMAGE"
    NOTE = "NOTE"


class PropertyOfferStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PREPARED = "PREPARED"
    SHARED = "SHARED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


# -------------------------------------------------------------------------
# Core Tenancy & Users
# -------------------------------------------------------------------------

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    domain = Column(String(255), unique=True, index=True, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    settings = Column(JSON, default={}, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    users = relationship("User", back_populates="company", cascade="all, delete-orphan")
    teams = relationship("Team", back_populates="company", cascade="all, delete-orphan")
    leads = relationship("Lead", back_populates="company", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="company", cascade="all, delete-orphan")
    properties = relationship("Property", back_populates="company", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="company", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    role = Column(SAEnum(UserRole), default=UserRole.SALES_AGENT, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company", back_populates="users")
    team = relationship("Team", foreign_keys=[team_id], back_populates="members")
    assigned_leads = relationship("Lead", back_populates="assigned_agent", foreign_keys="Lead.assigned_agent_id")
    assigned_conversations = relationship("Conversation", back_populates="assigned_agent", foreign_keys="Conversation.assigned_agent_id")
    agent_profile = relationship("SalesAgentProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    activities = relationship("Activity", back_populates="user")
    followups = relationship("FollowUp", back_populates="assigned_user", foreign_keys="FollowUp.assigned_user_id")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    created_offers = relationship("PropertyOffer", back_populates="created_by", foreign_keys="PropertyOffer.created_by_id")


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    leader_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company", back_populates="teams")
    leader = relationship("User", foreign_keys=[leader_id])
    members = relationship("User", foreign_keys=[User.team_id], back_populates="team")
    leads = relationship("Lead", back_populates="team")


# -------------------------------------------------------------------------
# Location Hierarchy: Governorates, Cities, Districts
# -------------------------------------------------------------------------

class Governorate(Base):
    __tablename__ = "governorates"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    name_ar = Column(String(100), nullable=False)
    name_en = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    cities = relationship("City", back_populates="governorate", cascade="all, delete-orphan")


class City(Base):
    __tablename__ = "cities"

    id = Column(Integer, primary_key=True, index=True)
    governorate_id = Column(Integer, ForeignKey("governorates.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    name_ar = Column(String(100), nullable=False)
    name_en = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    governorate = relationship("Governorate", back_populates="cities")
    districts = relationship("District", back_populates="city", cascade="all, delete-orphan")


class District(Base):
    __tablename__ = "districts"

    id = Column(Integer, primary_key=True, index=True)
    city_id = Column(Integer, ForeignKey("cities.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    name_ar = Column(String(100), nullable=False)
    name_en = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    city = relationship("City", back_populates="districts")
    projects = relationship("Project", back_populates="district")


# -------------------------------------------------------------------------
# Inventory: Projects & Properties
# -------------------------------------------------------------------------

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    developer = Column(String(255), nullable=False)
    location = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    project_type = Column(String(100), default="Residential")  # Residential, Commercial, Mixed-use
    status = Column(String(50), default="Under Construction")  # Ready to move, Launching, etc.
    governorate_id = Column(Integer, ForeignKey("governorates.id", ondelete="SET NULL"), nullable=True, index=True)
    city_id = Column(Integer, ForeignKey("cities.id", ondelete="SET NULL"), nullable=True, index=True)
    district_id = Column(Integer, ForeignKey("districts.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_archived = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company", back_populates="projects")
    properties = relationship("Property", back_populates="project", cascade="all, delete-orphan")
    governorate = relationship("Governorate", foreign_keys=[governorate_id])
    city_rel = relationship("City", foreign_keys=[city_id])
    district = relationship("District", foreign_keys=[district_id], back_populates="projects")


class Property(Base):
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), nullable=True)
    unit_number = Column(String(50), nullable=False)
    property_type = Column(String(100), default="Apartment")  # Villa, Townhouse, Duplex, Apartment, Penthouse
    city = Column(String(100), default="Cairo")
    location = Column(String(255), default="New Cairo")
    governorate_id = Column(Integer, ForeignKey("governorates.id", ondelete="SET NULL"), nullable=True, index=True)
    city_id = Column(Integer, ForeignKey("cities.id", ondelete="SET NULL"), nullable=True, index=True)
    district_id = Column(Integer, ForeignKey("districts.id", ondelete="SET NULL"), nullable=True, index=True)
    area = Column(Float, nullable=False)  # in sqm
    bedrooms = Column(Integer, default=2)
    bathrooms = Column(Integer, default=2)
    floor = Column(Integer, default=1)
    view = Column(String(100), default="Landscape")  # Pool, Garden, Lake, Street
    finishing_status = Column(String(100), default="Semi-Finished")  # Core & Shell, Fully Finished
    delivery_date = Column(String(50), default="2026-12-31")
    total_price = Column(Float, nullable=False)  # Decimal stored as Float/Numeric
    currency = Column(String(10), default="EGP")
    down_payment = Column(Float, default=0.0)
    installment_plan = Column(String(100), default="8 Years Equal")
    installment_frequency = Column(String(50), default="Quarterly")
    remaining_balance = Column(Float, default=0.0)
    availability_status = Column(SAEnum(PropertyStatus), default=PropertyStatus.AVAILABLE, nullable=False, index=True)
    is_archived = Column(Boolean, default=False, nullable=False)
    # Which lead holds this unit (set when the lead reaches RESERVATION / WON)
    reserved_for_lead_id = Column(Integer, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)
    reserved_at = Column(DateTime, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company", back_populates="properties")
    project = relationship("Project", back_populates="properties")
    reserved_for_lead = relationship("Lead", foreign_keys=[reserved_for_lead_id])
    governorate = relationship("Governorate", foreign_keys=[governorate_id])
    city_rel = relationship("City", foreign_keys=[city_id])
    district = relationship("District", foreign_keys=[district_id])
    images = relationship("PropertyImage", back_populates="property", cascade="all, delete-orphan", order_by="PropertyImage.sort_order")
    videos = relationship("PropertyVideo", back_populates="property", cascade="all, delete-orphan", order_by="PropertyVideo.sort_order")
    features = relationship("PropertyFeature", back_populates="property", cascade="all, delete-orphan")
    offers = relationship("PropertyOffer", back_populates="property", cascade="all, delete-orphan")


# -------------------------------------------------------------------------
# Leads & CRM Core
# -------------------------------------------------------------------------

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name = Column(String(255), nullable=False, index=True)
    phone = Column(String(50), nullable=False, index=True)
    email = Column(String(255), nullable=True)
    preferred_contact_method = Column(String(50), default="WhatsApp")  # Phone, WhatsApp, Email
    source = Column(String(100), default="Meta Ads")  # Facebook, Google, Referral, Walk-in
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_agent_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    status = Column(String(50), default="Active")
    pipeline_stage = Column(SAEnum(PipelineStage), default=PipelineStage.NEW, nullable=False, index=True)
    
    # Customer Preferences & Requirements
    budget_min = Column(Float, nullable=True, default=None)
    budget_max = Column(Float, nullable=True, default=None)
    preferred_project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    preferred_location = Column(String(255), default="")
    property_type = Column(String(100), default="Apartment")
    preferred_area_range = Column(String(100), default="")
    bedrooms = Column(Integer, default=0)
    down_payment_budget = Column(Float, default=0.0)
    purchase_timeline = Column(String(100), default="Immediate (1 month)")  # 1-3 months, 6 months+
    
    notes = Column(Text, default="")
    tags = Column(String(255), default="")
    do_not_contact = Column(Boolean, default=False, nullable=False)
    
    last_contact_date = Column(DateTime, nullable=True)
    next_followup_date = Column(DateTime, nullable=True)
    priority = Column(SAEnum(PriorityLevel), default=PriorityLevel.MEDIUM, nullable=False)
    score = Column(Integer, default=50)  # 0 to 100 explainable score
    score_factors = Column(JSON, default=list, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    company = relationship("Company", back_populates="leads")
    team = relationship("Team", back_populates="leads")
    assigned_agent = relationship("User", foreign_keys=[assigned_agent_id], back_populates="assigned_leads")
    preferred_project = relationship("Project", foreign_keys=[preferred_project_id])
    
    activities = relationship("Activity", back_populates="lead", cascade="all, delete-orphan", order_by="desc(Activity.created_at)")
    followups = relationship("FollowUp", back_populates="lead", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="lead", cascade="all, delete-orphan")
    transfer_requests = relationship("LeadTransferRequest", back_populates="lead", cascade="all, delete-orphan")
    assignment_history = relationship("LeadAssignmentHistory", back_populates="lead", cascade="all, delete-orphan", order_by="desc(LeadAssignmentHistory.created_at)")
    conversations = relationship("Conversation", back_populates="lead", cascade="all, delete-orphan", order_by="desc(Conversation.last_message_time)")
    property_offers = relationship("PropertyOffer", back_populates="lead", cascade="all, delete-orphan", order_by="desc(PropertyOffer.created_at)")


# -------------------------------------------------------------------------
# Activities, Visits & Objections
# -------------------------------------------------------------------------

class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    activity_type = Column(SAEnum(ActivityType), default=ActivityType.CALL, nullable=False)
    summary = Column(Text, nullable=False)
    outcome = Column(String(255), default="")  # Interested, Rejected Property, Visited, Price Objection
    objection = Column(String(255), default="")  # Price too high, Down payment too high, Location, Layout
    sentiment = Column(String(50), default="Neutral")  # Positive, Neutral, Hesitant, Negative
    next_action = Column(String(255), default="")
    next_followup_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company")
    lead = relationship("Lead", back_populates="activities")
    property = relationship("Property")
    user = relationship("User", back_populates="activities")


# -------------------------------------------------------------------------
# Follow-ups & Tasks
# -------------------------------------------------------------------------

class FollowUp(Base):
    __tablename__ = "followups"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True)
    assigned_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    
    follow_up_type = Column(String(50), default="Call")  # Call, WhatsApp, Meeting, Property Visit, Task
    purpose = Column(String(255), nullable=False)
    due_date = Column(DateTime, nullable=False, index=True)
    priority = Column(SAEnum(PriorityLevel), default=PriorityLevel.MEDIUM, nullable=False)
    status = Column(SAEnum(FollowUpStatus), default=FollowUpStatus.PENDING, nullable=False, index=True)
    
    notes = Column(Text, default="")
    completion_outcome = Column(String(255), default="")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    company = relationship("Company")
    lead = relationship("Lead", back_populates="followups")
    assigned_user = relationship("User", foreign_keys=[assigned_user_id], back_populates="followups")
    created_by = relationship("User", foreign_keys=[created_by_id])


# -------------------------------------------------------------------------
# Appointments & Calendar
# -------------------------------------------------------------------------

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    title = Column(String(255), nullable=False)
    appointment_type = Column(String(100), default="Property Visit")  # Office Meeting, Property Visit, Video Call
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    location = Column(String(255), default="")
    notes = Column(Text, default="")
    status = Column(SAEnum(AppointmentStatus), default=AppointmentStatus.SCHEDULED, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company")
    lead = relationship("Lead", back_populates="appointments")
    property = relationship("Property")
    user = relationship("User")


# -------------------------------------------------------------------------
# Lead Transfers & Assignment History
# -------------------------------------------------------------------------

class LeadTransferRequest(Base):
    __tablename__ = "lead_transfer_requests"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    current_owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    requested_owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    requested_by_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    reason = Column(String(255), nullable=False)
    notes = Column(Text, default="")
    status = Column(SAEnum(TransferStatus), default=TransferStatus.PENDING, nullable=False, index=True)
    
    reviewer_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)

    company = relationship("Company")
    lead = relationship("Lead", back_populates="transfer_requests")
    current_owner = relationship("User", foreign_keys=[current_owner_id])
    requested_owner = relationship("User", foreign_keys=[requested_owner_id])
    requested_by = relationship("User", foreign_keys=[requested_by_id])
    reviewer = relationship("User", foreign_keys=[reviewer_id])


class LeadAssignmentHistory(Base):
    __tablename__ = "lead_assignment_history"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_agent_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    new_agent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    changed_by_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reason = Column(String(255), default="Manual Reassignment")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company")
    lead = relationship("Lead", back_populates="assignment_history")
    previous_agent = relationship("User", foreign_keys=[previous_agent_id])
    new_agent = relationship("User", foreign_keys=[new_agent_id])
    changed_by = relationship("User", foreign_keys=[changed_by_id])


# -------------------------------------------------------------------------
# Notifications & Audit Logs
# -------------------------------------------------------------------------

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    link = Column(String(255), default="")
    notification_type = Column(String(50), default="INFO")  # LEAD_ASSIGNED, TRANSFER_REQUEST, OVERDUE_TASK
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company")
    user = relationship("User", back_populates="notifications")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)  # CREATE_LEAD, STAGE_CHANGE, TRANSFER_LEAD, PROPERTY_STATUS
    entity_type = Column(String(100), nullable=False)  # Lead, Property, TransferRequest
    entity_id = Column(Integer, nullable=False)
    before_state = Column(JSON, default=dict)
    after_state = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company")
    actor = relationship("User")


# -------------------------------------------------------------------------
# Omnichannel Conversations & Messages
# -------------------------------------------------------------------------

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_agent_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True)

    channel = Column(SAEnum(ConversationChannel), default=ConversationChannel.WHATSAPP, nullable=False, index=True)
    status = Column(SAEnum(ConversationStatus), default=ConversationStatus.OPEN, nullable=False, index=True)
    customer_name = Column(String(255), nullable=False)
    customer_phone = Column(String(50), nullable=True, index=True)
    customer_identifier = Column(String(255), nullable=True)  # WhatsApp JID, Meta PSID, etc.

    unread_count = Column(Integer, default=0, nullable=False)
    ai_enabled = Column(Boolean, default=True, nullable=False)
    human_takeover = Column(Boolean, default=False, nullable=False)
    last_message_text = Column(Text, default="", nullable=False)
    last_message_time = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    ai_summary = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    company = relationship("Company", back_populates="conversations")
    lead = relationship("Lead", back_populates="conversations")
    assigned_agent = relationship("User", foreign_keys=[assigned_agent_id], back_populates="assigned_conversations")
    team = relationship("Team")
    messages = relationship("ConversationMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="ConversationMessage.created_at")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_type = Column(SAEnum(MessageSenderType), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    message_type = Column(SAEnum(MessageType), default=MessageType.TEXT, nullable=False)
    content = Column(Text, nullable=False)
    audio_url = Column(String(500), nullable=True)
    audio_duration = Column(Float, nullable=True)
    is_internal_note = Column(Boolean, default=False, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    conversation = relationship("Conversation", back_populates="messages")
    company = relationship("Company")
    sender = relationship("User")


# -------------------------------------------------------------------------
# Sales Agent Profiles (AI, Voice, Targets)
# -------------------------------------------------------------------------

class SalesAgentProfile(Base):
    __tablename__ = "sales_agent_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)

    personality_prompt = Column(Text, default="مندوب مبيعات عقاري محترف، ودود ولبق، يتحدث باللهجة المصرية الطبيعية بإيجاز واحترافية.")
    preferred_voice = Column(String(100), default="ar-EG-SalmaNeural")
    speaking_rate = Column(String(20), default="+20%")
    working_hours_start = Column(String(10), default="09:00")
    working_hours_end = Column(String(10), default="18:00")
    max_active_leads = Column(Integer, default=50)
    is_accepting_leads = Column(Boolean, default=True, nullable=False)
    monthly_target_sales = Column(Float, default=10000000.0)
    target_visits_per_month = Column(Integer, default=20)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="agent_profile")
    company = relationship("Company")


# -------------------------------------------------------------------------
# Voice & AI Telemetry Metrics
# -------------------------------------------------------------------------

class VoiceMetric(Base):
    __tablename__ = "voice_metrics"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    session_id = Column(String(100), index=True, nullable=True)
    stage = Column(String(50), nullable=False)  # "STT", "LLM", "TTS", "E2E"
    provider = Column(String(50), nullable=False)  # "groq-whisper", "edge-tts", "browser", "qwen"
    duration_ms = Column(Float, default=0.0, nullable=False)
    success = Column(Boolean, default=True, nullable=False)
    error_category = Column(String(100), nullable=True)
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    company = relationship("Company")
    user = relationship("User")


# -------------------------------------------------------------------------
# Property Images, Features, Offers & AI State
# -------------------------------------------------------------------------

class PropertyImage(Base):
    __tablename__ = "property_images"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    image_url = Column(String(500), nullable=False)
    caption = Column(String(255), nullable=True)
    is_primary = Column(Boolean, default=False, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company")
    property = relationship("Property", back_populates="images")


class PropertyVideo(Base):
    __tablename__ = "property_videos"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    video_url = Column(String(500), nullable=False)
    video_type = Column(String(50), default="EXTERNAL")  # "UPLOAD" or "EXTERNAL" (YouTube, Drive, direct)
    title = Column(String(255), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company")
    property = relationship("Property", back_populates="videos")



class PropertyFeature(Base):
    __tablename__ = "property_features"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    value = Column(String(255), nullable=False)

    property = relationship("Property", back_populates="features")


class PropertyOffer(Base):
    __tablename__ = "property_offers"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(SAEnum(PropertyOfferStatus), default=PropertyOfferStatus.PREPARED, nullable=False, index=True)
    custom_price = Column(Float, nullable=True)
    message_text = Column(Text, nullable=True)
    shared_via = Column(String(50), default="WHATSAPP", nullable=False)
    shared_at = Column(DateTime, nullable=True)
    customer_feedback = Column(Text, nullable=True)
    feedback_recorded_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    company = relationship("Company")
    lead = relationship("Lead", back_populates="property_offers")
    property = relationship("Property", back_populates="offers")
    created_by = relationship("User", foreign_keys=[created_by_id], back_populates="created_offers")


class AIConversationState(Base):
    __tablename__ = "ai_conversation_states"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(100), unique=True, index=True, nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    intent = Column(String(100), nullable=True)
    entity = Column(String(100), nullable=True)
    collected_fields = Column(JSON, default=dict, nullable=False)
    missing_fields = Column(JSON, default=list, nullable=False)
    pending_tool = Column(String(100), nullable=True)
    confirmation_status = Column(String(50), default="NONE", nullable=False)
    confirmation_preview = Column(JSON, default=dict, nullable=False)
    context_expiration = Column(DateTime, nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company")
    user = relationship("User")


# -------------------------------------------------------------------------
# AI Marketing Studio & Auto Publishing Models
# -------------------------------------------------------------------------

class MarketingGenerationStatus(str, enum.Enum):
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MarketingPublishingStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class MarketingLogStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    INFO = "INFO"


class MarketingPost(Base):
    __tablename__ = "marketing_posts"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    topic = Column(String(255), nullable=False)
    headline = Column(String(255), nullable=False)
    caption = Column(Text, nullable=False)
    image_prompt = Column(Text, nullable=False)
    image_path = Column(String(500), nullable=True)
    raw_image_path = Column(String(500), nullable=True)
    generation_provider = Column(String(50), default="gemini", nullable=False)
    generation_model = Column(String(100), default="gemini-1.5-flash", nullable=False)
    image_provider = Column(String(50), default="cloudflare", nullable=False)
    image_model = Column(String(100), default="@cf/black-forest-labs/flux-1-schnell", nullable=False)
    generation_status = Column(SAEnum(MarketingGenerationStatus), default=MarketingGenerationStatus.PENDING, nullable=False, index=True)
    publishing_status = Column(SAEnum(MarketingPublishingStatus), default=MarketingPublishingStatus.DRAFT, nullable=False, index=True)
    facebook_post_id = Column(String(100), nullable=True)
    facebook_permalink_url = Column(String(500), nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    post_date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD for daily uniqueness
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    company = relationship("Company")
    logs = relationship("MarketingLog", back_populates="post", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_marketing_posts_company_date", "company_id", "post_date"),
    )


class MarketingSetting(Base):
    __tablename__ = "marketing_settings"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    auto_generation_enabled = Column(Boolean, default=True, nullable=False)
    auto_publishing_enabled = Column(Boolean, default=False, nullable=False)
    generation_time = Column(String(10), default="19:00", nullable=False)
    publishing_time = Column(String(10), default="20:00", nullable=False)
    timezone = Column(String(50), default="Africa/Cairo", nullable=False)
    text_provider = Column(String(50), default="gemini", nullable=False)
    text_model = Column(String(100), default="gemini-1.5-flash", nullable=False)
    image_provider = Column(String(50), default="cloudflare", nullable=False)
    image_model = Column(String(100), default="@cf/black-forest-labs/flux-1-schnell", nullable=False)
    facebook_page_id = Column(String(100), nullable=True)
    facebook_page_name = Column(String(255), nullable=True)
    facebook_access_token = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    company = relationship("Company")


class MarketingLog(Base):
    __tablename__ = "marketing_logs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("marketing_posts.id", ondelete="CASCADE"), nullable=True, index=True)
    action = Column(String(100), nullable=False)
    status = Column(SAEnum(MarketingLogStatus), default=MarketingLogStatus.INFO, nullable=False)
    error_message = Column(Text, nullable=True)
    details = Column(JSON, default=dict, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company")
    post = relationship("MarketingPost", back_populates="logs")

