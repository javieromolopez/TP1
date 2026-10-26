"""The eval CLI's two modes, driven directly with the model calls faked. No network."""

import asyncio
import json

import pytest
from PIL import Image

from app import critic, generator, openrouter
from app.generator import GeneratedImage, NoImageError
from app.openrouter import OpenRouterTimeout, Usage
from app.schemas import load_topics
from eval import run_eval
from tests.conftest import png_bytes

TOPIC = next(iter(load_topics().values()))


def good_expected(extra=None):
    return {
        "topic": TOPIC.id,
        "kind": "good",
        "parts": {p: "present" for p in TOPIC.required_parts},
        "forbidden": [],
        "arrangement": {r.id: True for r in TOPIC.arrangement_rules},
        "text_issue": False,
        "flaw": None,
        "note": "",
    } | (extra or {})


def canned_json(**changes):
    reply = {
        "parts": [{"name": p, "status": "present", "note": ""} for p in TOPIC.required_parts],
        "forbidden_found": [],
        "arrangement": [{"rule": r.id, "ok": True, "note": ""} for r in TOPIC.arrangement_rules],
        "text_issues": [],
        "people_present": False,
        "narrative": "Looks right.",
    }
    return json.dumps(reply | changes)


@pytest.fixture
def images(tmp_path):
    folder = tmp_path / "images"
    folder.mkdir()
    (folder / "a_good.png").write_bytes(png_bytes((1, 2, 3)))
    (folder / "b_good.png").write_bytes(png_bytes((4, 5, 6)))
    expected = tmp_path / "expected.json"
    expected.write_text(json.dumps({"a_good.png": good_expected(), "b_good.png": good_expected()}))
    return folder, expected


def fake_critic(monkeypatch, replies):
    """Replace critic.critique; each call logs a runs line like the real client and pops a reply."""
    calls = []

    async def fake(topic, png, *, retry_note=None, model=critic.MODEL):
        calls.append({"model": model, "retry_note": retry_note, "runs_path": openrouter.RUNS_PATH})
        openrouter._log_run(model, 200, Usage(100, 10, 0.01), 0.1, None)
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(critic, "critique", fake)
    return calls


def table_rows(markdown, marker):
    return [line for line in markdown.splitlines() if line.startswith("|") and marker in line]


def test_critic_mode_counts_first_try_validity_and_one_retry(images, monkeypatch, tmp_path, capsys):
    folder, expected = images
    # a_good: invalid first, valid on the single retry. b_good: valid at once.
    calls = fake_critic(monkeypatch, ["not json at all", canned_json(), canned_json()])

    md = asyncio.run(
        run_eval.run_critic(model="test/model", repeats=1, images_dir=folder, expected_path=expected)
    )

    assert len(calls) == 3
    assert [c["retry_note"] is not None for c in calls] == [False, True, False]
    assert all(c["model"] == "test/model" for c in calls)
    assert calls[0]["runs_path"] == calls[1]["runs_path"] != calls[2]["runs_path"]  # fresh file per image
    assert calls[0]["runs_path"] != tmp_path / "runs.jsonl"  # never the project log
    assert openrouter.RUNS_PATH == tmp_path / "runs.jsonl"  # restored afterwards

    assert md in capsys.readouterr().out
    assert "test/model" in md.splitlines()[0]
    assert "| Image | Kind | Valid (1st try) | Part acc. | False flags | Flaw caught | Verdict | Tokens in/out | Cost |" in md
    rows = table_rows(md, ".png")
    assert len(rows) == 2
    assert rows[0].startswith("| a_good.png | good | no") and "200/20" in rows[0] and "$0.0200" in rows[0]
    assert rows[1].startswith("| b_good.png | good | yes") and "100/10" in rows[1]
    assert all("| good |" in r for r in rows)  # verdict column, computed in code

    assert "Valid rate: 100%" in md
    assert "Valid on first try: 50%" in md
    assert "False flags on good: 0" in md
    assert "Behavior 16: PASS" in md


