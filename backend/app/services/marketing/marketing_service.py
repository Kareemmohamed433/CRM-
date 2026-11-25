import os
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from backend.app.models.models import (
    MarketingPost, MarketingSetting, MarketingLog,
    MarketingGenerationStatus, MarketingPublishingStatus, MarketingLogStatus
)
from backend.app.schemas.marketing import MarketingPostUpdate, MarketingSettingUpdate
from backend.app.services.marketing.gemini_content_service import GeminiContentService
from backend.app.services.marketing.image_providers import get_image_provider
from backend.app.services.marketing.image_branding_service import ImageBrandingService, MARKETING_UPLOADS_DIR
from backend.app.services.marketing.facebook_publisher import FacebookPublisher
from backend.app.core.config import settings

logger = logging.getLogger("marketing.service")


class MarketingService:
    """
    Central orchestration service for daily marketing content generation,
    brand composition, and Facebook auto-publishing.
    """

    def __init__(self, db: Session):
        self.db = db
        self.branding_service = ImageBrandingService()
        self.fb_publisher = FacebookPublisher()

    def get_or_create_settings(self, company_id: int) -> MarketingSetting:
        """Retrieves or creates default marketing settings for tenant."""
        m_settings = self.db.query(MarketingSetting).filter(MarketingSetting.company_id == company_id).first()
        if not m_settings:
            m_settings = MarketingSetting(
                company_id=company_id,
                auto_generation_enabled=True,
                auto_publishing_enabled=False,  # Disabled by default until Facebook is connected
                generation_time="19:00",
                publishing_time="20:00",
                timezone=getattr(settings, "TIMEZONE", "Africa/Cairo"),
                text_provider="gemini",
                text_model=getattr(settings, "GEMINI_MODEL", "gemini-1.5-flash"),
                image_provider="cloudflare",
                image_model=getattr(settings, "CLOUDFLARE_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell"),
                facebook_page_id=getattr(settings, "FACEBOOK_PAGE_ID", None) or None,
                facebook_access_token=getattr(settings, "FACEBOOK_PAGE_ACCESS_TOKEN", None) or None,
            )
            self.db.add(m_settings)
            self.db.commit()
            self.db.refresh(m_settings)
        return m_settings

    def update_settings(self, company_id: int, updates: MarketingSettingUpdate) -> MarketingSetting:
        m_settings = self.get_or_create_settings(company_id)
        data = updates.model_dump(exclude_unset=True)

        for key, val in data.items():
            if val is not None:
                setattr(m_settings, key, val)

        m_settings.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(m_settings)

        self._log(
            company_id=company_id,
            action="UPDATE_SETTINGS",
            status=MarketingLogStatus.INFO,
            details={"updated_keys": list(data.keys())}
        )
        return m_settings

    def get_dashboard_stats(self, company_id: int) -> Dict[str, Any]:
        """Calculates overview KPI metrics for the marketing dashboard."""
        m_settings = self.get_or_create_settings(company_id)

        base_q = self.db.query(MarketingPost).filter(MarketingPost.company_id == company_id)

        total_posts = base_q.count()
        published_posts = base_q.filter(MarketingPost.publishing_status == MarketingPublishingStatus.PUBLISHED).count()
        scheduled_posts = base_q.filter(MarketingPost.publishing_status == MarketingPublishingStatus.SCHEDULED).count()
        failed_posts = base_q.filter(
            (MarketingPost.generation_status == MarketingGenerationStatus.FAILED) |
            (MarketingPost.publishing_status == MarketingPublishingStatus.FAILED)
        ).count()
        draft_posts = base_q.filter(MarketingPost.publishing_status == MarketingPublishingStatus.DRAFT).count()

        # Next scheduled post
        next_post = (
            base_q.filter(
                MarketingPost.publishing_status == MarketingPublishingStatus.SCHEDULED,
                MarketingPost.scheduled_at >= datetime.utcnow()
            )
            .order_by(MarketingPost.scheduled_at.asc())
            .first()
        )

        # Last published post
        last_pub = (
            base_q.filter(MarketingPost.publishing_status == MarketingPublishingStatus.PUBLISHED)
            .order_by(MarketingPost.published_at.desc())
            .first()
        )

        has_fb = bool(
            (m_settings.facebook_page_id and m_settings.facebook_access_token) or
            (settings.FACEBOOK_PAGE_ID and settings.FACEBOOK_PAGE_ACCESS_TOKEN)
        )

        return {
            "total_posts": total_posts,
            "published_posts": published_posts,
            "scheduled_posts": scheduled_posts,
            "failed_posts": failed_posts,
            "draft_posts": draft_posts,
            "next_scheduled_post": next_post.scheduled_at if next_post else None,
            "last_published_at": last_pub.published_at if last_pub else None,
            "auto_publishing_enabled": m_settings.auto_publishing_enabled,
            "auto_generation_enabled": m_settings.auto_generation_enabled,
            "facebook_connected": has_fb,
            "facebook_page_name": m_settings.facebook_page_name or ("Connected" if has_fb else None)
        }

    async def generate_daily_post(
        self,
        company_id: int,
        custom_topic: Optional[str] = None,
        force: bool = False
    ) -> MarketingPost:
        """
        Generates exactly ONE marketing post and image for today.
        Guarantees duplicate prevention.
        """
        m_settings = self.get_or_create_settings(company_id)
        today_str = datetime.utcnow().strftime("%Y-%m-%d")

        # Check existing post for today
        existing = (
            self.db.query(MarketingPost)
            .filter(
                MarketingPost.company_id == company_id,
                MarketingPost.post_date == today_str
            )
            .first()
        )

        if existing and not force:
            if existing.publishing_status == MarketingPublishingStatus.PUBLISHED:
                raise ValueError("تم نشر منشور اليوم بالفعل على صفحة فيسبوك ولا يمكن استبداله.")
            return existing

        # If forcing replacement of an existing unpublished post
        post = existing if existing else MarketingPost(
            company_id=company_id,
            topic="جاري التوليد...",
            headline="جاري التوليد...",
            caption="جاري التوليد...",
            image_prompt="",
            post_date=today_str,
            generation_status=MarketingGenerationStatus.GENERATING,
            publishing_status=MarketingPublishingStatus.DRAFT,
            generation_provider=m_settings.text_provider,
            generation_model=m_settings.text_model,
            image_provider=m_settings.image_provider,
            image_model=m_settings.image_model,
            created_at=datetime.utcnow()
        )

        if not existing:
            self.db.add(post)
        else:
            post.generation_status = MarketingGenerationStatus.GENERATING
            post.error_message = None

        self.db.commit()
        self.db.refresh(post)

        try:
            # 1. Fetch recent topics to avoid repetition
            recent_posts = (
                self.db.query(MarketingPost.topic)
                .filter(
                    MarketingPost.company_id == company_id,
                    MarketingPost.id != post.id
                )
                .order_by(MarketingPost.created_at.desc())
                .limit(7)
                .all()
            )
            recent_topics = [r[0] for r in recent_posts if r[0]]

            # 2. Text Content Generation via Gemini (or local fallback)
            content_service = GeminiContentService(model=m_settings.text_model)
            pkg = await content_service.generate_marketing_package(
                custom_topic=custom_topic,
                recent_topics=recent_topics
            )

            post.topic = pkg["topic"]
            post.headline = pkg["headline"]
            post.caption = pkg["caption"]
            post.image_prompt = pkg["image_prompt"]
            self.db.commit()

            self._log(
                company_id=company_id,
                post_id=post.id,
                action="GENERATE_TEXT",
                status=MarketingLogStatus.SUCCESS,
                details={"topic": post.topic, "headline": post.headline}
            )

            # 3. Generate exactly ONE raw image via Image Generation Provider
            img_provider = get_image_provider(
                provider_name=m_settings.image_provider,
                account_id=getattr(settings, "CLOUDFLARE_ACCOUNT_ID", None),
                api_token=getattr(settings, "CLOUDFLARE_API_TOKEN", None),
                model=m_settings.image_model
            )
            raw_image_bytes = await img_provider.generate_image(prompt=post.image_prompt)

            # 4. Apply NEXORA Brand Identity Pipeline
            branded_url, raw_url = self.branding_service.process_and_brand_image(
                raw_image_bytes=raw_image_bytes,
                headline=post.headline,
                post_id=post.id,
                post_date=today_str
            )

            post.image_path = branded_url
            post.raw_image_path = raw_url
            post.generation_status = MarketingGenerationStatus.COMPLETED

            # If auto-publishing is enabled, set status to SCHEDULED
            if m_settings.auto_publishing_enabled:
                post.publishing_status = MarketingPublishingStatus.SCHEDULED
                # Compute scheduled time today at publishing_time
                try:
                    pub_h, pub_m = map(int, m_settings.publishing_time.split(":"))
                    sched_dt = datetime.utcnow().replace(hour=pub_h, minute=pub_m, second=0)
                    post.scheduled_at = sched_dt
                except Exception:
                    post.scheduled_at = datetime.utcnow()
            else:
                post.publishing_status = MarketingPublishingStatus.DRAFT

            post.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(post)

            self._log(
                company_id=company_id,
                post_id=post.id,
                action="BRAND_IMAGE",
                status=MarketingLogStatus.SUCCESS,
                details={"image_path": post.image_path}
            )
            return post

        except Exception as e:
            logger.error(f"Failed to generate daily marketing post for company {company_id}: {e}", exc_info=True)
            post.generation_status = MarketingGenerationStatus.FAILED
            post.error_message = str(e)
            post.updated_at = datetime.utcnow()
            self.db.commit()

            self._log(
                company_id=company_id,
                post_id=post.id,
                action="GENERATE_POST",
                status=MarketingLogStatus.ERROR,
                error_message=str(e)
            )
            raise e

    async def regenerate_image(self, company_id: int, post_id: int) -> MarketingPost:
        """Explicit admin action to re-run image generation and branding for a draft post."""
        post = self._get_post(company_id, post_id)
        if post.publishing_status == MarketingPublishingStatus.PUBLISHED:
            raise ValueError("لا يمكن إعادة توليد صورة لمنشور تم نشره بالفعل.")

        m_settings = self.get_or_create_settings(company_id)
        try:
            img_provider = get_image_provider(
                provider_name=m_settings.image_provider,
                account_id=getattr(settings, "CLOUDFLARE_ACCOUNT_ID", None),
                api_token=getattr(settings, "CLOUDFLARE_API_TOKEN", None),
                model=m_settings.image_model
            )
            raw_bytes = await img_provider.generate_image(prompt=post.image_prompt)

            branded_url, raw_url = self.branding_service.process_and_brand_image(
                raw_image_bytes=raw_bytes,
                headline=post.headline,
                post_id=post.id,
                post_date=post.post_date
            )

            post.image_path = branded_url
            post.raw_image_path = raw_url
            post.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(post)

            self._log(
                company_id=company_id,
                post_id=post.id,
                action="REGENERATE_IMAGE",
                status=MarketingLogStatus.SUCCESS,
                details={"new_image": post.image_path}
            )
            return post
        except Exception as e:
            self._log(
                company_id=company_id,
                post_id=post.id,
                action="REGENERATE_IMAGE",
                status=MarketingLogStatus.ERROR,
                error_message=str(e)
            )
            raise e

    async def publish_post_now(self, company_id: int, post_id: int) -> MarketingPost:
        """Publishes post immediately to the connected Facebook Page."""
        post = self._get_post(company_id, post_id)
        if post.publishing_status == MarketingPublishingStatus.PUBLISHED:
            raise ValueError("المنشور منشور بالفعل على صفحة فيسبوك.")

        if not post.image_path:
            raise ValueError("لا توجد صورة مرتبطة بالمنشور لنشرها.")

        m_settings = self.get_or_create_settings(company_id)
        page_id = (m_settings.facebook_page_id or getattr(settings, "FACEBOOK_PAGE_ID", "")).strip()
        token = (m_settings.facebook_access_token or getattr(settings, "FACEBOOK_PAGE_ACCESS_TOKEN", "")).strip()

        if not page_id or not token:
            raise ValueError("بيانات صفحة فيسبوك غير متصلة. يرجى ضبط Page ID و Page Access Token في الإعدادات.")

        # Resolve absolute image path
        filename = os.path.basename(post.image_path)
        abs_path = os.path.join(MARKETING_UPLOADS_DIR, filename)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"لم يتم العثور على ملف الصورة: {abs_path}")

        post.publishing_status = MarketingPublishingStatus.PUBLISHING
        self.db.commit()

        try:
            res = await self.fb_publisher.publish_photo_post(
                page_id=page_id,
                access_token=token,
                image_absolute_path=abs_path,
                caption=post.caption
            )

            post.publishing_status = MarketingPublishingStatus.PUBLISHED
            post.facebook_post_id = res.get("post_id") or res.get("photo_id")
            post.facebook_permalink_url = res.get("permalink_url")
            post.published_at = datetime.utcnow()
            post.error_message = None
            post.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(post)

            self._log(
                company_id=company_id,
                post_id=post.id,
                action="PUBLISH_FACEBOOK",
                status=MarketingLogStatus.SUCCESS,
                details={"post_id": post.facebook_post_id, "url": post.facebook_permalink_url}
            )
            return post

        except Exception as e:
            post.publishing_status = MarketingPublishingStatus.FAILED
            post.error_message = f"فشل النشر على فيسبوك: {str(e)}"
            post.updated_at = datetime.utcnow()
            self.db.commit()

            self._log(
                company_id=company_id,
                post_id=post.id,
                action="PUBLISH_FACEBOOK",
                status=MarketingLogStatus.ERROR,
                error_message=str(e)
            )
            raise e

    def approve_post(self, company_id: int, post_id: int) -> MarketingPost:
        """Approves a draft post and marks it as SCHEDULED."""
        post = self._get_post(company_id, post_id)
        if post.publishing_status == MarketingPublishingStatus.PUBLISHED:
            return post

        post.publishing_status = MarketingPublishingStatus.SCHEDULED
        if not post.scheduled_at:
            post.scheduled_at = datetime.utcnow()
        post.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(post)

        self._log(
            company_id=company_id,
            post_id=post.id,
            action="APPROVE_POST",
            status=MarketingLogStatus.SUCCESS
        )
        return post

    def update_post(self, company_id: int, post_id: int, updates: MarketingPostUpdate) -> MarketingPost:
        post = self._get_post(company_id, post_id)
        if updates.headline is not None:
            post.headline = updates.headline
        if updates.caption is not None:
            post.caption = updates.caption
        if updates.scheduled_at is not None:
            post.scheduled_at = updates.scheduled_at
        if updates.publishing_status is not None:
            post.publishing_status = updates.publishing_status

        post.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(post)
        return post

    def delete_post(self, company_id: int, post_id: int):
        post = self._get_post(company_id, post_id)
        if post.publishing_status == MarketingPublishingStatus.PUBLISHED:
            raise ValueError("لا يمكن حذف منشور تم نشره بالفعل على منصات التواصل.")

        # Remove image files from disk if present
        if post.image_path:
            p = os.path.join(MARKETING_UPLOADS_DIR, os.path.basename(post.image_path))
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

        if post.raw_image_path:
            p = os.path.join(MARKETING_UPLOADS_DIR, os.path.basename(post.raw_image_path))
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

        self.db.delete(post)
        self.db.commit()

    def _get_post(self, company_id: int, post_id: int) -> MarketingPost:
        post = (
            self.db.query(MarketingPost)
            .filter(
                MarketingPost.id == post_id,
                MarketingPost.company_id == company_id
            )
            .first()
        )
        if not post:
            raise ValueError(f"منشور التسويق غير موجود: {post_id}")
        return post

    def _log(
        self,
        company_id: int,
        action: str,
        status: MarketingLogStatus,
        post_id: Optional[int] = None,
        error_message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        try:
            log_entry = MarketingLog(
                company_id=company_id,
                post_id=post_id,
                action=action,
                status=status,
                error_message=error_message,
                details=details or {},
                created_at=datetime.utcnow()
            )
            self.db.add(log_entry)
            self.db.commit()
        except Exception as le:
            logger.error(f"Failed to record marketing log: {le}")

