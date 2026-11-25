import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union
from jose import jwt, JWTError
from backend.app.core.config import settings

# Salt for fallback secure hashing if passlib bcrypt has platform compatibility issues
SALT = b"crm_real_estate_salt_2026_secure"


def get_password_hash(password: str) -> str:
    # Use standard PBKDF2 HMAC SHA256 - pure python, fast, zero C-lib compilation issues on Windows
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), SALT, 100000)
    return "pbkdf2_sha256$" + key.hex()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    if hashed_password.startswith("pbkdf2_sha256$"):
        expected_hash = hashed_password.split("$", 1)[1]
        test_hash = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), SALT, 100000).hex()
        return hmac.compare_digest(expected_hash, test_hash)
    # Fallback plain comparison for simple testing if needed
    return hmac.compare_digest(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
