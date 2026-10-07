from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping
from typing import TYPE_CHECKING, Any

from .. import objects
from .._util import build_path
from ..pagination import AsyncPage, Page
from ._base import AsyncResource, SyncResource, options_only, split_params

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from ..types import (
        RequestOptions,
        SessionCreateKwargs,
        SessionListKwargs,
        SigningSessionCreateKwargs,
    )


class Sessions(SyncResource):
    """Signature requests created from a workflow (``/sessions``)."""

    def create(
        self, params: Mapping[str, Any] | None = None, /, **kwargs: Unpack[SessionCreateKwargs]
    ) -> objects.Session:
        body, options = split_params(params, kwargs)
        return self._request("POST", "/sessions", objects.Session, options, body)

    def list(
        self, params: Mapping[str, Any] | None = None, /, **kwargs: Unpack[SessionListKwargs]
    ) -> Page[objects.Session]:
        query, options = split_params(params, kwargs)
        return self._page("/sessions", objects.Session, query, options)

    def all(
        self, params: Mapping[str, Any] | None = None, /, **kwargs: Unpack[SessionListKwargs]
    ) -> Iterator[objects.Session]:
        query, options = split_params(params, kwargs)
        return self._iterate("/sessions", objects.Session, query, options)

    def retrieve(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.Session:
        return self._request(
            "GET",
            build_path("/sessions/{}", id),
            objects.Session,
            options_only("retrieve", options),
        )


class AsyncSessions(AsyncResource):
    """Signature requests created from a workflow (``/sessions``)."""

    async def create(
        self, params: Mapping[str, Any] | None = None, /, **kwargs: Unpack[SessionCreateKwargs]
    ) -> objects.Session:
        body, options = split_params(params, kwargs)
        return await self._request("POST", "/sessions", objects.Session, options, body)

    async def list(
        self, params: Mapping[str, Any] | None = None, /, **kwargs: Unpack[SessionListKwargs]
    ) -> AsyncPage[objects.Session]:
        query, options = split_params(params, kwargs)
        return await self._page("/sessions", objects.Session, query, options)

    def all(
        self, params: Mapping[str, Any] | None = None, /, **kwargs: Unpack[SessionListKwargs]
    ) -> AsyncIterator[objects.Session]:
        query, options = split_params(params, kwargs)
        return self._iterate("/sessions", objects.Session, query, options)

    async def retrieve(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.Session:
        return await self._request(
            "GET",
            build_path("/sessions/{}", id),
            objects.Session,
            options_only("retrieve", options),
        )


class Signers(SyncResource):
    """Signers and embedded signing (``/signers``)."""

    def retrieve(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.Signer:
        return self._request(
            "GET", build_path("/signers/{}", id), objects.Signer, options_only("retrieve", options)
        )

    def create_signing_session(
        self,
        id: str,
        params: Mapping[str, Any] | None = None,
        /,
        **kwargs: Unpack[SigningSessionCreateKwargs],
    ) -> objects.SigningSession:
        """A short-lived (30 minutes) iframe or redirect signing link for one signer."""
        body, options = split_params(params, kwargs)
        return self._request(
            "POST",
            build_path("/signers/{}/signing_session", id),
            objects.SigningSession,
            options,
            body,
        )


class AsyncSigners(AsyncResource):
    """Signers and embedded signing (``/signers``)."""

    async def retrieve(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.Signer:
        return await self._request(
            "GET", build_path("/signers/{}", id), objects.Signer, options_only("retrieve", options)
        )

    async def create_signing_session(
        self,
        id: str,
        params: Mapping[str, Any] | None = None,
        /,
        **kwargs: Unpack[SigningSessionCreateKwargs],
    ) -> objects.SigningSession:
        """A short-lived (30 minutes) iframe or redirect signing link for one signer."""
        body, options = split_params(params, kwargs)
        return await self._request(
            "POST",
            build_path("/signers/{}/signing_session", id),
            objects.SigningSession,
            options,
            body,
        )
