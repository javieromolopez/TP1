// One page: pick a topic, press Generate, render the diagram and its marked checklist.
// Model output is untrusted, so it only ever reaches the page through textContent.

const $ = (id) => document.getElementById(id);

const TOPIC_ICONS = {
  "plant-cell": "🌱", "animal-cell": "🧫", "water-cycle": "💧", "simple-circuit": "💡", "flower": "🌸",
};
const STATUS = {
  present: { icon: "i-check", label: "Present", tone: "good" },
  missing: { icon: "i-x", label: "Missing", tone: "bad" },
  mislabeled: { icon: "i-x", label: "Mislabeled", tone: "bad" },
  unclear: { icon: "i-question", label: "Unclear", tone: "warn" },
};
const VERDICTS = { good: "Good", needs_work: "Needs work", poor: "Poor" };
const PROBLEMS = { garbled: "garbled", misspelled: "misspelled", wrong_part: "on the wrong part" };

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function icon(id) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "icon");
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `#${id}`);
  svg.append(use);
  return svg;
}

function pill(status) {
  const s = STATUS[status] || STATUS.unclear;
  const span = el("span", undefined, `pill ${s.tone}`);
  span.append(icon(s.icon), el("span", s.label));
  return span;
}

// A list where each item is { ok, text }; an empty list shows `empty` as a passing line.
function fillList(list, countBadge, items, empty) {
  list.replaceChildren();
  const problems = items.filter((i) => !i.ok).length;
  countBadge.textContent = items.length ? (problems ? `${problems} to fix` : "all good") : "none";
  countBadge.className = `count ${problems ? "bad" : "good"}`;
  for (const item of items.length ? items : [{ ok: true, text: empty, quiet: true }]) {
    const li = el("li", undefined, item.quiet ? "quiet" : "");
    const mark = el("span", undefined, `mark ${item.ok ? "good" : "bad"}`);
    mark.append(icon(item.ok ? "i-check" : "i-x"));
    li.append(mark, el("span", item.text));
    list.append(li);
  }
}

async function loadTopics() {
  const topics = await (await fetch("/api/topics")).json();
  $("topics").replaceChildren(...topics.map((t, i) => {
    const card = el("label", undefined, "topic-card");
    const input = el("input");
    Object.assign(input, { type: "radio", name: "topic", value: t.id, checked: i === 0 });
    card.append(input, el("span", TOPIC_ICONS[t.id] || "📘", "topic-icon"), el("span", t.display_name, "topic-name"));
    return card;
  }));
}

function setFilter(filter) {
  for (const chip of document.querySelectorAll(".chip")) {
    chip.setAttribute("aria-pressed", String(chip.dataset.filter === filter));
  }
  let shown = 0;
  for (const row of $("checklist").rows) {
    row.hidden = filter === "problems" && row.dataset.status === "present";
    if (!row.hidden) shown += 1;
  }
  $("no-problems").hidden = shown > 0;
}

function renderCritique(body) {
  const critique = body.critique;
  $("critique").hidden = !critique;
  $("summary").hidden = !critique;
  $("critique-error").hidden = !body.critique_error;
  $("critique-error").textContent = body.critique_error || "";
  $("checklist").replaceChildren();
  if (!critique) return;

  for (const part of critique.parts) {
    const row = el("tr", undefined, "part-row");
    row.dataset.status = part.status;
    const mark = el("td");
    mark.append(pill(part.status));
    row.append(el("td", part.name, "part-name"), mark, el("td", part.note || "", "part-note"));
    $("checklist").append(row);
  }
  const correct = critique.parts.filter((p) => p.status === "present").length;
  $("problem-count").textContent = critique.parts.length - correct;
  setFilter("all");

  const rules = Object.fromEntries((body.arrangement_rules || []).map((r) => [r.id, r.text]));
  fillList($("arrangement"), $("arrangement-count"), critique.arrangement.map((a) => ({
    ok: a.ok,
    // A passing rule's note usually restates the rule, so the note is shown only on a failure.
    text: `${a.rule} · ${rules[a.rule] || ""}${!a.ok && a.note ? ` (${a.note})` : ""}`,
  })), "No arrangement rules were checked.");
  fillList($("text-issues"), $("text-count"), critique.text_issues.map((t) => (
    { ok: false, text: `“${t.label_text}” is ${PROBLEMS[t.problem] || t.problem}` }
  )), "Every label reads correctly.");
  fillList($("forbidden"), $("forbidden-count"), critique.forbidden_found.map((name) => (
    { ok: false, text: `${name} is drawn but should not be there` }
  )), "Nothing extra was drawn.");

  $("narrative").textContent = critique.narrative;
  $("score").textContent = `${correct} of ${critique.parts.length} parts correct`;
  $("verdict").textContent = VERDICTS[body.verdict] || body.verdict;
  $("verdict").dataset.verdict = body.verdict;
  $("verdict").hidden = false;
  $("summary").dataset.verdict = body.verdict;
}

function render(body, seconds) {
  $("diagram").hidden = !body.image;
  if (body.image) $("diagram").src = body.image;
  $("hidden-notice").hidden = !body.image_hidden_reason;
  $("hidden-notice").textContent = body.image_hidden_reason || "";
  $("caption").hidden = !body.image;
  renderCritique(body);
  $("run-meta").textContent = `Generated in ${seconds} s`;
  $("result").hidden = false;
}

function showError(message) {
  $("result").hidden = true;
  $("error").textContent = `${message} Press Generate diagram to try again.`;
  $("error").hidden = false;
}

async function generate(event) {
  event.preventDefault();
  const button = $("generate");
  if (button.disabled) return;
  button.disabled = true; // one click, one paid call
  $("error").hidden = true;
  $("result").hidden = true;
  $("loading").hidden = false;

  const started = Date.now();
  const seconds = () => Math.floor((Date.now() - started) / 1000);
  const tick = () => { $("status").textContent = `Drawing the diagram and checking it · ${seconds()} s`; };
  tick();
  $("status").hidden = false;
  const timer = setInterval(tick, 1000);

  try {
    const topicId = document.querySelector('input[name="topic"]:checked').value;
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic_id: topicId }),
    });
    const body = await response.json().catch(() => ({}));
    if (response.ok) render(body, seconds());
    else showError(body.detail || `The server answered ${response.status}.`);
  } catch {
    showError("Could not reach the server. Check that it is running.");
  } finally {
    clearInterval(timer);
    $("status").hidden = true;
    $("loading").hidden = true;
    button.disabled = false;
  }
}

$("controls").addEventListener("submit", generate);
for (const chip of document.querySelectorAll(".chip")) {
  chip.addEventListener("click", () => setFilter(chip.dataset.filter));
}
loadTopics();
