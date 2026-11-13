import { badge } from "../lib/badge.js";

// Same threshold as screen/cohort.py MIN_CELL. Totals keep the true count.
const MIN_CELL = 10;
const SVG = "http://www.w3.org/2000/svg";
const NATS = ["UAE national", "Non-national"];
const BANDS = ["3-4", "5-6", "7-8", "9-12", "18-39", "40-59", "60-69", "70-79", "80-99"];
const PATHS = [
  "WCV_DEV_REVIEW",
  "FALLS_PREVENTION",
  "ADULT_SARCOPENIA",
  "CLINICIAN_SPECIALIST",
  "ADULT_EARLY_REVIEW",
  "ROUTINE",
  "RECAPTURE",
];
const METRICS = [
  "tug_time",
  "sls_time",
  "gait_speed",
  "sts5_time",
  "step_length_si",
  "step_time_si",
  "heel_first_share",
  "cadence",
  "double_support",
];

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function daySpan(flagDate, attendedDate) {
  if (!flagDate || !attendedDate) return null;
  const start = Date.parse(`${flagDate}T00:00:00Z`);
  const end = Date.parse(`${attendedDate}T00:00:00Z`);
  if (Number.isNaN(start) || Number.isNaN(end)) return null;
  return Math.round((end - start) / 86400000);
}

