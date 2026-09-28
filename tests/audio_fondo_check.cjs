/* Harness Fases 8B.33 y 8B.33B: musica ambiental, clic y final.
   Ejecuta los modulos REALES (app/static/js/audio.js y el enganche de
   sala.js) con stubs de Audio, document, window y localStorage, y
   comprueba el contrato completo.
   Uso: node tests/audio_fondo_check.cjs */
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

// ---------------------------------------------------------------- DOM stub
function makeElemento(tag) {
  const el = {
    tag,
    nodeType: 1,
    children: [],
    parentElement: null,
    className: "",
    hidden: false,
    disabled: false,
    value: "",
    type: "",
    _texto: "",
    _html: "",
    _attrs: {},
    _oyentes: {},
    classList: {
      add(clase) { if (!el.className.split(" ").includes(clase)) el.className += ` ${clase}`; },
      remove(clase) { el.className = el.className.split(" ").filter((c) => c && c !== clase).join(" "); },
      toggle(clase, fuerza) {
        const tiene = el.className.split(" ").includes(clase);
        const poner = fuerza === undefined ? !tiene : fuerza;
        if (poner && !tiene) el.className += ` ${clase}`;
        if (!poner && tiene) el.classList.remove(clase);
      },
      contains(clase) { return el.className.split(" ").includes(clase); },
    },
    getAttribute(k) { return k in el._attrs ? el._attrs[k] : null; },
    matches(selector) {
      return selector.split(",").map((s) => s.trim()).some((parte) => {
        if (!parte) return false;
        if (parte.startsWith(".")) return el.className.split(" ").includes(parte.slice(1));
        const atributo = parte.match(/\[([^\]=]+)(?:=["']?([^\]"']+)["']?)?\]/);
        const etiqueta = parte.split("[")[0];
        if (etiqueta && el.tag !== etiqueta) return false;
        if (!atributo) return Boolean(etiqueta);
        const valor = el.getAttribute(atributo[1]);
        return atributo[2] === undefined ? valor !== null : valor === atributo[2];
      });
    },
    set textContent(v) { this._texto = String(v); },
    get textContent() { return this._texto; },
    set innerHTML(v) { this._html = String(v); },
    get innerHTML() { return this._html; },
    appendChild(hijo) { hijo.parentElement = el; this.children.push(hijo); return hijo; },
    addEventListener(evento, fn) {
      (this._oyentes[evento] = this._oyentes[evento] || []).push(fn);
    },
    setAttribute(k, v) { el._attrs[k] = String(v); },
    contains(nodo) {
      if (nodo === el) return true;
      return el.children.some((hijo) => hijo.contains(nodo));
    },
    focus() {},
    click() { (el._oyentes.click || []).forEach((fn) => fn({ target: el })); },
    dispara(evento) { (el._oyentes[evento] || []).forEach((fn) => fn({ target: el })); },
  };
  return el;
}

