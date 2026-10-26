"""FastAPI server: generate -> stamp -> critique -> validate -> verdict, one request per click (spec § API server).

  python -m uvicorn app.main:app      # then open http://localhost:8000
"""

import base64
import os
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import generator, openrouter, validator
from app.schemas import TOPICS_PATH, Critique, Topic, load_topics
from app.stamp import stamp
from app.verdict import verdict

load_dotenv()  # OPENROUTER_API_KEY from the git-ignored .env; an already-set variable wins

STATIC_DIR = Path(__file__).with_name("static")
PERSON_HIDDEN = "This diagram was hidden because it showed a person."


class GenerateRequest(BaseModel):
    topic_id: str | None = None


def key_present() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY"))


async def generate_image(topic: Topic) -> generator.GeneratedImage:
    """Run the one image call; turn its failures into the HTTP errors the UI shows."""
    try:
        return await generator.generate(topic)
    except generator.NoImageError as exc:
        raise HTTPException(502, f"The image model returned no image: {exc.text}") from exc
    except openrouter.OpenRouterTimeout as exc:
        raise HTTPException(504, "The image model timed out. Try again.") from exc
    except openrouter.OpenRouterError as exc:
        raise HTTPException(502, f"Image model error {exc.status}: {exc.message}") from exc


async def critique_image(topic: Topic, png: bytes) -> tuple[Critique | None, str | None]:
    """Return (critique, error). A failed critique never fails the request: the image is still shown."""
    try:
        return await validator.critique_with_retry(topic, png)
    except openrouter.OpenRouterTimeout:
        return None, "critique timed out"
    except openrouter.OpenRouterError:
        return None, validator.CRITIQUE_UNAVAILABLE


def create_app(topics_path: Path = TOPICS_PATH) -> FastAPI:
    topics = load_topics(topics_path)  # a bad catalog raises here, so the server never starts (behavior 2)
    api = FastAPI(title="TP1 diagram loop")

    @api.get("/api/health")
    def health():
        return {"ok": True, "key_present": key_present()}

    @api.get("/api/topics")
    def list_topics():
        return [{"id": t.id, "display_name": t.display_name} for t in topics.values()]

    @api.post("/api/generate")
    async def generate(request: GenerateRequest):
        topic = topics.get(request.topic_id) if request.topic_id else None
        if topic is None:
            raise HTTPException(400, f"Unknown topic {request.topic_id!r}. Valid ids: {', '.join(topics)}")
        if not key_present():
            raise HTTPException(503, "OpenRouter key not configured")

        image = await generate_image(topic)
        created = datetime.now(UTC).isoformat(timespec="seconds")
        png = stamp(image.png, {"generator": image.model, "topic": topic.id, "created": created})
        critique, critique_error = await critique_image(topic, png)

        # A diagram that shows a person is withheld; the critique still goes to the UI.
        hide = critique is not None and critique.people_present
        return {
            "image": None if hide else "data:image/png;base64," + base64.b64encode(png).decode(),
            "image_hidden_reason": PERSON_HIDDEN if hide else None,
            "critique": critique.model_dump() if critique else None,
            "critique_error": critique_error,
            "verdict": verdict(topic, critique) if critique else None,
            "arrangement_rules": [{"id": r.id, "text": r.text} for r in topic.arrangement_rules],
            "usage": {
                "image": {
                    "model": image.model,
                    "prompt_tokens": image.usage.prompt_tokens,
                    "completion_tokens": image.usage.completion_tokens,
                    "cost": image.usage.cost,
                }
            },
        }

    # Mounted last so the /api routes win; serves index.html at /.
    api.mount("/", StaticFiles(directory=STATIC_DIR, html=True, check_dir=False), name="static")
    return api


app = create_app()
