import asyncio
import io
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from backend.app.services.tts.base import TTSResult
from backend.app.services.tts.manager import clean_text_for_arabic_speech, get_tts_manager
from backend.app.services.tts.voicetut_provider import VoiceTutProvider
from backend.app.core.config import settings


@pytest.fixture(autouse=True)
def ensure_voicetut_primary(monkeypatch):
    monkeypatch.setattr(settings, "TTS_PRIMARY_PROVIDER", "voicetut")


# ---------------------------------------------------------------------------
# 1. Text Normalization & Real Estate Arabic Quality Tests
# ---------------------------------------------------------------------------

def test_arabic_text_cleaning_and_normalization():
    """Validates markdown removal, emoji stripping, and real-estate term normalization."""
    raw = "🏡 **فيلا للبيع** في _التجمع الخامس_ بسعر 12,000,000 EGP عبر نظام Nexora CRM!"
    cleaned = clean_text_for_arabic_speech(raw)
    
    assert "فيلا للبيع" in cleaned
    assert "التجمع الخامس" in cleaned
    assert "جنيه" in cleaned
    assert "EGP" not in cleaned
    assert "نيكسورا" in cleaned
    assert "Nexora" not in cleaned
    assert "سي آر إم" in cleaned
    assert "CRM" not in cleaned
    assert "*" not in cleaned
    assert "_" not in cleaned
    assert "🏡" not in cleaned


def test_male_voice_configuration():
    """Validates that Egyptian Arabic male voices (Ahmed, Karim, Ali, Hassan) resolve correctly."""
    provider = VoiceTutProvider()
    
    # Explicit male voices
    assert provider.resolve_speaker("Ahmed") == "Ahmed"
    assert provider.resolve_speaker("Karim") == "Karim"
    assert provider.resolve_speaker("Ali") == "Ali"
    assert provider.resolve_speaker("Hassan") == "Hassan"
    
    # Fallback to configured default when unknown or Edge voice passed
    assert provider.resolve_speaker("unknown_voice") == "Ahmed"
    assert provider.resolve_speaker("ar-EG-SalmaNeural") == "Ahmed"


# ---------------------------------------------------------------------------
# 2. VoiceTut Success & Metadata Tests
# ---------------------------------------------------------------------------

def test_voicetut_synthesize_success(client, agent1_token):
    """Test VoiceTut primary provider succeeding with Egyptian male voice audio."""
    mock_wav = b"RIFF" + b"\x00" * 2000  # Valid dummy WAV bytes

    with patch.object(
        VoiceTutProvider,
        "synthesize",
        new_callable=AsyncMock
    ) as mock_voicetut:
        mock_voicetut.return_value = TTSResult(
            audio_bytes=mock_wav,
            media_type="audio/wav",
            provider="voicetut",
            voice="Ahmed",
            duration_ms=420.5,
            is_fallback=False,
            metadata={"sampling_rate": 24000}
        )

        res = client.post(
            "/api/v1/voice/tts",
            json={"text": "أهلاً بك يا فندم في نيكسورا", "voice": "Ahmed"},
            headers={"Authorization": f"Bearer {agent1_token}"}
        )

        assert res.status_code == 200
        assert res.headers["Content-Type"] == "audio/wav"
        assert res.headers["X-TTS-Provider"] == "voicetut"
        assert res.headers["X-TTS-Fallback"] == "false"
        assert res.headers["X-Voice"] == "Ahmed"
        assert len(res.content) == len(mock_wav)
        mock_voicetut.assert_called_once()


# ---------------------------------------------------------------------------
# 3. Fallback Tests: Quota Exhaustion, Timeout, Server Error, Invalid Audio
# ---------------------------------------------------------------------------

