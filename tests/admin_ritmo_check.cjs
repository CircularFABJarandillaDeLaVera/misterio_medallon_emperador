/* Harness · Microfase 2: control de ritmo del anfitrión en sala.js.
   Comprueba que los controles solo existen para el anfitrión, que muestran
   la espera en segundos, que se saturan en los topes y que envían la
   credencial (no el jugador_id) en el cuerpo del mensaje.
   Uso: node tests/admin_ritmo_check.cjs */
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
let elementoActivo = null;
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
    classList: { add() {}, remove() {}, contains: () => false, toggle() {} },
    oyentes: {},
    appendChild() {},
    remove() {},
    focus() {
      elementoActivo = this;
    },
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
  const eventosDocumento = {};
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
    "admin-ritmo": elemento(""),
    "admin-ritmo-valor": elemento(""),
    "btn-ritmo-mas": elemento("MÁS RÁPIDO +"),
    "btn-ritmo-menos": elemento("MÁS LENTO −"),
    "btn-configuracion-partida": elemento("Configuración"),
    "modal-configuracion-partida": elemento(""),
    "dialogo-configuracion": elemento(""),
    "btn-cerrar-configuracion-partida": elemento("Cerrar"),
    "btn-pausar-partida": elemento("Pausar"),
    "btn-reanudar-partida": elemento("Reanudar"),
    "btn-guardar-partida": elemento("Guardar"),
  };
  porId["btn-cerrar-configuracion-partida"].hidden = false;
  porId["btn-ritmo-menos"].hidden = false;
  porId["btn-ritmo-mas"].hidden = false;
  porId["modal-configuracion-partida"].querySelector = () =>
    porId["dialogo-configuracion"];
  porId["dialogo-configuracion"].querySelectorAll = () =>
    [
      porId["btn-cerrar-configuracion-partida"],
      porId["btn-ritmo-menos"],
      porId["btn-ritmo-mas"],
      porId["btn-pausar-partida"],
      porId["btn-reanudar-partida"],
      porId["btn-guardar-partida"],
    ].filter((boton) => !boton.hidden && !boton.disabled);
  const claseBody = { add() {}, remove() {}, contains: () => false, toggle() {} };
  const sandbox = {
    console,
    document: {
      getElementById: (id) => porId[id] || (porId[id] = elemento()),
      addEventListener: (tipo, fn) => {
        (eventosDocumento[tipo] || (eventosDocumento[tipo] = [])).push(fn);
      },
      querySelector: () => null,
      querySelectorAll: () => [],
      createElement: () => elemento(),
      body: { classList: claseBody },
      documentElement: { classList: claseBody },
      get activeElement() {
        return elementoActivo;
      },
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
  return { enviados, porId, socket, sandbox, eventosDocumento };
}

function estado(extra) {
  return {
    codigo: "JARA-TEST",
    estado: "iniciada",
    modo: "rapido",
    alias: "Ana",
    es_anfitrion: true,
    velocidad_acciones: 3,
    jugadores: [],
    orden: [],
    historial: [],
    es_mi_turno: false,
    activo_investigacion: true,
    ...extra,
  };
}

// --- La plantilla trae el control provisional ---------------------------
{
  ok(SALA_HTML.includes('id="admin-ritmo"'), "la sala trae el panel de ritmo");
  ok(SALA_HTML.includes('id="btn-ritmo-mas"'), "la sala trae MÁS RÁPIDO");
  ok(SALA_HTML.includes('id="btn-ritmo-menos"'), "la sala trae MÁS LENTO");
  ok(SALA_HTML.includes('id="admin-ritmo-valor"'), "la sala trae la lectura de segundos");
  ok(
    SALA_HTML.includes('id="modal-configuracion-partida"') &&
      SALA_HTML.includes("CONFIGURACIÓN DE PARTIDA"),
    "la sala ofrece el diálogo de configuración"
  );
  ok(
    SALA_HTML.includes('id="btn-configuracion-partida"') &&
      SALA_HTML.includes("control-configuracion-partida"),
    "la sala trae el engranaje junto a los controles del marco"
  );
  ok(
    SALA_HTML.indexOf('id="admin-ritmo"') >
      SALA_HTML.indexOf('id="modal-configuracion-partida"') &&
      SALA_HTML.indexOf('id="admin-ritmo"') <
        SALA_HTML.indexOf('id="modal-historial"'),
    "los controles existentes se reutilizan dentro del diálogo"
  );
  ok(
    SALA_HTML.includes('aria-labelledby="configuracion-partida-titulo"') &&
      SALA_HTML.includes('id="btn-cerrar-configuracion-partida"'),
    "el diálogo tiene título accesible y botón X"
  );
}

// --- Estética: la familia medallón, no una nueva ------------------------
{
  const bloque = SALA_HTML.slice(
    SALA_HTML.indexOf('id="modal-configuracion-partida"'),
    SALA_HTML.indexOf('id="modal-historial"')
  );
  ok(
    bloque.includes("medallon medallon-secundario medallon-compacto"),
    "los botones reutilizan la familia medallón del juego"
  );
  ok(bloque.includes("nota-privada"), "el aviso usa el estilo de nota privada existente");
  ok(CSS.includes(".admin-ritmo-valor"), "la lectura de segundos tiene estilo propio");
  ok(
    CSS.includes("max-height: calc(100dvh - 16px)") &&
      CSS.includes("overflow-y: auto"),
    "la configuración se limita a la altura disponible y permite desplazarse"
  );
  ok(
    CSS.includes(".barra-controles-inferior > .control-configuracion-partida") &&
      CSS.includes("order: 3") &&
      CSS.includes(".barra-controles-inferior > button[hidden]"),
    "el engranaje está en la barra común y desaparece sin dejar hueco"
  );
  ok(
    CSS.includes(".admin-ritmo-fila .medallon"),
    "el tamaño de los botones se ajusta sin crear una familia nueva"
  );
}

// --- Solo el anfitrión ve el control -------------------------------------
{
  const { sandbox, porId } = montar("secreto");
  sandbox.pintarRitmo(estado({ es_anfitrion: false }));
  ok(porId["admin-ritmo"].hidden === true, "un jugador normal no ve el panel");
  const { sandbox: otro, porId: otroIds } = montar("secreto");
  otro.pintarRitmo(estado({ es_anfitrion: true }));
  ok(otroIds["admin-ritmo"].hidden === false, "el anfitrión sí lo ve");
}

// --- Muestra la espera en segundos y satura en los topes ---------------
{
  const { sandbox, porId } = montar("secreto");
  sandbox.pintarRitmo(estado({ velocidad_acciones: 3 }));
  ok(porId["admin-ritmo-valor"].textContent === "3 S", "muestra la espera en segundos");
  ok(porId["btn-ritmo-mas"].disabled === false, "con 3 s se puede acelerar");
  ok(porId["btn-ritmo-menos"].disabled === false, "con 3 s se puede ralentizar");

  sandbox.pintarRitmo(estado({ velocidad_acciones: 10 }));
  ok(porId["admin-ritmo-valor"].textContent === "10 S", "muestra el tope máximo");
  ok(porId["btn-ritmo-mas"].disabled === true, "en 10 s no se puede ir más rápido");
  ok(porId["btn-ritmo-menos"].disabled === false, "en 10 s aún se puede ralentizar");

  sandbox.pintarRitmo(estado({ velocidad_acciones: 1 }));
  ok(porId["admin-ritmo-valor"].textContent === "1 S", "muestra el tope mínimo");
  ok(porId["btn-ritmo-menos"].disabled === true, "en 1 s no se puede ir más lento");
  ok(porId["btn-ritmo-mas"].disabled === false, "en 1 s aún se puede acelerar");
}

// --- Los botones envían la acción con la credencial ---------------------
{
  const { enviados, porId, sandbox } = montar("secreto-admin");
  sandbox.pintarRitmo(estado({}));
  porId["btn-ritmo-mas"].click();
  porId["btn-ritmo-menos"].click();
  ok(enviados.length === 2, "cada botón envía su acción");
  ok(enviados[0].accion === "acelerar_acciones", "MÁS RÁPIDO acelera");
  ok(enviados[1].accion === "ralentizar_acciones", "MÁS LENTO ralentiza");
  ok(
    enviados.every((m) => m.credencial_admin === "secreto-admin"),
    "las acciones viajan con la credencial administrativa"
  );
  ok(
    enviados.every((m) => !("jugador_id" in m)),
    "las acciones no viajan con el jugador_id"
  );
}

// --- Lo que el cliente NO puede hacer por su cuenta ---------------------
{
  const fuente = SALA_JS;
  ok(
    !/"velocidad_acciones"\s*:/.test(fuente),
    "el cliente nunca envía un valor de velocidad: lo decide el servidor"
  );
  ok(
    fuente.includes("sala.velocidad_acciones"),
    "la lectura del valor viene del estado, no de un contador local"
  );
  ok(
    /function pintarRitmo\(sala\)/.test(fuente) &&
      /panelRitmo\.hidden = !puedeConfigurar/.test(fuente) &&
      /btnConfiguracionPartida\.hidden = !puedeConfigurar/.test(fuente),
    "el panel y el engranaje se deciden por rol"
  );
}

// --- Apertura, cierre y privacidad del modal ----------------------------
{
  const { sandbox, porId, eventosDocumento } = montar("secreto-admin");
  sandbox.pintarRitmo(estado({ es_anfitrion: true }));
  porId["btn-configuracion-partida"].click();
  ok(
    porId["modal-configuracion-partida"].hidden === false,
    "el anfitrión abre la configuración con el engranaje"
  );
  ok(
    elementoActivo === porId["btn-cerrar-configuracion-partida"],
    "al abrir se enfoca el botón X"
  );

  const escapar = (evento) =>
    eventosDocumento.keydown.forEach((oyente) => oyente(evento));
  escapar({ key: "Escape", preventDefault() {} });
  ok(
    porId["modal-configuracion-partida"].hidden === true,
    "Escape cierra la configuración"
  );
  ok(
    elementoActivo === porId["btn-configuracion-partida"],
    "al cerrar se devuelve el foco al engranaje"
  );

  porId["btn-configuracion-partida"].click();
  porId["modal-configuracion-partida"].oyentes.click[0]({
    target: porId["modal-configuracion-partida"],
  });
  ok(
    porId["modal-configuracion-partida"].hidden === true,
    "pulsar fuera cierra la configuración"
  );
  porId["btn-configuracion-partida"].click();
  porId["btn-cerrar-configuracion-partida"].click();
  ok(
    porId["modal-configuracion-partida"].hidden === true,
    "el botón X cierra la configuración"
  );

  porId["btn-configuracion-partida"].click();
  const primerBoton = porId["btn-cerrar-configuracion-partida"];
  const ultimoBoton = porId["btn-guardar-partida"];
  elementoActivo = ultimoBoton;
  escapar({ key: "Tab", shiftKey: false, preventDefault() {} });
  ok(elementoActivo === primerBoton, "Tab mantiene el foco dentro del diálogo");
  elementoActivo = primerBoton;
  escapar({ key: "Tab", shiftKey: true, preventDefault() {} });
  ok(elementoActivo === ultimoBoton, "Mayús+Tab mantiene el foco dentro del diálogo");
}

{
  const { sandbox, porId } = montar("secreto");
  sandbox.pintarRitmo(estado({ es_anfitrion: false }));
  porId["btn-configuracion-partida"].click();
  ok(porId["btn-configuracion-partida"].hidden, "el jugador normal no ve el engranaje");
  ok(
    porId["modal-configuracion-partida"].hidden,
    "el jugador normal no puede abrir el diálogo"
  );
}

{
  const { sandbox, porId } = montar("secreto");
  sandbox.pintarRitmo(estado({ es_anfitrion: true, estado: "esperando" }));
  ok(
    porId["btn-configuracion-partida"].hidden,
    "la configuración no aparece durante el lobby"
  );
  ok(
    porId["admin-ritmo"].hidden,
    "los controles siguen ocultos hasta que empieza la partida"
  );
}

if (fallos) process.exit(1);
console.log("ADMIN RITMO OK");
