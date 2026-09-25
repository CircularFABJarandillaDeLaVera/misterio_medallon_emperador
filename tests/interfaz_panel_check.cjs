/* Harness Fase 8A: panel contextual, cabecera compacta, peón activo,
   peones clicables con prioridad y reduced-motion.
   Uso: node tests/interfaz_panel_check.cjs */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

let fallos = 0;
function ok(condicion, nombre) {
  console.log(`${condicion ? "PASS" : "FAIL"} ${nombre}`);
  if (!condicion) fallos += 1;
}

function claseLista() {
  const clases = new Set();
  return {
    add(...cs) { cs.forEach((c) => clases.add(c)); },
    remove(...cs) { cs.forEach((c) => clases.delete(c)); },
    toggle(c, f) { if (f === undefined) { clases.has(c) ? clases.delete(c) : clases.add(c); } else if (f) clases.add(c); else clases.delete(c); },
    contains(c) { return clases.has(c); },
  };
}

function makeElemento(tag) {
  return {
    tag, children: [], hidden: true, disabled: false, style: {},
    className: "", classList: claseLista(), value: "", options: [],
    selectedIndex: -1, parentElement: { hidden: false }, dataset: {},
    _texto: "", _attrs: {}, _oyentes: {},
    set textContent(v) { this.children = []; this._texto = String(v); },
    get textContent() {
      return this._texto + this.children.map((h) => h.textContent).join("");
    },
    set innerHTML(v) { this.children = []; this._texto = ""; this._html = String(v); },
    get innerHTML() { return this._html || ""; },
    appendChild(h) { this.children.push(h); return h; },
    addEventListener(e, fn) { (this._oyentes[e] = this._oyentes[e] || []).push(fn); },
    click() { (this._oyentes.click || []).forEach((fn) => fn()); },
    setAttribute(k, v) { this._attrs[k] = String(v); },
    getAttribute(k) { return this._attrs[k]; },
    select() {}, focus() {},
  };
}

const registro = {};
const cuerpo = makeElemento("body");
const documentStub = {
  getElementById(id) {
    if (!registro[id]) registro[id] = makeElemento("div");
    return registro[id];
  },
  createElement: makeElemento,
  body: cuerpo,
};
registro.codigo = makeElemento("p");
registro.codigo.textContent = "JARA-TEST";

const enviados = [];
class WebSocketFalso {
  send(mensaje) { enviados.push(JSON.parse(mensaje)); }
}
class RenderFalso {
  actualizar() {}
}

const sandbox = {
  console,
  document: documentStub,
  window: {
    location: { protocol: "http:", host: "localhost:8000" },
    TableroCanvas: RenderFalso,
  },
  sessionStorage: { getItem: () => "jug-test", setItem() {} },
  fetch: () => ({ then: () => ({ then() {} }) }),
  WebSocket: WebSocketFalso,
};
vm.createContext(sandbox);
vm.runInContext(
  fs.readFileSync(path.join(__dirname, "..", "app", "static", "js", "sala.js"), "utf8"),
  sandbox,
  { filename: "sala.js" }
);

const $ = (id) => documentStub.getElementById(id);