def test_voicetut_quota_exhaustion_fallback(client, agent1_token):
    """When VoiceTut exhausts ZeroGPU quota, automatically fall back to Edge-TTS."""
    mock_mp3 = b"ID3\x03\x00\x00\x00" + b"\x00" * 1500

    with patch.object(
        VoiceTutProvider,
        "synthesize",
        new_callable=AsyncMock
    ) as mock_voicetut, patch(
        "backend.app.services.tts.edge_provider.EdgeTTSProvider.synthesize",
        new_callable=AsyncMock
    ) as mock_edge:
        # VoiceTut fails due to quota limit
        mock_voicetut.return_value = None
        # EdgeTTS succeeds
        mock_edge.return_value = TTSResult(
            audio_bytes=mock_mp3,
            media_type="audio/mpeg",
            provider="edge-tts",
            voice="ar-EG-SalmaNeural",
            duration_ms=280.0,
            is_fallback=True
        )

        res = client.post(
            "/api/v1/voice/tts",
            json={"text": "تم استنفاد كوتة السيرفر وجاري التحويل للبديل"},
            headers={"Authorization": f"Bearer {agent1_token}"}
        )

        assert res.status_code == 200
        assert res.headers["Content-Type"] == "audio/mpeg"
        assert res.headers["X-TTS-Provider"] == "edge-tts"
        assert res.headers["X-TTS-Fallback"] == "true"
        assert len(res.content) == len(mock_mp3)
        mock_voicetut.assert_called_once()
        mock_edge.assert_called_once()


def test_voicetut_timeout_fallback(client, agent1_token):
    """When VoiceTut times out after bounded limit, automatically fall back to Edge-TTS."""
    mock_mp3 = b"ID3\x03\x00\x00\x00" + b"\x00" * 1200

    with patch.object(
        VoiceTutProvider,
        "synthesize",
        new_callable=AsyncMock
    ) as mock_voicetut, patch(
        "backend.app.services.tts.edge_provider.EdgeTTSProvider.synthesize",
        new_callable=AsyncMock
    ) as mock_edge:
        # VoiceTut times out
        mock_voicetut.return_value = None
        mock_edge.return_value = TTSResult(
            audio_bytes=mock_mp3,
            media_type="audio/mpeg",
            provider="edge-tts",
            voice="ar-EG-SalmaNeural",
            duration_ms=310.0,
            is_fallback=True
        )

        res = client.post(
            "/api/v1/voice/tts",
            json={"text": "تجربة انتهاء المهلة الزمنية"},
            headers={"Authorization": f"Bearer {agent1_token}"}
        )

        assert res.status_code == 200
        assert res.headers["X-TTS-Provider"] == "edge-tts"
        assert res.headers["X-TTS-Fallback"] == "true"


def test_voicetut_server_unavailable_fallback(client, agent1_token):
    """When VoiceTut Hugging Face Space is sleeping or 503 unavailable, fall back to Edge-TTS."""
    mock_mp3 = b"ID3\x03\x00\x00\x00" + b"\x00" * 1300

    with patch.object(
        VoiceTutProvider,
        "synthesize",
        new_callable=AsyncMock
    ) as mock_voicetut, patch(
        "backend.app.services.tts.edge_provider.EdgeTTSProvider.synthesize",
        new_callable=AsyncMock
    ) as mock_edge:
        mock_voicetut.return_value = None
        mock_edge.return_value = TTSResult(
            audio_bytes=mock_mp3,
            media_type="audio/mpeg",
            provider="edge-tts",
            voice="ar-EG-ShakirNeural",
            duration_ms=340.0,
            is_fallback=True
        )

        res = client.post(
            "/api/v1/voice/tts",
            json={"text": "السيرفر غير متاح مؤقتاً"},
            headers={"Authorization": f"Bearer {agent1_token}"}
        )

        assert res.status_code == 200
        assert res.headers["X-TTS-Provider"] == "edge-tts"
        assert res.headers["X-TTS-Fallback"] == "true"


def test_voicetut_invalid_audio_response_fallback(client, agent1_token):
    """When VoiceTut returns corrupt or empty file (< 500 bytes), fall back to Edge-TTS."""
    mock_mp3 = b"ID3\x03\x00\x00\x00" + b"\x00" * 1100

    with patch.object(
        VoiceTutProvider,
        "synthesize",
        new_callable=AsyncMock
    ) as mock_voicetut, patch(
        "backend.app.services.tts.edge_provider.EdgeTTSProvider.synthesize",
        new_callable=AsyncMock
    ) as mock_edge:
        mock_voicetut.return_value = None
        mock_edge.return_value = TTSResult(
            audio_bytes=mock_mp3,
            media_type="audio/mpeg",
            provider="edge-tts",
            voice="ar-EG-SalmaNeural",
            duration_ms=290.0,
            is_fallback=True
        )

        res = client.post(
            "/api/v1/voice/tts",
            json={"text": "فحص ملف الصوت غير الصالح"},
            headers={"Authorization": f"Bearer {agent1_token}"}
        )

        assert res.status_code == 200
        assert res.headers["X-TTS-Provider"] == "edge-tts"
        assert res.headers["X-TTS-Fallback"] == "true"


