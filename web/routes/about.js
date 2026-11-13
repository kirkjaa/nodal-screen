import { loadSources } from "../lib/data.js";

function p(text, className) {
  const node = document.createElement("p");
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function h2(text) {
  const node = document.createElement("h2");
  node.textContent = text;
  return node;
}

export async function render(root, ctx) {
  const { t } = ctx;
  const title = document.createElement("h1");
  title.textContent = t("heading.about");
  const slot = p(t("about.method.engine"));
  slot.dataset.slot = "about.method.engine";
  const parts = [
    title,
    h2(t("about.h.method")),
    p(t("about.method"), "copy"),
    slot,
    h2(t("about.h.assumptions")),
    p(t("about.assumptions"), "copy"),
    h2(t("about.h.limitations")),
    p(t("about.limitations"), "copy"),
    h2(t("about.h.sources")),
  ];
  const sources = await loadSources();
  if (!sources || typeof sources !== "object") {
    parts.push(p(t("about.sources.missing")));
  } else {
    for (const id of Object.keys(sources).sort()) {
      const entry = sources[id];
      if (!entry || typeof entry !== "object") continue;
      const block = document.createElement("article");
      block.className = "panel";
      const name = document.createElement("p");
      name.className = "k";
      name.textContent = id;
      block.append(name, p(entry.citation || ""), p(entry.used_for || ""));
      parts.push(block);
    }
  }
  root.replaceChildren(...parts);
}