function salaBase(modo = "tablero") {
  return {
    codigo: "JARA-TEST", modo, estado: "iniciada",
    alias: "Yo", es_anfitrion: true, personaje_id: "vera",
    personaje: "Vera, la cronista", mis_cartas: [
      { id: "vera", nombre: "Vera, la cronista", categoria: "sospechoso" },
      { id: "baul-imperial", nombre: "Baúl imperial", categoria: "objeto" },
    ],
    investigacion: [
      { id: "vera", nombre: "Vera, la cronista", categoria: "sospechoso", estado: "la_tengo" },
      { id: "bruno", nombre: "Bruno, el cantero", categoria: "sospechoso", estado: "vista" },
      { id: "lucia", nombre: "Lucía, la boticaria", categoria: "sospechoso", estado: "sin_informacion" },
      { id: "alvaro", nombre: "Álvaro, el guardabosques", categoria: "sospechoso", estado: "sin_informacion" },
      { id: "mateo", nombre: "Mateo, el escobero", categoria: "sospechoso", estado: "sin_informacion" },
      { id: "eulalia", nombre: "Eulalia, la pimentonera", categoria: "sospechoso", estado: "sin_informacion" },
      { id: "parador", nombre: "Parador", categoria: "lugar" },
      { id: "baul-imperial", nombre: "Baúl imperial", categoria: "objeto", estado: "la_tengo" },
      { id: "cantaro-barro", nombre: "Cántaro de barro", categoria: "objeto", estado: "sin_informacion" },
      { id: "saco-pimenton", nombre: "Saco de pimentón", categoria: "objeto", estado: "sin_informacion" },
      { id: "zurron-cuero", nombre: "Zurrón de cuero", categoria: "objeto", estado: "sin_informacion" },
      { id: "caja-herramientas", nombre: "Caja de herramientas", categoria: "objeto", estado: "sin_informacion" },
      { id: "libro-hueco", nombre: "Libro hueco", categoria: "objeto", estado: "vista" },
    ],
    es_mi_turno: true, activo_investigacion: true,
    jugadores: [
      { alias: "Yo", personaje: "Vera, la cronista", personaje_id: "vera", tipo: "humano", activo: true, num_cartas: 3, es_anfitrion: true, posicion: { id: "parador", nombre: "Parador", tipo: "ubicacion" } },
      { alias: "Rival", personaje: "Bruno, el cantero", personaje_id: "bruno", tipo: "pnj", activo: true, num_cartas: 3, posicion: { id: "parador", nombre: "Parador", tipo: "ubicacion" } },
    ],
    orden: [
      { alias: "Yo", personaje: "Vera, la cronista", tipo: "humano", activo: true },
      { alias: "Rival", personaje: "Bruno, el cantero", tipo: "pnj", activo: true },
    ],
    turno_alias: "Yo", turno_tipo: "humano", pnj_pensando_alias: null,
    jugada: { estado: "esperando_movimiento" },
    posicion: { id: "parador", nombre: "Parador", tipo: "ubicacion" },
    movimiento: { fase: "esperando_movimiento", puede_tirar: true, tirada: null },
    resultado_final: null, ganador_alias: null,
  };
}

function fijarGlobales() {
  vm.runInContext(`TABLERO_VISUAL = { nodos: [
    { id: "parador", tipo: "ubicacion", nombre: "Parador", imagen_tarjeta: "/static/img/lugares/parador.jpeg" },
    { id: "plaza-constitucion", tipo: "ubicacion", nombre: "Plaza", imagen_tarjeta: "/static/img/lugares/plaza-constitucion.jpeg" }
  ] };`, sandbox);
  vm.runInContext(`PERSONAJES = ${JSON.stringify(salaBase().investigacion.filter((c) => c.categoria === "sospechoso"))};`, sandbox);
  const recursos = {};
  salaBase().investigacion.filter((c) => c.categoria !== "lugar").forEach((c) => {
    recursos[c.id] = c.categoria === "sospechoso"
      ? { nombre: `/static/img/personajes/${c.id}-nombre.png`, principal: `/static/img/personajes/${c.id}.png` }
      : { principal: `/static/img/objetos/${c.id}.jpeg` };
  });
  vm.runInContext(`RECURSOS_VISUALES = ${JSON.stringify(recursos)};`, sandbox);
}

// 1-4. Cabecera compacta y listados técnicos fuera de la vista principal.
fijarGlobales();
documentStub.getElementById("tablero-canvas").getContext = () => ({});
const sala = salaBase();
vm.runInContext(`ultimaSala = ${JSON.stringify(sala)};`, sandbox);
sandbox.pintarSala(sala);
ok($("partida").hidden === false, "la partida se muestra");
ok($("bloque-jugadores").hidden === true, "jugadores no permanentes en partida");
ok($("bloque-orden").hidden === true, "orden no permanente en partida");
ok($("bloque-codigo").hidden === true, "código grande fuera de la vista principal");
ok(
  $("resumen-sala").hidden === false &&
    $("resumen-sala").textContent.includes("JARA-TEST"),
  "resumen discreto sala"
);
ok(cuerpo.classList.contains("en-partida"), "marca en-partida para cabecera compacta");
ok($("tablero-ayuda").textContent === "", "sin texto técnico permanente en zona principal");
const salaLobby = {
  codigo: "JARA-TEST", modo: "tablero", estado: "esperando",
  es_anfitrion: true, jugadores: [], orden: [],
};
sandbox.pintarSala(salaLobby);
ok($("partida").hidden === true, "lobby oculta la partida");
ok($("bloque-jugadores").hidden === false && $("bloque-orden").hidden === false, "lobby recupera listados");
ok(!cuerpo.classList.contains("en-partida"), "lobby sin marca en-partida");
sandbox.pintarSala(sala);

