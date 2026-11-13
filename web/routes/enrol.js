import { badge } from "../lib/badge.js";
import { loadIndex, loadSession } from "../lib/data.js";

const ENROL_KEY = "nodal-screen-enrol";
const CONSENTS = ["adult", "guardian+assent"];

function readEnrol() {
  try {
    const raw = localStorage.getItem(ENROL_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    return data && typeof data === "object" ? data : null;
  } catch {
    return null;
  }
}

function writeEnrol(payload) {
  try {
    localStorage.setItem(ENROL_KEY, JSON.stringify(payload));
    return true;
  } catch {
    return false;
  }
}

function clearEnrol() {
  try {
    localStorage.removeItem(ENROL_KEY);
  } catch {
    /* nothing stored */
  }
}

function p(text, className) {
  const node = document.createElement("p");
  if (className) node.className = className;
  node.textContent = text;
  return node;
}

function consentBlock(t, titleKey, bodyKey) {
  const block = document.createElement("article");
  block.className = "panel consent";
  const heading = document.createElement("h2");
  heading.textContent = t(titleKey);
  const english = p(t(`${bodyKey}.en`));
  english.lang = "en";
  english.dir = "ltr";
  const arabic = p(t(`${bodyKey}.ar`));
  arabic.lang = "ar";
  arabic.dir = "rtl";
  block.append(heading, p(t("enrol.demo"), "k"), english, arabic);
  return block;
}

async function syntheticNames() {
  const index = await loadIndex();
  const names = [];
  for (const pid of index.pids || []) {
    const session = await loadSession(pid);
    const name = session?.participant?.display_name;
    if (name && !names.includes(name)) names.push(name);
  }
  return names;
}

export async function render(root, ctx) {
  const { t, lang } = ctx;
  const names = await syntheticNames();
  const title = document.createElement("h1");
  title.textContent = t("heading.enrol");
  const result = p("");
  const form = document.createElement("form");
  form.className = "stack";

  const who = document.createElement("fieldset");
  who.className = "choice";
  const legend = document.createElement("legend");
  legend.textContent = t("enrol.who");
  who.append(legend);
  for (const value of CONSENTS) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "consent";
    input.value = value;
    if (value === "adult") input.checked = true;
    label.append(input, document.createTextNode(t(value === "adult" ? "enrol.who.adult" : "enrol.who.guardian")));
    who.append(label);
  }

  const nameField = document.createElement("label");
  nameField.className = "field";
  const nameSpan = document.createElement("span");
  nameSpan.textContent = t("enrol.name");
  const nameSelect = document.createElement("select");
  nameSelect.name = "display_name";
  for (const name of names) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    nameSelect.append(option);
  }
  nameField.append(nameSpan, nameSelect);

  const langField = document.createElement("label");
  langField.className = "field";
  const langSpan = document.createElement("span");
  langSpan.textContent = t("enrol.language");
  const langSelect = document.createElement("select");
  langSelect.name = "language";
  for (const value of ["en", "ar"]) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = t(`enrol.lang.${value}`);
    langSelect.append(option);
  }
  langSelect.value = lang === "ar" ? "ar" : "en";
  langField.append(langSpan, langSelect);

  const agreeLabel = document.createElement("label");
  agreeLabel.className = "choice";
  const agree = document.createElement("input");
  agree.type = "checkbox";
  agree.name = "agree";
  agreeLabel.append(agree, document.createTextNode(t("enrol.agree")));

  const actions = document.createElement("div");
  actions.className = "actions";
  const submit = document.createElement("button");
  submit.type = "submit";
  submit.textContent = t("enrol.submit");
  const optOut = document.createElement("button");
  optOut.type = "button";
  optOut.textContent = t("enrol.optout");
  actions.append(submit, optOut);
  form.append(who, nameField, langField, agreeLabel, actions);

  function endOptOut() {
    clearEnrol();
    form.hidden = true;
    root.querySelectorAll(".consent").forEach((node) => {
      node.hidden = true;
    });
    result.textContent = t("enrol.optout.result");
  }

  optOut.addEventListener("click", endOptOut);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const consent = new FormData(form).get("consent");
    const displayName = nameSelect.value;
    const language = langSelect.value;
    if (!CONSENTS.includes(consent) || !["en", "ar"].includes(language)) return;
    if (displayName && !names.includes(displayName)) return;
    const payload = {
      consent,
      language,
      agree: agree.checked,
      at: new Date().toISOString(),
    };
    if (displayName) payload.display_name = displayName;
    result.textContent = writeEnrol(payload) ? t("enrol.stored") : t("enrol.keepfail");
  });

  const stored = readEnrol();
  if (stored) result.textContent = t("enrol.stored");

  root.replaceChildren(
    title,
    badge("synthetic", t),
    p(t("enrol.lead"), "lead"),
    consentBlock(t, "enrol.who.adult", "enrol.body.adult"),
    consentBlock(t, "enrol.who.guardian", "enrol.body.guardian"),
    form,
    result,
  );
}
