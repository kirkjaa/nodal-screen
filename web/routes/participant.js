import { badge } from "../lib/badge.js";
import { loadSession, loadSources } from "../lib/data.js";
import { renderAiTexts } from "../lib/aitexts.js";
import { loadReplay, renderReplay } from "../lib/replay.js";

const SVG = "http://www.w3.org/2000/svg";
const TASKS = ["gait", "tug", "sts5", "sls", "tandem", "hop"];
const CURVES = ["knee_flexion", "hip_flexion"];

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

function named(t, value) {
  if (value == null || value === "") return "";
  const key = `qc.value.${value}`;
  const label = t(key);
  return label === key ? String(value) : label;
}

function labelOf(t, key, fallback) {
  const label = t(key);
  return label === key ? fallback : label;
}

function taskNames(session) {
  const tasks = session.tasks || {};
  const names = TASKS.filter((name) => tasks[name]);
  for (const name of Object.keys(tasks)) {
    if (!names.includes(name)) names.push(name);
  }
  return names;
}

function rowId(task, metric) {
  return `m-${task}-${metric.id}-${metric.side || "none"}`;
}

function findRowId(session, metricId) {
  for (const task of taskNames(session)) {
    for (const metric of session.tasks[task].metrics || []) {
      if (metric.id === metricId) return rowId(task, metric);
    }
  }
  return "";
}

function sourceText(sources, sourceId, t) {
  if (sourceId === "nodal-rule") return t("source.nodal-rule");
  const entry = sources && sources[sourceId];
  if (entry && entry.citation) return entry.citation;
  return labelOf(t, `source.${sourceId}`, sourceId);
}

function oneDecimal(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(1) : String(value);
}

function referenceText(metric, t) {
  const ref = metric.ref;
  if (!ref) return t("empty.ref");
  if (ref.status === "placeholder") return t("report.ref.pending");
  if (ref.mean == null) return t("empty.ref");
  const unit = metric.unit ? ` ${metric.unit}` : "";
  let text = `${t("ref.mean")} ${ref.mean}${unit}`;
  if (ref.sd != null) text += `, ${t("ref.sd")} ${ref.sd}`;
  if (ref.z != null) text += `, ${t("ref.z")} ${oneDecimal(ref.z)}`;
  return text;
}

function cutoffText(metric, t) {
  const cutoff = metric.cutoff;
  if (!cutoff || cutoff.threshold == null || !cutoff.op) return t("empty.ref");
  const source = cutoff.source_id === "nodal-rule"
    ? t("source.nodal-rule")
    : labelOf(t, `source.${cutoff.source_id}`, cutoff.source_id || "");
  const unit = metric.unit ? ` ${metric.unit}` : "";
  const met = cutoff.met ? t("report.met") : t("report.notmet");
  return `${cutoff.op} ${cutoff.threshold}${unit}, ${source} ${met}`;
}

function cell(text, className, label) {
  const td = document.createElement("td");
  if (className) td.className = className;
  td.dataset.label = label;
  const span = document.createElement("span");
  span.append(bdi(text));
  td.append(span);
  return td;
}

function header(session, t) {
  const person = session.participant || {};
  const visit = session.visit || {};
  const title = el("h1", "", person.display_name || "");
  const line = el("p", "meta");
  const bits = [
    labelOf(t, `group.${person.group}`, person.group || ""),
    person.age_band || "",
    person.sex || "",
    visit.site || "",
    visit.date || "",
    visit.kit || "",
  ];
  bits.forEach((bit, index) => {
    if (index) line.append(document.createTextNode(" · "));
    const node = bdi(bit);
    if (index === bits.length - 1) {
      node.lang = "en";
      node.dir = "ltr";
    }
    line.append(node);
  });
  return [title, line, badge(session.provenance, t)];
}

