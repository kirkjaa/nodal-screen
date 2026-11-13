import { loadCatalog, translate } from "./i18n.js";

const DRAFTED = "Drafted by AI from the measurements. A clinician approves before anything is sent.";

let catalogPromise;

function catalog() {
  if (!catalogPromise) catalogPromise = loadCatalog();
  return catalogPromise;
}

function textFor(block, lang) {
  if (!block || typeof block !== "object") return "";
  const value = block[lang] || block.en || "";
  return typeof value === "string" ? value : "";
}

export async function renderAiTexts(session, lang) {
  const books = await catalog();
  const t = (key) => translate(books, lang, key);
  const root = document.createElement("section");
  root.className = "panel ai-block";
  const heading = document.createElement("h2");
  heading.textContent = t("ai.heading");
  root.append(heading);
  const texts = session?.ai_texts || {};
  const letter = texts.family_letter;
  const brief = texts.clinician_brief;
  if (letter || brief) {
    if (letter) {
      const name = document.createElement("p");
      name.className = "k";
      name.textContent = t("ai.family");
      const body = document.createElement("p");
      body.textContent = textFor(letter, lang);
      root.append(name, body);
    }
    if (brief) {
      const name = document.createElement("p");
      name.className = "k";
      name.textContent = t("ai.brief");
      const body = document.createElement("p");
      body.textContent = textFor(brief, lang);
      root.append(name, body);
    }
    const note = document.createElement("p");
    note.textContent = lang === "ar" ? t("ai.drafted") : DRAFTED;
    root.append(note);
  } else {
    const none = document.createElement("p");
    none.textContent = t("ai.none");
    root.append(none);
  }
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = t("ai.ask");
  const out = document.createElement("pre");
  out.className = "ai-out";
  const pid = session?.participant?.pid || "";
  button.addEventListener("click", async () => {
    if (!pid) {
      out.textContent = t("ai.error");
      return;
    }
    try {
      const res = await fetch(`/api/ai/${encodeURIComponent(pid)}`, { method: "POST" });
      out.textContent = await res.text();
    } catch {
      out.textContent = t("ai.error");
    }
  });
  root.append(button, out);
  return root;
}
