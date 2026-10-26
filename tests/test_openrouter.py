"""Step 6 proof: the OpenRouter client's timeouts, retry policy, and runs.jsonl log (spec behaviors 12-14)."""

import asyncio
import json

import httpx
import pytest

from app import openrouter

BODY = {"model": "openai/gpt-4o", "messages": [{"role": "user", "content": "hi"}]}
OK_REPLY = {
    "choices": [{"message": {"content": "hello"}}],
    "usage": {"prompt_tokens": 12, "completion_tokens": 3, "cost": 0.0004},
}


@pytest.fixture
def server(monkeypatch, tmp_path):
    """Route the client to a fake server that plays back `replies` and records each request."""
    state = {"replies": [], "requests": []}

    def handler(request: httpx.Request) -> httpx.Response:
        state["requests"].append(request)
        reply = state["replies"].pop(0)
        if isinstance(reply, Exception):
            raise reply
        status, payload = reply
        return httpx.Response(status, json=payload)

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(openrouter, "TRANSPORT", httpx.MockTransport(handler))
    monkeypatch.setattr(openrouter, "RUNS_PATH", tmp_path / "runs.jsonl")
    monkeypatch.setattr(openrouter, "RETRY_DELAY_S", 0)
    return state


def call(**kwargs):
    return asyncio.run(openrouter.chat(BODY, **kwargs))


def test_posts_body_with_bearer_key_and_parses_usage(server):
    server["replies"] = [(200, OK_REPLY)]
    result = call(timeout=30)

    (request,) = server["requests"]
    assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer test-key"
    assert json.loads(request.content)["model"] == "openai/gpt-4o"
    assert result.data["choices"][0]["message"]["content"] == "hello"
    assert (result.usage.prompt_tokens, result.usage.completion_tokens, result.usage.cost) == (12, 3, 0.0004)


def test_missing_key_raises_without_network(server, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY")
    with pytest.raises(openrouter.MissingKey):
        call(timeout=30)
    assert server["requests"] == []


@pytest.mark.parametrize("seconds", [60, 30])
def test_timeout_is_passed_to_the_request(server, seconds):
    server["replies"] = [(200, OK_REPLY)]
    call(timeout=seconds)
    assert server["requests"][0].extensions["timeout"]["read"] == seconds


def test_timeout_raises_openrouter_timeout(server):
    server["replies"] = [httpx.ReadTimeout("slow")]
    with pytest.raises(openrouter.OpenRouterTimeout):
        call(timeout=60)


@pytest.mark.parametrize("status", [429, 503])
def test_retry_5xx_retries_once_then_succeeds(server, status):
    server["replies"] = [(status, {"error": {"message": "busy"}}), (200, OK_REPLY)]
    result = call(timeout=30, retry_5xx=True)
    assert len(server["requests"]) == 2
    assert result.usage.prompt_tokens == 12


def test_retry_5xx_gives_up_after_one_retry(server):
    server["replies"] = [(503, {"error": {"message": "down"}})] * 2
    with pytest.raises(openrouter.OpenRouterError) as err:
        call(timeout=30, retry_5xx=True)
    assert len(server["requests"]) == 2
    assert err.value.status == 503


def test_no_retry_without_flag(server):
    """The image call passes retry_5xx=False: a second attempt costs money (spec § Failure handling)."""
    server["replies"] = [(503, {"error": {"message": "down"}})]
    with pytest.raises(openrouter.OpenRouterError):
        call(timeout=60)
    assert len(server["requests"]) == 1


def test_client_errors_are_not_retried(server):
    server["replies"] = [(400, {"error": {"message": "bad image_url"}})]
    with pytest.raises(openrouter.OpenRouterError) as err:
        call(timeout=30, retry_5xx=True)
    assert len(server["requests"]) == 1
    assert "bad image_url" in err.value.message


def test_each_call_appends_one_runs_line(server):
    server["replies"] = [(200, OK_REPLY), (200, OK_REPLY)]
    call(timeout=30)
    call(timeout=30)

    lines = [json.loads(line) for line in openrouter.RUNS_PATH.read_text().splitlines()]
    assert len(lines) == 2
    assert lines[0]["model"] == "openai/gpt-4o"
    assert (lines[0]["prompt_tokens"], lines[0]["completion_tokens"], lines[0]["cost"]) == (12, 3, 0.0004)
    assert lines[0]["latency_s"] >= 0


def test_failed_attempts_are_logged_too(server):
    server["replies"] = [(503, {"error": {"message": "busy"}}), (200, OK_REPLY)]
    call(timeout=30, retry_5xx=True)
    lines = [json.loads(line) for line in openrouter.RUNS_PATH.read_text().splitlines()]
    assert [line["status"] for line in lines] == [503, 200]
