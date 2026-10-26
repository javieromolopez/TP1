# Checks

Model comparisons and the eval for plan step 13 (spec behaviors 16–17). Run October 26, 2026, on `build/eval-13`, through OpenRouter.

## 1. The eval set

Ten diagrams in `eval/images/`, one good and one deliberately flawed per topic, with hand-checked expected statuses in `eval/expected.json`. Each entry has a `note` on how it was made.

| Topic | Good | Planted flaw |
|---|---|---|
| plant-cell | correct | **vacuole missing** (so A3 also fails) |
| animal-cell | correct | **chloroplast** drawn and labeled (forbidden) |
| water-cycle | correct | evaporation spelled **"evaparashun"** |
| simple-circuit | correct, + and − marked | **"wire" label points into the battery**; "battery" label floats. This is the real image from our first end-to-end run, which GPT-4o graded good. |
| flower | correct | **anther and stigma labels swapped**; the model also left out "pistil" |

**How the set was made, honestly:**
- **First attempt, Nano Banana:** every "good" image had garbled or misplaced labels (see section 3), so none could serve as a correct reference.
- **Final set:** the good images and the planted flaws were made with Nano Banana Pro. Some needed more than one try.
- **Two images were reassigned:** one image the model was told to flaw came out clean, so it became the good image. The "good" circuit from the app's own prompt failed A2 (no + and −), so the final one adds "mark the + and − terminals" to the prompt. Prompts are in `eval/images/prompts*.json`.
- **Who checked them:** Claude Code checked each image label by label and wrote `expected.json`. **Ralston and Javier should spot-check the five flawed entries before the presentation.**

## 2. Critic comparison (behavior 16)

`python eval/run_eval.py critic --model <model> --repeats 3`. That's 10 images × 3 repeats = 30 calls per model, all on the same images and prompt.

| Critic | Valid first try | Mean part accuracy | False flags on good images | Planted flaws caught | Tokens in / out | Cost (30 calls) | Behavior 16 |
|---|---|---|---|---|---|---|---|
| `openai/gpt-4o` (spec default) | 100% | 0.92 | 0 | **9 / 15** | 45,719 / 10,691 | $0.20 | **FAIL** |
| `xiaomi/mimo-v2.6-flash` (cheap comparison) | 100% | 0.97 | 0 | **15 / 15** | 43,764 / 37,750 | $0.013 | **PASS** |

**What GPT-4o missed, the same way all 3 times:**
- **`simple-circuit-flawed`:** it marked every part present and gave the verdict **good**, the same false pass as on Oct 25.
- **`flower-flawed`:** it did not notice the anther and stigma labels were swapped (verdict needs_work, but only for the missing pistil label).
- **What the two misses share:** both are a label pointing at the wrong part. GPT-4o reads label *text* reliably, but does not trace where leader lines go.

**What mimo said on the same two**, from one reply each:
- "The wire label points to the battery, not a drawn wire."
- "[anther] Label points to the top of the pistil, not the pollen tip." It also flagged the missing pistil label and the stigma swap.

**Costs of the cheap model:**
- **Hidden reasoning:** mimo writes far more output tokens. One flower reply used 6,806 output tokens, against about 700 normally. It is still $0.002, but latency varies.
- **No timeouts in these runs,** but the critic's 30 s timeout is the risk to watch.

**Decision rule from the spec:** "If the cheap model matches GPT-4o on false flags and per-part accuracy within one part per image, we propose switching in a new intent." mimo matches on false flags (both 0), beats GPT-4o on accuracy, and catches six more flaws at about 1/15 the cost. **Recommendation: a new intent to switch the critic to `xiaomi/mimo-v2.6-flash`.** The code is not changed here, because the intent comes first.

<details><summary>Per-call tables</summary>

**openai/gpt-4o**

