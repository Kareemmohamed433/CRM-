from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user
from backend.app.models.models import (
    User, UserRole, MarketingPost, MarketingSetting, MarketingLog,
    MarketingPublishingStatus
)
from backend.app.schemas.marketing import (
    MarketingPostOut, MarketingPostUpdate,
    MarketingSettingOut, MarketingSettingUpdate,
    MarketingLogOut, MarketingDashboardStats,
    GenerateTodayPostRequest,
    FacebookConnectionTestRequest, FacebookConnectionTestResponse
)
from backend.app.services.marketing.marketing_service import MarketingService
from backend.app.services.marketing.facebook_publisher import FacebookPublisher

router = APIRouter(prefix="/marketing", tags=["AI Marketing Studio"])

# Authorized roles for marketing studio
ALLOWED_ROLES = [UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.SALES_MANAGER]


def verify_marketing_access(current_user: User):
    if current_user.role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="غير مصرح لك بالوصول إلى أستوديو التسويق الذكي. الصلاحية مقتصرة على مدراء النظام ومدراء المبيعات."
        )


@router.get("/stats", response_model=MarketingDashboardStats)
def get_marketing_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns overview KPIs for the AI Marketing Studio dashboard."""
    verify_marketing_access(current_user)
    service = MarketingService(db)
    return service.get_dashboard_stats(company_id=current_user.company_id)


@router.get("/posts", response_model=List[MarketingPostOut])
def list_marketing_posts(
    status_filter: Optional[MarketingPublishingStatus] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns paginated list of generated marketing posts for company."""
    verify_marketing_access(current_user)
    query = db.query(MarketingPost).filter(MarketingPost.company_id == current_user.company_id)

    if status_filter:
        query = query.filter(MarketingPost.publishing_status == status_filter)

    posts = (
        query.order_by(MarketingPost.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return posts


@router.get("/posts/{post_id}", response_model=MarketingPostOut)
def get_marketing_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns details of a specific marketing post."""
    verify_marketing_access(current_user)
    post = (
        db.query(MarketingPost)
        .filter(MarketingPost.id == post_id, MarketingPost.company_id == current_user.company_id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="المنشور غير موجود.")
    return post


@router.post("/posts/generate", response_model=MarketingPostOut)
async def generate_today_post(
    request: GenerateTodayPostRequest = GenerateTodayPostRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually triggers AI marketing content generation and branding pipeline for today.
    Enforces exactly ONE post per calendar day unless force=True.
    """
    verify_marketing_access(current_user)
    service = MarketingService(db)
    try:
        post = await service.generate_daily_post(
            company_id=current_user.company_id,
            custom_topic=request.topic,
            force=request.force
        )
        return post
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"فشل توليد منشور اليوم: {str(e)}")


@router.post("/posts/{post_id}/regenerate-image", response_model=MarketingPostOut)
async def regenerate_post_image(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Regenerates the marketing image and branding for a specific draft post."""
    verify_marketing_access(current_user)
    service = MarketingService(db)
    try:
        post = await service.regenerate_image(company_id=current_user.company_id, post_id=post_id)
        return post
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"فشل إعادة توليد الصورة: {str(e)}")


@router.put("/posts/{post_id}", response_model=MarketingPostOut)
def update_marketing_post(
    post_id: int,
    updates: MarketingPostUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Allows manual editing of caption, headline, or scheduled publishing time."""
    verify_marketing_access(current_user)
    service = MarketingService(db)
    try:
        post = service.update_post(company_id=current_user.company_id, post_id=post_id, updates=updates)
        return post
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))


@router.post("/posts/{post_id}/approve", response_model=MarketingPostOut)
def approve_marketing_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Approves a draft post for auto-publishing."""
    verify_marketing_access(current_user)
    service = MarketingService(db)
    try:
        post = service.approve_post(company_id=current_user.company_id, post_id=post_id)
        return post
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.post("/posts/{post_id}/publish-now", response_model=MarketingPostOut)
async def publish_marketing_post_now(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Directly publishes the post and image to the connected Facebook Page."""
    verify_marketing_access(current_user)
    service = MarketingService(db)
    try:
        post = await service.publish_post_now(company_id=current_user.company_id, post_id=post_id)
        return post
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"فشل النشر على فيسبوك: {str(e)}")


