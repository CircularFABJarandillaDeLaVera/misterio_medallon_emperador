/* Harness del flujo real de la portada 8B.15: NUEVA PARTIDA abre popup,
   CREAR PARTIDA hace fetch POST /api/partidas con alias + modo.
   Uso: node tests/modo_seleccion_check.cjs */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

let fallos = 0;
function ok(condicion, nombre) {
  console.log(`${condicion ? "PASS" : "FAIL"} ${nombre}`);
  if (!condicion) fallos += 1;
}

function elemento(id) {
  return {
    id,
    value: "",
    textContent: "",
    hidden:
      id === "modal-nueva" || id === "modal-unirse" || id === "modal-cargar" ||
      id === "modal-preparacion-movil" || id === "envoltorio-modo",
    disabled: false,
    inert: false,
    classList: { add() {}, remove() {} },
    _oyentes: {},
    addEventListener(evento, fn) {
      this._oyentes[evento] = fn;
    },
    focus() {},
    click() {
      if (this._oyentes.click) return this._oyentes.click();
    },
  };
}

const elementos = {};
const escenaPortada = elemento("portada-escena");
const documentStub = {
  activeElement: null,
  _global: {},
  body: { classList: { add() {}, remove() {} } },
  documentElement: { classList: { add() {}, remove() {}, contains() { return false; } } },
  getElementById(id) {
    if (!elementos[id]) elementos[id] = elemento(id);
    return elementos[id];
  },
  addEventListener(evento, fn) {
    this._global[evento] = fn;
  },
  querySelector(selector) {
    return selector === ".portada-escena" ? escenaPortada : null;
  },
};

const peticiones = [];
async function fetchStub(url, opciones) {
  peticiones.push({ url, opciones });
  return {
    ok: true,
    async json() {
      return { codigo: "JARA-TEST", jugador_id: "jug-test", alias: "Host" };
    },
  };
}

const sandbox = {
  console,
  document: documentStub,
  fetch: fetchStub,
  navigator: { maxTouchPoints: 0, userAgentData: { mobile: false } },
  sessionStorage: { setItem() {} },
  window: {
    location: { href: "" },
    screen: { width: 1440, height: 900 },
    innerWidth: 1440,
    innerHeight: 900,
    matchMedia() { return { matches: false }; },
    addEventListener() {},
    visualViewport: null,
  },
};
vm.createContext(sandbox);
vm.runInContext(
  fs.readFileSync(path.join(__dirname, "..", "app", "static", "js", "inicio.js"), "utf8"),
  sandbox,
  { filename: "inicio.js" }
);

async function crearCon(modo) {
  // Flujo 8B.15: NUEVA PARTIDA abre el popup, CREAR PARTIDA envía el POST.
  await elementos["btn-nueva"].click();
  documentStub.getElementById("alias").value = "Host";
  documentStub.getElementById("modo").value = modo;
  await elementos["btn-crear"].click();
  return peticiones.at(-1);
}

(async () => {
  ok(elementos["btn-nueva"] && elementos["btn-unirse"], "portada expone NUEVA y UNIRSE");
  await elementos["btn-nueva"].click();
  ok(elementos["modal-nueva"].hidden === false, "NUEVA PARTIDA abre su popup");

  const rapido = await crearCon("rapido");
  const tablero = await crearCon("tablero");

  ok(
    rapido.url === "/api/partidas" && rapido.opciones.method === "POST",
    "la portada usa POST /api/partidas"
  );
  ok(
    JSON.parse(rapido.opciones.body).modo === "rapido",
    "seleccionar rápido envía modo=rapido"
  );
  ok(
    JSON.parse(tablero.opciones.body).modo === "tablero",
    "seleccionar tablero envía modo=tablero"
  );
  ok(
    JSON.parse(tablero.opciones.body).alias === "Host",
    "el payload conserva el alias junto al modo"
  );

  // CANCELAR no hace fetch.
  const antes = peticiones.length;
  await elementos["btn-cancelar-nueva"].click();
  ok(
    peticiones.length === antes && elementos["modal-nueva"].hidden === true,
    "CANCELAR cierra sin crear partida"
  );

  if (fallos) process.exitCode = 1;
  else console.log("MODO SELECCIÓN OK");
})();