| Image | Kind | Valid (1st try) | Part acc. | False flags | Flaw caught | Verdict | Tokens in/out | Cost |
|---|---|---|---|---|---|---|---|---|
| animal-cell-flawed.png | flawed | yes | 1.00 | 0 | yes | poor | 1517/358 | $0.0074 |
| animal-cell-flawed.png | flawed | yes | 1.00 | 0 | yes | poor | 1517/353 | $0.0056 |
| animal-cell-flawed.png | flawed | yes | 1.00 | 0 | yes | poor | 1517/363 | $0.0057 |
| animal-cell-good.png | good | yes | 1.00 | 0 | - | good | 1517/390 | $0.0077 |
| animal-cell-good.png | good | yes | 1.00 | 0 | - | good | 1517/389 | $0.0059 |
| animal-cell-good.png | good | yes | 1.00 | 0 | - | good | 1517/389 | $0.0059 |
| flower-flawed.png | flawed | yes | 0.78 | 0 | no | needs_work | 1519/425 | $0.0080 |
| flower-flawed.png | flawed | yes | 0.78 | 0 | no | needs_work | 1519/419 | $0.0062 |
| flower-flawed.png | flawed | yes | 0.78 | 0 | no | needs_work | 1519/413 | $0.0062 |
| flower-good.png | good | yes | 1.00 | 0 | - | good | 1519/428 | $0.0081 |
| flower-good.png | good | yes | 1.00 | 0 | - | good | 1519/407 | $0.0061 |
| flower-good.png | good | yes | 1.00 | 0 | - | good | 1519/421 | $0.0062 |
| plant-cell-flawed.png | flawed | yes | 1.00 | 0 | yes | needs_work | 1513/347 | $0.0073 |
| plant-cell-flawed.png | flawed | yes | 1.00 | 0 | yes | needs_work | 1710/355 | $0.0078 |
| plant-cell-flawed.png | flawed | yes | 1.00 | 0 | yes | needs_work | 1710/357 | $0.0078 |
| plant-cell-good.png | good | yes | 1.00 | 0 | - | good | 1710/357 | $0.0078 |
| plant-cell-good.png | good | yes | 1.00 | 0 | - | good | 1710/355 | $0.0078 |
| plant-cell-good.png | good | yes | 1.00 | 0 | - | good | 1513/349 | $0.0073 |
| simple-circuit-flawed.png | flawed | yes | 0.50 | 0 | no | good | 1285/272 | $0.0059 |
| simple-circuit-flawed.png | flawed | yes | 0.50 | 0 | no | good | 1147/270 | $0.0056 |
| simple-circuit-flawed.png | flawed | yes | 0.50 | 0 | no | good | 1147/266 | $0.0055 |
| simple-circuit-good.png | good | yes | 1.00 | 0 | - | good | 1684/270 | $0.0069 |
| simple-circuit-good.png | good | yes | 1.00 | 0 | - | good | 1684/271 | $0.0069 |
| simple-circuit-good.png | good | yes | 1.00 | 0 | - | good | 1684/277 | $0.0070 |
| water-cycle-flawed.png | flawed | yes | 1.00 | 0 | yes | needs_work | 1501/379 | $0.0075 |
| water-cycle-flawed.png | flawed | yes | 0.86 | 0 | yes | needs_work | 1501/367 | $0.0057 |
| water-cycle-flawed.png | flawed | yes | 1.00 | 0 | yes | needs_work | 1501/379 | $0.0058 |
| water-cycle-good.png | good | yes | 1.00 | 0 | - | good | 1501/355 | $0.0073 |
| water-cycle-good.png | good | yes | 1.00 | 0 | - | good | 1501/355 | $0.0055 |
| water-cycle-good.png | good | yes | 1.00 | 0 | - | good | 1501/355 | $0.0073 |

**xiaomi/mimo-v2.6-flash**