@router.delete("/posts/{post_id}", status_code=204)
def delete_marketing_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deletes a draft or failed marketing post."""
    verify_marketing_access(current_user)
    service = MarketingService(db)
    try:
        service.delete_post(company_id=current_user.company_id, post_id=post_id)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.get("/settings", response_model=MarketingSettingOut)
def get_marketing_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves publishing and provider configuration for tenant."""
    verify_marketing_access(current_user)
    service = MarketingService(db)
    m_set = service.get_or_create_settings(company_id=current_user.company_id)
    return MarketingSettingOut(
        id=m_set.id,
        company_id=m_set.company_id,
        auto_generation_enabled=m_set.auto_generation_enabled,
        auto_publishing_enabled=m_set.auto_publishing_enabled,
        generation_time=m_set.generation_time,
        publishing_time=m_set.publishing_time,
        timezone=m_set.timezone,
        text_provider=m_set.text_provider,
        text_model=m_set.text_model,
        image_provider=m_set.image_provider,
        image_model=m_set.image_model,
        facebook_page_id=m_set.facebook_page_id,
        facebook_page_name=m_set.facebook_page_name,
        has_facebook_token=bool(m_set.facebook_access_token),
        created_at=m_set.created_at,
        updated_at=m_set.updated_at
    )


@router.put("/settings", response_model=MarketingSettingOut)
def update_marketing_settings(
    updates: MarketingSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Updates marketing automation settings."""
    verify_marketing_access(current_user)
    service = MarketingService(db)
    m_set = service.update_settings(company_id=current_user.company_id, updates=updates)
    return MarketingSettingOut(
        id=m_set.id,
        company_id=m_set.company_id,
        auto_generation_enabled=m_set.auto_generation_enabled,
        auto_publishing_enabled=m_set.auto_publishing_enabled,
        generation_time=m_set.generation_time,
        publishing_time=m_set.publishing_time,
        timezone=m_set.timezone,
        text_provider=m_set.text_provider,
        text_model=m_set.text_model,
        image_provider=m_set.image_provider,
        image_model=m_set.image_model,
        facebook_page_id=m_set.facebook_page_id,
        facebook_page_name=m_set.facebook_page_name,
        has_facebook_token=bool(m_set.facebook_access_token),
        created_at=m_set.created_at,
        updated_at=m_set.updated_at
    )


@router.post("/facebook/test-connection", response_model=FacebookConnectionTestResponse)
async def test_facebook_connection(
    req: FacebookConnectionTestRequest = FacebookConnectionTestRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Validates Facebook Page ID and Token via Meta Graph API."""
    verify_marketing_access(current_user)
    service = MarketingService(db)
    m_set = service.get_or_create_settings(company_id=current_user.company_id)

    page_id = req.page_id or m_set.facebook_page_id
    token = req.page_access_token or m_set.facebook_access_token

    publisher = FacebookPublisher()
    res = await publisher.test_connection(page_id=page_id, access_token=token)

    # If successful, save verified page name
    if res.get("connected") and res.get("page_name"):
        m_set.facebook_page_name = res.get("page_name")
        if req.page_id:
            m_set.facebook_page_id = req.page_id
        if req.page_access_token:
            m_set.facebook_access_token = req.page_access_token
        m_set.updated_at = db.query(MarketingSetting).first().updated_at  # keep updated
        db.commit()

    return res


@router.get("/logs", response_model=List[MarketingLogOut])
def list_marketing_logs(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns audit activity logs for marketing generation and publishing."""
    verify_marketing_access(current_user)
    logs = (
        db.query(MarketingLog)
        .filter(MarketingLog.company_id == current_user.company_id)
        .order_by(MarketingLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return logs

