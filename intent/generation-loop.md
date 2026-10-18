# Intent: Educational Science Diagram Generation Loop

## Goal
A K-12 student picks a topic from a short curated list of 4–5 science concepts and the app produces a flat-color 2D textbook-style diagram of that concept, displays it, and then critiques it with a vision model — returning a per-part checklist plus a short narrative that says which expected parts are present, misarranged, or obscured by garbled AI text.

## Who it is for
K-12 students (grades 5–10) learning basic science. Today they rely on static textbook images or Google image search, which vary in quality, miss key parts, and rarely tell the student what is wrong with the picture.

## Constraints
- **No images of real people.** Project-wide rule (course requirement).
- **App stack.** Python backend (Flask or FastAPI) with a simple HTML/JavaScript frontend.
- **Image-generation model.** Google "Nano Banana" (Gemini 2.5 Flash Image) via OpenRouter. Chosen because the team has standardized on it and its text-rendering quality suits labeled 2D diagrams.
- **Vision-critique model.** OpenAI GPT-4o via OpenRouter. Chosen for reliable structured output on the per-part checklist.
- **Topic set.** Hardcoded list of 4–5 scientific concepts; each concept has a known checklist of expected parts that the critique must verify against.
- **Visual style.** Flat-color 2D textbook illustration — solid color fills, no gradients, clean labels, simple shapes.
- **Critique format.** Per-part checklist (✓/✗ for each expected part + arrangement + text-clarity notes) plus a short narrative summary.
- **Cost ceiling.** Under ~$0.25 per generation + critique. Total semester budget ~$25.
- **Latency target.** 15–45 seconds end-to-end (one image-gen call followed by one vision-critique call).

## Not in scope
- User accounts, login, or persistent history between sessions.
- Multi-turn editing — the critique is informational; the user cannot ask the app to refine the diagram. Re-running generates a fresh attempt.
- Export, download, share-link, or print view of the generated diagram.
- Mobile-specific responsive design — desktop browser is the target.
- Topics outside the curated 4–5 list. Free-form user topics are out of scope because they would defeat the hardcoded checklist.
- Non-English labels.

## Success looks like
- A user picks a topic, clicks generate, and within ~30 seconds sees the diagram alongside a per-part checklist and a short narrative critique.
- The critique reliably identifies missing or mislabeled parts when the diagram has them, and does not falsely flag a correct diagram.
- No nonsensical AI text appears in the displayed diagram (the critique calls it out when it does).
- A typical run costs well under $0.25 and completes within 45 seconds.

## Open questions
- Final 4–5 topics and each topic's expected-part checklist. Example seeds already named: plant cell, animal cell, water cycle, simple circuit. Lock during the design phase.
- Flask vs FastAPI — either fits the constraints; pick at implementation time.
- Exact image-generation prompt that reliably enforces "flat 2D textbook illustration" style — needs iteration.
- Whether GPT-4o should return strict JSON (with a defined schema) or prose that the app parses — depends on schema-following reliability on small vision tasks.

**Approved by:** Javier Romo & Raphael Ralston, October 5, 2026
