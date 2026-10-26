"""The overall verdict, computed in code so the model never grades itself (spec § Verdict)."""

from typing import Literal

from app.schemas import Critique, Topic

Verdict = Literal["good", "needs_work", "poor"]


def verdict(topic: Topic, critique: Critique) -> Verdict:
    statuses = [p.status for p in critique.parts]

    bad = sum(1 for s in statuses if s in ("missing", "mislabeled"))
    if critique.forbidden_found or 2 * bad >= len(topic.required_parts):
        return "poor"

    if (
        all(s == "present" for s in statuses)
        and all(a.ok for a in critique.arrangement)
        and not critique.text_issues
    ):
        return "good"

    return "needs_work"
