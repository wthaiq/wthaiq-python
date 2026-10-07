# Contributing

Thank you for helping improve the Wthaiq Python library.

## Development setup

```bash
git clone https://github.com/wthaiq/wthaiq-python.git
cd wthaiq-python
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e . -r requirements-dev.txt
```

The library supports Python 3.10 and later.

## Checks

Run all of these before opening a pull request:

```bash
ruff check .                 # lint
ruff format --check .        # formatting; ruff format . to apply
mypy                         # strict type checking of src/ and tests/
pytest                       # unit tests with fake transports (no network)
python -m build              # sdist and wheel
twine check dist/*           # package metadata
```

The integration suite talks to a real API in test mode and is skipped unless configured:

```bash
WTHAIQ_API_KEY=sk_test_... WTHAIQ_API_BASE=https://wthaiq.com/api/v1 pytest -m integration
```

It refuses live keys. It creates two drafts, a session and a test webhook endpoint and cancels or deletes
them at the end. Test mode allows 20 created requests per account per 24 hours.

## Guidelines

- Keep the public API backwards compatible within a major version.
- Add or update unit tests for every change (sync and async), and update `CHANGELOG.md` under "Unreleased".
- Follow the existing naming: resources mirror the API and request/response fields keep the API's names.
- No required runtime dependencies.
- Report security issues privately as described in [SECURITY.md](SECURITY.md).
