import base64
import hashlib
import hmac
import json


def sign_session(participant_id: int, secret: str) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"participant_id": participant_id}).encode()).decode()
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_session(value: str | None, secret: str) -> int | None:
    if not value or "." not in value:
        return None
    payload, signature = value.rsplit(".", 1)
    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        return int(json.loads(base64.urlsafe_b64decode(payload)).get("participant_id"))
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
