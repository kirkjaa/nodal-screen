import { badge } from "../lib/badge.js";
import { loadSession, loadSources } from "../lib/data.js";
import { renderAiTexts } from "../lib/aitexts.js";
import { loadReplay, renderReplay, renderStage } from "../lib/replay.js";

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
    const count = (n, key) => t(n === 1 ? `${key}.one` : `${key}.many`).replaceAll("{n}", String(n));
    box.append(el("p", "", t("report.count")
      .replaceAll("{flags}", count(nFlags, "report.flag"))
      .replaceAll("{watches}", count(nWatches, "report.watch"))));
  }
  box.append(el("p", "", t("report.clinician")));
  return box;
}

function flagsSection(session, sources, t) {
  const block = el("section");
  block.append(el("h2", "", t("section.flags")));
  if (!(session.flags || []).length) block.append(el("p", "", t("empty.flags")));
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

// ---------------------------------------------------------------------------
// The panel: Strain Watch layout. Left, the readouts and findings; centre, the
// measured take on a stage with the joint-angle curves; right, symmetry, change
// over time, the capture check and the next step. Everything comes from the
// session file; nothing here computes a metric, a status or a flag.

const SHORT = {
  bohannon2011: "Bohannon 2011", bohannon2006tug: "Bohannon 2006", bohannon2010sts: "Bohannon 2010",
  springer2007: "Springer 2007", voss2020: "Voss 2020", perera2006: "Perera 2006",
  steadi: "CDC STEADI", ewgsop2: "EWGSOP2", awgs2019: "AWGS 2019",
};

function shortSource(id, t) {
  return id === "nodal-rule" ? t("source.nodal-rule") : (SHORT[id] || id);
}

function metricOf(session, id, side = null) {
  for (const task of Object.values(session.tasks || {})) {
    for (const m of task.metrics || []) {
      if (m.id === id && (side == null || m.side === side)) return m;
    }
  }
  return null;
}

function tone(status) {
  return { in_range: "grn", borderline: "amb", out_of_range: "red" }[status] || "muted";
}

function fmt(value) {
  if (value == null || value === "") return "–";
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value);
  return Math.abs(n) >= 100 ? String(Math.round(n)) : String(n);
}

function refLine(metric, t) {
  if (!metric) return "";
  const bits = [];
  if (metric.ref && metric.ref.mean != null) bits.push(`${t("panel.mean")} ${metric.ref.mean}`);
  if (metric.cutoff && metric.cutoff.threshold != null) {
    bits.push(`${t("panel.cut")} ${metric.cutoff.op} ${metric.cutoff.threshold} · ${shortSource(metric.cutoff.source_id, t)}`);
  }
  return bits.join("  ·  ");
}

function readout(label, metric, t, unit) {
  const blk = el("div", "blk");
  blk.append(el("p", "mono k", label));
  const big = el("div", "big");
  big.append(bdi(fmt(metric?.value)));
  const u = el("small", "", unit ?? metric?.unit ?? "");
  big.append(u);
  blk.append(big);
  if (metric) {
    blk.append(el("p", `mono lvl ${tone(metric.status)}`, labelOf(t, `status.${metric.status}`, metric.status || "")));
    const ref = refLine(metric, t);
    if (ref) blk.append(el("p", "mono faint ref", ref));
  }
  return blk;
}

function pair(a, b) {
  const row = el("div", "pair");
  row.append(a, b);
  return row;
}

