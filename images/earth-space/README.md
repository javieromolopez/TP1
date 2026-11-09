# Earth and space image set (Week 6, Ralston)

Five FLUX.2 klein diagrams from one prompt family (seeds 501–505), each critiqued by `minimax/minimax-m3` and `xiaomi/mimo-v2.6-flash` against a yes/no checklist, and checked in code. Generated in the Week 6 lab ([`cpsc415-week05/week06`](https://github.com/ralstonraphael/cpsc415-week05/tree/main/week06)); `CHECKS.md` there records the costs, the disagreements, and what a person saw.

| File | What it is |
|---|---|
| `*.jpg` + `manifest.json` | The images, with prompt, seed, requirements, expected title, model, media type and `usage.cost` ($0.014 each). |
| `critique-minimax.json`, `critique-mimo.json` | Both critics' checklists and title reads. |

What it showed for this app: 0 of 5 pass. Every image has garbled labels, which both critics accepted as "labels". One title was misspelled ("Volacno Cros-Sectom"), and only the narrow read compared in code caught it. That finding is why `app/label_check.py` transcribes labels and compares them in code instead of trusting `text_issues`.
