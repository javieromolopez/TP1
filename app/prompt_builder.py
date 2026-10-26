"""Builds the image-generation prompt from a topic (spec § Diagram generator, behavior 4)."""

from app.schemas import Topic, load_style_block

STYLE_BLOCK = load_style_block()


def build_image_prompt(topic: Topic) -> str:
    """Shared style block with the topic's exact label strings, each quoted, filled in."""
    labels = ", ".join(f'"{label}"' for label in topic.labels)
    return f"A labeled diagram of {topic.with_article}. " + STYLE_BLOCK.format(labels=labels)