function crearEntorno({ almacenamientoInicial = {}, playRechaza = false, portada = false } = {}) {
  const instancias = [];
  const almacen = { ...almacenamientoInicial };
  const oyentesDoc = {};

  class AudioFalso {
    constructor() {
      this.loop = false;
      this.preload = "";
      this.volume = 1;
      this.currentTime = 0;
      this.pausado = true;
      this.src = "";
      this.reproducciones = 0;
      this.pausas = 0;
      instancias.push(this);
    }
    play() {
      this.reproducciones += 1;
      return playRechaza
        ? Promise.reject(new Error("autoplay bloqueado"))
        : Promise.resolve();
    }
    pause() {
      this.pausas += 1;
      this.pausado = true;
    }
  }

  const tarjeta = makeElemento("section");
  tarjeta.className = portada ? "portada-escena" : "tarjeta";
  const marcoCompleta = makeElemento("button");
  marcoCompleta.className = "medallon control-pantalla-completa";
  tarjeta.appendChild(marcoCompleta);
  const cuerpo = makeElemento("body");
  if (portada) cuerpo.className = "portada";
  cuerpo.appendChild(tarjeta);

  const documentStub = {
    documentElement: {},
    body: cuerpo,
    activeElement: null,
    createElement: (tag) => makeElemento(tag),
    querySelector(selector) {
      if (selector === ".control-pantalla-completa") return marcoCompleta;
      if (selector === ".tarjeta") return tarjeta;
      return null;
    },
    addEventListener(evento, fn) { (oyentesDoc[evento] = oyentesDoc[evento] || []).push(fn); },
    removeEventListener(evento, fn) {
      oyentesDoc[evento] = (oyentesDoc[evento] || []).filter((otro) => otro !== fn);
    },
    gesto() { (oyentesDoc.pointerdown || []).forEach((fn) => fn({ target: tarjeta })); },
    // Clic real de usuario: recorre los oyentes en fase de captura.
    click(destino) { (oyentesDoc.click || []).forEach((fn) => fn({ target: destino })); },
  };

  const sandbox = {
    console,
    document: documentStub,
    window: {
      localStorage: {
        getItem: (k) => (k in almacen ? almacen[k] : null),
        setItem: (k, v) => { almacen[k] = String(v); },
      },
    },
    Audio: AudioFalso,
    fetch: () => Promise.resolve({
      json: () => Promise.resolve({
        audio: {
          musica_fondo: "/static/audio/musica_fondo.mp3",
          clic: "/static/audio/clic.mp3",
          final: "/static/audio/final.mp3",
        },
      }),
    }),
  };
  sandbox.window.document = documentStub;
  vm.createContext(sandbox);
  vm.runInContext(
    fs.readFileSync(path.join(__dirname, "..", "app", "static", "js", "audio.js"), "utf8"),
    sandbox,
    { filename: "audio.js" }
  );
  return { sandbox, instancias, almacen, documentStub, tarjeta, marcoCompleta };
}

function control(entorno) {
  return entorno.tarjeta.children.find((hijo) => hijo.className.includes("control-sonido"));
}

function pistaDe(entorno, sufijo) {
  return entorno.instancias.find((p) => String(p.src).endsWith(sufijo));
}

function botonReal(clase, etiqueta) {
  const b = makeElemento("button");
  if (clase) b.className = clase;
  if (etiqueta) b.setAttribute("aria-label", etiqueta);
  return b;
}

// ------------------------------------------------------------------ Pruebas
// 9 · El modulo se carga en portada y sala; solo la sala pinta el control.
const htmlSala = fs.readFileSync(path.join(__dirname, "..", "app", "templates", "sala.html"), "utf8");
const htmlPortada = fs.readFileSync(path.join(__dirname, "..", "app", "templates", "inicio.html"), "utf8");
ok(htmlSala.includes("/static/js/audio.js"), "audio.js se carga en la sala");
ok(htmlPortada.includes("/static/js/audio.js"), "audio.js se carga tambien en portada (clic)");

// A · La musica NO suena en portada: ni pista creada, ni control visible.
const portada = crearEntorno({ portada: true });
const audioPortada = portada.sandbox.window.AudioFondo;
ok(portada.instancias.length === 0, "A · la portada no crea ninguna pista de audio");
ok(!control(portada), "A · la portada no muestra el control de sonido");
portada.documentStub.click(botonReal("medallon", "CREAR PARTIDA"));
ok(!pistaDe(portada, "musica_fondo.mp3"), "A · en portada solo se crea la pista de clic");
ok(!!pistaDe(portada, "clic.mp3"), "B · CREAR PARTIDA reproduce clic desde la portada");
ok(!pistaDe(portada, "final.mp3"), "A · la portada no crea la pista de final");

