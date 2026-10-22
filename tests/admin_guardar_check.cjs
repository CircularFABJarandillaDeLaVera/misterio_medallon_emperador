/* Harness · Microfase 4: GUARDAR PARTIDA en la interfaz.
   El botón solo existe para el anfitrión, pide la credencial por CABECERA
   (nunca en la URL), dispara la descarga del JSON y avisa de los errores.
   Uso: node tests/admin_guardar_check.cjs */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const RAIZ = path.join(__dirname, "..");
const leer = (...partes) => fs.readFileSync(path.join(RAIZ, ...partes), "utf8");
const SALA_JS = leer("app", "static", "js", "sala.js");
const SALA_HTML = leer("app", "templates", "sala.html");
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
    removeChild() {},
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
  const peticiones = [];
  const descargas = [];
  let socket = null;
  class WebSocketFalso {
    constructor(url) {
      this.url = url;
      this.readyState = 1;
      socket = this;
    }
    send(texto) {
      /* el guardado no usa el WebSocket */
    }
  }
  WebSocketFalso.OPEN = 1;
  WebSocketFalso.CLOSED = 3;

  const cuerpo = elemento();
  cuerpo.classList = elemento().classList;
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
    "btn-guardar-partida": elemento("GUARDAR PARTIDA"),
    "admin-guardar-estado": elemento(""),
  };
  const datos = { jugador_id: "jug-real", alias: "Ana" };
  if (credencial) datos.credencial_admin = credencial;

  const sandbox = {
    console,
    document: {
      getElementById: (id) => porId[id] || (porId[id] = elemento()),
      addEventListener: () => {},
      querySelector: () => null,
      querySelectorAll: () => [],
      createElement: () => elemento(),
      body: cuerpo,
      documentElement: { classList: cuerpo.classList },
    },
    sessionStorage: {
      getItem: (clave) => (clave in datos ? datos[clave] : null),
      setItem: (clave, valor) => {
        datos[clave] = valor;
      },
    },
    setTimeout: () => 0,
    clearTimeout: () => {},
    URL: {
      createObjectURL: () => "blob:simulado",
      revokeObjectURL: () => {},
    },
    Blob: class {
      constructor(partes, opciones) {
        this.partes = partes;
        this.opciones = opciones;
      }
    },
    fetch: (url, opciones) => {
      // Solo interesan las peticiones del guardado; el tablero que pide
      // sala.js al arrancar no forma parte de esta comprobación.
      if (!String(url).includes("/guardar")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          text: () => Promise.resolve("{}"),
          json: () => Promise.resolve({}),
        });
      }
      peticiones.push({ url, opciones });
      const cabecera = (opciones && opciones.headers) || {};
      const ok = cabecera["X-Token-Admin"] === "secreto-admin";
      const cuerpoRespuesta = ok
        ? '{"formato":"misterio-medallon/partida","version":1}'
        : '{"detalle":"Solo el anfitrión puede administrar la partida."}';
      return Promise.resolve({
        ok,
        status: ok ? 200 : 403,
        text: () => Promise.resolve(cuerpoRespuesta),
        json: () => Promise.resolve(JSON.parse(cuerpoRespuesta)),
      });
    },
    WebSocket: WebSocketFalso,
    Set,
    Map,
  };
  sandbox.window = { location: { protocol: "http:", host: "localhost:8000" } };
  vm.createContext(sandbox);
  vm.runInContext(SALA_JS, sandbox, { filename: "sala.js" });
  return { peticiones, descargas, porId, sandbox, cuerpo };
}

