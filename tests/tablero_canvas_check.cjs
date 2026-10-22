/* Harness del renderer oficial Canvas con contexto, imágenes y puntero simulados. */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

let fallos = 0;
function ok(condicion, nombre) {
  console.log(`${condicion ? "PASS" : "FAIL"} ${nombre}`);
  if (!condicion) fallos += 1;
}

class ContextoFalso {
  constructor() {
    this.operaciones = []; this.globalAlpha = 1; this.shadowColor = "";
    this.pixeles = new Uint8ClampedArray([0, 0, 0, 255, 244, 230, 184, 255]);
  }
  setTransform(...a) { this.operaciones.push(["transform", ...a]); }
  clearRect() {} fillRect() { this.operaciones.push(["fillRect", this.fillStyle]); }
  beginPath() {} moveTo() {} lineTo() {} closePath() {} clip() {}
  stroke() { this.operaciones.push(["stroke", this.strokeStyle, this.globalAlpha]); }
  fill() { this.operaciones.push(["fill", this.fillStyle, this.globalAlpha]); }
  arc() {} quadraticCurveTo() {} setLineDash() {}
  save() { this._guardado = [this.globalAlpha, this.shadowColor]; }
  restore() { if (this._guardado) [this.globalAlpha, this.shadowColor] = this._guardado; }
  drawImage(imagen) { this.operaciones.push(["drawImage", imagen, this.globalAlpha, this.shadowColor]); }
  getImageData() { return { data: new Uint8ClampedArray(this.pixeles) }; }
  putImageData(imagen) { this.pixeles = new Uint8ClampedArray(imagen.data); }
}

class CanvasFalso {
  constructor(lado = 600) {
    this.lado = lado; this.width = 0; this.height = 0; this.clientWidth = lado;
    this.style = {}; this.ctx = new ContextoFalso(); this.oyentes = {};
  }
  getContext() { return this.ctx; }
  getBoundingClientRect() { return { left: 0, top: 0, width: this.lado, height: this.lado }; }
  addEventListener(tipo, fn) { (this.oyentes[tipo] ||= []).push(fn); }
  removeEventListener(tipo, fn) {
    this.oyentes[tipo] = (this.oyentes[tipo] || []).filter((oyente) => oyente !== fn);
  }
  emitir(tipo, x, y) { (this.oyentes[tipo] || []).forEach((fn) => fn({ clientX: x * this.lado / 100, clientY: y * this.lado / 100 })); }
}

let fallarFotos = new Set();
let diferirCargaImagenes = false;
const imagenesCreadas = [];
class ImagenFalsa {
  constructor() {
    this.naturalWidth = 800; this.naturalHeight = 600; this.width = 800; this.height = 600;
    imagenesCreadas.push(this);
  }
  set src(url) {
    this._src = url;
    if (diferirCargaImagenes) return;
    if (fallarFotos.has(url)) { if (this.onerror) this.onerror(new Error("fallo")); }
    else if (this.onload) this.onload();
  }
  get src() { return this._src; }
}

const exteriores = ["parador", "iglesia-san-agustin", "ermita-sopetran", "cristo-humilladero", "nuestra-senora-torre", "museo-escobazos", "puente-parral", "picota"];
const coords = [[50, 11], [77.58, 22.42], [89, 50], [77.58, 77.58], [50, 89], [22.42, 77.58], [11, 50], [22.42, 22.42]];
const nodos = exteriores.map((id, i) => ({
  id, tipo: "ubicacion", nombre: id, x: coords[i][0], y: coords[i][1], diametro: 14,
  // Señuelo: el Canvas real ignora imagen_tarjeta y deriva el PNG del ID.
  imagen_tarjeta: `/static/img/lugares/${id}.jpeg`,
}));
nodos.push({ id: "plaza-constitucion", tipo: "ubicacion", nombre: "Plaza", x: 50, y: 50, diametro: 32.3,
  imagen_tarjeta: "/static/img/lugares/plaza-constitucion.jpeg" });
