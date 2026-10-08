/* Harness Fases 8B.33, 8B.33B y 8B.33C: musica ambiental (portada, lobby,
   partida), efectos clic y final, fundido de nivel ymute.
   Ejecuta los modulos REALES (app/static/js/audio.js y el enganche de
   sala.js) con stubs de Audio, document, window y localStorage.
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

const esperar = (ms) => new Promise((r) => setTimeout(r, ms));
// El fundido dura ~700 ms con pasos de 50 ms.
const esperarFade = () => esperar(900);

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
    removeEventListener(evento, fn) {
      this._oyentes[evento] = (this._oyentes[evento] || []).filter((otro) => otro !== fn);
    },
    setAttribute(k, v) { el._attrs[k] = String(v); },
    contains(nodo) {
      if (nodo === el) return true;
      return el.children.some((hijo) => hijo.contains(nodo));
    },
    querySelector() { return makeElemento("div"); },
    querySelectorAll() { return []; },
    focus() {},
    click() { (el._oyentes.click || []).forEach((fn) => fn({ target: el })); },
    dispara(evento) { (el._oyentes[evento] || []).forEach((fn) => fn({ target: el })); },
  };
  return el;
}

function crearEntorno({
  almacenamientoInicial = {},
  playRechaza = false,
  portada = false,
  posicionPrevia = null,
} = {}) {
  const instancias = [];
  const almacen = { ...almacenamientoInicial };
  const sesion = {};
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
      this.readyState = 1;
      this._oyentes = {};
      instancias.push(this);
    }
    addEventListener(evento, fn) { (this._oyentes[evento] = this._oyentes[evento] || []).push(fn); }
    removeEventListener(evento, fn) {
      this._oyentes[evento] = (this._oyentes[evento] || []).filter((otro) => otro !== fn);
    }
    play() {
      this.reproducciones += 1;
      this.pausado = false;
      return playRechaza
        ? Promise.reject(new Error("autoplay bloqueado"))
        : Promise.resolve();
    }
    pause() {
      this.pausas += 1;
      this.pausado = true;
    }
  }

  if (posicionPrevia !== null) {
    sesion.musica_fondo_posicion = JSON.stringify({
      posicion: posicionPrevia,
      momento: Date.now() - 1500,
    });
  }

  const tarjeta = makeElemento("section");
  tarjeta.className = portada ? "portada-escena" : "tarjeta";
  const marcoCompleta = makeElemento("button");
  marcoCompleta.className = "medallon control-pantalla-completa";
  tarjeta.appendChild(marcoCompleta);
  const barra = makeElemento("nav");
  barra.className = "barra-controles-inferior";
  tarjeta.appendChild(barra);
  const cuerpo = makeElemento("body");
  if (portada) cuerpo.className = "portada";
  cuerpo.appendChild(tarjeta);

  const documentStub = {
    documentElement: {},
    body: cuerpo,
    activeElement: null,
    createElement: (tag) => makeElemento(tag),
    querySelector(selector) {
      if (selector === ".barra-controles-inferior") return barra;
      if (selector === ".control-pantalla-completa") return marcoCompleta;
      if (selector === ".tarjeta") return tarjeta;
      return null;
    },
    addEventListener(evento, fn) { (oyentesDoc[evento] = oyentesDoc[evento] || []).push(fn); },
    removeEventListener(evento, fn) {
      oyentesDoc[evento] = (oyentesDoc[evento] || []).filter((otro) => otro !== fn);
    },
    gesto() { (oyentesDoc.pointerdown || []).forEach((fn) => fn({ target: tarjeta })); },
    click(destino) { (oyentesDoc.click || []).forEach((fn) => fn({ target: destino })); },
    // Simula el fin de un documento (navegacion PORTADA -> SALA).
    salir() { (oyentesDoc.pagehide || []).forEach((fn) => fn({})); },
  };

  const sandbox = {
    console,
    document: documentStub,
    window: {
      localStorage: {
        getItem: (k) => (k in almacen ? almacen[k] : null),
        setItem: (k, v) => { almacen[k] = String(v); },
      },
      sessionStorage: {
        getItem: (k) => (k in sesion ? sesion[k] : null),
        setItem: (k, v) => { sesion[k] = String(v); },
      },
      Date,
      JSON,
      setTimeout,
      clearTimeout,
      setInterval,
      clearInterval,
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
  sandbox.window.window = sandbox.window;
  // `window` y `document` comparten el registro de oyentes del stub: los
  // eventos de salida de pagina (pagehide/beforeunload) se escuchan en
  // `window`, y en un navegador real NO burbujean al documento.
  sandbox.window.addEventListener = (evento, fn) => {
    (oyentesDoc[evento] = oyentesDoc[evento] || []).push(fn);
  };
  sandbox.window.removeEventListener = (evento, fn) => {
    oyentesDoc[evento] = (oyentesDoc[evento] || []).filter((otro) => otro !== fn);
  };
  sandbox.window.dispatchEvent = (evento) => {
    (oyentesDoc[evento.tipo] = oyentesDoc[evento.tipo] || []).forEach((fn) => fn(evento));
  };
  // El contexto de vm no trae temporizadores: se inyectan como globales.
  sandbox.setInterval = setInterval;
  sandbox.clearInterval = clearInterval;
  sandbox.setTimeout = setTimeout;
  sandbox.clearTimeout = clearTimeout;
  vm.createContext(sandbox);
  vm.runInContext(
    fs.readFileSync(path.join(__dirname, "..", "app", "static", "js", "audio.js"), "utf8"),
    sandbox,
    { filename: "audio.js" }
  );
  return { sandbox, instancias, almacen, sesion, documentStub, tarjeta, barra, marcoCompleta };
}

function control(entorno) {
  return entorno.barra.children.find((hijo) => hijo.className.includes("control-sonido"));
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

async function main() {
  // 9 · El modulo se carga en portada y sala; el control, solo en la sala.
  const htmlSala = fs.readFileSync(path.join(__dirname, "..", "app", "templates", "sala.html"), "utf8");
  const htmlPortada = fs.readFileSync(path.join(__dirname, "..", "app", "templates", "inicio.html"), "utf8");
  ok(htmlSala.includes("/static/js/audio.js"), "audio.js se carga en la sala");
  ok(htmlPortada.includes("/static/js/audio.js"), "audio.js se carga tambien en portada");

  // ---------------- A, D, G, H · PORTADA
  const portada = crearEntorno({ portada: true });
  const audioPortada = portada.sandbox.window.AudioFondo;
  const musicaPortada = pistaDe(portada, "musica_fondo.mp3");
  ok(Boolean(musicaPortada), "A · la portada pide la musica al cargar");
  ok(musicaPortada.reproducciones === 1, "A · la portada intenta reproducir la musica");
  ok(musicaPortada.loop === true, "A · la musica ambiental va en loop");
  ok(Math.abs(musicaPortada.volume - 0.22) < 1e-9, "D · en portada el nivel objetivo es 0,22");
  ok(!control(portada), "A · la portada no muestra el control de sonido");
  ok(!pistaDe(portada, "final.mp3"), "A · la portada no crea la pista de final");
  ok(portada.instancias.filter((p) => String(p.src).endsWith("musica_fondo.mp3")).length === 1,
    "H · una sola pista musical, tambien en portada");

  // Clic en portada: la musica NO se reinicia ni se duplica.
  const botonPortada = botonReal("medallon", "CREAR PARTIDA");
  portada.tarjeta.appendChild(botonPortada);
  portada.documentStub.click(botonPortada);
  ok(!!pistaDe(portada, "clic.mp3"), "B · CREAR PARTIDA reproduce clic desde la portada");
  ok(musicaPortada.reproducciones === 1, "G · el clic no reinicia la musica");
  ok(portada.instancias.filter((p) => String(p.src).endsWith("musica_fondo.mp3")).length === 1,
    "H · el clic no crea una segunda musica");

  // M · Continuidad entre PORTADA y SALA (cambio de documento).
  musicaPortada.currentTime = 42;
  portada.documentStub.salir();
  ok(portada.sesion.musica_fondo_posicion, "M · al salir del documento guarda el punto de la pista");
  const salaTrasPortada = crearEntorno({ posicionPrevia: 42 });
  const musicaSala = pistaDe(salaTrasPortada, "musica_fondo.mp3");
  ok(musicaSala.currentTime === 42, "M · la sala retoma la musica donde estaba");
  const recarga = crearEntorno({ posicionPrevia: 42 });
  ok(pistaDe(recarga, "musica_fondo.mp3").reproducciones === 1, "M · una recarga no duplica pistas");

  // ---------------- B, C · Autoplay bloqueado
  const bloqueado = crearEntorno({ playRechaza: true });
  const audioBloqueado = bloqueado.sandbox.window.AudioFondo;
  let lanzo = false;
  try {
    bloqueado.documentStub.click(botonReal("medallon", "UNIRME"));
  } catch (error) {
    lanzo = true;
  }
  ok(!lanzo, "B · un play() rechazado no lanza excepcion visible");
  ok(audioBloqueado.isSonando() === false, "B · queda preparada pero sin sonar");
  ok(Boolean(control(bloqueado)), "B · el control de sonido sigue disponible");
  bloqueado.instancias[0].play = function () {
    this.reproducciones += 1;
    return Promise.resolve();
  };
  bloqueado.documentStub.gesto();
  ok(bloqueado.instancias[0].reproducciones >= 1, "C · la primera interaccion arranca la musica");

  // ---------------- E, F, G · LOBBY -> PARTIDA con fundido
  const entorno = crearEntorno();
  const audio = entorno.sandbox.window.AudioFondo;
  const musica = pistaDe(entorno, "musica_fondo.mp3");
  await esperar(20);
  ok(Math.abs(musica.volume - 0.22) < 1e-9, "D · en el lobby el nivel objetivo es 0,22");
  ok(audio.volumenActual() === 0.15, "D · el volumen general por defecto sigue siendo 0,15");
  ok(musica.preload === "metadata", "la musica sigue pidiendo solo metadato");

  // La cancion continua: se fija un punto y se comprueba que sigue en el.
  musica.currentTime = 77;
  const reproduccionesAntes = musica.reproducciones;
  audio.iniciar();   // COMENZAR PARTIDA
  ok(musica.pausas === 0, "G · comenzar la partida NO hace pause()");
  ok(musica.reproducciones === reproduccionesAntes, "G · comenzar la partida NO vuelve a dar play()");
  ok(musica.currentTime === 77, "G · la cancion sigue por el punto por el que iba");
  const nivelInmediato = musica.volume;
  ok(Math.abs(nivelInmediato - 0.22) < 1e-9, "F · el fundido no salta: el nivel no cambia de golpe");
  await esperar(250);
  const nivelMedio = musica.volume;
  ok(nivelMedio < 0.22 - 1e-6 && nivelMedio > 0.15 + 1e-6,
    `F · a mitad del fundido el nivel es intermedio (${nivelMedio.toFixed(3)})`);
  await esperarFade();
  ok(Math.abs(musica.volume - 0.15) < 1e-9, "E · al terminar el fundido el nivel es 0,15");

  for (let i = 0; i < 5; i += 1) audio.iniciar();
  ok(musica.reproducciones === reproduccionesAntes, "F/I · los repintados no tocan la musica");
  ok(musica.currentTime === 77, "G · los repintados tampoco la reinician");
  ok(entorno.instancias.filter((p) => String(p.src).endsWith("musica_fondo.mp3")).length === 1,
    "H · una sola pista musical por cliente");

  // ---------------- I, K, J · Clic, slider y mute
  const crear = botonReal("medallon medallon-primario", "CREAR PARTIDA");
  entorno.tarjeta.appendChild(crear);
  entorno.documentStub.click(crear);
  const clic = pistaDe(entorno, "clic.mp3");
  ok(clic.reproducciones === 1, "I · el clic suena con la musica de fondo");
  ok(musica.pausado === false, "I · el clic no detiene la musica");
  ok(musica.reproducciones === reproduccionesAntes, "I · el clic no reinicia la musica");
  entorno.documentStub.click(crear);
  ok(clic.reproducciones === 2, "K · un clic por accion, sin doble");
  ok(entorno.instancias.filter((p) => String(p.src).endsWith("clic.mp3")).length === 1,
    "H · el clic reutiliza una sola instancia");

  const miniatura = makeElemento("div");
  miniatura.className = "carta-visual-compacta";
  entorno.tarjeta.appendChild(miniatura);
  entorno.documentStub.click(miniatura);
  ok(clic.reproducciones === 3, "F · seleccionar una carta de la hoja suena");
  entorno.documentStub.click(entorno.marcoCompleta);
  ok(clic.reproducciones === 4, "F · el control de pantalla completa suena");

  // Donde NO suena.
  const parrafo = makeElemento("p");
  parrafo.textContent = "EL MISTERIO DEL MEDALLÓN";
  entorno.tarjeta.appendChild(parrafo);
  entorno.documentStub.click(parrafo);
  const deshabilitado = botonReal("medallon", "COMENZAR PARTIDA");
  deshabilitado.disabled = true;
  entorno.tarjeta.appendChild(deshabilitado);
  entorno.documentStub.click(deshabilitado);
  const ariaDeshabilitado = botonReal("medallon", "SIN INFORMACIÓN");
  ariaDeshabilitado.setAttribute("aria-disabled", "true");
  entorno.tarjeta.appendChild(ariaDeshabilitado);
  entorno.documentStub.click(ariaDeshabilitado);
  ok(clic.reproducciones === 4, "2 · texto, deshabilitados y aria-disabled NO suenan");
  ok(audio.reproducirEfecto("dado") === null, "los efectos no implementados siguen devolviendo null");

  // K · El slider general escala los dos niveles y no se rompe.
  const boton = control(entorno);
  const panel = boton.children.find((h) => h.className.includes("control-sonido-panel"));
  const etiqueta = panel.children.find((h) => h.className.includes("control-sonido-etiqueta"));
  const slider = etiqueta.children.find((h) => h.className.includes("control-sonido-slider"));
  slider.value = "30";
  slider.dispara("input");
  ok(Math.abs(audio.volumenActual() - 0.3) < 1e-9, "K · el slider sigue cambiando el volumen general");
  ok(Math.abs(musica.volume - 0.3) < 1e-9,
    "K · en partida el nivel es el general (0,15 por defecto escalado)");
  ok(Math.abs(clic.volume - 0.3 * 2.2) < 1e-9, "K · el clic conserva su multiplicador");
  ok(entorno.almacen.volumen_musica === "0.3", "K · la preferencia sigue en localStorage");
  ok(musica.reproducciones === reproduccionesAntes, "K · mover el slider no reinicia la musica");
  // Volumen general 0,15 con la fase de partida: no se sobrescribe nada.
  audio.fijarVolumen(0.15);
  ok(Math.abs(musica.volume - 0.15) < 1e-9, "K · volver al valor por defecto no pisa la eleccion del usuario");
  audio.fijarVolumen(0.4);
  ok(Math.abs(musica.volume - 0.4) < 1e-9, "K · en partida el 0,4 del jugador da 0,4 de nivel");
  ok(Math.abs(clic.volume - 0.4 * 2.2) < 1e-9, "4 · los multiplicadores de efectos no cambian");

  // J · Mute calla musica y efectos.
  audio.fijarVolumen(0);
  ok(musica.volume === 0, "J · volumen 0 silencia la musica");
  const antesDelSilencio = clic.reproducciones;
  entorno.documentStub.click(crear);
  ok(clic.reproducciones === antesDelSilencio, "J · con volumen 0 no se dispara el clic");
  audio.reproducirEfecto("final");
  ok(!pistaDe(entorno, "final.mp3"), "J · con volumen 0 no se dispara el final");
  ok(boton.classList.contains("silenciado"), "J · el estado silenciado se refleja visualmente");
  ok(boton.getAttribute("aria-pressed") === "false", "J · el estado silenciado se expone por ARIA");

  // 7 · Volumen al maximo satura los tres.
  audio.fijarVolumen(1);
  ok(musica.volume === 1 && clic.volume === 1, "7 · al maximo todo satura sin superar 1");
  audio.fijarVolumen(0.15);

  // ---------------- L · Final
  const finalAntes = pistaDe(entorno, "final.mp3");
  audio.reproducirEfecto("final");
  const final = pistaDe(entorno, "final.mp3");
  ok(final !== finalAntes, "L · el final usa su propia reproduccion");
  ok(final.loop === false, "L · el final no esta en loop");
  ok(final.reproducciones === 1, "L · el final suena una vez");
  ok(musica.pausado === false, "L · el final no detiene la musica por si mismo");
  audio.reproducirEfecto("final");
  ok(final.reproducciones === 1, "L · el final no se repite en la misma pagina");
  entorno.documentStub.click(crear);
  ok(final.pausas === 0 && final.reproducciones === 1,
    "L · un clic posterior no detiene ni reinicia el final");

  // S · Rutas runtime correctas.
  ok(musica.src === "/static/audio/musica_fondo.mp3", "S · la musica usa su ruta runtime");
  ok(clic.src === "/static/audio/clic.mp3", "S · el clic usa su ruta runtime");
  ok(final.src === "/static/audio/final.mp3", "S · el final usa su ruta runtime");

  // ---------------- Enganche real en sala.js (L)
  const llamadas = [];
  function stubAudio() {
    return {
      iniciar: () => llamadas.push("iniciar"),
      detener: () => llamadas.push("detener"),
      reproducirEfecto: (nombre) => llamadas.push(`efecto:${nombre}`),
    };
  }
  function paginaSala() {
    const registro = {};
    const documentSala = {
      getElementById(id) {
        if (!registro[id]) registro[id] = makeElemento("div");
        return registro[id];
      },
      querySelectorAll() { return []; },
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
  ok(llamadas.length === 0, "el lobby no toca el nivel: la musica sigue en ambiente");
  llamadas.length = 0;
  pintarFinal({ estado: "iniciada" });
  ok(llamadas.join(",") === "iniciar", "E · la partida iniciada baja el nivel de la musica");
  llamadas.length = 0;
  pintarFinal({ estado: "iniciada" });
  pintarFinal({ estado: "iniciada" });
  ok(!llamadas.includes("efecto:final"), "una resolucion fallida NO suena el final");
  ok(!llamadas.includes("detener"), "la musica sigue durante la partida");
  llamadas.length = 0;
  pintarFinal({ estado: "terminada", resultado_final: "resuelto", ganador_alias: "Vera" });
  ok(llamadas.join(",") === "detener,efecto:final", "L · el final detiene musica y suena una vez");
  llamadas.length = 0;
  pintarFinal({ estado: "terminada" });
  pintarFinal({ estado: "terminada" });
  ok(llamadas.filter((c) => c === "efecto:final").length === 0, "terminada -> terminada no repite");
  pintarFinal = paginaSala();
  llamadas.length = 0;
  pintarFinal({ estado: "terminada" });
  ok(!llamadas.includes("efecto:final"), "recargar ya terminada NO dispara el final");
  ok(llamadas.includes("detener"), "la musica sigue detenida tras recargar");

  if (fallos > 0) {
    console.log(`${fallos} FALLO(S)`);
    process.exit(1);
  }
  console.log("AUDIO FONDO OK");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