| Image | Kind | Valid (1st try) | Part acc. | False flags | Flaw caught | Verdict | Tokens in/out | Cost |
|---|---|---|---|---|---|---|---|---|
| animal-cell-flawed.png | flawed | yes | 1.00 | 0 | yes | poor | 1476/1157 | $0.0005 |
| animal-cell-flawed.png | flawed | yes | 1.00 | 0 | yes | poor | 1476/1413 | $0.0006 |
| animal-cell-flawed.png | flawed | yes | 1.00 | 0 | yes | poor | 1476/620 | $0.0002 |
| animal-cell-good.png | good | yes | 1.00 | 0 | - | good | 1476/630 | $0.0004 |
| animal-cell-good.png | good | yes | 1.00 | 0 | - | good | 1476/610 | $0.0002 |
| animal-cell-good.png | good | yes | 1.00 | 0 | - | good | 1476/606 | $0.0004 |
| flower-flawed.png | flawed | yes | 1.00 | 0 | yes | needs_work | 1472/681 | $0.0004 |
| flower-flawed.png | flawed | yes | 1.00 | 0 | yes | needs_work | 1472/810 | $0.0002 |
| flower-flawed.png | flawed | yes | 1.00 | 0 | yes | needs_work | 1472/6806 | $0.0019 |
| flower-good.png | good | yes | 1.00 | 0 | - | good | 1472/1055 | $0.0005 |
| flower-good.png | good | yes | 1.00 | 0 | - | good | 1472/793 | $0.0002 |
| flower-good.png | good | yes | 1.00 | 0 | - | good | 1472/720 | $0.0002 |
| plant-cell-flawed.png | flawed | yes | 1.00 | 0 | yes | needs_work | 1468/753 | $0.0004 |
| plant-cell-flawed.png | flawed | yes | 1.00 | 0 | yes | needs_work | 1468/1565 | $0.0004 |
| plant-cell-flawed.png | flawed | yes | 1.00 | 0 | yes | needs_work | 1468/5195 | $0.0015 |
| plant-cell-good.png | good | yes | 1.00 | 0 | - | good | 1468/609 | $0.0004 |
| plant-cell-good.png | good | yes | 1.00 | 0 | - | good | 1468/1668 | $0.0005 |
| plant-cell-good.png | good | yes | 1.00 | 0 | - | good | 1468/1771 | $0.0005 |
| simple-circuit-flawed.png | flawed | yes | 0.75 | 0 | yes | needs_work | 1408/533 | $0.0003 |
| simple-circuit-flawed.png | flawed | yes | 0.75 | 0 | yes | needs_work | 1408/772 | $0.0002 |
| simple-circuit-flawed.png | flawed | yes | 0.75 | 0 | yes | needs_work | 1408/795 | $0.0002 |
| simple-circuit-good.png | good | yes | 1.00 | 0 | - | good | 1440/2041 | $0.0008 |
| simple-circuit-good.png | good | yes | 1.00 | 0 | - | good | 1440/494 | $0.0001 |
| simple-circuit-good.png | good | yes | 1.00 | 0 | - | good | 1440/624 | $0.0002 |
| water-cycle-flawed.png | flawed | yes | 1.00 | 0 | yes | needs_work | 1454/880 | $0.0004 |
| water-cycle-flawed.png | flawed | yes | 1.00 | 0 | yes | needs_work | 1454/968 | $0.0005 |
| water-cycle-flawed.png | flawed | yes | 1.00 | 0 | yes | needs_work | 1454/1051 | $0.0003 |
| water-cycle-good.png | good | yes | 1.00 | 0 | - | good | 1454/767 | $0.0004 |
| water-cycle-good.png | good | yes | 1.00 | 0 | - | good | 1454/643 | $0.0002 |
| water-cycle-good.png | good | yes | 1.00 | 0 | - | good | 1454/720 | $0.0002 |

</details>

## 3. Generator comparison

`python eval/run_eval.py generate --model <model> --runs 3`. That's 5 topics × 3 runs = 15 images per model, all from the app's unchanged prompt.