// B/C · Un clic por interaccion manual, sobre la estructura de controles.
let entorno = crearEntorno();
const audio = entorno.sandbox.window.AudioFondo;
const crear = botonReal("medallon medallon-primario", "CREAR PARTIDA");
entorno.tarjeta.appendChild(crear);
entorno.documentStub.click(crear);
ok(pistaDe(entorno, "clic.mp3").reproducciones === 1, "B · CREAR PARTIDA suena una vez");
entorno.documentStub.click(crear);
ok(pistaDe(entorno, "clic.mp3").reproducciones === 2, "K · clic tras clic: un sonido por accion");
ok(entorno.instancias.filter((p) => p.src.endsWith("clic.mp3")).length === 1,
  "8 · el clic reutiliza una sola instancia, sin acumular Audio");

// Estructura real de la hoja de investigacion y del tablero.
const miniatura = makeElemento("div");
miniatura.className = "carta-visual-compacta";
entorno.tarjeta.appendChild(miniatura);
entorno.documentStub.click(miniatura);
ok(pistaDe(entorno, "clic.mp3").reproducciones === 3, "F · seleccionar una carta de la hoja suena");
entorno.documentStub.click(entorno.marcoCompleta);
ok(pistaDe(entorno, "clic.mp3").reproducciones === 4, "F · el control de pantalla completa suena");

// Donde NO suena clic.
const parrafo = makeElemento("p");
parrafo.textContent = "EL MISTERIO DEL MEDALLÓN";
entorno.tarjeta.appendChild(parrafo);
entorno.documentStub.click(parrafo);
ok(pistaDe(entorno, "clic.mp3").reproducciones === 4, "2 · un texto que no es control NO suena");
const deshabilitado = botonReal("medallon", "COMENZAR PARTIDA");
deshabilitado.disabled = true;
entorno.tarjeta.appendChild(deshabilitado);
entorno.documentStub.click(deshabilitado);
ok(pistaDe(entorno, "clic.mp3").reproducciones === 4, "J · un control deshabilitado NO suena");
const ariaDeshabilitado = botonReal("medallon", "SIN INFORMACIÓN");
ariaDeshabilitado.setAttribute("aria-disabled", "true");
entorno.tarjeta.appendChild(ariaDeshabilitado);
entorno.documentStub.click(ariaDeshabilitado);
ok(pistaDe(entorno, "clic.mp3").reproducciones === 4, "J · aria-disabled tampoco suena");
ok(entorno.sandbox.window.AudioFondo.reproducirEfecto("dado") === null,
  "los efectos no implementados siguen devolviendo null");

// M · La musica ambiental sigue exactamente como en 8B.33.
const musica = pistaDe(entorno, "musica_fondo.mp3");
ok(musica === undefined, "M · cargar el modulo no crea la pista musical");
audio.iniciar();
const musical = pistaDe(entorno, "musica_fondo.mp3");
ok(Boolean(musical), "M · la partida iniciada crea la pista musical");
ok(musical.loop === true, "M · la musica sigue en loop");
ok(musical.preload === "metadata", "M · la musica sigue pidiendo solo metadato");
ok(audio.volumenActual() === 0.15 && musical.volume === 0.15, "6 · volumen inicial 0.15");
for (let i = 0; i < 5; i += 1) audio.iniciar();
ok(musical.reproducciones === 1, "F/I · los repintados y WebSocket no reinician la musica");
ok(entorno.instancias.filter((p) => p.src.endsWith("musica_fondo.mp3")).length === 1,
  "M · una sola pista musical por cliente");

// 7 · El mismo mando gobierna musica, clic y final.
const clic = pistaDe(entorno, "clic.mp3");
ok(Math.abs(clic.volume - 0.15 * 2.2) < 1e-9, "7 · el clic se oye claro pero discreto (x2,2)");
audio.fijarVolumen(0.2);
ok(Math.abs(musical.volume - 0.2) < 1e-9, "7 · la musica sigue el volumen elegido");
ok(Math.abs(clic.volume - 0.2 * 2.2) < 1e-9, "7 · el clic se reescala con el mismo volumen");
audio.reproducirEfecto("final");
const final = pistaDe(entorno, "final.mp3");
ok(Math.abs(final.volume - 0.2 * 3) < 1e-9, "7 · el final es algo mas protagonista (x3)");
audio.fijarVolumen(1);
ok(clic.volume === 1 && final.volume === 1 && musical.volume === 1,
  "7 · al maximo todo satura sin superar 1");
