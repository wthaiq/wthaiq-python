"""Cursor pagination.

``list(...)`` returns one :class:`Page` (``data``, ``has_more``, ``next_cursor``);
``page.auto_paging_iter()`` and ``all(...)`` iterate over every item, requesting the next pages
lazily with ``starting_after``. Iteration stops when ``has_more`` is false, when a page is empty, or
when the API repeats a cursor (it ignores unknown cursors and would otherwise loop forever).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Mapping
from typing import Any, Generic, TypeVar, overload

from .error import UnexpectedResponseError
from .objects import ResponseInfo, WthaiqObject, convert

__all__ = ["AsyncPage", "Page"]

T = TypeVar("T", bound=WthaiqObject)


class _BasePage(Generic[T]):
    object = "list"

    def __init__(
        self,
        body: Mapping[str, Any],
        item_class: type[T],
        params: Mapping[str, Any],
        last_response: ResponseInfo | None,
    ) -> None:
        data = body.get("data")
        if not isinstance(data, list):
            raise UnexpectedResponseError(
                "The Wthaiq API returned a list without a data array.",
                status_code=last_response.status_code if last_response else None,
            )
        self.data: list[T] = [convert(item, item_class) for item in data]
        self.has_more: bool = body.get("has_more") is True
        cursor = body.get("next_cursor")
        self.next_cursor: str | None = cursor if isinstance(cursor, str) and cursor != "" else None
        self._params = dict(params)
        self._item_class = item_class
        self._last_response = last_response

    @property
    def last_response(self) -> ResponseInfo | None:
        """HTTP metadata of the call that returned this page."""
        return self._last_response

    def has_next_page(self) -> bool:
        return self.has_more and self.next_cursor is not None

    def next_page_params(self) -> dict[str, Any] | None:
        """Parameters of the next page, or ``None`` on the last page."""
        if not self.has_next_page():
            return None
        return {**self._params, "starting_after": self.next_cursor}

    def __iter__(self) -> Iterator[T]:
        """Iterates over the items of this page only. See ``auto_paging_iter()``."""
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    @overload
    def __getitem__(self, index: int) -> T: ...

    @overload
    def __getitem__(self, index: slice) -> list[T]: ...

    def __getitem__(self, index: int | slice) -> T | list[T]:
        return self.data[index]

    def __bool__(self) -> bool:
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "object": "list",
            "data": [item.to_dict() for item in self.data],
            "has_more": self.has_more,
            "next_cursor": self.next_cursor,
        }

    def __repr__(self) -> str:
        return (
            f"<{type(self).__name__} of {self._item_class.__name__}: {len(self.data)} items, "
            f"has_more={self.has_more}, next_cursor={self.next_cursor!r}>"
        )


class Page(_BasePage[T]):
    """One page of a list."""

    def __init__(
        self,
        body: Mapping[str, Any],
        item_class: type[T],
        params: Mapping[str, Any],
        last_response: ResponseInfo | None,
        loader: Callable[[dict[str, Any]], Page[T]],
    ) -> None:
        super().__init__(body, item_class, params, last_response)
        self._loader = loader

    def next_page(self) -> Page[T] | None:
        """Requests the next page, or returns ``None`` on the last page."""
        params = self.next_page_params()
        return None if params is None else self._loader(params)

    def auto_paging_iter(self) -> Iterator[T]:
        """Iterates over every item of this page and the following pages."""
        seen: set[str] = set()
        page: Page[T] | None = self
        while page is not None:
            yield from page.data
            cursor = page.next_cursor
            if not page.has_next_page() or cursor is None or not page.data or cursor in seen:
                return
            seen.add(cursor)
            page = page.next_page()


class AsyncPage(_BasePage[T]):
    """One page of a list, for :class:`~wthaiq.AsyncClient`."""

    def __init__(
        self,
        body: Mapping[str, Any],
        item_class: type[T],
        params: Mapping[str, Any],
        last_response: ResponseInfo | None,
        loader: Callable[[dict[str, Any]], Awaitable[AsyncPage[T]]],
    ) -> None:
        super().__init__(body, item_class, params, last_response)
        self._loader = loader

    async def next_page(self) -> AsyncPage[T] | None:
        """Requests the next page, or returns ``None`` on the last page."""
        params = self.next_page_params()
        return None if params is None else await self._loader(params)

    async def auto_paging_iter(self) -> AsyncIterator[T]:
        """Iterates (``async for``) over every item of this page and the following pages."""
        seen: set[str] = set()
        page: AsyncPage[T] | None = self
        while page is not None:
            for item in page.data:
                yield item
            cursor = page.next_cursor
            if not page.has_next_page() or cursor is None or not page.data or cursor in seen:
                return
            seen.add(cursor)
            page = await page.next_page()
