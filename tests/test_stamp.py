"""Step 4 proof: every stamped PNG carries the provenance text chunks (spec behavior 9)."""

import io

from PIL import Image

from app.stamp import stamp

META = {
    "generator": "google/gemini-2.5-flash-image",
    "topic": "plant-cell",
    "created": "2026-10-25T21:30:00+00:00",
}


def png_bytes(color=(10, 120, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(buf, format="PNG")
    return buf.getvalue()


def test_stamp_writes_provenance_chunks():
    out = Image.open(io.BytesIO(stamp(png_bytes(), META)))
    assert out.format == "PNG"
    assert out.text["ai_generated"] == "true"
    assert out.text["generator"] == META["generator"]
    assert out.text["topic"] == META["topic"]
    assert out.text["created"] == META["created"]
    assert out.text["app"] == "TP1 diagram loop"


def test_stamp_keeps_pixels():
    original = png_bytes()
    stamped = stamp(original, META)
    assert Image.open(io.BytesIO(stamped)).tobytes() == Image.open(io.BytesIO(original)).tobytes()


def test_unstamped_png_has_no_provenance():
    """Guards against the test passing because Pillow adds these chunks on its own."""
    assert "ai_generated" not in Image.open(io.BytesIO(png_bytes())).text