const parejas = exteriores.map((id, i) => [id, exteriores[(i + 1) % 8]]).concat(exteriores.map((id) => [id, "plaza-constitucion"]));
const caminos = parejas.map(([a, b]) => {
  const id = `camino-${a}-${b}`; const na = nodos.find((n) => n.id === a); const nb = nodos.find((n) => n.id === b);
  const casillas = [1, 2, 3].map((paso) => {
    const nodo = { id: `${id}-${paso}`, tipo: "casilla", nombre: `Casilla ${paso}`, x: na.x + (nb.x - na.x) * paso / 4, y: na.y + (nb.y - na.y) * paso / 4 };
    nodos.push(nodo); return nodo.id;
  });
  return { id, nodos: [a, ...casillas, b], inicio: na, fin: nb };
});
const personajes = ["vera", "bruno", "lucia", "alvaro", "mateo", "eulalia"];
const colores = { vera: "#6f42a5", bruno: "#3f4448", lucia: "#285943", alvaro: "#176b73", mateo: "#c49324", eulalia: "#b33a2f" };
const descriptor = {
  nodos, caminos,
  pasadizos: [
    { id: "p1", origen: "parador", destino: "nuestra-senora-torre" },
    { id: "p2", origen: "ermita-sopetran", destino: "puente-parral" },
  ],
  peon: "/static/img/personajes/peon.svg", colores_personajes: colores,
};
const casillaLegal = nodos.find((n) => n.tipo === "casilla");
const jugadores = personajes.map((id, i) => ({
  alias: `J${i + 1}`, personaje_id: id, personaje: id, activo: i !== 5,
  posicion: { id: i < 2 ? "parador" : exteriores[i], nombre: exteriores[i] },
}));
const estado = { jugadores, turno_alias: "J1", movimiento: { destinos: [{ id: casillaLegal.id }, { id: "plaza-constitucion" }] } };

const oyentesVentana = {};
const observadoresTamano = [];
const rafPendientes = new Map();
const rafCancelados = [];
let siguienteRaf = 1;
const ventana = {
  devicePixelRatio: 2,
  Image: ImagenFalsa,
  addEventListener(tipo, fn) { (oyentesVentana[tipo] ||= []).push(fn); },
  removeEventListener(tipo, fn) {
    oyentesVentana[tipo] = (oyentesVentana[tipo] || []).filter((oyente) => oyente !== fn);
  },
  requestAnimationFrame(fn) {
    const id = siguienteRaf++;
    rafPendientes.set(id, fn);
    return id;
  },
  cancelAnimationFrame(id) {
    rafCancelados.push(id);
    rafPendientes.delete(id);
  },
};
ventana.window = ventana;
ventana.ResizeObserver = class {
  constructor(fn) {
    this.fn = fn;
    this.desconectado = false;
    observadoresTamano.push(this);
  }
  observe() {}
  disconnect() { this.desconectado = true; }
};
const sandbox = {
  window: ventana, console,
  document: { createElement(tag) { return tag === "canvas" ? new CanvasFalso(64) : {}; } },
  Math, Map, Set,
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(__dirname, "..", "app", "static", "js", "tablero_canvas.js"), "utf8"), sandbox);

const consultas = [];
const movimientos = [];
const canvas = new CanvasFalso(600);
const renderer = new ventana.TableroCanvas(canvas, descriptor, {
  consultar: (nodo) => consultas.push(nodo.id),
  mover: (id) => movimientos.push(id),
});
renderer.actualizar(estado);

const esperadasTablero = nodos
  .filter((n) => n.tipo === "ubicacion")
  .map((n) => `/static/img/lugares/tablero_${n.id.replace(/-/g, "_")}.png`);
const urlsTablero = esperadasTablero;
const urlsTarjeta = nodos.filter((n) => n.tipo === "ubicacion").map((n) => n.imagen_tarjeta);
ok(urlsTablero.every((url) => renderer.imagenes.has(url)), "el medallón deriva imagen_tablero del ID en las 9 ubicaciones");
ok(urlsTarjeta.every((url) => !renderer.imagenes.has(url)), "el medallón nunca carga la tarjeta completa");

