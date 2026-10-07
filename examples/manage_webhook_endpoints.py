"""Create, update and delete a webhook endpoint."""

from __future__ import annotations

from _client import client

wt = client()

print("event types:", ", ".join(wt.webhook_endpoints.event_types()))

endpoint = wt.webhook_endpoints.create(
    url="https://example.com/hooks/wthaiq",
    enabled_events=["signature_request.completed", "signer.signed"],
)
print("created", endpoint.id, "store the secret now:", (endpoint.secret or "")[:10] + "...")

updated = wt.webhook_endpoints.update(endpoint.id, status="disabled")
print("status:", updated.status)

print("deliveries:", len(wt.webhook_endpoints.deliveries(endpoint.id)))
print("deleted:", wt.webhook_endpoints.delete(endpoint.id).deleted)