audio.fijarVolumen(0.2);
ok(final.loop === false, "R · el final no esta en loop");
ok(final.reproducciones === 1, "4 · el final suena una vez");
audio.reproducirEfecto("final");
ok(final.reproducciones === 1, "5 · el final no se repite en la misma pagina");
entorno.documentStub.click(crear);
ok(final.pausas === 0 && final.reproducciones === 1,
  "8 · un clic posterior no detiene ni reinicia el final");

// L · Mute: calla todo.
const clicsAntes = clic.reproducciones;
audio.fijarVolumen(0);
ok(musical.volume === 0, "L · volumen 0 silencia la musica");
entorno.documentStub.click(crear);
ok(clic.volume === 0, "L · volumen 0 silencia el clic");
ok(clic.reproducciones === clicsAntes, "L · con volumen 0 no se dispara el clic");
audio.reproducirEfecto("final");
ok(final.reproducciones === 1, "L · con volumen 0 no se dispara el final");

// 7 · El control de sonido gobierna tambien los efectos.
const boton = control(entorno);
const panel = boton.children.find((hijo) => hijo.className.includes("control-sonido-panel"));
const etiqueta = panel.children.find((hijo) => hijo.className.includes("control-sonido-etiqueta"));
const slider = etiqueta.children.find((hijo) => hijo.className.includes("control-sonido-slider"));
slider.value = "40";
slider.dispara("input");
ok(audio.volumenActual() === 0.4, "el slider sigue cambiando el volumen");
ok(Math.abs(musical.volume - 0.4) < 1e-9 && Math.abs(clic.volume - 0.4 * 2.2) < 1e-9,
  "el mismo slider gobierna musica y clic");
ok(entorno.almacen.volumen_musica === "0.4", "la preferencia sigue en localStorage");
ok(boton.classList.contains("silenciado") === false, "al volver a oir desaparece el estado silenciado");
slider.value = "0";
slider.dispara("input");
ok(boton.classList.contains("silenciado"), "volumen 0 se refleja visualmente");

// S · Rutas runtime correctas.
ok(musical.src === "/static/audio/musica_fondo.mp3", "S · la musica usa su ruta runtime");
ok(clic.src === "/static/audio/clic.mp3", "S · el clic usa su ruta runtime");
ok(final.src === "/static/audio/final.mp3", "S · el final usa su ruta runtime");

// O · Play rechazado: sin excepcion y con el control disponible.
const bloqueado = crearEntorno({ playRechaza: true });
const audioBloqueado = bloqueado.sandbox.window.AudioFondo;
let lanzoExcepcion = false;
try {
  audioBloqueado.iniciar();
  bloqueado.documentStub.click(botonReal("medallon", "COMENZAR"));
} catch (error) {
  lanzoExcepcion = true;
}
ok(!lanzoExcepcion, "O · un play() rechazado no lanza excepcion visible");
ok(audioBloqueado.isSonando() === false, "O · queda preparada pero sin sonar");
ok(Boolean(control(bloqueado)), "O · el control de sonido sigue disponible");
bloqueado.instancias[0].play = function () {
  this.reproducciones += 1;
  return Promise.resolve();
};
bloqueado.documentStub.gesto();
ok(bloqueado.instancias[0].reproducciones >= 1, "P · la primera interaccion arranca la musica");

// P · Recarga durante partida: misma pista preparada, sin duplicar.
const recarga = crearEntorno({ almacenamientoInicial: { volumen_musica: "0.3" } });
recarga.sandbox.window.AudioFondo.iniciar();
const trasRecarga = pistaDe(recarga, "musica_fondo.mp3");
recarga.sandbox.window.AudioFondo.iniciar();
ok(recarga.instancias.filter((p) => p.src.endsWith("musica_fondo.mp3")).length === 1,
  "P · la recarga no duplica la pista");
