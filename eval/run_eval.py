"""Eval harness: runs the critic and generator comparisons against the real APIs (spec § Eval harness).

  python eval/run_eval.py critic   --model openai/gpt-4o --repeats 1 --images eval/images --expected eval/expected.json [--out FILE]
  python eval/run_eval.py generate --model google/gemini-2.5-flash-image --runs 3 --out-dir eval/generated

It reuses app.critic, app.validator and app.generator, so it measures exactly what ships. Each image's
model calls log to a throwaway runs file, which is where tokens and cost are read from.
"""

import argparse
import asyncio
import json
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from app import critic, generator, openrouter, validator
from app.schemas import Critique, Topic, load_topics
from app.stamp import stamp
from eval.score import score_critique, summarize

load_dotenv()

CRITIC_HEADER = "| Image | Kind | Valid (1st try) | Part acc. | False flags | Flaw caught | Verdict | Tokens in/out | Cost |"
GENERATE_HEADER = "| Topic | Run | File | Cost | Latency s | Labels ok | Garbled text | Flat style |"
CALL_FAILURES = (openrouter.OpenRouterTimeout, openrouter.OpenRouterError)


class _FreshRunsLog:
    """Point openrouter.RUNS_PATH at a throwaway file for a block, so each image's usage is isolated."""

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._saved = openrouter.RUNS_PATH
        openrouter.RUNS_PATH = Path(self._tmp.name) / "runs.jsonl"
        self.path = openrouter.RUNS_PATH
        return self

    def __exit__(self, *exc):
        openrouter.RUNS_PATH = self._saved
        self._tmp.cleanup()

    def lines(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]


def _usage_totals(lines: list[dict]) -> tuple[int, int, float | None]:
    costs = [ln["cost"] for ln in lines if ln.get("cost") is not None]
    return (
        sum(ln.get("prompt_tokens", 0) for ln in lines),
        sum(ln.get("completion_tokens", 0) for ln in lines),
        sum(costs) if costs else None,
    )


async def _critique_one(topic: Topic, png: bytes, model: str) -> tuple[Critique | None, bool]:
    """Returns (critique or None, valid on the first try). One retry, as validator.critique_with_retry."""
    try:
        raw = await critic.critique(topic, png, model=model)
        try:
            return validator.validate(topic, raw), True
        except validator.CritiqueInvalid as first:
            retry_note = first.reason
        raw = await critic.critique(topic, png, retry_note=retry_note, model=model)
        try:
            return validator.validate(topic, raw), False
        except validator.CritiqueInvalid:
            return None, False
    except CALL_FAILURES:
        return None, False


def _money(value: float | None) -> str:
    return "n/a" if value is None else f"${value:.4f}"


def _first_try_cell(row: dict) -> str:
    if row["first_try_valid"]:
        return "yes"
    return "no (retry ok)" if row["valid"] else "no (invalid)"


def _critic_row_line(row: dict) -> str:
    caught = "-" if row["flaw_caught"] is None else ("yes" if row["flaw_caught"] else "no")
    cells = [
        row["image"], row["kind"], _first_try_cell(row), f"{row['part_accuracy']:.2f}",
        str(row["false_flags"]), caught, row["verdict"] or "-",
        f"{row['prompt_tokens']}/{row['completion_tokens']}", _money(row["cost"]),
    ]  # fmt: skip
    return "| " + " | ".join(cells) + " |"


def _critic_markdown(model: str, repeats: int, rows: list[dict]) -> str:
    s = summarize(rows)
    behavior = "PASS" if s["behavior_16"] else "FAIL"
    return "\n".join(
        [
            f"## Critic eval: {model} (repeats: {repeats})",
            "",
            CRITIC_HEADER,
            "|" + "---|" * 9,
            *(_critic_row_line(r) for r in rows),
            "",
            f"- Calls scored: {s['n_calls']}",
            f"- Valid rate: {s['valid_rate']:.0%}",
            f"- Valid on first try: {s['first_try_valid_rate']:.0%}",
            f"- Mean part accuracy: {s['mean_part_accuracy']:.2f}",
            f"- False flags on good: {s['false_flags_on_good']} (in {s['good_runs_with_false_flag']} good runs)",
            f"- Flaws caught: {s['flaws_caught']}/{s['flawed_runs']}",
            f"- Tokens in/out: {s['tokens_in']}/{s['tokens_out']}",
            f"- Total cost: {_money(s['total_cost'])}",
            f"- Behavior 16: {behavior}",
        ]
    )


