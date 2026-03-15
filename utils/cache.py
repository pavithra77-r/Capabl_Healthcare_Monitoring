import os

# Redis connection (optional) - DISABLED FOR LOCAL DEVELOPMENT
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_redis_client = None


def get_redis():
    """Get a shared Redis client instance."""
    # Return None if Redis is not needed for local dev
    return None


def cache_set(key: str, value: str, expire_seconds: int = 60):
    """Set cache - disabled for local development."""
    pass  # Do nothing if Redis is not available


def cache_get(key: str) -> str | None:
    """Get cache - disabled for local development."""
    return None  # Always return None if Redis is not available