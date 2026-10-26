# Plan

## Files to create or change

| File | Purpose |
|---|---|
| `requirements.txt` | Python deps: fastapi, uvicorn, pydantic, httpx, Pillow, python-dotenv, pytest, playwright. |
| `.env.example` | Template showing `OPENROUTER_API_KEY=<your-key>`; the real `.env` is gitignored. |
| `.gitignore` | Add `runs.jsonl`, `__pycache__/`, `.env`, `eval/__pycache__/`, Playwright artifacts. |
| `app/__init__.py`, `app/schemas.py` | Pydantic models for `Topic`, `Checklist`, `ArrangementRule`, `Critique`, `Parts`, `TextIssue`, plus the schema loaders. |
| `app/topics.json` | The five locked topics and their required parts, forbidden parts, arrangement rules, label strings (from spec.md § Topic catalog). |
| `app/verdict.py` | Pure `verdict(topic, critique)` → `good`/`needs_work`/`poor`; no model. |
| `app/stamp.py` | Pure `stamp(png, meta)` → `bytes`; Pillow writes four `tEXt` chunks. |
| `app/openrouter.py` | Thin httpx wrapper: explicit timeouts (60s image, 30s critic), one retry on 5xx for critic only, appends one `runs.jsonl` line per call. |
| `app/generator.py` | Builds prompt from topic, calls Nano Banana, extracts PNG bytes, returns `GeneratedImage`. |
| `app/critic.py` | Sends image + topic checklist to GPT-4o with `response_format: json_object`, returns the raw text. |
| `app/validator.py` | Strips ```json fences, parses, validates against the schema, one retry with the error, computes verdict; never returns a half-validated critique. |
| `app/main.py` | FastAPI server: `GET /api/topics`, `POST /api/generate`, `GET /api/health`. One handler runs generator → stamp → critic → validator. Validates `topics.json` at startup. |
| `app/static/index.html`, `app/static/app.js`, `app/static/style.css` | One-page UI: topic dropdown, Generate button (disabled while in flight), image + AI-generated caption, checklist table, arrangement + text-issue lists, narrative, verdict, spinner with elapsed seconds. |
| `tests/__init__.py` | Empty package marker. |
| `tests/test_topics.py` | Loads `topics.json`; asserts the five ids and Pydantic startup validation. Covers spec behavior 2. |
| `tests/test_verdict.py` | Table-driven tests over every boundary in spec § "Verdict, computed in code." |
| `tests/test_validator.py` | Covers fences, schema-invalid JSON, omitted part, invented part, one retry, second-failure path. Spec behavior 6, 7. |
| `tests/test_stamp.py` | Round-trips a PNG and asserts the four text chunks are present. Spec behavior 9. |
| `tests/test_prompt_builder.py` | Asserts the prompt contains the shared style block, every required label for the topic, and "No people". Spec behavior 4. |
| `tests/test_generator.py` | Mocked HTTP: asserts payload and parsed response. |
| `tests/test_critic.py` | Mocked HTTP: asserts the request includes the image and checklist, but **not** the generation prompt. Spec behavior 5. |
| `tests/test_api.py` | Mocked model calls: covers spec behaviors 1, 3, 6, 9, 10, 12, 13, 14. |
| `tests/test_browser.py` | Playwright, mocked backend: choose a topic, click Generate, see the full render. Spec behavior 15. |
| `eval/run_eval.py` | Runs the four model comparisons from spec.md § Diagram generator and § Diagram critic; prints markdown for `CHECKS.md`. |
| `eval/expected.json` | Hand-written expected statuses for the ten eval images. |
| `eval/images/*.png` | Five good + five deliberately flawed PNGs (one of each per topic). |
| `CHECKS.md` | Results table from `run_eval.py` (model comparisons, tokens, cost, latency). |
| `README.md` | Fill the empty Commands section: `pip install -r requirements.txt`, `python -m uvicorn app.main:app`, `pytest`, the two eval commands. |

## Order of work

1. **Scaffold.** `requirements.txt`, `.env.example`, `.gitignore`, `app/__init__.py`, `tests/__init__.py`. Nothing depends on the logic yet; everything depends on this.
2. **Schemas and topic catalog.** `app/schemas.py`, `app/topics.json`, the loader. Validates at startup. Every other component reads from it, so its shape has to be right before anything else runs.
3. **Verdict logic** (`app/verdict.py`). Pure function, no I/O. Test first — the spec's verdict rules are a closed table.
4. **PNG stamp** (`app/stamp.py`). Pure function, no I/O. Test with Pillow round-trip.
5. **Prompt builder** as a pure function on top of `Topic` → string. Tested separately so the style block and "No people" are pinned before any real API call.
6. **OpenRouter client** (`app/openrouter.py`). One place for httpx, timeouts, retry policy, and the `runs.jsonl` append.
7. **Generator** (`app/generator.py`). Uses prompt builder + client. Mocked-HTTP test.
8. **Critic** (`app/critic.py`). Uses client. Mocked-HTTP test.
9. **Validator + retry** (`app/validator.py`). Uses schemas + verdict. Covers the realistic JSON shapes including malformed ones.
10. **API server** (`app/main.py`). Wires the above into three endpoints; one request runs the full pipeline. Mocked-HTTP tests cover behaviors 1, 3, 6, 10, 12, 13.
11. **Frontend** (`app/static/*`). One screen, no build step. Playwright test against a mocked backend (behavior 15).
12. **CI wiring.** Run `pytest` on every PR. No key needed for the suite; eval is separate.
13. **Eval harness** (`eval/run_eval.py`, `eval/expected.json`, `eval/images/*.png`). Run with a real key; write `CHECKS.md`. This is the only step that costs money and is the gate for behavior 16 and 17.
14. **README updates.** Fill in the empty Commands section with the four commands a grader needs.

## Risks

- **R1. Nano Banana drifts off the flat-color 2D textbook style.** Mitigation: pinned shared style block (spec § Diagram generator) gets tuned during the eval. If more than 1 of 3 runs misses style, switch to Nano Banana Pro per the spec's model comparison. Blast radius: aesthetic; the structural critique still works.
- **R2. Nano Banana draws a person or face in some outputs.** Mitigation: the shared style block says "No people, no faces, no hands"; the critic checks `people_present: true` and the API withholds the image (spec behavior 11). Blast radius: high — a bad image reaching a student. The vision-model check is the real shield, not the prompt.
- **R3. GPT-4o returns invalid JSON or invents a part name.** Mitigation: Pydantic schema + one retry with the validation error (spec behavior 7). On second failure, the image still shows with "Critique unavailable." Blast radius: medium.
- **R4. Critic grades the prompt instead of the image.** Mitigation: spec behavior 5 forbids sending the generation prompt to the critic; the eval set has five deliberately flawed images to catch this (behavior 16).
- **R5. OpenRouter rate limit or transient 5xx.** Mitigation: explicit timeouts (60s image, 30s critic); one retry after 2s on the critic only; no retry on the image call (cost). Blast radius: one failed run per click.
- **R6. Topic catalog accepts invalid data; required/forbidden/label drift between catalog and critic.** Step 2 looks like static data, but Pydantic validates field types only — it does not catch cross-field mistakes like empty `required_parts`, duplicate arrangement-rule ids within a topic, a required part that is also forbidden, or label strings that don't match the part names the critic will check. Pydantic happily loads `"required_parts": []` and the bugs only surface at the first real run, when the verdict is silently wrong. Mitigation: the loader runs cross-checks after Pydantic validation: (a) topic ids unique, (b) each topic has ≥1 required part, (c) arrangement-rule ids unique within each topic, (d) `required_parts ∩ forbidden_parts = ∅` per topic, (e) every label string equals a part name the critic will be told to check for. The loader raises with the rule that failed and the offending topic, and the server refuses to start. The same checks double as the proof below. Blast radius: medium — a bad catalog poisons every critique until caught.
- **R7. Pydantic schema too strict and rejects valid critic JSON.** Mitigation: `Optional` on every field a critic can reasonably omit; tests cover realistic JSON shapes; schema frozen only after a real GPT-4o run lands inside it.
- **R8. PNG metadata stripped by some viewers.** Mitigation: the visible "AI-generated" caption is the user-facing signal; PNG text chunks are defense in depth, not load-bearing.
- **R9. Cost overrun.** Mitigation: `runs.jsonl` per call; `CHECKS.md` sums and is compared to OpenRouter's Activity page; semester estimate is ~$16 vs. $25 ceiling (spec § Cost estimate). Image call is the dominant cost; one retry cap keeps the worst case under $0.06.
- **R10. Two team members stepping on each other's branches.** Mitigation: split the order into non-overlapping chunks (one owns 1–6, the other owns 7–9, then both work 10–13 together). One branch per PR per CLAUDE.md.

## Proof

Each row names the exact command, the test functions (or invocations) it runs, and the output that means the step is done. "Works" = exit 0 with the listed per-test `PASSED` lines. For step 13, the success signal is a populated `CHECKS.md` with non-empty comparison tables. Step 13 is the only step that needs a real API key.

Step 2 is the highest-leverage proof in the plan — bad topic data silently breaks every critique — so its row is expanded below the table.

| Step | Proof (maps to spec behavior numbers) |
|---|---|
| 1. Scaffold | `pip install -r requirements.txt` succeeds; `python -c "import app"` succeeds. |
| 2. Topic catalog | See **Step 2 proof** below. (B2) |
| 3. Verdict | `pytest tests/test_verdict.py` table-driven over the four boundaries in spec § "Verdict, computed in code". (B8) |
| 4. Stamp | `pytest tests/test_stamp.py` round-trips a PNG and asserts the four `tEXt` chunks. (B9) |
| 5. Prompt builder | `pytest tests/test_prompt_builder.py` asserts style block, every required label, "No people". (B4) |
| 6. OpenRouter client | `pytest tests/test_openrouter.py` asserts timeouts, retries, and the `runs.jsonl` append. |
| 7. Generator | `pytest tests/test_generator.py` mocks httpx and checks payload + parse. |
| 8. Critic | `pytest tests/test_critic.py` asserts the image and checklist go in, the generation prompt does not. (B5) |
| 9. Validator | `pytest tests/test_validator.py` covers fences, schema-invalid JSON, omitted part, invented part, retry, second-failure. (B6, B7) |
| 10. API server | `pytest tests/test_api.py` covers B1, B3, B6, B9, B10, B12, B13, B14 with mocked model calls. |
| 11. Frontend | `pytest tests/test_browser.py` (Playwright, mocked backend) covers the full render path. (B15) |
| 12. CI | `pytest` green on every PR; GitHub Actions does not need a key. |
| 13. Eval | `python eval/run_eval.py critic --model openai/gpt-4o --repeats 3` (and the other critic and both `generate` runs) prints the comparison tables that go into `CHECKS.md`. (B16, B17) |
| 14. README | From a fresh clone, run `pip install -r requirements.txt`, `pytest`, `python -m uvicorn app.main:app`, and the eval command; all four work end to end. |

### Step 2 proof

Command: `pytest tests/test_topics.py -v`.

Tests in the file (one per cross-check, plus a parametrized bad-fixture test):

- `test_load_topics_returns_five_ids` — asserts the five ids from spec § Topic catalog (`plant-cell`, `animal-cell`, `water-cycle`, `simple-circuit`, `flower`) are present, in that order.
- `test_topic_ids_unique` — no two topics share an id.
- `test_each_topic_has_nonempty_required_parts` — every topic has ≥1 entry in `required_parts` (catches `[]`).
- `test_arrangement_rule_ids_unique_per_topic` — within each topic, no two arrangement rules share an id (the spec behavior 2 case).
- `test_required_and_forbidden_disjoint` — per topic, `required_parts ∩ forbidden_parts == ∅` (catches `plant-cell` with `vacuole` in `forbidden_parts`).
- `test_label_strings_match_part_names` — every label string equals a part name the critic will be told to check for (catches "Golgi body" vs "Golgi apparatus").
- `test_bad_topics_rejected_at_startup` — parametrized over five bad fixtures: (a) `required_parts: []`, (b) duplicate `A1` arrangement rule, (c) `plant-cell` with `vacuole` in `forbidden_parts`, (d) missing required field, (e) wrong type (`required_parts: "nucleus"`). Each case asserts the loader raises with a message that names both the failing rule and the offending topic id.

Output that means it worked: `pytest` exits 0; `pytest -v` prints 11 `PASSED` lines (6 invariant tests + 5 parametrized cases). For the bad-fixture test, every raised error message contains both the rule name and the topic id, so a human reading a failure locates the bad entry in `topics.json` in seconds. This is the same check R6 says the loader runs in production, so passing tests here mean a bad `topics.json` stops the server at startup, not at the first critique.

**End-to-end smoke** (manual, real key, behavior 17):

1. `python -m uvicorn app.main:app`, open `http://localhost:8000` in a desktop browser.
2. For each of the five topics: pick it, click Generate, confirm the image renders with the "AI-generated" caption, the checklist table, the narrative, and the verdict.
3. After ten runs, `wc -l runs.jsonl` shows 20 (one line per model call); `tail -f` confirms each line has model, tokens, cost, latency.
4. Cost per run ≤ $0.25, latency per run ≤ 45 s.

## Subagents and parallel work

Two pieces of work can move in parallel with the main pipeline, neither blocks code:

- **Eval images (step 13, `eval/images/*.png`).** Image work, not code. Can be prepared by the user or a subagent while steps 1–11 are in flight. They are a hard dependency only for step 13.
- **`CHECKS.md` writeup.** After `run_eval.py` produces raw numbers, a subagent can format the table the spec wants. Not a hard dependency; the human can do it.

No worktree isolation is needed — this is one feature on one branch per CLAUDE.md. Within the order above, the two team members should claim non-overlapping steps (e.g., one owns 1–6, the other owns 7–9) and meet at 10–13.

**Approved by:** Javier Romo & Ralston Raphael, October 19, 2026
