import pytest
import os
from datetime import datetime
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.models.models import (
    User, UserRole, Company, MarketingPost, MarketingSetting,
    MarketingGenerationStatus, MarketingPublishingStatus
)
from backend.app.core.security import create_access_token
from backend.app.services.marketing.gemini_content_service import GeminiContentService
from backend.app.services.marketing.image_providers import (
    MockProceduralImageProvider, CloudflareWorkersAIProvider, get_image_provider
)
from backend.app.services.marketing.image_branding_service import ImageBrandingService
from backend.app.services.marketing.marketing_service import MarketingService
from backend.app.services.marketing.facebook_publisher import FacebookPublisher

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def admin_headers(db_session):
    admin = db_session.query(User).filter(User.role == UserRole.COMPANY_ADMIN).first()
    if not admin:
        company = db_session.query(Company).first()
        admin = User(
            email="mkt_admin@nexora.com",
            hashed_password="hash",
            full_name="Marketing Admin",
            role=UserRole.COMPANY_ADMIN,
            company_id=company.id if company else 1,
            is_active=True
        )
        db_session.add(admin)
        db_session.commit()
        db_session.refresh(admin)

    token = create_access_token(data={"sub": admin.email, "company_id": admin.company_id, "role": admin.role.value})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def agent_headers(db_session):
    agent = db_session.query(User).filter(User.role == UserRole.SALES_AGENT).first()
    token = create_access_token(data={"sub": agent.email, "company_id": agent.company_id, "role": agent.role.value})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_gemini_content_service_rotation_and_copy():
    service = GeminiContentService()
    pkg1 = await service.generate_marketing_package()
    assert pkg1["topic"]
    assert pkg1["headline"]
    assert pkg1["caption"]
    assert pkg1["image_prompt"]
    assert "NEXORA" in pkg1["caption"]
    assert "Smart Replies" in pkg1["caption"]

    # Test non-repetition with recent topics
    pkg2 = await service.generate_marketing_package(recent_topics=[pkg1["topic"]])
    # With multiple available topics, pkg2 topic should prefer unvisited topic
    assert pkg2["headline"]


@pytest.mark.asyncio
async def test_image_provider_and_branding_pipeline(db_session):
    provider = MockProceduralImageProvider()
    raw_bytes = await provider.generate_image("Test Prompt", 1080, 1080)
    assert len(raw_bytes) > 1000
    assert raw_bytes.startswith(b"\x89PNG")

    branding = ImageBrandingService()
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    branded_path, raw_path = branding.process_and_brand_image(
        raw_image_bytes=raw_bytes,
        headline="ردود ذكية على مدار الساعة لمبيعات أسرع",
        post_id=888,
        post_date=today_str,
        target_width=1080,
        target_height=1350
    )

    assert branded_path.startswith("/uploads/marketing/")
    assert raw_path.startswith("/uploads/marketing/")

    # Check physical file existence on disk
    full_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", branded_path.lstrip("/")))
    assert os.path.exists(full_path)
    assert os.path.getsize(full_path) > 10000


@pytest.mark.asyncio
async def test_marketing_service_daily_workflow_and_duplicate_prevention(db_session):
    company = db_session.query(Company).first()
    service = MarketingService(db_session)

    # 1. Clean existing test posts for today to start fresh
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    db_session.query(MarketingPost).filter(
        MarketingPost.company_id == company.id,
        MarketingPost.post_date == today_str
    ).delete()
    db_session.commit()

    # 2. Generate today's post
    post1 = await service.generate_daily_post(company_id=company.id, force=False)
    assert post1.id
    assert post1.post_date == today_str
    assert post1.generation_status == MarketingGenerationStatus.COMPLETED
    assert post1.publishing_status in [MarketingPublishingStatus.DRAFT, MarketingPublishingStatus.SCHEDULED]
    assert post1.image_path is not None
    assert post1.headline

    # 3. Duplicate Prevention: Generating again on same date without force must return post1
    post2 = await service.generate_daily_post(company_id=company.id, force=False)
    assert post2.id == post1.id

    # 4. Approve post
    approved = service.approve_post(company_id=company.id, post_id=post1.id)
    assert approved.publishing_status == MarketingPublishingStatus.SCHEDULED

    # 5. Regenerate image
    regenerated = await service.regenerate_image(company_id=company.id, post_id=post1.id)
    assert regenerated.id == post1.id
    assert regenerated.image_path is not None


@pytest.mark.asyncio
async def test_facebook_publisher_connection_test():
    publisher = FacebookPublisher()
    # Test with empty credentials
    res = await publisher.test_connection(page_id="", access_token="")
    assert res["connected"] is False
    assert "غير مكتملة" in res["message"]

    # Test with dummy credentials
    res_dummy = await publisher.test_connection(page_id="123456", access_token="invalid_dummy_token")
    assert res_dummy["connected"] is False


def test_marketing_api_endpoints_and_rbac(admin_headers, agent_headers):
    # 1. Sales Agent should be forbidden (403)
    res_agent = client.get("/api/v1/marketing/stats", headers=agent_headers)
    assert res_agent.status_code == 403

    # 2. Admin should get 200 OK for stats
    res_stats = client.get("/api/v1/marketing/stats", headers=admin_headers)
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert "total_posts" in stats
    assert "published_posts" in stats

    # 3. List posts
    res_posts = client.get("/api/v1/marketing/posts", headers=admin_headers)
    assert res_posts.status_code == 200
    posts = res_posts.json()
    assert isinstance(posts, list)

    # 4. Settings GET and PUT
    res_get_settings = client.get("/api/v1/marketing/settings", headers=admin_headers)
    assert res_get_settings.status_code == 200
    settings_data = res_get_settings.json()
    assert "auto_generation_enabled" in settings_data

    res_put_settings = client.put(
        "/api/v1/marketing/settings",
        json={"auto_generation_enabled": True, "generation_time": "19:30"},
        headers=admin_headers
    )
    assert res_put_settings.status_code == 200
    assert res_put_settings.json()["generation_time"] == "19:30"

    # 5. Test Facebook Connection endpoint
    res_fb_test = client.post(
        "/api/v1/marketing/facebook/test-connection",
        json={"page_id": "test_page", "page_access_token": "test_token"},
        headers=admin_headers
    )
    assert res_fb_test.status_code == 200
    assert "connected" in res_fb_test.json()

    # 6. Audit Logs endpoint
    res_logs = client.get("/api/v1/marketing/logs", headers=admin_headers)
    assert res_logs.status_code == 200
    logs = res_logs.json()
    assert isinstance(logs, list)