def test_critic_mode_repeats_and_out_file(images, monkeypatch, tmp_path):
    folder, expected = images
    calls = fake_critic(monkeypatch, [canned_json()] * 4)
    out = tmp_path / "res" / "critic.md"

    md = asyncio.run(
        run_eval.run_critic(model="m/x", repeats=2, images_dir=folder, expected_path=expected, out=out)
    )

    assert len(calls) == 4
    assert len(table_rows(md, ".png")) == 4
    assert out.read_text().strip() == md.strip()


def test_critic_mode_failures_become_invalid_rows_and_flag_behavior_16(images, monkeypatch):
    folder, expected = images
    flawed = good_expected({"kind": "flawed", "flaw": {"kind": "part", "target": TOPIC.required_parts[0]}})
    expected.write_text(json.dumps({"a_good.png": good_expected(), "b_good.png": flawed}))
    # a_good: timeout (no retry on a transport failure). b_good: clean reply, flaw not caught.
    fake_critic(monkeypatch, [OpenRouterTimeout("slow"), canned_json()])

    md = asyncio.run(run_eval.run_critic(model="m/x", repeats=1, images_dir=folder, expected_path=expected))

    rows = table_rows(md, ".png")
    assert "no (invalid)" in rows[0]
    assert "| no |" in rows[1]  # planted flaw not caught
    assert "Valid rate: 50%" in md
    assert "Behavior 16: FAIL" in md


def fake_generator(monkeypatch, fail_on=()):
    calls = []

    async def fake(topic, model=generator.MODEL):
        calls.append((topic.id, model))
        if len(calls) in fail_on:
            raise NoImageError("I can't draw that")
        return GeneratedImage(png=png_bytes(), model=model, usage=Usage(1, 1, 0.04))

    monkeypatch.setattr(generator, "generate", fake)
    return calls


def test_generate_mode_writes_stamped_files_and_one_row_per_topic_run(monkeypatch, tmp_path):
    topics = list(load_topics())
    calls = fake_generator(monkeypatch)
    out_dir = tmp_path / "generated"

    md = asyncio.run(run_eval.run_generate(model="google/gemini-2.5-flash-image", runs=2, out_dir=out_dir))

    assert len(calls) == len(topics) * 2
    assert [c[0] for c in calls[:3]] == [topics[0], topics[0], topics[1]]  # catalog order, runs grouped
    folder = out_dir / "google_gemini-2.5-flash-image"
    names = sorted(p.name for p in folder.glob("*.png"))
    assert names == sorted(f"{t}-{n}.png" for t in topics for n in (1, 2))
    with Image.open(folder / f"{topics[0]}-1.png") as im:
        assert im.text["topic"] == topics[0]
        assert im.text["generator"] == "google/gemini-2.5-flash-image"
        assert im.text["ai_generated"] == "true"
        assert "created" in im.text

    assert "| Topic | Run | File | Cost | Latency s | Labels ok | Garbled text | Flat style |" in md
    rows = table_rows(md, "-1.png") + table_rows(md, "-2.png")
    assert len(rows) == len(topics) * 2
    assert rows[0].rstrip().endswith("|  |  |  |")  # hand-scored columns stay blank
    assert "Images: 10" in md and "Failures: 0" in md
    assert "Total cost: $0.4000" in md
    assert "Mean latency" in md


def test_generate_mode_records_failures_and_continues(monkeypatch, tmp_path):
    fake_generator(monkeypatch, fail_on=(2,))
    out_dir = tmp_path / "generated"

    md = asyncio.run(run_eval.run_generate(model="m/img", runs=1, out_dir=out_dir))

    topics = list(load_topics())
    assert len(list((out_dir / "m_img").glob("*.png"))) == len(topics) - 1
    assert "Failures: 1" in md
    assert f"Images: {len(topics) - 1}" in md
    failed = [line for line in md.splitlines() if "FAILED" in line]
    assert len(failed) == 1 and topics[1] in failed[0] and "can't draw" in failed[0]
