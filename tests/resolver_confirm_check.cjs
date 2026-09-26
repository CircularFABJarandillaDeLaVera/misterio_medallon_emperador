/* Harness: flujo de confirmación de RESOLVER EL MISTERIO sin confirm()
   nativo, anti doble envío y aviso de timeout de refutación.
   Uso: node tests/resolver_confirm_check.cjs */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

let fallos = 0;
function ok(cond, nombre) {
  if (cond) {
    console.log(`PASS ${nombre}`);
  } else {
    fallos += 1;
    console.log(`FAIL ${nombre}`);
  }
}

const fuente = fs.readFileSync(
  path.join(__dirname, "..", "app", "static", "js", "sala.js"),
  "utf8"
);
ok(!fuente.includes("window.confirm"), "sin window.confirm en sala.js");
ok(!/[^a-zA-Z]confirm\s*\(/.test(fuente), "sin llamadas confirm(...) en sala.js");
ok(!/[^a-zA-Z]alert\s*\(/.test(fuente), "sin alert(...) en sala.js");
ok(!/[^a-zA-Z]prompt\s*\(/.test(fuente), "sin prompt(...) en sala.js");
ok(fuente.includes("btn-enviar-resolver"), "existe botón de envío único");

function claseLista() {
  const clases = new Set();
  return {
    add(...cs) { cs.forEach((c) => clases.add(c)); },
    remove(...cs) { cs.forEach((c) => clases.delete(c)); },
    toggle(c, f) {
      if (f === undefined) { if (clases.has(c)) clases.delete(c); else clases.add(c); }
      else if (f) clases.add(c); else clases.delete(c);
    },
    contains(c) { return clases.has(c); },
  };
}

function makeElemento(tag) {
  const el = {
    tag,
    children: [],
    className: "",
    classList: claseLista(),
    dataset: {},
    hidden: true,
    disabled: false,
    title: "",
    type: "",
    value: "",
    options: [],
    selectedIndex: -1,
    style: {},
    _texto: "",
    _attrs: {},
    _oyentes: {},
    set textContent(v) {
      this.children = [];
      this._texto = String(v);
    },
    get textContent() {
      return this._texto + this.children.map((c) => c.textContent).join("");
    },
    set innerHTML(v) {
      this.children = [];
      this._texto = "";
      this._html = String(v);
    },
    get innerHTML() {
      return this._html || "";
    },
    appendChild(hijo) {
      this.children.push(hijo);
      return hijo;
    },
    addEventListener(evento, fn) {
      (this._oyentes[evento] = this._oyentes[evento] || []).push(fn);
    },
    setAttribute(k, v) {
      this._attrs[k] = String(v);
    },
    getAttribute(k) {
      return this._attrs[k];
    },
    click() {
      (this._oyentes.click || []).forEach((fn) => fn());
    },
  };
  return el;
}

const registro = {};
const documentStub = {
  getElementById(id) {
    if (!registro[id]) {
      registro[id] = makeElemento("div");
    }
    return registro[id];
  },
  createElement(tag) {
    return makeElemento(tag);
  },
};
registro.codigo = makeElemento("p");
registro.codigo.textContent = "JARA-TEST";

const enviados = [];
class WebSocketFalso {
  constructor() {}
  send(mensaje) {
    enviados.push(JSON.parse(mensaje));
  }
}

const sandbox = {
  console,
  document: documentStub,
  window: { location: { protocol: "http:", host: "localhost:8000" } },
  sessionStorage: { getItem: () => "jug-test", setItem: () => {} },
  fetch: () => ({ then: () => ({ then: () => {} }) }),
  WebSocket: WebSocketFalso,
};
vm.createContext(sandbox);
vm.runInContext(fuente, sandbox, { filename: "sala.js" });

const $ = (id) => documentStub.getElementById(id);

// 0. Resolver ya no usa selects; el modo rápido conserva los suyos.
const htmlSala = fs.readFileSync(
  path.join(__dirname, "..", "app", "templates", "sala.html"),
  "utf8"
);
ok(
  !htmlSala.includes('id="resolver-sospechoso"') &&
    !htmlSala.includes('id="resolver-lugar"') &&
    !htmlSala.includes('id="resolver-objeto"'),
  "Resolver sin selects visibles"
);
ok(
  htmlSala.includes('id="sospecha-sospechoso"') &&
    htmlSala.includes('id="sospecha-lugar"') &&
    htmlSala.includes('id="sospecha-objeto"'),
  "modo rápido conserva sus selects"
);
ok(
  htmlSala.includes('id="resolver-grupo-sospechoso"') &&
    htmlSala.includes('id="resolver-grupo-lugar"') &&
    htmlSala.includes('id="resolver-grupo-objeto"'),
  "Resolver ofrece 3 grupos visuales"
);

// 1. Abrir selección y pasar a confirmación con los nombres visibles.
vm.runInContext(`ultimaSala = {
  investigacion: [
    { id: "vera", nombre: "Vera", categoria: "sospechoso", estado: "sin_informacion" },
    { id: "bruno", nombre: "Bruno", categoria: "sospechoso", estado: "sin_informacion" },
    { id: "parador", nombre: "Parador", categoria: "lugar", estado: "sin_informacion" },
    { id: "picota", nombre: "Picota", categoria: "lugar", estado: "sin_informacion" },
    { id: "baul-imperial", nombre: "Baúl Imperial", categoria: "objeto", estado: "sin_informacion" },
    { id: "libro-hueco", nombre: "Libro Hueco", categoria: "objeto", estado: "sin_informacion" }
  ],
  mis_cartas: [{ id: "vera", nombre: "Vera", categoria: "sospechoso" }]
};`, sandbox);
function pulsarCarta(grupoId, indice = 0) {
  const botones = $(grupoId).children.filter((h) => h.tag === "button");
  botones[indice].click();
  return botones;
}
$("modal-resolver").hidden = true;
$("modal-confirmar-resolver").hidden = true;
$("btn-resolver").click();
ok($("modal-resolver").hidden === false, "RESOLVER abre el modal de selección");
ok($("btn-confirmar-resolver").disabled === true, "CONTINUAR exige las tres selecciones");
const cartasS = pulsarCarta("resolver-grupo-sospechoso", 0);
ok(cartasS.length === 2, "el grupo muestra los sospechosos disponibles");
pulsarCarta("resolver-grupo-lugar", 0);
ok($("btn-confirmar-resolver").disabled === true, "con dos selecciones sigue bloqueado");
pulsarCarta("resolver-grupo-objeto", 0);
ok($("btn-confirmar-resolver").disabled === false, "con tres selecciones se habilita");
// Exclusividad: una nueva selección sustituye a la anterior.
pulsarCarta("resolver-grupo-sospechoso", 1);
ok(
  cartasS.filter((b) => b.classList.contains("seleccionada")).length === 1,
  "una sola carta seleccionada por categoría"
);
pulsarCarta("resolver-grupo-sospechoso", 0);
ok(
  $("resolver-grupo-sospechoso").textContent.includes("TU CARTA"),
  "la carta propia se identifica y sigue seleccionable"
);
$("btn-confirmar-resolver").click();
ok(enviados.length === 0, "CONTINUAR no envía WebSocket");
ok($("modal-resolver").hidden === true, "CONTINUAR cierra la selección");
ok(
  $("modal-confirmar-resolver").hidden === false,
  "CONTINUAR abre la confirmación integrada"
);
const figuras = $("conf-resolver-cartas").children;
ok(figuras.length === 3, "la confirmación muestra exactamente 3 cartas");
ok(
  figuras.every((f) => f.tag === "div"),
  "las cartas de confirmación no son seleccionables"
);
ok(
  figuras[0].getAttribute("aria-label") === "Vera" &&
    figuras[1].getAttribute("aria-label") === "Parador" &&
    figuras[2].getAttribute("aria-label") === "Baúl Imperial",
  "las cartas corresponden a los tres IDs en orden sospechoso/lugar/escondite"
);
ok(
  !$("conf-resolver-cartas").textContent.includes("TU CARTA") &&
    !$("conf-resolver-cartas").textContent.includes("VISTA") &&
    !$("conf-resolver-cartas").textContent.includes("DESCARTADA"),
  "la confirmación no muestra insignias de conocimiento"
);

// 2. Un solo envío aunque haya doble clic.
enviados.length = 0;
$("btn-enviar-resolver").click();
$("btn-enviar-resolver").click();
const acusaciones = enviados.filter((m) => m.accion === "resolver_misterio");
ok(acusaciones.length === 1, "doble clic envía exactamente una acusación");
ok(
  acusaciones[0].sospechoso_id === "vera" &&
    acusaciones[0].lugar_id === "parador" &&
    acusaciones[0].objeto_id === "baul-imperial",
  "la acusación lleva los valores elegidos"
);
ok(
  $("modal-confirmar-resolver").hidden === true,
  "enviar cierra la confirmación"
);

// 3. CANCELAR no envía nada y conserva la selección.
enviados.length = 0;
$("btn-resolver").click();
pulsarCarta("resolver-grupo-sospechoso", 0);
pulsarCarta("resolver-grupo-lugar", 0);
pulsarCarta("resolver-grupo-objeto", 0);
$("btn-confirmar-resolver").click();
$("btn-cancelar-confirmar-resolver").click();
ok(
  enviados.filter((m) => m.accion === "resolver_misterio").length === 0,
  "CANCELAR no modifica ningún estado ni envía"
);
ok(
  $("modal-confirmar-resolver").hidden === true &&
    $("modal-resolver").hidden === false,
  "CANCELAR vuelve a la selección conservando valores"
);

// 4. Reconfirmar rearma el envío único.
enviados.length = 0;
$("btn-confirmar-resolver").click();
$("btn-enviar-resolver").click();
ok(
  enviados.filter((m) => m.accion === "resolver_misterio").length === 1,
  "reconfirmar permite un nuevo envío único"
);

// 5. Aviso de timeout solo con plazo server-side.
const pintarJugada = sandbox.pintarJugada;
ok(typeof pintarJugada === "function", "pintarJugada existe en sala.js");
function salaBase(jugada) {
  return {
    jugada,
    jugadores: [],
    orden: [],
    estado: "iniciada",
    es_mi_turno: false,
    activo_investigacion: false,
    turno_alias: "X",
  };
}
pintarJugada(
  salaBase({
    estado: "esperando_eleccion_refutador",
    opciones_refutacion: [{ id: "vera", nombre: "Vera" }],
    timeout_refutacion_seg: 3,
  })
);
ok(
  $("aviso-timeout-refutacion").hidden === false &&
    $("aviso-timeout-refutacion").textContent.includes("servidor"),
  "con plazo se avisa del timeout server-side"
);
pintarJugada(
  salaBase({
    estado: "esperando_eleccion_refutador",
    opciones_refutacion: [{ id: "vera", nombre: "Vera" }],
  })
);
ok(
  $("aviso-timeout-refutacion").hidden === true,
  "sin plazo no hay aviso de timeout"
);

// 6. Revelación visual: solo aparece cuando el privado incluye carta_mostrada.
vm.runInContext(`RECURSOS_VISUALES = {
  vera: { principal: "/static/img/personajes/vera.png", nombre: "/static/img/personajes/vera-nombre.png" },
  parador: { principal: "/static/img/lugares/parador.jpeg" },
  "cantaro-barro": { principal: "/static/img/objetos/cantaro-barro.jpeg" }
};`, sandbox);

function jugadaRefutada(carta, refutador = "Bruno") {
  return {
    estado: "esperando_movimiento",
    resultado: "refutada",
    investigador_alias: "Yo",
    refutador_alias: refutador,
    sospecha: {
      sospechoso_id: { id: "vera", nombre: "Vera" },
      lugar_id: { id: "parador", nombre: "Parador" },
      objeto_id: { id: "cantaro-barro", nombre: "Cántaro de barro" },
    },
    carta_mostrada: carta,
  };
}

const revelacionPersonaje = jugadaRefutada({
  id: "vera", nombre: "Vera, la cronista", categoria: "sospechoso",
});
pintarJugada(salaBase(revelacionPersonaje));
ok(
  $("modal-revelacion-refutacion").hidden === false &&
    $("revelacion-refutador").textContent === "BRUNO REFUTA TU SOSPECHA",
  "investigador ve quién refuta"
);
ok(
  $("revelacion-carta-imagen").src === "/static/img/personajes/vera-nombre.png" &&
    $("revelacion-carta-nombre").textContent === "Vera, la cronista",
  "personaje revelado usa la variante con nombre"
);
const enviosAntesContinuar = enviados.length;
$("btn-continuar-revelacion").click();
ok(
  $("modal-revelacion-refutacion").hidden && enviados.length === enviosAntesContinuar,
  "CONTINUAR solo cierra la presentación"
);
pintarJugada(salaBase(revelacionPersonaje));
ok($("modal-revelacion-refutacion").hidden, "el mismo estado no reabre la revelación descartada");

// Un estado sin carta privada limpia el ciclo y no revela nada a terceros.
pintarJugada(salaBase({
  estado: "esperando_movimiento", resultado: "refutada",
  investigador_alias: "Otra", refutador_alias: "Bruno",
}));
ok($("modal-revelacion-refutacion").hidden, "otro cliente no ve la carta mostrada");

const revelacionLugar = jugadaRefutada({
  id: "parador", nombre: "Parador", categoria: "lugar",
});
pintarJugada(salaBase(revelacionLugar));
ok(
  $("revelacion-carta-imagen").src === "/static/img/lugares/parador.jpeg",
  "lugar revelado usa su JPEG original"
);
$("btn-continuar-revelacion").click();
pintarJugada(salaBase({ estado: "esperando_movimiento", resultado: "sin_refutacion" }));
ok($("modal-revelacion-refutacion").hidden, "sospecha sin refutación no abre revelación");

const revelacionPnj = jugadaRefutada({
  id: "cantaro-barro", nombre: "Cántaro de barro", categoria: "objeto",
}, "Mateo PNJ");
pintarJugada(salaBase(revelacionPnj));
ok(
  $("revelacion-refutador").textContent === "MATEO PNJ REFUTA TU SOSPECHA" &&
    $("revelacion-carta-imagen").src === "/static/img/objetos/cantaro-barro.jpeg",
  "PNJ produce la misma revelación privada con la imagen del objeto"
);

if (fallos > 0) {
  console.log(`${fallos} FALLO(S)`);
  process.exit(1);
}
console.log("RESOLVER CONFIRM OK");
