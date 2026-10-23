/* Harness · Microfase 3: pausa y reanudación en la interfaz.
   El aviso de pausa lo ve TODO el mundo; los botones, solo el anfitrión, y
   solo el que corresponde al estado. Ninguna acción de la interfaz decide
   nada: el servidor manda.
   Uso: node tests/admin_pausa_check.cjs */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const RAIZ = path.join(__dirname, "..");
const leer = (...partes) => fs.readFileSync(path.join(RAIZ, ...partes), "utf8");
const SALA_JS = leer("app", "static", "js", "sala.js");
const SALA_HTML = leer("app", "templates", "_sala_interfaz.html");
const CSS = leer("app", "static", "css", "estilos.css");

let fallos = 0;
function ok(condicion, nombre) {
  console.log(`${condicion ? "PASS" : "FAIL"} ${nombre}`);
  if (!condicion) fallos += 1;
}

function elemento(texto) {
  return {
    textContent: texto || "",
    innerHTML: "",
    hidden: true,
    disabled: false,
    value: "",
    style: {},
    dataset: {},
    children: [],
    classList: {
      clases: new Set(),
      add(n) {
        this.clases.add(n);
      },
      remove(n) {
        this.clases.delete(n);
      },
      contains(n) {
        return this.clases.has(n);
      },
      toggle(n, activo) {
        if (activo) this.clases.add(n);
        else this.clases.delete(n);
      },
    },
    oyentes: {},
    appendChild() {},
    remove() {},
    focus() {},
    setAttribute() {},
    addEventListener(tipo, fn) {
      (this.oyentes[tipo] || (this.oyentes[tipo] = [])).push(fn);
    },
    click() {
      (this.oyentes.click || []).forEach((fn) => fn({ preventDefault() {} }));
    },
    querySelector: () => elemento(),
    querySelectorAll: () => [],
  };
}

function montar(credencial) {
  const enviados = [];
  let socket = null;
  class WebSocketFalso {
    constructor(url) {
      this.url = url;
      this.readyState = 1;
      socket = this;
    }
    send(texto) {
      enviados.push(JSON.parse(texto));
    }
  }
  WebSocketFalso.OPEN = 1;
  WebSocketFalso.CLOSED = 3;
  const datos = { jugador_id: "jug-real", alias: "Ana" };
  if (credencial) datos.credencial_admin = credencial;
  const porId = {
    codigo: elemento("JARA-TEST"),
    error: elemento(""),
    "admin-pausa-aviso": elemento("PARTIDA EN PAUSA"),
    "admin-ritmo": elemento(""),
    "admin-ritmo-valor": elemento("3 S"),
    "btn-ritmo-mas": elemento("MÁS RÁPIDO +"),
    "btn-ritmo-menos": elemento("MÁS LENTO −"),
    "btn-pausar-partida": elemento("PAUSAR PARTIDA"),
    "btn-reanudar-partida": elemento("REANUDAR PARTIDA"),
  };
  const body = { classList: elemento().classList };
  const sandbox = {
    console,
    document: {
      getElementById: (id) => porId[id] || (porId[id] = elemento()),
      addEventListener: () => {},
      querySelector: () => null,
      querySelectorAll: () => [],
      createElement: () => elemento(),
      body,
      documentElement: { classList: body.classList },
    },
    sessionStorage: {
      getItem: (clave) => (clave in datos ? datos[clave] : null),
      setItem: (clave, valor) => {
        datos[clave] = valor;
      },
    },
    setTimeout: () => 0,
    clearTimeout: () => {},
    fetch: () => ({ then: () => ({ then: () => {} }) }),
    WebSocket: WebSocketFalso,
    Set,
    Map,
  };
  sandbox.window = { location: { protocol: "http:", host: "localhost:8000" } };
  vm.createContext(sandbox);
  vm.runInContext(SALA_JS, sandbox, { filename: "sala.js" });
  return { enviados, porId, body, sandbox };
}

function estado(extra) {
  return {
    codigo: "JARA-TEST",
    estado: "iniciada",
    modo: "rapido",
    alias: "Ana",
    es_anfitrion: true,
    velocidad_acciones: 3,
    pausada: false,
    jugadores: [],
    orden: [],
    historial: [],
    es_mi_turno: false,
    activo_investigacion: true,
    ...extra,
  };
}

