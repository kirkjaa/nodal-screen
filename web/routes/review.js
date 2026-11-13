import { badge } from "../lib/badge.js";
import { loadIndex, loadSession } from "../lib/data.js";

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

export async function render(root, ctx) {
  if (ctx.pid) await renderDetail(root, ctx);
  else await renderQueue(root, ctx);
}

async function renderQueue(root, ctx) {
  const { t } = ctx;
  const index = await loadIndex();
  const rows = [];
  for (const pid of index.pids || []) {
    const session = await loadSession(pid);
    if (session && inQueue(session)) rows.push(session);
  }
  const title = document.createElement("h1");
  title.textContent = t("heading.review");
  const list = document.createElement("div");
  list.className = "queue";
  if (!rows.length) {
    list.append(p(t("review.empty")));
  }
  for (const session of rows) {
    const pid = session.participant?.pid || "";
    const link = document.createElement("a");
    link.className = "card";
    link.href = `#/review/${encodeURIComponent(pid)}`;
    const name = document.createElement("strong");
    name.textContent = session.participant?.display_name || pid;
    link.append(
      badge(session.provenance, t),
      name,
      p(`${pid} · ${groupLabel(t, session.participant?.group)} · ${t("review.age")} ${session.participant?.age_y ?? ""}`),
      p(queueSummary(session, t)),
      p(pathwayLabel(t, session.suggested_pathway?.code)),
    );
    list.append(link);
  }
  root.replaceChildren(title, badge(rows[0]?.provenance || "synthetic", t), p(t("review.lead"), "lead"), list);
}

async function renderDetail(root, ctx) {
  const { t, pid } = ctx;
  const title = document.createElement("h1");
  title.textContent = t("heading.review");
  const session = await loadSession(pid);
  if (!session) {
    root.replaceChildren(title, p(t("missing")));
    return;
  }
  const back = document.createElement("a");
  back.className = "text-link";
  back.href = "#/review";
  back.textContent = t("review.back");
  const report = document.createElement("a");
  report.className = "text-link";
  report.href = `#/p/${encodeURIComponent(pid)}`;
  report.textContent = t("review.report");
  const flags = document.createElement("div");
  for (const flag of session.flags || []) {
    const block = document.createElement("div");
    block.className = flag.severity === "watch" ? "flag watch" : "flag";
    const sources = (flag.source_ids || []).map((id) => sourceName(t, id)).join(", ");
    block.append(
      p(flag.title || flag.id || ""),
      p(`${t("review.evidence")}: ${flag.evidence || ""}`),
      p(`${t("review.confidence")}: ${named(t, flag.confidence)}`),
      p(`${t("review.source")}: ${sources}`),
    );
    flags.append(block);
  }
  const notes = (session.qc?.notes || []).filter(Boolean).join(" ");
  const noteLine = notes ? p(`${t("qc.notes")}: ${notes}`) : null;
  const decisionLabel = document.createElement("h2");
  decisionLabel.textContent = t("review.decision");
  const actions = document.createElement("div");
  actions.className = "actions";
  const buttons = {};
  const pathwayField = document.createElement("label");
  pathwayField.className = "field";
  const pathwayName = document.createElement("span");
  pathwayName.textContent = t("review.pathway");
  const select = document.createElement("select");
  const suggested = session.suggested_pathway?.code || "";
  for (const code of pathwayCodes(suggested)) {
    const option = document.createElement("option");
    option.value = code;
    option.textContent = pathwayLabel(t, code);
    select.append(option);
  }
  if (suggested) select.value = suggested;
  pathwayField.append(pathwayName, select);
  const noteField = document.createElement("label");
  noteField.className = "field";
  const noteName = document.createElement("span");
  noteName.textContent = t("review.note");
  const note = document.createElement("textarea");
  noteField.append(noteName, note);
  const kept = p(t("review.local"));
  const status = p("");
  const fhirLead = p(t("review.fhir.lead"));
  const fhirHost = document.createElement("div");

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
    const heading = document.createElement("h2");
    heading.textContent = t("review.fhir.heading");
    const line = p(`${t("review.fhir.status")}: ${resource.status}. ${t("review.fhir.subject")}: ${pid}. ${t("review.fhir.reason")}: ${reason}`);
    const pre = document.createElement("pre");
    pre.id = "fhir";
    pre.className = "fhir";
    pre.textContent = JSON.stringify(resource, null, 2);
    fhirHost.replaceChildren(heading, line, pre);
    status.textContent = t("review.saved");
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
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.decision = decision;
    button.setAttribute("aria-pressed", "false");
    button.textContent = t(`review.${decision}`);
    button.addEventListener("click", () => save(decision));
    buttons[decision] = button;
    actions.append(button);
  }

  const saved = readReview(pid);
  if (saved && DECISIONS.includes(saved.decision)) showDecision(saved);

  const parts = [
    title,
    badge(session.provenance, t),
    back,
    p(`${session.participant?.display_name || ""} · ${pid} · ${groupLabel(t, session.participant?.group)} · ${t("review.age")} ${session.participant?.age_y ?? ""}`),
    report,
    flags,
  ];
  if (noteLine) parts.push(noteLine);
  parts.push(decisionLabel, actions, pathwayField, noteField, kept, status, fhirLead, fhirHost);
  root.replaceChildren(...parts);
}
