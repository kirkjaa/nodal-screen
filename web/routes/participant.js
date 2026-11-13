import { badge } from "../lib/badge.js";
import { loadSession, metricsOf } from "../lib/data.js";

const COLUMNS = [
  ["col.metric", ""],
  ["col.value", "value"],
  ["col.unit", "unit"],
  ["col.ref", ""],
  ["col.status", ""],
];

function cell(text, className, label) {
  const td = document.createElement("td");
  if (className) td.className = className;
  td.dataset.label = label;
  const span = document.createElement("span");
  span.textContent = text;
  td.append(span);
  return td;
}

function sourceName(t, sourceId) {
  const key = `source.${sourceId}`;
  const label = t(key);
  return label === key ? sourceId : label;
}

function referenceText(metric, t) {
  const parts = [];
  const ref = metric.ref;
  if (ref && ref.kind === "norm" && ref.mean != null) {
    let text = `${t("ref.mean")} ${ref.mean}`;
    if (ref.z != null) text += `, ${t("ref.z")} ${ref.z}`;
    parts.push(text);
  }
  const cutoff = metric.cutoff;
  if (cutoff && cutoff.threshold != null && cutoff.op) {
    const unit = metric.unit ? ` ${metric.unit}` : "";
    parts.push(`${cutoff.op} ${cutoff.threshold}${unit}, ${sourceName(t, cutoff.source_id)}`);
  }
  return parts.length ? parts.join("; ") : t("empty.ref");
}

function named(t, value) {
  if (value == null || value === "") return "";
  return t(`qc.value.${value}`);
}

function curveLabels(session, t) {
  const labels = [];
  for (const task of Object.values(session.tasks || {})) {
    const curves = task.curves;
    if (!curves || typeof curves !== "object") continue;
    for (const [name, curve] of Object.entries(curves)) {
      if (!curve || typeof curve !== "object") continue;
      const points = ["left", "right"].some((side) => Array.isArray(curve[side]) && curve[side].length);
      if (!points) continue;
      const key = `curve.${name}`;
      const label = t(key);
      labels.push(label === key ? name : label);
    }
  }
  return labels;
}

function curveSection(session, t) {
  const labels = curveLabels(session, t);
  if (!labels.length) return [];
  const title = document.createElement("h2");
  title.textContent = t("section.curves");
  const body = document.createElement("p");
  body.textContent = labels.join(", ");
  return [title, body];
}

export async function render(root, ctx) {
  const { t, pid } = ctx;
  const title = document.createElement("h1");
  title.textContent = t("heading.report");
  const session = await loadSession(pid);
  if (!session) {
    const missing = document.createElement("p");
    missing.textContent = t("missing");
    root.replaceChildren(title, missing);
    return;
  }
  const scroller = document.createElement("div");
  scroller.className = "table-scroll";
  const table = document.createElement("table");
  table.className = "metrics";
  const head = document.createElement("tr");
  const labels = [];
  for (const [key] of COLUMNS) {
    const th = document.createElement("th");
    const label = t(key);
    th.textContent = label;
    labels.push(label);
    head.append(th);
  }
  table.append(head);
  for (const metric of metricsOf(session)) {
    const tr = document.createElement("tr");
    const name = t(`metric.${metric.id}`);
    const side = metric.side ? ` (${t(`side.${metric.side}`)})` : "";
    const value = metric.value == null ? "" : String(metric.value);
    tr.append(
      cell(`${name}${side}`, "", labels[0]),
      cell(value, "value num", labels[1]),
      cell(metric.unit || "", "unit num", labels[2]),
      cell(referenceText(metric, t), "num", labels[3]),
      cell(t(`status.${metric.status}`), "", labels[4]),
    );
    table.append(tr);
  }
  scroller.append(table);
  const flagsTitle = document.createElement("h2");
  flagsTitle.textContent = t("section.flags");
  const flags = document.createElement("div");
  if (!session.flags?.length) {
    flags.textContent = t("empty.flags");
  } else {
    for (const flag of session.flags) {
      const block = document.createElement("p");
      block.className = flag.severity === "watch" ? "flag watch" : "flag";
      const id = document.createElement("span");
      id.className = "k";
      id.textContent = flag.id;
      block.append(id, document.createTextNode(` ${flag.title}. ${flag.evidence}`));
      flags.append(block);
    }
  }
  const pathTitle = document.createElement("h2");
  pathTitle.textContent = t("section.pathway");
  const path = document.createElement("p");
  const code = session.suggested_pathway?.code || "";
  path.textContent = t(`pathway.${code}`);
  const qcTitle = document.createElement("h2");
  qcTitle.textContent = t("section.qc");
  const qc = document.createElement("p");
  const notes = (session.qc?.notes || []).join(" ");
  const status = named(t, session.qc?.status);
  const confidence = named(t, session.qc?.confidence);
  qc.textContent = `${t("qc.status")}: ${status}. ${t("qc.confidence")}: ${confidence}. ${notes}`;
  root.replaceChildren(
    title,
    badge(session.provenance, t),
    scroller,
    ...curveSection(session, t),
    flagsTitle,
    flags,
    pathTitle,
    path,
    qcTitle,
    qc,
  );
}