function leftColumn(session, t) {
  const col = el("aside", "side");
  const qc = session.qc || {};
  const code = session.suggested_pathway?.code || "";
  const flags = session.flags || [];
  const nFlags = flags.filter((f) => f.severity === "flag").length;
  const nWatches = flags.filter((f) => f.severity === "watch").length;

  const path = el("div", "blk");
  path.append(el("p", "mono k", t("section.pathway")));
  path.append(el("p", `mid ${code === "RECAPTURE" ? "red" : code === "ROUTINE" ? "grn" : "amb"}`, labelOf(t, `pathway.${code}`, code)));
  if (qc.status !== "insufficient") {
    const counts = el("p", "mono lvl");
    counts.append(el("span", nFlags ? "red" : "muted", (nFlags === 1 ? t("report.flag.one") : t("report.flag.many")).replace("{n}", nFlags)));
    counts.append(document.createTextNode("  ·  "));
    counts.append(el("span", nWatches ? "amb" : "muted", (nWatches === 1 ? t("report.watch.one") : t("report.watch.many")).replace("{n}", nWatches)));
    path.append(counts);
  }
  col.append(path);

  if (qc.status === "insufficient") {
    const box = el("div", "blk");
    box.append(el("p", "mono k red", t("panel.recapture")));
    box.append(el("p", "", t("report.repeat")));
    for (const note of qc.notes || []) box.append(el("p", "mono faint", note));
    col.append(box);
    return col;
  }

  col.append(readout(t("panel.gait"), metricOf(session, "gait_speed"), t));
  col.append(pair(
    readout(t("metric.tug_time"), metricOf(session, "tug_time"), t),
    readout(t("metric.sts5_time"), metricOf(session, "sts5_time"), t),
  ));
  const slsL = metricOf(session, "sls_time", "left");
  const slsR = metricOf(session, "sls_time", "right");
  if (slsL || slsR) {
    col.append(pair(
      readout(`${t("panel.sls")} · ${t("replay.left")}`, slsL, t),
      readout(`${t("panel.sls")} · ${t("replay.right")}`, slsR, t),
    ));
  }

  const find = el("div", "blk");
  find.append(el("p", "mono k", t("panel.findings")));
  if (!flags.length) find.append(el("p", "muted", t("report.none")));
  for (const flag of flags) {
    const card = el("div", `find${flag.severity === "watch" ? " amb" : ""}`);
    const sources = (flag.source_ids || []).map((id) => shortSource(id, t)).join(" · ");
    card.append(el("span", `mono ${flag.severity === "watch" ? "amb" : "red"}`,
      `${flag.severity === "watch" ? t("report.watch") : t("report.flag")} · ${sources}`));
    const target = findRowId(session, (flag.metric_ids || [])[0]);
    const title = document.createElement(target ? "a" : "span");
    if (target) title.href = `#${target}`;
    title.className = "find-title";
    title.textContent = flag.title || "";
    card.append(title);
    card.append(el("span", "mono faint find-ev", flag.evidence || ""));
    find.append(card);
  }
  col.append(find);
  return col;
}

function gauge(label, metric, max, t) {
  const blk = el("div", "gauge");
  const head = el("div", "gauge-h");
  head.append(el("span", "mono k", label));
  const val = el("span", `gauge-v ${tone(metric?.status)}`);
  val.append(bdi(metric?.value == null ? "–" : `${fmt(metric.value)} %`));
  head.append(val);
  blk.append(head);
  const track = el("div", "gauge-t");
  track.dir = "ltr";
  const fill = el("span", `gauge-f ${tone(metric?.status)}`);
  const v = Math.max(0, Math.min(Number(metric?.value) || 0, max));
  fill.style.width = `${(100 * v) / max}%`;
  track.append(fill);
  const th = metric?.cutoff?.threshold;
  if (th != null && th <= max) {
    const mark = el("span", "gauge-m");
    mark.style.left = `${(100 * th) / max}%`;
    mark.title = `${metric.cutoff.op} ${th}`;
    track.append(mark);
  }
  blk.append(track);
  if (th != null) blk.append(el("p", "mono faint", `${shortSource(metric.cutoff.source_id, t)} ${metric.cutoff.op} ${th} %`));
  return blk;
}

