import asyncio
import logging
import os
import time
from typing import Optional, Dict, Any, List

from backend.app.core.config import settings
from backend.app.services.tts.base import BaseTTSProvider, TTSResult

logger = logging.getLogger(__name__)

# Valid male & female Egyptian Arabic speakers supported by VoiceTut-TTS Space
VOICETUT_MALE_SPEAKERS = {
    "Ahmed", "Ali", "Karim", "Hassan", "Mahmoud",
    "Mohammed", "Mostafa", "Omar", "Tarek", "Youssef"
}
VOICETUT_ALL_SPEAKERS = VOICETUT_MALE_SPEAKERS | {"Salma", "Yasmin", "Mariam", "Nour"}


def _sanitize_space_url(raw_url: str) -> str:
    """Normalizes HuggingFace Space URLs to repo_id or direct endpoint for gradio_client."""
    u = raw_url.strip()
    if u.startswith("https://huggingface.co/spaces/"):
        return u.replace("https://huggingface.co/spaces/", "").strip("/")
    if u.startswith("http://huggingface.co/spaces/"):
        return u.replace("http://huggingface.co/spaces/", "").strip("/")
    return u


def _mask_secret(text: str) -> str:
    """Ensures HF tokens or sensitive keys are never exposed in log outputs."""
    token = settings.HF_TOKEN
    if token and token in text:
        return text.replace(token, "[REDACTED_HF_TOKEN]")
    return text


