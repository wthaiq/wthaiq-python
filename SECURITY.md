# Security Policy

## Reporting a vulnerability

Please report security issues privately by email to **support@wthaiq.com** with the subject
"Security: wthaiq-python". Do not open a public GitHub issue, pull request or discussion for a vulnerability.

Include a description of the issue, the affected version, steps to reproduce and, if possible, a proof of
concept. We acknowledge reports within three business days and keep you informed until the issue is fixed.

## Supported versions

| Version | Supported |
| ------- | --------- |
| 1.x     | Yes       |

## Handling secrets

- Keep secret keys (`sk_…`) and webhook secrets (`whsec_…`) on your server, for example in environment
  variables. Never commit them, log them, or send them to a browser.
- Use this library on the server only. Publishable keys (`pk_…`) are meant for the embeddable console and are
  limited to a few routes and origins.
- Rotate a key immediately from the developer portal at <https://developers.wthaiq.com> if it may have leaked.
- Always verify webhook signatures with `wthaiq.Webhook.construct_event()` on the raw request body before
  trusting a payload, and dedupe deliveries on `event.id`.
- The library verifies TLS certificates and never follows redirects. If you supply your own transport, keep
  certificate verification enabled and do not log the `Authorization` header.
