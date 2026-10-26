"""Step 3 proof: verdict() follows spec § "Verdict, computed in code" (behavior 8)."""

import pytest

from app.schemas import ArrangementResult, Critique, Part, TextIssue, load_topics
from app.verdict import verdict

TOPICS = load_topics()
PLANT = TOPICS["plant-cell"]  # 7 required parts: half or more = 4
CIRCUIT = TOPICS["simple-circuit"]  # 4 required parts: half or more = 2


def make_critique(topic, bad=None, forbidden=(), arrangement_ok=True, text_issues=()):
    """A critique where every part is present except those named in `bad` ({part: status})."""
    bad = bad or {}
    return Critique(
        parts=[Part(name=p, status=bad.get(p, "present")) for p in topic.required_parts],
        forbidden_found=list(forbidden),
        arrangement=[ArrangementResult(rule=r.id, ok=arrangement_ok) for r in topic.arrangement_rules],
        text_issues=[TextIssue(label_text=t, problem="misspelled") for t in text_issues],
        people_present=False,
        narrative="A short note for the student.",
    )


def first(topic, n, status="missing"):
    return {p: status for p in topic.required_parts[:n]}


@pytest.mark.parametrize(
    "topic, critique, expected",
    [
        # good: everything clean
        (PLANT, make_critique(PLANT), "good"),
        # good boundary: one flaw of each kind is enough to leave good
        (PLANT, make_critique(PLANT, bad=first(PLANT, 1, "unclear")), "needs_work"),
        (PLANT, make_critique(PLANT, arrangement_ok=False), "needs_work"),
        (PLANT, make_critique(PLANT, text_issues=["Mitochondrin"]), "needs_work"),
        # poor boundary on 7 parts: 3 bad is needs_work, 4 bad is poor
        (PLANT, make_critique(PLANT, bad=first(PLANT, 3)), "needs_work"),
        (PLANT, make_critique(PLANT, bad=first(PLANT, 4)), "poor"),
        # poor boundary on 4 parts: exactly half counts ("half or more")
        (CIRCUIT, make_critique(CIRCUIT, bad=first(CIRCUIT, 1)), "needs_work"),
        (CIRCUIT, make_critique(CIRCUIT, bad=first(CIRCUIT, 2, "mislabeled")), "poor"),
        # unclear parts do not count toward poor
        (CIRCUIT, make_critique(CIRCUIT, bad=first(CIRCUIT, 3, "unclear")), "needs_work"),
        # any forbidden part is poor, even with every required part present
        (TOPICS["animal-cell"], make_critique(TOPICS["animal-cell"], forbidden=["cell wall"]), "poor"),
    ],
    ids=[
        "all-clean-good",
        "one-unclear",
        "arrangement-fails",
        "one-text-issue",
        "plant-3-of-7-missing",
        "plant-4-of-7-missing",
        "circuit-1-of-4-missing",
        "circuit-2-of-4-mislabeled",
        "circuit-3-unclear",
        "forbidden-found",
    ],
)
def test_verdict(topic, critique, expected):
    assert verdict(topic, critique) == expected