function estado(extra) {
  return {
    codigo: "JARA-TEST",
    estado: "iniciada",
    modo: "tablero",
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

// Vuelca todas las microtareas pendientes y una macrotarea: así la cadena
// de promesas del guardado ha terminado cuando se comprueba.
const esperar = async () => {
  for (let vuelta = 0; vuelta < 5; vuelta += 1) {
    await new Promise((resolver) => setTimeout(resolver, 0));
  }
};

// --- La plantilla trae el botón y su aviso -----------------------------
{
  ok(SALA_HTML.includes('id="btn-guardar-partida"'), "la sala trae GUARDAR PARTIDA");
  ok(SALA_HTML.includes('id="admin-guardar-estado"'), "trae el aviso de resultado");
  const bloque = SALA_HTML.slice(
    SALA_HTML.indexOf('id="btn-guardar-partida"') - 200,
    SALA_HTML.indexOf('id="admin-guardar-estado"') + 200
  );
  ok(
    bloque.includes("medallon medallon-secundario medallon-compacto"),
    "el botón reutiliza la familia medallón"
  );
  ok(CSS.includes(".admin-guardar-estado"), "el aviso tiene estilo propio");
}

// --- Solo el anfitrión lo ve -------------------------------------------
{
  const { sandbox, porId } = montar("secreto-admin");
  sandbox.pintarRitmo(estado({ es_anfitrion: false }));
  ok(porId["admin-ritmo"].hidden === true, "un jugador normal no ve el panel");
  ok(porId["btn-guardar-partida"].hidden === true, "ni el botón de guardar");

  const otro = montar("secreto-admin");
  otro.sandbox.pintarRitmo(estado({ es_anfitrion: true }));
  ok(otro.porId["btn-guardar-partida"].hidden === false, "el anfitrión sí lo ve");
}

// --- Se puede guardar en pausa ------------------------------------------
{
  const { sandbox, porId } = montar("secreto-admin");
  sandbox.pintarRitmo(estado({ pausada: true }));
  ok(porId["btn-guardar-partida"].hidden === false, "en pausa también se puede guardar");
}

// --- Pide la credencial por cabecera, nunca por la URL -----------------
async function comprobarDescarga() {
  const { sandbox, porId, peticiones } = montar("secreto-admin");
  sandbox.pintarRitmo(estado({}));
  porId["btn-guardar-partida"].click();
  await esperar();
  ok(peticiones.length === 1, "pulsa GUARDAR pide el archivo");
  const peticion = peticiones[0];
  ok(
    peticion.url === "/api/partidas/JARA-TEST/guardar",
    "la URL solo lleva el código de la sala"
  );
  ok(
    !peticion.url.includes("secreto-admin") && !peticion.url.includes("?"),
    "la credencial NO viaja en la URL"
  );
  ok(
    peticion.opciones.headers["X-Token-Admin"] === "secreto-admin",
    "la credencial viaja en la cabecera X-Token-Admin"
  );
  ok(
    porId["admin-guardar-estado"].textContent === "PARTIDA GUARDADA.",
    "confirma que se ha guardado"
  );
  ok(
    porId["admin-guardar-estado"].classList.contains("error") === false,
    "un guardado correcto no se marca como error"
  );
  ok(porId["btn-guardar-partida"].disabled === false, "el botón vuelve a estar disponible");
}

// --- Trata el error de autorización ------------------------------------
async function comprobarError() {
  const { sandbox, porId } = montar("otra-credencial");
  sandbox.pintarRitmo(estado({}));
  porId["btn-guardar-partida"].click();
  await esperar();
  ok(
    porId["admin-guardar-estado"].classList.contains("error"),
    "un rechazo del servidor se marca como error"
  );
  ok(
    porId["admin-guardar-estado"].textContent.includes("ANFITRIÓN"),
    "muestra el motivo del rechazo"
  );
  ok(porId["btn-guardar-partida"].disabled === false, "el botón se rehabilita tras fallar");
}

// --- Sin credencial guardada -------------------------------------------
async function comprobarSinCredencial() {
  const { sandbox, porId, peticiones } = montar(null);
  sandbox.pintarRitmo(estado({}));
  porId["btn-guardar-partida"].click();
  await esperar();
  ok(peticiones.length === 1, "intenta la descarga igualmente");
  ok(
    peticiones[0].opciones.headers["X-Token-Admin"] === "",
    "manda la cabecera vacía, sin inventarse nada"
  );
  ok(
    porId["admin-guardar-estado"].classList.contains("error"),
    "y explica que no ha podido"
  );
}

// --- El cliente no inventa el archivo ----------------------------------
{
  ok(
    !/enviarPorWebSocket|ws\.send\(JSON\.stringify\(\{[^}]*guardar/.test(SALA_JS),
    "el archivo no se pide por el WebSocket"
  );
  ok(
    SALA_JS.includes("/guardar"),
    "la descarga se pide por HTTP"
  );
  ok(
    /new Blob\(\[texto\]/.test(SALA_JS),
    "la respuesta se baja como archivo"
  );
}

(async () => {
  await comprobarDescarga();
  await comprobarError();
  await comprobarSinCredencial();
  if (fallos) process.exit(1);
  console.log("ADMIN GUARDAR OK");
})();
