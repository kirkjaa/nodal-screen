import { badge } from "../lib/badge.js";
import { loadIndex, loadSession } from "../lib/data.js";
import { loadReplay, renderStage } from "../lib/replay.js";

const PATHWAYS = [
  "RECAPTURE",
  "WCV_DEV_REVIEW",
  "FALLS_PREVENTION",
  "ADULT_SARCOPENIA",
  "CLINICIAN_SPECIALIST",
  "ADULT_EARLY_REVIEW",
  "ROUTINE",
];

const DECISIONS = ["confirm", "dismiss", "recapture"];

function reviewKey(pid) {
  return `nodal-screen-review-${pid}`;
}

function readReview(pid) {
  try {
    const raw = localStorage.getItem(reviewKey(pid));
    if (!raw) return null;
    const data = JSON.parse(raw);
    return data && typeof data === "object" ? data : null;
  } catch {
    return null;
  }
}

function writeReview(pid, review) {
  try {
    localStorage.setItem(reviewKey(pid), JSON.stringify(review));
    return true;
  } catch {
    return false;
  }
}

function named(t, value) {
  const key = `qc.value.${value}`;
  const label = t(key);
  return label === key ? String(value ?? "") : label;
}

function sourceName(t, sourceId) {
  const key = `source.${sourceId}`;
  const label = t(key);
  return label === key ? sourceId : label;
}

function pathwayLabel(t, code) {
  const key = `pathway.${code}`;
  const label = t(key);
  return label === key ? (code || "") : label;
}

function groupLabel(t, group) {
  const key = `group.${group}`;
  const label = t(key);
  return label === key ? (group || "") : label;
}

function pathwayCodes(selected) {
  if (selected && PATHWAYS.includes(selected)) {
    return [selected, ...PATHWAYS.filter((code) => code !== selected)];
  }
  return PATHWAYS.slice();
}

function reasonText(session) {
  const flags = session.flags || [];
  if (flags.length) return flags.map((flag) => flag.title).filter(Boolean).join("; ");
  return (session.qc?.notes || []).filter(Boolean).join(" ");
}

function queueSummary(session, t) {
  const flags = session.flags || [];
  if (flags.length && flags[0].title) return flags[0].title;
  const notes = (session.qc?.notes || []).filter(Boolean).join(" ");
  return notes || t("qc.value.insufficient");
}

function inQueue(session) {
  return (session.flags || []).length > 0 || session.qc?.status === "insufficient";
}

