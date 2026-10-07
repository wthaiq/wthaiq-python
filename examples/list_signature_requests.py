"""List signature requests: one page, then every item with auto-pagination."""

from __future__ import annotations

import itertools

from _client import client

wt = client()

page = wt.signature_requests.list(limit=5)
print(f"first page: {len(page)} items, has_more={page.has_more}")

for sr in itertools.islice(wt.signature_requests.all(status="completed"), 20):
    print(sr.id, sr.status, sr.reference)