class VoiceTutProvider(BaseTTSProvider):
    """
    Primary Text-to-Speech provider using the official VoiceTut-TTS model
    hosted on Hugging Face Spaces (mohammedaly22/VoiceTut-TTS).
    Produces authentic colloquial Egyptian Arabic speech with male voices.
    """

    def __init__(self):
        self.space_url = _sanitize_space_url(settings.VOICETUT_SPACE_URL)
        self.default_voice = settings.VOICETUT_VOICE or "Ahmed"
        self.timeout = float(settings.VOICETUT_TIMEOUT or 12.0)
        self._client = None
        self._client_lock = asyncio.Lock()

    @property
    def provider_name(self) -> str:
        return "voicetut"

    def is_available(self) -> bool:
        """VoiceTut is enabled when TTS_PRIMARY_PROVIDER is voicetut and space URL is set."""
        return bool(self.space_url and settings.TTS_PRIMARY_PROVIDER == "voicetut")

    def _get_or_init_client(self):
        """Initializes gradio_client.Client with token authentication if configured."""
        if self._client is not None:
            return self._client

        from gradio_client import Client

        token = settings.HF_TOKEN if settings.HF_TOKEN else None
        logger.info(f"Connecting to VoiceTut-TTS Space '{self.space_url}' (auth: {'token' if token else 'anonymous'})...")
        self._client = Client(self.space_url, token=token)
        return self._client

    def resolve_speaker(self, voice: Optional[str]) -> str:
        """Maps requested voice to a valid VoiceTut Egyptian speaker, defaulting to Ahmed."""
        if voice and voice in VOICETUT_ALL_SPEAKERS:
            return voice
        # If user/agent specifies a preferred male Egyptian voice
        if self.default_voice in VOICETUT_ALL_SPEAKERS:
            return self.default_voice
        return "Ahmed"

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
    ) -> Optional[TTSResult]:
        if not self.is_available():
            logger.debug("VoiceTut provider is disabled or not configured.")
            return None

        clean_text = text.strip()
        if not clean_text:
            return None

        speaker = self.resolve_speaker(voice)
        start_t = time.perf_counter()
        logger.info(f"[VoiceTut] Starting synthesis request for speaker='{speaker}' (text length={len(clean_text)} chars)")

        try:
            # Connect/acquire client safely in threadpool
            client = await asyncio.to_thread(self._get_or_init_client)

            # Define prediction task with exact parameter schema from VoiceTut-TTS Space
            def _predict():
                return client.predict(
                    text=clean_text,
                    language="arz",         # Egyptian Arabic language code
                    voice_mode="speaker",    # Preset speaker mode
                    speaker=speaker,
                    ref_audio=None,
                    ref_text="",
                    num_step=float(settings.VOICETUT_NUM_STEPS or 16),
                    guidance=float(settings.VOICETUT_GUIDANCE or 2.0),
                    speed=float(settings.VOICETUT_SPEED or 1.0),
                    normalize=bool(settings.VOICETUT_NORMALIZE),
                    api_name="/synthesize"
                )

            # Enforce bounded timeout to guarantee low conversation latency
            result = await asyncio.wait_for(
                asyncio.to_thread(_predict),
                timeout=self.timeout
            )

            duration_ms = (time.perf_counter() - start_t) * 1000.0

            # Validate prediction result: expected (wav_filepath, metrics_dict)
            if not result or not isinstance(result, (tuple, list)) or len(result) < 1:
                logger.warning(f"[VoiceTut] Invalid or empty response structure from Space: {result}")
                return None

            wav_path = result[0]
            if isinstance(wav_path, dict) and "path" in wav_path:
                wav_path = wav_path["path"]

            if not wav_path or not isinstance(wav_path, str) or not os.path.exists(wav_path):
                logger.warning(f"[VoiceTut] Generated audio file does not exist at path: '{wav_path}'")
                return None

            file_size = os.path.getsize(wav_path)
            if file_size < 500:
                logger.warning(f"[VoiceTut] Generated audio file is corrupt or too small: {file_size} bytes")
                return None

            # Read audio bytes into memory and clean up temporary file
            wav_bytes: bytes
            try:
                with open(wav_path, "rb") as f:
                    wav_bytes = f.read()
            finally:
                try:
                    if os.path.exists(wav_path):
                        os.remove(wav_path)
                except Exception as cleanup_err:
                    logger.debug(f"[VoiceTut] Notice cleaning temp audio file: {cleanup_err}")

            metrics = result[1] if len(result) > 1 and isinstance(result[1], dict) else {}
            logger.info(
                f"[VoiceTut] Synthesis succeeded in {round(duration_ms, 1)}ms | "
                f"Audio: {len(wav_bytes)} bytes | Speaker: {speaker}"
            )

            return TTSResult(
                audio_bytes=wav_bytes,
                media_type="audio/wav",
                provider="voicetut",
                voice=speaker,
                duration_ms=duration_ms,
                is_fallback=False,
                metadata=metrics
            )

        except asyncio.TimeoutError:
            duration_ms = (time.perf_counter() - start_t) * 1000.0
            logger.warning(f"[VoiceTut] Request timed out after {self.timeout}s (elapsed {round(duration_ms, 1)}ms). Triggering fallback.")
            return None

        except Exception as e:
            duration_ms = (time.perf_counter() - start_t) * 1000.0
            err_msg = _mask_secret(str(e))
            lower_err = err_msg.lower()

            if "quota" in lower_err or "exceeded" in lower_err:
                logger.warning(f"[VoiceTut] ZeroGPU quota exhausted or rate-limited ({round(duration_ms, 1)}ms): {err_msg}")
            elif "sleep" in lower_err or "starting" in lower_err or "unavailable" in lower_err or "503" in lower_err:
                logger.warning(f"[VoiceTut] Space is sleeping, starting, or unavailable ({round(duration_ms, 1)}ms): {err_msg}")
            elif "auth" in lower_err or "401" in lower_err or "403" in lower_err:
                logger.warning(f"[VoiceTut] Authentication or authorization error: {err_msg}")
            else:
                logger.warning(f"[VoiceTut] Synthesis failed ({round(duration_ms, 1)}ms): {err_msg}")

            # Reset client instance on connection errors so next turn re-establishes cleanly
            self._client = None
            return None

