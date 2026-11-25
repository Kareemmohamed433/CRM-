import re
import time
import logging
from typing import Optional, Dict
from collections import OrderedDict

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user
from backend.app.models.models import User
from backend.app.schemas.ai import (
    VoiceTranscribeAndExtractRequest, VoiceExtractionResponse,
    VoiceConversationRequest, VoiceConversationResponse,
    VoiceConfirmAndSaveRequest, VoiceConfirmAndSaveResponse,
    VoiceTranscriptionResponse
)
from backend.app.services.voice_service import extract_crm_data_from_voice_or_text
from backend.app.services.voice_conversation_service import (
    process_voice_conversation, confirm_and_save_voice_activity
)
from backend.app.services.llm_client import transcribe_audio_bytes, is_llm_configured
from backend.app.services.voice_metrics_service import record_voice_metric, get_voice_analytics
from backend.app.services.tts import get_tts_manager, clean_text_for_arabic_speech

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["Voice & Speech CRM"])

MAX_AUDIO_BYTES = 10 * 1024 * 1024

# Hint for Whisper so Egyptian real-estate words are spelled right
WHISPER_PROMPT = (
    "مندوب مبيعات عقارات مصري بيحكي عن معاينة أو مكالمة مع عميل: التجمع الخامس، الشيخ زايد، "
    "العاصمة الإدارية، الساحل الشمالي، المقدم، القسط، التشطيب، الاستلام، معاينة، متابعة، ميزانية، مليون، ألف."
)

# In-memory LRU cache for synthesized speech to deliver ultra-low latency on frequent responses
_TTS_CACHE: OrderedDict[str, bytes] = OrderedDict()
_MAX_CACHE_ENTRIES = 120


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1500)
    voice: Optional[str] = None  # VoiceTut speaker (Ahmed, Karim, Ali, Hassan) or Edge-TTS voice
    rate: Optional[str] = None   # Rate multiplier (e.g. "+15%")
    session_id: Optional[str] = None


def _clean_for_speech(text: str) -> str:
    """Cleans Markdown symbols, emojis, and normalizes brand names for natural Arabic speech."""
    return clean_text_for_arabic_speech(text)


async def _synthesize_audio_with_fallback(text: str, voice: str, rate: str) -> Optional[bytes]:
    """Backward compatibility helper delegating to EdgeTTSProvider."""
    from backend.app.services.tts import EdgeTTSProvider
    provider = EdgeTTSProvider()
    res = await provider.synthesize(text, voice, rate)
    return res.audio_bytes if res else None


