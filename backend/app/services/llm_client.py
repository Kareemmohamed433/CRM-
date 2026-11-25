import json
import logging
import re
from typing import Dict, Any, List, Optional
import httpx

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# One shared client: keeps connections alive, so no new TLS handshake on every voice turn.
_client = httpx.Client(timeout=httpx.Timeout(12.0, connect=3.0))

_THINK_RE = re.compile(r"<think>.*?</think>", re.S)


def is_llm_configured() -> bool:
    """Checks whether an actual LLM provider and API key are configured."""
    return bool(settings.effective_ai_api_key and settings.AI_PROVIDER not in ("mock", "none"))


def _base_url() -> str:
    return settings.AI_API_BASE_URL.rstrip("/")


def _auth_headers(json_body: bool = True) -> Dict[str, str]:
    headers = {"Authorization": f"Bearer {settings.effective_ai_api_key}"}
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def _model() -> str:
    return settings.AI_MODEL or "qwen/qwen3.8-27b"


def generate_chat_completion(
    messages: List[Dict[str, str]],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None
) -> Optional[str]:
    """
    Calls the OpenAI-compatible chat completions endpoint (Groq / OpenAI / Custom).
    Returns the string reply or None on failure/disabled.
    """
    if not is_llm_configured():
        return None

    payload = {
        "model": _model(),
        "messages": messages,
        "temperature": temperature if temperature is not None else settings.AI_TEMPERATURE,
        "max_tokens": max_tokens if max_tokens is not None else settings.AI_MAX_TOKENS,
        # For "thinking" models, disable thinking here (provider-specific), e.g. Groq Qwen3:
        # "reasoning_effort": "none",
    }

             
    try:
        resp = _client.post(f"{_base_url()}/chat/completions", json=payload, headers=_auth_headers())
        if resp.status_code == 200:
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "") or ""
                return _THINK_RE.sub("", content).strip()
            return None
        logger.warning(f"LLM API returned status {resp.status_code}: {resp.text[:300]}")
        return None
    except Exception as e:
        logger.warning(f"Failed to communicate with LLM endpoint: {e}")
        return None
def generate_json_completion(
    system_prompt: str,
    user_prompt: str,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Requests a structured JSON response from the LLM (single system + user prompt).
    """
    return generate_json_chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=12.0,
    )


def safe_extract_json(raw: str) -> Optional[Dict[str, Any]]:
    """
    Robustly parses JSON from LLM output.
    Handles:
    - Direct JSON strings
    - Markdown code fences (```json ... ``` or ``` ... ```)
    - Conversational Arabic/English text surrounding the JSON block
    - Trailing commas before closing braces/brackets
    - LLM reply that is pure Arabic text with no JSON (returns None cleanly)
    """
    if not raw or not isinstance(raw, str):
        return None

    cleaned = _THINK_RE.sub("", raw).strip()
    if not cleaned:
        return None

    # 1. Direct parse attempt
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # 2. Extract from markdown code fences: ```json ... ``` or ``` ... ```
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if fence_match:
        fence_content = fence_match.group(1).strip()
        try:
            data = json.loads(fence_content)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    # 3. Find outermost curly braces { ... } — works even with Arabic text before/after
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = cleaned[first_brace : last_brace + 1]
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        # 4. Strip trailing commas before } and ]
        fixed = re.sub(r",\s*([\]}])", r"\1", candidate)
        try:
            data = json.loads(fixed)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    # 5. LLM returned pure Arabic/text with no JSON at all — log and return None cleanly
    logger.debug(f"safe_extract_json: no JSON found in response (len={len(cleaned)}), treating as plain text reply.")
    return None


def generate_json_chat(
    messages: List[Dict[str, str]],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: float = 8.0,
) -> Optional[Dict[str, Any]]:
    """
    Structured JSON response using a full chat history.
    Uses safe_extract_json to guarantee resilient parsing even when the LLM
    returns markdown fences or text preambles.
    """
    if not is_llm_configured():
        return None

    payload = {
        "model": _model(),
        "messages": messages,
        "temperature": temperature if temperature is not None else 0.2,
        "max_tokens": max_tokens if max_tokens is not None else settings.AI_MAX_TOKENS,
        # NOTE: response_format json_object is NOT supported by Qwen on Groq.
        # We rely on safe_extract_json() to parse JSON from free-form text instead.
    }

    try:
        resp = _client.post(
            f"{_base_url()}/chat/completions",
            json=payload,
            headers=_auth_headers(),
            timeout=timeout,
        )
        if resp.status_code != 200:
            logger.warning(f"LLM JSON API returned status {resp.status_code}: {resp.text[:300]}")
            return None
        raw_content = resp.json()["choices"][0]["message"]["content"] or ""
        extracted = safe_extract_json(raw_content)
        if extracted is None:
            # LLM replied with plain Arabic text (no JSON) — wrap it so callers get a usable reply
            plain = _THINK_RE.sub("", raw_content).strip()
            if plain:
                logger.debug(f"LLM returned plain text instead of JSON, wrapping as reply: {plain[:120]}")
                return {"fields": {}, "reply": plain}
            logger.warning(f"LLM returned empty or unparseable response: {raw_content[:200]}")
        return extracted
    except Exception as e:
        logger.warning(f"Failed to get structured JSON from LLM: {e}")
        return None


def transcribe_audio_bytes(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    language: str = "ar",
    prompt: Optional[str] = None,
    content_type: str = "audio/webm",
) -> Optional[str]:
    """
    Transcribes audio bytes using Groq Whisper (whisper-large-v3-turbo / whisper-large-v3).
    `prompt` biases Whisper toward domain vocabulary (e.g. Egyptian real-estate terms).
    Returns Arabic transcript text or None.
    """
    if not is_llm_configured():
        return None

    files = {"file": (filename, audio_bytes, content_type or "audio/webm")}
    data = {
        "model": "whisper-large-v3-turbo",
        "language": language,
        "response_format": "json",
        "temperature": "0",
    }
    if prompt:
        data["prompt"] = prompt

    try:
        resp = _client.post(
            f"{_base_url()}/audio/transcriptions",
            headers=_auth_headers(json_body=False),
            files=files,
            data=data,
            timeout=30.0,
        )
        if resp.status_code == 200:
            return (resp.json().get("text", "") or "").strip()
        logger.warning(f"Whisper transcription failed with status {resp.status_code}: {resp.text[:300]}")
        return None
    except Exception as e:
        logger.warning(f"Audio transcription exception: {e}")
        return None