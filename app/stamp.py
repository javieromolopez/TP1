"""Provenance stamp: PNG tEXt chunks on every generated image (spec § Provenance stamp)."""

import io

from PIL import Image
from PIL.PngImagePlugin import PngInfo

APP_NAME = "TP1 diagram loop"


def stamp(png: bytes, meta: dict) -> bytes:
    """Return the PNG re-encoded with ai_generated=true, app, and every key in meta as text chunks."""
    image = Image.open(io.BytesIO(png))
    info = PngInfo()
    info.add_text("ai_generated", "true")
    info.add_text("app", APP_NAME)
    for key, value in meta.items():
        info.add_text(key, str(value))

    out = io.BytesIO()
    image.save(out, format="PNG", pnginfo=info)
    return out.getvalue()