function p(text, className) {
  const node = document.createElement("p");
  if (className) node.className = className;
  node.textContent = text;
  return node;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function bdi(text) {
  const node = document.createElement("bdi");
  node.textContent = text == null ? "" : String(text);
  return node;
}

function counts(session) {
  const flags = session.flags || [];
  return {
    flags: flags.filter((f) => f.severity === "flag").length,
    watches: flags.filter((f) => f.severity === "watch").length,
  };
}

function severity(session) {
  if (session.qc?.status === "insufficient") return "red";
  const c = counts(session);
  return c.flags ? "red" : c.watches ? "amb" : "grn";
}

function decisionChip(t, review) {
  if (!review || !DECISIONS.includes(review.decision)) return el("span", "chip mono", t("review.pending"));
  const cls = review.decision === "confirm" ? "" : review.decision === "dismiss" ? "" : "bad";
  return el("span", `chip mono ${cls}`, t(`review.${review.decision}`));
}

export async function render(root, ctx) {
  if (ctx.pid) await renderDetail(root, ctx);
  else await renderQueue(root, ctx);
}

async function renderQueue(root, ctx) {
  const { t } = ctx;
  root.classList.add("wide");
  const index = await loadIndex();
  const rows = [];
  for (const pid of index.pids || []) {
    const session = await loadSession(pid);
    if (session && inQueue(session)) rows.push(session);
  }
  const rank = { red: 0, amb: 1, grn: 2 };
  rows.sort((a, b) => rank[severity(a)] - rank[severity(b)]);

  const head = el("div", "rp-head");
  const hl = el("div");
  hl.append(el("h1", "", t("heading.review")), el("p", "mono crumb", t("review.lead")));
  const chips = el("div", "chips");
  const c1 = el("span", "chip mono");
  c1.append(el("i"), document.createTextNode(`${rows.length} ${t("review.cases")}`));
  const c2 = el("span", "chip mono sample");
  c2.append(el("i"), document.createTextNode(t("review.local")));
  chips.append(c1, c2);
  head.append(hl, chips);

  const list = el("div", "case-list");
  if (!rows.length) list.append(el("p", "muted", t("review.empty")));
  for (const session of rows) {
    const pid = session.participant?.pid || "";
    const c = counts(session);
    const link = el("a", `case ${severity(session)}`);
    link.href = `#/review/${encodeURIComponent(pid)}`;
    const who = el("div", "case-who");
    who.append(el("strong", "", session.participant?.display_name || pid));
    const meta = el("p", "mono k");
    meta.append(bdi(`${pid}  ·  ${groupLabel(t, session.participant?.group)}  ·  ${t("review.age")} ${session.participant?.age_y ?? ""}`));
    who.append(meta);
    const what = el("div", "case-what");
    what.append(el("p", "case-title", queueSummary(session, t)));
    const tally = el("p", "mono k");
    if (session.qc?.status === "insufficient") tally.append(el("span", "red", t("qc.value.insufficient")));
    else {
      tally.append(el("span", c.flags ? "red" : "muted", (c.flags === 1 ? t("report.flag.one") : t("report.flag.many")).replace("{n}", c.flags)));
      tally.append(document.createTextNode("  ·  "));
      tally.append(el("span", c.watches ? "amb" : "muted", (c.watches === 1 ? t("report.watch.one") : t("report.watch.many")).replace("{n}", c.watches)));
    }
    what.append(tally);
    const path = el("p", `case-path ${severity(session)}`, pathwayLabel(t, session.suggested_pathway?.code));
    const state = el("div", "case-state");
    state.append(decisionChip(t, readReview(pid)));
    link.append(who, what, path, state);
    list.append(link);
  }
  const wrap = el("section", "case-wrap");
  wrap.append(list);
  root.replaceChildren(head, wrap);
}

async function renderDetail(root, ctx) {
  const { t, pid } = ctx;
  root.classList.add("wide");
  const session = await loadSession(pid);
  if (!session) {
    root.replaceChildren(el("h1", "", t("heading.review")), p(t("missing")));
    return;
  }
  let replay = null;
  try { replay = await loadReplay(session); } catch { replay = null; }

  // Header
  const head = el("div", "rp-head");
  const hl = el("div");
  hl.append(el("h1", "", session.participant?.display_name || pid));
  const meta = el("p", "mono crumb");
  meta.append(bdi(`${pid}  ·  ${groupLabel(t, session.participant?.group)}  ·  ${t("review.age")} ${session.participant?.age_y ?? ""}  ·  ${session.visit?.date || ""}`));
  hl.append(meta);
  const chips = el("div", "chips");
  const back = el("a", "btn mono", t("review.back"));
  back.href = "#/review";
  const report = el("a", "btn mono", t("review.report"));
  report.href = `#/p/${encodeURIComponent(pid)}`;
  const decisionNow = el("span");
  chips.append(back, report, decisionNow);
  head.append(hl, chips);

  // Left: the case
  const left = el("aside", "side");
  const sug = el("div", "blk");
  sug.append(el("p", "mono k", t("section.pathway")), el("p", `mid ${severity(session)}`, pathwayLabel(t, session.suggested_pathway?.code)));
  left.append(sug);
  const find = el("div", "blk");
  find.append(el("p", "mono k", t("panel.findings")));
  if (!(session.flags || []).length) find.append(el("p", "muted", t("report.none")));
  for (const flag of session.flags || []) {
    const card = el("div", `find${flag.severity === "watch" ? " amb" : ""}`);
    const sources = (flag.source_ids || []).map((id) => sourceName(t, id)).join(" · ");
    card.append(el("span", `mono ${flag.severity === "watch" ? "amb" : "red"}`,
      `${flag.severity === "watch" ? t("report.watch") : t("report.flag")} · ${sources}`));
    card.append(el("span", "find-title", flag.title || flag.id || ""));
    card.append(el("span", "mono faint find-ev", `${t("review.evidence")}: ${flag.evidence || ""}  ·  ${t("review.confidence")}: ${named(t, flag.confidence)}`));
    find.append(card);
  }
  left.append(find);
  const notes = (session.qc?.notes || []).filter(Boolean);
  if (notes.length) {
    const qc = el("div", "blk");
    qc.append(el("p", "mono k red", t("qc.notes")));
    for (const n of notes) qc.append(el("p", "", n));
    left.append(qc);
  }

  // Centre: the movement
  const centre = el("section", "stage");
  const stageBox = el("div", "stage-box");
  centre.append(stageBox);
  if (replay) {
    const curves = el("div", "rp-curves panel-curves");
    curves.dir = "ltr";
    renderStage(stageBox, session, replay, ctx, { curvesInto: curves });
    const tail = el("div", "stage-foot");
    tail.append(el("p", "mono k", t("panel.curves")), curves);
    centre.append(tail);
  } else {
    stageBox.append(el("p", "muted rp-none", t("replay.none")));
  }

  // Right: the decision
  const right = el("aside", "side r");
  const dec = el("div", "blk");
  dec.append(el("p", "mono k", t("review.decision")));
  const actions = el("div", "decide");
  const buttons = {};
  dec.append(actions);
  const pathwayField = el("label", "field");
  pathwayField.append(el("span", "mono k", t("review.pathway")));
  const select = el("select", "cap-select");
  const suggested = session.suggested_pathway?.code || "";
  for (const code of pathwayCodes(suggested)) {
    const option = el("option", "", pathwayLabel(t, code));
    option.value = code;
    select.append(option);
  }
  if (suggested) select.value = suggested;
  pathwayField.append(select);
  const noteField = el("label", "field");
  noteField.append(el("span", "mono k", t("review.note")));
  const note = el("textarea", "decide-note");
  note.rows = 4;
  noteField.append(note);
  const status = el("p", "mono grn decide-status", "");
  dec.append(pathwayField, noteField, status, el("p", "mono faint", t("review.local")));
  const fhir = el("div", "blk");
  fhir.append(el("p", "mono k", t("review.fhir.heading")), el("p", "mono faint", t("review.fhir.lead")));
  const fhirHost = el("div");
  fhir.append(fhirHost);
  right.append(dec, fhir);

  function showDecision(review) {
    for (const [decision, button] of Object.entries(buttons)) {
      button.setAttribute("aria-pressed", decision === review.decision ? "true" : "false");
    }
    if (review.pathway) select.value = review.pathway;
    note.value = review.note || "";
    const reason = reasonText(session);
    const resource = {
      resourceType: "ServiceRequest",
      status: "draft",
      intent: "order",
      subject: { identifier: { value: pid } },
      reasonCode: [{ text: reason }],
    };
    const line = p(`${t("review.fhir.status")}: ${resource.status}. ${t("review.fhir.subject")}: ${pid}. ${t("review.fhir.reason")}: ${reason}`, "mono faint");
    const pre = el("pre", "fhir");
    pre.id = "fhir";
    pre.dir = "ltr";
    pre.textContent = JSON.stringify(resource, null, 2);
    fhirHost.replaceChildren(line, pre);
    status.textContent = t("review.saved");
    decisionNow.replaceChildren(decisionChip(t, review));
  }

  function save(decision) {
    const review = {
      clinician: "CLN-01",
      decision,
      pathway: select.value,
      note: note.value,
      at: new Date().toISOString(),
    };
    if (!writeReview(pid, review)) {
      status.textContent = t("review.keepfail");
      return;
    }
    showDecision(review);
  }

  for (const decision of DECISIONS) {
    const button = el("button", `btn decide-${decision}`, t(`review.${decision}`));
    button.type = "button";
    button.dataset.decision = decision;
    button.setAttribute("aria-pressed", "false");
    button.addEventListener("click", () => save(decision));
    buttons[decision] = button;
    actions.append(button);
  }

  const saved = readReview(pid);
  decisionNow.replaceChildren(decisionChip(t, saved));
  if (saved && DECISIONS.includes(saved.decision)) showDecision(saved);
  else fhirHost.append(p(t("review.fhir.wait"), "muted"));

  const lead = el("div", "rp-lead");
  lead.append(left, centre, right);
  root.replaceChildren(head, lead);
}