ok(canvas.width === 1200 && canvas.height === 1200, "devicePixelRatio escala el backing store HiDPI");
ok(renderer.metricas.dpr === 2, "el renderer registra DPR 2");
ok(renderer.metricas.ubicaciones === 9, "dibuja 9 ubicaciones");
ok(renderer.metricas.casillas === 48, "dibuja 48 casillas");
ok(renderer.metricas.diametroCasilla === 3.125, "aumenta un 25 % el diámetro visual de las casillas intermedias");
ok(renderer.metricas.tamanoPeonCasilla === 4.5 &&
  renderer.metricas.tamanoPeonCasilla / renderer.metricas.diametroCasilla === 1.44,
"el peón de camino mide 1.44 veces el diámetro de la casilla");
ok(renderer.metricas.caminos === 16, "dibuja 16 caminos");
ok(renderer.metricas.pasadizos === 2, "dibuja 2 pasadizos");
ok(renderer.metricas.peones === 6, "dibuja 6 peones");
ok(renderer.metricas.destinos === 2, "resalta solo destinos recibidos");
ok(renderer.peonesTintados.size === 6 && personajes.every((id) => renderer.peonesTintados.has(colores[id])), "recolorea un único SVG con los seis colores");
const pixelesBruno = renderer.peonesTintados.get(colores.bruno).ctx.pixeles;
ok(pixelesBruno[0] === 63 && pixelesBruno[1] === 68 && pixelesBruno[2] === 72,
  "el cuerpo de Bruno conserva su color canónico");
ok(pixelesBruno[4] === 244 && pixelesBruno[5] === 230 && pixelesBruno[6] === 184,
  "el tintado preserva el contorno crema del SVG para contraste");
ok(canvas.ctx.operaciones.some((o) => o[0] === "drawImage" && o[3] === "#fff0a3"), "el turno actual recibe halo");
ok(canvas.ctx.operaciones.some((o) => o[0] === "drawImage" && o[3] === "#f4efe3"), "los peones reciben halo neutro de contraste");
ok(canvas.ctx.operaciones.some((o) => o[0] === "drawImage" && o[2] === 0.38), "el eliminado queda atenuado");
ok(renderer.metricas.conteoPeones.peonesSolicitados === 6 &&
  renderer.metricas.conteoPeones.peonesSvgDibujados + renderer.metricas.conteoPeones.fallbacksDibujados === 6,
"cada participante con posición obtiene una representación dibujada");

const posicionesSeparadas = {
  vera: "plaza-constitucion", bruno: "parador", lucia: "puente-parral",
  alvaro: "iglesia-san-agustin", mateo: "museo-escobazos", eulalia: "picota",
};
const estadoSeparado = {
  jugadores: personajes.map((id, i) => ({
    id: `jugador-${id}`, alias: `S${i + 1}`, personaje_id: id,
    personaje: id, tipo: i ? "pnj" : "humano", activo: true,
    posicion: { id: posicionesSeparadas[id], nombre: posicionesSeparadas[id] },
  })),
  turno_alias: "S1", movimiento: { destinos: [] },
};
renderer.actualizar(estadoSeparado);
ok(personajes.every((id) => renderer.metricas.representacionesPeones.some((p) =>
  p.personaje_id === id && p.posicion === posicionesSeparadas[id] && p.drawEjecutado === "svg")),
"identifica y dibuja por personaje los seis participantes separados");

const tintarOriginal = renderer._peonTintado.bind(renderer);
const coloresConFallo = new Set([colores.bruno, colores.lucia, colores.mateo]);
renderer._peonTintado = (color) => coloresConFallo.has(color) ? null : tintarOriginal(color);
renderer.actualizar(estadoSeparado);
ok(["bruno", "lucia", "mateo"].every((id) => renderer.metricas.representacionesPeones.some((p) =>
  p.personaje_id === id && p.drawEjecutado === "fallback")),
"Bruno, Lucía y Mateo reciben fallback inmediato si su variante SVG falla o tarda");
ok(renderer.metricas.conteoPeones.peonesSolicitados === 6 &&
  renderer.metricas.conteoPeones.peonesSvgDibujados === 3 &&
  renderer.metricas.conteoPeones.fallbacksDibujados === 3,
"el fallo de tres variantes conserva la invariante 6 = 3 SVG + 3 fallbacks");
renderer._peonTintado = tintarOriginal;
renderer.actualizar(estado);

