"""Step 7 proof: the generator's request and reply handling, with mocked HTTP (spec behaviors 4, 10)."""

import asyncio

import pytest

from app.generator import MODEL, NoImageError, generate
from app.prompt_builder import build_image_prompt
from app.schemas import load_topics
from tests.conftest import data_url, png_bytes, reply

TOPIC = load_topics()["plant-cell"]


def test_request_has_model_modalities_and_prompt(fake_chat):
    fake_chat.replies = [reply({"content": "", "images": [{"image_url": {"url": data_url(png_bytes())}}]})]
    asyncio.run(generate(TOPIC))

    (body, _), = fake_chat.calls
    assert body["model"] == MODEL == "google/gemini-2.5-flash-image"
    assert body["modalities"] == ["image", "text"]
    assert body["messages"] == [{"role": "user", "content": build_image_prompt(TOPIC)}]


def test_image_call_uses_60s_timeout_and_no_retry(fake_chat):
    fake_chat.replies = [reply({"content": "", "images": [{"image_url": {"url": data_url(png_bytes())}}]})]
    asyncio.run(generate(TOPIC))

    _, kwargs = fake_chat.calls[0]
    assert kwargs["timeout"] == 60
    assert not kwargs.get("retry_5xx", False)


def test_data_url_decodes_to_the_original_png(fake_chat):
    png = png_bytes((200, 30, 30))
    fake_chat.replies = [reply({"content": "", "images": [{"image_url": {"url": data_url(png)}}]})]
    image = asyncio.run(generate(TOPIC))

    assert image.png == png
    assert image.model == MODEL
    assert image.usage.prompt_tokens == 1


def test_text_without_image_raises_with_the_model_text(fake_chat):
    fake_chat.replies = [reply({"content": "I can't help with that request."})]
    with pytest.raises(NoImageError) as err:
        asyncio.run(generate(TOPIC))
    assert err.value.text == "I can't help with that request."
