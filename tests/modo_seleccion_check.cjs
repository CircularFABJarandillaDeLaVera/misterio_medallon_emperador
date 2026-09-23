/* Harness del flujo real de la portada: selector -> fetch POST /api/partidas.
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

function elemento() {
  return {
    value: "",
    textContent: "",
    _oyentes: {},
    addEventListener(evento, fn) {
      this._oyentes[evento] = fn;
    },
  };
}

const elementos = {};
const documentStub = {
  getElementById(id) {
    if (!elementos[id]) elementos[id] = elemento();
    return elementos[id];
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
  sessionStorage: { setItem() {} },
  window: { location: { href: "" } },
};
vm.createContext(sandbox);
vm.runInContext(
  fs.readFileSync(path.join(__dirname, "..", "app", "static", "js", "inicio.js"), "utf8"),
  sandbox,
  { filename: "inicio.js" }
);

async function crearCon(modo) {
  documentStub.getElementById("alias").value = "Host";
  documentStub.getElementById("modo").value = modo;
  await elementos["btn-nueva"]._oyentes.click();
  return peticiones.at(-1);
}

(async () => {
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

  if (fallos) process.exitCode = 1;
  else console.log("MODO SELECCIÓN OK");
})();
