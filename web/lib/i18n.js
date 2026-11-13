export async function loadCatalog() {
  const load = (name) => fetch(`i18n/${name}.json`).then((res) => {
    if (!res.ok) throw new Error(name);
    return res.json();
  });
  const [en, ar] = await Promise.all([load("en"), load("ar")]);
  return { en, ar };
}

export function readLang() {
  try {
    return localStorage.getItem("nodal-screen-lang") === "ar" ? "ar" : "en";
  } catch {
    return "en";
  }
}

export function storeLang(lang) {
  try {
    localStorage.setItem("nodal-screen-lang", lang);
  } catch {
    /* keep the choice for this page only */
  }
}

export function translate(catalog, lang, key) {
  return catalog[lang]?.[key] ?? catalog.en[key] ?? key;
}
