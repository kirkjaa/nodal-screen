import { badge } from "../lib/badge.js";
import { loadIndex } from "../lib/data.js";

const STEPS = [
  ["overview.step.consent", "#/enrol"],
  ["overview.step.capture", "#/capture"],
  ["overview.step.report", "#/p/SYN-C-0007"],
  ["overview.step.review", "#/review"],
  ["overview.step.annual", "#/p/SYN-C-0007/history"],
  ["overview.step.program", "#/cohort"],
];

export async function render(root, ctx) {
  const { t } = ctx;
  const title = document.createElement("h1");
  title.textContent = t("nav.overview");
  const lead = document.createElement("p");
  lead.className = "lead";
  lead.textContent = t("overview.lead");
  const cards = document.createElement("div");
  cards.className = "cards";
  for (const [key, href] of STEPS) {
    const link = document.createElement("a");
    link.className = "card";
    link.href = href;
    const name = document.createElement("strong");
    name.textContent = t(key);
    link.append(name);
    cards.append(link);
  }
  const list = document.createElement("p");
  list.className = "k";
  try {
    const index = await loadIndex();
    list.textContent = (index.pids || []).join("  ");
  } catch {
    list.textContent = "";
  }
  root.replaceChildren(title, badge("synthetic", t), lead, cards, list);
}
