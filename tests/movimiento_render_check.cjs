/* Harness de la frontera estado privado WS -> render de movimiento.
   Uso: node tests/movimiento_render_check.cjs */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

let fallos = 0;
function ok(condicion, nombre) {
  console.log(`${condicion ? "PASS" : "FAIL"} ${nombre}`);
  if (!condicion) fallos += 1;
}

function makeElemento(tag) {
  return {
    tag,
    children: [],
    hidden: true,
    disabled: false,
    style: {},
    className: "",
    classList: { add() {} },
    value: "",
    options: [],
    selectedIndex: -1,
    parentElement: { hidden: false },
    _texto: "",
    _oyentes: {},
    set textContent(valor) {
      this.children = [];
      this._texto = String(valor);
    },
    get textContent() {
      return this._texto + this.children.map((hijo) => hijo.textContent).join("");
    },
    set innerHTML(valor) {
      this.children = [];
      this._texto = "";
      this._html = String(valor);
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
    click() {
      (this._oyentes.click || []).forEach((fn) => fn());
    },
    setAttribute() {},
  };
}

const registro = {};
const documentStub = {
  getElementById(id) {
    if (!registro[id]) registro[id] = makeElemento("div");
    return registro[id];
  },
  createElement: makeElemento,
};
registro.codigo = makeElemento("p");
registro.codigo.textContent = "JARA-TEST";

const enviados = [];
class WebSocketFalso {
  send(mensaje) { enviados.push(JSON.parse(mensaje)); }
}

const sandbox = {
  console,
  document: documentStub,
  window: { location: { protocol: "http:", host: "localhost:8000" } },
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
const base = {
  modo: "tablero",
  estado: "iniciada",
  posicion: { id: "parador", nombre: "Parador", tipo: "ubicacion" },
  orden: [],
  pnj_pensando_alias: null,
};

sandbox.pintarMovimiento({
  ...base,
  turno_tipo: "humano",
  movimiento: {
    fase: "esperando_movimiento",
    puede_tirar: true,
    pasadizo: {
      id: "nuestra-senora-torre",
      nombre: "Ntra. Sra. de la Torre",
      tipo: "ubicacion",
    },
    tirada: null,
  },
  pnj_movimiento_pendiente: false,
});
ok($("movimiento").hidden === false, "el panel de movimiento aparece en modo tablero");
ok($("btn-tirar").hidden === false, "puede_tirar=true muestra TIRAR DADO");
ok(
  !fs.readFileSync(path.join(__dirname, "..", "app", "templates", "sala.html"), "utf8")
    .includes('id="btn-sospecha-aqui"'),
  "la interfaz no ofrece sospecha gratuita al inicio"
);
ok($("btn-pasadizo").hidden === false, "el pasadizo sigue disponible como alternativa");

sandbox.pintarMovimiento({
  ...base,
  movimiento: {
    fase: "esperando_destino",
    puede_tirar: false,
    tirada: 2,
    destinos: [
      { id: "camino-1", nombre: "Camino 1", tipo: "casilla" },
      { id: "camino-2", nombre: "Camino 2", tipo: "casilla" },
    ],
  },
});
ok($("destinos-movimiento").children.length === 2, "tras tirar se renderizan los destinos server-side");

vm.runInContext(`ultimaSala = {
  modo: "tablero",
  estado: "iniciada",
  turno_alias: "Yo",
  jugadores: [],
  posicion: { id: "parador", nombre: "Parador" },
  movimiento: { puede_sospechar: true },
  investigacion: [
    { id: "vera", nombre: "Vera", categoria: "sospechoso" },
    { id: "parador", nombre: "Parador", categoria: "lugar" },
    { id: "libro-hueco", nombre: "Libro hueco", categoria: "objeto" }
  ]
}`, sandbox);
sandbox.verSospecha();
const selPanel = [];
(function recoge(nodo) {
  if (nodo.tag === "select") selPanel.push(nodo);
  nodo.children.forEach(recoge);
})($("vista-contextual"));
ok(selPanel.length === 2, "en tablero la sospecha del panel no vuelve a pedir ubicación");
selPanel[0].value = "vera";
selPanel[1].value = "libro-hueco";
enviados.length = 0;
$("vista-contextual").children
  .find((h) => h.tag === "button" && h.textContent === "CONFIRMAR SOSPECHA").click();
ok(
  enviados.length === 1 && enviados[0].accion === "formular_sospecha" &&
    enviados[0].lugar_id === "parador",
  "confirmar usa la posición de entrada como lugar"
);

sandbox.pintarJugada({
  ...base,
  activo_investigacion: true,
  es_mi_turno: false,
  jugada: {
    estado: "esperando_movimiento",
    investigador_alias: "Bruno",
    tipo: "movimiento",
    movimiento_pnj: {
      accion: "movimiento",
      tirada: 4,
      origen: "Parador",
      destino: "Plaza de la Constitución",
    },
  },
});
ok(
  $("jugada").textContent.includes("ha tirado un 4") &&
    $("jugada").textContent.includes("Plaza de la Constitución"),
  "el estado público explica tirada y movimiento PNJ"
);

sandbox.pintarMovimiento({
  ...base,
  turno_alias: "Lucía",
  turno_tipo: "pnj",
  movimiento: {
    fase: "esperando_movimiento",
    puede_tirar: false,
    tirada: null,
  },
  pnj_movimiento_pendiente: true,
});
sandbox.pintarTurno({
  ...base,
  turno_alias: "Lucía",
  turno_tipo: "pnj",
  es_mi_turno: false,
});
ok($("btn-tirar").hidden === true, "un turno PNJ no ofrece el dado al humano");
ok(
  !$("destinos-movimiento").textContent.includes("pendiente de Fase 6C"),
  "ya no aparece el bloqueo provisional de Fase 6C"
);
ok(
  $("turno").textContent === "TURNO DE LUCÍA · PNJ",
  "la cabecera identifica explícitamente el turno PNJ"
);

if (fallos) process.exit(1);
console.log("MOVIMIENTO RENDER OK");
