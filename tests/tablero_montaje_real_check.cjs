/* Montaje completo: plantilla real + estado WS antes del descriptor fetch.
   Uso: node tests/tablero_montaje_real_check.cjs */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

let fallos = 0;
function ok(condicion, nombre) {
  console.log(`${condicion ? "PASS" : "FAIL"} ${nombre}`);
  if (!condicion) fallos += 1;
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
  _oyentes: {},
  getElementById(id) {
    if (!registro[id]) registro[id] = id === "tablero-canvas" ? new CanvasMontaje() : elemento("div");
    return registro[id];
  },
  createElement(tag) { return tag === "canvas" ? new CanvasMontaje() : elemento(tag); },
  createElementNS(_ns, tag) { return elemento(tag); },
  addEventListener(tipo, fn) { (this._oyentes[tipo] ||= []).push(fn); },
  dispatch(tipo, evento) { (this._oyentes[tipo] || []).forEach((fn) => fn(evento)); },
};
registro.codigo = elemento("p");
registro.codigo.textContent = "JARA-REAL";

const exteriores = [
  "parador", "iglesia-san-agustin", "ermita-sopetran", "cristo-humilladero",
  "nuestra-senora-torre", "museo-escobazos", "puente-parral", "picota",
];
const ubicaciones = [...exteriores, "plaza-constitucion"];
const coordenadas = [[50, 8], [79, 20], [92, 50], [79, 80], [50, 92], [21, 80], [8, 50], [21, 20], [50, 50]];
const nodos = ubicaciones.map((id, i) => ({
  id, tipo: "ubicacion", nombre: id, x: coordenadas[i][0], y: coordenadas[i][1],
  imagen: `/static/img/lugares/${id}.jpeg`,
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

let resolverTablero;
let socket;
const enviados = [];
class WebSocketFalso {
  constructor() { socket = this; }
  send(mensaje) { enviados.push(JSON.parse(mensaje)); }
}
const fetchFalso = (url) => {
  if (url === "/api/tablero") {
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
    ResizeObserver: class { constructor(fn) { this.fn = fn; } observe() {} },
    addEventListener() {},
  },
  sessionStorage: { getItem: () => "jug-real", setItem() {} },
  fetch: fetchFalso, WebSocket: WebSocketFalso, Set, Map,
};
vm.createContext(sandbox);

(async () => {
  const raiz = path.join(__dirname, "..");
  const html = fs.readFileSync(path.join(raiz, "app", "templates", "sala.html"), "utf8");
  ok(html.includes('id="tablero-visual"'), "sala.html contiene el contenedor real");
  ok(html.includes('/static/js/tablero_canvas.js?v=7d'), "la plantilla carga el renderer Canvas oficial");
  ok(html.includes('/static/js/sala.js?v=7d'), "la plantilla carga la integración Canvas consolidada");
  ok(!html.includes('id="tablero-superficie"') && !html.includes('id="tablero-nodos"'),
    "la plantilla ya no contiene el renderer HTML/SVG descartado");

  sandbox.window.window = sandbox.window;
  vm.runInContext(fs.readFileSync(path.join(raiz, "app", "static", "js", "tablero_canvas.js"), "utf8"), sandbox, { filename: "tablero_canvas.js" });
  vm.runInContext(fs.readFileSync(path.join(raiz, "app", "static", "js", "sala.js"), "utf8"), sandbox, { filename: "sala.js" });
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
    posicion: jugadores[0].posicion,
    movimiento: { fase: "esperando_movimiento", puede_tirar: true, tirada: null, destinos: [] },
    resultado_final: null, ganador_alias: null,
  };

  socket.onmessage({ data: JSON.stringify({ tipo: "estado_privado", sala }) });
  ok(registro["tablero-visual"].hidden === false, "el estado WS real de modo tablero muestra el contenedor");
  ok(vm.runInContext("rendererCanvas", sandbox) === null, "la carrera se reproduce: el estado puede llegar antes del descriptor");

  resolverTablero();
  await new Promise((resolve) => setImmediate(resolve));
  await new Promise((resolve) => setImmediate(resolve));
  ok(registro["tablero-visual"].hidden === false, "el contenedor permanece visible tras cargar descriptor");
  ok(registro["tablero-canvas-contenedor"].hidden === false, "sala.js activa Canvas en navegador compatible");
  const metricas = vm.runInContext("rendererCanvas.metricas", sandbox);
  ok(metricas.ubicaciones === 9 && metricas.casillas === 48, "Canvas monta 9 ubicaciones y 48 casillas");
  ok(metricas.caminos === 16 && metricas.pasadizos === 2, "Canvas monta 16 caminos y 2 pasadizos");
  ok(metricas.peones === 6 && metricas.dpr === 2, "Canvas monta 6 peones con escala HiDPI");
  ok(personajes.every((id) => metricas.representacionesPeones.some((p) =>
    p.personaje_id === id && p.drawSolicitado && p.drawEjecutado)),
  "el montaje integrado identifica y representa individualmente los seis personajes");
  const accesibles = registro["tablero-canvas-accesible"].children;
  const botonesInfo = accesibles.filter((n) => n.tag === "button" && n.textContent.startsWith("Ver carta de "));
  ok(botonesInfo.length === 9, "la capa HTML mantiene las 9 ubicaciones consultables");
  registro["tablero-canvas"].emitir(50, 8);
  ok(registro["modal-ubicacion"].hidden === false, "hit test Canvas abre el modal HTML");
  ok(registro["imagen-ubicacion"].src === "/static/img/lugares/parador.jpeg", "el modal usa la imagen runtime canónica");
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

  if (fallos) process.exit(1);
  console.log("MONTAJE REAL TABLERO OK");
})().catch((error) => { console.error(error); process.exit(1); });