function estadoCoincidente(cantidad, nodoId) {
  return {
    jugadores: personajes.slice(0, cantidad).map((id, i) => ({
      alias: `C${i + 1}`, personaje_id: id, personaje: id, activo: true,
      posicion: { id: nodoId, nombre: nodoId },
    })),
    turno_alias: "C1", movimiento: { destinos: [] },
  };
}

function comprobarDistribucion(cantidad, nodoId, radioMaximo, separacionMinima) {
  renderer.actualizar(estadoCoincidente(cantidad, nodoId));
  const centros = renderer.metricas.distribucionPeones;
  const claves = new Set(centros.map((p) => `${p.offsetX.toFixed(5)},${p.offsetY.toFixed(5)}`));
  let minima = Infinity;
  for (let i = 0; i < centros.length; i += 1) {
    for (let j = i + 1; j < centros.length; j += 1) {
      minima = Math.min(minima, Math.hypot(centros[i].x - centros[j].x, centros[i].y - centros[j].y));
    }
  }
  const dentro = centros.every((p) => Math.hypot(p.offsetX, p.offsetY) <= radioMaximo + 1e-6);
  const coloresPresentes = new Set(centros.map((p) => p.color));
  ok(centros.length === cantidad && claves.size === cantidad, `${cantidad} peón(es): centros visuales distintos`);
  ok(dentro, `${cantidad} peón(es): permanecen en el área asociada a ${nodoId}`);
  if (cantidad > 1) ok(minima >= separacionMinima, `${cantidad} peones: separación mínima ${minima.toFixed(2)}`);
  ok(coloresPresentes.size === cantidad, `${cantidad} peón(es): conserva todos los colores`);
}

for (let cantidad = 1; cantidad <= 6; cantidad += 1) {
  comprobarDistribucion(cantidad, "plaza-constitucion", 6.2, 5.9);
}
comprobarDistribucion(6, "parador", 3.25, 3.1);
comprobarDistribucion(6, casillaLegal.id, 1.65, 1.55);
const coronaPlaza = renderer._geometriaPeones(nodos.find((n) => n.id === "plaza-constitucion"), 6);
ok(coronaPlaza.offsets.every(([x, y]) => Math.abs(Math.hypot(x, y) - 6.2) < 1e-6), "Plaza usa corona regular de radio 6.2");
ok(renderer._geometriaPeones(casillaLegal, 1).tamano === 4.5,
  "el peón situado en una casilla usa la escala física ampliada");
ok(Math.abs(renderer._geometriaPeones(nodos.find((n) => n.id === "parador"), 1).tamano - 4.76) < 1e-9 &&
  renderer._geometriaPeones(nodos.find((n) => n.id === "plaza-constitucion"), 1).tamano === 5,
"el ajuste no cambia el tamaño de peones en Plaza ni ubicaciones exteriores");

renderer.actualizar(estado);

canvas.emitir("pointerup", 50, 11);
ok(consultas[0] === "parador" && movimientos.length === 0, "hit test de ubicación consulta y no mueve");
canvas.emitir("pointerup", casillaLegal.x, casillaLegal.y);
ok(movimientos[0] === casillaLegal.id, "hit test de casilla legal usa destino_id existente");
canvas.emitir("pointerup", 50, 50);
ok(consultas.includes("plaza-constitucion") && movimientos.length === 1, "ubicación legal sigue consultando sin movimiento automático");

canvas.lado = 400;
renderer.redimensionar();
ok(canvas.width === 800 && renderer.metricas.peones === 6, "resize repinta sin alterar lógica ni peones");
renderer.actualizar({ ...estado, turno_alias: "J2" });
ok(renderer.metricas.peones === 6, "repintado WebSocket/reconexión no duplica peones");

