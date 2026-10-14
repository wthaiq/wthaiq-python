from __future__ import annotations

import asyncio
import platform

import httpx
import pytest

import wthaiq
from wthaiq import HttpRequest, HttpResponse, InvalidArgumentError
from wthaiq.transport import AsyncHttpxTransport, ThreadedAsyncTransport, UrllibTransport

from .conftest import (
    LIVE_KEY,
    TEST_KEY,
    AsyncFakeTransport,
    FakeTransport,
    make_async_client,
    make_client,
    response,
)


def test_defaults() -> None:
    client = wthaiq.Client(TEST_KEY)
    assert client.base_url == "https://wthaiq.com/api/v1"
    assert client.api_version == wthaiq.API_VERSION == "2026-07-01"
    assert client.user_agent == f"wthaiq-python/{wthaiq.VERSION} Python/{platform.python_version()}"
    assert isinstance(client._requestor.transport, UrllibTransport)
    assert client.is_test_mode() and not client.is_live_mode()
    assert wthaiq.Client(LIVE_KEY).is_live_mode()
    assert wthaiq.Client("pk_test_" + "c" * 40).is_test_mode()


def test_repr_never_shows_the_key() -> None:
    text = repr(wthaiq.Client(TEST_KEY))
    assert TEST_KEY not in text
    assert text == "<wthaiq.Client test https://wthaiq.com/api/v1>"


@pytest.mark.parametrize(
    "key", [None, "", "abc", "Bearer sk_test_x", " sk_test_x", "sk_te st", 123]
)
def test_invalid_keys(key: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WTHAIQ_API_KEY", raising=False)
    with pytest.raises(InvalidArgumentError):
        wthaiq.Client(key)  # type: ignore[arg-type]


def test_key_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WTHAIQ_API_KEY", TEST_KEY)
    assert wthaiq.Client().is_test_mode()


def test_invalid_key_is_also_a_value_error() -> None:
    with pytest.raises(ValueError, match="sk_"):
        wthaiq.Client("nope")


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://example.com/api/v1/", "https://example.com/api/v1"),
        ("http://127.0.0.1:8782/api/v1", "http://127.0.0.1:8782/api/v1"),
        ("http://localhost/api/v1", "http://localhost/api/v1"),
        ("http://wthaiq.test/api/v1", "http://wthaiq.test/api/v1"),
    ],
)
def test_base_url_accepted(url: str, expected: str) -> None:
    assert wthaiq.Client(TEST_KEY, base_url=url).base_url == expected


@pytest.mark.parametrize("url", ["http://wthaiq.com/api/v1", "ftp://x", "", "wthaiq.com"])
def test_base_url_refused(url: str) -> None:
    with pytest.raises(InvalidArgumentError):
        wthaiq.Client(TEST_KEY, base_url=url)


@pytest.mark.parametrize(
    "options",
    [
        {"timeout": 0},
        {"timeout": -1},
        {"timeout": True},
        {"connect_timeout": 0},
        {"max_retries": -1},
        {"max_retries": 1.5},
        {"api_version": ""},
        {"app_info": {"version": "1"}},
        {"language": ""},
        {"language": "en us"},
        {"language": 1},
    ],
)
def test_invalid_options(options: dict[str, object]) -> None:
    with pytest.raises(InvalidArgumentError):
        wthaiq.Client(TEST_KEY, **options)  # type: ignore[arg-type]


def test_app_info_in_user_agent() -> None:
    client = wthaiq.Client(
        TEST_KEY, app_info={"name": "Acme", "version": "2.1", "url": "https://acme.example"}
    )
    assert client.user_agent.endswith(" Acme/2.1 (https://acme.example)")
    assert wthaiq.Client(TEST_KEY, app_info={"name": "Acme"}).user_agent.endswith(" Acme")


def test_no_accept_language_by_default() -> None:
    transport = FakeTransport(response(200, {"object": "usage"}))
    make_client(transport).usage.retrieve()
    assert all(name.lower() != "accept-language" for name in transport.last.headers)