// Panel por defecto: siguiente acción / turno ajeno.
ok($("vista-contextual").textContent === "Tira el dado.", "panel indica la siguiente acción");
const salaRival = { ...sala, es_mi_turno: false, turno_alias: "Rival" };
sandbox.pintarSala(salaRival);
ok($("vista-contextual").textContent.includes("Turno de Rival"), "panel informa turno ajeno");
vm.runInContext(`ultimaSala = ${JSON.stringify(sala)};`, sandbox);
sandbox.pintarSala(sala);

// 8. Copiar código.
let copiado = null;
sandbox.navigator = { clipboard: { writeText(t) { copiado = t; return { then(fn) { fn(); } }; } } };
$("btn-copiar-codigo").click();
ok(copiado === "JARA-TEST" && $("btn-copiar-codigo").textContent === "¡COPIADO!", "copiar código discreto");

// 11-15. Modal contextual de ubicación con ocupantes reales y acciones.
sandbox.verUbicacion("parador");
const vista = $("modal-contextual-titulo").textContent + $("modal-contextual-detalle").textContent;
ok(vista.includes("Parador"), "ubicación muestra su nombre");
ok(
  $("imagen-ubicacion").src === "/static/img/lugares/parador.jpeg",
  "ubicación muestra su tarjeta"
);
const botones = [];
(function recogeBotones(nodo) {
  if (nodo.tag === "button") botones.push(nodo.textContent);
  nodo.children.forEach(recogeBotones);
})($("modal-contextual-detalle"));
ok(botones.includes("Yo") && botones.includes("Rival"), "ocupantes reales desde posiciones");
ok($("btn-mover-ubicacion-canvas").hidden, "sin destino legal no hay MOVER AQUÍ");
ok(!botones.includes("FORMULAR SOSPECHA"), "sin permiso del servidor no hay sospecha");
sandbox.verUbicacion("plaza-constitucion");
ok($("modal-contextual-detalle").textContent.includes("No hay personajes aquí."), "ubicación vacía discreta");

// 13. Ocupante abre su personaje (solo público).
sandbox.verUbicacion("parador");
$("modal-contextual-detalle").children
  .find((h) => h.tag === "div").children
  .find((b) => b.textContent === "Rival").click();
ok($("modal-contextual-titulo").textContent.includes("Bruno, el cantero"), "ocupante abre su personaje");
ok(
  $("imagen-ubicacion").src === "/static/img/personajes/bruno.png",
  "personaje muestra su carta pública"
);
ok(!$("modal-contextual-detalle").textContent.includes("LA TENGO"), "personaje sin datos privados");
ok(
  !$("modal-contextual-detalle").textContent.includes("CARTAS") &&
    !$("modal-contextual-detalle").textContent.includes("INVESTIGACIÓN") &&
    !$("modal-contextual-detalle").textContent.includes("RESOLVER"),
  "ficha de personaje sin herramientas globales"
);
ok($("vista-contextual").textContent === "Tira el dado.", "panel derecho permanece en estado base");

// El personaje propio ofrece solo la investigación unificada; otros no.
sandbox.verPersonaje("vera");
const detallePropio = $("modal-contextual-detalle");
const botonesPropios = detallePropio.children.filter((h) => h.tag === "button");
ok(
  detallePropio.children.some((h) => h.tag === "p" && h.textContent === "Yo"),
  "personaje propio muestra solo el alias"
);
ok(
  !botonesPropios.some((b) => b.textContent === "CARTAS") &&
    botonesPropios.some((b) => b.textContent === "INVESTIGACIÓN") &&
    !botonesPropios.some((b) => b.textContent === "RESOLVER") &&
    !botonesPropios.some((b) => b.textContent === "FORMULAR SOSPECHA"),
  "personaje propio ofrece INVESTIGACIÓN sin acceso redundante a CARTAS"
);
botonesPropios.find((b) => b.textContent === "INVESTIGACIÓN").click();
ok($("modal-hoja").hidden === false, "INVESTIGACIÓN propia reutiliza su modal");
$("btn-cerrar-hoja").click();

