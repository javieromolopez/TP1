"""Step 10 proof: the API server wires the pipeline, mocked at openrouter.chat
(spec behaviors 1, 2, 3, 9, 10, 11, 12, 13, plus the verdict staying in code)."""

import base64
import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import openrouter
from app.main import PERSON_HIDDEN, app, create_app
from app.schemas import TOPICS_PATH, TopicCatalogError, load_topics
from app.validator import CRITIQUE_UNAVAILABLE
from tests.conftest import data_url, png_bytes, reply

TOPICS = load_topics()
CIRCUIT = TOPICS["simple-circuit"]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    return TestClient(app)


def image_reply(png=None):
    return reply({"content": "", "images": [{"image_url": {"url": data_url(png or png_bytes())}}]})


def critique_reply(topic=CIRCUIT, **overrides):
    data = {
        "parts": [{"name": p, "status": "present", "note": ""} for p in topic.required_parts],
        "forbidden_found": [],
        "arrangement": [{"rule": r.id, "ok": True, "note": ""} for r in topic.arrangement_rules],
        "text_issues": [],
        "people_present": False,
        "narrative": "Every part is drawn and labeled.",
    }
    data.update(overrides)
    return reply({"content": json.dumps(data)})


def generate(client, topic_id="simple-circuit"):
    return client.post("/api/generate", json={"topic_id": topic_id})


def png_text_chunks(image_field: str) -> dict:
    header, _, encoded = image_field.partition(",")
    assert header == "data:image/png;base64"
    return Image.open(io.BytesIO(base64.b64decode(encoded))).text


# B1
def test_topics_lists_five_with_id_and_display_name_only(client):
    body = client.get("/api/topics").json()
    assert [t["id"] for t in body] == list(TOPICS)
    assert all(set(t) == {"id", "display_name"} for t in body)


# B2
def test_server_refuses_to_start_on_a_bad_catalog(tmp_path):
    raw = json.loads(TOPICS_PATH.read_text())
    raw["topics"][0]["required_parts"] = []
    bad = tmp_path / "topics.json"
    bad.write_text(json.dumps(raw))
    with pytest.raises(TopicCatalogError):
        create_app(topics_path=bad)


# B3
@pytest.mark.parametrize("payload", [{"topic_id": "volcano"}, {}, {"topic_id": None}])
def test_unknown_or_missing_topic_is_400_with_no_model_call(client, fake_chat, payload):
    response = client.post("/api/generate", json=payload)
    assert response.status_code == 400
    assert "plant-cell" in response.json()["detail"]
    assert fake_chat.calls == []


# B12
def test_no_key_health_reports_it_and_generate_is_503_without_a_call(monkeypatch, fake_chat):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    client = TestClient(app)
    assert client.get("/api/health").json() == {"ok": True, "key_present": False}
    response = generate(client)
    assert response.status_code == 503
    assert response.json()["detail"] == "OpenRouter key not configured"
    assert fake_chat.calls == []


def test_health_with_key(client):
    assert client.get("/api/health").json() == {"ok": True, "key_present": True}


# Full pipeline, B9
def test_generate_returns_stamped_image_critique_and_code_verdict(client, fake_chat):
    fake_chat.replies = [image_reply(), critique_reply()]
    response = generate(client)

    assert response.status_code == 200
    body = response.json()
    chunks = png_text_chunks(body["image"])
    assert chunks["ai_generated"] == "true"
    assert chunks["generator"] == "google/gemini-2.5-flash-image"
    assert chunks["topic"] == "simple-circuit"
    assert chunks["created"]
    assert [p["name"] for p in body["critique"]["parts"]] == CIRCUIT.required_parts
    assert body["critique_error"] is None
    assert body["verdict"] == "good"
    assert body["image_hidden_reason"] is None
    assert body["usage"]["image"]["model"] == "google/gemini-2.5-flash-image"
    assert body["arrangement_rules"] == [{"id": r.id, "text": r.text} for r in CIRCUIT.arrangement_rules]
    assert len(fake_chat.calls) == 2


def test_verdict_comes_from_code_not_the_model(client, fake_chat):
    """A critic that claims "verdict": "good" while reporting two missing parts still gets "poor"."""
    parts = [{"name": p, "status": "missing" if i < 2 else "present"} for i, p in enumerate(CIRCUIT.required_parts)]
    fake_chat.replies = [image_reply(), critique_reply(parts=parts, verdict="good")]
    assert generate(client).json()["verdict"] == "poor"


# B10
def test_image_refusal_is_502_with_model_text_and_no_critic_call(client, fake_chat):
    fake_chat.replies = [reply({"content": "I can't create that image."})]
    response = generate(client)
    assert response.status_code == 502
    assert "I can't create that image." in response.json()["detail"]
    assert len(fake_chat.calls) == 1


def test_image_provider_error_is_502(client, fake_chat):
    fake_chat.replies = [openrouter.OpenRouterError(402, "Insufficient credits")]
    response = generate(client)
    assert response.status_code == 502
    assert "Insufficient credits" in response.json()["detail"]
    assert len(fake_chat.calls) == 1


# B11
def test_person_in_image_withholds_the_image(client, fake_chat):
    fake_chat.replies = [image_reply(), critique_reply(people_present=True)]
    body = generate(client).json()
    assert body["image"] is None
    assert body["image_hidden_reason"] == PERSON_HIDDEN == "This diagram was hidden because it showed a person."


# B13
def test_image_timeout_is_504(client, fake_chat):
    fake_chat.replies = [openrouter.OpenRouterTimeout("slow")]
    response = generate(client)
    assert response.status_code == 504
    assert len(fake_chat.calls) == 1


def test_critique_timeout_still_returns_the_image(client, fake_chat):
    fake_chat.replies = [image_reply(), openrouter.OpenRouterTimeout("slow")]
    body = generate(client).json()
    assert body["image"].startswith("data:image/png;base64,")
    assert body["critique"] is None
    assert body["verdict"] is None
    assert body["critique_error"] == "critique timed out"


# B7 through the API: two bad critiques, image still shown
def test_two_invalid_critiques_return_the_image_and_an_error(client, fake_chat):
    fake_chat.replies = [image_reply(), reply({"content": "no json"}), reply({"content": "still none"})]
    body = generate(client).json()
    assert body["image"] is not None
    assert body["critique"] is None
    assert body["critique_error"] == CRITIQUE_UNAVAILABLE
    assert len(fake_chat.calls) == 3


def test_critic_provider_error_returns_the_image_and_an_error(client, fake_chat):
    fake_chat.replies = [image_reply(), openrouter.OpenRouterError(503, "upstream down")]
    body = generate(client).json()
    assert body["image"] is not None
    assert body["critique_error"] == CRITIQUE_UNAVAILABLE


@pytest.mark.parametrize("payload", [{}, {"topic_id": None}, {"topic_id": ""}])
def test_missing_topic_says_no_topic_selected(client, fake_chat, payload):
    """Review on #4/#5: a missing topic read 'Unknown topic None'."""
    detail = client.post("/api/generate", json=payload).json()["detail"]
    assert detail.startswith("No topic selected.")
    assert "None" not in detail


def test_unknown_topic_names_it(client, fake_chat):
    assert client.post("/api/generate", json={"topic_id": "volcano"}).json()["detail"].startswith(
        "Unknown topic 'volcano'."
    )
