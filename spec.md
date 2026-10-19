# Spec: Educational Science Diagram Generation Loop

<!-- The agent writes this from the approved intent. You validate it against the intent.
     If the spec and the intent disagree, the intent wins until you change the intent. -->

## Intent
Implements [`intent/generation-loop.md`](intent/generation-loop.md) (approved October 5, 2026).

A student picks one of five science topics. The app generates a flat-color 2D textbook diagram, shows it, and sends **the generated image itself** to a vision model. The vision model checks the image against that topic's hand-written checklist. The student sees the diagram next to a per-part checklist (✓/✗), arrangement notes, label-text problems, and a short narrative.

### Open questions from the intent, resolved here
| Question | Decision |
|---|---|
| Final topics and checklists | Five topics, locked below in [Topic catalog](#topic-catalog). |
| Flask vs FastAPI | **FastAPI.** Pydantic models validate the critic's JSON in the same place we declare the API types. See [API server](#api-server). |
| Prompt that enforces flat 2D style | One shared style block plus per-topic label list (see [Diagram generator](#diagram-generator)). The wording gets tuned in the eval, and the final text is committed in `topics.json`. |
| Strict JSON vs prose | **Strict JSON** against the schema in [Critique schema](#critique-schema), validated in code, with one retry. The app computes the verdict and never takes it from the model. |

## Architecture

```
browser (index.html + app.js)
   │  GET /api/topics          POST /api/generate {topic_id}
   ▼
FastAPI server (app/main.py)
   ├─ topic catalog   (topics.json, validated at startup)
   ├─ diagram generator ──► OpenRouter ──► google/gemini-2.5-flash-image  (returns PNG)
   ├─ provenance stamp (Pillow writes PNG text chunks)
   ├─ diagram critic   ──► OpenRouter ──► openai/gpt-4o                  (image + checklist in, JSON out)
   ├─ critique validator + verdict (pure Python, no model)
   └─ run log (runs.jsonl: tokens, cost, latency per call)
```

There is one request per generation. The server makes the image call, stamps the result, then makes the critique call, and returns both together. No state is kept between requests.

## Components
Each component lists the two required decisions (language, model) and the alternative we considered.

### Topic catalog
- **What it does:** Holds the five topics. Each topic has the exact label strings the generator must draw, the parts the critic must check, parts that must *not* appear, and arrangement rules. Both model calls and the verdict logic read from it, so changing a checklist is a data edit and needs no code change.
- **Language:** JSON file (`app/topics.json`) loaded by Python. **Why:** the teacher-facing content stays readable and diffable apart from code. Alternative: a Python dict in a module. It is just as easy to load, but it mixes content with code, and a non-programmer reviewing checklists would have to read Python. Pydantic validates the file at startup, so a typo in it stops the server instead of producing a bad critique.
- **Model:** none.
- **Interfaces:** `load_topics() -> dict[str, Topic]`. `GET /api/topics` exposes only `id` and `display_name`.
- **Dependencies:** pydantic (schema validation of the file).

### Diagram generator
- **What it does:** Builds the image prompt from the topic (shared style block + the topic's label list + "no people, no faces"). It calls the image model once and returns PNG bytes. It does not retry automatically: a fresh attempt costs money and the student can press Generate again.
- **Language:** Python 3.12. **Why:** the rest of the backend is Python, and both team members have used Python for OpenRouter calls in Weeks 2–5. Alternative: Java with `java.net.http`. That works, but it would split the backend across two languages for one HTTP call.
- **Model:** `google/gemini-2.5-flash-image` ("Nano Banana"). **Why:** the intent fixes it, because its in-image text rendering suits labeled diagrams at about $0.039 per image. **Comparison (required):** cheap = `google/gemini-2.5-flash-image` versus strong = `google/gemini-3-pro-image` (Nano Banana Pro, about $0.134 per image). Real task: generate each of the 5 topics 3 times on each model (30 images). For every image we hand-score (a) required labels present and correctly placed, (b) garbled or misspelled label text, (c) flat-style compliance (no gradients or photo shading), (d) cost and latency. We keep Nano Banana unless Pro removes garbled labels on topics where Nano Banana fails more than 1 in 3 runs. If that happens, we update the intent before switching. *Results: recorded in `CHECKS.md` once the eval runs (not yet run at spec time).*
- **Interfaces:** `generate(topic: Topic) -> GeneratedImage(png: bytes, model: str, usage: Usage)`. Calls `POST https://openrouter.ai/api/v1/chat/completions` with `modalities: ["image", "text"]`. Reads the image from `choices[0].message.images[0].image_url.url` (base64 data URL).
- **Dependencies:** httpx (HTTP client with explicit timeouts; no vendor SDK, so the request we send is visible in our code).

### Provenance stamp
- **What it does:** Writes PNG `tEXt` chunks into every generated image before it leaves the server: `ai_generated=true`, `generator=<model slug>`, `topic=<id>`, `created=<ISO time>`, `app=TP1 diagram loop`. Gemini images also carry Google's invisible SynthID watermark. We note it but do not rely on it, because we cannot verify it ourselves. The UI shows a visible "AI-generated diagram" caption under every image.
- **Language:** Python. **Why:** Pillow writes PNG metadata in a few lines. Alternative: C2PA manifests via `c2pa-python`. That is the stronger standard, but it needs signing certificates we do not have. We list it under Out of scope.
- **Model:** none.
- **Interfaces:** `stamp(png: bytes, meta: dict) -> bytes`.
- **Dependencies:** Pillow.

### Diagram critic
- **What it does:** Sends the generated image plus the topic's checklist, forbidden parts, and arrangement rules to a vision model and asks for JSON in the [Critique schema](#critique-schema). It deliberately does **not** send the generation prompt. The critic must judge what is in the picture, not what we asked for (assignment requirement: "the critique must read the generated image itself").
- **Language:** Python. **Why:** same process as the generator, and it shares the OpenRouter client.
- **Model:** `openai/gpt-4o`. **Why:** the intent picks it for reliable structured output on small vision tasks. About $0.01 per critique. **Comparison (required):** cheap = `xiaomi/mimo-v2.6-flash` (class vision model, about $0.0005 per critique) versus strong = `openai/gpt-4o`. Real task: an eval set of 10 images, one good and one deliberately flawed per topic (e.g. an animal cell drawn with a cell wall, a circuit with a gap in the loop, a flower with the anther and stigma swapped). Each image has hand-written expected statuses in `eval/expected.json`. Measured per model: per-part accuracy, false flags on the good images (intent: "does not falsely flag a correct diagram"), whether garbled text is caught, JSON validity rate before retry, tokens, cost. If the cheap model matches GPT-4o on false flags and per-part accuracy within one part per image, we propose switching in a new intent, since a 20× cheaper critic matters for the $25 budget. *Results: recorded in `CHECKS.md` once the eval runs (not yet run at spec time).*
- **Interfaces:** `critique(topic: Topic, png: bytes) -> RawCritique`. Same OpenRouter endpoint, image sent as a base64 `image_url` content part, `response_format: {"type": "json_object"}`, `temperature: 0`.
- **Dependencies:** httpx.

### Critique validator and verdict
- **What it does:** Turns the model's reply into something the UI can trust. It strips ```json fences, parses the JSON, and validates it against the schema. It checks that every checklist part appears exactly once and that no invented part names appear. Then it computes the overall verdict **in code** from the part statuses, so the model never grades itself. This is the same rule as the Week 5 receipt checker: the model reports observations and our code draws the conclusion.
- **Language:** Python. **Why:** this is pure logic that must be unit-tested without a key, and pytest is already our test runner. **Model:** none, on purpose.
- **Interfaces:** `validate(topic, raw_text) -> Critique | ValidationError`; `verdict(topic, critique) -> "good" | "needs_work" | "poor"`.
- **Dependencies:** pydantic.

### API server
- **What it does:** Serves the static frontend and two JSON endpoints. It runs generate → stamp → critique → validate per request and logs usage.
- **Language:** Python with **FastAPI** + uvicorn. **Why:** request and response bodies and the critique schema are all Pydantic models, so one validation layer covers both our API and the model's output. Async handlers also keep a 30-second model call from blocking the server. Alternative considered: Flask. It is simpler to start, but it needs a separate validation library, and its dev server handles one request at a time by default. Java/Spring Boot was ruled out as far heavier than two endpoints need.
- **Model:** none.
- **Interfaces:**
  - `GET /api/topics` → `[{"id": "plant-cell", "display_name": "Plant cell"}, ...]`
  - `POST /api/generate` body `{"topic_id": "plant-cell"}` → `{"image": "data:image/png;base64,...", "critique": Critique | null, "critique_error": str | null, "verdict": str | null, "usage": {...}}`
  - `GET /api/health` → `{"ok": true, "key_present": bool}`
  - Errors: `400` unknown topic, `503` no API key, `502` model returned no image, `504` timeout.
- **Dependencies:** fastapi, uvicorn, python-dotenv (reads `OPENROUTER_API_KEY` from `.env`, which is git-ignored).

### Web frontend
- **What it does:** A single page with a topic dropdown, a Generate button, the image with its "AI-generated" caption, the checklist table (part, ✓/✗/?, note), arrangement and text-issue lists, the narrative, and the computed verdict. It shows a spinner with elapsed seconds while the request runs.
- **Language:** HTML, CSS, vanilla JavaScript (`fetch`). **Why:** the intent asks for a simple HTML/JS frontend, and it needs no build step. Both of us can read every line in the presentation. Alternative: React + Vite. That adds a toolchain and a second dependency tree for one screen and no client-side state worth managing.
- **Model:** none.
- **Interfaces:** calls the three endpoints above. Served from `app/static/`.
- **Dependencies:** none at runtime. Playwright (Python) for the browser-driven test.

### Eval harness
- **What it does:** Runs both model comparisons above against the real APIs and writes a results table plus token and cost totals to `CHECKS.md`. It only runs when a key is set.
- **Language:** Python script (`eval/run_eval.py`). **Why:** it reuses the generator and critic code directly, so the eval measures exactly what ships.
- **Model:** the four models named above. **Interfaces:** `python eval/run_eval.py --critic openai/gpt-4o` etc.; reads `eval/images/*.png` + `eval/expected.json`.
- **Dependencies:** none beyond the app.

## Topic catalog
Locked for TP1. Labels are the exact strings the generator is told to draw and the critic checks for. A ✗ on a **forbidden** part means it appeared when it should not.

| id | Required parts | Forbidden | Arrangement rules |
|---|---|---|---|
| `plant-cell` | cell wall, cell membrane, cytoplasm, nucleus, chloroplast, vacuole, mitochondrion | — | A1 cell wall is the outermost layer, outside the membrane · A2 all organelles sit inside the membrane · A3 the vacuole is the largest organelle |
| `animal-cell` | cell membrane, cytoplasm, nucleus, mitochondrion, ribosome, endoplasmic reticulum, Golgi apparatus | cell wall, chloroplast | A1 the membrane is the outer boundary · A2 all organelles sit inside the membrane · A3 the endoplasmic reticulum is next to the nucleus |
| `water-cycle` | sun, ocean or lake, evaporation, condensation, cloud, precipitation, collection | — | A1 the evaporation arrow rises from the water · A2 precipitation falls from the cloud · A3 the arrows form one closed loop |
| `simple-circuit` | battery, wire, switch, light bulb | — | A1 all components lie on one loop · A2 the battery shows + and − terminals · A3 the loop is closed except at an open switch |
| `flower` | petal, sepal, stamen, anther, filament, pistil, stigma, style, ovary | — | A1 the anther sits on top of the filament · A2 the stigma is at the top of the style, the ovary at its base · A3 the sepals are below the petals |

**Shared style block** (prepended to every image prompt, tuned during the eval):
> Flat-color 2D textbook illustration for a grade 5–10 science class. Solid color fills, no gradients, no shading, no photorealism, white background, thin dark outlines. Every label in clear sans-serif English with a straight leader line to its part. Draw only these labels, spelled exactly: {labels}. No people, no faces, no hands.

## Critique schema
The critic must return exactly this shape (enforced by Pydantic):

```json
{
  "parts": [
    {"name": "nucleus", "status": "present", "note": "centered, labeled clearly"}
  ],
  "forbidden_found": ["cell wall"],
  "arrangement": [{"rule": "A1", "ok": true, "note": ""}],
  "text_issues": [{"label_text": "Mitochondrin", "problem": "misspelled"}],
  "people_present": false,
  "narrative": "Two to four sentences for a student."
}
```

- `parts[].status` ∈ `present` | `missing` | `mislabeled` | `unclear`.
- `text_issues[].problem` ∈ `garbled` | `misspelled` | `wrong_part`.
- `narrative` ≤ 80 words.

**Verdict, computed in code:**
- `good`: every required part `present`, `forbidden_found` empty, every arrangement rule `ok`, no `text_issues`.
- `poor`: half or more of the required parts are `missing` or `mislabeled`, or any forbidden part was found.
- `needs_work`: everything else.

## Behavior
Requirements the tests will check. Tests marked *(no key)* use a mocked HTTP layer and run in CI. Tests marked *(eval)* need a real key.

1. `GET /api/topics` returns exactly the five topics in the catalog, each with `id` and `display_name` only. *(no key)*
2. The server refuses to start if `topics.json` fails validation, for example a topic with no required parts or an arrangement rule id that is not unique. *(no key)*
3. `POST /api/generate` with an unknown `topic_id` returns `400`, and no model call is made. *(no key)*
4. The image prompt contains the shared style block, every required label for the topic, and "No people". *(no key)*
5. The critique request contains the image as an `image_url` part plus the topic's checklist. It does **not** contain the image-generation prompt text. *(no key)*
6. A critic reply wrapped in ```json fences parses the same as a bare JSON reply. *(no key)*
7. A critic reply that is not JSON, fails the schema, omits a required part, or invents a part name triggers exactly one retry with the validation error included. A second failure returns the image with `critique: null` and a readable `critique_error`. It never returns a half-validated critique. *(no key)*
8. `verdict()` returns `good` / `needs_work` / `poor` per the rules above, covered by one table-driven test per rule boundary. *(no key)*
9. Every PNG returned by `/api/generate` carries the provenance text chunks (`ai_generated=true`, `generator`, `topic`, `created`). *(no key)*
10. If the image model replies with text and no image (a refusal or safety block), the API returns `502` with the model's text as the reason, and the critic is not called. *(no key)*
11. If the critic reports `people_present: true`, the image is withheld from the response and the student sees "This diagram was hidden because it showed a person." *(no key)*
12. With `OPENROUTER_API_KEY` unset, `/api/health` reports `key_present: false` and `/api/generate` returns `503` without making any network call. *(no key)*
13. Timeouts are 60 s for the image call and 30 s for the critique. An image timeout returns `504`. A critique timeout returns the image with `critique_error: "critique timed out"`. *(no key)*
14. Each model call appends one line to `runs.jsonl`: model, prompt/completion tokens, cost from OpenRouter's `usage` field, latency. The README's running cost total is summed from this file and checked against OpenRouter's Activity page. *(no key)*
15. Browser check (Playwright, mocked backend): choose a topic, click Generate, and the button disables while the request runs. The image, the "AI-generated" caption, one checklist row per required part, the narrative, and the verdict all render. *(no key)*
16. On the critic eval set, the chosen critic raises no false ✗ on the five good diagrams and catches the planted flaw in at least four of the five flawed ones. *(eval)*
17. A real end-to-end run completes in ≤ 45 s and costs ≤ $0.25, read from `runs.jsonl`. *(eval)*

## Failure handling
| Case | What happens |
|---|---|
| Unknown or missing topic | `400`, message names the valid ids, no model call. |
| Missing API key | Server still starts so the UI loads. `/api/generate` returns `503` "OpenRouter key not configured". |
| Image model refuses or returns no image | `502` with the model's text, no critique call, no charge for a second call. |
| Garbled labels in the image | Not an error. This is exactly what the critic reports under `text_issues`. |
| Critic returns non-JSON or schema-invalid JSON | One retry with the validation error appended. If that fails, the image is shown with "Critique unavailable — try again." |
| Critic invents a part or skips one | Treated as schema-invalid (same path as above). We never show a checklist with a missing row. |
| Critic sees a person in the image | Image withheld (behavior 11). |
| Timeout | Image call `504`. Critique call: image still shown with a critique error. |
| OpenRouter `429` / `5xx` | No automatic retry on the image call (cost). One retry after 2 s on the critique call. |
| Double-click on Generate | Button disabled until the response arrives, so one click means one paid call. |

## Cost estimate
Prices from OpenRouter's model list, checked October 18, 2026.

| Call | Tokens (approx.) | Cost per call |
|---|---|---|
| Image, `google/gemini-2.5-flash-image` | ~150 in, 1 image out (~1,290 image tokens) | ~$0.039 |
| Critique, `openai/gpt-4o` ($2.50 / $10 per M) | ~765 image + ~700 text in, ~600 out | ~$0.010 |
| **One run** | | **~$0.05** (≤ $0.06 with a critique retry) |

The intent's per-run ceiling is $0.25, so a run is about 5× under it.

**Semester:** about 250 development and demo runs ≈ $12.50. Generator comparison: 15 Pro images × ~$0.134 + 15 Nano Banana images ≈ $2.60. Critic comparison: 10 images × 2 models × 3 repeats ≈ $0.35. **Total ≈ $16**, under the intent's $25 and the assignment's ~$20 flag. Switching the critic to `xiaomi/mimo-v2.6-flash` would save only about $2.50, because the image dominates the cost.

## Out of scope
Carried over from the intent:
- User accounts, login, saved history.
- Multi-turn editing or "fix this diagram" (re-running makes a fresh attempt).
- Export, download, share links, print view.
- Mobile layout (desktop browser only).
- Topics outside the five above, free-form topics.
- Non-English labels.

Ruled out by this design:
- Automatic image regeneration when the critique is bad (doubles cost; the student decides).
- Letting the critic see the generation prompt.
- Letting the model decide the overall verdict.
- C2PA signed manifests (needs signing certificates). Provenance uses PNG text chunks + a visible caption instead.
- Streaming partial results to the browser.
- Uploading a student's own photo, and audio (assignment stretch goals; revisit only if the core loop is done early).

**Approved by:** Javier Romo & Ralston Raphael, October 18, 2026
