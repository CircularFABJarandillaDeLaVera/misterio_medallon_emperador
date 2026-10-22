/* Harness 8B.19: control global de pantalla completa.
   Verifica portada/lobby/partida comparten el control, la sincronía
   de estado (incluido Escape vía fullscreenchange) y la degradación
   cuando el navegador no soporta la API o rechaza la petición.
   Uso: node tests/pantalla_completa_check.cjs */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const RUTA = path.join(__dirname, "..", "app", "static", "js", "pantalla_completa.js");
const FUENTE = fs.readFileSync(RUTA, "utf8");

let fallos = 0;
function ok(condicion, nombre) {
  console.log(`${condicion ? "PASS" : "FAIL"} ${nombre}`);
  if (!condicion) fallos += 1;
}

function nodo(tag) {
  return {
    tag, type: "", className: "", innerHTML: "", hidden: false,
    textContent: "", children: [], parentNode: null, _attrs: {}, _oyentes: {},
    classList: {
      _dueno: null,
      contains(clase) {
        return this._dueno.className.split(/\s+/).includes(clase);
      },
      add(clase) {
        if (!this.contains(clase)) this._dueno.className += ` ${clase}`;
      },
      remove(clase) {
        this._dueno.className = this._dueno.className
          .split(/\s+/).filter((valor) => valor && valor !== clase).join(" ");
      },
      toggle(clase, fuerza) {
        const activar = fuerza === undefined ? !this.contains(clase) : Boolean(fuerza);
        if (activar) this.add(clase);
        else this.remove(clase);
        return activar;
      },
    },
    setAttribute(k, v) { this._attrs[k] = String(v); },
    getAttribute(k) { return this._attrs[k]; },
    appendChild(h) {
      if (h.parentNode) {
        h.parentNode.children = h.parentNode.children.filter((n) => n !== h);
      }
      h.parentNode = this;
      this.children.push(h);
      return h;
    },
    addEventListener(e, fn) { (this._oyentes[e] = this._oyentes[e] || []).push(fn); },
    click() { (this._oyentes.click || []).forEach((fn) => fn()); },
  };
}

function prepararNodo(tag) {
  const elemento = nodo(tag);
  elemento.classList._dueno = elemento;
  return elemento;
}

function crearAlmacen(inicial = {}) {
  const datos = new Map(Object.entries(inicial));
  return {
    getItem(clave) { return datos.has(clave) ? datos.get(clave) : null; },
    setItem(clave, valor) { datos.set(clave, String(valor)); },
    removeItem(clave) { datos.delete(clave); },
  };
}

function montar(opciones) {
  const raiz = prepararNodo("html");
  const oyentesDoc = {};
  const cuerpo = prepararNodo("body");
  const marco = prepararNodo("section");
  if (opciones.sinMarco !== true) {
    marco.className = opciones.marcoClase || "portada-escena";
  }
  const doc = {
    documentElement: raiz,
    body: cuerpo,
    fullscreenElement: null,
    webkitFullscreenElement: null,
    createElement: prepararNodo,
    getElementById() { return null; },
    addEventListener(e, fn) { (oyentesDoc[e] = oyentesDoc[e] || []).push(fn); },
    querySelector(sel) {
      if (sel === ".barra-controles-inferior" && marco.className === "barra-controles-inferior") return marco;
      if (sel === ".portada-escena" && marco.className === "portada-escena") return marco;
      if (sel === ".tarjeta" && marco.className === "tarjeta") return marco;
      return null;
    },
  };
  let pedirLlamadas = 0;
  let salirLlamadas = 0;
  if (opciones.soportado !== false) {
    raiz.requestFullscreen = () => {
      pedirLlamadas += 1;
      doc.fullscreenElement = raiz;
      if (opciones.rechaza) return Promise.reject(new Error("denegado"));
      return Promise.resolve();
    };
    doc.exitFullscreen = () => {
      salirLlamadas += 1;
      doc.fullscreenElement = null;
      return Promise.resolve();
    };
  }
  const sandbox = {
    console, document: doc, Promise, Error,
    sessionStorage: opciones.almacen || crearAlmacen(),
  };
  vm.createContext(sandbox);
  vm.runInContext(FUENTE, sandbox, { filename: "pantalla_completa.js" });
  return {
    doc, cuerpo, raiz, marco, pantalla: () => sandbox.PantallaCompleta,
    boton: () => marco.children[0] || cuerpo.children[0],
    pide: () => pedirLlamadas,
    pedir: () => pedirLlamadas,
    salir: () => salirLlamadas,
    cambiarFullscreen: () => (oyentesDoc.fullscreenchange || []).forEach((fn) => fn()),
    error: () => (oyentesDoc.fullscreenerror || []).forEach((fn) => fn()),
    oyentes: () => Object.values(oyentesDoc).reduce((total, lista) => total + lista.length, 0),
    recargarModulo: () => vm.runInContext(FUENTE, sandbox, { filename: "pantalla_completa-repetida.js" }),
  };
}

