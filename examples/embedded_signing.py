"""Create a session on the default workflow (link channel) and open an embedded signing link.

WTHAIQ_API_KEY=sk_test_... python examples/embedded_signing.py tpl_123 you@example.com
"""

from __future__ import annotations

import sys

from _client import client

import wthaiq

template_id, signer_email = sys.argv[1], sys.argv[2]
wt = client()

session = wt.sessions.create(
    workflow_id="default",
    template_id=template_id,
    channel="link",  # nothing is sent; you deliver the link
    language="en",
    vendor_data="customer-42",
    signers=[{"name": "Noha Adel", "email": signer_email}],
)
print("session", session.id, "sign_url:", session.sign_url)

try:
    link = wt.signers.create_signing_session(session.signers[0].id)
    print("iframe url:", link.signing_url, "expires at", link.expires_at)
except wthaiq.PermissionDeniedError as e:
    print("embedded signing is not in your plan:", e.feature, e.upgrade_url)
finally:
    wt.signature_requests.cancel(session.id)
    print("session canceled")
