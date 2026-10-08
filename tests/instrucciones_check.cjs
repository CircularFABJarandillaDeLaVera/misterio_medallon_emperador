/* Fase 3A: contenido canónico, navegación y convivencia no invasiva de las
   instrucciones. Uso: node tests/instrucciones_check.cjs */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const raiz = path.join(__dirname, "..");
const leer = (...partes) => fs.readFileSync(path.join(raiz, ...partes), "utf8");
let fallos = 0;
function ok(condicion, nombre) {
  console.log(`${condicion ? "PASS" : "FAIL"} ${nombre}`);
  if (!condicion) fallos += 1;
}

const parcial = leer("app", "templates", "_aprender_a_jugar.html");
const inicio = leer("app", "templates", "inicio.html");
const sala = leer("app", "templates", "sala.html");
const css = leer("app", "static", "css", "estilos.css");
const js = leer("app", "static", "js", "aprender_a_jugar.js");
const cartasFuente = leer("app", "datos", "jarandilla.py");

function bloqueEntre(nombre, siguiente) {
  const inicio = cartasFuente.indexOf(`${nombre}:`);
  const fin = siguiente ? cartasFuente.indexOf(`${siguiente}:`, inicio) : cartasFuente.indexOf("CARTAS:", inicio);
  return cartasFuente.slice(inicio, fin);
}
const bloques = {
  SOSPECHOSOS: bloqueEntre("SOSPECHOSOS", "LUGARES"),
  LUGARES: bloqueEntre("LUGARES", "OBJETOS"),
  OBJETOS: bloqueEntre("OBJETOS", null),
};
const idsPorGrupo = Object.fromEntries(Object.entries(bloques).map(([grupo, texto]) => [
  grupo,
  [...texto.matchAll(/\{"id": "([^"]+)"/g)].map((hallazgo) => hallazgo[1]),
]));
const ids = Object.values(idsPorGrupo).flat();
ok(
  idsPorGrupo.SOSPECHOSOS.length === 6 && idsPorGrupo.LUGARES.length === 9 &&
    idsPorGrupo.OBJETOS.length === 6 && ids.length === 21 && new Set(ids).size === 21,
  "el mazo canónico contiene 6 personajes, 9 lugares y 6 objetos únicos"
);

const extensiones = { eulalia: "jpeg" };
const faltan = [];
for (const id of idsPorGrupo.SOSPECHOSOS) {
  for (const archivo of [`${id}.png`, `${id}-nombre.${extensiones[id] || "png"}`]) {
    if (!fs.existsSync(path.join(raiz, "app", "static", "img", "personajes", archivo))) faltan.push(archivo);
  }
}
for (const id of idsPorGrupo.LUGARES) {
  if (!fs.existsSync(path.join(raiz, "app", "static", "img", "lugares", `${id}.jpeg`))) faltan.push(id);
}
for (const id of idsPorGrupo.OBJETOS) {
  if (!fs.existsSync(path.join(raiz, "app", "static", "img", "objetos", `${id}.png`))) faltan.push(id);
}
ok(faltan.length === 0, "las 21 cartas tienen todos sus recursos locales canónicos");

const imagenesTutorial = [...parcial.matchAll(/src="(\/static\/img\/[^"]+)"/g)].map((m) => m[1]);
ok(
  imagenesTutorial.length > 0 && imagenesTutorial.every((url) => fs.existsSync(path.join(raiz, "app", url))),
  "todas las imágenes usadas por las instrucciones existen"
);
ok(
  (parcial.match(/data-aprender-panel=/g) || []).length === 5 &&
    ["EL MISTERIO", "TUS CARTAS", "INVESTIGA", "SIGUE LAS PISTAS", "RESUELVE EL MISTERIO"]
      .every((titulo) => parcial.includes(titulo)),
  "las instrucciones conservan los cinco apartados acordados"
);
ok(
  ["Bruno", "Vera", "La Picota", "Zurrón de cuero", "Lucía", "Solo Bruno ve", "nadie puede refutar"]
    .every((texto) => parcial.includes(texto)),
  "el ejemplo visual explica sospecha, refutación privada y ausencia de refutador"
);
ok(
  inicio.includes("data-abrir-aprender") && inicio.includes("APRENDE A JUGAR") &&
    sala.includes("data-abrir-aprender") && sala.includes("CÓMO JUGAR") &&
    inicio.includes('{% include "_aprender_a_jugar.html" %}') &&
    sala.includes('{% include "_aprender_a_jugar.html" %}'),
  "portada y sala incluyen el mismo componente y sus accesos"
);
ok(
  /\.modal-aprender\s*\{[^}]*z-index:\s*80/.test(css) &&
    /\.aprender-contenido\s*\{[^}]*overflow-y:\s*auto/.test(css) &&
    /@media\s*\(max-width:\s*700px\)[\s\S]*?\.aprender-caja/.test(css),
  "la ayuda se apila sobre el juego, tiene scroll interno y adaptación móvil"
);
ok(
  !/WebSocket|\.send\s*\(|fetch\s*\(/.test(js),
  "el controlador de instrucciones no realiza acciones de red"
);

class Elemento {
  constructor(id = "") {
    this.id = id;
    this.hidden = false;
    this.disabled = false;
    this.dataset = {};
    this.oyentes = {};
    this.atributos = {};
    this.textContent = "";
    this.enfocado = false;
  }
  addEventListener(tipo, fn) { (this.oyentes[tipo] ||= []).push(fn); }
  click() { for (const fn of this.oyentes.click || []) fn({ target: this, currentTarget: this }); }
  focus() { documentStub.activeElement = this; this.enfocado = true; }
  setAttribute(nombre, valor) { this.atributos[nombre] = String(valor); }
  removeAttribute(nombre) { delete this.atributos[nombre]; }
  getAttribute(nombre) { return this.atributos[nombre]; }
}

const modal = new Elemento("modal-aprender");
modal.hidden = true;
const abrirInicio = new Elemento("btn-aprender-inicio");
const abrirSala = new Elemento("btn-aprender-sala");
const indices = Array.from({ length: 5 }, (_, i) => {
  const boton = new Elemento(`indice-${i}`);
  boton.dataset.aprenderPaso = String(i);
  return boton;
});
const paneles = Array.from({ length: 5 }, (_, i) => {
  const panel = new Elemento(`panel-${i}`);
  panel.hidden = i !== 0;
  return panel;
});
const elementos = {
  "modal-aprender": modal,
  "btn-anterior-aprender": new Elemento("btn-anterior-aprender"),
  "btn-siguiente-aprender": new Elemento("btn-siguiente-aprender"),
  "btn-cerrar-aprender": new Elemento("btn-cerrar-aprender"),
  "aprender-progreso": new Elemento("aprender-progreso"),
  "aprender-contenido": new Elemento("aprender-contenido"),
};
modal.querySelectorAll = (selector) => selector === "[data-aprender-paso]"
  ? indices : selector === "[data-aprender-panel]" ? paneles
    : selector === "button:not([disabled])"
      ? [...indices, elementos["btn-anterior-aprender"], elementos["btn-siguiente-aprender"], elementos["btn-cerrar-aprender"]]
      : [];
const globales = {};
const documentStub = {
  activeElement: null,
  getElementById: (id) => elementos[id] || null,
  querySelectorAll: (selector) => selector === "[data-abrir-aprender]" ? [abrirInicio, abrirSala] : [],
  addEventListener: (tipo, fn) => { (globales[tipo] ||= []).push(fn); },
};
const sandbox = { document: documentStub, console };
vm.createContext(sandbox);
vm.runInContext(js, sandbox, { filename: "aprender_a_jugar.js" });

const ventanaObligatoria = { hidden: false };
abrirSala.click();
ok(
  modal.hidden === false && paneles[0].hidden === false &&
    elementos["aprender-progreso"].textContent === "1 DE 5" && ventanaObligatoria.hidden === false,
  "abrir desde la sala conserva una ventana obligatoria y muestra el primer apartado"
);
elementos["btn-siguiente-aprender"].click();
ok(paneles[1].hidden === false && paneles[0].hidden === true, "SIGUIENTE avanza un apartado");
indices[4].click();
ok(
  paneles[4].hidden === false && elementos["btn-siguiente-aprender"].hidden === true &&
    elementos["aprender-progreso"].textContent === "5 DE 5",
  "los medallones permiten navegar directamente hasta el quinto apartado"
);
elementos["btn-anterior-aprender"].click();
ok(paneles[3].hidden === false, "ANTERIOR retrocede un apartado");

// Simula que el estado canónico cambia detrás de la ayuda: cerrar no intenta
// restaurar la ventana antigua ni altera el nuevo estado.
ventanaObligatoria.hidden = true;
elementos["btn-cerrar-aprender"].click();
ok(
  modal.hidden === true && ventanaObligatoria.hidden === true && documentStub.activeElement === abrirSala,
  "CERRAR revela el estado actualizado y devuelve el foco al acceso"
);

abrirInicio.click();
const escape = {
  key: "Escape", detenido: false, prevenido: false,
  preventDefault() { this.prevenido = true; },
  stopImmediatePropagation() { this.detenido = true; },
};
for (const fn of globales.keydown || []) fn(escape);
ok(
  modal.hidden === true && escape.prevenido && escape.detenido && documentStub.activeElement === abrirInicio,
  "Escape cierra solo la capa de ayuda y restaura el foco"
);

if (fallos) process.exit(1);
console.log("INSTRUCCIONES FASE 3A OK");
