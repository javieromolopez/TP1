# Project conventions

<!-- The agent reads this at the start of every session. Keep it short and current.
     Graded: does it reflect how the team actually works? -->

## What this repository is
The user picks a science topic, the app draws a labeled diagram, a vision model critiques the image itself, and the verdict is computed in code. See the current `spec.md`.

## Commands
```text
# build    pip install -r requirements.txt && python -m playwright install chromium   (Python 3.12)
# test     python -m pytest -v        (no API key needed; HEADED=1 to watch the browser test)
# run      python -m uvicorn app.main:app   (needs OPENROUTER_API_KEY in .env), then open http://localhost:8000
# lint     ruff check .
```

## Conventions

- code in app/, tests in tests/test_.py
- tests written and committed before the code they test
- branches build/, polish/ or docs/
- one feature per PR
- never push to main

## Working rules

For an introductory lab, follow its explicitly assigned stages; the full chain below applies to major projects. Week 1 uses its own minimal repository.

- Write or update `intent/` and `spec.md` before code. Get `plan.md` approved before implementing.
- One feature per branch and pull request. Never push to `main` directly.
- Never commit `.env` or `.claude/settings.local.json`.
- This is Team Project 1 (Multimodal Web App).
- Current assigned stage: build.
- The project explicitly requires generating an image, displaying it, and critiquing the generated image itself with a vision model.
- No images of real people are permitted.

## Common mistakes
Things the agent got wrong before and must not repeat. Add to this list as they happen.
