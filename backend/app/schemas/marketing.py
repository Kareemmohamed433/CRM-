from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from backend.app.models.models import MarketingGenerationStatus, MarketingPublishingStatus, MarketingLogStatus


class MarketingLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    post_id: Optional[int] = None
    action: str
    status: MarketingLogStatus
    error_message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    created_at: datetime


class MarketingPostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    topic: str
    headline: str
    caption: str
    image_prompt: str
    image_path: Optional[str] = None
    raw_image_path: Optional[str] = None
    generation_provider: str
    generation_model: str
    image_provider: str
    image_model: str
    generation_status: MarketingGenerationStatus
    publishing_status: MarketingPublishingStatus
    facebook_post_id: Optional[str] = None
    facebook_permalink_url: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    post_date: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MarketingPostUpdate(BaseModel):
    headline: Optional[str] = None
    caption: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    publishing_status: Optional[MarketingPublishingStatus] = None


class MarketingSettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    auto_generation_enabled: bool
    auto_publishing_enabled: bool
    generation_time: str
    publishing_time: str
    timezone: str
    text_provider: str
    text_model: str
    image_provider: str
    image_model: str
    facebook_page_id: Optional[str] = None
    facebook_page_name: Optional[str] = None
    has_facebook_token: bool = False
    created_at: datetime
    updated_at: datetime


class MarketingSettingUpdate(BaseModel):
    auto_generation_enabled: Optional[bool] = None
    auto_publishing_enabled: Optional[bool] = None
    generation_time: Optional[str] = None
    publishing_time: Optional[str] = None
    timezone: Optional[str] = None
    text_provider: Optional[str] = None
    text_model: Optional[str] = None
    image_provider: Optional[str] = None
    image_model: Optional[str] = None
    facebook_page_id: Optional[str] = None
    facebook_page_name: Optional[str] = None
    facebook_access_token: Optional[str] = None


class FacebookConnectionTestRequest(BaseModel):
    page_id: Optional[str] = None
    page_access_token: Optional[str] = None


class FacebookConnectionTestResponse(BaseModel):
    connected: bool
    page_id: Optional[str] = None
    page_name: Optional[str] = None
    message: str
    permissions: List[str] = []


class MarketingDashboardStats(BaseModel):
    total_posts: int
    published_posts: int
    scheduled_posts: int
    failed_posts: int
    draft_posts: int
    next_scheduled_post: Optional[datetime] = None
    last_published_at: Optional[datetime] = None
    auto_publishing_enabled: bool
    auto_generation_enabled: bool
    facebook_connected: bool
    facebook_page_name: Optional[str] = None


class GenerateTodayPostRequest(BaseModel):
    topic: Optional[str] = None  # Optional custom topic, otherwise rotated by AI
    force: bool = False  # If True, replace today's draft if not yet published

