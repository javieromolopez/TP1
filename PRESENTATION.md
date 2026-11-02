# TP1 presentation flow (DRAFT)

Mon Nov 2, 1:30 PM, MC-225. 10 minutes plus 5 of questions. Order is drawn at the start of class.
The sheet asks for three things: the app running live, one artifact from the chain on screen, and one thing we tried that failed or took out, and what we did about it.

**Audience:** CS students, not AI researchers. Say "the AI looks at the picture" before saying "vision model". Explain any term once, then use it.

**Speaker split:** R = Ralston, J = Javier. Both of us must be able to answer questions on every part.

## Before we start (5 minutes before class)
- [ ] `.env` has the OpenRouter key; `python -m uvicorn app.main:app` is running; http://localhost:8000 loads.
- [ ] Run one full generation on the plant cell. Know that it takes about 13 to 15 seconds and costs about $0.05.
- [ ] Backup ready: screenshots or a screen recording of one good run, in case the network or API fails.
- [ ] `spec.md` open at the architecture diagram. `CHECKS.md` open at the generator comparison.
- [ ] Peer notes form open on a laptop: https://docs.google.com/forms/d/e/1FAIpQLSfNKbChCap-3fGF5U-2mELJmqkGJPybHt7KplK3F__zngARNA/viewform
- [ ] Browser zoom at 125% or more so the back row can read it.

## Timeline

| Time | Who | Section |
|---|---|---|
| 0:00 to 0:45 | R | The problem and what we built |
| 0:45 to 3:30 | R drives, J narrates | Live demo |
| 3:30 to 6:00 | J | Artifact on screen: the architecture in `spec.md` |
| 6:00 to 8:30 | R | What failed: garbled labels, and the critic fooled |
| 8:30 to 9:30 | J | What we'd do next |
| 9:30 to 10:00 | R | Close, hand over to questions |

## 1. The problem and what we built (R, 45 s)
- AI image models draw diagrams that look right but have garbled or wrong labels. A student can't tell.
- Our app: pick a science topic, it draws a labeled textbook diagram, then a second AI looks at the picture and checks it against a checklist we wrote.
- One line that frames everything: **the AI reports what it sees, and our code decides the grade.**

## 2. Live demo (R drives, J narrates, 2 min 45 s)
- Pick the plant cell (most reliable). Click Generate. While the spinner runs (about 15 s), J says what is happening: draw, stamp, check.
- Point out: the "AI-generated diagram" caption (provenance), the checklist table with the marks per part, the arrangement notes, any text issues, and the verdict.
- If the verdict is "needs_work", good: explain what flagged it. A perfect run is less interesting than the checker catching something.
- If time allows, run a second topic (flower is the hardest).
- Do not narrate code here. Save it for section 3.

## 3. Artifact on screen: the architecture in spec.md (J, 2 min 30 s)
Show the diagram at the top of `spec.md`: browser, then FastAPI server, then generator, stamp, critic, validator and verdict.
- Walk it left to right in one sentence per box.
- **Key design idea (say it plainly):** the critic never sees the prompt we gave the image model. It judges the picture, not our intentions. And it never grades itself: it lists what it sees, and `verdict.py` applies fixed rules (a forbidden part or half the parts missing is "poor", everything present is "good").
- Why it matters: models are confidently wrong, so the trustworthy part must be code we can test without an API key.
- Show one line from the spec where a language and a model were chosen with the alternative considered (generator: Python, `gemini-2.5-flash-image`, alternative the Pro model).
- This is also where we say it is a chain: intent, spec, plan, tests, reviewed PRs, annotation.

## 4. What failed (R, 2 min 30 s)
Two short stories. Pick the first for sure; add the second if time is OK.
1. **Garbled labels.** The cheap image model (Nano Banana) misspelled or misplaced labels on four of five topics in every run. Show the contact sheet in `eval/generator-comparison/` (cheap model on the top row, Pro below). We could not even use its output as "correct" reference images. The Pro model fixed most of it but costs about 3.5x as much per image, which would put the semester over our $25 budget. So we stopped and wrote it up as a decision for a new intent instead of switching quietly.
2. **The checker was fooled.** GPT-4o graded a mislabeled circuit "good" four times in a row. Our 10-image eval (one good and one planted flaw per topic) caught it. The cheaper model caught 15 of 15 planted flaws against GPT-4o's 9 of 15, at about 1/15 the cost. Be upfront that we chose the flawed circuit because GPT-4o had already passed it, so the test leans against GPT-4o.
- What we did about it: moved the grading into code, added the eval, and recorded the findings in `CHECKS.md` rather than editing the answer key to look better.

## 5. What we'd do next (J, 1 min)
- Switch the critic to the cheaper model through a new intent (the spec says intent comes first).
- Fix the circuit prompt so it asks for + and - terminals; today a correct-looking circuit can fail rule A2.
- Decide whether the better image model is worth the budget.
- Total spend so far: about $6.07 on the key (see README cost section).

## 6. Close (R, 30 s)
- One-sentence recap: draw, look, and let code decide.
- "Questions?" Then open the peer notes form for the room.

## Likely questions and who answers

| Question | Answer in one or two sentences | Lead |
|---|---|---|
| Why not just ask the image model if its own image is right? | It tends to agree with itself. A second model reading only the picture, plus a code-computed verdict, is harder to fool. | R |
| Why doesn't the critic see the prompt? | The assignment requires judging the image itself. If it saw the prompt, it could pass what we asked for rather than what was drawn. | J |
| What does `checker.py` do and why strict equality? | It compares the critic's reply to an answer key with exact matches, so results are the same every time and tests need no API key. A fuzzy match could hide real mistakes. | J |
| How much did it cost? | About $6.07 total on the key; about $0.05 per generate-and-check run. | R |
| What if the model returns garbage instead of JSON? | The validator strips code fences, retries once, and if it still fails the page shows "Critique unavailable". It never crashes. | R |
| What does the provenance stamp do? | It writes "ai_generated" and the model name into the PNG's metadata, plus a visible caption. It's removed if the image is screenshotted. | J |
| Which parts did each of you write? | R: the app code (generator, critic, validator, server, page, eval). J: the Week 6 image set integration and the checker. Both reviewed each other's PRs. | both |
| What would you do differently? | Start the eval earlier; our spec's default critic lost to a cheaper model. | either |

## Rules for both of us
- Keep to 10 minutes. Cut the second demo topic or the second failure story before running over.
- Don't read from the repo for more than a few seconds at a time.
- If the live demo fails, switch to the backup within 10 seconds and say what went wrong.
- Everything we say has to be something we can explain if asked.