function medianOf(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  const value = sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function summarize(people) {
  const metrics = Object.fromEntries(METRICS.map((id) => [id, 0]));
  const pathways = Object.fromEntries(PATHS.map((id) => [id, 0]));
  let invited = 0;
  let screened = 0;
  let flagged = 0;
  let within30 = 0;
  let within60 = 0;
  const gaps = [];
  for (const person of people) {
    if (person.invited) invited += 1;
    if (person.screened) screened += 1;
    for (const id of person.flags || []) {
      if (id in metrics) metrics[id] += 1;
    }
    if ((person.flags || []).length) {
      flagged += 1;
      const span = daySpan(person.flag_date, person.attended_date);
      if (span != null) {
        gaps.push(span);
        if (span <= 30) within30 += 1;
        if (span <= 60) within60 += 1;
      }
    }
    if (person.pathway in pathways) pathways[person.pathway] += 1;
  }
  return { n: people.length, invited, screened, flagged, within30, within60, gaps, metrics, pathways };
}

function bar(fraction, color) {
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", "0 0 100 8");
  svg.setAttribute("class", "bar");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  svg.setAttribute("preserveAspectRatio", "none");
  const width = Math.max(0, Math.min(100, Math.round(fraction * 1000) / 10));
  const rtl = document.documentElement.dir === "rtl";
  svg.append(svgRect(0, 100, "var(--rule)"), svgRect(rtl ? 100 - width : 0, width, color));
  return svg;
}

function svgRect(x, width, fill) {
  const node = document.createElementNS(SVG, "rect");
  node.setAttribute("x", String(x));
  node.setAttribute("y", "0");
  node.setAttribute("width", String(width));
  node.setAttribute("height", "8");
  node.setAttribute("fill", fill);
  return node;
}

function statRow(label, text, suppressed, plot, fraction, color) {
  const row = el("div", "stat");
  const top = el("div", "stat-top");
  const value = el("span", "stat-value", text);
  if (suppressed) value.dataset.suppressed = "true";
  top.append(el("span", "stat-label", label), value);
  row.append(top);
  if (plot) row.append(bar(fraction, color));
  return row;
}

function countRow(t, label, count, asTotal, scale, color) {
  const reveal = asTotal || count >= MIN_CELL;
  const text = reveal ? String(count) : t("cohort.suppressed");
  const plot = count >= MIN_CELL && scale > 0;
  return statRow(label, text, !reveal, plot, scale ? count / scale : 0, color);
}

function rateRow(t, label, numer, denom, color) {
  if (denom < MIN_CELL || denom === 0) return statRow(label, t("cohort.suppressed"), true, false, 0, color);
  const pct = Math.round((100 * numer) / denom);
  return statRow(label, t("cohort.percent").replaceAll("{n}", String(pct)), false, true, pct / 100, color);
}

function medianRow(t, gaps) {
  if (gaps.length < MIN_CELL) return statRow(t("cohort.median"), t("cohort.suppressed"), true, false, 0, "var(--ready)");
  const shown = medianOf(gaps);
  const value = Number(shown);
  return statRow(
    t("cohort.median"),
    t("cohort.days").replaceAll("{n}", shown),
    false,
    true,
    Math.min(value / 90, 1),
    "var(--ready)",
  );
}

function fill(block, t, stats, asTotal, scale, mode) {
  if (mode === "reach") {
    block.append(countRow(t, t("cohort.invited"), stats.invited, asTotal, scale, "var(--n-400)"));
    block.append(countRow(t, t("cohort.screened"), stats.screened, asTotal, scale, "var(--info)"));
    return;
  }
  if (mode === "flags") {
    block.append(countRow(t, t("cohort.flagged"), stats.flagged, asTotal, scale, "var(--live)"));
    for (const id of METRICS) {
      if (!stats.metrics[id]) continue;
      block.append(countRow(t, t(`metric.${id}`), stats.metrics[id], asTotal, scale, "var(--live)"));
    }
    return;
  }
  if (mode === "pathways") {
    for (const code of PATHS) {
      if (!stats.pathways[code]) continue;
      block.append(countRow(t, t(`pathway.${code}`), stats.pathways[code], asTotal, scale, "var(--alpha)"));
    }
    block.append(countRow(t, t("cohort.total"), stats.n, true, scale, "var(--n-400)"));
    return;
  }
  block.append(countRow(t, t("cohort.flagged"), stats.flagged, asTotal, scale, "var(--ready)"));
  block.append(rateRow(t, t("cohort.within30"), stats.within30, stats.flagged, "var(--ready)"));
  block.append(rateRow(t, t("cohort.within60"), stats.within60, stats.flagged, "var(--ready)"));
  block.append(medianRow(t, stats.gaps));
}

function siteCard(t, site, people, key, values, mode) {
  const panel = el("section", "panel");
  panel.append(el("p", "site-id", site.id), el("p", "k", t(`site.${site.id}`)));
  const scale = people.length || 1;
  for (const value of values) {
    const group = people.filter((person) => person[key] === value);
    if (!group.length) continue;
    const block = el("div", "group-block");
    const label = key === "nationality_group" ? t(`nat.${value}`) : value;
    block.append(el("p", "group-name", label));
    fill(block, t, summarize(group), false, scale, mode);
    panel.append(block);
  }
  const total = el("div", "group-block");
  total.append(el("p", "group-name", t("cohort.total")));
  fill(total, t, summarize(people), true, scale, mode);
  panel.append(total);
  return panel;
}

function split(t, titleKey, sites, buckets, key, values, mode) {
  const wrap = el("section", "split");
  wrap.append(el("h3", "", t(titleKey)));
  const grid = el("div", "site-grid");
  for (const site of sites) grid.append(siteCard(t, site, buckets.get(site.id) || [], key, values, mode));
  wrap.append(grid);
  return wrap;
}

function summaryCard(label, text, plot, fraction, color) {
  const panel = el("div", "panel");
  panel.append(el("strong", "", text), el("span", "", label));
  if (plot) panel.append(bar(fraction, color));
  return panel;
}

function summary(t, stats) {
  const invited = stats.invited || 1;
  const cards = el("div", "cards");
  const flaggedRate = stats.flagged >= MIN_CELL;
  cards.append(summaryCard(t("cohort.invited"), String(stats.invited), stats.invited >= MIN_CELL, 1, "var(--n-400)"));
  cards.append(summaryCard(
    t("cohort.screened"),
    String(stats.screened),
    stats.screened >= MIN_CELL,
    stats.screened / invited,
    "var(--info)",
  ));
  cards.append(summaryCard(
    t("cohort.flagged"),
    String(stats.flagged),
    flaggedRate,
    stats.flagged / invited,
    "var(--live)",
  ));
  const within30 = rateText(t, stats.within30, stats.flagged);
  const within60 = rateText(t, stats.within60, stats.flagged);
  cards.append(summaryCard(t("cohort.within30"), within30.text, within30.plot, within30.fraction, "var(--ready)"));
  cards.append(summaryCard(t("cohort.within60"), within60.text, within60.plot, within60.fraction, "var(--ready)"));
  const median = stats.gaps.length >= MIN_CELL ? medianOf(stats.gaps) : null;
  cards.append(summaryCard(
    t("cohort.median"),
    median == null ? t("cohort.suppressed") : t("cohort.days").replaceAll("{n}", median),
    median != null,
    median == null ? 0 : Math.min(Number(median) / 90, 1),
    "var(--alpha)",
  ));
  return cards;
}

function rateText(t, numer, denom) {
  if (denom < MIN_CELL) return { text: t("cohort.suppressed"), plot: false, fraction: 0 };
  const pct = Math.round((100 * numer) / denom);
  return { text: t("cohort.percent").replaceAll("{n}", String(pct)), plot: true, fraction: pct / 100 };
}

function section(t, titleKey, leadKey, sites, buckets, mode) {
  const block = el("section", "cohort-section");
  block.append(el("h2", "", t(titleKey)), el("p", "lead", t(leadKey)));
  block.append(split(t, "cohort.byNationality", sites, buckets, "nationality_group", NATS, mode));
  block.append(split(t, "cohort.byAge", sites, buckets, "age_band", BANDS, mode));
  return block;
}

export async function render(root, ctx) {
  const { t } = ctx;
  const title = el("h1", "", t("overview.step.program"));
  let cohortFile;
  try {
    const res = await fetch("data/cohort.json");
    if (!res.ok) throw new Error(String(res.status));
    cohortFile = await res.json();
  } catch {
    root.replaceChildren(title, el("p", "lead", t("cohort.loadError")));
    return;
  }
  const people = cohortFile.people || [];
  const sites = cohortFile.sites || [];
  const buckets = new Map(sites.map((site) => [site.id, []]));
  for (const person of people) {
    if (!buckets.has(person.site)) buckets.set(person.site, []);
    buckets.get(person.site).push(person);
  }
  const stats = summarize(people);
  const head = el("div", "cohort");
  const generated = el("p", "k", `${t("cohort.generated")} ${cohortFile.generated || ""}`);
  head.append(
    title,
    badge(cohortFile.provenance || "synthetic", t),
    generated,
    el("p", "lead", t("cohort.noComplement")),
    summary(t, stats),
    section(t, "cohort.reach", "cohort.reachLead", sites, buckets, "reach"),
    section(t, "cohort.flags", "cohort.flagsLead", sites, buckets, "flags"),
    section(t, "cohort.pathways", "cohort.pathwaysLead", sites, buckets, "pathways"),
    section(t, "cohort.completion", "cohort.completionLead", sites, buckets, "completion"),
  );
  root.replaceChildren(head);
}
