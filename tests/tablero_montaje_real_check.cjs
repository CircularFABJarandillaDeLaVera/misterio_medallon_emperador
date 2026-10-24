/* Montaje completo: plantilla real + estado WS antes del descriptor fetch.
   Uso: node tests/tablero_montaje_real_check.cjs */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const CSS = fs.readFileSync(
  path.join(__dirname, "..", "app", "static", "css", "estilos.css"),
  "utf8"
);

let fallos = 0;
let riesgos = 0;
let contratosPendientes = 0;
function ok(condicion, nombre) {
  console.log(`${condicion ? "PASS" : "FAIL"} ${nombre}`);
  if (!condicion) fallos += 1;
}

function riesgo(condicion, nombre) {
  console.log(`${condicion ? "PASS" : "RIESGO CONOCIDO"} ${nombre}`);
  if (!condicion) riesgos += 1;
}

function contrato(condicion, nombre, motivo) {
  console.log(
    condicion
      ? `PASS CONTRATO ${nombre}`
      : `XFAIL CONTRATO ${nombre} · ${motivo}`
  );
  if (!condicion) contratosPendientes += 1;
}

function elemento(tag) {
  const e = {
    tag, children: [], hidden: true, disabled: false, style: {}, dataset: {},
    attributes: {}, className: "", value: "", options: [], selectedIndex: -1,
    parentElement: { hidden: false }, _texto: "", _oyentes: {},
    set textContent(v) { this.children = []; this._texto = String(v); },
    get textContent() { return this._texto + this.children.map((h) => h.textContent).join(""); },
    set innerHTML(v) { this.children = []; this._texto = ""; this._html = String(v); },
    get innerHTML() { return this._html || ""; },
    appendChild(h) { this.children.push(h); h.parentElement = this; return h; },
    addEventListener(tipo, fn) { (this._oyentes[tipo] ||= []).push(fn); },
    click() { if (!this.disabled) (this._oyentes.click || []).forEach((fn) => fn({ target: this })); },
    setAttribute(k, v) { this.attributes[k] = String(v); if (k === "class") this.className = String(v); },
    querySelector() { return elemento("div"); },
  };
  e.classList = {
    add(...cs) { const s = new Set(e.className.split(/\s+/).filter(Boolean)); cs.forEach((c) => s.add(c)); e.className = [...s].join(" "); },
    remove(...cs) { e.className = e.className.split(/\s+/).filter((c) => c && !cs.includes(c)).join(" "); },
    toggle(c, activo) { activo ? this.add(c) : this.remove(c); },
    contains(c) { return e.className.split(/\s+/).includes(c); },
  };
  return e;
}

class ContextoCanvas {
  setTransform() {} clearRect() {} fillRect() {} beginPath() {} moveTo() {}
  lineTo() {} stroke() {} fill() {} arc() {} clip() {} save() {} restore() {}
  setLineDash() {} drawImage() {} quadraticCurveTo() {} closePath() {}
}
class CanvasMontaje {
  constructor() {
    Object.assign(this, elemento("canvas"));
    this.ctx = new ContextoCanvas(); this.lado = 700; this.style = {};
  }
  getContext() { return this.ctx; }
  getBoundingClientRect() { return { left: 0, top: 0, width: this.lado, height: this.lado }; }
  emitir(x, y) {
    (this._oyentes.pointerup || []).forEach((fn) => fn({ clientX: x * 7, clientY: y * 7 }));
  }
}
class ImagenMontaje {
  constructor() { this.naturalWidth = 800; this.naturalHeight = 600; this.width = 800; this.height = 600; }
  set src(valor) { this._src = valor; if (this.onload) this.onload(); }
  get src() { return this._src; }
}

const registro = {};
const documentStub = {
  body: elemento("body"),
  documentElement: elemento("html"),
  activeElement: null,
  _oyentes: {},
  getElementById(id) {
    if (!registro[id]) registro[id] = id === "tablero-canvas" ? new CanvasMontaje() : elemento("div");
    return registro[id];
  },
  createElement(tag) { return tag === "canvas" ? new CanvasMontaje() : elemento(tag); },
  createElementNS(_ns, tag) { return elemento(tag); },
  addEventListener(tipo, fn) { (this._oyentes[tipo] ||= []).push(fn); },
  dispatch(tipo, evento) { (this._oyentes[tipo] || []).forEach((fn) => fn(evento)); },
  querySelector(selector) {
    if (selector === ".interfaz-sala") {
      if (!registro["interfaz-sala"]) registro["interfaz-sala"] = elemento("main");
      return registro["interfaz-sala"];
    }
    return null;
  },
  querySelectorAll(selector) {
    if (selector !== ".modal") return [];
    return Object.entries(registro)
      .filter(([id]) => id.startsWith("modal-"))
      .map(([, modal]) => modal);
  },
};
registro.codigo = elemento("p");
registro.codigo.textContent = "JARA-REAL";
registro["modal-aprender"] = elemento("div");
registro["modal-aprender"].hidden = true;
registro["barra-controles-inferior"] = elemento("nav");
registro["barra-controles-inferior"].hidden = false;

const exteriores = [
  "parador", "iglesia-san-agustin", "ermita-sopetran", "cristo-humilladero",
  "nuestra-senora-torre", "museo-escobazos", "puente-parral", "picota",
];
const ubicaciones = [...exteriores, "plaza-constitucion"];
const coordenadas = [[50, 8], [79, 20], [92, 50], [79, 80], [50, 92], [21, 80], [8, 50], [21, 20], [50, 50]];
const nodos = ubicaciones.map((id, i) => ({
  id, tipo: "ubicacion", nombre: id, x: coordenadas[i][0], y: coordenadas[i][1],
  imagen_tarjeta: `/static/img/lugares/${id}.jpeg`,
}));
const parejas = exteriores.map((id, i) => [id, exteriores[(i + 1) % 8]])
  .concat(exteriores.map((id) => [id, "plaza-constitucion"]));
const caminos = parejas.map(([origen, destino]) => {
  const id = `camino-${origen}-${destino}`;
  const a = nodos.find((n) => n.id === origen);
  const b = nodos.find((n) => n.id === destino);
  const casillas = [1, 2, 3].map((paso) => {
    const cid = `${id}-${paso}`;
    nodos.push({ id: cid, tipo: "casilla", nombre: cid,
      x: a.x + (b.x - a.x) * paso / 4, y: a.y + (b.y - a.y) * paso / 4 });
    return cid;
  });
  return { id, nodos: [origen, ...casillas, destino] };
});
const personajes = ["vera", "bruno", "lucia", "alvaro", "mateo", "eulalia"];
const descriptor = {
  nodos, caminos,
  pasadizos: [
    { id: "pasadizo-parador-nuestra-senora-torre", origen: "parador", destino: "nuestra-senora-torre" },
    { id: "pasadizo-ermita-sopetran-puente-parral", origen: "ermita-sopetran", destino: "puente-parral" },
  ],
  peon: "/static/img/personajes/peon.svg",
  colores_personajes: {
    vera: "#6f42a5", bruno: "#3f4448", lucia: "#285943",
    alvaro: "#176b73", mateo: "#c49324", eulalia: "#b33a2f",
  },
};

/* Contrato futuro de SalaJuego. Este escenario empieza como una portada real:
   no inventa nodos al consultarlos y solo incorpora la interfaz cuando la
   prueba llama a insertarSala(). Los contadores observan efectos efectivos,
   no la presencia textual de nombres o funciones en sala.js. */
