"""Scoring for the critic eval: pure functions, no I/O (plan step 13, spec behavior 16)."""

from app.schemas import Critique, Topic, load_topics
from app.verdict import verdict


def _folded(names) -> set[str]:
    return {n.casefold() for n in names}


def _false_flags(expected: dict, critique: Critique) -> int:
    """Complaints the critic made about a diagram we hand-checked as correct."""
    status = {p.name: p.status for p in critique.parts}
    flags = sum(1 for part, want in expected["parts"].items() if want == "present" and status.get(part) != "present")
    allowed = _folded(expected.get("forbidden", []))
    flags += sum(1 for name in critique.forbidden_found if name.casefold() not in allowed)
    flags += sum(1 for a in critique.arrangement if not a.ok and expected["arrangement"].get(a.rule) is True)
    if critique.text_issues and not expected.get("text_issue"):
        flags += 1
    return flags


def _flaw_caught(flaw: dict, critique: Critique) -> bool:
    kind, target = flaw["kind"], flaw["target"]
    if kind == "part":
        return any(p.name == target and p.status != "present" for p in critique.parts)
    if kind == "forbidden":
        return target.casefold() in _folded(critique.forbidden_found)
    if kind == "arrangement":
        return any(a.rule == target and not a.ok for a in critique.arrangement)
    if kind == "text":  # with a target, only an issue about that planted label counts
        if target is None:
            return bool(critique.text_issues)
        return any(target.casefold() in issue.label_text.casefold() for issue in critique.text_issues)
    return False


def score_critique(expected: dict, critique: Critique | None, topic: Topic | None = None) -> dict:
    """Compare one critic reply with the hand-written expected statuses for that image.

    The verdict needs the topic: pass it, or it is looked up in the catalog by expected["topic"]
    (verdict None if the id is not there).
    """
    flawed = expected["kind"] == "flawed"
    if critique is None:
        return {
            "valid": False,
            "part_accuracy": 0.0,
            "false_flags": 0,
            "flaw_caught": False if flawed else None,
            "verdict": None,
        }

    if topic is None:
        topic = load_topics().get(expected["topic"])
    status = {p.name: p.status for p in critique.parts}
    parts = expected["parts"]
    agree = sum(1 for part, want in parts.items() if (status.get(part) == "present") == (want == "present"))
    return {
        "valid": True,
        "part_accuracy": agree / len(parts) if parts else 0.0,
        "false_flags": 0 if flawed else _false_flags(expected, critique),
        "flaw_caught": _flaw_caught(expected["flaw"], critique) if flawed else None,
        "verdict": verdict(topic, critique) if topic is not None else None,
    }


def _rate(count: int, total: int) -> float:
    return count / total if total else 0.0


def summarize(rows: list[dict]) -> dict:
    """Aggregate scored rows. Each row carries the score keys plus kind, first_try_valid, cost, tokens."""
    good = [r for r in rows if r["kind"] == "good"]
    flawed = [r for r in rows if r["kind"] == "flawed"]
    false_flags = sum(r["false_flags"] for r in good)
    caught = sum(1 for r in flawed if r["flaw_caught"])
    return {
        "n_calls": len(rows),
        "valid_rate": _rate(sum(1 for r in rows if r["valid"]), len(rows)),
        "first_try_valid_rate": _rate(sum(1 for r in rows if r["first_try_valid"]), len(rows)),
        "mean_part_accuracy": _rate(sum(r["part_accuracy"] for r in rows), len(rows)),
        "false_flags_on_good": false_flags,
        "good_runs_with_false_flag": sum(1 for r in good if r["false_flags"] > 0),
        "flaws_caught": caught,
        "flawed_runs": len(flawed),
        "tokens_in": sum(r["prompt_tokens"] for r in rows),
        "tokens_out": sum(r["completion_tokens"] for r in rows),
        "total_cost": sum(r["cost"] for r in rows if r["cost"] is not None),
        "behavior_16": false_flags == 0 and caught >= 0.8 * len(flawed),
    }
