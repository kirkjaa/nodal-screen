import { badge } from "../lib/badge.js";
import { loadSession, metricsOf } from "../lib/data.js";

function cell(text) {
  const td = document.createElement("td");
  td.textContent = text;
  return td;
}

function refText(ref, t) {
  if (!ref) return t("empty.ref");
  if (ref.kind === "norm") return `${ref.source_id}  mean ${ref.mean}`;
  if (ref.kind === "cutoff") return `${ref.source_id}  ${ref.op} ${ref.threshold}`;
  return t("empty.ref");
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
  const table = document.createElement("table");
  const head = document.createElement("tr");
  for (const key of ["col.metric", "col.value", "col.unit", "col.ref", "col.status"]) {
    const th = document.createElement("th");
    th.textContent = t(key);
    head.append(th);
  }
  table.append(head);
  for (const metric of metricsOf(session)) {
    const tr = document.createElement("tr");
    const label = t(`metric.${metric.id}`);
    const side = metric.side ? ` (${metric.side})` : "";
    tr.append(
      cell(`${label}${side}`),
      cell(String(metric.value)),
      cell(metric.unit || ""),
      cell(refText(metric.ref, t)),
      cell(t(`status.${metric.status}`)),
    );
    table.append(tr);
  }
  const flagsTitle = document.createElement("h2");
  flagsTitle.textContent = t("section.flags");
  const flags = document.createElement("div");
  if (!session.flags?.length) {
    flags.textContent = t("empty.flags");
  } else {
    for (const flag of session.flags) {
      const block = document.createElement("p");
      block.className = flag.severity === "watch" ? "flag watch" : "flag";
      const name = document.createElement("span");
      name.className = "k";
      name.textContent = flag.id;
      block.append(name, document.createTextNode(` ${flag.title}. ${flag.evidence}`));
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
  qc.textContent = `${t("qc.status")}: ${session.qc?.status || ""}. ${t("qc.confidence")}: ${session.qc?.confidence || ""}. ${notes}`;
  root.replaceChildren(title, badge(session.provenance, t), table, flagsTitle, flags, pathTitle, path, qcTitle, qc);
}
