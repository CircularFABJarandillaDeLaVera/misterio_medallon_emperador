/* Fase 3B: historia canónica, portada, controles y preservación de formularios.
   Uso: node tests/historia_portada_check.cjs */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const raiz = path.join(__dirname, "..");
const leer = (...partes) => fs.readFileSync(path.join(raiz, ...partes), "utf8");
const html = leer("app", "templates", "inicio.html");
const css = leer("app", "static", "css", "estilos.css");
const js = leer("app", "static", "js", "historia.js");
let fallos = 0;
function ok(condicion, nombre) {
  console.log(`${condicion ? "PASS" : "FAIL"} ${nombre}`);
  if (!condicion) fallos += 1;
}

const titulos = [
  "LA LLEGADA", "EL LEGADO", "LOS PASADIZOS", "LA DESAPARICIÓN",
  "LOS SOSPECHOSOS", "LAS LOCALIZACIONES", "LA INVESTIGACIÓN", "EL DESAFÍO",
];
ok(
  (html.match(/data-historia-escena=/g) || []).length === 8 && titulos.every((titulo) => html.includes(titulo)),
  "la introducción contiene las ocho escenas canónicas"
);
ok(
  html.includes("CONTEXTO HISTÓRICO · 1556") && html.includes("FICCIÓN DEL JUEGO") &&
    html.includes("LEYENDA LOCAL") && html.includes("templarios"),
  "el relato distingue contexto histórico, ficción y leyenda"
);
ok(
  ["Vera", "Bruno", "Lucía", "Álvaro", "Mateo", "Eulalia"].every((nombre) => html.includes(nombre)) &&
    (html.match(/class="historia-retratos"[\s\S]*?<\/div>/) || [""])[0].match(/<figure>/g).length === 6,
  "la escena de sospechosos usa los seis personajes reales"
);
const bloqueLugares = (html.match(/class="historia-localizaciones"[\s\S]*?<\/div>/) || [""])[0];
ok((bloqueLugares.match(/<img /g) || []).length === 9, "la triangulación muestra las nueve localizaciones reales");
ok(
  html.includes("Un sospechoso. Un lugar. Un objeto. Decenas de pistas. Pero una sola verdad.") &&
    html.includes("¿Serás capaz de descubrirla?"),
  "la escena final conserva el desafío acordado"
);