function montarSalaReal({ almacen, rechaza = false }) {
  const raiz = prepararNodo("html");
  const cuerpo = prepararNodo("body");
  const tarjeta = prepararNodo("section");
  tarjeta.className = "tarjeta lobby-marco";
  const lobby = prepararNodo("p");
  lobby.className = "lobby-sala-linea";
  const barra = prepararNodo("nav");
  barra.className = "barra-controles-inferior";
  barra.hidden = true;
  const codigo = prepararNodo("span");
  codigo.textContent = "JARA-TEST";
  const oyentesDoc = {};
  let observador = null;
  let observadoresCreados = 0;
  let pedirLlamadas = 0;

  raiz.requestFullscreen = () => {
    pedirLlamadas += 1;
    if (rechaza) return Promise.reject(new Error("denegado"));
    doc.fullscreenElement = raiz;
    return Promise.resolve();
  };
  const doc = {
    documentElement: raiz,
    body: cuerpo,
    fullscreenElement: null,
    webkitFullscreenElement: null,
    exitFullscreen() {
      this.fullscreenElement = null;
      return Promise.resolve();
    },
    createElement: prepararNodo,
    getElementById(id) { return id === "codigo" ? codigo : null; },
    addEventListener(e, fn) { (oyentesDoc[e] = oyentesDoc[e] || []).push(fn); },
    querySelector(selector) {
      if (selector === ".lobby-sala-linea") return lobby;
      if (selector === ".barra-controles-inferior") return barra;
      if (selector === ".tarjeta") return tarjeta;
      return null;
    },
  };
  class ObservadorFalso {
    constructor(fn) { observador = fn; observadoresCreados += 1; }
    observe() {}
  }
  const sandbox = {
    console, document: doc, Promise, Error,
    sessionStorage: almacen,
    MutationObserver: ObservadorFalso,
  };
  vm.createContext(sandbox);
  vm.runInContext(FUENTE, sandbox, { filename: "pantalla_completa.js" });
  const boton = () => lobby.children[0] || barra.children[0];
  return {
    doc, lobby, barra, boton, pantalla: () => sandbox.PantallaCompleta,
    pedir: () => pedirLlamadas,
    observadores: () => observadoresCreados,
    recargarModulo: () => vm.runInContext(FUENTE, sandbox, { filename: "pantalla-sala-repetida.js" }),
    cambiarFullscreen: () => (oyentesDoc.fullscreenchange || []).forEach((fn) => fn()),
    errorFullscreen: () => (oyentesDoc.fullscreenerror || []).forEach((fn) => fn()),
    empezarPartida() {
      cuerpo.classList.add("en-partida");
      if (observador) observador();
    },
  };
}

const m = montar({ soportado: true });
const boton = m.boton();

ok(Boolean(boton), "el control se inyecta en el documento");
ok(m.marco.children.length === 1 && m.cuerpo.children.length === 0,
  "el control se monta en el marco canónico, no en el flujo del body");
ok(
  boton && boton.className.includes("medallon") && boton.className.includes("control-pantalla-completa"),
  "reutiliza la familia medallón (sin familia visual nueva)"
);
ok(boton && boton._attrs.title === "Pantalla completa", "tooltip inicial: Pantalla completa");
ok(boton && boton._attrs["aria-label"] === "Pantalla completa", "aria-label inicial correcto");
ok(boton && boton.children.length === 3, "iconos y etiqueta de recuperación presentes");
ok(boton && boton.children[0].innerHTML.includes("<svg"), "icono de entrada es SVG (⛶)");
ok(boton && boton.children[0].hidden === false && boton.children[1].hidden === true,
  "estado inicial: muestra entrar, oculta salir");
const servicioPantalla = m.pantalla();
const oyentesPantallaIniciales = m.oyentes();
m.recargarModulo();
ok(m.pantalla() === servicioPantalla && m.boton() === boton,
  "una segunda carga reutiliza el servicio y el mismo control");
ok(m.marco.children.length === 1 && m.oyentes() === oyentesPantallaIniciales,
  "una segunda carga no duplica controles ni eventos fullscreen");