function crearEscenarioContrato(interfazSala) {
  const nodos = {};
  const metricas = {
    listeners: 0,
    observadores: 0,
    sockets: [],
    peticiones: [],
    temporizadores: [],
    redirecciones: [],
  };
  let siguienteTemporizadorContrato = 1;
  let raizSala = null;

  function nodoContrato(tag, id = null) {
    const nodo = tag === "canvas" ? new CanvasMontaje() : elemento(tag);
    const agregarOriginal = nodo.addEventListener.bind(nodo);
    nodo.addEventListener = (tipo, fn) => {
      metricas.listeners += 1;
      agregarOriginal(tipo, fn);
    };
    nodo.removeEventListener = (tipo, fn) => {
      const lista = nodo._oyentes[tipo] || [];
      nodo._oyentes[tipo] = lista.filter((oyente) => oyente !== fn);
    };
    nodo.querySelector = (selector) => {
      if (selector === '[role="dialog"]') return elemento("div");
      if (selector.startsWith("#")) return nodos[selector.slice(1)] || null;
      return null;
    };
    nodo.querySelectorAll = (selector) => {
      if (selector === ".modal") {
        return Object.entries(nodos)
          .filter(([clave]) => clave.startsWith("modal-"))
          .map(([, modal]) => modal);
      }
      return [];
    };
    nodo.ownerDocument = null;
    if (id) nodos[id] = nodo;
    return nodo;
  }

  const body = nodoContrato("body");
  const documentElement = nodoContrato("html");
  const documentStubContrato = {
    body,
    documentElement,
    activeElement: null,
    readyState: "complete",
    _oyentes: {},
    getElementById(id) { return nodos[id] || null; },
    createElement(tag) { return nodoContrato(tag); },
    createElementNS(_ns, tag) { return nodoContrato(tag); },
    addEventListener(tipo, fn) {
      metricas.listeners += 1;
      (this._oyentes[tipo] ||= []).push(fn);
    },
    removeEventListener(tipo, fn) {
      const lista = this._oyentes[tipo] || [];
      this._oyentes[tipo] = lista.filter((oyente) => oyente !== fn);
    },
    querySelector(selector) {
      if (selector === ".interfaz-sala") return raizSala;
      if (selector.startsWith("#")) return nodos[selector.slice(1)] || null;
      return null;
    },
    querySelectorAll(selector) {
      if (selector === ".modal") {
        return Object.entries(nodos)
          .filter(([clave]) => clave.startsWith("modal-"))
          .map(([, modal]) => modal);
      }
      return [];
    },
  };
  body.ownerDocument = documentStubContrato;
  documentElement.ownerDocument = documentStubContrato;

  const ubicacion = { protocol: "http:", host: "localhost:8000" };
  let href = "http://localhost:8000/";
  Object.defineProperty(ubicacion, "href", {
    get() { return href; },
    set(valor) {
      href = String(valor);
      metricas.redirecciones.push(href);
    },
  });

  class WebSocketContrato {
    constructor(url) {
      this.url = url;
      this.readyState = 1;
      metricas.sockets.push(this);
    }
    send() {}
    close() { this.readyState = 3; }
  }
  WebSocketContrato.OPEN = 1;
  WebSocketContrato.CLOSED = 3;

  class ObservadorContrato {
    constructor(callback) {
      this.callback = callback;
      this.desconectado = false;
      metricas.observadores += 1;
    }
    observe() {}
    disconnect() { this.desconectado = true; }
  }

  const visualViewport = {
    width: 1280, height: 720, offsetLeft: 0, offsetTop: 0, _oyentes: {},
    addEventListener(tipo, fn) {
      metricas.listeners += 1;
      (this._oyentes[tipo] ||= []).push(fn);
    },
    removeEventListener(tipo, fn) {
      const lista = this._oyentes[tipo] || [];
      this._oyentes[tipo] = lista.filter((oyente) => oyente !== fn);
    },
  };

  const contexto = {
    console,
    document: documentStubContrato,
    location: ubicacion,
    visualViewport,
    innerWidth: 1280,
    innerHeight: 720,
    screen: { width: 1280, height: 720 },
    devicePixelRatio: 1,
    Image: ImagenMontaje,
    navigator: { maxTouchPoints: 0 },
    sessionStorage: {
      getItem(clave) { return clave === "jugador_id" ? "jug-contrato" : null; },
      setItem() {},
      removeItem() {},
    },
    fetch(url, opciones) {
      metricas.peticiones.push({ url, opciones });
      if (url === "/api/tablero") {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ tablero: descriptor }) });
      }
      if (url === "/api/recursos") {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ recursos: {} }) });
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => ({ personajes: [] }) });
    },
    WebSocket: WebSocketContrato,
    MutationObserver: ObservadorContrato,
    ResizeObserver: class { observe() {} disconnect() {} },
    Set,
    Map,
    URL,
    Blob,
    _oyentes: {},
    addEventListener(tipo, fn) {
      metricas.listeners += 1;
      (this._oyentes[tipo] ||= []).push(fn);
    },
    removeEventListener(tipo, fn) {
      const lista = this._oyentes[tipo] || [];
      this._oyentes[tipo] = lista.filter((oyente) => oyente !== fn);
    },
    setTimeout(fn, ms) {
      const registroTemporizador = {
        id: siguienteTemporizadorContrato++, fn, ms, activo: true,
      };
      metricas.temporizadores.push(registroTemporizador);
      return registroTemporizador.id;
    },
    clearTimeout(id) {
      const registroTemporizador = metricas.temporizadores.find((item) => item.id === id);
      if (registroTemporizador) registroTemporizador.activo = false;
    },
  };
  contexto.window = contexto;
  contexto.globalThis = contexto;
  contexto.matchMedia = () => ({ matches: false });
  vm.createContext(contexto);

  function insertarSala() {
    for (const coincidencia of interfazSala.matchAll(/id="([^"]+)"/g)) {
      const id = coincidencia[1];
      if (!nodos[id]) nodoContrato(id === "tablero-canvas" ? "canvas" : "div", id);
    }
    for (const id of [
      "modal-preparacion-movil",
      "btn-entrar-pantalla-completa",
      "preparacion-movil-nota",
    ]) {
      if (!nodos[id]) nodoContrato("div", id);
    }
    nodos.codigo.textContent = "JARA-CONTRATO";
    raizSala = nodoContrato("main");
    raizSala.className = "contenedor lobby-contenedor interfaz-sala";
    raizSala.ownerDocument = documentStubContrato;
    return raizSala;
  }

  function servicioSala() {
    return contexto.SalaJuego || contexto.window.SalaJuego || null;
  }

  function peticionesSala() {
    return metricas.peticiones.filter(({ url }) =>
      url === "/api/personajes" || url === "/api/recursos" || url === "/api/tablero"
    );
  }

  return {
    contexto,
    metricas,
    insertarSala,
    servicioSala,
    peticionesSala,
  };
}