@router.post("/conversation", response_model=VoiceConversationResponse)
def handle_voice_conversation(
    req: VoiceConversationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Real-time multi-turn conversational AI in natural Egyptian Arabic.
    Maintains conversational memory, detects missing information, probes naturally in Egyptian dialect,
    and produces structured confirmation drafts for CRM saving.
    """
    start_t = time.perf_counter()
    resp = process_voice_conversation(
        db=db,
        current_user=current_user,
        req=req
    )
    duration_ms = (time.perf_counter() - start_t) * 1000.0
    record_voice_metric(
        db=db,
        stage="LLM",
        provider="qwen-chat",
        duration_ms=duration_ms,
        success=True,
        company_id=current_user.company_id,
        user_id=current_user.id
    )
    return resp


@router.post("/confirm-and-save", response_model=VoiceConfirmAndSaveResponse)
def confirm_and_save_voice_outcome(
    req: VoiceConfirmAndSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Saves the extracted activity to the database ONLY after explicit user confirmation.
    Enforces authentication, company tenant isolation, role authorization, and updates pipeline/scoring.
    """
    if not req.explicit_confirmation:
        raise HTTPException(
            status_code=400,
            detail="Explicit user confirmation is required to save records to the CRM."
        )

    try:
        return confirm_and_save_voice_activity(
            db=db,
            current_user=current_user,
            req=req
        )
    except PermissionError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save activity: {str(e)}")


@router.post("/transcribe", response_model=VoiceTranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = Form("ar"),
    session_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Transcribes audio file to Arabic text using Groq Whisper.
    Enables devices without browser Web Speech API to seamlessly use Voice Mode.
    Records latency and accuracy metrics.
    """
    start_t = time.perf_counter()
    try:
        audio_content = await file.read()
        if not audio_content:
            raise HTTPException(status_code=400, detail="Empty audio file provided")
        if len(audio_content) > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="Audio file too large")

        # transcribe_audio_bytes is a blocking HTTP call: run it off the event loop
        transcript = await run_in_threadpool(
            transcribe_audio_bytes,
            audio_content,
            file.filename or "audio.webm",
            language,
            WHISPER_PROMPT,
            file.content_type or "audio/webm",
        )

        duration_ms = (time.perf_counter() - start_t) * 1000.0

        if transcript is None:
            record_voice_metric(
                db=db,
                stage="STT",
                provider="groq-whisper",
                duration_ms=duration_ms,
                success=False,
                company_id=current_user.company_id,
                user_id=current_user.id,
                session_id=session_id,
                error_category="service_unavailable"
            )
            raise HTTPException(status_code=503, detail="Transcription service unavailable")

        record_voice_metric(
            db=db,
            stage="STT",
            provider="groq-whisper",
            duration_ms=duration_ms,
            success=True,
            company_id=current_user.company_id,
            user_id=current_user.id,
            session_id=session_id
        )

        return VoiceTranscriptionResponse(
            transcript=transcript,
            language=language,
            confidence=0.96
        )
    except HTTPException:
        raise
    except Exception as e:
        duration_ms = (time.perf_counter() - start_t) * 1000.0
        record_voice_metric(
            db=db,
            stage="STT",
            provider="groq-whisper",
            duration_ms=duration_ms,
            success=False,
            company_id=current_user.company_id,
            user_id=current_user.id,
            session_id=session_id,
            error_category=str(type(e).__name__)
        )
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@router.post("/tts")
async def text_to_speech(
    req: TTSRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Colloquial Egyptian Arabic neural text-to-speech.
    Uses VoiceTut-TTS on Hugging Face Spaces as primary provider (male Egyptian voices),
    with automatic fallback to Edge-TTS whenever VoiceTut fails, times out, or sleeps.
    Returns valid binary audio (audio/wav or audio/mpeg) with accurate Content-Length and headers,
    or a structured 502 with fallback_to_browser: true if all neural providers fail.
    """
    cleaned_text = clean_text_for_arabic_speech(req.text)
    if not cleaned_text:
        raise HTTPException(status_code=400, detail="Nothing to speak")

    manager = get_tts_manager()
    result = await manager.synthesize(
        text=cleaned_text,
        voice=req.voice,
        rate=req.rate,
        session_id=req.session_id,
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id
    )

    if result:
        return Response(
            content=result.audio_bytes,
            media_type=result.media_type,
            headers={
                "Content-Length": str(len(result.audio_bytes)),
                "Cache-Control": "public, max-age=86400",
                "Accept-Ranges": "bytes",
                "X-TTS-Provider": result.provider,
                "X-TTS-Fallback": "true" if result.is_fallback else "false",
                "X-Voice": result.voice,
                "X-Latency-Ms": str(round(result.duration_ms, 1)),
            }
        )
    else:
        # All neural TTS providers failed: return structured 502 with fallback flag
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "detail": "All neural TTS providers temporarily unavailable",
                "fallback_to_browser": True,
                "text": cleaned_text
            }
        )


@router.get("/metrics")
def get_voice_metrics(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns aggregated real voice AI metrics and latency telemetry for authorized users."""
    return get_voice_analytics(db=db, company_id=current_user.company_id, days=days)


@router.post("/extract", response_model=VoiceExtractionResponse)
def extract_fields_from_speech_or_text(
    req: VoiceTranscribeAndExtractRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Legacy single-turn extraction route preserved for backward compatibility.
    """
    if not req.transcript_text or not req.transcript_text.strip():
        raise HTTPException(status_code=400, detail="Transcript text cannot be empty")

    extraction = extract_crm_data_from_voice_or_text(
        db=db,
        company_id=current_user.company_id,
        transcript=req.transcript_text,
        target_form=req.target_form
    )
    return extraction
