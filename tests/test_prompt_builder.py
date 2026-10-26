"""Step 5 proof: the image prompt pins the style block, every label, and "No people" (spec behavior 4)."""

import pytest

from app.prompt_builder import build_image_prompt
from app.schemas import load_style_block, load_topics

TOPICS = load_topics()


@pytest.mark.parametrize("topic_id", list(TOPICS))
def test_prompt_has_style_block_labels_and_no_people(topic_id):
    topic = TOPICS[topic_id]
    prompt = build_image_prompt(topic)

    before, after = load_style_block().split("{labels}")
    assert before.strip() in prompt
    assert after.strip() in prompt
    for label in topic.labels:
        assert f'"{label}"' in prompt, label
    assert "No people" in prompt
    assert "{labels}" not in prompt


def test_style_block_is_the_spec_text():
    block = load_style_block()
    assert block.startswith("Flat-color 2D textbook illustration for a grade 5-10 science class.")
    assert "no gradients" in block
    assert block.endswith("No people, no faces, no hands.")