function trend(session, t) {
  const history = Array.isArray(session.history) ? session.history : [];
  const now = metricOf(session, "gait_speed");
  const pts = history.map((h) => ({ label: h.visit_id, date: h.date, v: gaitSpeed(h.metrics) }))
    .concat([{ label: session.visit?.visit_id, date: session.visit?.date, v: now?.value }])
    .filter((p) => p.v != null);
  const blk = el("div", "blk");
  blk.append(el("p", "mono k", t("panel.change")));
  if (pts.length < 2) {
    blk.append(el("p", "muted", t("panel.baseline")));
    return blk;
  }
  const W = 300; const H = 150;
  const vals = pts.map((p) => Number(p.v));
  const cut = now?.cutoff?.threshold;
  const lo = Math.min(...vals, cut ?? Infinity) - 0.1;
  const hi = Math.max(...vals) + 0.1;
  const X = (i) => 30 + (i * (W - 60)) / (pts.length - 1);
  const Y = (v) => 18 + ((hi - v) * (H - 46)) / (hi - lo);
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("class", "trend");
  svg.setAttribute("role", "img");
  const title = document.createElementNS(SVG, "title");
  title.textContent = `${t("panel.change")}: ${pts.map((p) => `${p.label} ${p.v} m/s`).join(", ")}`;
  svg.append(title);
  const mk = (name, attrs, text) => {
    const n = document.createElementNS(SVG, name);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (text != null) n.textContent = text;
    svg.append(n);
    return n;
  };
  if (cut != null) {
    mk("line", { x1: 20, x2: W - 10, y1: Y(cut), y2: Y(cut), class: "trend-cut" });
    mk("text", { x: W - 12, y: Y(cut) - 5, class: "trend-lab red", "text-anchor": "end" }, `${shortSource(now.cutoff.source_id, t)} ${cut}`);
  }
  mk("polyline", { points: pts.map((p, i) => `${X(i)},${Y(p.v)}`).join(" "), class: "trend-line" });
  pts.forEach((p, i) => {
    mk("circle", { cx: X(i), cy: Y(p.v), r: 3.5, class: i === pts.length - 1 ? "trend-dot now" : "trend-dot" });
    mk("text", { x: X(i), y: Y(p.v) - 9, class: "trend-val", "text-anchor": "middle" }, String(p.v));
    const anchor = i === 0 ? "start" : i === pts.length - 1 ? "end" : "middle";
    mk("text", { x: i === 0 ? X(i) - 6 : i === pts.length - 1 ? X(i) + 6 : X(i), y: H - 6, class: "trend-lab", "text-anchor": anchor }, `${p.label} · ${String(p.date || "").slice(0, 4)}`);
  });
  const box = el("div", "trend-box");
  box.dir = "ltr";
  box.append(svg);
  blk.append(box);
  for (const flag of session.flags || []) {
    if (flag.rule === "change") blk.append(el("p", `mono ${flag.severity === "watch" ? "amb" : "red"}`, `${flag.evidence} · ${shortSource("perera2006", t)}`));
  }
  return blk;
}

function rightColumn(session, t) {
  const col = el("aside", "side r");
  const qc = session.qc || {};
  if (qc.status !== "insufficient") {
    const sym = el("div", "blk");
    sym.append(el("p", "mono k", t("panel.symmetry")));
    sym.append(gauge(t("metric.step_length_si"), metricOf(session, "step_length_si"), 30, t));
    sym.append(gauge(t("metric.step_time_si"), metricOf(session, "step_time_si"), 30, t));
    col.append(sym);
    if (session.participant?.group === "child") {
      const heel = el("div", "blk");
      heel.append(el("p", "mono k", t("metric.heel_first_share")));
      heel.append(gauge(t("replay.left"), metricOf(session, "heel_first_share", "left"), 100, t));
      heel.append(gauge(t("replay.right"), metricOf(session, "heel_first_share", "right"), 100, t));
      col.append(heel);
    }
    col.append(trend(session, t));
  }
  const cap = el("div", "blk");
  cap.append(el("p", "mono k", t("section.qc")));
  const rows = [
    [t("qc.status"), named(t, qc.status), qc.status === "ok" ? "grn" : "red"],
    [t("qc.confidence"), named(t, qc.confidence), qc.confidence === "high" ? "grn" : qc.confidence === "medium" ? "amb" : "red"],
    [t("qc.strides"), `${qc.strides_left ?? "–"} L · ${qc.strides_right ?? "–"} R`, ""],
    [t("qc.keypoint"), qc.keypoint_confidence ?? "–", ""],
  ];
  const dl = el("dl", "qc");
  for (const [k, v, cls] of rows) {
    dl.append(el("dt", "mono", k));
    const dd = el("dd", cls);
    dd.append(bdi(v));
    dl.append(dd);
  }
  cap.append(dl);
  cap.append(el("p", "mono faint", qc.calib_residual_px == null ? t("panel.calib") : `${t("qc.calib")} ${qc.calib_residual_px}`));
  col.append(cap);

  const next = el("div", "blk");
  next.append(el("p", "mono k", t("panel.next")));
  const code = session.suggested_pathway?.code || "";
  const warn = el("div", `warn${code === "ROUTINE" ? " grn" : code === "RECAPTURE" ? "" : " amb"}`);
  warn.append(el("span", "mono", labelOf(t, `pathway.${code}`, code)));
  warn.append(el("p", "", t("report.clinician")));
  next.append(warn);
  col.append(next);
  return col;
}

