import abc
import io
import math
import logging
from typing import Optional
import httpx
from PIL import Image, ImageDraw, ImageFilter

from backend.app.core.config import settings

logger = logging.getLogger("marketing.image_provider")


class ImageGenerationProvider(abc.ABC):
    """Abstract interface for external image generation APIs."""

    @abc.abstractmethod
    async def generate_image(self, prompt: str, width: int = 1024, height: int = 1024) -> bytes:
        """Generates exactly ONE raw marketing image given a visual prompt."""
        pass


class CloudflareWorkersAIProvider(ImageGenerationProvider):
    """
    Official Cloudflare Workers AI REST API integration using FLUX.1 Schnell.
    Model: @cf/black-forest-labs/flux-1-schnell
    """

    def __init__(
        self,
        account_id: Optional[str] = None,
        api_token: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.account_id = (account_id or getattr(settings, "CLOUDFLARE_ACCOUNT_ID", "")).strip()
        self.api_token = (api_token or getattr(settings, "CLOUDFLARE_API_TOKEN", "")).strip()
        self.model = (model or getattr(settings, "CLOUDFLARE_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell")).strip()

    def is_configured(self) -> bool:
        return bool(self.account_id and self.api_token)

    async def generate_image(self, prompt: str, width: int = 1024, height: int = 1024) -> bytes:
        if not self.is_configured():
            raise ValueError("Cloudflare Workers AI credentials (CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN) are not configured.")

        url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/ai/run/{self.model}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "prompt": prompt,
            "num_steps": 4,  # FLUX.1 Schnell optimal fast step count
            "width": width,
            "height": height
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                error_detail = response.text[:300]
                logger.error(f"Cloudflare Workers AI error (HTTP {response.status_code}): {error_detail}")
                raise RuntimeError(f"Cloudflare Workers AI generation failed with status {response.status_code}: {error_detail}")

            image_bytes = response.content
            # Validate image format
            if not self._is_valid_image(image_bytes):
                raise ValueError("Cloudflare Workers AI response did not contain a valid image payload.")

            return image_bytes

    def _is_valid_image(self, data: bytes) -> bool:
        if len(data) < 16:
            return False
        # PNG, JPEG, or WEBP magic bytes
        if data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\xff\xd8\xff") or (data[:4] == b"RIFF" and data[8:12] == b"WEBP"):
            return True
        return False


class MockProceduralImageProvider(ImageGenerationProvider):
    """
    High-aesthetic procedural background generator using NEXORA's brand identity:
    Deep Navy (#050817), Neon Cyan (#00D5E9), Electric Blue (#2878FF), and Electric Purple (#7650F5).
    Guarantees that the branding pipeline and post generation work without external API friction.
    """

    async def generate_image(self, prompt: str, width: int = 1024, height: int = 1024) -> bytes:
        # Base background: Deep Navy (#050817)
        img = Image.new("RGB", (width, height), (5, 8, 23))
        draw = ImageDraw.Draw(img)

        # Draw subtle cybernetic grid in background
        grid_color = (15, 25, 55)
        step = 64
        for x in range(0, width, step):
            draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
        for y in range(0, height, step):
            draw.line([(0, y), (width, y)], fill=grid_color, width=1)

        # Create glowing ambient light orbs (Cyan & Purple)
        orb_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        orb_draw = ImageDraw.Draw(orb_layer)

        # Electric Blue / Neon Cyan Orb (Top-Right / Center)
        cx1, cy1, r1 = int(width * 0.7), int(height * 0.35), int(width * 0.35)
        orb_draw.ellipse([cx1 - r1, cy1 - r1, cx1 + r1, cy1 + r1], fill=(0, 213, 233, 90))

        # Electric Purple / Magenta Orb (Bottom-Left / Center)
        cx2, cy2, r2 = int(width * 0.3), int(height * 0.65), int(width * 0.4)
        orb_draw.ellipse([cx2 - r2, cy2 - r2, cx2 + r2, cy2 + r2], fill=(118, 80, 245, 85))

        # Core Glow (Electric Blue)
        cx3, cy3, r3 = int(width * 0.5), int(height * 0.5), int(width * 0.25)
        orb_draw.ellipse([cx3 - r3, cy3 - r3, cx3 + r3, cy3 + r3], fill=(40, 120, 255, 110))

        # Heavy Gaussian Blur to create smooth luxury atmospheric lighting
        orb_layer = orb_layer.filter(ImageFilter.GaussianBlur(radius=70))

        # Composite orbs onto base image
        img_rgba = img.convert("RGBA")
        img_rgba = Image.alpha_composite(img_rgba, orb_layer)

        # Draw futuristic holographic 3D message cards & tech nodes in center
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)

        # Card 1 (Holographic Glass message bubble)
        card1_box = [int(width * 0.2), int(height * 0.36), int(width * 0.8), int(height * 0.48)]
        overlay_draw.rounded_rectangle(card1_box, radius=24, fill=(10, 20, 45, 180), outline=(0, 213, 233, 140), width=2)
        # Inner glow line
        overlay_draw.line([(card1_box[0] + 30, card1_box[1] + 30), (card1_box[2] - 120, card1_box[1] + 30)], fill=(0, 213, 233, 200), width=6)
        overlay_draw.line([(card1_box[0] + 30, card1_box[1] + 50), (card1_box[2] - 240, card1_box[1] + 50)], fill=(40, 120, 255, 150), width=4)

        # Card 2 (Lower floating smart reply pill)
        card2_box = [int(width * 0.25), int(height * 0.52), int(width * 0.75), int(height * 0.62)]
        overlay_draw.rounded_rectangle(card2_box, radius=20, fill=(15, 18, 50, 200), outline=(118, 80, 245, 160), width=2)
        overlay_draw.line([(card2_box[0] + 30, card2_box[1] + 25), (card2_box[2] - 160, card2_box[1] + 25)], fill=(118, 80, 245, 220), width=5)

        # Final composite
        final_img = Image.alpha_composite(img_rgba, overlay)
        final_rgb = final_img.convert("RGB")

        output = io.BytesIO()
        final_rgb.save(output, format="PNG")
        return output.getvalue()


def get_image_provider(
    provider_name: str = "cloudflare",
    account_id: Optional[str] = None,
    api_token: Optional[str] = None,
    model: Optional[str] = None
) -> ImageGenerationProvider:
    """Provider factory respecting configuration and fallbacks."""
    name = (provider_name or "cloudflare").lower().strip()
    if name == "cloudflare":
        cf_provider = CloudflareWorkersAIProvider(account_id=account_id, api_token=api_token, model=model)
        if cf_provider.is_configured():
            return cf_provider
        logger.info("Cloudflare credentials not provided; using procedural NEXORA brand image generator.")
        return MockProceduralImageProvider()
    return MockProceduralImageProvider()

