from fastapi import HTTPException, status, Depends
from fastapi.security import APIKeyHeader
import os
import time
import logging

# Optional import; the API may run locally without GCP Secret Manager
try:
    from google.cloud import secretmanager
except Exception:
    secretmanager = None

API_KEY_NAME = 'X-API-Key'
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

SECRET_ID = 'gameteam-api-keys'
ENV_KEYS_NAME = 'GAMETEAM_API_KEYS'

# Secret Manager lookups are cached so an authenticated request does not cost a
# network round trip. Without this, every request builds a fresh client and
# calls Secret Manager, which dominates latency at min-instances 0.
SECRET_CACHE_TTL_SECONDS = 300

_client = None
_cached_keys = None
_cached_at = 0.0


def _get_client():
    """Return a lazily created, reused Secret Manager client."""
    global _client
    if secretmanager is None:
        raise RuntimeError("google-cloud-secret-manager is not installed")
    if _client is None:
        _client = secretmanager.SecretManagerServiceClient()
    return _client


def get_secret(secret_id: str) -> str:
    """Retrieve secret from Google Secret Manager. Returns string or raises."""
    project_id = os.environ.get('GCP_PROJECT_ID')
    if not project_id:
        raise RuntimeError('GCP_PROJECT_ID env variable not set')
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = _get_client().access_secret_version(request={"name": name})
    return response.payload.data.decode('UTF-8')


def _parse_keys(raw: str) -> dict:
    """Parse a comma-separated 'app:key' list into a mapping key -> app_name."""
    keys = {}
    for entry in raw.split(','):
        parts = entry.strip().split(':')
        if len(parts) >= 2:
            keys[parts[1].strip()] = parts[0].strip()
    return keys


def load_api_keys() -> dict:
    """Load API keys; prefer Secret Manager, fall back to env vars.

    Returns a mapping key -> app_name.
    """
    try:
        if secretmanager is not None and os.environ.get('GCP_PROJECT_ID'):
            keys = _parse_keys(get_secret(SECRET_ID))
            if keys:
                logging.getLogger(__name__).info(
                    f"Loaded {len(keys)} API key(s) from Secret Manager"
                )
                return keys
    except Exception:
        # ignore; fallback to env
        pass

    env_keys_raw = os.environ.get(ENV_KEYS_NAME)
    return _parse_keys(env_keys_raw) if env_keys_raw else {}


def get_valid_api_keys() -> dict:
    """Return the current mapping of API keys, cached for SECRET_CACHE_TTL_SECONDS.

    The env var path is deliberately left uncached so that tests which set
    GAMETEAM_API_KEYS at runtime take effect immediately.
    """
    global _cached_keys, _cached_at

    using_secret_manager = secretmanager is not None and os.environ.get('GCP_PROJECT_ID')
    if not using_secret_manager:
        try:
            return load_api_keys() or {}
        except Exception:
            return {}

    now = time.monotonic()
    if _cached_keys is not None and (now - _cached_at) < SECRET_CACHE_TTL_SECONDS:
        return _cached_keys

    try:
        _cached_keys = load_api_keys() or {}
        _cached_at = now
        return _cached_keys
    except Exception:
        return _cached_keys or {}


def refresh_valid_api_keys() -> dict:
    """Clear the cache and reload API keys immediately."""
    global _cached_keys, _cached_at
    _cached_keys = None
    _cached_at = 0.0
    return get_valid_api_keys()


def mask_key(key: str) -> str:
    if not key:
        return ''
    visible_start = 8
    visible_end = 4
    if len(key) <= visible_start + visible_end + 3:
        return key[:visible_start] + '...'
    return key[:visible_start] + '...' + key[-visible_end:]


async def require_api_key(api_key: str = Depends(api_key_header)):
    """FastAPI dependency to require an API key in the X-API-Key header."""
    if not api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail='Missing API key in header')
    keys = get_valid_api_keys()
    if api_key not in keys:
        logging.getLogger().warning(f"Invalid API key received: {mask_key(api_key)}")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail='Invalid API key')
    app_name = keys[api_key]
    logging.getLogger().info(f"API access granted for app '{app_name}': {mask_key(api_key)}")
    return {'app_name': app_name, 'api_key': api_key}
