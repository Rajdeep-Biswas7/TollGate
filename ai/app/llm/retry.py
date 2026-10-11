"""POST with retries for transient provider errors, plus friendly error mapping."""
from __future__ import annotations

import asyncio

import httpx

from ..errors import LLMError

_RETRY_STATUS = {429, 500, 502, 503, 504, 529}


def _provider_message(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        err = body.get("error", body)
        if isinstance(err, dict):
            return str(err.get("message") or err)[:300]
        return str(err)[:300]
    except Exception:
        return (resp.text or "")[:300]


async def post_json(
    http: httpx.AsyncClient, url: str, *, headers: dict, body: dict, provider: str, model: str, attempts: int = 5
) -> dict:
    last: httpx.Response | None = None
    for attempt in range(attempts):
        try:
            resp = await http.post(url, headers=headers, json=body, timeout=httpx.Timeout(90.0, connect=10.0))
        except httpx.TimeoutException as exc:
            if attempt == attempts - 1:
                raise LLMError("timeout", f"{provider} took too long to respond. Try again.") from exc
            await asyncio.sleep(2.0 * (attempt + 1))
            continue
        except httpx.HTTPError as exc:
            raise LLMError("network", f"Could not reach {provider}: {type(exc).__name__}.") from exc

        if resp.status_code < 400:
            return resp.json()
        last = resp
        if resp.status_code in _RETRY_STATUS and attempt < attempts - 1:
            await asyncio.sleep(2.0 * (attempt + 1))
            continue
        break

    assert last is not None
    status, detail = last.status_code, _provider_message(last)
    if status in (401, 403) or "api key" in detail.lower():
        raise LLMError("bad_key", f"{provider} rejected the API key. Check it in ai/.env. ({detail})")
    if status == 404:
        raise LLMError("bad_model", f"Model '{model}' was not found for this {provider} key.")
    if status in (429, 529):
        raise LLMError("rate_limit", f"{provider} is rate limiting or overloaded for '{model}'. Wait a moment or switch model.")
    raise LLMError("provider_error", f"{provider} error {status}: {detail}")
