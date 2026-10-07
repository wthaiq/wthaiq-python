"""Transports against a real local HTTP server and httpx mock transports."""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

import wthaiq
from wthaiq import HttpRequest
from wthaiq.transport import (
    AsyncHttpxTransport,
    HttpxTransport,
    ThreadedAsyncTransport,
    UrllibTransport,
)

from .conftest import TEST_KEY


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass

    def _reply(self, status: int, body: bytes, headers: dict[str, str] | None = None) -> None:
        try:
            self.send_response(status)
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except OSError:
            pass

    def do_GET(self) -> None:
        if self.path.startswith("/api/v1/redirect"):
            self._reply(302, b"", {"Location": "http://127.0.0.1:1/steal"})
        elif self.path.startswith("/api/v1/slow"):
            time.sleep(1.0)
            self._reply(200, b"{}")
        elif "missing" in self.path:
            self._reply(
                404,
                json.dumps({"error": {"code": "resource_missing", "message": "x"}}).encode(),
                {"Content-Type": "application/json", "Wthaiq-Request-Id": "req_1"},
            )
        else:
            echo = {
                "object": "api_root",
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "version": self.headers.get("Wthaiq-Version"),
                "agent": self.headers.get("User-Agent"),
            }
            self._reply(200, json.dumps(echo).encode(), {"Set-Cookie": "a=1", "X-Multi": "1"})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        echo = {
            "object": "echo",
            "body": body.decode("utf-8"),
            "content_type": self.headers.get("Content-Type"),
            "idempotency_key": self.headers.get("Idempotency-Key"),
        }
        self._reply(201, json.dumps(echo, ensure_ascii=False).encode("utf-8"))

    do_DELETE = do_GET


@pytest.fixture(scope="module")
def server() -> Iterator[str]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/api/v1"
    httpd.shutdown()


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_urllib_end_to_end(server: str) -> None:
    client = wthaiq.Client(TEST_KEY, base_url=server)
    root = client.account.retrieve()
    assert root.authorization == f"Bearer {TEST_KEY}"
    assert root.version == "2026-07-01"
    assert root.agent.startswith("wthaiq-python/")
    assert root.last_response is not None
    assert root.last_response.get_header("x-multi") == "1"
    created = client.templates.create(name="عقد", content="<p>x</p>")
    assert json.loads(created.body) == {"name": "عقد", "content": "<p>x</p>"}
    assert created.content_type == "application/json"
    assert created.idempotency_key


def test_urllib_returns_error_responses(server: str) -> None:
    client = wthaiq.Client(TEST_KEY, base_url=server, max_retries=0)
    with pytest.raises(wthaiq.NotFoundError) as info:
        client.signature_requests.retrieve("missing")
    assert info.value.request_id == "req_1"


def test_urllib_does_not_follow_redirects(server: str) -> None:
    transport = UrllibTransport()
    result = transport.send(HttpRequest("GET", f"{server}/redirect", {}))
    assert result.status_code == 302
    assert result.headers["location"] == "http://127.0.0.1:1/steal"


def test_urllib_timeout(server: str) -> None:
    with pytest.raises(wthaiq.ApiConnectionError) as info:
        UrllibTransport().send(HttpRequest("GET", f"{server}/slow", {}, timeout=0.2))
    assert info.value.timed_out is True
    assert "timed out" in str(info.value)


def test_urllib_connection_refused() -> None:
    url = f"http://127.0.0.1:{free_port()}/api/v1/"
    with pytest.raises(wthaiq.ApiConnectionError) as info:
        UrllibTransport().send(HttpRequest("GET", url, {}, timeout=15))
    assert info.value.timed_out is False
    assert "Could not connect" in str(info.value)


def test_urllib_with_explicit_proxies(server: str) -> None:
    transport = UrllibTransport(proxies={})
    assert transport.send(HttpRequest("GET", f"{server}/", {})).status_code == 200
    transport.close()


def test_threaded_async_transport(server: str) -> None:
    async def run() -> None:
        client = wthaiq.AsyncClient(
            TEST_KEY, base_url=server, http_client=ThreadedAsyncTransport(UrllibTransport())
        )
        root = await client.account.retrieve()
        assert root.object == "api_root"
        await client.aclose()
        owned = ThreadedAsyncTransport()
        assert (await owned.send(HttpRequest("GET", f"{server}/", {}))).status_code == 200
        await owned.aclose()

    asyncio.run(run())


def test_httpx_transport() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/boom"):
            raise httpx.ConnectError("refused", request=request)
        if request.url.path.endswith("/slow"):
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(302, headers={"Location": "https://evil.example"}, content=b"")

    transport = HttpxTransport(httpx.Client(transport=httpx.MockTransport(handler)))
    result = transport.send(
        HttpRequest("POST", "https://wthaiq.com/api/v1/x", {"A": "b"}, b"{}", 5, 2)
    )
    assert result.status_code == 302, "redirects are returned, never followed"
    assert seen[0].headers["A"] == "b"
    assert seen[0].content == b"{}"
    with pytest.raises(wthaiq.ApiConnectionError) as info:
        transport.send(HttpRequest("GET", "https://wthaiq.com/api/v1/boom", {}))
    assert info.value.timed_out is False
    with pytest.raises(wthaiq.ApiConnectionError) as info:
        transport.send(HttpRequest("GET", "https://wthaiq.com/api/v1/slow", {}))
    assert info.value.timed_out is True
    transport.close()
    owned = HttpxTransport()
    owned.close()


def test_async_httpx_transport() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/boom"):
            raise httpx.ConnectTimeout("slow", request=request)
        return httpx.Response(200, json={"object": "api_root", "method": request.method})

    async def run() -> None:
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        transport = AsyncHttpxTransport(http)
        result = await transport.send(HttpRequest("DELETE", "https://wthaiq.com/api/v1/x", {}))
        assert json.loads(result.body)["method"] == "DELETE"
        with pytest.raises(wthaiq.ApiConnectionError) as info:
            await transport.send(HttpRequest("GET", "https://wthaiq.com/api/v1/boom", {}))
        assert info.value.timed_out is True
        await transport.aclose()
        assert not http.is_closed
        await http.aclose()
        owned = AsyncHttpxTransport()
        await owned.aclose()

    asyncio.run(run())
