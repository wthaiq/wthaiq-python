from __future__ import annotations

import asyncio

import pytest

import wthaiq
from wthaiq import objects

from .conftest import (
    AsyncFakeTransport,
    FakeTransport,
    make_async_client,
    make_client,
    page,
    query_of,
)


def sr(n: int) -> dict[str, object]:
    return {"id": f"sr_{n}", "object": "signature_request", "status": "completed"}


def three_pages() -> list[object]:
    return [
        page([sr(1), sr(2)], True, "sr_2"),
        page([sr(3), sr(4)], True, "sr_4"),
        page([sr(5)], False, None),
    ]


def test_list_returns_one_page() -> None:
    transport = FakeTransport(page([sr(1), sr(2)], True, "sr_2"))
    result = make_client(transport).signature_requests.list(status="completed", limit=2)
    assert isinstance(result, wthaiq.Page)
    assert [item.id for item in result] == ["sr_1", "sr_2"]
    assert len(result) == 2
    assert result[0].id == "sr_1"
    assert [item.id for item in result[0:1]] == ["sr_1"]
    assert result.has_more is True
    assert result.next_cursor == "sr_2"
    assert result.object == "list"
    assert result.has_next_page()
    assert result.next_page_params() == {
        "status": "completed",
        "limit": 2,
        "starting_after": "sr_2",
    }
    assert result.last_response is not None
    assert isinstance(result.data[0], objects.SignatureRequest)
    assert result.to_dict()["next_cursor"] == "sr_2"
    assert "2 items" in repr(result)
    assert len(transport.requests) == 1


def test_auto_paging_iter_follows_cursors() -> None:
    transport = FakeTransport(*three_pages())  # type: ignore[arg-type]
    client = make_client(transport)
    items = list(client.signature_requests.list(status="completed", limit=2).auto_paging_iter())
    assert [item.id for item in items] == ["sr_1", "sr_2", "sr_3", "sr_4", "sr_5"]
    assert [query_of(r) for r in transport.requests] == [
        [("status", "completed"), ("limit", "2")],
        [("status", "completed"), ("limit", "2"), ("starting_after", "sr_2")],
        [("status", "completed"), ("limit", "2"), ("starting_after", "sr_4")],
    ]


def test_webhook_endpoints_walk_every_page() -> None:
    def we(n: int) -> dict[str, object]:
        return {"id": f"we_{n}", "object": "webhook_endpoint", "url": "https://x/hook"}

    transport = FakeTransport(
        page([we(3), we(2)], True, "we_2"),
        page([we(1)], False, None),
    )
    client = make_client(transport)
    items = list(client.webhook_endpoints.all(limit=2))
    assert [item.id for item in items] == ["we_3", "we_2", "we_1"]
    assert all(isinstance(item, objects.WebhookEndpoint) for item in items)
    assert query_of(transport.requests[0]) == [("limit", "2")]
    assert query_of(transport.requests[1]) == [("limit", "2"), ("starting_after", "we_2")]

    one = client.webhook_endpoints.list(limit=1, starting_after="we_2")
    assert one.has_more is False
    assert query_of(transport.last) == [("limit", "1"), ("starting_after", "we_2")]


def test_all_is_lazy() -> None:
    transport = FakeTransport(*three_pages())  # type: ignore[arg-type]
    iterator = make_client(transport).signature_requests.all(limit=2)
    assert transport.requests == []
    assert next(iterator).id == "sr_1"
    assert len(transport.requests) == 1
    assert [item.id for item in iterator] == ["sr_2", "sr_3", "sr_4", "sr_5"]
    assert len(transport.requests) == 3


def test_stops_on_repeated_cursor() -> None:
    transport = FakeTransport(page([sr(1)], True, "sr_1"))
    items = list(make_client(transport).templates.all())
    assert len(items) == 2
    assert len(transport.requests) == 2


def test_stops_on_empty_page_and_missing_cursor() -> None:
    transport = FakeTransport(page([], True, "sr_9"))
    assert list(make_client(transport).events.all()) == []
    assert len(transport.requests) == 1
    transport = FakeTransport(page([sr(1)], True, None))
    assert len(list(make_client(transport).events.all())) == 1
    assert len(transport.requests) == 1


def test_next_page() -> None:
    transport = FakeTransport(*three_pages())  # type: ignore[arg-type]
    first = make_client(transport).sessions.list(limit=2)
    second = first.next_page()
    assert second is not None and second[0].id == "sr_3"
    third = second.next_page()
    assert third is not None and third.next_page() is None
    assert third.next_page_params() is None


def test_list_without_data_array() -> None:
    client = make_client(FakeTransport(page([])))
    client._requestor.transport = FakeTransport(
        wthaiq.HttpResponse(200, {}, b'{"object": "list", "data": null}')
    )
    with pytest.raises(wthaiq.UnexpectedResponseError):
        client.flows.list()


def test_async_pagination() -> None:
    async def run() -> None:
        transport = AsyncFakeTransport(*three_pages())  # type: ignore[arg-type]
        client = make_async_client(transport)
        first = await client.signature_requests.list(limit=2)
        assert isinstance(first, wthaiq.AsyncPage)
        assert [item.id async for item in first.auto_paging_iter()] == [
            "sr_1",
            "sr_2",
            "sr_3",
            "sr_4",
            "sr_5",
        ]

        transport = AsyncFakeTransport(*three_pages())  # type: ignore[arg-type]
        client = make_async_client(transport)
        iterator = client.signature_requests.all(limit=2)
        assert transport.requests == []
        ids = [item.id async for item in iterator]
        assert ids == ["sr_1", "sr_2", "sr_3", "sr_4", "sr_5"]
        assert len(transport.requests) == 3

        transport = AsyncFakeTransport(page([sr(1)], True, "sr_1"))
        repeated = [item async for item in make_async_client(transport).templates.all()]
        assert len(repeated) == 2

        transport = AsyncFakeTransport(*three_pages())  # type: ignore[arg-type]
        events_page = await make_async_client(transport).events.list()
        second = await events_page.next_page()
        assert second is not None and second.next_cursor == "sr_4"
        third = await second.next_page()
        assert third is not None and await third.next_page() is None

        for name in ("sessions", "webhook_endpoints", "flows", "events"):
            transport = AsyncFakeTransport(page([sr(1)]))
            resource = getattr(make_async_client(transport), name)
            assert len([item async for item in resource.all()]) == 1

    asyncio.run(run())


@pytest.mark.parametrize("name", ["sessions", "webhook_endpoints", "flows", "events", "templates"])
def test_all_exists_on_list_resources(name: str) -> None:
    transport = FakeTransport(page([sr(1)]))
    assert len(list(getattr(make_client(transport), name).all())) == 1