async function comprobarContratoSalaJuego(fuenteSala, interfazSala) {
  console.log("\nCONTRATO FUTURO DE MONTAJE SALAJUEGO");

  const portada = crearEscenarioContrato(interfazSala);
  let errorCargaPortada = null;
  try {
    vm.runInContext(fuenteSala, portada.contexto, {
      filename: "sala-contrato-portada.js",
    });
    await Promise.resolve();
    await Promise.resolve();
  } catch (error) {
    errorCargaPortada = error;
  }
  const detalleCarga = errorCargaPortada
    ? `la evaluacion aborta: ${errorCargaPortada.name}: ${errorCargaPortada.message}`
    : "SalaJuego todavia no esta publicado";
  contrato(
    errorCargaPortada === null,
    "cargar sala.js sin HTML de sala no provoca excepciones",
    detalleCarga
  );
  contrato(
    errorCargaPortada === null && portada.metricas.redirecciones.length === 0,
    "la portada no se redirige al evaluar el controlador de sala",
    detalleCarga
  );
  contrato(
    errorCargaPortada === null && portada.metricas.sockets.length === 0,
    "la carga sin interfaz no abre WebSockets",
    detalleCarga
  );
  contrato(
    errorCargaPortada === null && portada.peticionesSala().length === 0,
    "la carga sin interfaz no solicita recursos propios de sala",
    detalleCarga
  );
  contrato(
    errorCargaPortada === null && portada.metricas.listeners === 0,
    "la carga sin interfaz no registra listeners propios de sala",
    detalleCarga
  );
  contrato(
    errorCargaPortada === null &&
      portada.servicioSala() &&
      typeof portada.servicioSala().montar === "function",
    "la evaluacion deja disponible SalaJuego.montar()",
    detalleCarga
  );

  const raizMontaje = portada.insertarSala();
  const servicio = portada.servicioSala();
  const antesMontaje = {
    sockets: portada.metricas.sockets.length,
    observadores: portada.metricas.observadores,
    peticiones: portada.peticionesSala().length,
    listeners: portada.metricas.listeners,
    temporizadores: portada.metricas.temporizadores.filter((item) => item.activo).length,
  };
  let errorMontaje = null;
  if (servicio && typeof servicio.montar === "function") {
    try {
      await servicio.montar({
        codigo: "JARA-CONTRATO",
        jugadorId: "jug-contrato",
        raiz: raizMontaje,
        cambioInterno: true,
      });
      await Promise.resolve();
      await Promise.resolve();
    } catch (error) {
      errorMontaje = error;
    }
  }
  const motivoSinServicio = errorMontaje
    ? `montar() falla: ${errorMontaje.name}: ${errorMontaje.message}`
    : "SalaJuego.montar() no existe todavia";
  const peticionesTrasMontaje = portada.peticionesSala();
  const cantidadesPorRuta = peticionesTrasMontaje.reduce((cantidades, { url }) => {
    cantidades[url] = (cantidades[url] || 0) + 1;
    return cantidades;
  }, {});
  const recursosSinDuplicar = ["/api/personajes", "/api/recursos", "/api/tablero"]
    .every((url) => cantidadesPorRuta[url] === 1);
  contrato(
    Boolean(servicio) && errorMontaje === null &&
      portada.metricas.sockets.length === antesMontaje.sockets + 1,
    "el montaje diferido abre exactamente un WebSocket",
    motivoSinServicio
  );
  contrato(
    Boolean(servicio) && errorMontaje === null &&
      portada.metricas.observadores === antesMontaje.observadores + 1,
    "el montaje diferido registra exactamente un observador de sala",
    motivoSinServicio
  );
  contrato(
    Boolean(servicio) && errorMontaje === null &&
      peticionesTrasMontaje.length > antesMontaje.peticiones && recursosSinDuplicar,
    "el montaje carga una sola vez cada recurso necesario",
    motivoSinServicio
  );
  contrato(
    Boolean(servicio) && errorMontaje === null &&
      portada.metricas.listeners > antesMontaje.listeners,
    "el montaje asocia los listeners despues de existir la interfaz",
    motivoSinServicio
  );

  const trasPrimerMontaje = {
    sockets: portada.metricas.sockets.length,
    observadores: portada.metricas.observadores,
    peticiones: portada.peticionesSala().length,
    listeners: portada.metricas.listeners,
    temporizadores: portada.metricas.temporizadores.filter((item) => item.activo).length,
  };
  let errorRepeticionMontaje = null;
  if (servicio && typeof servicio.montar === "function") {
    try {
      await servicio.montar({
        codigo: "JARA-CONTRATO", jugadorId: "jug-contrato",
        raiz: raizMontaje, cambioInterno: true,
      });
      await servicio.montar({
        codigo: "JARA-CONTRATO", jugadorId: "jug-contrato",
        raiz: raizMontaje, cambioInterno: true,
      });
    } catch (error) {
      errorRepeticionMontaje = error;
    }
  }
  const montajeIdempotente = Boolean(servicio) && errorMontaje === null &&
    errorRepeticionMontaje === null &&
    portada.metricas.sockets.length === trasPrimerMontaje.sockets &&
    portada.metricas.observadores === trasPrimerMontaje.observadores &&
    portada.peticionesSala().length === trasPrimerMontaje.peticiones &&
    portada.metricas.listeners === trasPrimerMontaje.listeners &&
    portada.metricas.temporizadores.filter((item) => item.activo).length ===
      trasPrimerMontaje.temporizadores;
  contrato(
    montajeIdempotente,
    "montar dos veces la misma sala no duplica recursos",
    errorRepeticionMontaje
      ? `la repeticion falla: ${errorRepeticionMontaje.name}: ${errorRepeticionMontaje.message}`
      : motivoSinServicio
  );

  const directa = crearEscenarioContrato(interfazSala);
  directa.insertarSala();
  let errorEntradaDirecta = null;
  try {
    vm.runInContext(fuenteSala, directa.contexto, {
      filename: "sala-contrato-directa.js",
    });
    await Promise.resolve();
    await Promise.resolve();
  } catch (error) {
    errorEntradaDirecta = error;
  }
  const servicioDirecto = directa.servicioSala();
  contrato(
    errorEntradaDirecta === null && Boolean(servicioDirecto) &&
      directa.metricas.sockets.length === 1 &&
      directa.metricas.sockets[0].url ===
        "ws://localhost:8000/ws/JARA-CONTRATO/jug-contrato",
    "la entrada directa monta automaticamente con codigo e identidad existentes",
    errorEntradaDirecta
      ? `el arranque directo falla: ${errorEntradaDirecta.name}: ${errorEntradaDirecta.message}`
      : "la entrada directa actual conecta, pero no expone el servicio SalaJuego"
  );

  const socketsAntesDeRecarga = directa.metricas.sockets.length;
  const observadoresAntesDeRecarga = directa.metricas.observadores;
  const peticionesAntesDeRecarga = directa.peticionesSala().length;
  const listenersAntesDeRecarga = directa.metricas.listeners;
  const servicioAntesDeRecarga = servicioDirecto;
  let errorCargaDuplicada = null;
  try {
    vm.runInContext(fuenteSala, directa.contexto, {
      filename: "sala-contrato-carga-duplicada.js",
    });
    await Promise.resolve();
    await Promise.resolve();
  } catch (error) {
    errorCargaDuplicada = error;
  }
  contrato(
    errorCargaDuplicada === null && servicioAntesDeRecarga &&
      directa.servicioSala() === servicioAntesDeRecarga &&
      directa.metricas.sockets.length === socketsAntesDeRecarga &&
      directa.metricas.observadores === observadoresAntesDeRecarga &&
      directa.peticionesSala().length === peticionesAntesDeRecarga &&
      directa.metricas.listeners === listenersAntesDeRecarga,
    "una carga accidental duplicada conserva una sola instancia y sus recursos",
    errorCargaDuplicada
      ? `la segunda evaluacion lanza ${errorCargaDuplicada.name}: ${errorCargaDuplicada.message}`
      : "SalaJuego no conserva todavia una instancia compartida verificable"
  );
}

let resolverTablero;
let socket;
let sincronizarBarra;
let socketsCreados = 0;
let observadoresMutacionCreados = 0;
let observadoresTamanoCreados = 0;
const enviados = [];
const peticionesFetch = [];
const temporizadores = [];
let siguienteTemporizador = 1;
function programarTemporizador(fn, ms) {
  const registro = { id: siguienteTemporizador++, fn, ms, activo: true };
  temporizadores.push(registro);
  return registro.id;
}
function cancelarTemporizador(id) {
  const registro = temporizadores.find((item) => item.id === id);
  if (registro) registro.activo = false;
}
function ejecutarSiguienteTemporizador() {
  const registro = temporizadores.find((item) => item.activo);
  if (!registro) return false;
  registro.activo = false;
  registro.fn();
  return true;
}
function temporizadoresPendientes() {
  return temporizadores.filter((item) => item.activo).length;
}
class WebSocketFalso {
  constructor(url) { socket = this; this.url = url; socketsCreados += 1; }
  send(mensaje) { enviados.push(JSON.parse(mensaje)); }
}
WebSocketFalso.OPEN = 1;
const fetchFalso = (url, opciones) => {
  peticionesFetch.push({ url, opciones });
  if (typeof url === "string" && url.startsWith("/api/tablero")) {
    return new Promise((resolve) => { resolverTablero = () => resolve({ ok: true, status: 200, json: async () => ({ tablero: descriptor }) }); });
  }
  return Promise.resolve({ ok: true, status: 200, json: async () => ({ personajes: [] }) });
};

