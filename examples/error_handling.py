"""How the library reports errors."""

from __future__ import annotations

from _client import client

import wthaiq

wt = client()

try:
    wt.signature_requests.create(
        source={"type": "template", "template_id": "tpl_0"},
        signers=[{"name": "Someone", "email": "not-an-email"}],
        send=False,
    )
except wthaiq.TooManySignersError as e:
    print("too many signers: at most", e.max_signers, "per request")
except wthaiq.ValidationError as e:
    print("validation:", e.code, e.param, e.field_errors, e.request_id)
except wthaiq.NotFoundError as e:
    print("not found:", e.code, e.request_id)
except wthaiq.PermissionDeniedError as e:
    if e.is_kyb_required():
        print("verify your company first:", e.verify_url)
    else:
        print("permission:", e.code, e.feature, e.upgrade_url)
except wthaiq.PaymentRequiredError as e:
    print("payment required:", e.code, e.upgrade_url)
except wthaiq.RateLimitError as e:
    print("rate limited:", e.code, e.retry_after)
except wthaiq.ApiConnectionError as e:
    print("network problem:", e)

result = wt.verifications.retrieve("WTQ-UNKNOWN")
print("verification found:", result.found, result.status)
