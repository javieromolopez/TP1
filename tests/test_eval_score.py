"""Pure scoring of a critic reply against the hand-written expected statuses (plan step 13)."""

import pytest

from app.schemas import ArrangementResult, Critique, Part, TextIssue, Topic
from eval.score import score_critique, summarize

TOPIC = Topic.model_validate(
    {
        "id": "cell",
        "display_name": "Animal cell",
        "required_parts": ["nucleus", "membrane", "mitochondrion", "cytoplasm"],
        "forbidden_parts": ["cell wall"],
        "arrangement_rules": [
            {"id": "A1", "text": "nucleus inside"},
            {"id": "A2", "text": "membrane outside"},
            {"id": "A3", "text": "mitochondria in cytoplasm"},
        ],
        "labels": ["nucleus", "membrane", "mitochondrion", "cytoplasm"],
    }
)

GOOD = {
    "topic": "cell",
    "kind": "good",
    "parts": {p: "present" for p in TOPIC.required_parts},
    "forbidden": [],
    "arrangement": {"A1": True, "A2": True, "A3": True},
    "text_issue": False,
    "flaw": None,
    "note": "",
}


def flawed(kind, target, **changes):
    expected = {**GOOD, "kind": "flawed", "flaw": {"kind": kind, "target": target}, **changes}
    return expected


def critique(statuses=None, forbidden=(), rules=None, issues=()):
    statuses = {p: "present" for p in TOPIC.required_parts} | (statuses or {})
    rules = {"A1": True, "A2": True, "A3": True} | (rules or {})
    return Critique(
        parts=[Part(name=n, status=s) for n, s in statuses.items()],
        forbidden_found=list(forbidden),
        arrangement=[ArrangementResult(rule=r, ok=ok) for r, ok in rules.items()],
        text_issues=[TextIssue(label_text=t, problem="misspelled") for t in issues],
        narrative="ok",
    )


def test_perfect_reply_on_good_image():
    s = score_critique(GOOD, critique(), TOPIC)
    assert s == {"valid": True, "part_accuracy": 1.0, "false_flags": 0, "flaw_caught": None, "verdict": "good"}


def test_none_critique_is_invalid_and_scores_zero():
    good = score_critique(GOOD, None)
    assert good == {"valid": False, "part_accuracy": 0.0, "false_flags": 0, "flaw_caught": None, "verdict": None}
    assert score_critique(flawed("part", "nucleus"), None)["flaw_caught"] is False


def test_part_accuracy_compares_present_vs_not_present():
    s = score_critique(GOOD, critique({"nucleus": "missing", "membrane": "unclear"}))
    assert s["part_accuracy"] == 0.5


def test_unclear_and_missing_both_count_as_not_present_when_expected_missing():
    expected = flawed("part", "nucleus", parts={**GOOD["parts"], "nucleus": "missing"})
    assert score_critique(expected, critique({"nucleus": "unclear"}))["part_accuracy"] == 1.0
    assert score_critique(expected, critique())["part_accuracy"] == 0.75


def test_false_flags_count_each_kind_on_a_good_image():
    c = critique(
        {"nucleus": "mislabeled", "cytoplasm": "unclear"},
        forbidden=["Cell Wall"],
        rules={"A2": False},
        issues=["Nucleas"],
    )
    assert score_critique(GOOD, c)["false_flags"] == 2 + 1 + 1 + 1


def test_forbidden_name_expected_drawn_is_not_a_false_flag():
    expected = {**GOOD, "forbidden": ["cell wall"]}
    assert score_critique(expected, critique(forbidden=["CELL WALL"]))["false_flags"] == 0


def test_rule_expected_false_is_not_a_false_flag_and_text_issue_expected_is_fine():
    expected = {**GOOD, "arrangement": {"A1": True, "A2": True, "A3": False}, "text_issue": True}
    c = critique(rules={"A3": False}, issues=["x"])
    assert score_critique(expected, c)["false_flags"] == 0


def test_text_issues_count_once_however_many():
    assert score_critique(GOOD, critique(issues=["a", "b", "c"]))["false_flags"] == 1


def test_false_flags_are_zero_for_flawed_images():
    c = critique({"nucleus": "missing"}, forbidden=["cell wall"], issues=["x"])
    assert score_critique(flawed("part", "nucleus"), c)["false_flags"] == 0