const salaOtroHumano = {
  ...sala,
  jugadores: sala.jugadores.map((j) => j.personaje_id === "bruno" ? { ...j, tipo: "humano" } : j),
};
vm.runInContext(`ultimaSala = ${JSON.stringify(salaOtroHumano)};`, sandbox);
sandbox.verPersonaje("bruno");
ok(
  !$("modal-contextual-detalle").textContent.includes("CARTAS") &&
    !$("modal-contextual-detalle").textContent.includes("INVESTIGACIÓN"),
  "otro humano no muestra herramientas privadas"
);
vm.runInContext(`ultimaSala = ${JSON.stringify(sala)};`, sandbox);
sandbox.verPersonaje("bruno");
ok(
  !$("modal-contextual-detalle").textContent.includes("CARTAS") &&
    !$("modal-contextual-detalle").textContent.includes("INVESTIGACIÓN"),
  "PNJ no muestra herramientas privadas"
);

// 14-15. Destino legal mantiene MOVER AQUÍ y consultar no mueve.
enviados.length = 0;
vm.runInContext(`ultimaSala = ${JSON.stringify({ ...sala, movimiento: { ...sala.movimiento, destinos: [{ id: "plaza-constitucion", nombre: "Plaza" }] } })};`, sandbox);
sandbox.pintarSala({ ...sala, movimiento: { ...sala.movimiento, destinos: [{ id: "plaza-constitucion", nombre: "Plaza" }] } });
sandbox.verUbicacion("plaza-constitucion");
const btnMover = $("btn-mover-ubicacion-canvas");
ok(!btnMover.hidden, "destino legal ofrece MOVER AQUÍ");
btnMover.click();
ok(enviados.length === 1 && enviados[0].accion === "mover" && enviados[0].destino_id === "plaza-constitucion", "MOVER AQUÍ envía el destino legal");
enviados.length = 0;
sandbox.verUbicacion("parador");
ok(enviados.length === 0, "consultar no mueve");

// 16-19. FORMULAR SOSPECHA solo con permiso del servidor.
const conPermiso = { ...sala, movimiento: { ...sala.movimiento, puede_sospechar: true } };
vm.runInContext(`ultimaSala = ${JSON.stringify(conPermiso)};`, sandbox);
sandbox.pintarSala(conPermiso);
sandbox.verUbicacion("parador");
ok($("modal-contextual-detalle").textContent.includes("FORMULAR SOSPECHA"), "entrar permite sospechar");
const sinPermiso = { ...sala, movimiento: { ...sala.movimiento } };
vm.runInContext(`ultimaSala = ${JSON.stringify(sinPermiso)};`, sandbox);
sandbox.pintarSala(sinPermiso);
sandbox.verUbicacion("parador");
ok(!$("modal-contextual-detalle").textContent.includes("FORMULAR SOSPECHA"), "empezar en ubicación no ofrece sospecha");

// 20. Sospecha en tablero: selector visual privado de sospechoso y objeto.
vm.runInContext(`ultimaSala = ${JSON.stringify(conPermiso)};`, sandbox);
sandbox.pintarSala(conPermiso);
sandbox.verUbicacion("parador");
$("modal-contextual-detalle").children.find((h) => h.tag === "button" && h.textContent === "FORMULAR SOSPECHA").click();
const gruposCartas = $("modal-contextual-detalle").children
  .filter((h) => h.className === "selector-cartas-sospecha");