async def run_critic(
    *,
    model: str,
    repeats: int,
    images_dir: Path,
    expected_path: Path,
    out: Path | None = None,
) -> str:
    expected = json.loads(Path(expected_path).read_text())
    topics = load_topics()
    rows: list[dict] = []
    for name in sorted(expected):
        meta = expected[name]
        topic = topics[meta["topic"]]
        png = (Path(images_dir) / name).read_bytes()
        for _ in range(repeats):
            with _FreshRunsLog() as log:
                critique, first_try_valid = await _critique_one(topic, png, model)
                tokens_in, tokens_out, cost = _usage_totals(log.lines())
            row = score_critique(meta, critique, topic)
            row["image"], row["kind"] = name, meta["kind"]
            row["first_try_valid"] = first_try_valid
            row["prompt_tokens"], row["completion_tokens"], row["cost"] = tokens_in, tokens_out, cost
            rows.append(row)

    markdown = _critic_markdown(model, repeats, rows)
    print(markdown)
    if out is not None:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(markdown + "\n")
    return markdown


async def run_generate(*, model: str, runs: int, out_dir: Path) -> str:
    folder = Path(out_dir) / model.replace("/", "_")
    folder.mkdir(parents=True, exist_ok=True)
    table: list[str] = []
    images = failures = 0
    cost_total = 0.0
    latencies: list[float] = []

    for topic in load_topics().values():
        for n in range(1, runs + 1):
            filename = f"{topic.id}-{n}.png"
            started = time.perf_counter()
            with _FreshRunsLog() as log:
                try:
                    result = await generator.generate(topic, model=model)
                    error = None
                except (*CALL_FAILURES, generator.NoImageError) as exc:
                    result, error = None, str(getattr(exc, "text", exc))
                logged = [ln["latency_s"] for ln in log.lines() if ln.get("latency_s") is not None]
            latency = sum(logged) if logged else time.perf_counter() - started
            latencies.append(latency)

            if result is None:
                failures += 1
                table.append(f"| {topic.id} | {n} | FAILED: {error} | - | {latency:.1f} |  |  |  |")
                continue
            meta = {"generator": model, "topic": topic.id, "created": datetime.now(UTC).isoformat(timespec="seconds")}
            (folder / filename).write_bytes(stamp(result.png, meta))
            images += 1
            cost_total += result.usage.cost or 0.0
            table.append(
                f"| {topic.id} | {n} | {folder / filename} | {_money(result.usage.cost)} | {latency:.1f} |  |  |  |"
            )

    mean_latency = sum(latencies) / len(latencies) if latencies else 0.0
    markdown = "\n".join(
        [
            f"## Generator eval: {model} (runs per topic: {runs})",
            "",
            GENERATE_HEADER,
            "|" + "---|" * 8,
            *table,
            "",
            f"- Images: {images}",
            f"- Failures: {failures}",
            f"- Total cost: {_money(cost_total)}",
            f"- Mean latency: {mean_latency:.1f} s",
        ]
    )
    print(markdown)
    return markdown


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the critic or generator eval against OpenRouter.")
    modes = parser.add_subparsers(dest="mode", required=True)

    c = modes.add_parser("critic", help="score a critic model on eval/images against eval/expected.json")
    c.add_argument("--model", default=critic.MODEL)
    c.add_argument("--repeats", type=int, default=1)
    c.add_argument("--images", type=Path, default=ROOT / "eval" / "images")
    c.add_argument("--expected", type=Path, default=ROOT / "eval" / "expected.json")
    c.add_argument("--out", type=Path, default=None, help="also write the markdown to this file")

    g = modes.add_parser("generate", help="generate every topic several times for hand-scoring")
    g.add_argument("--model", default=generator.MODEL)
    g.add_argument("--runs", type=int, default=3)
    g.add_argument("--out-dir", type=Path, default=ROOT / "eval" / "generated")
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        if args.mode == "critic":
            coro = run_critic(
                model=args.model, repeats=args.repeats, images_dir=args.images,
                expected_path=args.expected, out=args.out,
            )  # fmt: skip
        else:
            coro = run_generate(model=args.model, runs=args.runs, out_dir=args.out_dir)
        asyncio.run(coro)
    except openrouter.MissingKey:
        sys.exit("OPENROUTER_API_KEY is not set (put it in .env). The eval makes real, paid calls.")


if __name__ == "__main__":
    main()
