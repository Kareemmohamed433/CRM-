"""
Storage Service for NEXORA CRM.
Handles secure file uploads, validation (MIME types, extensions, size limits),
and file storage abstraction (local directory with cloud storage extensibility).
"""

import os
import uuid
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".mkv"}
ALLOWED_VIDEO_MIME_TYPES = {"video/mp4", "video/webm", "video/quicktime", "video/x-matroska"}
MAX_VIDEO_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

BASE_UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "uploads"))
PROPERTY_UPLOAD_DIR = os.path.join(BASE_UPLOAD_DIR, "properties")


def ensure_upload_dirs():
    os.makedirs(PROPERTY_UPLOAD_DIR, exist_ok=True)


class StorageService:
    @staticmethod
    def validate_image(file_bytes: bytes, filename: str, content_type: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        if not file_bytes:
            return False, "File is empty."

        if len(file_bytes) > MAX_IMAGE_SIZE_BYTES:
            return False, f"File exceeds maximum allowed size of {MAX_IMAGE_SIZE_BYTES // (1024 * 1024)}MB."

        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            return False, f"Invalid file extension '{ext}'. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}."

        if content_type and content_type.lower() not in ALLOWED_IMAGE_MIME_TYPES:
            return False, f"Invalid MIME type '{content_type}'. Allowed: {', '.join(ALLOWED_IMAGE_MIME_TYPES)}."

        # Magic bytes check for image headers
        is_jpeg = file_bytes.startswith(b"\xff\xd8\xff")
        is_png = file_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        is_webp = file_bytes.startswith(b"RIFF") and b"WEBP" in file_bytes[:16]

        if not (is_jpeg or is_png or is_webp):
            return False, "Corrupted image file or unsupported image binary format."

        return True, None

    @staticmethod
    def validate_video(file_bytes: bytes, filename: str, content_type: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        if not file_bytes:
            return False, "File is empty."

        if len(file_bytes) > MAX_VIDEO_SIZE_BYTES:
            return False, f"Video file exceeds maximum allowed size of {MAX_VIDEO_SIZE_BYTES // (1024 * 1024)}MB."

        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_VIDEO_EXTENSIONS:
            return False, f"Invalid video extension '{ext}'. Allowed: {', '.join(ALLOWED_VIDEO_EXTENSIONS)}."

        if content_type and content_type.lower() not in ALLOWED_VIDEO_MIME_TYPES:
            return False, f"Invalid video MIME type '{content_type}'. Allowed: {', '.join(ALLOWED_VIDEO_MIME_TYPES)}."

        # Video magic bytes: MP4 has ftyp box at offset 4; WebM/MKV starts with \x1a\x45\xdf\xa3
        is_mp4_mov = len(file_bytes) >= 12 and (
            file_bytes[4:8] in [b"ftyp", b"moov", b"mdat", b"wide"] or b"ftyp" in file_bytes[:16]
        )
        is_webm_mkv = file_bytes.startswith(b"\x1a\x45\xdf\xa3")

        if not (is_mp4_mov or is_webm_mkv):
            return False, "Corrupted video file or unsupported video binary format."

        return True, None

    @classmethod
    def save_property_image(cls, file_bytes: bytes, filename: str, content_type: Optional[str] = None) -> str:
        ensure_upload_dirs()
        valid, err = cls.validate_image(file_bytes, filename, content_type)
        if not valid:
            raise ValueError(err)

        ext = os.path.splitext(filename)[1].lower()
        unique_name = f"prop_{uuid.uuid4().hex}{ext}"
        target_path = os.path.join(PROPERTY_UPLOAD_DIR, unique_name)

        with open(target_path, "wb") as f:
            f.write(file_bytes)

        logger.info(f"[StorageService] Saved property image to '{target_path}'")
        return f"/uploads/properties/{unique_name}"

    @classmethod
    def save_property_video(cls, file_bytes: bytes, filename: str, content_type: Optional[str] = None) -> str:
        ensure_upload_dirs()
        valid, err = cls.validate_video(file_bytes, filename, content_type)
        if not valid:
            raise ValueError(err)

        ext = os.path.splitext(filename)[1].lower()
        unique_name = f"prop_vid_{uuid.uuid4().hex}{ext}"
        target_path = os.path.join(PROPERTY_UPLOAD_DIR, unique_name)

        with open(target_path, "wb") as f:
            f.write(file_bytes)

        logger.info(f"[StorageService] Saved property video to '{target_path}'")
        return f"/uploads/properties/{unique_name}"

    @classmethod
    def delete_property_image(cls, image_url: str) -> bool:
        if not image_url or not image_url.startswith("/uploads/properties/"):
            return False

        filename = os.path.basename(image_url)
        target_path = os.path.join(PROPERTY_UPLOAD_DIR, filename)

        if os.path.exists(target_path):
            try:
                os.remove(target_path)
                logger.info(f"[StorageService] Deleted property image '{target_path}'")
                return True
            except Exception as e:
                logger.warning(f"[StorageService] Failed deleting image file '{target_path}': {e}")
                return False
        return False

    @classmethod
    def delete_property_video(cls, video_url: str) -> bool:
        if not video_url or not video_url.startswith("/uploads/properties/"):
            return False

        filename = os.path.basename(video_url)
        target_path = os.path.join(PROPERTY_UPLOAD_DIR, filename)

        if os.path.exists(target_path):
            try:
                os.remove(target_path)
                logger.info(f"[StorageService] Deleted property video '{target_path}'")
                return True
            except Exception as e:
                logger.warning(f"[StorageService] Failed deleting video file '{target_path}': {e}")
                return False
        return False


storage_service = StorageService()