ok(
  $("modal-ubicacion").hidden === false &&
    $("modal-contextual-titulo").textContent === "SOSPECHA EN PARADOR" &&
    gruposCartas.length === 2 &&
    !$("modal-contextual-detalle").children.some((h) => h.tag === "select"),
  "sospecha abre selector visual sin los selects antiguos"
);
ok(gruposCartas[0].children.length === 6, "selector visual muestra los 6 personajes");
ok(gruposCartas[1].children.length === 6, "selector visual muestra los 6 objetos");
ok(gruposCartas.every((grupo) => grupo.children.every((carta) =>
  !carta.classList.contains("carta-visual-compacta"))),
"FORMULAR SOSPECHA conserva cartas de tamaño normal");
ok(gruposCartas.every((grupo) => grupo.children.every((carta) =>
  carta.children.some((hijo) => hijo.className === "carta-selector-nombre"))),
"FORMULAR SOSPECHA conserva los nombres visibles de 8B.9");
const veraVisual = gruposCartas[0].children.find((b) => b.dataset.cartaId === "vera");
const brunoVisual = gruposCartas[0].children.find((b) => b.dataset.cartaId === "bruno");
const baulVisual = gruposCartas[1].children.find((b) => b.dataset.cartaId === "baul-imperial");
const libroVisual = gruposCartas[1].children.find((b) => b.dataset.cartaId === "libro-hueco");
ok(veraVisual.textContent.includes("TU CARTA") && baulVisual.textContent.includes("TU CARTA"),
  "TU CARTA procede de mis_cartas privadas");
ok(brunoVisual.textContent.includes("VISTA") && libroVisual.textContent.includes("VISTA"),
  "VISTA procede del estado privado de investigación");
ok(veraVisual.children[0].src.includes("vera-nombre.png") && baulVisual.children[0].src.includes("objetos/baul-imperial.jpeg"),
  "personajes y objetos reutilizan el manifiesto de recursos");
ok(
  $("vista-contextual").textContent ===
    "Has llegado. Pulsa la ubicación para ver tus opciones.",
  "sospecha no sustituye el panel derecho"
);
ok(
  !$("modal-contextual-detalle").textContent.includes("CARTAS") &&
    !$("modal-contextual-detalle").textContent.includes("INVESTIGACIÓN") &&
    !$("modal-contextual-detalle").textContent.includes("RESOLVER"),
  "popup de sospecha sin herramientas globales"
);
$("modal-contextual-detalle").children
  .find((h) => h.tag === "button" && h.textContent === "VOLVER").click();
ok(
  $("modal-contextual-titulo").textContent === "Parador" &&
    $("imagen-ubicacion").src === "/static/img/lugares/parador.jpeg",
  "VOLVER recupera el popup de la misma ubicación"
);
ok(
  $("modal-contextual-detalle").textContent.includes("FORMULAR SOSPECHA"),
  "VOLVER no consume el derecho a sospechar"
);
$("modal-contextual-detalle").children
  .find((h) => h.tag === "button" && h.textContent === "FORMULAR SOSPECHA").click();
const gruposConfirmacion = $("modal-contextual-detalle").children
  .filter((h) => h.className === "selector-cartas-sospecha");
const brunoConfirmacion = gruposConfirmacion[0].children.find((b) => b.dataset.cartaId === "bruno");
const veraConfirmacion = gruposConfirmacion[0].children.find((b) => b.dataset.cartaId === "vera");
const baulConfirmacion = gruposConfirmacion[1].children.find((b) => b.dataset.cartaId === "baul-imperial");
// HTMLCollection real no implementa forEach. El harness anterior usaba arrays
// y ocultaba la excepción que interrumpía el listener en el navegador.
gruposConfirmacion[0].children.forEach = undefined;
gruposConfirmacion[1].children.forEach = undefined;
brunoConfirmacion.click();
veraConfirmacion.click();
baulConfirmacion.click();
ok(brunoConfirmacion.getAttribute("aria-pressed") === "false" && veraConfirmacion.getAttribute("aria-pressed") === "true",
  "click real persiste una sola selección de personaje con HTMLCollection");
ok(veraConfirmacion.classList.contains("seleccionada") && baulConfirmacion.classList.contains("seleccionada"),
  "personaje y objeto conservan simultáneamente la clase seleccionada");
ok(brunoConfirmacion.textContent.includes("VISTA") && !brunoConfirmacion.classList.contains("seleccionada"),
  "VISTA permanece visible al seleccionar y deseleccionar la carta");
ok(veraConfirmacion.textContent.includes("TU CARTA") && veraConfirmacion.classList.contains("seleccionada"),
  "TU CARTA permanece visible junto a SELECCIONADA");
ok(!$("modal-contextual-detalle").children.find((h) => h.textContent === "CONFIRMAR SOSPECHA").disabled,
  "confirmar se activa al elegir personaje y objeto, incluso conocidos");
enviados.length = 0;
$("modal-contextual-detalle").children
  .find((h) => h.tag === "button" && h.textContent === "CONFIRMAR SOSPECHA").click();
