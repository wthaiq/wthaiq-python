from __future__ import annotations

import os
import platform
from collections.abc import Mapping
from types import TracebackType
from typing import Any
from urllib.parse import urlsplit

from ._requestor import AsyncRequestor, ClientConfig, Requestor, validate_api_key
from ._version import API_VERSION, VERSION
from .error import InvalidArgumentError
from .resources import (
    AccountResource,
    AsyncAccountResource,
    AsyncBalanceResource,
    AsyncDocuments,
    AsyncEvents,
    AsyncFlows,
    AsyncIdentityVerifications,
    AsyncSessions,
    AsyncSignatureRequests,
    AsyncSigners,
    AsyncTemplates,
    AsyncUsageResource,
    AsyncVerifications,
    AsyncWebhookEndpoints,
    BalanceResource,
    Documents,
    Events,
    Flows,
    IdentityVerifications,
    Sessions,
    SignatureRequests,
    Signers,
    Templates,
    UsageResource,
    Verifications,
    WebhookEndpoints,
)
from .retry import RetryPolicy
from .transport import (
    AsyncHttpClient,
    SyncHttpClient,
    resolve_async_transport,
    resolve_sync_transport,
)

DEFAULT_BASE_URL = "https://wthaiq.com/api/v1"
_LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")


def _base_url(value: object) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise InvalidArgumentError("base_url must be a non-empty URL.")
    url = value.strip().rstrip("/")
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme == "https" and host:
        return url
    local = host in _LOCAL_HOSTS or host.endswith((".localhost", ".test"))
    if parts.scheme == "http" and local:
        return url
    raise InvalidArgumentError(
        "base_url must be an https:// URL (plain http:// is accepted for localhost only)."
    )


def _user_agent(app_info: Mapping[str, str] | None) -> str:
    agent = f"wthaiq-python/{VERSION} Python/{platform.python_version()}"
    if app_info is None:
        return agent
    if not isinstance(app_info, Mapping) or not isinstance(app_info.get("name"), str):
        raise InvalidArgumentError("app_info must be a mapping with at least a 'name'.")
    app = app_info["name"].strip()
    if app_info.get("version"):
        app += f"/{app_info['version']}"
    if app_info.get("url"):
        app += f" ({app_info['url']})"
    return f"{agent} {app}"


