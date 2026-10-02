import time


def allowed(request, bucket: str, limit: int = 10, window: int = 60) -> bool:
    now = time.monotonic()
    key = (request.client.host if request.client else "unknown", bucket)
    entries = request.app.state.rate_limits.setdefault(key, [])
    entries[:] = [value for value in entries if now - value < window]
    if len(entries) >= limit:
        return False
    entries.append(now)
    return True
