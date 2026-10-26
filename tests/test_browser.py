"""Step 11 proof: a real browser drives the page (spec behavior 15).

The real FastAPI app runs in a thread and serves the page and /api/topics. /api/generate is
held and answered by Playwright inside the browser (the "mocked backend"), so no key and no
credits are needed, and the test controls exactly when the answer arrives.

  python -m playwright install chromium      # once
  python -m pytest tests/test_browser.py -v  # HEADED=1 to watch it
"""

import os
import socket
import threading
import time

import pytest
import uvicorn
from playwright.sync_api import expect, sync_playwright

from app.main import app
from app.schemas import load_topics
from tests.conftest import data_url, png_bytes

PLANT = load_topics()["plant-cell"]


def critique_response(**overrides):
    body = {
        "image": data_url(png_bytes()),
        "image_hidden_reason": None,
        "critique": {
            "parts": [
                {"name": p, "status": "missing" if p == "vacuole" else "present", "note": f"note on {p}"}
                for p in PLANT.required_parts
            ],
            "forbidden_found": [],
            "arrangement": [
                {"rule": "A1", "ok": True, "note": ""},
                {"rule": "A2", "ok": True, "note": ""},
                {"rule": "A3", "ok": False, "note": "no vacuole to compare"},
            ],
            "text_issues": [{"label_text": "Mitochondrin", "problem": "misspelled"}],
            "people_present": False,
            "narrative": "Most parts are here, but the vacuole is missing.",
        },
        "critique_error": None,
        "verdict": "needs_work",
        "arrangement_rules": [{"id": r.id, "text": r.text} for r in PLANT.arrangement_rules],
        "usage": {"image": {"model": "google/gemini-2.5-flash-image", "prompt_tokens": 96,
                            "completion_tokens": 1290, "cost": 0.0387}},
    }
    body.update(overrides)
    return body


@pytest.fixture(scope="module")
def base_url():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def page(base_url):
    headed = bool(os.environ.get("HEADED"))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed, slow_mo=400 if headed else 0)
        page = browser.new_page()
        page.goto(base_url)
        yield page
        browser.close()


def hold_generate(page):
    """Intercept POST /api/generate and keep each request open until the test answers it."""
    held = []
    page.route("**/api/generate", lambda route: held.append(route))
    return held


def test_full_render_and_button_disables_while_running(page):
    requests = []
    page.on("request", lambda r: requests.append(r))
    held = hold_generate(page)

    expect(page.locator("#topics .topic-card")).to_have_count(5)
    page.locator(".topic-card", has_text="Water cycle").click()
    with page.expect_request("**/api/generate"):
        page.click("#generate")

    # While the request is open: disabled, loading state with elapsed seconds, and a second click does nothing.
    expect(page.locator("#generate")).to_be_disabled()
    expect(page.locator("#status")).to_contain_text(" s")
    expect(page.locator("#loading")).to_be_visible()
    page.evaluate("document.querySelector('#generate').click()")
    assert len(held) == 1
    assert held[0].request.post_data_json == {"topic_id": "water-cycle"}

    held[0].fulfill(json=critique_response())

    expect(page.locator("#generate")).to_be_enabled()
    expect(page.locator("#diagram")).to_have_attribute("src", data_url(png_bytes()))
    expect(page.locator("#caption")).to_have_text("AI-generated diagram")
    rows = page.locator("#checklist tr.part-row")
    expect(rows).to_have_count(len(PLANT.required_parts))
    expect(rows.filter(has_text="vacuole")).to_contain_text("Missing")
    expect(rows.filter(has_text="nucleus")).to_contain_text("Present")
    expect(page.locator("#score")).to_have_text("6 of 7 parts correct")
    expect(page.locator("#arrangement")).to_contain_text("A3 · The vacuole is the largest organelle.")
    expect(page.locator("#text-issues")).to_contain_text("Mitochondrin")
    expect(page.locator("#narrative")).to_have_text("Most parts are here, but the vacuole is missing.")
    expect(page.locator("#verdict")).to_have_text("Needs work")
    expect(page.locator("#status")).to_be_hidden()
    expect(page.locator("#loading")).to_be_hidden()

    generate_calls = [r for r in requests if r.url.endswith("/api/generate")]
    assert len(generate_calls) == 1
    assert not any("openrouter" in r.url for r in requests)


def test_needs_attention_filter_shows_only_problem_parts(page):
    held = hold_generate(page)
    with page.expect_request("**/api/generate"):
        page.click("#generate")
    held[0].fulfill(json=critique_response())

    rows = page.locator("#checklist tr.part-row")
    expect(rows).to_have_count(7)
    page.get_by_role("button", name="Needs attention").click()
    expect(rows.locator("visible=true")).to_have_count(1)
    expect(rows.locator("visible=true")).to_contain_text("vacuole")
    page.get_by_role("button", name="All parts").click()
    expect(rows.locator("visible=true")).to_have_count(7)


def test_needs_attention_with_nothing_wrong_says_so(page):
    held = hold_generate(page)
    with page.expect_request("**/api/generate"):
        page.click("#generate")
    clean = critique_response()
    for part in clean["critique"]["parts"]:
        part["status"] = "present"
    held[0].fulfill(json=clean)

    page.get_by_role("button", name="Needs attention").click()
    expect(page.locator("#no-problems")).to_have_text("No parts need attention: every part is present.")
    page.get_by_role("button", name="All parts").click()
    expect(page.locator("#no-problems")).to_be_hidden()


def test_topics_failing_to_load_shows_an_error(page):
    """Review on #4/#5: a failed /api/topics left the topic list empty with no message."""
    page.route("**/api/topics", lambda route: route.fulfill(status=500, body="boom"))
    page.reload()
    expect(page.locator("#error")).to_contain_text("Could not load the topics")
    expect(page.locator("#generate")).to_be_disabled()


def test_critique_error_still_shows_the_image(page):
    held = hold_generate(page)
    with page.expect_request("**/api/generate"):
        page.click("#generate")
    held[0].fulfill(json=critique_response(critique=None, verdict=None,
                                           critique_error="Critique unavailable — try again."))

    expect(page.locator("#diagram")).to_be_visible()
    expect(page.locator("#caption")).to_have_text("AI-generated diagram")
    expect(page.locator("#critique-error")).to_have_text("Critique unavailable — try again.")
    expect(page.locator("#checklist tr.part-row")).to_have_count(0)
    expect(page.locator("#verdict")).to_be_hidden()


def test_hidden_image_shows_the_notice_instead(page):
    held = hold_generate(page)
    with page.expect_request("**/api/generate"):
        page.click("#generate")
    held[0].fulfill(json=critique_response(image=None,
                                           image_hidden_reason="This diagram was hidden because it showed a person."))

    expect(page.locator("#diagram")).to_be_hidden()
    expect(page.locator("#hidden-notice")).to_have_text("This diagram was hidden because it showed a person.")


def test_server_error_is_shown_and_the_button_comes_back(page):
    held = hold_generate(page)
    with page.expect_request("**/api/generate"):
        page.click("#generate")
    held[0].fulfill(status=502, json={"detail": "The image model returned no image: refused"})

    expect(page.locator("#error")).to_contain_text("refused")
    expect(page.locator("#generate")).to_be_enabled()
    expect(page.locator("#result")).to_be_hidden()