// --- La plantilla trae los dos controles y el aviso ---------------------
{
  ok(SALA_HTML.includes('id="btn-pausar-partida"'), "la sala trae PAUSAR PARTIDA");
  ok(SALA_HTML.includes('id="btn-reanudar-partida"'), "la sala trae REANUDAR PARTIDA");
  ok(SALA_HTML.includes('id="admin-pausa-aviso"'), "la sala trae el aviso de pausa");
  ok(
    SALA_HTML.includes("PARTIDA EN PAUSA"),
    "el aviso dice literalmente PARTIDA EN PAUSA"
  );
  ok(
    SALA_HTML.indexOf('id="admin-pausa-aviso"') <
      SALA_HTML.indexOf('id="admin-ritmo"'),
    "el aviso está FUERA del panel que solo ve el anfitrión"
  );
  ok(CSS.includes(".admin-pausa-aviso"), "el aviso tiene estilo propio");
  ok(CSS.includes(".admin-pausa-fila"), "los botones de pausa tienen su bloque");
}

// --- El aviso lo ve todo el mundo; los botones, solo el anfitrión --------
{
  const { sandbox, porId } = montar("secreto");
  sandbox.pintarRitmo(estado({ es_anfitrion: false, pausada: true }));
  ok(porId["admin-pausa-aviso"].hidden === false, "un jugador normal ve el aviso de pausa");
  ok(porId["admin-ritmo"].hidden === true, "pero no ve los controles");
  ok(porId["btn-pausar-partida"].hidden === true, "ni puede pulsar PAUSAR");
  ok(porId["btn-reanudar-partida"].hidden === true, "ni REANUDAR");
}

{
  const { sandbox, porId } = montar("secreto");
  sandbox.pintarRitmo(estado({ es_anfitrion: true, pausada: true }));
  ok(porId["admin-pausa-aviso"].hidden === false, "el anfitrión también ve el aviso");
  ok(porId["admin-ritmo"].hidden === false, "y tiene su panel");
}

// --- Solo se muestra la acción que toca ---------------------------------
{
  const { sandbox, porId } = montar("secreto");
  sandbox.pintarRitmo(estado({ pausada: false }));
  ok(porId["btn-pausar-partida"].hidden === false, "en marcha se ofrece PAUSAR");
  ok(porId["btn-reanudar-partida"].hidden === true, "y no REANUDAR");

  sandbox.pintarRitmo(estado({ pausada: true }));
  ok(porId["btn-pausar-partida"].hidden === true, "en pausa se ofrece REANUDAR");
  ok(porId["btn-reanudar-partida"].hidden === false, "y no PAUSAR");
}

{
  const { sandbox, porId, body } = montar("secreto");
  sandbox.pintarRitmo(estado({ pausada: false }));
  ok(
    body.classList.contains("partida-en-pausa") === false,
    "sin pausa no se marca el cuerpo"
  );
  sandbox.pintarRitmo(estado({ pausada: true }));
  ok(body.classList.contains("partida-en-pausa"), "con pausa se marca el cuerpo");
}

// --- El ritmo conserva su valor durante la pausa ------------------------
{
  const { sandbox, porId } = montar("secreto");
  sandbox.pintarRitmo(estado({ pausada: false, velocidad_acciones: 7 }));
  sandbox.pintarRitmo(estado({ pausada: true, velocidad_acciones: 7 }));
  ok(porId["admin-ritmo-valor"].textContent === "7 S", "la velocidad se conserva en pausa");
  ok(porId["btn-ritmo-mas"].disabled === false, "y se puede seguir ajustando");
  ok(porId["btn-ritmo-menos"].disabled === false, "en ambos sentidos");
}

// --- Los botones envían la acción con la credencial ---------------------
{
  const { enviados, porId, sandbox } = montar("secreto-admin");
  sandbox.pintarRitmo(estado({ pausada: false }));
  porId["btn-pausar-partida"].click();
  sandbox.pintarRitmo(estado({ pausada: true }));
  porId["btn-reanudar-partida"].click();
  ok(enviados.length === 2, "cada botón envía su acción");
  ok(enviados[0].accion === "pausar_partida", "PAUSAR PARTIDA pausa");
  ok(enviados[1].accion === "reanudar_partida", "REANUDAR PARTIDA reanuda");
  ok(
    enviados.every((m) => m.credencial_admin === "secreto-admin"),
    "las dos acciones viajan con la credencial administrativa"
  );
  ok(
    enviados.every((m) => !("jugador_id" in m)),
    "ninguna acción viaja con el jugador_id"
  );
}

// --- El cliente no inventa el estado de pausa ---------------------------
{
  ok(
    !/"pausada"\s*:\s*true/.test(SALA_JS),
    "el cliente nunca se marca la pausa por su cuenta"
  );
  ok(
    /Boolean\(sala && sala\.pausada\)/.test(SALA_JS),
    "el estado de pausa se lee del servidor"
  );
  ok(
    SALA_JS.includes('!sessionStorage.getItem("credencial_admin")'),
    "la credencial se sigue buscando donde se guardó"
  );
}

if (fallos) process.exit(1);
console.log("ADMIN PAUSA OK");