const sandbox = {
  console, document: documentStub,
  window: {
    location: { protocol: "http:", host: "localhost:8000" },
    devicePixelRatio: 2,
    Image: ImagenMontaje,
    ResizeObserver: class {
      constructor(fn) { this.fn = fn; observadoresTamanoCreados += 1; }
      observe() {}
    },
    _oyentes: {},
    addEventListener(tipo, fn) { (this._oyentes[tipo] ||= []).push(fn); },
    setTimeout: programarTemporizador,
    clearTimeout: cancelarTemporizador,
  },
  sessionStorage: { getItem: () => "jug-real", setItem() {} },
  fetch: fetchFalso, WebSocket: WebSocketFalso, Set, Map,
  MutationObserver: class {
    constructor(callback) {
      sincronizarBarra = callback;
      observadoresMutacionCreados += 1;
    }
    observe() {}
  },
};
vm.createContext(sandbox);

(async () => {
  const raiz = path.join(__dirname, "..");
  const documentoSala = fs.readFileSync(
    path.join(raiz, "app", "templates", "sala.html"),
    "utf8"
  );
  const interfazSala = fs.readFileSync(
    path.join(raiz, "app", "templates", "_sala_interfaz.html"),
    "utf8"
  );
  const html = documentoSala.replace(
    '{% include "_sala_interfaz.html" %}',
    interfazSala
  );
  ok(html.includes('id="tablero-visual"'), "sala.html contiene el contenedor real");
  ok(html.includes('/static/js/tablero_canvas.js?v=8b8b'),
    "la plantilla invalida la caché del renderer Canvas animado");
  ok(html.includes('/static/js/sala.js?v=admin10'),
    "la plantilla invalida la caché tras recuperar la geometría estable");
  ok(html.includes('/static/css/estilos.css?v=chat1'),
    "la plantilla invalida la caché de la barra inferior");
  ok(
    (CSS.match(/@media \(min-width: 768px\)/g) || []).length === 3,
    "cuadrícula, panel y altura del tablero comparten el breakpoint de 768 px"
  );
  ok(
    !CSS.includes("--lado-tablero-ventana") &&
      !/modo-tablero-activo \.tarjeta\s*\{[^}]*container-type:\s*size/.test(CSS) &&
      !/modo-tablero-activo #partida\s*\{[^}]*container-type:\s*size/.test(CSS),
    "el tablero no depende de una cadena circular de contenedores de tamaño"
  );
  ok(
    CSS.includes("grid-template-rows: minmax(0, 1fr) auto") &&
      CSS.includes("grid-row: 2"),
    "el registro ocupa una fila explícita y no altera la altura de la fila del tablero"
  );
  ok(
    CSS.includes("max-width: none") &&
      CSS.includes("width: min(100cqw, 100cqh)") &&
      CSS.includes("height: min(100cqw, 100cqh)") &&
      CSS.includes("margin: auto"),
    "el tablero ocupa el mayor cuadrado entre ancho y alto disponibles y queda centrado"
  );
  ok(
    CSS.includes("height: calc(100% + 16px)") &&
      CSS.includes(".tarjeta:fullscreen .tablero-visual") &&
      CSS.includes("height: 100%"),
    "la ventana recupera el padding del marco y pantalla completa conserva su altura estable"
  );
  ok(
    CSS.includes("body.modo-tablero-activo #zona-juego") &&
      CSS.includes("row-gap: 0") &&
      CSS.includes("padding-bottom: 10px"),
    "en escritorio se aprovecha la fila sin registro y no se reserva bajo el tablero el espacio de la barra lateral"
  );
  ok(
    CSS.includes("min-height: 320px") &&
      CSS.includes("padding-bottom: 64px") &&
      !/body\.en-partida\s*\{[^}]*overflow:\s*hidden/s.test(CSS),
    "se reserva la barra, se conserva un mínimo legible y se permite scroll si falta altura"
  );
  ok(html.includes('/static/js/audio.js?v=8b33c'),
    "la plantilla invalida la caché del control de música compartido");
  ok(html.includes('/static/js/pantalla_completa.js?v=8b19b'),
    "la plantilla incluye el control global de pantalla completa");
  ok(html.includes('id="barra-controles-inferior"') &&
      html.includes('id="btn-configuracion-partida"') &&
      html.includes('id="btn-aprender-sala"'),
    "la barra común contiene la configuración y la ayuda reutilizada");
  ok(!html.includes('id="tablero-superficie"') && !html.includes('id="tablero-nodos"'),
    "la plantilla ya no contiene el renderer HTML/SVG descartado");

  sandbox.window.window = sandbox.window;
  vm.runInContext(fs.readFileSync(path.join(raiz, "app", "static", "js", "tablero_canvas.js"), "utf8"), sandbox, { filename: "tablero_canvas.js" });
  const fuenteSala = fs.readFileSync(path.join(raiz, "app", "static", "js", "sala.js"), "utf8");
  vm.runInContext(fuenteSala, sandbox, { filename: "sala.js" });
  ok(typeof sandbox.inicializarSala === "function",
    "sala.js expone el inicializador explícito");
  ok(socketsCreados === 1, "el arranque de sala crea exactamente un WebSocket");
  const solicitudesTableroIniciales = peticionesFetch.filter(
    (peticion) => typeof peticion.url === "string" && peticion.url.startsWith("/api/tablero")
  ).length;
  ok(solicitudesTableroIniciales === 1,
    "la primera inicialización solicita una vez el descriptor del tablero");
  ok(socket.url === "ws://localhost:8000/ws/JARA-REAL/jug-real",
    "el WebSocket usa una sola identidad de sala y jugador");
  ok(observadoresMutacionCreados === 1,
    "el arranque instala un solo observador de visibilidad de controles");
  sandbox.inicializarSala();
  sandbox.inicializarSala();
  const solicitudesTableroTrasReentrada = peticionesFetch.filter(
    (peticion) => typeof peticion.url === "string" && peticion.url.startsWith("/api/tablero")
  ).length;
  ok(socketsCreados === 1,
    "dos llamadas adicionales no crean WebSockets duplicados");
  ok(observadoresMutacionCreados === 1,
    "dos llamadas adicionales no duplican observadores");
  ok(solicitudesTableroTrasReentrada === solicitudesTableroIniciales,
    "dos llamadas adicionales no repiten la petición del descriptor");
  const oyentesDocumentoIniciales = Object.values(documentStub._oyentes)
    .reduce((total, lista) => total + lista.length, 0);
  const oyentesVentanaIniciales = Object.values(sandbox.window._oyentes)
    .reduce((total, lista) => total + lista.length, 0);
  ok(oyentesDocumentoIniciales > 0 && oyentesVentanaIniciales > 0,
    "el harness contabiliza los eventos globales instalados por la sala");
  let errorReentrada = null;
  try {
    vm.runInContext(fuenteSala, sandbox, { filename: "sala-segunda-ejecucion.js" });
  } catch (error) {
    errorReentrada = error;
  }
  riesgo(
    errorReentrada === null,
    "sala.js puede inicializarse dos veces sin colisionar ni duplicar recursos"
  );
  ok(socketsCreados === 1,
    "una segunda evaluacion fallida no alcanza a abrir otro WebSocket");
  ok(registro["barra-controles-inferior"].hidden === true,
    "el lobby mantiene la barra oculta");
  const jugadores = personajes.map((id, i) => ({
    alias: `Jugador ${i + 1}`, personaje_id: id, personaje: id,
    tipo: i ? "pnj" : "humano", activo: i !== 5, num_cartas: 3,
    posicion: { id: ubicaciones[i], nombre: ubicaciones[i], tipo: "ubicacion" },
  }));
  const sala = {
    codigo: "JARA-REAL", modo: "tablero", estado: "iniciada", alias: "Jugador 1",
    es_anfitrion: true, personaje_id: "vera", personaje: "vera", jugadores,
    orden: jugadores.map((j) => ({ alias: j.alias, personaje: j.personaje, tipo: j.tipo, activo: j.activo })),
    turno_alias: "Jugador 1", turno_tipo: "humano", pnj_pensando_alias: null,
    es_mi_turno: true, activo_investigacion: true, mis_cartas: [], investigacion: [],
    jugada: { estado: "esperando_movimiento" },
    movimiento_resuelto: {
      movimiento_id: 40, personaje_id: "vera", origen_id: "picota",
      destino_id: "parador", recorrido: ["parador"], tipo: "normal",
    },
    posicion: jugadores[0].posicion,
    movimiento: { fase: "esperando_movimiento", puede_tirar: true, tirada: null, destinos: [] },
    resultado_final: null, ganador_alias: null,
  };

  socket.onmessage({ data: JSON.stringify({ tipo: "estado_privado", sala }) });
  ok(registro["tablero-visual"].hidden === false, "el estado WS real de modo tablero muestra el contenedor");
  const idsMapaPantalla = [
    "bloque-codigo", "lobby-personajes", "btn-comenzar", "partida",
    "bloque-orden", "total", "resumen-sala", "tablero-visual",
    "admin-pausa-aviso",
  ];
  const visible = (id) => id === "lobby-personajes" || id === "btn-comenzar"
    ? registro[id].style.display !== "none"
    : !registro[id].hidden;
  ok(registro.partida.hidden === false && registro["resumen-sala"].hidden === false &&
      visible("tablero-visual") && registro["lobby-personajes"].style.display === "none" &&
      registro["btn-comenzar"].style.display === "none",
    "el estado iniciado conserva tablero y resumen y oculta las zonas de selección");

  sandbox.pintarSala({ ...sala, estado: "esperando", pausada: false });
  ok(registro["bloque-codigo"].hidden === false &&
      registro["lobby-personajes"].style.display !== "none" &&
      registro["btn-comenzar"].style.display !== "none" &&
      registro.partida.hidden === true && registro["bloque-orden"].hidden === false &&
      registro.total.hidden === false && registro["resumen-sala"].hidden === true,
    "selección de personaje muestra sus zonas y oculta la partida, incluido su tablero");

  sandbox.pintarSala(sala);
  sandbox.pintarSala({ ...sala, pausada: true });
  ok(registro.partida.hidden === false && registro["tablero-visual"].hidden === false &&
      registro["admin-pausa-aviso"].hidden === false &&
      documentStub.body.classList.contains("partida-en-pausa"),
    "la pausa conserva el tablero y aplica el aviso y la clase de pausa");
  sandbox.pintarSala(sala);
  ok(registro["admin-pausa-aviso"].hidden === true &&
      !documentStub.body.classList.contains("partida-en-pausa") &&
      registro.partida.hidden === false && registro["tablero-visual"].hidden === false,
    "reanudar retira el aviso y la clase y conserva el tablero");

  sandbox.pintarSala({ ...sala, estado: "terminada" });
  ok(registro.partida.hidden === false && registro["tablero-visual"].hidden === false &&
      registro["resumen-sala"].hidden === false,
    "la partida terminada conserva la vista general para presentar el diálogo final");
  sandbox.pintarSala({ ...sala, estado: "estado-desconocido", pausada: false });
  ok(registro.partida.hidden === true && registro["lobby-personajes"].style.display !== "none" &&
      !documentStub.body.classList.contains("en-partida"),
    "un estado desconocido sigue la misma vista de selección que la rama de lobby");
  sandbox.pintarSala(sala);

  const escriturasMapa = {};
  for (const id of idsMapaPantalla) {
    const nodo = registro[id];
    if (!nodo) continue;
    let oculto = nodo.hidden;
    Object.defineProperty(nodo, "hidden", {
      configurable: true,
      get() { return oculto; },
      set(valor) { escriturasMapa[id] = (escriturasMapa[id] || 0) + 1; oculto = valor; },
    });
    if (id === "lobby-personajes" || id === "btn-comenzar") {
      let display = nodo.style.display;
      Object.defineProperty(nodo.style, "display", {
        configurable: true,
        get() { return display; },
        set(valor) { escriturasMapa[id] = (escriturasMapa[id] || 0) + 1; display = valor; },
      });
    }
  }
  vm.runInContext('aplicarPantallaInterfaz("partida")', sandbox);
  for (const id of Object.keys(escriturasMapa)) escriturasMapa[id] = 0;
  vm.runInContext('aplicarPantallaInterfaz("partida")', sandbox);
  ok(Object.values(escriturasMapa).every((cantidad) => cantidad === 0),
    "reaplicar la misma pantalla no vuelve a escribir estados ya aplicados");

  const zonaPartidaAnterior = registro.partida;
  zonaPartidaAnterior.hidden = true;
  registro.partida = elemento("div");
  vm.runInContext('aplicarPantallaInterfaz("partida")', sandbox);
  ok(registro.partida !== zonaPartidaAnterior && registro.partida.hidden === false &&
      zonaPartidaAnterior.hidden === true,
    "el mapa vuelve a resolver por ID y no conserva el nodo sustituido");
  const getElementByIdOriginal = documentStub.getElementById;
  documentStub.getElementById = (id) => id === "admin-pausa-aviso"
    ? null : getElementByIdOriginal.call(documentStub, id);
  let errorElementoOpcional = null;
  try {
    vm.runInContext('aplicarPantallaInterfaz("partidaPausada")', sandbox);
  } catch (errorDeElemento) {
    errorElementoOpcional = errorDeElemento;
  } finally {
    documentStub.getElementById = getElementByIdOriginal;
  }
  ok(errorElementoOpcional === null,
    "un elemento opcional ausente no interrumpe la aplicación del mapa");

  vm.runInContext('aplicarPantallaInterfaz("partida")', sandbox);
  const zonasAntesDeModal = idsMapaPantalla.map((id) => [
    id, registro[id] && registro[id].hidden, registro[id] && registro[id].style.display,
  ]);
  const pausaAntesDeModal = documentStub.body.classList.contains("partida-en-pausa");
  registro["modal-aprender"].hidden = false;
  registro["modal-chat"].hidden = false;
  sincronizarBarra();
  registro["modal-aprender"].hidden = true;
  registro["modal-chat"].hidden = true;
  sincronizarBarra();
  ok(JSON.stringify(zonasAntesDeModal) === JSON.stringify(idsMapaPantalla.map((id) => [
      id, registro[id] && registro[id].hidden, registro[id] && registro[id].style.display,
    ])) && documentStub.body.classList.contains("partida-en-pausa") === pausaAntesDeModal,
    "abrir y cerrar ayuda o chat no modifica el estado base de pantalla");

  sincronizarBarra();
  ok(registro["barra-controles-inferior"].hidden === false,
    "la barra aparece en el tablero principal del anfitrión");
  ok(registro["btn-configuracion-partida"].hidden === false,
    "el anfitrión ve la configuración en la barra");
  ok(vm.runInContext("rendererCanvas", sandbox) === null, "la carrera se reproduce: el estado puede llegar antes del descriptor");
  const temporizadoresTrasPrimerEstado = temporizadoresPendientes();
  socket.onmessage({ data: JSON.stringify({ tipo: "estado_privado", sala }) });
  ok(temporizadoresPendientes() === temporizadoresTrasPrimerEstado,
    "repetir el mismo estado no programa una animacion de movimiento duplicada");

  registro["modal-aprender"].hidden = false;
  sincronizarBarra();
  ok(registro["barra-controles-inferior"].hidden === true,
    "abrir Cómo jugar oculta la barra y la saca del orden de tabulación");
  registro["modal-aprender"].hidden = true;
  sincronizarBarra();
  ok(registro["barra-controles-inferior"].hidden === false,
    "cerrar Cómo jugar restaura la barra");

  for (const id of [
    "modal-configuracion-partida",
    "modal-confirmar-resolver",
    "modal-resolucion-fallida",
    "modal-presentacion-sospecha",
    "modal-revelacion-refutacion",
    "modal-sospecha",
    "modal-refutacion",
    "modal-cartas",
    "modal-ubicacion",
    "modal-hoja",
    "modal-inactividad",
    "modal-historial",
    "modal-resolver",
    "modal-victoria",
  ]) {
    const modal = registro[id];
    modal.hidden = false;
    sincronizarBarra();
    ok(registro["barra-controles-inferior"].hidden === true,
      `${id} oculta la barra`);
    modal.hidden = true;
    sincronizarBarra();
    ok(registro["barra-controles-inferior"].hidden === false,
      `cerrar ${id} restaura la barra`);
  }

  sala.es_anfitrion = false;
  socket.onmessage({ data: JSON.stringify({ tipo: "estado_privado", sala }) });
  sincronizarBarra();
  ok(registro["barra-controles-inferior"].hidden === false &&
    registro["btn-configuracion-partida"].hidden === true,
  "el invitado ve la barra, pero no el acceso de configuración");
  sala.es_anfitrion = true;
  socket.onmessage({ data: JSON.stringify({ tipo: "estado_privado", sala }) });
  sincronizarBarra();

  resolverTablero();
  await new Promise((resolve) => setImmediate(resolve));
  ok(observadoresTamanoCreados === 1,
    "el tablero crea un solo observador de tamano");
  const rendererInicial = vm.runInContext("rendererCanvas", sandbox);
  let actualizacionesDuplicadas = 0;
  const actualizarReal = rendererInicial.actualizar.bind(rendererInicial);
  rendererInicial.actualizar = (...argumentos) => {
    actualizacionesDuplicadas += 1;
    return actualizarReal(...argumentos);
  };
  const temporizadoresAntesDeDuplicado = temporizadoresPendientes();
  socket.onmessage({ data: JSON.stringify({ tipo: "estado_privado", sala }) });
  ok(vm.runInContext("rendererCanvas", sandbox) === rendererInicial,
    "un estado repetido reutiliza el renderer Canvas existente");
  ok(temporizadoresPendientes() === temporizadoresAntesDeDuplicado,
    "un estado repetido no duplica temporizadores tras montar el Canvas");
  riesgo(actualizacionesDuplicadas === 0,
    "un estado privado identico evita un repintado Canvas innecesario");
  await new Promise((resolve) => setImmediate(resolve));
  ok(registro["tablero-visual"].hidden === false, "el contenedor permanece visible tras cargar descriptor");
  ok(
    peticionesFetch.some((p) => typeof p.url === "string" && p.url.startsWith("/api/tablero")),
    "se solicita el descriptor visual al montar"
  );
  ok(registro["tablero-canvas-contenedor"].hidden === false, "sala.js activa Canvas en navegador compatible");
  const metricas = vm.runInContext("rendererCanvas.metricas", sandbox);
  ok(metricas.ubicaciones === 9 && metricas.casillas === 48, "Canvas monta 9 ubicaciones y 48 casillas");
  ok(metricas.caminos === 16 && metricas.pasadizos === 2, "Canvas monta 16 caminos y 2 pasadizos");
  ok(metricas.peones === 6 && metricas.dpr === 2, "Canvas monta 6 peones con escala HiDPI");
  ok(personajes.every((id) => metricas.representacionesPeones.some((p) =>
    p.personaje_id === id && p.drawSolicitado && p.drawEjecutado)),
  "el montaje integrado identifica y representa individualmente los seis personajes");
  const posicionVisual = (personajeId) => vm.runInContext(
    `rendererCanvas.metricas.representacionesPeones.find((p) => p.personaje_id === ${JSON.stringify(personajeId)}).posicion`,
    sandbox
  );
  const enviarMovimiento = (movimiento, personajeId = movimiento.personaje_id) => {
    const jugador = sala.jugadores.find((item) => item.personaje_id === personajeId);
    jugador.posicion = { id: movimiento.destino_id, nombre: movimiento.destino_id, tipo: "casilla" };
    if (personajeId === sala.personaje_id) sala.posicion = jugador.posicion;
    sala.movimiento_resuelto = movimiento;
    socket.onmessage({ data: JSON.stringify({ tipo: "estado_privado", sala }) });
  };
  const observarMovimiento = (movimiento) => {
    enviarMovimiento(movimiento);
    const observadas = [posicionVisual(movimiento.personaje_id)];
    while (ejecutarSiguienteTemporizador()) observadas.push(posicionVisual(movimiento.personaje_id));
    return observadas;
  };
  ok(posicionVisual("vera") === "parador" && temporizadoresPendientes() === 0,
    "la primera hidrataciÃ³n muestra el estado lÃ³gico sin animar el movimiento histÃ³rico");
  ok(registro["modal-ubicacion"].hidden === true,
    "recargar dentro de una ubicación no abre el popup histórico");

  socket.onmessage({ data: JSON.stringify({ tipo: "estado_privado", sala }) });
  ok(registro["modal-ubicacion"].hidden === true,
    "iniciar o actualizar el turno dentro de una ubicación no abre el popup");

  const paso1 = caminos[0].nodos[1];
  const paso2 = caminos[0].nodos[2];
  const paso3 = caminos[0].nodos[3];
  let observadas = observarMovimiento({
    movimiento_id: 41, personaje_id: "vera", origen_id: "parador",
    destino_id: paso1, recorrido: [paso1], tipo: "normal",
  });
  ok(JSON.stringify(observadas.slice(0, 2)) === JSON.stringify(["parador", paso1]),
    "un recorrido de un paso se presenta primero en origen y despuÃ©s en el nodo intermedio");
  ok(registro["modal-ubicacion"].hidden === true,
    "un movimiento humano a nodo intermedio no abre popup");

  observadas = observarMovimiento({
    movimiento_id: 42, personaje_id: "vera", origen_id: paso1,
    destino_id: paso3, recorrido: [paso2, paso3], tipo: "normal",
  });
  ok(JSON.stringify(observadas.slice(0, 3)) === JSON.stringify([paso1, paso2, paso3]),
    "un recorrido de dos pasos respeta exactamente el orden canÃ³nico");

  const movimientoLlegada = {
    movimiento_id: 43, personaje_id: "vera", origen_id: paso3,
    destino_id: "iglesia-san-agustin", recorrido: [paso2, paso1, "iglesia-san-agustin"], tipo: "normal",
  };
  enviarMovimiento(movimientoLlegada);
  ok(registro["modal-ubicacion"].hidden === true,
    "la llegada humana no abre el popup antes de terminar la animación");
  observadas = [posicionVisual(movimientoLlegada.personaje_id)];
  while (ejecutarSiguienteTemporizador()) observadas.push(posicionVisual(movimientoLlegada.personaje_id));
  ok(JSON.stringify(observadas.slice(0, 4)) === JSON.stringify([paso3, paso2, paso1, "iglesia-san-agustin"]),
    "el flujo parte de un nodo intermedio y completa literalmente el recorrido hasta una ubicaciÃ³n");
  ok(registro["modal-ubicacion"].hidden === false &&
    registro["modal-contextual-titulo"].textContent === "iglesia-san-agustin",
  "la llegada humana abre el popup existente después de terminar la animación");
  const estadoTrasLlegada = JSON.stringify(sala.movimiento_resuelto);
  registro["btn-cerrar-ubicacion"].click();
  ok(registro["modal-ubicacion"].hidden === true &&
    JSON.stringify(sala.movimiento_resuelto) === estadoTrasLlegada,
  "cerrar el popup vuelve al tablero sin alterar el estado");

  const temporizadoresAntes = temporizadoresPendientes();
  enviarMovimiento(sala.movimiento_resuelto);
  ok(temporizadoresPendientes() === temporizadoresAntes && posicionVisual("vera") === "iglesia-san-agustin",
    "un movimiento_id repetido no vuelve a animarse");

  enviarMovimiento({
    movimiento_id: 44, personaje_id: "vera", origen_id: "iglesia-san-agustin",
    destino_id: "nuestra-senora-torre", recorrido: ["nuestra-senora-torre"], tipo: "pasadizo",
  });
  ok(posicionVisual("vera") === "nuestra-senora-torre" && temporizadoresPendientes() === 0,
    "un pasadizo salta directamente al destino sin temporizadores");
  ok(registro["modal-ubicacion"].hidden === false &&
    registro["modal-contextual-titulo"].textContent === "nuestra-senora-torre",
  "un pasadizo humano confirmado abre el popup al completar el salto");
  registro["btn-cerrar-ubicacion"].click();

  const brunoOrigen = sala.jugadores.find((item) => item.personaje_id === "bruno").posicion.id;
  observadas = observarMovimiento({
    movimiento_id: 45, personaje_id: "bruno", origen_id: brunoOrigen,
    destino_id: paso2, recorrido: [paso1, paso2], tipo: "normal",
  });
  ok(JSON.stringify(observadas.slice(0, 3)) === JSON.stringify([brunoOrigen, paso1, paso2]),
    "un PNJ utiliza el mismo flujo visual de origen y recorrido");
  ok(registro["modal-ubicacion"].hidden === true,
    "el movimiento de un PNJ no abre el popup al jugador local");
  const accesibles = registro["tablero-canvas-accesible"].children;
  const botonesInfo = accesibles.filter((n) => n.tag === "button" && n.textContent.startsWith("Ver carta de "));
  ok(botonesInfo.length === 9, "la capa HTML mantiene las 9 ubicaciones consultables");
  registro["tablero-canvas"].emitir(50, 13);
  ok(registro["modal-ubicacion"].hidden === false, "hit test Canvas abre el modal HTML");
  ok(registro["imagen-ubicacion"].src === "/static/img/lugares/parador.jpeg", "el modal usa la tarjeta completa, no imagen_tablero");
  ok(!String(registro["imagen-ubicacion"].src).includes("tablero_"), "el modal jamás usa tablero_*.png");
  const imagenesCanvas = vm.runInContext("rendererCanvas.imagenes", sandbox);
  ok(imagenesCanvas.has("/static/img/lugares/tablero_parador.png"), "el medallón Canvas deriva imagen_tablero del ID");
  ok(!imagenesCanvas.has("/static/img/lugares/parador.jpeg"), "el medallón Canvas no carga la tarjeta");
  // Iglesia: Canvas dibuja su PNG pero el modal carga su JPEG.
  // (clic fuera del peón central: el peón tiene prioridad de hit testing)
  registro["tablero-canvas"].emitir(79, 25);
  ok(registro["imagen-ubicacion"].src === "/static/img/lugares/iglesia-san-agustin.jpeg", "iglesia: el modal carga su tarjeta JPEG");
  ok(!String(registro["imagen-ubicacion"].src).includes("tablero_"), "iglesia: el modal no usa tablero_*.png");
  ok(imagenesCanvas.has("/static/img/lugares/tablero_iglesia_san_agustin.png"), "iglesia: el medallón dibuja su PNG");
  // Picota: ID directo a tarjeta, sin guiones bajos ni tablero_*.png.
  sandbox.cerrarCartaUbicacion();
  registro["tablero-canvas"].emitir(21, 20);
  ok(registro["imagen-ubicacion"].src === "/static/img/lugares/picota.jpeg", "picota: el modal carga EXACTAMENTE picota.jpeg");
  ok(imagenesCanvas.has("/static/img/lugares/tablero_picota.png"), "picota: el medallón dibuja tablero_picota.png");
  ok(enviados.length === 0, "consultar una ubicación no envía movimiento");
  registro["btn-cerrar-ubicacion"].click();
  ok(registro["modal-ubicacion"].hidden === true, "el botón cerrar cierra el modal");
  botonesInfo[0].click();
  documentStub.dispatch("keydown", { key: "Escape" });
  ok(registro["modal-ubicacion"].hidden === true, "Escape cierra el modal");
  botonesInfo[0].click();
  registro["modal-ubicacion"].click();
  ok(registro["modal-ubicacion"].hidden === true, "tocar fuera cierra el modal");

  sala.movimiento.destinos = [{ id: "plaza-constitucion", nombre: "Plaza" }];
  socket.onmessage({ data: JSON.stringify({ tipo: "estado_privado", sala }) });
  registro["tablero-canvas"].emitir(50, 50);
  const moverPlaza = registro["btn-mover-ubicacion-canvas"];
  ok(registro["modal-ubicacion"].hidden === false && !moverPlaza.hidden, "ubicación legal separa CONSULTAR de MOVER AQUÍ HTML");
  ok(registro["imagen-ubicacion"].src === "/static/img/lugares/plaza-constitucion.jpeg", "plaza: el modal carga su tarjeta JPEG");
  ok(!String(registro["imagen-ubicacion"].src).includes("tablero_"), "plaza: el modal no usa tablero_*.png");
  ok(enviados.length === 0, "consultar una ubicación legal tampoco mueve");
  sandbox.cerrarCartaUbicacion();
  registro["tablero-canvas"].emitir(50, 50);
  moverPlaza.click();
  ok(enviados.length === 1 && enviados[0].destino_id === "plaza-constitucion", "MOVER AQUÍ envía inequívocamente el destino legal");

  sandbox.window.TableroCanvas = null;
  vm.runInContext("rendererCanvas = null; canvasFallido = false", sandbox);
  sandbox.pintarTablero(sala);
  ok(registro["tablero-ayuda"].classList.contains("error") &&
    registro["tablero-ayuda"].textContent.includes("No se pudo mostrar el tablero"),
  "un fallo crítico de Canvas muestra un error útil sin activar otro renderer");
  ok(registro["tablero-canvas-accesible"].children.length > 0,
    "la capa accesible y sus controles sobreviven al fallo visual de Canvas");

  function crearContextoConFalloInicializacion(opciones = {}) {
    const fallosIniciales = {
      constructorObservador: opciones.falloConstructorObservador !== false,
      observar: false,
      fetchTablero: false,
      constructorWebSocket: false,
      observadores: [],
      intentosWebSocket: 0,
      sockets: [],
      solicitudesTablero: 0,
      solicitudesPersonajes: 0,
    };
    class ObservadorConFallo {
      constructor(callback) {
        if (fallosIniciales.constructorObservador) {
          throw new Error("fallo simulado del constructor MutationObserver");
        }
        this.callback = callback;
        this.desconectado = false;
        fallosIniciales.observadores.push(this);
      }
      observe() {
        if (fallosIniciales.observar) {
          throw new Error("fallo simulado de MutationObserver.observe");
        }
      }
      disconnect() { this.desconectado = true; }
    }
    class WebSocketConFallo {
      constructor(url) {
        fallosIniciales.intentosWebSocket += 1;
        if (fallosIniciales.constructorWebSocket) {
          throw new Error("fallo simulado del constructor WebSocket");
        }
        this.url = url;
        this.cerrado = false;
        fallosIniciales.sockets.push(this);
      }
      send() {}
      close() { this.cerrado = true; }
    }
    WebSocketConFallo.OPEN = 1;
    const fetchConFallo = (url) => {
      if (url === "/api/personajes") {
        fallosIniciales.solicitudesPersonajes += 1;
        const respuesta = opciones.respuestasPersonajes?.shift();
        if (respuesta instanceof Error) return Promise.reject(respuesta);
        if (respuesta) return Promise.resolve(respuesta);
        return Promise.resolve({ ok: true, json: async () => ({ personajes: [] }) });
      }
      if (url === "/api/tablero") {
        fallosIniciales.solicitudesTablero += 1;
        if (fallosIniciales.fetchTablero) {
          throw new Error("fallo simulado síncrono de fetch");
        }
        return new Promise(() => {});
      }
      return Promise.resolve({
        ok: true,
        json: async () => url === "/api/personajes"
          ? { personajes: [] }
          : { recursos: {} },
      });
    };
    const contexto = vm.createContext({
      ...sandbox,
      MutationObserver: ObservadorConFallo,
      WebSocket: WebSocketConFallo,
      fetch: fetchConFallo,
    });
    vm.runInContext(fuenteSala, contexto, {
      filename: "sala-fallo-inicializacion.js",
    });
    return { contexto, fallosIniciales };
  }

  const falloConstructorObservador = crearContextoConFalloInicializacion();
  ok(falloConstructorObservador.fallosIniciales.observadores.length === 0 &&
    falloConstructorObservador.fallosIniciales.solicitudesTablero === 0 &&
    falloConstructorObservador.fallosIniciales.intentosWebSocket === 0,
  "fallar el constructor del observer no inicia los recursos posteriores");
  falloConstructorObservador.fallosIniciales.constructorObservador = false;
  ok(falloConstructorObservador.contexto.inicializarSala() === true &&
    falloConstructorObservador.fallosIniciales.observadores.length === 1 &&
    falloConstructorObservador.fallosIniciales.solicitudesTablero === 1 &&
    falloConstructorObservador.fallosIniciales.sockets.length === 1,
  "fallar el constructor del observer permite reintentar sin recursos duplicados");

  const falloObserve = crearContextoConFalloInicializacion();
  falloObserve.fallosIniciales.constructorObservador = false;
  falloObserve.fallosIniciales.observar = true;
  ok(falloObserve.contexto.inicializarSala() === false &&
    falloObserve.fallosIniciales.observadores.length === 1 &&
    falloObserve.fallosIniciales.observadores[0].desconectado &&
    falloObserve.fallosIniciales.solicitudesTablero === 0 &&
    falloObserve.fallosIniciales.sockets.length === 0,
  "fallar observe desconecta el observer parcial y no crea recursos posteriores");
  falloObserve.fallosIniciales.observar = false;
  ok(falloObserve.contexto.inicializarSala() === true &&
    falloObserve.fallosIniciales.observadores.filter((observador) => !observador.desconectado).length === 1 &&
    falloObserve.fallosIniciales.solicitudesTablero === 1 &&
    falloObserve.fallosIniciales.sockets.length === 1,
  "reintentar tras fallar observe crea una sola instancia activa de cada recurso");

  const falloFetchTablero = crearContextoConFalloInicializacion();
  falloFetchTablero.fallosIniciales.constructorObservador = false;
  falloFetchTablero.fallosIniciales.fetchTablero = true;
  ok(falloFetchTablero.contexto.inicializarSala() === false &&
    falloFetchTablero.fallosIniciales.observadores[0].desconectado &&
    falloFetchTablero.fallosIniciales.solicitudesTablero === 1 &&
    falloFetchTablero.fallosIniciales.intentosWebSocket === 0,
  "un fetch síncrono fallido revierte el observer y no crea el WebSocket");
  falloFetchTablero.fallosIniciales.fetchTablero = false;
  ok(falloFetchTablero.contexto.inicializarSala() === true &&
    falloFetchTablero.fallosIniciales.solicitudesTablero === 2 &&
    falloFetchTablero.fallosIniciales.sockets.length === 1,
  "reintentar tras fallo síncrono de fetch vuelve a solicitar el tablero una sola vez");

  const falloConstructorSocket = crearContextoConFalloInicializacion();
  falloConstructorSocket.fallosIniciales.constructorObservador = false;
  falloConstructorSocket.fallosIniciales.constructorWebSocket = true;
  ok(falloConstructorSocket.contexto.inicializarSala() === false &&
    falloConstructorSocket.fallosIniciales.observadores[0].desconectado &&
    falloConstructorSocket.fallosIniciales.solicitudesTablero === 1 &&
    falloConstructorSocket.fallosIniciales.intentosWebSocket === 1,
  "un constructor WebSocket fallido revierte el observer y conserva la carga iniciada");
  falloConstructorSocket.fallosIniciales.constructorWebSocket = false;
  ok(falloConstructorSocket.contexto.inicializarSala() === true &&
    falloConstructorSocket.fallosIniciales.solicitudesTablero === 1 &&
    falloConstructorSocket.fallosIniciales.sockets.length === 1 &&
    typeof falloConstructorSocket.fallosIniciales.sockets[0].onmessage === "function",
  "reintentar tras fallo WebSocket reutiliza la carga y enlaza los handlers");

  const personajesHttp = crearContextoConFalloInicializacion({
    falloConstructorObservador: false,
    respuestasPersonajes: [
      { ok: false, status: 503, json: async () => ({ detalle: "no disponible" }) },
      { ok: true, json: async () => ({ personajes: [{ id: "vera", nombre: "Vera" }] }) },
    ],
  });
  await new Promise((resolver) => setImmediate(resolver));
  ok(personajesHttp.fallosIniciales.solicitudesPersonajes === 1,
    "el error HTTP de personajes se solicita una vez y se captura");
  ok(personajesHttp.fallosIniciales.sockets.length === 1 &&
    personajesHttp.fallosIniciales.observadores.filter((observador) => !observador.desconectado).length === 1,
  "el fallo de personajes no impide montar ni duplica el socket y el observador");
  vm.runInContext(
    'ultimaSala = { jugadores: [], personaje_id: null }',
    personajesHttp.contexto
  );
  const reintentoHttp = personajesHttp.contexto.reintentarCargaPersonajes();
  const repetidoHttp = personajesHttp.contexto.reintentarCargaPersonajes();
  ok(reintentoHttp === repetidoHttp,
    "dos solicitudes simultáneas de personajes comparten la misma promesa");
  ok(await reintentoHttp === true &&
    personajesHttp.fallosIniciales.solicitudesPersonajes === 2,
  "el reintento tras HTTP fallido recupera personajes con una sola petición");
  ok(personajesHttp.fallosIniciales.sockets.length === 1 &&
    personajesHttp.fallosIniciales.observadores.filter((observador) => !observador.desconectado).length === 1,
  "recuperar personajes con la sala activa conserva un solo socket y observador");
  ok(vm.runInContext("PERSONAJES.length", personajesHttp.contexto) === 1 &&
    registro.personajes.children.length === 1,
  "la carga recuperada actualiza los datos y pinta la selección de personajes");
  ok(personajesHttp.contexto.reintentarCargaPersonajes() === reintentoHttp &&
    personajesHttp.fallosIniciales.solicitudesPersonajes === 2,
  "una carga exitosa permanece cacheada y no duplica peticiones");

  const personajesRed = crearContextoConFalloInicializacion({
    falloConstructorObservador: false,
    respuestasPersonajes: [
      new Error("fallo de conexión"),
      { ok: true, json: async () => ({ personajes: [{ id: "bruno", nombre: "Bruno" }] }) },
    ],
  });
  await new Promise((resolver) => setImmediate(resolver));
  const reintentoRed = personajesRed.contexto.reintentarCargaPersonajes();
  ok(await reintentoRed === true &&
    personajesRed.fallosIniciales.solicitudesPersonajes === 2 &&
    vm.runInContext('PERSONAJES[0].id', personajesRed.contexto) === "bruno",
  "el rechazo asíncrono de fetch permite un reintento exitoso posterior");

  await comprobarContratoSalaJuego(fuenteSala, interfazSala);

  if (fallos) process.exit(1);
  console.log(
    `MONTAJE REAL TABLERO OK · RIESGOS CONOCIDOS ${riesgos} ` +
    `· CONTRATOS FUTUROS PENDIENTES ${contratosPendientes}`
  );
})().catch((error) => { console.error(error); process.exit(1); });