// Entrar: el propio click entra y el evento resincroniza.
boton.click();
ok(m.pedir() === 1, "un clic entra en pantalla completa");
m.cambiarFullscreen();
ok(boton._attrs["aria-label"] === "Salir de pantalla completa",
  "tras entrar, el control ofrece salir");
ok(boton.children[0].hidden === true && boton.children[1].hidden === false,
  "icono de salida visible tras entrar");

// Escape del navegador: fullscreenchange sin nuestra intervención.
m.doc.fullscreenElement = null;
m.cambiarFullscreen();
ok(boton._attrs["aria-label"] === "Pantalla completa",
  "Escape (fullscreenchange) resincroniza a entrar");
ok(boton.children[0].hidden === false && boton.children[1].hidden === true,
  "icono de entrada vuelve a verse");

// Tras Escape, el siguiente clic entra de nuevo; desde dentro, el mismo
// botón sale. El botón nunca hace otra cosa.
boton.click();
m.cambiarFullscreen();
ok(m.pedir() === 2 && m.salir() === 0, "tras salir, el botón vuelve a entrar");
boton.click();
ok(m.pedir() === 2 && m.salir() === 1, "el mismo botón sale de pantalla completa");
m.cambiarFullscreen();
ok(boton._attrs["aria-label"] === "Pantalla completa", "estado final: entrar");

// Navegador que rechaza la petición: sin aviso técnico y estado estable.
const r = montar({ soportado: true, rechaza: true });
r.boton().click();
r.cambiarFullscreen();
ok(r.boton()._attrs["aria-label"] !== undefined, "petición rechazada: el control sigue coherente");

// Navegador sin Fullscreen API: no se muestra nada y no rompe.
const s = montar({ soportado: false });
ok(s.cuerpo.children.length === 0, "sin soporte de API el control no se inyecta");
ok(true, "la aplicación sigue utilizable sin Fullscreen API");

// Sin duplicar implementaciones en inicio.js ni sala.js.
const inicioJs = fs.readFileSync(path.join(__dirname, "..", "app", "static", "js", "inicio.js"), "utf8");
const salaJs = fs.readFileSync(path.join(__dirname, "..", "app", "static", "js", "sala.js"), "utf8");
ok(!/requestFullscreen/.test(inicioJs) && !/requestFullscreen/.test(salaJs),
  "inicio.js y sala.js no reimplementan el control");
ok(/PantallaCompleta\.actualizarFase/.test(salaJs),
  "la sala actualiza la ubicación mediante la interfaz compartida");
ok(
  (inicioJs.match(
    /registrarContinuidadPantallaCompleta\(datos\);\s*window\.location\.href/g
  ) || []).length === 3,
  "crear, unirse y cargar registran continuidad justo antes de navegar"
);

// Lobby y partida comparten el mismo módulo con su marco canónico.
const lobby = montar({ soportado: true, marcoClase: "tarjeta" });
ok(lobby.marco.children.length === 1 && lobby.cuerpo.children.length === 0,
  "en lobby el control usa el marco .tarjeta (mismo módulo)");
ok(lobby.boton().className === boton.className,
  "mismo control y mismo lenguaje visual en ambas vistas");

const sala = montar({ soportado: true, marcoClase: "barra-controles-inferior" });
ok(sala.marco.children.length === 1 && sala.cuerpo.children.length === 0,
  "en la sala el control se monta dentro de la barra inferior compartida");

// Navegación real: el documento de portada registra intención, la sala nace
// fuera de fullscreen y ofrece recuperar mediante el mismo control.
const almacenContinuidad = crearAlmacen({ jugador_id: "jugador-1" });
const portadaActiva = montar({ soportado: true, almacen: almacenContinuidad });
portadaActiva.boton().click();
ok(
  portadaActiva.pantalla().registrarContinuidad({
    codigo: "JARA-TEST", jugador_id: "jugador-1",
  }),
  "la portada registra continuidad solo mientras Fullscreen API está activa"
);
const lobbyReal = montarSalaReal({ almacen: almacenContinuidad });
const servicioSala = lobbyReal.pantalla();
lobbyReal.recargarModulo();
ok(lobbyReal.pantalla() === servicioSala && lobbyReal.observadores() === 1,
  "reinicializar la sala no duplica el observador de ubicación");
ok(lobbyReal.lobby.children.length === 1 && lobbyReal.barra.children.length === 0,
  "con lobby y barra coexistiendo, el control visible se monta junto al código");
ok(
  lobbyReal.boton().children[2].hidden === false &&
    lobbyReal.boton()._attrs["aria-label"] === "Continuar en pantalla completa",
  "la sala muestra la acción explícita de recuperación"
);
ok(almacenContinuidad.getItem("pantalla_completa_pendiente") === null,
  "la señal temporal se consume al llegar a la sala correcta");
