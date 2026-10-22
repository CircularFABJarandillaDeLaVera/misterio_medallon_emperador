/* Harness · Microfase 1 de administración: circuito de la credencial en el
   cliente. El servidor es la autoridad; aquí se comprueba que el navegador
   solo pide el secreto cuando no lo tiene, que lo guarda cuando se lo
   mandan y que nunca lo manda por la URL del WebSocket.
   Uso: node tests/admin_credencial_check.cjs */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const RAIZ = path.join(__dirname, "..");
const leer = (...partes) => fs.readFileSync(path.join(RAIZ, ...partes), "utf8");
const SALA_JS = leer("app", "static", "js", "sala.js");
const INICIO_JS = leer("app", "static", "js", "inicio.js");
const SALA_HTML = leer("app", "templates", "sala.html");

let fallos = 0;
function ok(condicion, nombre) {
  console.log(`${condicion ? "PASS" : "FAIL"} ${nombre}`);
  if (!condicion) fallos += 1;
}

function montarSala({ almacen }) {
  const enviados = [];
  let socket = null;
  class WebSocketFalso {
    constructor(url) {
      this.url = url;
      socket = this;
    }
    send(texto) {
      enviados.push(JSON.parse(texto));
    }
  }
  function elemento(texto) {
    return {
      textContent: texto || "",
      innerHTML: "",
      hidden: true,
      disabled: false,
      style: {},
      dataset: {},
      children: [],
      classList: { add() {}, remove() {}, contains: () => false, toggle() {} },
      appendChild() {},
      remove() {},
      focus() {},
      setAttribute() {},
      addEventListener() {},
      querySelector: () => elemento(),
      querySelectorAll: () => [],
    };
  }
  const porId = { codigo: elemento("JARA-TEST"), error: elemento("") };
  const claseBody = { add() {}, remove() {}, contains: () => false, toggle() {} };
  const sandbox = {
    console,
    document: {
      getElementById: (id) => porId[id] || (porId[id] = elemento()),
      addEventListener: () => {},
      querySelector: () => null,
      querySelectorAll: () => [],
      createElement: () => elemento(),
      body: { classList: claseBody },
      documentElement: { classList: claseBody },
    },
    sessionStorage: almacen,
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
  return { enviados, onmessage: socket.onmessage, sandbox };
}

function estado(extra) {
  return {
    codigo: "JARA-TEST",
    estado: "iniciada",
    modo: "rapido",
    alias: "Ana",
    es_anfitrion: true,
    jugadores: [],
    orden: [],
    historial: [],
    es_mi_turno: false,
    activo_investigacion: true,
    ...extra,
  };
}

function almacenInicial(conCredencial) {
  const datos = { jugador_id: "jug-real", alias: "Ana" };
  if (conCredencial) datos.credencial_admin = "secreto-ya-guardado";
  return {
    getItem: (clave) => (clave in datos ? datos[clave] : null),
    setItem: (clave, valor) => {
      datos[clave] = valor;
    },
    _datos: datos,
  };
}

// --- El anfitrión sin secreto lo pide -----------------------------------
{
  const almacen = almacenInicial(false);
  const { enviados, onmessage } = montarSala({ almacen });
  onmessage({ data: JSON.stringify({ tipo: "estado_privado", sala: estado({}) }) });
  ok(enviados.length === 1, "el anfitrión sin secreto pide exactamente uno");
  ok(
    enviados[0] && enviados[0].accion === "pedir_credencial_admin",
    "la petición es la acción administrativa esperada"
  );
  ok(
    !("credencial_admin" in (enviados[0] || {})),
    "la petición no incluye ninguna credencial en la URL ni en el cuerpo"
  );

  // El servidor responde y el cliente lo conserva.
  onmessage({
    data: JSON.stringify({ tipo: "credencial_admin", credencial: "secreto-nuevo" }),
  });
  ok(
    almacen._datos.credencial_admin === "secreto-nuevo",
    "el secreto recibido se guarda para las acciones de administración"
  );

  // Con el secreto ya en su poder, no vuelve a pedirlo.
  const antes = enviados.length;
  onmessage({ data: JSON.stringify({ tipo: "estado_privado", sala: estado({}) }) });
  ok(enviados.length === antes, "con el secreto guardado no se vuelve a pedir");
}

// --- Un jugador normal no pide nada -------------------------------------
{
  const almacen = almacenInicial(false);
  const { enviados, onmessage } = montarSala({ almacen });
  onmessage({
    data: JSON.stringify({ tipo: "estado_privado", sala: estado({ es_anfitrion: false }) }),
  });
  ok(enviados.length === 0, "un jugador que no es anfitrión no pide ninguna credencial");
}

// --- Nada de credenciales en el estado ni en la URL ----------------------
{
  const almacen = almacenInicial(true);
  const { enviados, onmessage } = montarSala({ almacen });
  onmessage({ data: JSON.stringify({ tipo: "estado_privado", sala: estado({}) }) });
  ok(enviados.length === 0, "el estado privado no provoca ninguna petición");
  ok(
    !/mensaje\.sala\.credencial/.test(SALA_JS),
    "la credencial nunca se lee del estado privado"
  );
  const bloqueWs = SALA_JS.slice(
    SALA_JS.indexOf("new WebSocket("),
    SALA_JS.indexOf(");", SALA_JS.indexOf("new WebSocket("))
  );
  ok(
    !/credencial|token|admin/i.test(bloqueWs),
    "la URL del WebSocket no contiene la credencial"
  );
}

// --- La portada guarda el secreto solo al crear -------------------------
{
  ok(
    INICIO_JS.includes('sessionStorage.setItem("credencial_admin", datos.credencial_admin)'),
    "la portada guarda el secreto que devuelve la creación"
  );
  ok(
    INICIO_JS.includes("if (datos.credencial_admin)"),
    "solo se guarda si la respuesta trae credencial (nadie más la recibe)"
  );
  const bloqueUnirse = INICIO_JS.slice(
    INICIO_JS.indexOf("async function unirsePartida"),
    INICIO_JS.indexOf("// --- Microfase 6", INICIO_JS.indexOf("async function unirsePartida"))
  );
  ok(
    !bloqueUnirse.includes("credencial_admin"),
    "unirse a una partida no guarda ninguna credencial"
  );
}

// --- La plantilla no expone el secreto ----------------------------------
{
  ok(
    !/credencial_admin/.test(SALA_HTML),
    "la plantilla de sala no contiene ninguna credencial incrustada"
  );
}

if (fallos) process.exit(1);
console.log("ADMIN CREDENCIAL OK");
