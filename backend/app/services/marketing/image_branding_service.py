import os
import io
import logging
from typing import Tuple, List, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import arabic_reshaper
from bidi.algorithm import get_display

logger = logging.getLogger("marketing.branding")

# Base directory for uploads
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
MARKETING_UPLOADS_DIR = os.path.join(PROJECT_ROOT, "uploads", "marketing")
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "assets")
BRAND_LOGO_PATH = os.path.join(ASSETS_DIR, "brand", "nexora_logo.png")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")


class ImageBrandingService:
    """
    Applies NEXORA's official brand identity to generated images.
    - Preserves official logo without redrawing.
    - Programmatically renders Arabic typography with proper shaping & bidi.
    - Applies dark navy, cyan, and purple SaaS ambient lighting & glassmorphic cards.
    """

    def __init__(self):
        os.makedirs(MARKETING_UPLOADS_DIR, exist_ok=True)
        self.font_bold_path = self._find_font()

    def _find_font(self) -> str:
        candidates = [
            os.path.join(FONTS_DIR, "segoeuib.ttf"),
            os.path.join(FONTS_DIR, "tahomabd.ttf"),
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/tahomabd.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return ""

    def process_and_brand_image(
        self,
        raw_image_bytes: bytes,
        headline: str,
        post_id: int,
        post_date: str,
        target_width: int = 1080,
        target_height: int = 1350
    ) -> Tuple[str, str]:
        """
        Takes raw image bytes, saves raw image, applies NEXORA branding,
        and saves final branded image.
        Returns: (branded_relative_path, raw_relative_path)
        """
        # Save raw image first
        raw_filename = f"raw_{post_date}_{post_id}.png"
        raw_filepath = os.path.join(MARKETING_UPLOADS_DIR, raw_filename)
        with open(raw_filepath, "wb") as f:
            f.write(raw_image_bytes)

        # Open and resize raw image to target dimensions
        raw_img = Image.open(io.BytesIO(raw_image_bytes)).convert("RGBA")
        base_img = self._resize_and_crop(raw_img, target_width, target_height)

        # Apply dark navy gradient overlay at top and bottom for readability & luxury tech feel
        graded_img = self._apply_ambient_vignette(base_img, target_width, target_height)

        # Overlay official NEXORA logo at top
        branded_img = self._overlay_logo(graded_img, target_width, target_height)

        # Render Arabic headline inside sleek glassmorphic container
        final_img = self._render_arabic_headline_and_badge(branded_img, headline, target_width, target_height)

        # Convert to RGB and save final branded image
        final_rgb = final_img.convert("RGB")
        final_filename = f"nexora_marketing_{post_date}_{post_id}.png"
        final_filepath = os.path.join(MARKETING_UPLOADS_DIR, final_filename)
        final_rgb.save(final_filepath, "PNG", optimize=True)

        logger.info(f"Successfully branded and saved marketing post {post_id} at {final_filepath}")
        return f"/uploads/marketing/{final_filename}", f"/uploads/marketing/{raw_filename}"

    def _resize_and_crop(self, img: Image.Image, target_w: int, target_h: int) -> Image.Image:
        orig_w, orig_h = img.size
        target_ratio = target_w / target_h
        orig_ratio = orig_w / orig_h

        if orig_ratio > target_ratio:
            # Crop width
            new_w = int(orig_h * target_ratio)
            left = (orig_w - new_w) // 2
            img = img.crop((left, 0, left + new_w, orig_h))
        else:
            # Crop height
            new_h = int(orig_w / target_ratio)
            top = (orig_h - new_h) // 2
            img = img.crop((0, top, orig_w, top + new_h))

        return img.resize((target_w, target_h), Image.Resampling.LANCZOS)

    def _apply_ambient_vignette(self, img: Image.Image, w: int, h: int) -> Image.Image:
        """Applies smooth Deep Navy (#050817) top and bottom overlays."""
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Top gradient: darker at very top (for logo)
        top_h = int(h * 0.28)
        for y in range(top_h):
            ratio = 1.0 - (y / top_h)
            alpha = int(220 * (ratio ** 1.5))
            draw.line([(0, y), (w, y)], fill=(5, 8, 23, alpha))

        # Bottom gradient: deep navy for headline and brand footer
        bottom_h = int(h * 0.45)
        bottom_start = h - bottom_h
        for y in range(bottom_start, h):
            ratio = (y - bottom_start) / bottom_h
            alpha = int(240 * (ratio ** 1.3))
            draw.line([(0, y), (w, y)], fill=(5, 8, 23, alpha))

        # Subtle cyan/purple ambient border lines at bottom
        draw.line([(int(w * 0.1), h - 140), (int(w * 0.9), h - 140)], fill=(0, 213, 233, 100), width=1)

        return Image.alpha_composite(img, overlay)

    def _overlay_logo(self, img: Image.Image, w: int, h: int) -> Image.Image:
        """Loads and places the official NEXORA logo without modifying proportions or transparency."""
        if not os.path.exists(BRAND_LOGO_PATH):
            logger.warning(f"Logo not found at {BRAND_LOGO_PATH}; creating clean header badge")
            return img

        try:
            logo = Image.open(BRAND_LOGO_PATH).convert("RGBA")
            # Target logo height: around 110px
            target_logo_h = 100
            orig_lw, orig_lh = logo.size
            target_logo_w = int(orig_lw * (target_logo_h / orig_lh))
            logo_resized = logo.resize((target_logo_w, target_logo_h), Image.Resampling.LANCZOS)

            # Center logo at top
            pos_x = (w - target_logo_w) // 2
            pos_y = 55

            img.paste(logo_resized, (pos_x, pos_y), logo_resized)
        except Exception as e:
            logger.error(f"Failed to overlay brand logo: {e}")

        return img

    def _render_arabic_headline_and_badge(
        self,
        img: Image.Image,
        headline: str,
        w: int,
        h: int
    ) -> Image.Image:
        """Renders properly shaped Arabic headline and call-to-action badge."""
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # 1. Headline Typography
        font_size = 48
        font = None
        if self.font_bold_path:
            try:
                font = ImageFont.truetype(self.font_bold_path, font_size)
            except Exception:
                font = ImageFont.load_default()
        else:
            font = ImageFont.load_default()

        # Word wrap headline to fit nicely in 2 lines
        lines = self._wrap_arabic_text(headline, font, max_width=int(w * 0.82))

        # Calculate bounding box and draw glassmorphic card behind headline
        line_height = int(font_size * 1.5)
        total_text_h = len(lines) * line_height
        card_pad_x = 45
        card_pad_y = 35
        card_y = h - 260 - total_text_h
        card_w = int(w * 0.88)
        card_x = (w - card_w) // 2

        # Draw glassmorphic container: Deep Navy with Cyan & Purple borders
        draw.rounded_rectangle(
            [card_x, card_y, card_x + card_w, card_y + total_text_h + card_pad_y * 2],
            radius=26,
            fill=(5, 8, 23, 205),
            outline=(0, 213, 233, 160),
            width=2
        )

        # Top cyan accent glow on the card
        draw.line(
            [(card_x + 50, card_y), (card_x + card_w - 50, card_y)],
            fill=(0, 213, 233, 240),
            width=4
        )

        # Draw each line of Arabic text centered
        text_start_y = card_y + card_pad_y
        for i, line in enumerate(lines):
            reshaped_line = arabic_reshaper.reshape(line)
            bidi_line = get_display(reshaped_line)

            # Get text bounding box for exact horizontal centering
            bbox = font.getbbox(bidi_line)
            text_w = bbox[2] - bbox[0]
            pos_x = (w - text_w) // 2
            pos_y = text_start_y + (i * line_height)

            # Draw text shadow for extreme contrast
            draw.text((pos_x + 2, pos_y + 2), bidi_line, font=font, fill=(0, 0, 0, 220))
            # Main crisp white text
            draw.text((pos_x, pos_y), bidi_line, font=font, fill=(255, 255, 255, 255))

        # 2. Bottom Call-To-Action Pill Badge
        # "ردود ذكية. مبيعات أسرع."
        sub_font_size = 26
        sub_font = None
        if self.font_bold_path:
            try:
                sub_font = ImageFont.truetype(self.font_bold_path, sub_font_size)
            except Exception:
                sub_font = font
        else:
            sub_font = font

        badge_text_ar = "ردود ذكية • مبيعات أسرع • على مدار الساعة"
        reshaped_badge = arabic_reshaper.reshape(badge_text_ar)
        bidi_badge = get_display(reshaped_badge)

        badge_bbox = sub_font.getbbox(bidi_badge)
        badge_text_w = badge_bbox[2] - badge_bbox[0]
        badge_w = badge_text_w + 60
        badge_h = 56
        badge_x = (w - badge_w) // 2
        badge_y = h - 100

        # Draw glowing pill
        draw.rounded_rectangle(
            [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
            radius=28,
            fill=(40, 120, 255, 220),
            outline=(0, 213, 233, 240),
            width=2
        )

        # Draw pill text
        badge_pos_x = (w - badge_text_w) // 2
        badge_pos_y = badge_y + 11
        draw.text((badge_pos_x, badge_pos_y), bidi_badge, font=sub_font, fill=(255, 255, 255, 255))

        return Image.alpha_composite(img, overlay)

    def _wrap_arabic_text(self, text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
        words = text.split()
        if not words:
            return [""]

        lines = []
        current_line = []

        for word in words:
            test_line = " ".join(current_line + [word])
            reshaped_test = arabic_reshaper.reshape(test_line)
            bidi_test = get_display(reshaped_test)
            bbox = font.getbbox(bidi_test)
            test_w = bbox[2] - bbox[0]

            if test_w <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)
                    current_line = []

        if current_line:
            lines.append(" ".join(current_line))

        return lines[:3]  # Max 3 lines

