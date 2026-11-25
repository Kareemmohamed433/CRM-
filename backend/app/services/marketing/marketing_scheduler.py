import asyncio
import logging
from datetime import datetime
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
import zoneinfo

from backend.app.core.database import SessionLocal
from backend.app.models.models import (
    Company, MarketingSetting, MarketingPost,
    MarketingPublishingStatus, MarketingGenerationStatus
)
from backend.app.services.marketing.marketing_service import MarketingService

logger = logging.getLogger("marketing.scheduler")

_scheduler: Optional[BackgroundScheduler] = None


class MarketingScheduler:
    """
    Robust daily marketing scheduler operating strictly in the Africa/Cairo timezone.
    Periodically checks settings and database state to execute:
    1. Automated daily post generation (default 7:00 PM Cairo)
    2. Automated Facebook publishing (default 8:00 PM Cairo if enabled)
    """

    @classmethod
    def start(cls):
        global _scheduler
        if _scheduler and _scheduler.running:
            logger.info("Marketing scheduler is already running.")
            return

        try:
            cairo_tz = zoneinfo.ZoneInfo("Africa/Cairo")
        except Exception:
            cairo_tz = None

        _scheduler = BackgroundScheduler(timezone=cairo_tz)
        # Check every 60 seconds
        _scheduler.add_job(
            func=cls._run_tick,
            trigger="interval",
            seconds=60,
            id="marketing_daily_tick",
            replace_existing=True,
            max_instances=1,
            coalesce=True
        )
        _scheduler.start()
        logger.info("Marketing scheduler started successfully (Africa/Cairo).")

    @classmethod
    def shutdown(cls):
        global _scheduler
        if _scheduler and _scheduler.running:
            _scheduler.shutdown(wait=False)
            logger.info("Marketing scheduler stopped.")

    @classmethod
    def _run_tick(cls):
        """Worker tick executed every minute."""
        try:
            cairo_tz = zoneinfo.ZoneInfo("Africa/Cairo")
            now_cairo = datetime.now(cairo_tz)
        except Exception:
            now_cairo = datetime.utcnow()

        current_time_str = now_cairo.strftime("%H:%M")
        today_date_str = now_cairo.strftime("%Y-%m-%d")

        db = SessionLocal()
        try:
            # 1. Process Auto-Generation
            settings_list = (
                db.query(MarketingSetting)
                .filter(MarketingSetting.auto_generation_enabled == True)
                .all()
            )

            for m_set in settings_list:
                gen_time = m_set.generation_time.strip()
                if current_time_str == gen_time:
                    # Check if post already generated today
                    existing = (
                        db.query(MarketingPost)
                        .filter(
                            MarketingPost.company_id == m_set.company_id,
                            MarketingPost.post_date == today_date_str
                        )
                        .first()
                    )

                    if not existing:
                        logger.info(f"Triggering automated daily marketing generation for company {m_set.company_id} at {current_time_str} Cairo.")
                        # Run async generation in worker loop
                        service = MarketingService(db)
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(
                                service.generate_daily_post(company_id=m_set.company_id, force=False)
                            )
                            loop.close()
                        except Exception as ge:
                            logger.error(f"Automated generation error for company {m_set.company_id}: {ge}")

            # 2. Process Auto-Publishing for SCHEDULED posts
            scheduled_posts = (
                db.query(MarketingPost)
                .join(MarketingSetting, MarketingSetting.company_id == MarketingPost.company_id)
                .filter(
                    MarketingPost.publishing_status == MarketingPublishingStatus.SCHEDULED,
                    MarketingSetting.auto_publishing_enabled == True
                )
                .all()
            )

            for post in scheduled_posts:
                m_set = db.query(MarketingSetting).filter(MarketingSetting.company_id == post.company_id).first()
                if not m_set or not m_set.auto_publishing_enabled:
                    continue

                pub_time = m_set.publishing_time.strip()
                # If current time is publishing time or scheduled time has passed
                should_publish = False
                if current_time_str == pub_time:
                    should_publish = True
                elif post.scheduled_at and datetime.utcnow() >= post.scheduled_at:
                    should_publish = True

                if should_publish:
                    logger.info(f"Triggering automated Facebook publishing for post {post.id} (Company {post.company_id}).")
                    service = MarketingService(db)
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(
                            service.publish_post_now(company_id=post.company_id, post_id=post.id)
                        )
                        loop.close()
                    except Exception as pe:
                        logger.error(f"Automated Facebook publishing error for post {post.id}: {pe}")

        except Exception as e:
            logger.error(f"Error in marketing scheduler tick: {e}", exc_info=True)
        finally:
            db.close()

