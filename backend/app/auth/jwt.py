from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from app.config.settings import settings
from app.core.exceptions import AuthenticationError
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        "iss": settings.JWT_ISSUER,
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(
        payload, settings.JWT_SECRET_KEY.get_secret_value(), algorithm=settings.JWT_ALGORITHM)
    logger.debug(
        "access_token_created",
        user_id=str(user_id),
        role=role,
        algorithm=settings.JWT_ALGORITHM,
        issuer=settings.JWT_ISSUER,
        expires_in_minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    )
    return token


def create_refresh_token(user_id: uuid.UUID) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        "iss": settings.JWT_ISSUER,
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(
        payload, settings.JWT_SECRET_KEY.get_secret_value(), algorithm=settings.JWT_ALGORITHM)
    logger.debug(
        "refresh_token_created",
        user_id=str(user_id),
        algorithm=settings.JWT_ALGORITHM,
        issuer=settings.JWT_ISSUER,
    )
    return token


def decode_token(token: str) -> dict:
    logger.debug("jwt_decode_started", token_preview=token[:10] + "..." if len(token) > 10 else token[:5])

    secret = settings.JWT_SECRET_KEY.get_secret_value()
    algorithm = settings.JWT_ALGORITHM
    issuer = settings.JWT_ISSUER

    try:
        payload = jwt.decode(
            token, secret, algorithms=[algorithm],
            options={"verify_exp": True, "verify_iss": True}, issuer=issuer)
    except JWTError as exc:
        logger.warning(
            "token_decode_failed",
            error=str(exc),
            algorithm=algorithm,
            issuer=issuer,
        )
        raise AuthenticationError("Invalid or expired token") from exc

    logger.debug(
        "jwt_decode_succeeded",
        sub=payload.get("sub", "missing"),
        type=payload.get("type", "missing"),
        iss=payload.get("iss", "missing"),
        jti=payload.get("jti", "missing"),
    )
    return payload


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def extract_user_id_from_token(token: str) -> uuid.UUID:
    payload = decode_token(token)
    return uuid.UUID(payload["sub"])


async def is_token_blacklisted(jti: str) -> bool:
    try:
        from app.dependencies.redis import get_redis
        redis_client = await get_redis()
        result = await redis_client.exists(f"jti_blacklist:{jti}")
        is_blacklisted = result > 0
        if is_blacklisted:
            logger.debug("token_blacklist_hit", jti=jti)
        return is_blacklisted
    except Exception as exc:
        logger.debug("token_blacklist_redis_unavailable", error=str(exc))
        return False


async def blacklist_token(jti: str, expires_at: datetime) -> None:
    try:
        from app.dependencies.redis import get_redis
        redis_client = await get_redis()
        ttl_seconds = max(1, int((expires_at - datetime.now(UTC)).total_seconds()))
        await redis_client.setex(f"jti_blacklist:{jti}", ttl_seconds, "1")
        logger.debug("token_blacklisted", jti=jti, ttl=ttl_seconds)
    except Exception as exc:
        logger.warning("token_blacklist_failed", jti=jti, error=str(exc))
