from __future__ import annotations

from typing import TYPE_CHECKING

from .. import objects
from ._base import AsyncResource, SyncResource, options_only

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from ..types import RequestOptions


class AccountResource(SyncResource):
    """``GET /`` — the account, plan and pricing of the API key."""

    def retrieve(self, **options: Unpack[RequestOptions]) -> objects.Account:
        return self._request("GET", "/", objects.Account, options_only("retrieve", options))


class UsageResource(SyncResource):
    """``GET /usage`` — balance, plan quota, pricing and request counts (secret key)."""

    def retrieve(self, **options: Unpack[RequestOptions]) -> objects.Usage:
        return self._request("GET", "/usage", objects.Usage, options_only("retrieve", options))


class BalanceResource(SyncResource):
    """``GET /balance`` — wallet balance and plan quota (secret key)."""

    def retrieve(self, **options: Unpack[RequestOptions]) -> objects.Balance:
        return self._request("GET", "/balance", objects.Balance, options_only("retrieve", options))


class AsyncAccountResource(AsyncResource):
    """``GET /`` — the account, plan and pricing of the API key."""

    async def retrieve(self, **options: Unpack[RequestOptions]) -> objects.Account:
        return await self._request("GET", "/", objects.Account, options_only("retrieve", options))


class AsyncUsageResource(AsyncResource):
    """``GET /usage`` — balance, plan quota, pricing and request counts (secret key)."""

    async def retrieve(self, **options: Unpack[RequestOptions]) -> objects.Usage:
        return await self._request(
            "GET", "/usage", objects.Usage, options_only("retrieve", options)
        )


class AsyncBalanceResource(AsyncResource):
    """``GET /balance`` — wallet balance and plan quota (secret key)."""

    async def retrieve(self, **options: Unpack[RequestOptions]) -> objects.Balance:
        return await self._request(
            "GET", "/balance", objects.Balance, options_only("retrieve", options)
        )
