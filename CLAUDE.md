# Project conventions

<!-- The agent reads this at the start of every session. Keep it short and current.
     Graded: does it reflect how the team actually works? -->

## What this repository is
Team Project 1 (Multimodal Web App). The user picks a science topic, the app draws a labeled diagram, a vision model critiques the image itself, and the verdict is computed in code. FastAPI on Python 3.12; `google/gemini-2.5-flash-image` draws and `openai/gpt-4o` critiques, both through OpenRouter. See [spec.md](spec.md) and [plan.md](plan.md).

## Commands
Use the repo's `.venv` (Python 3.12).
```text
# build    pip install -r requirements.txt && python -m playwright install chromium
# test     python -m pytest -v        (no API key needed; HEADED=1 to watch the browser test)
# run      python -m uvicorn app.main:app   (needs OPENROUTER_API_KEY in .env), then open http://localhost:8000
# lint     uvx ruff check .
```
Eval (needs the key): `python eval/run_eval.py critic --model openai/gpt-4o --repeats 3` and `python eval/run_eval.py generate --model google/gemini-2.5-flash-image --runs 3`; results in `CHECKS.md`. Not built yet: CI (plan step 12).

## Conventions

- Code in `app/`, tests in `tests/test_<module>.py` (e.g. `tests/test_verdict.py` for `app/verdict.py`).
- Tests are written and committed before the code they test (a red commit, then a green one).
- Branches are `<prefix>/<kebab-name>` with prefix `spec/`, `build/`, `polish/` or `docs/` (e.g. `build/model-calls-7-9`).
- One feature per PR, reviewed against `REVIEW.md` by a separate agent before merging.
- Never push to `main`.

## Working rules

For an introductory lab, follow its explicitly assigned stages; the full chain below applies to major projects. Week 1 uses its own minimal repository.

- Write or update `intent/` and `spec.md` before code. Get `plan.md` approved before implementing.
- One feature per branch and pull request. Never push to `main` directly.
- Never commit `.env` or `.claude/settings.local.json`.
- Current stage: Test and Deploy (due October 26); Build is complete. Update this line at each stage.
- The critique must read the generated image itself, never the generation prompt (spec behavior 5).
- Generated diagrams contain no people or faces (the prompt says so, and the critic's `people_present` withholds the image).

## Common mistakes
Things the agent got wrong before and must not repeat. Add to this list as they happen.

- Stacked PRs: merge each one into `main`, or delete its branch so the next PR retargets. #3 and #4 were merged into stacked branches and had to be re-landed in #6 and #7.
- Pull before reviewing: a review on a stale checkout re-reported findings that were already fixed.
- Prompts use `Topic.with_article`, never a hardcoded "a"/"an" ("a animal cell" shipped once).
- Never edit `eval/expected.json` to make the critic look better; a disagreement is a finding for `CHECKS.md`.
