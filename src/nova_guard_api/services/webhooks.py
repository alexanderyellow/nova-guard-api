import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any

import httpx

from nova_guard_api.core.config import get_settings


def sign_payload(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def dispatch_webhook(event: str, payload: dict[str, Any]) -> None:
    settings = get_settings()
    if not settings.webhook_url:
        return
    body = json.dumps({"event": event, "payload": payload, "ts": datetime.now(UTC).isoformat()}).encode()
    sig = sign_payload(settings.webhook_hmac_secret, body)
    headers = {
        "Content-Type": "application/json",
        "X-Nova-Guard-Signature": sig,
        "X-Nova-Guard-Event": event,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(settings.webhook_url, content=body, headers=headers)
    except Exception:
        pass


def dispatch_webhook_sync(event: str, payload: dict[str, Any]) -> None:
    settings = get_settings()
    if not settings.webhook_url:
        return
    body = json.dumps({"event": event, "payload": payload, "ts": datetime.now(UTC).isoformat()}).encode()
    sig = sign_payload(settings.webhook_hmac_secret, body)
    headers = {
        "Content-Type": "application/json",
        "X-Nova-Guard-Signature": sig,
        "X-Nova-Guard-Event": event,
    }
    try:
        httpx.post(settings.webhook_url, content=body, headers=headers, timeout=5.0)
    except Exception:
        pass
