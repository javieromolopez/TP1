# Four-question annotation (DRAFT, not the final ANNOTATION.md)

This is a starting point for Ralston and Javier. Sections 1 to 9 answer What is this, Why this choice, and What breaks in plain language, using only what the code, `spec.md` and `CHECKS.md` say. Each "What did I learn?" is left empty on purpose: it has to be your own experience, and it must include at least one place the agent was confidently wrong and you caught it. Rewrite anything that doesn't sound like you, then rename this file to `ANNOTATION.md`.

Examples already in the repo you can use for "What did I learn?" (use only what you really remember):
- GPT-4o graded a mislabeled circuit "good" four times. The 10-image eval caught it (`CHECKS.md` section 5).
- The cheaper critic model caught 15/15 planted flaws; GPT-4o caught 9/15.
- The prompt never asked for + and - on the battery, so a good-looking circuit failed rule A2.
- A prompt said "a animal cell" until `Topic.with_article` fixed it (`CLAUDE.md`, Common mistakes).
- The typo check first counted any text issue as a catch; review made it require the planted label.

---

## 1. Topic catalog (`app/topics.json`, `app/schemas.py`)
**What is this?** A JSON file describing the five topics: plant cell, animal cell, water cycle, simple circuit, flower. Each topic lists the labels to draw, the parts that must appear, the parts that must not appear, and a few arrangement rules (for example, the cell wall is outside the membrane). The image prompt, the critic and the verdict all read this one file. It does not call any model.
**Why this choice?** JSON instead of a Python dict, so the checklists can be read and changed without touching code. Pydantic checks the file when the server starts, so a typo stops the server instead of silently breaking a critique.
**What breaks?** If a checklist is wrong, every critique for that topic is wrong and nothing errors. There are only five topics. One rule (the circuit's A2, "battery shows + and -") disagreed with the image prompt until the prompt was fixed.
**What did I learn?** [YOUR WORDS]

## 2. Diagram generator (`app/generator.py`, `app/prompt_builder.py`)
**What is this?** Builds the image prompt (a shared "flat 2D textbook style" block, the topic's labels, and "no people, no faces"), sends it to an image model through OpenRouter, and returns the PNG. It makes one call and does not retry, because every retry costs money.
**Why this choice?** Python, since the rest of the backend is Python. `google/gemini-2.5-flash-image` costs about $0.039 per image; `google/gemini-3-pro-image` about $0.138. In our eval the cheaper model garbled labels on four of five topics in every run, and the Pro model mostly fixed it. Using Pro for a whole semester would be about $35 instead of the $25 budget, so that decision goes in a new intent, not in this code. Requests use plain `httpx` instead of a vendor SDK so the exact request is visible.
**What breaks?** Misspelled or garbled labels. Images that aren't flat. A timeout (504). A reply with no image (502). Cost adds up with every click.
**What did I learn?** [YOUR WORDS]

## 3. Provenance stamp (`app/stamp.py`)
**What is this?** Before an image leaves the server, it is re-saved with PNG text fields that say it is AI-generated (plus the app name, model and topic). The page also shows an "AI-generated diagram" caption under every image.
**Why this choice?** Pillow does it in a few lines. The stronger standard, C2PA, needs signing certificates we don't have.
**What breaks?** The text fields disappear if someone screenshots or re-encodes the image or uploads it to a site that strips metadata. It is a label, not proof.
**What did I learn?** [YOUR WORDS]

## 4. Diagram critic (`app/critic.py`)
**What is this?** Sends the generated image and the topic's checklist to a vision model and asks for strict JSON back: which parts are present, missing or mislabeled, arrangement rules, and text problems. It deliberately does not send the original prompt, so the model judges the picture itself and not what we asked for. Temperature is 0 and the reply format is JSON.
**Why this choice?** The spec's default is `openai/gpt-4o`. We tested it against `xiaomi/mimo-v2.6-flash` on 10 images (one good and one flawed per topic) with 3 repeats each. GPT-4o caught 9 of 15 planted flaws for about $0.20; mimo caught 15 of 15 for about $0.013 and raised no false flags on the good images. The code still uses GPT-4o because switching models requires a new intent first.
**What breaks?** A critic can say a wrong diagram is fine, and GPT-4o did that four times on one circuit. mimo sometimes writes thousands of hidden reasoning tokens (one reply used 6,806), so its speed varies. Replies that aren't valid JSON. The eval set is small, and the flawed circuit was chosen because GPT-4o had already passed it, which tilts the comparison against GPT-4o.
**What did I learn?** [YOUR WORDS]

## 5. Validator and verdict (`app/validator.py`, `app/verdict.py`)
**What is this?** Takes the critic's raw reply and makes it safe to show. It strips code fences, parses the JSON, and checks it against the schema: every required part exactly once, no invented parts. If the reply is invalid, it asks the critic once more. Then plain Python computes the verdict: "poor" if a forbidden part appears or half or more of the required parts are missing or mislabeled; "good" if every part is present, every rule is satisfied and there are no text issues; otherwise "needs_work". No model is involved.
**Why this choice?** The model reports what it sees, and code draws the conclusion, so the model never grades itself. It is pure Python, so it is tested without an API key. It is the same pattern as the Week 5 receipt checker.
**What breaks?** The verdict is only as good as the statuses the model reports. The "half or more" cutoff is our own judgment. After one failed retry the page shows "Critique unavailable".
**What did I learn?** [YOUR WORDS]

## 6. API server (`app/main.py`, `app/openrouter.py`)
**What is this?** A FastAPI server with `GET /api/topics`, `POST /api/generate` and `GET /api/health`. One generate request runs: draw, stamp, critique, validate, verdict. It logs tokens, cost and latency for every model call to `runs.jsonl` and keeps no state between requests. Errors are explicit: 400 for a bad topic, 503 if the key is missing, 502 or 504 when a model fails or times out.
**Why this choice?** FastAPI, because the request, the response and the critic's JSON can all be described as Pydantic models, and async handlers keep a 30-second model call from blocking the server. Flask would need a separate validation library; Spring Boot is more than two endpoints need.
**What breaks?** It needs `OPENROUTER_API_KEY` in `.env`. It has no login or rate limit, so anyone who can reach it can spend credits; it is meant for localhost only.
**What did I learn?** [YOUR WORDS]

## 7. Web frontend (`app/static/`)
**What is this?** One page in plain HTML, CSS and JavaScript: a topic dropdown, a Generate button, the image with its caption, a checklist table, arrangement and text issues, a short narrative, the verdict, and a timer while it waits.
**Why this choice?** No build step, and every line can be read in the presentation. React with Vite would add a toolchain for one screen. A Playwright test drives the real page in a browser.
**What breaks?** It depends on the exact JSON shape from the API. Error handling is a displayed message, nothing smarter.
**What did I learn?** [YOUR WORDS]

## 8. Eval harness (`eval/run_eval.py`, `eval/score.py`, `eval/expected.json`)
**What is this?** A script that runs the generator and critic comparisons against the real APIs on 10 hand-checked images and writes the tables and cost totals into `CHECKS.md`.
**Why this choice?** It reuses the app's own generator and critic code, so it measures what actually ships.
**What breaks?** Only 10 images and 3 repeats. `expected.json` was written by Claude Code and the team was supposed to spot-check the five flawed entries. The typo check first counted any text issue as a catch; review fixed it to require the planted label. A single network failure used to abort a run; now it becomes an invalid row.
**What did I learn?** [YOUR WORDS]

## 9. Checker (`app/checker.py`), from the Week 6 integration
**What is this?** Pure Python, no model and no network. It parses a critic reply (stripping one JSON fence), compares it to an answer key, and returns a result per part. A non-JSON reply is a structured failure, not a crash. A required part the critic didn't answer is a failing row. A part the critic made up is a failing row. An image passes only if every row passes.
**Why this choice?** Comparison is strict equality: `True` is not `"true"`, and `"nucleus"` is not `"Nucleus"` or `"nucleeus"`. No fuzzy matching and no model as judge, so the same input always gives the same result and tests don't need a key.
**What breaks?** Strictness means a harmless difference in wording counts as a failure. It is only as good as the answer key.
**What did I learn?** [YOUR WORDS]
