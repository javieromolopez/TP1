// One screen: pick a topic, press Generate, render the image and the critique.
// Model output is untrusted, so it only ever goes into the page through textContent.

const $ = (id) => document.getElementById(id);

const MARKS = { present: "✓", missing: "✗", mislabeled: "✗", unclear: "?" };
const VERDICTS = { good: "Good", needs_work: "Needs work", poor: "Poor" };
const PROBLEMS = { garbled: "garbled", misspelled: "misspelled", wrong_part: "on the wrong part" };

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function fillList(list, items, empty) {
  list.replaceChildren();
  if (items.length === 0) items = [{ text: empty, kind: "none" }];
  for (const item of items) {
    const li = el("li", undefined, item.kind);
    if (item.mark) li.append(el("span", item.mark, "mark"));
    li.append(el("span", item.text));
    list.append(li);
  }
}

async function loadTopics() {
  const response = await fetch("/api/topics");
  const topics = await response.json();
  $("topic").replaceChildren(...topics.map((t) => {
    const option = el("option", t.display_name);
    option.value = t.id;
    return option;
  }));
}

function renderCritique(body) {
  const critique = body.critique;
  $("critique").hidden = !critique;
  $("critique-error").hidden = !body.critique_error;
  $("critique-error").textContent = body.critique_error || "";
  $("checklist").replaceChildren();
  $("verdict").hidden = true;
  if (!critique) return;

  for (const part of critique.parts) {
    const row = el("tr", undefined, `part-row ${part.status}`);
    row.append(el("td", part.name));
    const mark = el("td", undefined, "mark-cell");
    mark.append(el("span", MARKS[part.status] || "?", "mark"), el("span", ` ${part.status}`, "status-word"));
    row.append(mark, el("td", part.note || ""));
    $("checklist").append(row);
  }

  fillList($("forbidden"), critique.forbidden_found.map((name) => (
    { mark: "✗", text: `${name} is drawn but should not be there`, kind: "bad" }
  )), "Nothing extra was drawn.");

  const ruleText = Object.fromEntries((body.arrangement_rules || []).map((r) => [r.id, r.text]));
  fillList($("arrangement"), critique.arrangement.map((a) => ({
    mark: a.ok ? "✓" : "✗",
    // The critic's note on a passing rule usually restates the rule, so it is shown only on a failure.
    text: `${a.rule}. ${ruleText[a.rule] || ""}${!a.ok && a.note ? ` (${a.note})` : ""}`,
    kind: a.ok ? "good" : "bad",
  })), "No arrangement rules were checked.");

  fillList($("text-issues"), critique.text_issues.map((t) => (
    { mark: "✗", text: `"${t.label_text}" is ${PROBLEMS[t.problem] || t.problem}`, kind: "bad" }
  )), "Every label reads correctly.");

  $("narrative").textContent = critique.narrative;
  $("verdict").textContent = VERDICTS[body.verdict] || body.verdict;
  $("verdict").dataset.verdict = body.verdict;
  $("verdict").hidden = false;
}

function render(body) {
  $("diagram").hidden = !body.image;
  if (body.image) $("diagram").src = body.image;
  $("hidden-notice").hidden = !body.image_hidden_reason;
  $("hidden-notice").textContent = body.image_hidden_reason || "";
  $("caption").hidden = !body.image;
  renderCritique(body);
  $("result").hidden = false;
}

async function generate(event) {
  event.preventDefault();
  const button = $("generate");
  if (button.disabled) return;
  button.disabled = true; // one click, one paid call
  $("error").hidden = true;

  const started = Date.now();
  const tick = () => {
    $("status").textContent = `Drawing and checking the diagram… ${Math.floor((Date.now() - started) / 1000)} s`;
  };
  tick();
  $("status").hidden = false;
  const timer = setInterval(tick, 1000);

  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic_id: $("topic").value }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      $("result").hidden = true;
      $("error").textContent = `${body.detail || `The server answered ${response.status}.`} Press Generate diagram to try again.`;
      $("error").hidden = false;
      return;
    }
    render(body);
  } catch {
    $("result").hidden = true;
    $("error").textContent = "Could not reach the server. Check that it is running, then try again.";
    $("error").hidden = false;
  } finally {
    clearInterval(timer);
    $("status").hidden = true;
    button.disabled = false;
  }
}

$("controls").addEventListener("submit", generate);
loadTopics();
