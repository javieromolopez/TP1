"""Shared test helpers: a fake openrouter.chat that records requests and plays back replies."""

import base64
import io

import pytest
from PIL import Image

from app import openrouter


def png_bytes(color=(10, 120, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(buf, format="PNG")
    return buf.getvalue()


def data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode()


def reply(message: dict) -> dict:
    return {"choices": [{"message": message}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.0}}


@pytest.fixture
def fake_chat(monkeypatch):
    """Replace openrouter.chat. Append reply payloads to .replies; inspect .calls as (body, kwargs)."""

    class FakeChat:
        def __init__(self):
            self.replies: list[dict] = []
            self.calls: list[tuple[dict, dict]] = []

        async def __call__(self, body, **kwargs):
            self.calls.append((body, kwargs))
            payload = self.replies.pop(0)
            return openrouter.ChatResult(data=payload, usage=openrouter._usage(payload), latency_s=0.0)

    fake = FakeChat()
    monkeypatch.setattr(openrouter, "chat", fake)
    return fake