function summary(session, t) {
  const box = el("section", "panel");
  box.append(el("h2", "", t("report.summary")));
  const qc = session.qc || {};
  if (qc.status === "insufficient") {
    box.append(el("p", "", t("report.repeat")));
    for (const note of qc.notes || []) box.append(el("p", "", note));
    return box;
  }
  const code = session.suggested_pathway?.code || "";
  box.append(el("p", "", labelOf(t, `pathway.${code}`, code)));
  const flags = session.flags || [];
  const nFlags = flags.filter((flag) => flag.severity === "flag").length;
  const nWatches = flags.filter((flag) => flag.severity === "watch").length;
  if (!nFlags && !nWatches) box.append(el("p", "", t("report.none")));
  else {
    box.append(el("p", "", t("report.count")
      .replaceAll("{n_flags}", String(nFlags))
      .replaceAll("{n_watches}", String(nWatches))));
  }
  box.append(el("p", "", t("report.clinician")));
  return box;
}

function flagsSection(session, sources, t) {
  const block = el("section");
  block.append(el("h2", "", t("section.flags")));
  for (const flag of session.flags || []) {
    const row = el("article", flag.severity === "watch" ? "flag watch" : "flag");
    const chip = el("span", "k", flag.severity === "watch" ? t("report.watch") : t("report.flag"));
    const title = document.createElement("a");
    title.textContent = flag.title || "";
    const target = findRowId(session, (flag.metric_ids || [])[0]);
    if (target) title.href = `#${target}`;
    const names = (flag.source_ids || []).map((id) => sourceText(sources, id, t));
    row.append(
      chip,
      title,
      el("p", "", flag.evidence || ""),
      el("p", "", names.join(", ")),
      el("p", "", `${t("review.confidence")}: ${named(t, flag.confidence)}`),
    );
    block.append(row);
  }
  return block;
}

function resultTables(session, t) {
  const parts = [el("h2", "", t("report.results"))];
  const columns = ["col.metric", "col.value", "col.ref", "col.cutoff", "col.status"];
  const headings = columns.map((key) => t(key));
  for (const task of taskNames(session)) {
    const metrics = session.tasks[task].metrics || [];
    if (!metrics.length) continue;
    parts.push(el("h3", "", labelOf(t, `task.${task}`, task)));
    const scroller = el("div", "table-scroll");
    const table = el("table", "metrics");
    const head = document.createElement("tr");
    for (const heading of headings) head.append(el("th", "", heading));
    table.append(head);
    for (const metric of metrics) {
      const tr = document.createElement("tr");
      tr.id = rowId(task, metric);
      const name = labelOf(t, `metric.${metric.id}`, metric.id);
      const side = metric.side ? ` (${t(`side.${metric.side}`)})` : "";
      const value = metric.value == null ? "" : `${metric.value} ${metric.unit || ""}`.trim();
      tr.append(
        cell(`${name}${side}`, "", headings[0]),
        cell(value, "value num", headings[1]),
        cell(referenceText(metric, t), "num", headings[2]),
        cell(cutoffText(metric, t), "num", headings[3]),
        cell(labelOf(t, `status.${metric.status}`, metric.status || ""), "", headings[4]),
      );
      table.append(tr);
    }
    scroller.append(table);
    parts.push(scroller);
  }
  return parts;
}

function pointsOf(series) {
  return Array.isArray(series) ? series.filter((value) => typeof value === "number") : [];
}