ok(
  enviados.length === 1 && enviados[0].accion === "formular_sospecha" &&
    enviados[0].sospechoso_id === "vera" && enviados[0].lugar_id === "parador" &&
    enviados[0].objeto_id === "baul-imperial",
  "sospecha usa la posición de entrada como lugar"
);

// 21. Rápido mantiene modal con sus tres componentes.
const salaRapida = {
  ...salaBase("rapido"),
  jugada: { estado: "esperando_sospecha" },
  movimiento: {},
};
vm.runInContext(`ultimaSala = ${JSON.stringify(salaRapida)};`, sandbox);
sandbox.pintarSala(salaRapida);
ok($("btn-sospecha").hidden === false, "rápido conserva FORMULAR SOSPECHA clásico");
$("btn-sospecha").click();
ok($("modal-sospecha").hidden === false, "rápido abre el modal de sospecha");
ok(
  ["sospecha-sospechoso", "sospecha-lugar", "sospecha-objeto"].every(
    (id) => $(id).children.length > 0
  ),
  "rápido mantiene sus tres componentes"
);
const salaTableroSospecha = { ...sala, jugada: { estado: "esperando_sospecha" } };
vm.runInContext(`ultimaSala = ${JSON.stringify(salaTableroSospecha)};`, sandbox);
sandbox.pintarSala(salaTableroSospecha);
ok($("btn-sospecha").hidden === true, "tablero no duplica el botón clásico");

// 22-24. Herramientas y resolver siguen cableados.
$("btn-ver-hoja").click();
ok($("modal-hoja").hidden === false, "HOJA funciona");
$("btn-ver-cartas").click();
ok($("modal-cartas").hidden === false, "MIS CARTAS funciona");
ok($("barra-herramientas") && $("btn-ver-cartas").hidden, "panel oculta CARTAS y conserva herramientas");
sandbox.pintarSala({ ...sala, jugada: { estado: "esperando_sospecha" } });
ok($("btn-resolver").hidden === false, "resolver visible cuando el servidor lo permite");

// CERRAR limpia el modal y mantiene el panel derecho en su vista general.
sandbox.verUbicacion("parador");
$("btn-cerrar-ubicacion").click();
ok(
  $("modal-ubicacion").hidden && $("imagen-ubicacion").src === "" &&
    $("modal-contextual-titulo").textContent === "" &&
    $("modal-contextual-detalle").textContent === "",
  "CERRAR limpia el panel intermedio"
);
ok($("vista-contextual").textContent === "Tira el dado.", "CERRAR deja el panel derecho en estado base");

if (fallos) process.exit(1);
console.log("INTERFAZ PANEL OK");

// 6-10. Canvas: peón activo, peones clicables, prioridad y reduced-motion.
class CtxCanvas {
  constructor() { this.ops = []; }
  setTransform() {} clearRect() {}
  fillRect(...a) { this.ops.push(["fillRect", this.fillStyle, ...a]); }
  beginPath() {} moveTo() {} lineTo() {} closePath() {} clip() {}
  stroke() {} fill() { this.ops.push(["fill", this.fillStyle]); }
  arc() {} quadraticCurveTo() {} setLineDash() {}
  save() {} restore() {}
  drawImage(img, ...a) { this.ops.push(["drawImage", img && img._src, ...a]); }
  getImageData() { return { data: new Uint8ClampedArray(64 * 80 * 4) }; }
  putImageData() {}
}
class CanvasPrueba {
  constructor(lado = 600) {
    this.ctx = new CtxCanvas(); this.clientWidth = lado; this.style = {};
    this.oyentes = {};
  }
  getContext() { return this.ctx; }
  getBoundingClientRect() { return { left: 0, top: 0, width: 600, height: 600 }; }
  addEventListener(t, fn) { (this.oyentes[t] = this.oyentes[t] || []).push(fn); }
  pulsar(x, y) { (this.oyentes.pointerup || []).forEach((fn) => fn({ clientX: x * 6, clientY: y * 6 })); }
}
class ImagenLista {
  set src(url) { this._src = url; this.naturalWidth = 500; this.naturalHeight = 500; if (this.onload) this.onload(); }
}

