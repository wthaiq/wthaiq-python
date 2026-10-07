"""HTTP transports.

The library talks to the network through a small transport interface so that the HTTP stack can be
replaced (proxies, custom TLS, logging, tests). A transport receives an :class:`HttpRequest` and
returns an :class:`HttpResponse` for every HTTP status; it raises
:class:`~wthaiq.error.ApiConnectionError` when no response could be obtained.

* :class:`UrllibTransport` (default for :class:`~wthaiq.Client`): standard library only.
* :class:`HttpxTransport` / :class:`AsyncHttpxTransport`: adapters for ``httpx`` (optional extra
  ``wthaiq[httpx]``). :class:`~wthaiq.AsyncClient` uses ``httpx`` when it is installed.
* :class:`ThreadedAsyncTransport`: runs a synchronous transport in a worker thread, so
  :class:`~wthaiq.AsyncClient` works without any third-party package.
"""

from __future__ import annotations

import asyncio
import http.client
import inspect
import socket
import ssl
import urllib.error
import urllib.request
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, Union, runtime_checkable

from .error import ApiConnectionError, InvalidArgumentError

if TYPE_CHECKING:
    import httpx

__all__ = [
    "AsyncHttpxTransport",
    "AsyncTransport",
    "HttpRequest",
    "HttpResponse",
    "HttpxTransport",
    "ThreadedAsyncTransport",
    "Transport",
    "UrllibTransport",
]


@dataclass(frozen=True)
class HttpRequest:
    """A request handed to a transport."""

    method: str
    url: str
    headers: Mapping[str, str]
    body: bytes | None = None
    timeout: float = 60.0
    """Seconds allowed for the request (per read or write for the standard-library transport)."""
    connect_timeout: float = 10.0
    """Seconds allowed to establish the connection (where the transport supports it)."""


@dataclass(frozen=True)
class HttpResponse:
    """A response returned by a transport. Header names are lower-case."""

    status_code: int
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes = b""


@runtime_checkable
class Transport(Protocol):
    """Synchronous transport."""

    def send(self, request: HttpRequest) -> HttpResponse: ...


@runtime_checkable
class AsyncTransport(Protocol):
    """Asynchronous transport."""

    async def send(self, request: HttpRequest) -> HttpResponse: ...


def _lower_headers(items: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in items:
        name = str(key).lower()
        out[name] = f"{out[name]}, {value}" if name in out else str(value)
    return out


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


class UrllibTransport:
    """Default synchronous transport, built on :mod:`urllib.request` (no third-party packages).

    TLS certificates are always verified. Redirects are never followed, so the API key is never
    sent to another host. Proxies come from the usual ``HTTPS_PROXY`` environment variables unless
    ``proxies`` is given. ``request.timeout`` applies to the connection and to each read.
    """

    def __init__(
        self,
        *,
        ssl_context: ssl.SSLContext | None = None,
        proxies: Mapping[str, str] | None = None,
    ) -> None:
        context = ssl_context if ssl_context is not None else ssl.create_default_context()
        handlers: list[urllib.request.BaseHandler] = [
            _NoRedirect(),
            urllib.request.HTTPSHandler(context=context),
        ]
        if proxies is not None:
            handlers.append(urllib.request.ProxyHandler(dict(proxies)))
        self._opener = urllib.request.build_opener(*handlers)

    def send(self, request: HttpRequest) -> HttpResponse:
        req = urllib.request.Request(
            request.url, data=request.body, headers=dict(request.headers), method=request.method
        )
        try:
            with self._opener.open(req, timeout=request.timeout) as resp:
                return HttpResponse(resp.status, _lower_headers(resp.headers.items()), resp.read())
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read()
            except (OSError, http.client.HTTPException):
                body = b""
            headers = _lower_headers(exc.headers.items()) if exc.headers is not None else {}
            return HttpResponse(exc.code, headers, body)
        except urllib.error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, (TimeoutError, socket.timeout)):
                raise _timeout(request) from exc
            raise _connection(request, str(reason)) from exc
        except TimeoutError as exc:
            raise _timeout(request) from exc
        except (OSError, http.client.HTTPException, ValueError) as exc:
            raise _connection(request, str(exc) or type(exc).__name__) from exc

    def close(self) -> None:
        """Nothing to release; present for symmetry with other transports."""


def _url_without_query(url: str) -> str:
    return url.split("?", 1)[0]


def _timeout(request: HttpRequest) -> ApiConnectionError:
    return ApiConnectionError(
        f"The request to the Wthaiq API timed out after {request.timeout:g} s "
        f"({request.method} {_url_without_query(request.url)}).",
        timed_out=True,
    )


def _connection(request: HttpRequest, detail: str) -> ApiConnectionError:
    return ApiConnectionError(
        f"Could not connect to the Wthaiq API ({_url_without_query(request.url)}): {detail}"
    )


class ThreadedAsyncTransport:
    """Runs a synchronous transport in a worker thread (:func:`asyncio.to_thread`)."""

    def __init__(self, transport: Transport | None = None) -> None:
        self._transport: Transport = transport if transport is not None else UrllibTransport()

    async def send(self, request: HttpRequest) -> HttpResponse:
        return await asyncio.to_thread(self._transport.send, request)

    async def aclose(self) -> None:
        close = getattr(self._transport, "close", None)
        if callable(close):
            close()


