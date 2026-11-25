import logging
import time
from typing import Optional

from backend.app.core.config import settings
from backend.app.services.tts.base import BaseTTSProvider, TTSResult

logger = logging.getLogger(__name__)


class EdgeTTSProvider(BaseTTSProvider):
    """
    Fallback Text-to-Speech provider using Microsoft edge-tts.
    Supports Egyptian Arabic neural voices ('ar-EG-SalmaNeural', 'ar-EG-ShakirNeural').
    Guarantees fast, robust speech playback when external cloud spaces are unavailable.
    """

    def __init__(self):
        self.primary_voice = settings.EDGE_TTS_VOICE_PRIMARY or "ar-EG-SalmaNeural"
        self.secondary_voice = settings.EDGE_TTS_VOICE_SECONDARY or "ar-EG-ShakirNeural"
        self.default_rate = "+15%"

    @property
    def provider_name(self) -> str:
        return "edge-tts"

    def is_available(self) -> bool:
        try:
            import edge_tts
            return True
        except ImportError:
            return False

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
    ) -> Optional[TTSResult]:
        if not self.is_available():
            logger.error("[EdgeTTS] edge-tts package is not installed.")
            return None

        clean_text = text.strip()
        if not clean_text:
            return None

        import edge_tts

        effective_rate = rate or self.default_rate

        # Determine voice candidate sequence
        candidate_voice = voice if (voice and "Neural" in voice) else self.primary_voice
        voices_to_try = [candidate_voice]
        fallback_v = self.secondary_voice if candidate_voice == self.primary_voice else self.primary_voice
        if fallback_v not in voices_to_try:
            voices_to_try.append(fallback_v)

        start_t = time.perf_counter()

        for v in voices_to_try:
            try:
                communicate = edge_tts.Communicate(clean_text, v, rate=effective_rate)
                chunks = []
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        chunks.append(chunk["data"])

                if chunks:
                    audio_bytes = b"".join(chunks)
                    if len(audio_bytes) > 200:  # Valid audio payload
                        duration_ms = (time.perf_counter() - start_t) * 1000.0
                        logger.info(
                            f"[EdgeTTS] Synthesis succeeded with voice='{v}' in {round(duration_ms, 1)}ms | "
                            f"Audio: {len(audio_bytes)} bytes"
                        )
                        return TTSResult(
                            audio_bytes=audio_bytes,
                            media_type="audio/mpeg",
                            provider="edge-tts",
                            voice=v,
                            duration_ms=duration_ms,
                            is_fallback=True,  # Usually invoked as fallback
                            metadata={"rate": effective_rate}
                        )
            except Exception as e:
                logger.warning(f"[EdgeTTS] Synthesis attempt with voice '{v}' failed: {e}")

        duration_ms = (time.perf_counter() - start_t) * 1000.0
        logger.error(f"[EdgeTTS] All voice candidates failed after {round(duration_ms, 1)}ms.")
        return None

