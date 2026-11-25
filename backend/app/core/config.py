import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Nexora Real Estate CRM SaaS"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    TIMEZONE: str = "Africa/Cairo"
    
    # Security & Tokens
    SECRET_KEY: str = "insecure-dev-secret-key-change-in-production-realestatecrm-2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day for dev convenience
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    # Defaults to local SQLite file for immediate out-of-the-box local operation;
    # in docker or production, set DATABASE_URL=postgresql://postgres:postgres@db:5432/crm_db
    DATABASE_URL: str = "sqlite:///./crm.db"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "*"
    ]

    # AI & Speech Configuration
    AI_PROVIDER: str = "openai"  # "mock" | "openai" | "groq" | "gemini"
    AI_API_KEY: str = ""
    AI_API_BASE_URL: str = "https://api.groq.com/openai/v1"
    AI_MODEL: str = "qwen/qwen3.8-27b"
    AI_TEMPERATURE: float = 0.3
    AI_MAX_TOKENS: int = 500

    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # Cloudflare Workers AI (Image Generation)
    CLOUDFLARE_ACCOUNT_ID: str = ""
    CLOUDFLARE_API_TOKEN: str = ""
    CLOUDFLARE_IMAGE_MODEL: str = "@cf/black-forest-labs/flux-1-schnell"

    # Meta Graph API (Facebook Page Publishing)
    FACEBOOK_PAGE_ID: str = ""
    FACEBOOK_PAGE_ACCESS_TOKEN: str = ""
    FACEBOOK_API_VERSION: str = "v20.0"

    STT_PROVIDER: str = "mock"  # "mock" | "whisper" | "browser"

    # TTS Settings: VoiceTut-TTS as Primary with Edge-TTS Fallback
    TTS_PRIMARY_PROVIDER: str = "voicetut"  # "voicetut" | "edge-tts"
    VOICETUT_SPACE_URL: str = "https://huggingface.co/spaces/mohammedaly22/VoiceTut-TTS"
    VOICETUT_VOICE: str = "Ahmed"           # Default male Egyptian voice: "Ahmed", "Karim", "Ali", "Hassan"
    VOICETUT_TIMEOUT: float = 12.0          # Max seconds before automatic fallback
    VOICETUT_NUM_STEPS: int = 16            # Steps (8-32, 16 is fast & high fidelity)
    VOICETUT_SPEED: float = 1.0             # Speech rate multiplier
    VOICETUT_GUIDANCE: float = 2.0          # Guidance scale
    VOICETUT_NORMALIZE: bool = True         # Auto-normalize numbers, dates, EGP
    HF_TOKEN: Optional[str] = None          # Hugging Face token (loaded from env only)

    # Edge-TTS Fallback Voices
    EDGE_TTS_VOICE_PRIMARY: str = "ar-EG-SalmaNeural"
    EDGE_TTS_VOICE_SECONDARY: str = "ar-EG-ShakirNeural"

    @property
    def effective_ai_api_key(self) -> str:
        return (self.AI_API_KEY or self.OPENAI_API_KEY or "").strip()

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", "backend/.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


settings = Settings()
