"""The asynchronous client."""

from __future__ import annotations

import asyncio
import os

import wthaiq


async def main() -> None:
    async with wthaiq.AsyncClient(
        os.environ.get("WTHAIQ_API_KEY"),
        base_url=os.environ.get("WTHAIQ_API_BASE", wthaiq.DEFAULT_BASE_URL),
    ) as wt:
        root, usage = await asyncio.gather(wt.account.retrieve(), wt.usage.retrieve())
        print(root.account.name, root.plan.id, usage.balance.amount, usage.balance.currency)

        count = 0
        async for sr in wt.signature_requests.all(limit=10):
            print(sr.id, sr.status)
            count += 1
            if count == 5:
                break


asyncio.run(main())
