# TP1 presentation plan (draft)

Monday Nov 2, 1:30 PM, MC-225. We get 10 minutes, then 5 minutes of questions. The order is drawn when class starts.

The assignment wants three things: the app running live, one file from our project shown on screen, and one thing that went wrong and what we did about it.

Our audience is CS students. Say "the AI looks at the picture" before you say "vision model."

R = Ralston, J = Javier.

## Before class
- [ ] The server is running and http://localhost:8000 loads (key in `.env`).
- [ ] Run one plant cell to check it works. It takes about 15 seconds and costs about 5 cents.
- [ ] Have screenshots of one good run, in case the network or API fails.
- [ ] Open `spec.md` to the architecture diagram, and `eval/generator-comparison/` for the failure story.
- [ ] Open the peer notes form: https://docs.google.com/forms/d/e/1FAIpQLSfNKbChCap-3fGF5U-2mELJmqkGJPybHt7KplK3F__zngARNA/viewform
- [ ] Zoom the browser in so the back row can read it.

## Timeline

| Time | Who | What |
|---|---|---|
| 0:00 | R | What we built (45 sec) |
| 0:45 | R + J | Live demo (2 min 45 sec) |
| 3:30 | J | The architecture in `spec.md` (2 min 30 sec) |
| 6:00 | R | What went wrong (2 min 30 sec) |
| 8:30 | J | What we'd do next (1 min) |
| 9:30 | R | Wrap up (30 sec) |

## 1. What we built (R)
- AI image tools draw diagrams that look right but often have misspelled or wrong labels. A student can't tell.
- Our app: you pick a science topic, it draws a labeled diagram, and a second AI checks the picture against a checklist.
- The one idea to remember: **the AI says what it sees, and our code decides the grade.**

## 2. Live demo (R clicks, J talks)
- Use the plant cell. Click Generate.
- While it loads, J explains: the app draws the image, adds an "AI-generated" label, then sends the picture to the checker.
- Show the result: the checklist with ✓ and ✗, any label problems, and the final grade (good, needs work, or poor).
- A "needs work" result is fine. Explain what the checker caught.
- Keep code out of this part.

## 3. The architecture in spec.md (J)
Show the diagram at the top of `spec.md`. Go left to right, one sentence per box: page, server, image model, label stamp, checker, grade.

Three points to hit:
1. The checker never sees the prompt we gave the image model. It only sees the picture, so it can't pass something just because we asked for it.
2. The checker doesn't give the grade. It lists which parts it sees, and a small Python function (`verdict.py`) turns that list into good, needs work, or poor.
3. That function is plain code, so we can test it without an API key.

Then point to one line in the spec where we picked a language and a model and wrote down the alternative. This is our project's chain: intent, spec, plan, tests, reviewed pull requests, annotation.

## 4. What went wrong (R)
**Story 1: garbled labels.**
- The cheap image model misspelled or misplaced labels on four of the five topics, every run.
- Show the comparison sheet in `eval/generator-comparison/`: cheap model on top, better model below.
- The better model fixed most of it but costs about 3.5 times as much. That would put the semester over our $25 budget.
- So we didn't switch quietly. We wrote it up as a decision for a new intent.

**Story 2: the checker got fooled** (use if time allows).
- GPT-4o graded a wrong circuit as fine, four times in a row.
- We built a test of 10 images, one good and one with a planted mistake for each topic. It caught this.
- On that test, the cheaper checker found 15 of 15 planted mistakes and GPT-4o found 9 of 15.
- Be honest: we picked that circuit because GPT-4o had already passed it, so the test is a bit unfair to GPT-4o.

## 5. What we'd do next (J)
- Switch to the cheaper checker, through a new intent first.
- Fix the circuit prompt so it asks for + and − on the battery.
- Decide if the better image model is worth the money.
- We've spent about $6.07 so far.

## 6. Wrap up (R)
- One sentence: the AI draws, a second AI looks, and our code decides.
- Say "Questions?" and have the peer form open.

## Questions we might get

| Question | Short answer | Who |
|---|---|---|
| Why not ask the image model if its own picture is right? | It tends to agree with itself. A second model plus a grade from code is harder to fool. | R |
| Why doesn't the checker see the prompt? | It has to judge the picture, not what we asked for. | J |
| What does `checker.py` do? Why exact matching? | It compares the checker's answer to an answer key. Exact matching gives the same result every time and needs no API key. | J |
| How much did it cost? | About $6.07 total, about 5 cents per run. | R |
| What if the AI returns something that isn't JSON? | We retry once. If it fails again the page says "Critique unavailable." It doesn't crash. | R |
| What does the stamp do? | It writes "ai_generated" into the PNG's hidden data and shows a caption. A screenshot would remove the hidden part. | J |
| Who wrote what? | R: generator, checker, server, page, eval. J: the Week 6 image set and `checker.py`. We reviewed each other's PRs. | both |
| What would you change? | Start the eval earlier. Our default checker lost to a cheaper one. | either |

## Ground rules
- Stay under 10 minutes. Cut the second story or second demo topic first.
- Don't read from the repo for more than a few seconds.
- If the demo breaks, switch to the screenshots within 10 seconds and say what happened.
- Only say things we could explain if asked.
