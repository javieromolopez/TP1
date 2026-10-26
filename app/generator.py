"""Diagram generator: one image call per click, no automatic retry (spec § Diagram generator)."""

import base64
from dataclasses import dataclass

from app import openrouter
from app.prompt_builder import build_image_prompt
from app.schemas import Topic

MODEL = "google/gemini-2.5-flash-image"
IMAGE_TIMEOUT_S = 60


@dataclass
class GeneratedImage:
    png: bytes
    model: str
    usage: openrouter.Usage


class NoImageError(Exception):
    """The image model answered with text and no image (a refusal or a safety block)."""

    def __init__(self, text: str):
        super().__init__(text)
        self.text = text


async def generate(topic: Topic, model: str = MODEL) -> GeneratedImage:
    body = {
        "model": model,
        "modalities": ["image", "text"],
        "messages": [{"role": "user", "content": build_image_prompt(topic)}],
    }
    # No retry_5xx: a second image attempt costs money; the student can press Generate again.
    result = await openrouter.chat(body, timeout=IMAGE_TIMEOUT_S)

    message = result.data["choices"][0]["message"]
    images = message.get("images") or []
    if not images:
        raise NoImageError(message.get("content") or "The image model returned no image.")

    header, _, encoded = images[0]["image_url"]["url"].partition(",")
    if not header.startswith("data:image/") or not encoded:
        raise NoImageError("The image model returned an image in an unexpected format.")
    return GeneratedImage(png=base64.b64decode(encoded), model=model, usage=result.usage)
