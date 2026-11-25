import logging
import re
import time
from collections import OrderedDict
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.services.tts.base import BaseTTSProvider, TTSResult
from backend.app.services.tts.voicetut_provider import VoiceTutProvider
from backend.app.services.tts.edge_provider import EdgeTTSProvider
from backend.app.services.voice_metrics_service import record_voice_metric

logger = logging.getLogger(__name__)


def clean_text_for_arabic_speech(text: str) -> str:
    """
    Cleans markdown formatting, emojis, internal codes, and normalizes real-estate terminology
    for clear, natural colloquial Egyptian Arabic speech.
    """
    if not text:
        return ""
    # Remove markdown syntax
    t = re.sub(r"[*#_`•>~]+", "", text)
    # Remove emojis and symbols
    t = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", "", t)
    # Real estate & brand terminology pronunciation
    t = t.replace("CRM", "سي آر إم")
    t = t.replace("Nexora", "نيكسورا")
    t = re.sub(r"\bEGP\b", "جنيه", t, flags=re.IGNORECASE)
    t = re.sub(r"\bUSD\b", "دولار", t, flags=re.IGNORECASE)
    t = re.sub(r"\bm2\b", "متر مربع", t, flags=re.IGNORECASE)
    # Remove JSON / code artifacts if any leaked
    t = re.sub(r"\{.*?\}", "", t)
    # Collapse excess whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


class TTSManager:
    """
    Central Text-to-Speech coordinator.
    Directs speech synthesis requests to the primary provider (VoiceTut-TTS on Hugging Face Spaces),
    and instantly triggers the automatic fallback provider (Edge-TTS) whenever VoiceTut fails,
    times out, exhausts ZeroGPU quota, or is sleeping.
    """

    def __init__(self):
        self.voicetut = VoiceTutProvider()
        self.edge_tts = EdgeTTSProvider()
        self._cache: OrderedDict[str, TTSResult] = OrderedDict()
        self._max_cache_size = 150

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        session_id: Optional[str] = None,
        db: Optional[Session] = None,
        company_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> Optional[TTSResult]:
        cleaned = clean_text_for_arabic_speech(text)
        if not cleaned:
            logger.warning("[TTSManager] Empty text provided for synthesis.")
            return None

        # Check LRU cache for ultra-fast response
        cache_key = f"{voice or 'auto'}:{rate or 'default'}:{cleaned}"
        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            hit = self._cache[cache_key]
            logger.debug(f"[TTSManager] LRU cache HIT for key '{cache_key[:30]}...'")
            return hit

        primary_provider = settings.TTS_PRIMARY_PROVIDER.lower().strip()
        result: Optional[TTSResult] = None

        if primary_provider == "voicetut" and self.voicetut.is_available():
            # 1. Attempt Primary: VoiceTut-TTS
            logger.info(f"[TTSManager] Attempting primary TTS provider: VoiceTut-TTS...")
            result = await self.voicetut.synthesize(cleaned, voice=voice, rate=rate)

            if result is not None:
                # Primary succeeded
                logger.info(f"[TTSManager] Primary provider VoiceTut succeeded in {round(result.duration_ms, 1)}ms.")
                if db and company_id and user_id:
                    record_voice_metric(
                        db=db,
                        stage="TTS",
                        provider="voicetut",
                        duration_ms=result.duration_ms,
                        success=True,
                        company_id=company_id,
                        user_id=user_id,
                        session_id=session_id
                    )
            else:
                # Primary failed: trigger automatic fallback immediately
                logger.warning("[TTSManager] Primary provider VoiceTut failed or timed out. Activating automatic fallback to Edge-TTS...")
                if db and company_id and user_id:
                    record_voice_metric(
                        db=db,
                        stage="TTS",
                        provider="voicetut",
                        duration_ms=0.0,
                        success=False,
                        company_id=company_id,
                        user_id=user_id,
                        session_id=session_id,
                        error_category="voicetut_failed"
                    )

                result = await self.edge_tts.synthesize(cleaned, voice=voice, rate=rate)
                if result is not None:
                    result.is_fallback = True
                    logger.info(f"[TTSManager] Automatic fallback to Edge-TTS SUCCEEDED in {round(result.duration_ms, 1)}ms.")
                    if db and company_id and user_id:
                        record_voice_metric(
                            db=db,
                            stage="TTS",
                            provider="edge-tts",
                            duration_ms=result.duration_ms,
                            success=True,
                            company_id=company_id,
                            user_id=user_id,
                            session_id=session_id
                        )
                else:
                    logger.error("[TTSManager] BOTH VoiceTut and fallback Edge-TTS providers failed.")
                    if db and company_id and user_id:
                        record_voice_metric(
                            db=db,
                            stage="TTS",
                            provider="edge-tts",
                            duration_ms=0.0,
                            success=False,
                            company_id=company_id,
                            user_id=user_id,
                            session_id=session_id,
                            error_category="all_tts_failed"
                        )
        else:
            # Direct Edge-TTS configured as primary
            logger.info("[TTSManager] Direct Edge-TTS provider selected as primary.")
            result = await self.edge_tts.synthesize(cleaned, voice=voice, rate=rate)
            if result:
                result.is_fallback = False
                if db and company_id and user_id:
                    record_voice_metric(
                        db=db,
                        stage="TTS",
                        provider="edge-tts",
                        duration_ms=result.duration_ms,
                        success=True,
                        company_id=company_id,
                        user_id=user_id,
                        session_id=session_id
                    )

        # Store in LRU cache on success
        if result is not None:
            self._cache[cache_key] = result
            if len(self._cache) > self._max_cache_size:
                self._cache.popitem(last=False)

        return result


# Singleton manager instance
_manager: Optional[TTSManager] = None


def get_tts_manager() -> TTSManager:
    """Returns singleton TTSManager instance."""
    global _manager
    if _manager is None:
        _manager = TTSManager()
    return _manager

