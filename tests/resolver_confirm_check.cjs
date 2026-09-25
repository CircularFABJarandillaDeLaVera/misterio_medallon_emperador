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

function makeElemento(tag) {
  const el = {
    tag,
    children: [],
    className: "",
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

function fijarSelect(id, valor, nombre) {
  const sel = $(id);
  sel.value = valor;
  sel.options = [{ textContent: nombre }];
  sel.selectedIndex = 0;
}

// 1. Abrir selección y pasar a confirmación con los nombres visibles.
$("modal-resolver").hidden = true;
$("modal-confirmar-resolver").hidden = true;
fijarSelect("resolver-sospechoso", "vera", "Vera");
fijarSelect("resolver-lugar", "parador", "Parador");
fijarSelect("resolver-objeto", "baul-imperial", "Baúl Imperial");
$("btn-resolver").click();
ok($("modal-resolver").hidden === false, "RESOLVER abre el modal de selección");
$("btn-confirmar-resolver").click();
ok($("modal-resolver").hidden === true, "CONTINUAR cierra la selección");
ok(
  $("modal-confirmar-resolver").hidden === false,
  "CONTINUAR abre la confirmación integrada"
);
ok(
  $("conf-resolver-sospechoso").textContent.includes("Vera") &&
    $("conf-resolver-lugar").textContent.includes("Parador") &&
    $("conf-resolver-objeto").textContent.includes("Baúl"),
  "la confirmación muestra sospechoso/lugar/objeto"
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
