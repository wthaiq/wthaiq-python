from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ._util import encode_json, encode_query, new_idempotency_key
from .error import (
    ApiConnectionError,
    ApiError,
    InvalidArgumentError,
    UnexpectedResponseError,
    error_from_response,
)
from .objects import ResponseInfo
from .retry import RetryPolicy
from .transport import AsyncTransport, HttpRequest, HttpResponse, Transport

OPTION_KEYS = ("idempotency_key", "timeout", "max_retries", "headers", "api_key")


def validate_api_key(api_key: object, *, name: str = "api_key") -> str:
    if not isinstance(api_key, str) or api_key == "":
        raise InvalidArgumentError(
            f"{name} is required: pass your secret key (sk_...) or set WTHAIQ_API_KEY."
        )
    if api_key != api_key.strip() or any(ch.isspace() for ch in api_key):
        raise InvalidArgumentError(f"{name} must not contain spaces or line breaks.")
    if not api_key.startswith(("sk_", "pk_")):
        raise InvalidArgumentError(
            f"{name} must be a Wthaiq API key starting with sk_ (secret) or pk_ (publishable)."
        )
    return api_key


@dataclass(frozen=True)
class ParsedOptions:
    idempotency_key: str | None = None
    timeout: float | None = None
    max_retries: int | None = None
    headers: Mapping[str, str] | None = None
    api_key: str | None = None

    @classmethod
    def parse(cls, raw: Mapping[str, Any]) -> ParsedOptions:
        key = raw.get("idempotency_key")
        if key is not None and (not isinstance(key, str) or key == "" or len(key) > 200):
            raise InvalidArgumentError(
                "idempotency_key must be a non-empty string of up to 200 characters."
            )
        timeout = raw.get("timeout")
        if timeout is not None and (
            isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0
        ):
            raise InvalidArgumentError("timeout must be a positive number of seconds.")
        retries = raw.get("max_retries")
        if retries is not None and (
            isinstance(retries, bool) or not isinstance(retries, int) or retries < 0
        ):
            raise InvalidArgumentError("max_retries must be a non-negative integer.")
        headers = raw.get("headers")
        if headers is not None:
            if not isinstance(headers, Mapping) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in headers.items()
            ):
                raise InvalidArgumentError("headers must be a mapping of strings to strings.")
            if any(k.lower() == "authorization" for k in headers):
                raise InvalidArgumentError(
                    "Set the Authorization header with api_key, not headers."
                )
        api_key = raw.get("api_key")
        if api_key is not None:
            validate_api_key(api_key)
        return cls(
            idempotency_key=key,
            timeout=float(timeout) if timeout is not None else None,
            max_retries=retries,
            headers=dict(headers) if headers is not None else None,
            api_key=api_key,
        )


def split_params(
    params: Mapping[str, Any] | None, kwargs: Mapping[str, Any]
) -> tuple[dict[str, Any], ParsedOptions]:
    """Separates request options from API parameters given as keyword arguments."""
    if params is not None and not isinstance(params, Mapping):
        raise InvalidArgumentError("params must be a mapping (dict) of API parameters.")
    options = {key: kwargs[key] for key in OPTION_KEYS if key in kwargs}
    merged = dict(params or {})
    merged.update({key: value for key, value in kwargs.items() if key not in OPTION_KEYS})
    return merged, ParsedOptions.parse(options)


@dataclass(frozen=True)
class ClientConfig:
    api_key: str
    base_url: str
    timeout: float
    connect_timeout: float
    max_retries: int
    api_version: str
    user_agent: str
    retry_policy: RetryPolicy


@dataclass(frozen=True)
class Spec:
    method: str
    path: str
    query: Mapping[str, Any] | None = None
    json: Mapping[str, Any] | None = None
    body: bytes | None = None
    content_type: str | None = None
    accept: str = "application/json"


def decode_object(response: HttpResponse) -> dict[str, Any]:
    text = response.body.decode("utf-8", errors="replace")
    try:
        decoded = json.loads(text) if text.strip() else None
    except ValueError:
        decoded = None
    if not isinstance(decoded, dict):
        raise UnexpectedResponseError(
            f"The Wthaiq API returned an unexpected response (HTTP {response.status_code}): "
            "expected a JSON object.",
            status_code=response.status_code,
            raw_body=text[:500],
        )
    return decoded