ok(trasRecarga.reproducciones === 1, "P · la recarga no reinicia la reproduccion");
ok(recarga.sandbox.window.AudioFondo.volumenActual() === 0.3, "P · restaura la preferencia local");

// M · Preferencia independiente por dispositivo.
const otro = crearEntorno({ almacenamientoInicial: { volumen_musica: "0.05" } });
ok(otro.sandbox.window.AudioFondo.volumenActual() === 0.05, "M · otra preferencia local se restaura");

// ------------------------------------------- enganche real en sala.js (N/O/P/Q)
const llamadas = [];
function stubAudio() {
  return {
    iniciar: () => llamadas.push("iniciar"),
    detener: () => llamadas.push("detener"),
    reproducirEfecto: (nombre) => llamadas.push(`efecto:${nombre}`),
  };
}
// Cada carga es una PAGINA nueva: asi la recarga se prueba de verdad.
function paginaSala() {
  const registro = {};
  const documentSala = {
    getElementById(id) {
      if (!registro[id]) registro[id] = makeElemento("div");
      return registro[id];
    },
    createElement: (tag) => makeElemento(tag),
    addEventListener() {},
    removeEventListener() {},
    body: makeElemento("body"),
    activeElement: null,
    documentElement: {},
  };
  registro.codigo = makeElemento("p");
  registro.codigo.textContent = "JARA-AUDIO";
  const sandbox = {
    console,
    document: documentSala,
    window: { location: { protocol: "http:", host: "localhost:8000" }, AudioFondo: stubAudio() },
    sessionStorage: { getItem: () => "jug-audio", setItem: () => {} },
    fetch: () => Promise.resolve({ then: () => ({ then: () => {} }) }),
    WebSocket: class { send() {} },
  };
  vm.createContext(sandbox);
  vm.runInContext(
    fs.readFileSync(path.join(__dirname, "..", "app", "static", "js", "sala.js"), "utf8"),
    sandbox,
    { filename: "sala.js" }
  );
  return sandbox.pintarFinal;
}

let pintarFinal = paginaSala();
pintarFinal({ estado: "esperando" });
ok(llamadas.length === 0, "A/B · portada y lobby no suenan musica");
llamadas.length = 0;
pintarFinal({ estado: "iniciada" });
ok(llamadas.join(",") === "iniciar", "M · la partida iniciada comienza la musica");

// Resolucion fallida y eliminados: NO suenan final.
llamadas.length = 0;
pintarFinal({ estado: "iniciada" });
pintarFinal({ estado: "iniciada" });
ok(!llamadas.includes("efecto:final"), "Q · una resolucion fallida NO suena el final");
ok(!llamadas.includes("detener"), "Q · la musica sigue durante la partida");

// N · Transicion iniciada -> terminada: detiene musica y suena final UNA vez.
llamadas.length = 0;
pintarFinal({ estado: "terminada", resultado_final: "resuelto", ganador_alias: "Vera" });
ok(llamadas.join(",") === "detener,efecto:final", "N · el final detiene musica y suena una vez");

// O · terminada -> terminada: no se repite.
llamadas.length = 0;
pintarFinal({ estado: "terminada" });
pintarFinal({ estado: "terminada" });
ok(llamadas.filter((c) => c === "efecto:final").length === 0, "O · terminada -> terminada no repite");
ok(llamadas.filter((c) => c === "detener").length === 2, "O · la musica se mantiene detenida");

// P · Recarga con la partida ya terminada: no suena el final.
pintarFinal = paginaSala();
llamadas.length = 0;
pintarFinal({ estado: "terminada" });
ok(!llamadas.includes("efecto:final"), "P · recargar ya terminada NO dispara el final");
ok(llamadas.includes("detener"), "P · la musica sigue detenida tras recargar");

if (fallos > 0) {
  console.log(`${fallos} FALLO(S)`);
  process.exit(1);
}
console.log("AUDIO FONDO OK");