def test_language_option_is_sent_as_accept_language() -> None:
    transport = FakeTransport(
        response(200, {"object": "usage"}),
        response(200, {"id": "sgr_1", "object": "signer"}),
        response(200, {"object": "usage"}),
    )
    client = make_client(transport, language="en")
    client.usage.retrieve()
    assert transport.last.headers["Accept-Language"] == "en"
    client.signers.decide_identity_match("sgr_1", decision="approve")
    assert transport.last.headers["Accept-Language"] == "en"
    client.usage.retrieve(headers={"accept-language": "ar"})
    sent = {k: v for k, v in transport.last.headers.items() if k.lower() == "accept-language"}
    assert sent == {"accept-language": "ar"}

    arabic = FakeTransport(response(200, {"object": "usage"}))
    make_client(arabic, language="ar").usage.retrieve()
    assert arabic.last.headers["Accept-Language"] == "ar"
    assert wthaiq.Client(TEST_KEY, language="en-GB").is_test_mode()

    async def run() -> None:
        async_transport = AsyncFakeTransport(response(200, {"object": "usage"}))
        await make_async_client(async_transport, language="en").usage.retrieve()
        assert async_transport.last.headers["Accept-Language"] == "en"

    asyncio.run(run())


def test_callable_http_client() -> None:
    seen: list[HttpRequest] = []

    def send(request: HttpRequest) -> HttpResponse:
        seen.append(request)
        return response(200, {"object": "api_root", "name": "wthaiq API"})

    client = wthaiq.Client(TEST_KEY, http_client=send)
    assert client.account.retrieve().name == "wthaiq API"
    assert seen[0].method == "GET"


def test_http_client_must_be_usable() -> None:
    with pytest.raises(InvalidArgumentError):
        wthaiq.Client(TEST_KEY, http_client=42)  # type: ignore[arg-type]
    with pytest.raises(InvalidArgumentError):
        wthaiq.Client(TEST_KEY, http_client=AsyncFakeTransport())  # type: ignore[arg-type]


def test_httpx_client_is_wrapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"object": "api_root", "livemode": False})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = wthaiq.Client(TEST_KEY, http_client=http)
        assert client.account.retrieve().livemode is False
        client.close()
        assert not http.is_closed, "a caller-supplied httpx.Client is not closed by the SDK"


def test_context_manager_closes_owned_transport() -> None:
    class Closable(FakeTransport):
        closed = False

        def close(self) -> None:
            self.closed = True

    transport = Closable()
    with wthaiq.Client(TEST_KEY, http_client=transport):
        pass
    assert transport.closed is False, "caller-supplied transports stay open"
    with wthaiq.Client(TEST_KEY) as client:
        assert client.base_url


def test_async_client_transport_selection() -> None:
    async def run() -> None:
        default = wthaiq.AsyncClient(TEST_KEY)
        assert isinstance(default._requestor.transport, AsyncHttpxTransport)
        await default.aclose()
        threaded = wthaiq.AsyncClient(TEST_KEY, http_client=FakeTransport(response(200, {})))
        assert isinstance(threaded._requestor.transport, ThreadedAsyncTransport)
        await threaded.account.retrieve()

        async def acall(request: HttpRequest) -> HttpResponse:
            return response(200, {"object": "usage"})

        async with wthaiq.AsyncClient(TEST_KEY, http_client=acall) as client:
            assert (await client.usage.retrieve()).object == "usage"

        def call(request: HttpRequest) -> HttpResponse:
            return response(200, {"object": "balance"})

        sync_callable = wthaiq.AsyncClient(TEST_KEY, http_client=call)
        assert (await sync_callable.balance.retrieve()).object == "balance"

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"object": "api_root"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = wthaiq.AsyncClient(TEST_KEY, http_client=http)
            assert (await client.account.retrieve()).object == "api_root"
            await client.aclose()
            assert not http.is_closed

        sync_httpx = httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
        )
        client = wthaiq.AsyncClient(TEST_KEY, http_client=sync_httpx)
        assert isinstance(client._requestor.transport, ThreadedAsyncTransport)
        await client.account.retrieve()
        sync_httpx.close()

    asyncio.run(run())


def test_async_client_without_httpx_uses_threads(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "httpx":
            raise ImportError("no httpx")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", fake_import)
    client = wthaiq.AsyncClient(TEST_KEY)
    assert isinstance(client._requestor.transport, ThreadedAsyncTransport)
    with pytest.raises(InvalidArgumentError):
        wthaiq.AsyncClient(TEST_KEY, http_client=42)  # type: ignore[arg-type]