fallarFotos = new Set([descriptor.peon, "/static/img/lugares/tablero_parador.png"]);
const canvasFallos = new CanvasFalso(500);
const rendererFallos = new ventana.TableroCanvas(canvasFallos, descriptor, {});
rendererFallos.actualizar(estado);
ok(rendererFallos.imagenes.get("/static/img/lugares/tablero_parador.png").estado === "error" && rendererFallos.metricas.ubicaciones === 9, "fallo de imagen_tablero usa placeholder sin destruir tablero");
ok(rendererFallos.imagenes.get(descriptor.peon).estado === "error" && rendererFallos.metricas.peones === 6, "fallo de peon.svg usa fallback geométrico");

diferirCargaImagenes = true;
const canvasDestruido = new CanvasFalso(420);
const rendererDestruido = new ventana.TableroCanvas(canvasDestruido, descriptor, {});
const posicionesVisualesExternas = new Map([["vera", "parador"]]);
rendererDestruido.actualizar(estado, descriptor, posicionesVisualesExternas);
const callbacksImagen = [...rendererDestruido.imagenes.values()]
  .map((recurso) => recurso.imagen.onload)
  .filter(Boolean);
const rafDestruido = rendererDestruido._raf;
const callbackRaf = rafPendientes.get(rafDestruido);
const operacionesAntesDeDestruir = canvasDestruido.ctx.operaciones.length;
const observadorDestruido = rendererDestruido.observador;
ok(Boolean(rafDestruido && callbackRaf), "el renderer registra el RAF activo del pulso");
rendererDestruido.destruir();
ok(observadorDestruido.desconectado, "destruir desconecta el ResizeObserver");
ok((canvasDestruido.oyentes.pointerup || []).length === 0 &&
  (canvasDestruido.oyentes.pointermove || []).length === 0,
"destruir retira ambos listeners persistentes del Canvas");
ok(!rafPendientes.has(rafDestruido) && rafCancelados.includes(rafDestruido),
"destruir cancela el RAF pendiente");
ok(rendererDestruido.imagenes.size === 0 && rendererDestruido.peonesTintados.size === 0,
"destruir libera las cachés de imágenes y peones tintados");
ok(posicionesVisualesExternas.get("vera") === "parador",
"destruir no modifica el mapa de posiciones compartido por quien llama al renderer");
rendererDestruido.destruir();
ok(observadoresTamano.filter((observador) => observador === observadorDestruido && observador.desconectado).length === 1 &&
  rafCancelados.filter((id) => id === rafDestruido).length === 1,
"una segunda destrucción no repite la limpieza");
callbacksImagen.forEach((callback) => callback());
callbackRaf(123);
rendererDestruido.actualizar(estado);
rendererDestruido.redimensionar();
rendererDestruido.dibujar();
ok(canvasDestruido.ctx.operaciones.length === operacionesAntesDeDestruir,
"callbacks de imagen y RAF, y llamadas posteriores, no repintan el renderer destruido");

diferirCargaImagenes = false;
const rendererNuevo = new ventana.TableroCanvas(canvasDestruido, descriptor, {});
rendererNuevo.actualizar(estado);
ok((canvasDestruido.oyentes.pointerup || []).length === 1 &&
  (canvasDestruido.oyentes.pointermove || []).length === 1 &&
  rendererNuevo.metricas.peones === 6,
"se puede montar y dibujar un renderer nuevo sobre el mismo Canvas");
rendererNuevo.destruir();

const ResizeObserverOriginal = ventana.ResizeObserver;
ventana.ResizeObserver = null;
const canvasResizeAlternativo = new CanvasFalso(300);
const oyentesResizeAntes = (oyentesVentana.resize || []).length;
const rendererResizeAlternativo = new ventana.TableroCanvas(
  canvasResizeAlternativo, descriptor, {}
);
ok((oyentesVentana.resize || []).length === oyentesResizeAntes + 1,
"sin ResizeObserver se registra el listener alternativo de resize");
rendererResizeAlternativo.destruir();
ok((oyentesVentana.resize || []).length === oyentesResizeAntes,
"destruir retira el listener alternativo de resize");
ventana.ResizeObserver = ResizeObserverOriginal;

if (fallos) process.exit(1);
console.log("TABLERO CANVAS OK");
