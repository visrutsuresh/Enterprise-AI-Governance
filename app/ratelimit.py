"""Per-key sliding-window rate limiter.

ponytail: in-memory on purpose. The app is pinned to one uvicorn worker
(cancellation state is already in-process), so a shared dict is correct.
Move to Redis only if we ever scale past one worker.
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException

_hits: dict[str, deque] = defaultdict(deque)


def check(key: str, max_calls: int, window_s: int) -> None:
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > window_s:
        q.popleft()
    if len(q) >= max_calls:
        raise HTTPException(status_code=429, detail="Too many requests. Wait a minute and try again.")
    q.append(now)


def client_ip(request) -> str:
    # first hop in X-Forwarded-For when behind a proxy (Render), else the socket peer
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
