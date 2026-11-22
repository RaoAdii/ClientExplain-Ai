"""Atomic Redis fixed windows shared across API processes."""

from app.core.config import settings
from app.db.session import redis_client
from fastapi import HTTPException, Response
from redis.exceptions import RedisError

ADMIT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
local ttl = redis.call('TTL', KEYS[1])
if ttl < 0 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
    ttl = tonumber(ARGV[1])
end
return {count, ttl}
"""


def rate_limit(principal, operation: str, response: Response):
    limit = getattr(settings, f"{operation}_rate_limit")
    key = f"clientexplain:rate:{operation}:{principal.firm_id}:{principal.user_id}"
    try:
        count, ttl = redis_client.eval(ADMIT, 1, key, settings.rate_limit_window_seconds)
    except RedisError:
        raise HTTPException(503, "Request admission is unavailable. Try again shortly.") from None
    headers = {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(max(0, limit - count)),
        "X-RateLimit-Reset": str(max(1, ttl)),
    }
    if count > limit:
        raise HTTPException(
            429,
            "Too many requests. Try again shortly.",
            headers={**headers, "Retry-After": str(max(1, ttl))},
        )
    response.headers.update(headers)
