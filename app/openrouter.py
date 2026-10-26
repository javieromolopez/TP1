"""The one place that talks to OpenRouter: key, timeouts, retry policy, run log (spec behaviors 12-14)."""

import asyncio
import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

URL = "https://openrouter.ai/api/v1/chat/completions"
RUNS_PATH = Path(__file__).resolve().parent.parent / "runs.jsonl"
RETRY_DELAY_S = 2.0
TRANSPORT: httpx.AsyncBaseTransport | None = None  # tests swap in httpx.MockTransport


class MissingKey(Exception):
    """OPENROUTER_API_KEY is not set. Raised before any network call."""


class OpenRouterTimeout(Exception):
    pass


class OpenRouterError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"OpenRouter {status}: {message}")
        self.status = status
        self.message = message


@dataclass
class Usage:
    prompt_tokens: int
    completion_tokens: int
    cost: float | None


@dataclass
class ChatResult:
    data: dict
    usage: Usage
    latency_s: float


def _usage(payload: dict) -> Usage:
    usage = payload.get("usage") or {}
    return Usage(
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        cost=usage.get("cost"),
    )


def _log_run(model: str, status: int | None, usage: Usage, latency_s: float, error: str | None) -> None:
    line = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": model,
        "status": status,
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "cost": usage.cost,
        "latency_s": round(latency_s, 3),
        "error": error,
    }
    with RUNS_PATH.open("a") as f:
        f.write(json.dumps(line) + "\n")


def _error_message(response: httpx.Response) -> str:
    try:
        return response.json()["error"]["message"]
    except (ValueError, KeyError, TypeError):
        return response.text[:300]


async def _post_once(client: httpx.AsyncClient, body: dict, timeout: float) -> ChatResult:
    model = body.get("model", "?")
    start = time.perf_counter()
    try:
        response = await client.post(URL, json=body, timeout=timeout)
    except httpx.TimeoutException as exc:
        _log_run(model, None, Usage(0, 0, None), time.perf_counter() - start, "timeout")
        raise OpenRouterTimeout(f"{model} did not answer within {timeout:g} s") from exc
    latency = time.perf_counter() - start

    if response.status_code != 200:
        message = _error_message(response)
        _log_run(model, response.status_code, Usage(0, 0, None), latency, message)
        raise OpenRouterError(response.status_code, message)

    payload = response.json()
    usage = _usage(payload)
    _log_run(model, 200, usage, latency, None)
    return ChatResult(data=payload, usage=usage, latency_s=latency)


async def chat(body: dict, *, timeout: float, retry_5xx: bool = False) -> ChatResult:
    """POST one chat completion. With retry_5xx, a 429 or 5xx is retried once after RETRY_DELAY_S."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise MissingKey("OpenRouter key not configured")

    body = {**body, "usage": {"include": True}}  # ask OpenRouter to report cost in usage
    headers = {"Authorization": f"Bearer {key}"}
    async with httpx.AsyncClient(headers=headers, transport=TRANSPORT) as client:
        try:
            return await _post_once(client, body, timeout)
        except OpenRouterError as err:
            if not (retry_5xx and (err.status == 429 or err.status >= 500)):
                raise
        await asyncio.sleep(RETRY_DELAY_S)
        return await _post_once(client, body, timeout)
