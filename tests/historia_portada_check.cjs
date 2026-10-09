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
  (html.match(/data-historia-escena=/g) || []).length === 14 && titulos.every((titulo) => html.includes(titulo)),
  "la introducción conserva las ocho escenas canónicas y suma seis presentaciones"
);
const escenasHtml = [...html.matchAll(/<article class="historia-escena[\s\S]*?<\/article>/g)].map((m) => m[0]);
const sospechosos = ["VERA", "BRUNO", "LUCÍA", "ÁLVARO", "MATEO", "EULALIA"];
const indiceEscena = (texto) => escenasHtml.findIndex((escena) => escena.includes(texto));
ok(
  indiceEscena("SEIS PERSONAS BAJO INVESTIGACIÓN") === 4 &&
    sospechosos.every((nombre, indice) => escenasHtml[indice + 5].includes(nombre)) &&
    indiceEscena("NUEVE LUGARES POSIBLES") === 11 &&
    escenasHtml[12].includes("VII · LA INVESTIGACIÓN") && escenasHtml[13].includes("VIII · EL DESAFÍO"),
  "seis personajes precede las cartas, nueve ubicaciones las sigue y el cierre conserva su orden"
);
const textosPersonajes = [
  {
    descripcion: "Vera conoce cada rincón y cada leyenda de Jarandilla. Está preparando una investigación sobre la estancia de Carlos V y siempre lleva su cámara para documentar cualquier hallazgo.",
    motivo: "Quería fotografiar el medallón y estudiarlo detenidamente antes de incluirlo en su investigación.",
    frase: "«Toda historia deja una pista»",
  },
  {
    descripcion: "Bruno ha trabajado la piedra de Jarandilla durante toda su vida. Conoce las marcas de sus edificios históricos y sabe reconocer cada herramienta y cada tipo de roca.",
    motivo: "Quería utilizar el medallón como modelo para crear una réplica exacta en piedra.",
    frase: "«La piedra recuerda lo que otros olvidan»",
  },
  {
    descripcion: "Lucía conoce las plantas y los remedios tradicionales de La Vera. Su mirada atenta y sus conocimientos le permiten descubrir rastros que otros pasarían por alto.",
    motivo: "Sospechaba que el medallón ocultaba restos de una antigua sustancia o una inscripción secreta.",
    frase: "«Hasta el secreto más antiguo deja algún rastro»",
  },
  {
    descripcion: "Álvaro conoce todos los caminos, montes y senderos de Jarandilla. Su prudencia y sentido de la orientación le permiten encontrar señales que otros no ven.",
    motivo: "Aseguraba haber encontrado el medallón años atrás y creía que le pertenecía por derecho.",
    frase: "«Todos los caminos dejan señales»",
  },
  {
    descripcion: "Mateo lleva toda la vida preparando los escobones de Jarandilla. Conoce cada rama, cada atadura y cada historia relacionada con esta antigua tradición.",
    motivo: "Afirmaba que el medallón había pertenecido a su familia y debía volver a sus manos.",
    frase: "«El fuego ilumina hasta los secretos más antiguos»",
  },
  {
    descripcion: "Eulalia ha dedicado toda su vida al cultivo, secado y molienda de los pimientos de la Vera. Reconoce cada variedad por su aroma y guarda recetas transmitidas durante generaciones.",
    motivo: "Aseguraba que el medallón escondía una marca relacionada con una antigua receta familiar y quería examinarlo antes de que saliera de Jarandilla.",
    frase: "«Los secretos, como el pimentón, se descubren por su aroma»",
  },
];
ok(
  textosPersonajes.every((textos, indice) => {
    const escena = escenasHtml[indice + 5];
    return escena.includes(textos.descripcion) && escena.includes(textos.motivo) && escena.includes(textos.frase);
  }) && (html.match(/<strong>POSIBLE MOTIVO<\/strong>/g) || []).length === 6,
  "las seis escenas reproducen literalmente descripción, posible motivo y frase originales"
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
  ["EL MISTERIO", "DEL MEDALLÓN IMPERIAL", "CREAR PARTIDA", "UNIRSE A UNA PARTIDA", "CARGAR PARTIDA", "APRENDE A JUGAR", "VER LA HISTORIA"]
    .every((texto) => html.includes(texto)) && html.includes('data-abrir-aprender'),
  "la portada conserva sus cinco acciones reales y reutiliza Aprende a jugar"
);
ok(
  html.includes('class="portada-identidad solo-lectores"') &&
    css.includes('--portada-imagen: url("/static/img/portada/portada-fondo.png")') &&
    fs.existsSync(path.join(raiz, "app", "static", "img", "portada", "portada-fondo.png")) &&
    !css.includes("portada referencia.png"),
  "la portada usa el fondo limpio y no duplica visualmente su identidad integrada"
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
const escenas = Array.from({ length: 14 }, (_, indice) => {
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
  "btn-retroceder-historia": new Elemento("btn-retroceder-historia"),
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
  historia.hidden === false && escenas[0].hidden === false && elementos["historia-contador"].textContent === "1 DE 14",
  "la primera visita abre la historia en la escena inicial"
);
const demora = ejecutarAutomatico();
ok(
  demora === 6500 && escenas[1].hidden === false && elementos["historia-contador"].textContent === "2 DE 14",
  "la reproducción automática avanza con 6,5 segundos por escena"
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
elementos["btn-retroceder-historia"].click();
ok(escenas[1].hidden === false, "RETROCEDER vuelve a la escena anterior");

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
const flechaIzquierda = { key: "ArrowLeft", preventDefault() { this.prevenido = true; } };
for (const fn of eventosDocumento.keydown || []) fn(flechaIzquierda);
ok(flechaIzquierda.prevenido && escenas[0].hidden === false, "la flecha izquierda permite retroceder con teclado");
elementos["btn-avanzar-historia"].click();

for (let i = 0; i < 12; i += 1) elementos["btn-avanzar-historia"].click();
ok(
  escenas[13].hidden === false && elementos["btn-avanzar-historia"].textContent === "ENTRAR AL MISTERIO" &&
    progreso.getAttribute("aria-valuenow") === "14",
  "la escena final ofrece entrar al misterio y actualiza el progreso accesible"
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