function chartSvg(name, curve, t) {
  const left = pointsOf(curve.left);
  const right = pointsOf(curve.right);
  const values = left.concat(right);
  if (!values.length) return null;
  const width = 640;
  const height = 220;
  const padL = 44;
  const padR = 12;
  const padT = 16;
  const padB = 32;
  let min = Math.min(...values);
  let max = Math.max(...values);
  const step = max - min > 40 ? 20 : 10;
  min = Math.floor(min / step) * step;
  max = Math.ceil(max / step) * step;
  if (min === max) max = min + step;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;
  const xAt = (index, count) => padL + (count <= 1 ? 0 : (index / (count - 1)) * plotW);
  const yAt = (value) => padT + ((max - value) / (max - min)) * plotH;
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("role", "img");
  svg.classList.add("chart");
  const title = document.createElementNS(SVG, "title");
  title.textContent = labelOf(t, `curve.${name}`, name);
  const desc = document.createElementNS(SVG, "desc");
  desc.textContent = t("report.curves.desc");
  svg.append(title, desc);
  for (let tick = min; tick <= max; tick += step) {
    const y = yAt(tick);
    const grid = document.createElementNS(SVG, "line");
    grid.setAttribute("x1", String(padL));
    grid.setAttribute("x2", String(width - padR));
    grid.setAttribute("y1", String(y));
    grid.setAttribute("y2", String(y));
    grid.setAttribute("stroke", "var(--rule)");
    svg.append(grid);
    const label = document.createElementNS(SVG, "text");
    label.setAttribute("x", "4");
    label.setAttribute("y", String(y + 4));
    label.setAttribute("fill", "var(--muted)");
    label.setAttribute("font-size", "11");
    label.textContent = String(tick);
    svg.append(label);
  }
  const axis = document.createElementNS(SVG, "text");
  axis.setAttribute("x", String(padL));
  axis.setAttribute("y", String(height - 8));
  axis.setAttribute("fill", "var(--muted)");
  axis.setAttribute("font-size", "11");
  axis.textContent = t("report.axis.x");
  svg.append(axis);
  const yName = document.createElementNS(SVG, "text");
  yName.setAttribute("x", String(padL));
  yName.setAttribute("y", "12");
  yName.setAttribute("fill", "var(--muted)");
  yName.setAttribute("font-size", "11");
  yName.textContent = t("report.axis.y");
  svg.append(yName);
  const draw = (series, dashed) => {
    if (!series.length) return;
    const poly = document.createElementNS(SVG, "polyline");
    poly.setAttribute("fill", "none");
    poly.setAttribute("stroke", dashed ? "var(--muted)" : "var(--text)");
    poly.setAttribute("stroke-width", "2");
    if (dashed) poly.setAttribute("stroke-dasharray", "6 4");
    poly.setAttribute("points", series.map((value, index) => `${xAt(index, series.length)},${yAt(value)}`).join(" "));
    svg.append(poly);
  };
  const mean = pointsOf(curve.norm_mean);
  const sd = pointsOf(curve.norm_sd);
  if (mean.length === 101 && sd.length === 101) {
    const upper = mean.map((value, index) => `${xAt(index, 101)},${yAt(value + sd[index])}`);
    const lower = mean.map((value, index) => `${xAt(index, 101)},${yAt(value - sd[index])}`).reverse();
    const band = document.createElementNS(SVG, "polygon");
    band.setAttribute("points", upper.concat(lower).join(" "));
    band.setAttribute("fill", "var(--rule)");
    svg.append(band);
  }
  draw(left, false);
  draw(right, true);
  const legend = el("p", "meta");
  legend.append(bdi(t("side.left")), document.createTextNode(" · "), bdi(t("side.right")));
  return [svg, legend];
}

function movement(session, replay, ctx) {
  const { t, pid } = ctx;
  const parts = [el("h2", "", t("report.movement"))];
  if (session.replay && session.replay.gait) {
    const section = el("section");
    section.id = "replay";
    if (replay) renderReplay(section, session, replay, ctx);
    else section.append(el("p", "", t("replay.error")));
    const open = document.createElement("a");
    open.href = `#/p/${encodeURIComponent(pid)}/replay`;
    open.textContent = t("replay.open");
    const line = el("p");
    line.append(open);
    parts.push(section, line);
    return parts;
  }
  const curves = session.tasks?.gait?.curves || {};
  let drew = false;
  for (const name of CURVES) {
    const curve = curves[name];
    if (!curve || typeof curve !== "object") continue;
    const drawn = chartSvg(name, curve, t);
    if (!drawn) continue;
    drew = true;
    parts.push(el("h3", "", labelOf(t, `curve.${name}`, name)), ...drawn);
  }
  if (drew) parts.push(el("p", "note", t("report.curves.note")));
  return parts;
}

