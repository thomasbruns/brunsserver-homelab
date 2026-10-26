// Helpers mínimos compartilhados pelas páginas.
const $ = (sel, root = document) => root.querySelector(sel);

// el("div", {class: "x"}, "texto", outroNo) — monta DOM sem innerHTML.
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) node.setAttribute(k, v);
  for (const c of children) if (c != null) node.append(c);
  return node;
}

async function getJSON(url) {
  const r = await fetch(url, {cache: "no-store"});
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

function every(fn, ms) {
  fn();
  setInterval(fn, ms);
}