const imagenes = [...html.matchAll(/src="(\/static\/img\/[^"]+)"/g)].map((m) => m[1]);
ok(
  imagenes.length > 0 && imagenes.every((url) => fs.existsSync(path.join(raiz, "app", url))),
  "todos los recursos gráficos utilizados existen localmente"
);
ok(
  ["EL MISTERIO", "DEL MEDALLÓN IMPERIAL", "CREAR PARTIDA", "UNIRSE A UNA PARTIDA", "APRENDE A JUGAR", "VER LA HISTORIA"]
    .every((texto) => html.includes(texto)) && html.includes('data-abrir-aprender'),
  "la nueva portada contiene las cuatro acciones y reutiliza Aprende a jugar"
);
ok(
  html.includes('{% include "_aprender_a_jugar.html" %}') && html.includes("/static/js/aprender_a_jugar.js?v=fase3a"),
  "la fase 3A sigue incluida sin duplicar su componente"
);
ok(
  /@media\s*\(max-width:\s*760px\)[\s\S]*?\.historia-escena/.test(css) &&
    /@media\s*\(max-width:\s*420px\)[\s\S]*?\.historia-controles/.test(css) &&
    /@media\s*\(prefers-reduced-motion:\s*reduce\)[\s\S]*?historia-escena-activa/.test(css),
  "la historia contempla móvil estrecho y movimiento reducido"
);
ok(
  !/fetch\s*\(|WebSocket|\.send\s*\(/.test(js) &&
    !/\b(alias|codigo|modo)\b/.test(js),
  "el controlador narrativo no usa red ni conoce los campos de partida"
);

function listaClases() {
  const valores = new Set();
  return {
    add(...clases) { clases.forEach((clase) => valores.add(clase)); },
    remove(...clases) { clases.forEach((clase) => valores.delete(clase)); },
    toggle(clase, fuerza) {
      if (fuerza === undefined) fuerza = !valores.has(clase);
      fuerza ? valores.add(clase) : valores.delete(clase);
    },
    contains(clase) { return valores.has(clase); },
  };
}

class Elemento {
  constructor(id = "") {
    this.id = id;
    this.hidden = false;
    this.textContent = "";
    this.value = "";
    this.style = {};
    this.classList = listaClases();
    this.atributos = {};
    this.oyentes = {};
  }
  addEventListener(tipo, fn) { (this.oyentes[tipo] ||= []).push(fn); }
  click() { for (const fn of this.oyentes.click || []) fn({ currentTarget: this, target: this }); }
  focus() { documentStub.activeElement = this; }
  setAttribute(nombre, valor) { this.atributos[nombre] = String(valor); }
  getAttribute(nombre) { return this.atributos[nombre]; }
}

const historia = new Elemento("historia-intro");
historia.hidden = true;
const escenas = Array.from({ length: 8 }, (_, indice) => {
  const escena = new Elemento(`escena-${indice}`);
  escena.hidden = indice !== 0;
  return escena;
});
const progreso = new Elemento("progreso");
historia.querySelectorAll = (selector) => selector === "[data-historia-escena]" ? escenas : [];
historia.querySelector = (selector) => selector === "[role='progressbar']" ? progreso : null;

const elementos = {
  "historia-intro": historia,
  "btn-ver-historia": new Elemento("btn-ver-historia"),
  "btn-saltar-historia": new Elemento("btn-saltar-historia"),
  "btn-pausar-historia": new Elemento("btn-pausar-historia"),
  "btn-avanzar-historia": new Elemento("btn-avanzar-historia"),
  "historia-contador": new Elemento("historia-contador"),
  "historia-barra": new Elemento("historia-barra"),
  alias: new Elemento("alias"),
  codigo: new Elemento("codigo"),
  "alias-unirse": new Elemento("alias-unirse"),
};
const eventosDocumento = {};
const documentStub = {
  activeElement: null,
  body: new Elemento("body"),
  getElementById(id) { return elementos[id] || null; },
  addEventListener(tipo, fn) { (eventosDocumento[tipo] ||= []).push(fn); },
};
const memoria = new Map();
const sessionStorageStub = {
  getItem(clave) { return memoria.has(clave) ? memoria.get(clave) : null; },
  setItem(clave, valor) { memoria.set(clave, String(valor)); },
};
let siguienteTemporizador = 1;
const temporizadores = new Map();
function setTimeoutStub(fn, demora) {
  const id = siguienteTemporizador++;
  temporizadores.set(id, { fn, demora });
  return id;
}
function clearTimeoutStub(id) { temporizadores.delete(id); }
function ejecutarAutomatico() {
  const entrada = [...temporizadores.entries()].at(-1);
  if (!entrada) return false;
  temporizadores.delete(entrada[0]);
  entrada[1].fn();
  return entrada[1].demora;
}

const sandbox = {
  console,
  document: documentStub,
  window: { matchMedia: () => ({ matches: false }) },
  sessionStorage: sessionStorageStub,
  setTimeout: setTimeoutStub,
  clearTimeout: clearTimeoutStub,
};
vm.createContext(sandbox);
vm.runInContext(js, sandbox, { filename: "historia.js" });

ok(
  historia.hidden === false && escenas[0].hidden === false && elementos["historia-contador"].textContent === "1 DE 8",
  "la primera visita abre la historia en la escena inicial"
);
const demora = ejecutarAutomatico();
ok(
  demora === 6500 && escenas[1].hidden === false && elementos["historia-contador"].textContent === "2 DE 8",
  "la reproducción automática avanza con una duración total aproximada de 52 segundos"
);

elementos["btn-pausar-historia"].click();
ok(
  elementos["btn-pausar-historia"].textContent === "REANUDAR" && temporizadores.size === 0,
  "PAUSAR detiene el avance automático"
);
elementos["btn-pausar-historia"].click();
ok(
  elementos["btn-pausar-historia"].textContent === "PAUSAR" && temporizadores.size === 1,
  "REANUDAR recupera el avance automático"
);
elementos["btn-avanzar-historia"].click();
ok(escenas[2].hidden === false, "AVANZAR cambia de escena inmediatamente");

elementos.alias.value = "Paco";
elementos.codigo.value = "JARA-TEST";
elementos["alias-unirse"].value = "Ana";
elementos["btn-saltar-historia"].click();
ok(
  historia.hidden && memoria.get("historia_intro_vista") === "1" &&
    elementos.alias.value === "Paco" && elementos.codigo.value === "JARA-TEST" && elementos["alias-unirse"].value === "Ana",
  "SALTAR vuelve a la portada sin borrar datos de crear o unirse"
);

elementos["btn-ver-historia"].click();
ok(historia.hidden === false && escenas[0].hidden === false, "VER LA HISTORIA reinicia el relato desde la portada");
documentStub.activeElement = elementos["btn-avanzar-historia"];
const tabulador = { key: "Tab", shiftKey: false, preventDefault() { this.prevenido = true; } };
for (const fn of eventosDocumento.keydown || []) fn(tabulador);
ok(
  tabulador.prevenido && documentStub.activeElement === elementos["btn-saltar-historia"],
  "el foco de teclado permanece dentro de la introducción"
);
const flecha = { key: "ArrowRight", preventDefault() { this.prevenido = true; } };
for (const fn of eventosDocumento.keydown || []) fn(flecha);
ok(flecha.prevenido && escenas[1].hidden === false, "la flecha derecha permite avanzar con teclado");

for (let i = 0; i < 6; i += 1) elementos["btn-avanzar-historia"].click();
ok(
  escenas[7].hidden === false && elementos["btn-avanzar-historia"].textContent === "ENTRAR AL MISTERIO" &&
    progreso.getAttribute("aria-valuenow") === "8",
  "la octava escena ofrece entrar al misterio y actualiza el progreso accesible"
);
elementos["btn-avanzar-historia"].click();
ok(historia.hidden === true, "ENTRAR AL MISTERIO muestra la portada sin espera adicional");

sandbox.window.matchMedia = () => ({ matches: true });
elementos["btn-ver-historia"].click();
ok(
  elementos["btn-pausar-historia"].textContent === "REPRODUCIR" && temporizadores.size === 0,
  "movimiento reducido desactiva el avance automático hasta una interacción"
);
elementos["btn-saltar-historia"].click();

if (fallos) process.exit(1);
console.log("HISTORIA Y PORTADA FASE 3B OK");
