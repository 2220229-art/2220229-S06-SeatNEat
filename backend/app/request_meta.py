from fastapi import Request


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        host = forwarded.split(",")[0].strip()
        return host[:80] or None
    if request.client and request.client.host:
        return request.client.host[:80]
    return None


def client_agent(request: Request) -> str | None:
    agent = request.headers.get("user-agent", "").strip()
    return agent[:300] or None