@pytest.mark.parametrize(
    ("expected", "reply", "caught"),
    [
        (flawed("part", "nucleus"), critique({"nucleus": "missing"}), True),
        (flawed("part", "nucleus"), critique({"nucleus": "mislabeled"}), True),
        (flawed("part", "nucleus"), critique({"nucleus": "unclear"}), True),
        (flawed("part", "nucleus"), critique({"membrane": "missing"}), False),
        (flawed("forbidden", "cell wall"), critique(forbidden=["Cell wall"]), True),
        (flawed("forbidden", "cell wall"), critique(), False),
        (flawed("arrangement", "A2"), critique(rules={"A2": False}), True),
        (flawed("arrangement", "A2"), critique(rules={"A1": False}), False),
        (flawed("text", None), critique(issues=["Mitochondrin"]), True),
        (flawed("text", None), critique(), False),
        # Review on #9: with a target, only an issue about that label counts.
        (flawed("text", "evaparashun"), critique(issues=["Evaparashun"]), True),
        (flawed("text", "evaparashun"), critique(issues=["Mitochondrin"]), False),
    ],
)
def test_flaw_caught_per_kind(expected, reply, caught):
    assert score_critique(expected, reply)["flaw_caught"] is caught


def test_verdict_is_computed_by_app_code():
    assert score_critique(GOOD, critique(forbidden=["cell wall"]), TOPIC)["verdict"] == "poor"
    assert score_critique(GOOD, critique({"nucleus": "unclear"}), TOPIC)["verdict"] == "needs_work"


def row(kind, *, valid=True, first=True, acc=1.0, flags=0, caught=None, cost=0.01, tin=100, tout=20):
    return {
        "kind": kind, "valid": valid, "first_try_valid": first, "part_accuracy": acc,
        "false_flags": flags, "flaw_caught": caught, "verdict": None, "cost": cost,
        "prompt_tokens": tin, "completion_tokens": tout,
    }  # fmt: skip


def test_summarize_totals_and_behavior_16_pass():
    rows = [row("good") for _ in range(5)] + [row("flawed", caught=True) for _ in range(4)]
    rows.append(row("flawed", caught=False, first=False, acc=0.5, cost=None))
    s = summarize(rows)
    assert s["n_calls"] == 10
    assert s["valid_rate"] == 1.0
    assert s["first_try_valid_rate"] == 0.9
    assert s["mean_part_accuracy"] == pytest.approx(0.95)
    assert s["false_flags_on_good"] == 0
    assert s["good_runs_with_false_flag"] == 0
    assert (s["flaws_caught"], s["flawed_runs"]) == (4, 5)
    assert (s["tokens_in"], s["tokens_out"]) == (1000, 200)
    assert s["total_cost"] == pytest.approx(0.09)
    assert s["behavior_16"] is True


def test_summarize_behavior_16_fails_on_a_false_flag_or_few_catches():
    flagged = [row("good", flags=2), row("good"), row("flawed", caught=True)]
    s = summarize(flagged)
    assert (s["false_flags_on_good"], s["good_runs_with_false_flag"]) == (2, 1)
    assert s["behavior_16"] is False

    weak = [row("good")] + [row("flawed", caught=True)] * 3 + [row("flawed", caught=False)] * 2
    assert summarize(weak)["behavior_16"] is False  # 3/5 < 0.8


def test_summarize_invalid_rows_lower_valid_rate_and_empty_is_safe():
    s = summarize([row("good"), row("good", valid=False, first=False, acc=0.0)])
    assert s["valid_rate"] == 0.5
    assert s["first_try_valid_rate"] == 0.5
    assert s["mean_part_accuracy"] == 0.5
    empty = summarize([])
    assert empty["n_calls"] == 0
    assert empty["valid_rate"] == 0.0
    assert empty["total_cost"] == 0


def test_topic_defaults_to_the_catalog_entry_for_expected_topic():
    from app.schemas import load_topics

    real = next(iter(load_topics().values()))
    statuses = [Part(name=p, status="present") for p in real.required_parts]
    rules = [ArrangementResult(rule=r.id, ok=True) for r in real.arrangement_rules]
    expected = {**GOOD, "topic": real.id, "parts": {p: "present" for p in real.required_parts},
                "arrangement": {r.id: True for r in real.arrangement_rules}}  # fmt: skip
    reply = Critique(parts=statuses, arrangement=rules, narrative="ok")
    assert score_critique(expected, reply)["verdict"] == "good"
    assert score_critique({**expected, "topic": "no-such-topic"}, reply)["verdict"] is None
