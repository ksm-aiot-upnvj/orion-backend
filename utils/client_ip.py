import ipaddress

from fastapi import Request

from config.config import settings


def _valid_ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def get_client_ip(request: Request) -> str:
    """
    Resolve the client IP for rate limiting and audit logs.

    X-Forwarded-For is client-controlled except for the entries appended by our own proxies, so with
    TRUSTED_PROXY_HOPS=N the N-th entry from the right is used (the address our outermost proxy saw).
    With 0 hops the header is ignored. Anything that is not a valid IP falls back to the socket peer.
    """
    peer = request.client.host if request.client else "127.0.0.1"
    hops = settings.TRUSTED_PROXY_HOPS
    if hops > 0:
        forwarded = [part.strip() for part in request.headers.get("X-Forwarded-For", "").split(",") if part.strip()]
        if len(forwarded) >= hops:
            candidate = _valid_ip(forwarded[-hops])
            if candidate:
                return candidate
    return _valid_ip(peer) or "127.0.0.1"
