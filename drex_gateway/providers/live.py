"""Live Drex provider implementing typed System One decision API at https://drex.nace.ai."""
from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import urlsplit

import httpx

from drex_gateway.config import GatewayConfig
from drex_gateway.errors import ProviderError, ProviderErrorKind, ValidationError
from drex_gateway.models import AnyQuestion
from drex_gateway.providers.base import BaseDecisionProvider, ProviderResponse

SAFE_RESPONSE_HEADERS = {
    "retry-after",
    "retry-after-ms",
    "x-request-id",
    "x-typesafe-request-id",
    "server-timing",
}


def _safe_headers(headers: httpx.Headers) -> dict[str, str]:
    return {
        k.lower(): v
        for k, v in headers.items()
        if k.lower() in SAFE_RESPONSE_HEADERS
        or k.lower().startswith(("ratelimit-", "x-ratelimit-", "rate-limit-", "x-rate-limit-"))
    }


class DrexProvider(BaseDecisionProvider):
    """Production adapter for Nace AI's Drex System One API."""

    def __init__(self, config: GatewayConfig | None = None):
        self.config = config or GatewayConfig.from_env()
        self._verify_base_url()

    @property
    def provider_name(self) -> str:
        return "Drex"

    @property
    def default_model(self) -> str:
        return self.config.model

    def _verify_base_url(self) -> None:
        parsed = urlsplit(self.config.base_url)
        if parsed.scheme != "https" or parsed.hostname != "drex.nace.ai":
            raise ProviderError(
                ProviderErrorKind.PROVIDER_AUTH,
                f"Invalid or unverified Drex API origin: {self.config.base_url}. Production Drex requires https://drex.nace.ai",
            )

    def _get_api_key(self) -> str:
        key = self.config.get_api_key()
        if not key:
            raise ProviderError(
                ProviderErrorKind.PROVIDER_AUTH,
                "Drex API credential is not configured or permissions are insecure (must be 0600 mode).",
            )
        return key

    async def list_models(self) -> list[dict[str, Any]]:
        """GET /v1/models (non-billed verification endpoint)."""
        key = self._get_api_key()
        headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
        url = f"{self.config.base_url.rstrip('/')}/v1/models"
        start_time = time.perf_counter()

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=headers)
        except httpx.TimeoutException as exc:
            raise ProviderError(ProviderErrorKind.PROVIDER_TIMEOUT, "Timeout connecting to Drex API") from exc
        except httpx.RequestError as exc:
            raise ProviderError(ProviderErrorKind.PROVIDER_UNAVAILABLE, f"Transport failure: {exc}") from exc
        finally:
            key = ""

        safe_hdrs = _safe_headers(resp.headers)
        if resp.status_code == 401 or resp.status_code == 403:
            raise ProviderError(ProviderErrorKind.PROVIDER_AUTH, "Drex authentication failed", status_code=resp.status_code, headers=safe_hdrs)
        if resp.status_code != 200:
            raise ProviderError(
                ProviderErrorKind.UNKNOWN_PROVIDER_FAILURE,
                f"Unexpected status from /v1/models: {resp.status_code}",
                status_code=resp.status_code,
                headers=safe_hdrs,
            )

        try:
            body = resp.json()
            models = body.get("models", [])
            return models
        except Exception as exc:
            raise ProviderError(ProviderErrorKind.INVALID_RESPONSE, "Failed to decode models JSON response") from exc

    async def decide(
        self,
        state: str,
        questions: dict[str, AnyQuestion],
        *,
        model: str | None = None,
        trace_id: str | None = None,
    ) -> ProviderResponse:
        """POST /v1/systemone typed decision call."""
        self.validate_request(state, questions)
        key = self._get_api_key()
        model_name = model or self.default_model

        # Serialize questions to dicts
        q_payload = {}
        for q_id, q in questions.items():
            if hasattr(q, "model_dump"):
                q_payload[q_id] = q.model_dump()
            elif isinstance(q, dict):
                q_payload[q_id] = q
            else:
                raise ValidationError(f"Invalid question object: {q}")

        payload = {
            "model": model_name,
            "state": state,
            "questions": q_payload,
        }

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if trace_id:
            headers["X-Trace-Id"] = trace_id

        url = f"{self.config.base_url.rstrip('/')}/v1/systemone"
        start_time = time.perf_counter()

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderError(ProviderErrorKind.PROVIDER_TIMEOUT, f"Drex decision timed out after {self.config.timeout_seconds}s") from exc
        except httpx.RequestError as exc:
            raise ProviderError(ProviderErrorKind.PROVIDER_UNAVAILABLE, f"Drex transport failure: {exc}") from exc
        finally:
            key = ""

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        safe_hdrs = _safe_headers(resp.headers)

        if resp.status_code != 200:
            self._handle_error_response(resp, safe_hdrs)

        try:
            body = resp.json()
        except Exception as exc:
            raise ProviderError(
                ProviderErrorKind.INVALID_RESPONSE,
                "Malformed JSON in Drex response",
                status_code=resp.status_code,
                headers=safe_hdrs,
            ) from exc

        self.validate_response(questions, body)

        answers = body.get("answers", {})
        usage = body.get("usage") or {}
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        eval_time = body.get("evaluation_time_ms")
        req_id = body.get("request_id") or safe_hdrs.get("x-request-id")
        resolved_model = body.get("model", model_name)

        return ProviderResponse(
            provider_name=self.provider_name,
            model=resolved_model,
            answers=answers,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            provider_latency_ms=float(eval_time) if eval_time is not None else None,
            request_id=req_id,
            headers=safe_hdrs,
        )

    def _handle_error_response(self, resp: httpx.Response, headers: dict[str, str]) -> None:
        status = resp.status_code
        retry_after = None
        if "retry-after-ms" in headers:
            try:
                retry_after = float(headers["retry-after-ms"]) / 1000.0
            except ValueError:
                pass
        elif "retry-after" in headers:
            try:
                retry_after = float(headers["retry-after"])
            except ValueError:
                pass

        err_type = "http_error"
        err_msg = ""
        try:
            err_data = resp.json()
            if isinstance(err_data, dict):
                error_obj = err_data.get("error") or err_data
                err_type = error_obj.get("type", err_type)
                err_msg = error_obj.get("message", "")
        except Exception:
            err_msg = resp.text[:200]

        if status in (401, 403):
            raise ProviderError(
                ProviderErrorKind.PROVIDER_AUTH,
                f"Authentication failed ({status}): {err_msg or err_type}",
                status_code=status,
                headers=headers,
            )
        elif status == 429:
            raise ProviderError(
                ProviderErrorKind.PROVIDER_RATE_LIMIT,
                f"Rate limit exceeded: {err_msg or err_type}",
                status_code=status,
                headers=headers,
                retry_after_seconds=retry_after,
            )
        elif status in (502, 503, 504):
            raise ProviderError(
                ProviderErrorKind.PROVIDER_UNAVAILABLE,
                f"Drex service unavailable ({status}): {err_msg or err_type}",
                status_code=status,
                headers=headers,
            )
        elif status in (400, 422):
            raise ProviderError(
                ProviderErrorKind.INVALID_REQUEST,
                f"Invalid request rejected by Drex ({status}): {err_msg or err_type}",
                status_code=status,
                headers=headers,
            )
        elif "model" in err_type.lower() or "not found" in err_msg.lower():
            raise ProviderError(
                ProviderErrorKind.MODEL_UNAVAILABLE,
                f"Requested model unavailable: {err_msg or err_type}",
                status_code=status,
                headers=headers,
            )
        else:
            raise ProviderError(
                ProviderErrorKind.UNKNOWN_PROVIDER_FAILURE,
                f"Drex API error ({status}): {err_msg or err_type}",
                status_code=status,
                headers=headers,
            )