function montarCanvas(reducido) {
  const raf = [];
  const ventana = {
    devicePixelRatio: 1, Image: ImagenLista, addEventListener() {},
    matchMedia: () => ({ matches: reducido }),
    requestAnimationFrame: (fn) => { raf.push(fn); return raf.length; },
    cancelAnimationFrame: (id) => { raf[id - 1] = null; },
  };
  ventana.window = ventana;
  const caja = {
    window: ventana, console,
    document: { createElement(t) { return t === "canvas" ? new CanvasPrueba(64) : {}; } },
    Math, Map, Set,
  };
  vm.createContext(caja);
  vm.runInContext(
    fs.readFileSync(path.join(__dirname, "..", "app", "static", "js", "tablero_canvas.js"), "utf8"),
    caja
  );
  const descriptor = {
    nodos: [
      { id: "parador", tipo: "ubicacion", nombre: "Parador", x: 50, y: 50, diametro: 14, imagen_tablero: "/t/parador.png" },
      { id: "plaza-constitucion", tipo: "ubicacion", nombre: "Plaza", x: 20, y: 20, diametro: 32, imagen_tablero: "/t/plaza.png" },
    ],
    caminos: [], pasadizos: [], peon: "/p/peon.svg",
    colores_personajes: { vera: "#111111", bruno: "#222222" },
  };
  const estado = {
    turno_alias: "Yo",
    jugadores: [
      { alias: "Yo", personaje_id: "vera", activo: true, posicion: { id: "parador", nombre: "Parador" } },
      { alias: "Rival", personaje_id: "bruno", activo: true, posicion: { id: "parador", nombre: "Parador" } },
    ],
    movimiento: { destinos: [] },
  };
  const canvas = new CanvasPrueba();
  const consultados = [];
  const personajes = [];
  const renderer = new caja.window.TableroCanvas(canvas, descriptor, {
    consultar: (n) => consultados.push(n.id),
    mover: () => {},
    personaje: (info) => personajes.push(info.personaje_id),
  });
  renderer.actualizar(estado);
  return { renderer, canvas, raf, consultados, personajes };
}

const montaje = montarCanvas(false);
const rep = montaje.renderer.metricas.representacionesPeones;
const yo = rep.find((p) => p.personaje_id === "vera");
const rival = rep.find((p) => p.personaje_id === "bruno");
ok(yo && yo.esTurno && yo.encima, "peón activo marcado y por encima");
ok(montaje.renderer.metricas.escalaTurno === 1.2, "peón activo escala 1.2");
ok(montaje.renderer.metricas.peonActivo === "Yo", "métricas identifican el turno");
ok(montaje.renderer.metricas.animacion === "pulso", "pulso sutil con movimiento permitido");
ok(montaje.raf.filter(Boolean).length === 1, "una sola animación programada");
montaje.raf[0](0);
montaje.raf.filter(Boolean)[0](942);
const t0 = montaje.renderer.metricas.representacionesPeones.find((p) => p.personaje_id === "vera");
ok(t0, "repintado por animación sin duplicar peones");
ok(rival && !rival.esTurno, "el otro peón conserva su tamaño");

// 9-10. Peón sobre ubicación: el peón gana; fuera del peón, la ubicación.
const areaYo = montaje.renderer.areasPeones.find((a) => a.personaje_id === "vera");
montaje.canvas.pulsar(areaYo.x, areaYo.y);
ok(montaje.personajes.length === 1 && montaje.personajes[0] === "vera", "clic en peón abre el personaje");
ok(montaje.consultados.length === 0, "clic en peón no abre la ubicación");
montaje.canvas.pulsar(50, 50 + 5.5);
ok(montaje.consultados.length === 1 && montaje.consultados[0] === "parador", "fuera del peón sigue abriendo ubicación");

// 7. Reduced-motion: halo/tamaño estáticos, sin animación.
const quieto = montarCanvas(true);
ok(quieto.renderer.metricas.animacion === "estatica", "reduced-motion desactiva el pulso");
ok(quieto.raf.filter(Boolean).length === 0, "reduced-motion no programa animación");
ok(
  quieto.renderer.metricas.representacionesPeones.some((p) => p.personaje_id === "vera" && p.esTurno),
  "reduced-motion conserva la marca estática de turno"
);

if (fallos) process.exit(1);
console.log("INTERFAZ CANVAS OK");