function gaitSpeed(metrics) {
  if (!metrics) return null;
  if (typeof metrics.gait_speed === "number") return metrics.gait_speed;
  const row = (Array.isArray(metrics) ? metrics : []).find((metric) => metric.id === "gait_speed");
  return row ? row.value : null;
}

function changeSection(session, t, pid) {
  const history = Array.isArray(session.history) ? session.history : [];
  if (!history.length) return [];
  const block = el("section");
  block.append(el("h2", "", t("report.change")));
  const scroller = el("div", "table-scroll");
  const table = el("table", "metrics");
  const head = document.createElement("tr");
  for (const key of ["history.visit", "history.date", "metric.gait_speed"]) {
    head.append(el("th", "", t(key)));
  }
  table.append(head);
  const visit = session.visit || {};
  const rows = history.concat([{
    visit_id: visit.visit_id,
    date: visit.date,
    metrics: { gait_speed: gaitSpeed((session.tasks?.gait?.metrics) || []) },
  }]);
  for (const item of rows) {
    const tr = document.createElement("tr");
    const speed = gaitSpeed(item.metrics);
    tr.append(
      cell(item.visit_id || "", "", t("history.visit")),
      cell(item.date || "", "num", t("history.date")),
      cell(speed == null ? "" : `${speed} m/s`, "value num", t("metric.gait_speed")),
    );
    table.append(tr);
  }
  scroller.append(table);
  block.append(scroller);
  for (const flag of session.flags || []) {
    if (flag.rule !== "change") continue;
    block.append(el("p", "", flag.evidence || ""));
  }
  const link = document.createElement("a");
  link.href = `#/p/${encodeURIComponent(pid)}/history`;
  link.textContent = t("report.history");
  const line = el("p");
  line.append(link);
  block.append(line);
  return [block];
}

function captureCheck(session, t) {
  const qc = session.qc || {};
  const block = el("section");
  block.append(el("h2", "", t("section.qc")));
  const lines = [
    `${t("qc.status")}: ${named(t, qc.status)}`,
    `${t("qc.confidence")}: ${named(t, qc.confidence)}`,
    `${t("qc.strides")}: ${qc.strides_left ?? ""} ${t("side.left")}, ${qc.strides_right ?? ""} ${t("side.right")}`,
    `${t("qc.keypoint")}: ${qc.keypoint_confidence ?? ""}`,
  ];
  for (const line of lines) block.append(el("p", "", line));
  if (qc.calib_residual_px == null) block.append(el("p", "", t("report.calib")));
  else block.append(el("p", "", `${t("qc.calib")}: ${qc.calib_residual_px}`));
  for (const note of qc.notes || []) block.append(el("p", "", note));
  return block;
}

export async function render(root, ctx) {
  const { t, pid } = ctx;
  const title = el("h1", "", t("heading.report"));
  const session = await loadSession(pid);
  if (!session) {
    root.replaceChildren(title, el("p", "", t("missing")));
    return;
  }
  const sources = await loadSources();
  let replay = null;
  if (session.replay && session.replay.gait) {
    try {
      replay = await loadReplay(session);
    } catch {
      replay = null;
    }
  }
  const footer = el("p", "note", t("report.footer"));
  const provenance = el("p", "note", session.provenance_note || "");
  root.replaceChildren(
    ...header(session, t),
    summary(session, t),
    flagsSection(session, sources, t),
    ...resultTables(session, t),
    ...movement(session, replay, ctx),
    ...changeSection(session, t, pid),
    captureCheck(session, t),
    await renderAiTexts(session, ctx.lang),
    footer,
    provenance,
  );
}
