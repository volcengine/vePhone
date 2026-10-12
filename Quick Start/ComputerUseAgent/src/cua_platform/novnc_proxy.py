import asyncio
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from http.cookies import SimpleCookie
from urllib.parse import urljoin
from urllib.request import HTTPRedirectHandler, Request as UrlRequest, build_opener

from starlette.websockets import WebSocket


@dataclass
class NoVncProxySession:
    base_url: str
    viewer_url: str
    websocket_url: str | None
    expires_at: int | None = None
    cookie_header: str = ""


class _NoRedirectHandler(HTTPRedirectHandler):
    def http_error_302(self, _request, response, _code, _message, _headers):
        return response

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = (
        http_error_302
    )


class NoVncProxyStore:
    def __init__(self) -> None:
        self._sessions: dict[str, NoVncProxySession] = {}

    def create(self, *, base_url: str, viewer_url: str, websocket_url: str | None, expires_at: int | None) -> str:
        self.cleanup()
        session_id = secrets.token_urlsafe(24)
        self._sessions[session_id] = NoVncProxySession(
            base_url=base_url.rstrip("/"),
            viewer_url=viewer_url,
            websocket_url=websocket_url,
            expires_at=expires_at,
        )
        return session_id

    def get(self, session_id: str | None) -> NoVncProxySession | None:
        if not session_id:
            return None
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if session.expires_at and session.expires_at <= int(datetime.now(UTC).timestamp()):
            self._sessions.pop(session_id, None)
            return None
        return session

    def cleanup(self) -> None:
        now = int(datetime.now(UTC).timestamp())
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if session.expires_at and session.expires_at <= now
        ]
        for session_id in expired:
            self._sessions.pop(session_id, None)


def update_session_cookie(session: NoVncProxySession, set_cookie_headers: list[str]) -> None:
    cookie = SimpleCookie()
    if session.cookie_header:
        cookie.load(session.cookie_header)
    for header in set_cookie_headers:
        cookie.load(header)
    session.cookie_header = "; ".join(
        f"{key}={morsel.value}" for key, morsel in cookie.items()
    )


async def proxy_http_request(
    session: NoVncProxySession,
    *,
    method: str,
    path: str,
    query: str,
    body: bytes,
    content_type: str | None,
) -> tuple[int, list[tuple[str, str]], bytes]:
    return await asyncio.to_thread(
        _proxy_http_request,
        session,
        method,
        path,
        query,
        body,
        content_type,
    )


def _proxy_http_request(
    session: NoVncProxySession,
    method: str,
    path: str,
    query: str,
    body: bytes,
    content_type: str | None,
) -> tuple[int, list[tuple[str, str]], bytes]:
    upstream = urljoin(f"{session.base_url}/", f"novnc/{path}")
    if query:
        upstream = f"{upstream}?{query}"
    headers = {}
    if content_type:
        headers["Content-Type"] = content_type
    if session.cookie_header:
        headers["Cookie"] = session.cookie_header
    request = UrlRequest(
        upstream,
        data=body if body else None,
        headers=headers,
        method=method,
    )
    opener = build_opener(_NoRedirectHandler())
    with opener.open(request, timeout=15) as response:  # noqa: S310 - URL comes from CUA.
        content = response.read()
        response_headers = list(response.headers.items())
        update_session_cookie(session, response.headers.get_all("Set-Cookie") or [])
        return response.status, response_headers, content


async def relay_websocket(websocket: WebSocket, session: NoVncProxySession) -> None:
    if not session.websocket_url:
        await websocket.close(code=1011)
        return
    import websockets

    await websocket.accept()
    headers = {}
    if session.cookie_header:
        headers["Cookie"] = session.cookie_header
    async with websockets.connect(
        session.websocket_url,
        additional_headers=headers,
    ) as upstream:
        client_to_upstream = asyncio.create_task(_client_to_upstream(websocket, upstream))
        upstream_to_client = asyncio.create_task(_upstream_to_client(websocket, upstream))
        done, pending = await asyncio.wait(
            {client_to_upstream, upstream_to_client},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        for task in done:
            task.result()


async def _client_to_upstream(websocket: WebSocket, upstream) -> None:
    while True:
        message = await websocket.receive()
        if message["type"] == "websocket.disconnect":
            await upstream.close()
            return
        if "bytes" in message and message["bytes"] is not None:
            await upstream.send(message["bytes"])
        elif "text" in message and message["text"] is not None:
            await upstream.send(message["text"])


async def _upstream_to_client(websocket: WebSocket, upstream) -> None:
    async for message in upstream:
        if isinstance(message, bytes):
            await websocket.send_bytes(message)
        else:
            await websocket.send_text(message)