def _import_httpx() -> Any:
    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise InvalidArgumentError(
            "This transport needs the httpx package: pip install 'wthaiq[httpx]'."
        ) from exc
    return httpx


def _httpx_timeout(httpx_module: Any, request: HttpRequest) -> Any:
    return httpx_module.Timeout(request.timeout, connect=request.connect_timeout)


def _from_httpx(response: Any) -> HttpResponse:
    return HttpResponse(
        response.status_code, _lower_headers(response.headers.items()), response.content
    )


def _httpx_error(httpx_module: Any, request: HttpRequest, exc: Exception) -> ApiConnectionError:
    if isinstance(exc, httpx_module.TimeoutException):
        return _timeout(request)
    return _connection(request, str(exc) or type(exc).__name__)


class HttpxTransport:
    """Synchronous transport backed by an ``httpx.Client`` (created when not given)."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._httpx = _import_httpx()
        self._owned = client is None
        self._client: httpx.Client = client if client is not None else self._httpx.Client()

    def send(self, request: HttpRequest) -> HttpResponse:
        try:
            response = self._client.request(
                request.method,
                request.url,
                headers=dict(request.headers),
                content=request.body,
                timeout=_httpx_timeout(self._httpx, request),
                follow_redirects=False,
            )
        except self._httpx.HTTPError as exc:
            raise _httpx_error(self._httpx, request, exc) from exc
        return _from_httpx(response)

    def close(self) -> None:
        if self._owned:
            self._client.close()


class AsyncHttpxTransport:
    """Asynchronous transport backed by an ``httpx.AsyncClient`` (created when not given)."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._httpx = _import_httpx()
        self._owned = client is None
        self._client: httpx.AsyncClient = (
            client if client is not None else self._httpx.AsyncClient()
        )

    async def send(self, request: HttpRequest) -> HttpResponse:
        try:
            response = await self._client.request(
                request.method,
                request.url,
                headers=dict(request.headers),
                content=request.body,
                timeout=_httpx_timeout(self._httpx, request),
                follow_redirects=False,
            )
        except self._httpx.HTTPError as exc:
            raise _httpx_error(self._httpx, request, exc) from exc
        return _from_httpx(response)

    async def aclose(self) -> None:
        if self._owned:
            await self._client.aclose()


SyncHttpClient = Union[Transport, Callable[[HttpRequest], HttpResponse], "httpx.Client"]
"""What :class:`~wthaiq.Client` accepts as ``http_client``."""

AsyncHttpClient = Union[
    AsyncTransport,
    Transport,
    Callable[[HttpRequest], Awaitable[HttpResponse]],
    Callable[[HttpRequest], HttpResponse],
    "httpx.AsyncClient",
    "httpx.Client",
]
"""What :class:`~wthaiq.AsyncClient` accepts as ``http_client``."""


def _is_httpx(obj: object, name: str) -> bool:
    cls = type(obj)
    if cls.__module__.split(".")[0] != "httpx":
        return False
    httpx = _import_httpx()
    return isinstance(obj, getattr(httpx, name))


class _CallableTransport:
    def __init__(self, func: Callable[[HttpRequest], HttpResponse]) -> None:
        self._func = func

    def send(self, request: HttpRequest) -> HttpResponse:
        return self._func(request)


class _AsyncCallableTransport:
    def __init__(self, func: Callable[[HttpRequest], Awaitable[HttpResponse]]) -> None:
        self._func = func

    async def send(self, request: HttpRequest) -> HttpResponse:
        return await self._func(request)


def resolve_sync_transport(http_client: object | None) -> tuple[Transport, bool]:
    """Returns the transport and whether the client owns (and must close) it."""
    if http_client is None:
        return UrllibTransport(), True
    if _is_httpx(http_client, "Client"):
        return HttpxTransport(http_client), False  # type: ignore[arg-type]
    send = getattr(http_client, "send", None)
    if callable(send):
        if inspect.iscoroutinefunction(send):
            raise InvalidArgumentError("Client needs a synchronous transport; use AsyncClient.")
        return http_client, False  # type: ignore[return-value]
    if callable(http_client):
        return _CallableTransport(http_client), False
    raise InvalidArgumentError(
        "http_client must be a transport with send(request), a callable or an httpx.Client."
    )


def resolve_async_transport(http_client: object | None) -> tuple[AsyncTransport, bool]:
    """Returns the async transport and whether the client owns (and must close) it."""
    if http_client is None:
        try:
            import httpx  # noqa: F401
        except ImportError:
            return ThreadedAsyncTransport(), True
        return AsyncHttpxTransport(), True
    if _is_httpx(http_client, "AsyncClient"):
        return AsyncHttpxTransport(http_client), False  # type: ignore[arg-type]
    if _is_httpx(http_client, "Client"):
        return ThreadedAsyncTransport(HttpxTransport(http_client)), False  # type: ignore[arg-type]
    send = getattr(http_client, "send", None)
    if callable(send):
        if inspect.iscoroutinefunction(send):
            return http_client, False  # type: ignore[return-value]
        return ThreadedAsyncTransport(http_client), False  # type: ignore[arg-type]
    if callable(http_client):
        if inspect.iscoroutinefunction(http_client):
            return _AsyncCallableTransport(http_client), False
        return ThreadedAsyncTransport(_CallableTransport(http_client)), False
    raise InvalidArgumentError(
        "http_client must be an async transport, a transport, a callable or an httpx.AsyncClient."
    )