def _config(
    api_key: str | None,
    base_url: str,
    timeout: float,
    connect_timeout: float,
    max_retries: int,
    api_version: str,
    app_info: Mapping[str, str] | None,
    retry_policy: RetryPolicy | None,
) -> ClientConfig:
    key = api_key if api_key is not None else os.environ.get("WTHAIQ_API_KEY")
    for name, value in (("timeout", timeout), ("connect_timeout", connect_timeout)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise InvalidArgumentError(f"{name} must be a positive number of seconds.")
    if isinstance(max_retries, bool) or not isinstance(max_retries, int) or max_retries < 0:
        raise InvalidArgumentError("max_retries must be a non-negative integer.")
    if not isinstance(api_version, str) or api_version == "":
        raise InvalidArgumentError("api_version must be a non-empty string.")
    return ClientConfig(
        api_key=validate_api_key(key),
        base_url=_base_url(base_url),
        timeout=float(timeout),
        connect_timeout=float(connect_timeout),
        max_retries=max_retries,
        api_version=api_version,
        user_agent=_user_agent(app_info),
        retry_policy=retry_policy if retry_policy is not None else RetryPolicy(),
    )


class _ClientBase:
    _config: ClientConfig

    @property
    def base_url(self) -> str:
        return self._config.base_url

    @property
    def api_version(self) -> str:
        return self._config.api_version

    @property
    def user_agent(self) -> str:
        return self._config.user_agent

    def is_test_mode(self) -> bool:
        """``True`` for test keys (``sk_test_`` / ``pk_test_``): free, no real messages."""
        return self._config.api_key.startswith(("sk_test_", "pk_test_"))

    def is_live_mode(self) -> bool:
        return not self.is_test_mode()

    def __repr__(self) -> str:
        mode = "test" if self.is_test_mode() else "live"
        return (
            f"<{type(self).__module__.split('.')[0]}.{type(self).__name__} {mode} {self.base_url}>"
        )


class Client(_ClientBase):
    """Synchronous client for the Wthaiq API.

    :param api_key: secret key (``sk_…`` or ``sk_test_…``). Defaults to ``WTHAIQ_API_KEY``.
    :param base_url: API base URL (default ``https://wthaiq.com/api/v1``).
    :param timeout: seconds allowed for each attempt (default 60).
    :param connect_timeout: seconds allowed to connect, when the transport supports it.
    :param max_retries: automatic retries of transient failures (default 2).
    :param api_version: value of the ``Wthaiq-Version`` header.
    :param app_info: ``{"name": …, "version": …, "url": …}`` appended to the User-Agent.
    :param http_client: a transport, a callable ``(HttpRequest) -> HttpResponse``
        or an ``httpx.Client``.
    :param retry_policy: backoff settings.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
        connect_timeout: float = 10.0,
        max_retries: int = 2,
        api_version: str = API_VERSION,
        app_info: Mapping[str, str] | None = None,
        http_client: SyncHttpClient | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._config = _config(
            api_key,
            base_url,
            timeout,
            connect_timeout,
            max_retries,
            api_version,
            app_info,
            retry_policy,
        )
        transport, self._owns_transport = resolve_sync_transport(http_client)
        requestor = Requestor(self._config, transport)
        self._requestor = requestor
        self.account = AccountResource(requestor)
        self.usage = UsageResource(requestor)
        self.balance = BalanceResource(requestor)
        self.templates = Templates(requestor)
        self.signature_requests = SignatureRequests(requestor)
        self.sessions = Sessions(requestor)
        self.signers = Signers(requestor)
        self.documents = Documents(requestor)
        self.identity_verifications = IdentityVerifications(requestor)
        self.verifications = Verifications(requestor)
        self.webhook_endpoints = WebhookEndpoints(requestor)
        self.events = Events(requestor)
        self.flows = Flows(requestor)

    def close(self) -> None:
        """Releases the HTTP transport when the client created it."""
        if self._owns_transport:
            close = getattr(self._requestor.transport, "close", None)
            if callable(close):
                close()

    def __enter__(self) -> Client:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class AsyncClient(_ClientBase):
    """Asynchronous client for the Wthaiq API (``await`` every call).

    Uses ``httpx.AsyncClient`` when ``httpx`` is installed (``pip install 'wthaiq[httpx]'``);
    otherwise the standard-library transport runs in a worker thread. Same options as
    :class:`Client`; ``http_client`` may also be an async transport or an ``httpx.AsyncClient``.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
        connect_timeout: float = 10.0,
        max_retries: int = 2,
        api_version: str = API_VERSION,
        app_info: Mapping[str, str] | None = None,
        http_client: AsyncHttpClient | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._config = _config(
            api_key,
            base_url,
            timeout,
            connect_timeout,
            max_retries,
            api_version,
            app_info,
            retry_policy,
        )
        transport, self._owns_transport = resolve_async_transport(http_client)
        requestor = AsyncRequestor(self._config, transport)
        self._requestor = requestor
        self.account = AsyncAccountResource(requestor)
        self.usage = AsyncUsageResource(requestor)
        self.balance = AsyncBalanceResource(requestor)
        self.templates = AsyncTemplates(requestor)
        self.signature_requests = AsyncSignatureRequests(requestor)
        self.sessions = AsyncSessions(requestor)
        self.signers = AsyncSigners(requestor)
        self.documents = AsyncDocuments(requestor)
        self.identity_verifications = AsyncIdentityVerifications(requestor)
        self.verifications = AsyncVerifications(requestor)
        self.webhook_endpoints = AsyncWebhookEndpoints(requestor)
        self.events = AsyncEvents(requestor)
        self.flows = AsyncFlows(requestor)

    async def aclose(self) -> None:
        """Releases the HTTP transport when the client created it."""
        if self._owns_transport:
            aclose: Any = getattr(self._requestor.transport, "aclose", None)
            if callable(aclose):
                await aclose()

    async def __aenter__(self) -> AsyncClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()
