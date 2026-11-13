import { badge } from "../lib/badge.js";
import { loadSession, metricsOf } from "../lib/data.js";

function p(text, className) {
  const node = document.createElement("p");
  if (className) node.className = className;
  node.textContent = text;
  return node;
}

function metricName(t, id) {
  const key = `metric.${id}`;
  const label = t(key);
  return label === key ? id : label;
}

function metricLine(t, id, value) {
  const line = document.createElement("p");
  line.append(document.createTextNode(`${metricName(t, id)}: `));
  const num = document.createElement("bdi");
  num.textContent = String(value);
  line.append(num);
  return line;
}

export async function render(root, ctx) {
  const { t, pid } = ctx;
  const title = document.createElement("h1");
  title.textContent = t("heading.history");
  const session = await loadSession(pid);
  if (!session) {
    root.replaceChildren(title, p(t("missing")));
    return;
  }
  const parts = [title, badge(session.provenance, t)];
  const speeds = metricsOf(session).filter((metric) => metric.id === "gait_speed");
  if (!speeds.length) {
    parts.push(p(t("history.no-speed")));
  } else {
    const current = document.createElement("p");
    current.append(document.createTextNode(`${t("history.current")}: `));
    speeds.forEach((metric, index) => {
      if (index) current.append(document.createTextNode(", "));
      const num = document.createElement("bdi");
      num.textContent = `${metric.value} ${metric.unit || ""}`.trim();
      current.append(num);
    });
    parts.push(current);
  }
  const visits = Array.isArray(session.history) ? session.history : [];
  if (!visits.length) {
    parts.push(p(t("history.empty")));
  } else {
    for (const visit of visits) {
      const panel = document.createElement("article");
      panel.className = "panel";
      const head = document.createElement("p");
      head.className = "k";
      head.textContent = `${t("history.visit")} ${visit.visit_id || ""} · ${t("history.date")} ${visit.date || ""}`;
      panel.append(head);
      for (const [id, value] of Object.entries(visit.metrics || {})) {
        panel.append(metricLine(t, id, value));
      }
      parts.push(panel);
    }
  }
  for (const flag of session.flags || []) {
    if (flag.rule !== "change") continue;
    const block = document.createElement("div");
    block.className = flag.severity === "watch" ? "flag watch" : "flag";
    block.append(p(flag.title || ""), p(flag.evidence || ""));
    parts.push(block);
  }
  root.replaceChildren(...parts);
}
