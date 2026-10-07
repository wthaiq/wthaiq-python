from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping
from typing import TYPE_CHECKING, Any

from .. import objects
from .._util import build_path
from ..pagination import AsyncPage, Page
from ._base import AsyncResource, SyncResource, split_params

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from ..types import TemplateCreateKwargs, TemplateListKwargs, TemplateRetrieveKwargs


class Templates(SyncResource):
    """Contract templates (``/templates``)."""

    def list(
        self, params: Mapping[str, Any] | None = None, /, **kwargs: Unpack[TemplateListKwargs]
    ) -> Page[objects.Template]:
        """One page of templates: your own with ``scope="mine"``, else the public catalogue."""
        query, options = split_params(params, kwargs)
        return self._page("/templates", objects.Template, query, options)

    def all(
        self, params: Mapping[str, Any] | None = None, /, **kwargs: Unpack[TemplateListKwargs]
    ) -> Iterator[objects.Template]:
        """Iterates over every template, requesting pages lazily."""
        query, options = split_params(params, kwargs)
        return self._iterate("/templates", objects.Template, query, options)

    def retrieve(
        self,
        id: str | int,
        params: Mapping[str, Any] | None = None,
        /,
        **kwargs: Unpack[TemplateRetrieveKwargs],
    ) -> objects.Template:
        """A template by ``tpl_123``, ``123`` or exact title; ``include="content"`` adds HTML."""
        query, options = split_params(params, kwargs)
        return self._request(
            "GET", build_path("/templates/{}", id), objects.Template, options, query
        )

    def create(
        self, params: Mapping[str, Any] | None = None, /, **kwargs: Unpack[TemplateCreateKwargs]
    ) -> objects.Template:
        """Creates a private template from HTML with ``{{key}}`` placeholders."""
        body, options = split_params(params, kwargs)
        return self._request("POST", "/templates", objects.Template, options, body)


class AsyncTemplates(AsyncResource):
    """Contract templates (``/templates``)."""

    async def list(
        self, params: Mapping[str, Any] | None = None, /, **kwargs: Unpack[TemplateListKwargs]
    ) -> AsyncPage[objects.Template]:
        """One page of templates: your own with ``scope="mine"``, else the public catalogue."""
        query, options = split_params(params, kwargs)
        return await self._page("/templates", objects.Template, query, options)

    def all(
        self, params: Mapping[str, Any] | None = None, /, **kwargs: Unpack[TemplateListKwargs]
    ) -> AsyncIterator[objects.Template]:
        """Iterates (``async for``) over every template, requesting pages lazily."""
        query, options = split_params(params, kwargs)
        return self._iterate("/templates", objects.Template, query, options)

    async def retrieve(
        self,
        id: str | int,
        params: Mapping[str, Any] | None = None,
        /,
        **kwargs: Unpack[TemplateRetrieveKwargs],
    ) -> objects.Template:
        """A template by ``tpl_123``, ``123`` or exact title; ``include="content"`` adds HTML."""
        query, options = split_params(params, kwargs)
        return await self._request(
            "GET", build_path("/templates/{}", id), objects.Template, options, query
        )

    async def create(
        self, params: Mapping[str, Any] | None = None, /, **kwargs: Unpack[TemplateCreateKwargs]
    ) -> objects.Template:
        """Creates a private template from HTML with ``{{key}}`` placeholders."""
        body, options = split_params(params, kwargs)
        return await self._request("POST", "/templates", objects.Template, options, body)