function centre(session, replay, ctx) {
  const { t, pid } = ctx;
  const col = el("section", "stage");
  const stageBox = el("div", "stage-box");
  col.append(stageBox);
  const curves = el("div", "rp-curves panel-curves");
  curves.dir = "ltr";
  if (replay) {
    renderStage(stageBox, session, replay, ctx, { curvesInto: curves });
    const tail = el("div", "stage-foot");
    tail.append(el("p", "mono k", t("panel.curves")));
    tail.append(curves);
    const open = document.createElement("a");
    open.href = `#/p/${encodeURIComponent(pid)}/replay`;
    open.className = "mono";
    open.textContent = t("replay.open");
    tail.append(open);
    col.append(tail);
  } else {
    stageBox.append(...movement(session, null, ctx));
  }
  return col;
}

function topLine(session, t) {
  const person = session.participant || {};
  const visit = session.visit || {};
  const qc = session.qc || {};
  const bar = el("div", "rp-head");
  const name = el("h1", "", person.display_name || "");
  const crumb = el("p", "mono crumb");
  const bits = [labelOf(t, `group.${person.group}`, person.group || ""), person.age_band, person.sex, visit.site, visit.visit_id, visit.date];
  crumb.append(bdi(bits.filter(Boolean).join("  ·  ")));
  const chips = el("div", "chips");
  const chip = (text, cls = "") => { const c = el("span", `chip mono ${cls}`); c.append(el("i"), bdi(text)); return c; };
  chips.append(chip(visit.kit || ""));
  if (qc.strides_left != null) chips.append(chip(`${qc.strides_left + qc.strides_right} ${t("qc.strides").toLowerCase()}`, qc.status === "ok" ? "" : "bad"));
  chips.append(chip(t(`badge.${session.provenance}`) || t("badge.synthetic"), "sample"));
  const left = el("div");
  left.append(name, crumb);
  bar.append(left, chips);
  return bar;
}

export async function render(root, ctx) {
  const { t, pid } = ctx;
  const session = await loadSession(pid);
  if (!session) {
    root.replaceChildren(el("h1", "", t("heading.report")), el("p", "", t("missing")));
    return;
  }
  root.classList.add("wide");
  const sources = await loadSources();
  let replay = null;
  if (session.replay && session.replay.gait) {
    try {
      replay = await loadReplay(session);
    } catch {
      replay = null;
    }
  }
  const lead = el("div", "rp-lead");
  lead.append(leftColumn(session, t), centre(session, replay, ctx), rightColumn(session, t));
  const details = el("section", "details");
  details.append(
    el("h2", "", t("panel.details")),
    flagsSection(session, sources, t),
    ...resultTables(session, t),
    ...changeSection(session, t, pid),
    await renderAiTexts(session, ctx.lang),
    el("p", "note", t("report.footer")),
    el("p", "note", session.provenance_note || ""),
  );
  root.replaceChildren(topLine(session, t), lead, details);
}
