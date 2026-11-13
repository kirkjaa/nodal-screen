import { loadCatalog, readLang, storeLang, translate } from "./lib/i18n.js";
import * as overview from "./routes/overview.js";
import * as enrol from "./routes/enrol.js";
import * as capture from "./routes/capture.js";
import * as review from "./routes/review.js";
import * as cohort from "./routes/cohort.js";
import * as about from "./routes/about.js";
import * as participant from "./routes/participant.js";
import * as history from "./routes/history.js";
import * as crossover from "./routes/crossover.js";

const NAV = [
  ["#/", "nav.overview"],
  ["#/enrol", "nav.enrol"],
  ["#/capture", "nav.capture"],
  ["#/review", "nav.review"],
  ["#/cohort", "nav.cohort"],
  ["#/about", "nav.about"],
  ["#/crossover", "nav.crossover"],
];

const catalog = await loadCatalog();
let lang = readLang();

function t(key) {
  return translate(catalog, lang, key);
}

function applyDocument() {
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  document.title = t("product");
  for (const node of document.querySelectorAll("[data-i18n]")) {
    node.textContent = t(node.dataset.i18n);
  }
  const nav = document.querySelector("#nav");
  nav.replaceChildren();
  const hash = location.hash || "#/";
  for (const [href, key] of NAV) {
    const link = document.createElement("a");
    link.href = href;
    link.textContent = t(key);
    if (hash === href || (href === "#/" && (hash === "" || hash === "#"))) link.setAttribute("aria-current", "page");
    nav.append(link);
  }
  const button = document.querySelector("#lang");
  button.textContent = t("lang.switch");
}

function routeOf(hash) {
  const text = hash || "#/";
  const historyMatch = text.match(/^#\/p\/([^/]+)\/history$/);
  if (historyMatch) return { mod: history, pid: decodeURIComponent(historyMatch[1]), href: text };
  const personMatch = text.match(/^#\/p\/([^/]+)$/);
  if (personMatch) return { mod: participant, pid: decodeURIComponent(personMatch[1]), href: text };
  const table = {
    "#/": overview,
    "#": overview,
    "#/enrol": enrol,
    "#/capture": capture,
    "#/review": review,
    "#/cohort": cohort,
    "#/about": about,
    "#/crossover": crossover,
  };
  return { mod: table[text] || overview, pid: null, href: text };
}

async function draw() {
  applyDocument();
  const root = document.querySelector("#view");
  const route = routeOf(location.hash);
  await route.mod.render(root, { t, lang, pid: route.pid });
}

document.querySelector("#lang").addEventListener("click", () => {
  lang = lang === "ar" ? "en" : "ar";
  storeLang(lang);
  draw();
});
window.addEventListener("hashchange", draw);
draw();