**How they were scored:** by looking at every image. Claude Code did the scoring; the contact sheets are in `eval/generator-comparison/` (Flash on the top row, Pro below), so anyone can check.

The columns:
- **Labels ok:** every required label is present and points at its part.
- **Garbled:** at least one misspelled or garbled label.
- **Flat:** no gradients or photo shading.

| Topic | Flash: labels ok | Flash: garbled | Flash: flat | Pro: labels ok | Pro: garbled | Pro: flat |
|---|---|---|---|---|---|---|
| plant-cell | 0/3 | 3/3 ("CELL MEMRANE", "chlorclospast", "vacuule") | 3/3 | 3/3 | 1/3 ("chloplast") | 3/3 |
| animal-cell | 0/3 | 3/3 ("mitohinotrion", "enderapemic retriclum") | 3/3 | 3/3 | 0/3 | 3/3 |
| water-cycle | 0/3 | 3/3 ("evaparation", "preciptation") | 3/3 | 3/3 | 0/3 | 1/3 (runs 2–3 shade water and mountains) |
| simple-circuit | 2/3 (run 2's labels float) | 0/3 | 3/3 | 3/3 | 0/3 | 3/3 |
| flower | 0/3 (labels on wrong parts, "style" twice) | 0/3 | 3/3 | 3/3 | 0/3 | 3/3 |
| **Total** | **2/15** | **9/15** | **15/15** | **15/15** | **1/15** | **13/15** |

| Model | Cost per image | Mean latency | 15 images |
|---|---|---|---|
| `google/gemini-2.5-flash-image` (Nano Banana, spec default) | $0.039 | 6.4 s | $0.58 |
| `google/gemini-3-pro-image` (Nano Banana Pro) | $0.138 | 19.6 s | $2.08 |

**Decision rule from the spec:** "We keep Nano Banana unless Pro removes garbled labels on topics where Nano Banana fails more than 1 in 3 runs. If that happens, we update the intent before switching."
- **The rule triggers.** Nano Banana garbles or misplaces labels on four of five topics in every run, and Pro fixes both.
- **The catch is cost.** A Pro image plus a mimo critique is about $0.14 a run (under the $0.25 per-run ceiling), and about 20 s plus the critique (under 45 s). But the spec's 250-run semester estimate becomes about $35, over the intent's $25 budget. **That trade-off is a team decision for the new intent.**

## 4. End-to-end runs (behavior 17)

Real runs through the app with the current models (Nano Banana + GPT-4o):

| Date | Topic | Time | Cost | Within 45 s and $0.25? |
|---|---|---|---|---|
| Oct 25 | simple-circuit | 13.8 s | $0.044 | yes |
| Oct 25 | animal-cell (browser) | 15.0 s | $0.047 | yes |
| Oct 26 | flower (browser) | 12.9 s | $0.046 | yes |

## 5. Findings for the presentation and `ANNOTATION.md`

1. **The critic was confidently wrong.** GPT-4o graded a mislabeled circuit "good" four times (once on Oct 25, three times here). The spec's eval existed to catch exactly this, and it did.
2. **The cheaper model was better at this task:** 15/15 against 9/15, at 1/15 the price.
3. **The prompt and the checklist disagree.** Rule A2 requires + and − terminals, but the image prompt never asks for them, so a correct-looking circuit can fail A2. This should be fixed in `topics.json` or the prompt builder through the new intent.
4. **Nano Banana could not produce a single fully correct cell, water-cycle or flower diagram** in 9 tries.

## 6. Spend

The eval work on Oct 26 cost about $5.80 of OpenRouter credit:
- **Eval set:** about $2.20. That covers the first Flash attempt and several Pro tries, since some images came out wrong.
- **Generator comparison:** $2.66.
- **Critic comparison:** $0.21.
- **Spot checks:** a few cents.

Total on the key so far: **$6.07**. That includes the earlier development runs and other coursework.
