const TEXT = {
  synthetic: "badge.synthetic",
  "simulated-m1": "badge.simulated-m1",
  measured: "badge.measured",
};

export function badge(provenance, t) {
  const el = document.createElement("p");
  el.className = "badge";
  el.textContent = t(TEXT[provenance] || "badge.synthetic");
  return el;
}