class _BaseRequestor:
    def __init__(self, config: ClientConfig) -> None:
        self.config = config

    def build(self, spec: Spec, options: ParsedOptions) -> tuple[HttpRequest, int]:
        config = self.config
        url = config.base_url + spec.path
        if spec.query:
            query = encode_query(spec.query)
            if query:
                url += ("&" if "?" in url else "?") + query
        headers: dict[str, str] = {
            "Authorization": f"Bearer {options.api_key or config.api_key}",
            "User-Agent": config.user_agent,
            "Wthaiq-Version": config.api_version,
            "Accept": spec.accept,
        }
        body: bytes | None = None
        if spec.body is not None:
            body = spec.body
            headers["Content-Type"] = spec.content_type or "application/octet-stream"
        elif spec.method == "POST":
            body = encode_json(spec.json)
            headers["Content-Type"] = "application/json"
        if spec.method == "POST":
            headers["Idempotency-Key"] = options.idempotency_key or new_idempotency_key()
        if options.headers:
            overridden = {name.lower() for name in options.headers}
            headers = {k: v for k, v in headers.items() if k.lower() not in overridden}
            headers.update(options.headers)
        request = HttpRequest(
            method=spec.method,
            url=url,
            headers=headers,
            body=body,
            timeout=options.timeout if options.timeout is not None else config.timeout,
            connect_timeout=config.connect_timeout,
        )
        retries = options.max_retries if options.max_retries is not None else config.max_retries
        return request, retries

    def _failure(self, response: HttpResponse) -> ApiError | None:
        if 200 <= response.status_code < 300:
            return None
        text = response.body.decode("utf-8", errors="replace")
        return error_from_response(response.status_code, response.headers, text)

    def _retry_decision(
        self, error: ApiError | ApiConnectionError, attempt: int, max_retries: int
    ) -> float | None:
        policy = self.config.retry_policy
        status = error.status_code if isinstance(error, ApiError) else None
        code = error.code if isinstance(error, ApiError) else None
        if attempt >= max_retries or not policy.should_retry(status, code):
            return None
        retry_after = error.get_header("retry-after") if isinstance(error, ApiError) else None
        return policy.delay(attempt, retry_after)


class Requestor(_BaseRequestor):
    def __init__(self, config: ClientConfig, transport: Transport) -> None:
        super().__init__(config)
        self.transport = transport

    def request(self, spec: Spec, options: ParsedOptions) -> HttpResponse:
        request, max_retries = self.build(spec, options)
        attempt = 0
        while True:
            error: ApiError | ApiConnectionError | None
            try:
                response = self.transport.send(request)
            except ApiConnectionError as exc:
                error = exc
            else:
                error = self._failure(response)
                if error is None:
                    return response
            delay = self._retry_decision(error, attempt, max_retries)
            if delay is None:
                raise error
            self.config.retry_policy.sleep(delay)
            attempt += 1

    def request_json(
        self, spec: Spec, options: ParsedOptions
    ) -> tuple[dict[str, Any], ResponseInfo]:
        response = self.request(spec, options)
        return decode_object(response), ResponseInfo(response.status_code, dict(response.headers))


class AsyncRequestor(_BaseRequestor):
    def __init__(self, config: ClientConfig, transport: AsyncTransport) -> None:
        super().__init__(config)
        self.transport = transport

    async def request(self, spec: Spec, options: ParsedOptions) -> HttpResponse:
        request, max_retries = self.build(spec, options)
        attempt = 0
        while True:
            error: ApiError | ApiConnectionError | None
            try:
                response = await self.transport.send(request)
            except ApiConnectionError as exc:
                error = exc
            else:
                error = self._failure(response)
                if error is None:
                    return response
            delay = self._retry_decision(error, attempt, max_retries)
            if delay is None:
                raise error
            await self.config.retry_policy.async_sleep(delay)
            attempt += 1

    async def request_json(
        self, spec: Spec, options: ParsedOptions
    ) -> tuple[dict[str, Any], ResponseInfo]:
        response = await self.request(spec, options)
        return decode_object(response), ResponseInfo(response.status_code, dict(response.headers))