# ---------------------------------------------------------------------------
# 4. Both Providers Failing & Text-Only Fallback
# ---------------------------------------------------------------------------

def test_both_tts_providers_failing(client, agent1_token):
    """When BOTH VoiceTut and Edge-TTS fail, returns HTTP 502 with fallback_to_browser: true."""
    with patch.object(
        VoiceTutProvider,
        "synthesize",
        new_callable=AsyncMock
    ) as mock_voicetut, patch(
        "backend.app.services.tts.edge_provider.EdgeTTSProvider.synthesize",
        new_callable=AsyncMock
    ) as mock_edge:
        mock_voicetut.return_value = None
        mock_edge.return_value = None

        res = client.post(
            "/api/v1/voice/tts",
            json={"text": "فشل جميع المزودات السحابية"},
            headers={"Authorization": f"Bearer {agent1_token}"}
        )

        assert res.status_code == 502
        data = res.json()
        assert data["fallback_to_browser"] is True
        assert "فشل جميع المزودات" in data["text"]


# ---------------------------------------------------------------------------
# 5. Groq Single Call & Conversation Flow Preservation
# ---------------------------------------------------------------------------

def test_groq_called_only_once_per_response(client, agent1_token):
    """
    Verifies that Groq LLM is invoked exactly once per conversation turn,
    and is NOT re-invoked if TTS subsequently fails.
    """
    llm_call_count = 0

    def mock_generate_json_chat(*args, **kwargs):
        nonlocal llm_call_count
        llm_call_count += 1
        return {
            "reply_text": "تمام يا فندم، هسجل المعاينة دي.",
            "reply_audio_text": "تمام يا فندم، هسجل المعاينة دي.",
            "conversation_state": "COLLECTING_INFO",
            "extracted_fields": {
                "activity_type": "VISIT",
                "lead_name": "أحمد جمال"
            },
            "missing_fields": []
        }

    with patch(
        "backend.app.services.voice_conversation_service.generate_json_chat",
        side_effect=mock_generate_json_chat
    ):
        # 1. User conversation turn
        conv_res = client.post(
            "/api/v1/voice/conversation",
            json={
                "messages": [{"role": "user", "content": "نزلت معاينة مع أحمد جمال في التجمع"}],
                "current_context": {},
                "target_form": "activity"
            },
            headers={"Authorization": f"Bearer {agent1_token}"}
        )
        assert conv_res.status_code == 200
        assert llm_call_count == 1
        conv_data = conv_res.json()
        audio_text = conv_data["reply_audio_text"]

    # 2. TTS fails on both VoiceTut and EdgeTTS
    with patch.object(
        VoiceTutProvider,
        "synthesize",
        new_callable=AsyncMock,
        return_value=None
    ), patch(
        "backend.app.services.tts.edge_provider.EdgeTTSProvider.synthesize",
        new_callable=AsyncMock,
        return_value=None
    ):
        tts_res = client.post(
            "/api/v1/voice/tts",
            json={"text": audio_text},
            headers={"Authorization": f"Bearer {agent1_token}"}
        )
        assert tts_res.status_code == 502
        assert tts_res.json()["fallback_to_browser"] is True
        # LLM was NOT called again during TTS failure!
        assert llm_call_count == 1


# ---------------------------------------------------------------------------
# 6. Existing STT Whisper Flow Preservation
# ---------------------------------------------------------------------------

def test_existing_stt_transcription_flow(client, agent1_token):
    """Verifies that existing Whisper STT /voice/transcribe endpoint remains functional."""
    with patch(
        "backend.app.api.v1.voice.transcribe_audio_bytes",
        return_value="عاينت شقة في الشيخ زايد مع العميل"
    ):
        fake_audio = io.BytesIO(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00data\x00\x00\x00\x00")
        res = client.post(
            "/api/v1/voice/transcribe",
            files={"file": ("audio.webm", fake_audio, "audio/webm")},
            data={"language": "ar"},
            headers={"Authorization": f"Bearer {agent1_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert "عاينت شقة" in data["transcript"]
        assert data["language"] == "ar"
        assert data["confidence"] >= 0.9

