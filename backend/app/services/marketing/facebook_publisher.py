import os
import logging
from typing import Dict, Any, Optional, List
import httpx

from backend.app.core.config import settings

logger = logging.getLogger("marketing.facebook")


class FacebookPublisher:
    """
    Direct integration with Meta Graph API for Facebook Page publishing.
    Supports token validation, permission checks, and photo post publishing.
    """

    def __init__(
        self,
        api_version: Optional[str] = None,
        default_page_id: Optional[str] = None,
        default_token: Optional[str] = None
    ):
        self.api_version = (api_version or getattr(settings, "FACEBOOK_API_VERSION", "v20.0")).strip()
        self.default_page_id = (default_page_id or getattr(settings, "FACEBOOK_PAGE_ID", "")).strip()
        self.default_token = (default_token or getattr(settings, "FACEBOOK_PAGE_ACCESS_TOKEN", "")).strip()
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

    async def test_connection(
        self,
        page_id: Optional[str] = None,
        access_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validates page access token and returns page details and permissions.
        """
        target_page_id = (page_id or self.default_page_id).strip()
        target_token = (access_token or self.default_token).strip()

        if not target_page_id or not target_token:
            return {
                "connected": False,
                "page_id": target_page_id or None,
                "page_name": None,
                "message": "بيانات الربط غير مكتملة. يرجى إدخال معرف الصفحة (Page ID) ورمز الوصول (Page Access Token).",
                "permissions": []
            }

        url = f"{self.base_url}/{target_page_id}"
        params = {
            "fields": "id,name,category,tasks",
            "access_token": target_token
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, params=params)
                data = response.json()

                if response.status_code != 200 or "error" in data:
                    err = data.get("error", {})
                    err_msg = err.get("message", "فشل التحقق من صفحة فيسبوك.")
                    err_code = err.get("code")
                    logger.warning(f"Facebook Graph API validation error ({err_code}): {err_msg}")
                    return {
                        "connected": False,
                        "page_id": target_page_id,
                        "page_name": None,
                        "message": f"خطأ من فيسبوك: {err_msg} (رمز: {err_code})",
                        "permissions": []
                    }

                page_name = data.get("name", "صفحة فيسبوك")
                tasks = data.get("tasks", [])

                return {
                    "connected": True,
                    "page_id": data.get("id", target_page_id),
                    "page_name": page_name,
                    "message": f"تم الاتصال بنجاح بصفحة: {page_name}",
                    "permissions": tasks
                }
        except httpx.RequestError as e:
            logger.error(f"Network error while connecting to Facebook: {e}")
            return {
                "connected": False,
                "page_id": target_page_id,
                "page_name": None,
                "message": f"تعذر الاتصال بـ Meta Graph API: {str(e)}",
                "permissions": []
            }

    async def publish_photo_post(
        self,
        page_id: str,
        access_token: str,
        image_absolute_path: str,
        caption: str
    ) -> Dict[str, Any]:
        """
        Publishes a photo with caption to the specified Facebook Page feed.
        Endpoint: POST /{page_id}/photos
        """
        page_id = page_id.strip()
        access_token = access_token.strip()

        if not page_id or not access_token:
            raise ValueError("Facebook Page ID and Page Access Token are required to publish.")

        if not os.path.exists(image_absolute_path):
            raise FileNotFoundError(f"Marketing image not found at {image_absolute_path}")

        url = f"{self.base_url}/{page_id}/photos"
        filename = os.path.basename(image_absolute_path)

        with open(image_absolute_path, "rb") as img_file:
            files = {
                "source": (filename, img_file, "image/png")
            }
            data = {
                "caption": caption,
                "access_token": access_token
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, data=data, files=files)
                res_data = response.json()

                if response.status_code != 200 or "error" in res_data:
                    err = res_data.get("error", {})
                    msg = err.get("message", "خطأ في النشر التلقائي على فيسبوك")
                    code = err.get("code")
                    subcode = err.get("error_subcode")
                    logger.error(f"Facebook publish failed: {msg} (code: {code}, subcode: {subcode})")
                    raise RuntimeError(f"Meta Graph API error ({code}): {msg}")

                photo_id = res_data.get("id")
                post_id = res_data.get("post_id") or photo_id
                permalink = f"https://www.facebook.com/{post_id}" if post_id else None

                logger.info(f"Published marketing post to Facebook Page {page_id}, post ID: {post_id}")
                return {
                    "photo_id": photo_id,
                    "post_id": post_id,
                    "permalink_url": permalink,
                    "raw_response": res_data
                }

