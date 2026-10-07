from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping
from typing import Any, TypeVar

from .._requestor import (
    OPTION_KEYS,
    AsyncRequestor,
    ParsedOptions,
    Requestor,
    Spec,
    split_params,
)
from ..objects import ResponseInfo, WthaiqObject
from ..pagination import AsyncPage, Page

T = TypeVar("T", bound=WthaiqObject)


def options_only(method: str, kwargs: Mapping[str, Any]) -> ParsedOptions:
    unknown = sorted(key for key in kwargs if key not in OPTION_KEYS)
    if unknown:
        raise TypeError(f"{method}() got unexpected keyword argument(s): {', '.join(unknown)}")
    return ParsedOptions.parse(kwargs)


def _spec(method: str, path: str, params: Mapping[str, Any] | None) -> Spec:
    if method == "POST":
        return Spec(method, path, json=params or {})
    return Spec(method, path, query=params or None)


class SyncResource:
    def __init__(self, requestor: Requestor) -> None:
        self._requestor = requestor

    def _request(
        self,
        method: str,
        path: str,
        cls: type[T],
        options: ParsedOptions,
        params: Mapping[str, Any] | None = None,
    ) -> T:
        body, info = self._requestor.request_json(_spec(method, path, params), options)
        return cls(body, last_response=info)

    def _raw(self, spec: Spec, options: ParsedOptions) -> tuple[dict[str, Any], ResponseInfo]:
        return self._requestor.request_json(spec, options)

    def _page(
        self, path: str, cls: type[T], params: Mapping[str, Any] | None, options: ParsedOptions
    ) -> Page[T]:
        def load(page_params: dict[str, Any]) -> Page[T]:
            body, info = self._requestor.request_json(_spec("GET", path, page_params), options)
            return Page(body, cls, page_params, info, load)

        return load(dict(params or {}))

    def _iterate(
        self, path: str, cls: type[T], params: Mapping[str, Any] | None, options: ParsedOptions
    ) -> Iterator[T]:
        yield from self._page(path, cls, params, options).auto_paging_iter()


class AsyncResource:
    def __init__(self, requestor: AsyncRequestor) -> None:
        self._requestor = requestor

    async def _request(
        self,
        method: str,
        path: str,
        cls: type[T],
        options: ParsedOptions,
        params: Mapping[str, Any] | None = None,
    ) -> T:
        body, info = await self._requestor.request_json(_spec(method, path, params), options)
        return cls(body, last_response=info)

    async def _raw(self, spec: Spec, options: ParsedOptions) -> tuple[dict[str, Any], ResponseInfo]:
        return await self._requestor.request_json(spec, options)

    async def _page(
        self, path: str, cls: type[T], params: Mapping[str, Any] | None, options: ParsedOptions
    ) -> AsyncPage[T]:
        async def load(page_params: dict[str, Any]) -> AsyncPage[T]:
            body, info = await self._requestor.request_json(
                _spec("GET", path, page_params), options
            )
            return AsyncPage(body, cls, page_params, info, load)

        return await load(dict(params or {}))

    async def _iterate(
        self, path: str, cls: type[T], params: Mapping[str, Any] | None, options: ParsedOptions
    ) -> AsyncIterator[T]:
        page = await self._page(path, cls, params, options)
        async for item in page.auto_paging_iter():
            yield item


__all__ = ["AsyncResource", "SyncResource", "options_only", "split_params"]
