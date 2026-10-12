from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from cua_platform.api import novnc


def test_novnc_proxy_preserves_redirect_for_browser(authenticated_client):
    redirect_location = (
        "/novnc/vnc.html"
        "?autoconnect=true&path=novnc%2Fws%3Fsid%3Dupstream"
    )

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/novnc/view?sid=upstream":
                self.send_response(302)
                self.send_header("Location", redirect_location)
                self.send_header(
                    "Set-Cookie",
                    "cua_novnc_session_http=upstream-cookie; Path=/novnc",
                )
                self.end_headers()
                return

            cookie = self.headers.get("Cookie", "")
            self.send_response(
                200 if "cua_novnc_session_http=upstream-cookie" in cookie else 401
            )
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        sid = authenticated_client.app.state.novnc_proxy_store.create(
            base_url=f"http://127.0.0.1:{server.server_port}",
            viewer_url=(
                f"http://127.0.0.1:{server.server_port}/novnc/view?sid=upstream"
            ),
            websocket_url=None,
            expires_at=None,
        )

        response = authenticated_client.get(
            f"/novnc/view?sid={sid}",
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert response.headers["location"] == redirect_location
        assert "cua_novnc_proxy_session=" in response.headers["set-cookie"]
        session = authenticated_client.app.state.novnc_proxy_store.get(sid)
        assert session is not None
        assert session.cookie_header == "cua_novnc_session_http=upstream-cookie"

        redirected = authenticated_client.get(response.headers["location"])

        assert redirected.status_code == 200
        assert redirected.content == b"ok"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_novnc_proxy_view_sets_same_origin_session_cookie(authenticated_client, monkeypatch):
    sid = authenticated_client.app.state.novnc_proxy_store.create(
        base_url="http://agent.example.com:8910",
        viewer_url="http://agent.example.com:8910/novnc/view?sid=upstream",
        websocket_url="ws://agent.example.com:8910/novnc/ws?sid=upstream",
        expires_at=None,
    )

    async def fake_proxy_http_request(session, **_kwargs):
        session.cookie_header = "cua_novnc_session_http=upstream-cookie"
        return 200, [("Content-Type", "text/html")], b"<html>ok</html>"

    monkeypatch.setattr(novnc, "proxy_http_request", fake_proxy_http_request)

    response = authenticated_client.get(f"/novnc/view?sid={sid}")

    assert response.status_code == 200
    assert response.text == "<html>ok</html>"
    assert "cua_novnc_proxy_session=" in response.headers["set-cookie"]
    assert "Path=/novnc" in response.headers["set-cookie"]


def test_novnc_proxy_rejects_missing_session(authenticated_client):
    response = authenticated_client.post(
        "/novnc/resize",
        json={"width": 1280, "height": 720, "dpr": 1},
    )

    assert response.status_code == 401
    assert response.json() == {"success": False, "stderr": "invalid session"}
