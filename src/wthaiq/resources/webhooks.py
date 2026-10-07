from __future__ import annotations

import builtins
from collections.abc import AsyncIterator, Iterator, Mapping
from typing import TYPE_CHECKING, Any

from .. import objects
from .._requestor import Spec
from .._util import build_path
from ..error import UnexpectedResponseError
from ..objects import ResponseInfo
from ..pagination import AsyncPage, Page
from ._base import AsyncResource, SyncResource, options_only, split_params

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from ..types import (
        EventListKwargs,
        EventRedeliverKwargs,
        ListKwargs,
        RequestOptions,
        WebhookEndpointCreateKwargs,
        WebhookEndpointListKwargs,
        WebhookEndpointUpdateKwargs,
    )

_EVENT_TYPES_SPEC = Spec("GET", "/webhook_endpoints/event_types")


def _event_types(body: Mapping[str, Any], info: ResponseInfo) -> builtins.list[str]:
    data = body.get("data")
    if not isinstance(data, builtins.list):
        raise UnexpectedResponseError(
            "Unexpected response for the event type list.", status_code=info.status_code
        )
    return [item for item in data if isinstance(item, str)]


class WebhookEndpoints(SyncResource):
    """Webhook endpoints (``/webhook_endpoints``, secret key)."""

    def create(
        self,
        params: Mapping[str, Any] | None = None,
        /,
        **kwargs: Unpack[WebhookEndpointCreateKwargs],
    ) -> objects.WebhookEndpoint:
        """Creates an endpoint. The response holds the signing ``secret`` once: store it."""
        body, options = split_params(params, kwargs)
        return self._request("POST", "/webhook_endpoints", objects.WebhookEndpoint, options, body)

    def retrieve(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.WebhookEndpoint:
        return self._request(
            "GET",
            build_path("/webhook_endpoints/{}", id),
            objects.WebhookEndpoint,
            options_only("retrieve", options),
        )

    def update(
        self,
        id: str,
        params: Mapping[str, Any] | None = None,
        /,
        **kwargs: Unpack[WebhookEndpointUpdateKwargs],
    ) -> objects.WebhookEndpoint:
        """Changes ``enabled_events`` or ``status``. The URL cannot be changed."""
        body, options = split_params(params, kwargs)
        return self._request(
            "POST", build_path("/webhook_endpoints/{}", id), objects.WebhookEndpoint, options, body
        )

    def delete(
        self, id: str, /, **options: Unpack[RequestOptions]
    ) -> objects.DeletedWebhookEndpoint:
        return self._request(
            "DELETE",
            build_path("/webhook_endpoints/{}", id),
            objects.DeletedWebhookEndpoint,
            options_only("delete", options),
        )

    def list(
        self,
        params: Mapping[str, Any] | None = None,
        /,
        **kwargs: Unpack[WebhookEndpointListKwargs],
    ) -> Page[objects.WebhookEndpoint]:
        query, options = split_params(params, kwargs)
        return self._page("/webhook_endpoints", objects.WebhookEndpoint, query, options)

    def all(
        self,
        params: Mapping[str, Any] | None = None,
        /,
        **kwargs: Unpack[WebhookEndpointListKwargs],
    ) -> Iterator[objects.WebhookEndpoint]:
        query, options = split_params(params, kwargs)
        return self._iterate("/webhook_endpoints", objects.WebhookEndpoint, query, options)

    def deliveries(
        self, id: str, /, **options: Unpack[RequestOptions]
    ) -> Page[objects.WebhookDelivery]:
        """The last 50 deliveries to the endpoint (single page)."""
        return self._page(
            build_path("/webhook_endpoints/{}/deliveries", id),
            objects.WebhookDelivery,
            None,
            options_only("deliveries", options),
        )

    def test(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.WebhookTestResult:
        """Sends a synthetic ``signature_request.completed`` event to the endpoint."""
        return self._request(
            "POST",
            build_path("/webhook_endpoints/{}/test", id),
            objects.WebhookTestResult,
            options_only("test", options),
        )

    def event_types(self, **options: Unpack[RequestOptions]) -> builtins.list[str]:
        """Every event type an endpoint can subscribe to."""
        body, info = self._raw(_EVENT_TYPES_SPEC, options_only("event_types", options))
        return _event_types(body, info)


class AsyncWebhookEndpoints(AsyncResource):
    """Webhook endpoints (``/webhook_endpoints``, secret key)."""

    async def create(
        self,
        params: Mapping[str, Any] | None = None,
        /,
        **kwargs: Unpack[WebhookEndpointCreateKwargs],
    ) -> objects.WebhookEndpoint:
        """Creates an endpoint. The response holds the signing ``secret`` once: store it."""
        body, options = split_params(params, kwargs)
        return await self._request(
            "POST", "/webhook_endpoints", objects.WebhookEndpoint, options, body
        )

    async def retrieve(
        self, id: str, /, **options: Unpack[RequestOptions]
    ) -> objects.WebhookEndpoint:
        return await self._request(
            "GET",
            build_path("/webhook_endpoints/{}", id),
            objects.WebhookEndpoint,
            options_only("retrieve", options),
        )

    async def update(
        self,
        id: str,
        params: Mapping[str, Any] | None = None,
        /,
        **kwargs: Unpack[WebhookEndpointUpdateKwargs],
    ) -> objects.WebhookEndpoint:
        """Changes ``enabled_events`` or ``status``. The URL cannot be changed."""
        body, options = split_params(params, kwargs)
        return await self._request(
            "POST", build_path("/webhook_endpoints/{}", id), objects.WebhookEndpoint, options, body
        )

    async def delete(
        self, id: str, /, **options: Unpack[RequestOptions]
    ) -> objects.DeletedWebhookEndpoint:
        return await self._request(
            "DELETE",
            build_path("/webhook_endpoints/{}", id),
            objects.DeletedWebhookEndpoint,
            options_only("delete", options),
        )

    async def list(
        self,
        params: Mapping[str, Any] | None = None,
        /,
        **kwargs: Unpack[WebhookEndpointListKwargs],
    ) -> AsyncPage[objects.WebhookEndpoint]:
        query, options = split_params(params, kwargs)
        return await self._page("/webhook_endpoints", objects.WebhookEndpoint, query, options)

    def all(
        self,
        params: Mapping[str, Any] | None = None,
        /,
        **kwargs: Unpack[WebhookEndpointListKwargs],
    ) -> AsyncIterator[objects.WebhookEndpoint]:
        query, options = split_params(params, kwargs)
        return self._iterate("/webhook_endpoints", objects.WebhookEndpoint, query, options)

    async def deliveries(
        self, id: str, /, **options: Unpack[RequestOptions]
    ) -> AsyncPage[objects.WebhookDelivery]:
        """The last 50 deliveries to the endpoint (single page)."""
        return await self._page(
            build_path("/webhook_endpoints/{}/deliveries", id),
            objects.WebhookDelivery,
            None,
            options_only("deliveries", options),
        )

    async def test(
        self, id: str, /, **options: Unpack[RequestOptions]
    ) -> objects.WebhookTestResult:
        """Sends a synthetic ``signature_request.completed`` event to the endpoint."""
        return await self._request(
            "POST",
            build_path("/webhook_endpoints/{}/test", id),
            objects.WebhookTestResult,
            options_only("test", options),
        )

    async def event_types(self, **options: Unpack[RequestOptions]) -> builtins.list[str]:
        """Every event type an endpoint can subscribe to."""
        body, info = await self._raw(_EVENT_TYPES_SPEC, options_only("event_types", options))
        return _event_types(body, info)


class Events(SyncResource):
    """Webhook events (``/events``, secret key)."""

    def list(
        self, params: Mapping[str, Any] | None = None, /, **kwargs: Unpack[EventListKwargs]
    ) -> Page[objects.Event]:
        query, options = split_params(params, kwargs)
        return self._page("/events", objects.Event, query, options)

    def all(
        self, params: Mapping[str, Any] | None = None, /, **kwargs: Unpack[EventListKwargs]
    ) -> Iterator[objects.Event]:
        query, options = split_params(params, kwargs)
        return self._iterate("/events", objects.Event, query, options)

    def retrieve(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.Event:
        return self._request(
            "GET", build_path("/events/{}", id), objects.Event, options_only("retrieve", options)
        )

    def redeliver(
        self,
        id: str,
        params: Mapping[str, Any] | None = None,
        /,
        **kwargs: Unpack[EventRedeliverKwargs],
    ) -> objects.EventRedelivery:
        """Delivers the event again, synchronously (``endpoint`` limits it to one endpoint)."""
        body, options = split_params(params, kwargs)
        return self._request(
            "POST", build_path("/events/{}/redeliver", id), objects.EventRedelivery, options, body
        )


class AsyncEvents(AsyncResource):
    """Webhook events (``/events``, secret key)."""

    async def list(
        self, params: Mapping[str, Any] | None = None, /, **kwargs: Unpack[EventListKwargs]
    ) -> AsyncPage[objects.Event]:
        query, options = split_params(params, kwargs)
        return await self._page("/events", objects.Event, query, options)

    def all(
        self, params: Mapping[str, Any] | None = None, /, **kwargs: Unpack[EventListKwargs]
    ) -> AsyncIterator[objects.Event]:
        query, options = split_params(params, kwargs)
        return self._iterate("/events", objects.Event, query, options)

    async def retrieve(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.Event:
        return await self._request(
            "GET", build_path("/events/{}", id), objects.Event, options_only("retrieve", options)
        )

    async def redeliver(
        self,
        id: str,
        params: Mapping[str, Any] | None = None,
        /,
        **kwargs: Unpack[EventRedeliverKwargs],
    ) -> objects.EventRedelivery:
        """Delivers the event again, synchronously (``endpoint`` limits it to one endpoint)."""
        body, options = split_params(params, kwargs)
        return await self._request(
            "POST", build_path("/events/{}/redeliver", id), objects.EventRedelivery, options, body
        )


class Flows(SyncResource):
    """Embeddable console flows (``/flows``, read-only)."""

    def list(
        self, params: Mapping[str, Any] | None = None, /, **kwargs: Unpack[ListKwargs]
    ) -> Page[objects.Flow]:
        query, options = split_params(params, kwargs)
        return self._page("/flows", objects.Flow, query, options)

    def all(
        self, params: Mapping[str, Any] | None = None, /, **kwargs: Unpack[ListKwargs]
    ) -> Iterator[objects.Flow]:
        query, options = split_params(params, kwargs)
        return self._iterate("/flows", objects.Flow, query, options)

    def retrieve(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.Flow:
        return self._request(
            "GET", build_path("/flows/{}", id), objects.Flow, options_only("retrieve", options)
        )


class AsyncFlows(AsyncResource):
    """Embeddable console flows (``/flows``, read-only)."""

    async def list(
        self, params: Mapping[str, Any] | None = None, /, **kwargs: Unpack[ListKwargs]
    ) -> AsyncPage[objects.Flow]:
        query, options = split_params(params, kwargs)
        return await self._page("/flows", objects.Flow, query, options)

    def all(
        self, params: Mapping[str, Any] | None = None, /, **kwargs: Unpack[ListKwargs]
    ) -> AsyncIterator[objects.Flow]:
        query, options = split_params(params, kwargs)
        return self._iterate("/flows", objects.Flow, query, options)

    async def retrieve(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.Flow:
        return await self._request(
            "GET", build_path("/flows/{}", id), objects.Flow, options_only("retrieve", options)
        )