lobbyReal.boton().click();
ok(lobbyReal.pedir() === 1, "la recuperación requiere y usa un clic del jugador");
lobbyReal.cambiarFullscreen();
ok(
  lobbyReal.boton().children[2].hidden &&
    lobbyReal.boton()._attrs["aria-label"] === "Salir de pantalla completa",
  "al recuperar, el texto deja paso al control normal"
);
lobbyReal.empezarPartida();
ok(lobbyReal.barra.children[0] === lobbyReal.boton() && lobbyReal.lobby.children.length === 0,
  "al empezar, el mismo nodo se traslada a la barra del tablero");
const controlMovible = lobbyReal.boton();
lobbyReal.pantalla().actualizarFase("seleccion");
ok(lobbyReal.lobby.children[0] === controlMovible && lobbyReal.barra.children.length === 0,
  "la API de fase devuelve el mismo control a la selección");
lobbyReal.pantalla().actualizarFase("tablero");
ok(lobbyReal.barra.children[0] === controlMovible && lobbyReal.lobby.children.length === 0,
  "la API de fase mueve la única instancia al tablero");

const almacenNormal = crearAlmacen({ jugador_id: "jugador-1" });
const lobbyNormal = montarSalaReal({ almacen: almacenNormal });
ok(
  lobbyNormal.boton().children[2].hidden &&
    lobbyNormal.boton()._attrs["aria-label"] === "Pantalla completa",
  "sin fullscreen previo no aparece una recuperación innecesaria"
);

const almacenRechazo = crearAlmacen({
  jugador_id: "jugador-1",
  pantalla_completa_pendiente: JSON.stringify({
    codigo: "JARA-TEST", jugador_id: "jugador-1",
  }),
});
const lobbyRechazo = montarSalaReal({ almacen: almacenRechazo, rechaza: true });
lobbyRechazo.boton().click();
lobbyRechazo.errorFullscreen();
ok(
  lobbyRechazo.doc.fullscreenElement === null &&
    lobbyRechazo.boton().children[2].hidden === false,
  "si el navegador rechaza la solicitud, el lobby sigue estable y permite reintentar"
);

// Sin marco identificado: degradación sin romper la aplicación.
const suelto = montar({ soportado: true, sinMarco: true });
ok(suelto.boton() !== undefined, "sin marco reconocido el control no se pierde");

// La barra compartida controla distribución y tamaño uniforme.
const css = fs.readFileSync(
  path.join(__dirname, "..", "app", "static", "css", "estilos.css"), "utf8");
ok(/\.barra-controles-inferior\s*\{[^}]*display:\s*flex[^}]*gap:\s*6px/.test(css),
  "la barra usa Flexbox y separación uniforme");
ok(/\.barra-controles-inferior > button\s*\{[^}]*width:\s*44px[^}]*height:\s*44px/.test(css),
  "los accesos comparten dimensiones en escritorio");
ok(/\.barra-controles-inferior > \.control-pantalla-completa\s*\{[^}]*order:\s*5/.test(css),
  "pantalla completa queda en el extremo derecho");
ok(/\.barra-controles-inferior > \.control-aprender-sala\s*\{[^}]*order:\s*1/.test(css),
  "instrucciones quedan a la izquierda y se recolocan sin huecos");
ok(/body\.en-partida\s*\{[^}]*--columna-derecha:\s*\d+px/.test(css),
  "el token de columna derecha se define para la partida");
ok(/grid-template-columns:[^;]*var\(--columna-derecha, 280px\)/.test(css),
  "la retícula lateral y el control comparten el mismo token");
ok(/@media \(orientation: landscape\) and \(max-height: 560px\) and \(pointer: coarse\)[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s+minmax\(240px,\s*var\(--columna-derecha,\s*280px\)\)/.test(css),
  "el apaisado bajo mantiene compacta la pista derecha y entrega el resto al tablero");
ok(!/\.medallon\.control-pantalla-completa\s*\{[^}]*top:\s*\d/.test(css),
  "no queda anclado arriba (competía con la cabecera)");
ok(!/\.control-pantalla-completa\s*\{[^}]*position:\s*fixed/.test(css),
  "no queda el fixed que le ganaba a .medallon");
ok(/\.portada-escena,[\s\S]{0,80}body:not\(\.portada\) \.tarjeta\s*\{[^}]*position:\s*relative/.test(css),
  "los marcos canónicos de ambas vistas son reference");

if (fallos) process.exitCode = 1;
else console.log("PANTALLA COMPLETA OK");
