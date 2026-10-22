/* Harness del orden móvil real de portada: el documento empieza con la
   preparación compartida y los formularios solo quedan disponibles después.
   Uso: node tests/preparacion_portada_movil_check.cjs */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

let fallos = 0;
function ok(condicion, nombre) {
  console.log(`${condicion ? "PASS" : "FAIL"} ${nombre}`);
  if (!condicion) fallos += 1;
}

function crearEntorno() {
  const elementos = {};
  const clasesHtml = new Set(["preparacion-movil-inicial"]);
  let peticiones = 0;
  let inmersiones = 0;

  const documentStub = {
    activeElement: null,
    body: { classList: { add() {}, remove() {} } },
    documentElement: {
      classList: {
        add(clase) { clasesHtml.add(clase); },
        remove(clase) { clasesHtml.delete(clase); },
        contains(clase) { return clasesHtml.has(clase); },
      },
    },
    getElementById(id) {
      if (!elementos[id]) elementos[id] = crearElemento(id);
      return elementos[id];
    },
    querySelector(selector) {
      return selector === ".portada-escena" ? this.getElementById("portada-escena") : null;
    },
    addEventListener() {},
  };

  function crearElemento(id) {
    const ocultos = new Set([
      "modal-nueva", "modal-unirse", "modal-cargar", "modal-preparacion-movil",
      "envoltorio-modo", "archivo-elegido",
    ]);
    return {
      id,
      hidden: ocultos.has(id),
      value: "",
      textContent: "",
      disabled: false,
      inert: false,
      files: [],
      style: {},
      classList: { add() {}, remove() {} },
      _oyentes: {},
      addEventListener(tipo, fn) { this._oyentes[tipo] = fn; },
      focus() { documentStub.activeElement = this; },
      click() { if (this._oyentes.click) return this._oyentes.click(); },
    };
  }

  const windowStub = {
    location: { href: "" },
    screen: { width: 390, height: 844 },
    innerWidth: 390,
    innerHeight: 844,
    ontouchstart: null,
    matchMedia(consulta) { return { matches: consulta === "(pointer: coarse)" }; },
    addEventListener() {},
    visualViewport: null,
    PantallaCompleta: {
      solicitarInmersionHorizontal() {
        inmersiones += 1;
        return Promise.resolve(false);
      },
    },
    PreparacionPortadaInicial: {
      activa: true,
      omitirHistoriaAutomatica: true,
      tomarControl() {},
    },
  };

  const sandbox = {
    console,
    document: documentStub,
    navigator: { maxTouchPoints: 5, userAgentData: { mobile: true } },
    sessionStorage: { setItem() {}, getItem() { return null; } },
    fetch: async () => {
      peticiones += 1;
      throw new Error("El formulario no debe enviar durante esta prueba de apertura");
    },
    window: windowStub,
  };
  vm.createContext(sandbox);
  vm.runInContext(
    fs.readFileSync(path.join(__dirname, "..", "app", "static", "js", "inicio.js"), "utf8"),
    sandbox,
    { filename: "inicio.js" }
  );
  return {
    elementos,
    peticiones: () => peticiones,
    inmersiones: () => inmersiones,
    focoActivo: () => documentStub.activeElement && documentStub.activeElement.id,
    tieneClaseHtml: (clase) => clasesHtml.has(clase),
    preparacion: () => windowStub.PreparacionPortadaMovil,
  };
}

const casos = [
  ["btn-nueva", "modal-nueva", "alias", "btn-cancelar-nueva", "CREAR"],
  ["btn-unirse", "modal-unirse", "codigo", "btn-cancelar-unirse", "UNIRSE"],
  ["btn-cargar", "modal-cargar", "archivo-partida", "btn-cancelar-cargar", "CARGAR"],
];

for (const [abrir, modal, foco, cancelar, nombre] of casos) {
  const entorno = crearEntorno();
  const { elementos } = entorno;
  ok(
    elementos["modal-preparacion-movil"].hidden === false && elementos[modal].hidden === true,
    `${nombre}: la preparación ya está visible antes de pulsar la portada`
  );
  ok(entorno.tieneClaseHtml("preparacion-movil-activa"), `${nombre}: la portada permanece bloqueada`);
  ok(entorno.peticiones() === 0, `${nombre}: la preparación no envía datos`);

  elementos["btn-entrar-pantalla-completa"].click();
  ok(
    elementos["modal-preparacion-movil"].hidden === true && elementos[modal].hidden === true,
    `${nombre}: completar la preparación muestra la portada sin abrir formularios`
  );
  ok(!entorno.tieneClaseHtml("preparacion-movil-activa"), `${nombre}: desbloquea la portada`);
  ok(entorno.focoActivo() === "btn-nueva", `${nombre}: devuelve el foco a la portada`);
  ok(entorno.inmersiones() === 1, `${nombre}: mantiene la inmersión horizontal progresiva`);

  elementos[abrir].click();
  ok(
    elementos[modal].hidden === false && elementos["modal-preparacion-movil"].hidden === true,
    `${nombre}: el botón abre directamente su formulario original`
  );
  ok(entorno.focoActivo() === foco, `${nombre}: enfoca el campo inicial`);
  elementos[cancelar].click();
  ok(elementos[modal].hidden === true, `${nombre}: cancelar vuelve a la portada`);
}

const continuidad = crearEntorno();
const botonPreparacion = continuidad.elementos["btn-entrar-pantalla-completa"];
const oyenteCompletar = botonPreparacion._oyentes.click;
continuidad.preparacion().inicializar();
ok(botonPreparacion._oyentes.click === oyenteCompletar,
  "reinicializar la primera vista no duplica el evento de preparación");
botonPreparacion.click();
const inmersionesTrasCompletar = continuidad.inmersiones();
continuidad.preparacion().inicializar({ cambioInterno: true });
ok(continuidad.elementos["modal-preparacion-movil"].hidden === true,
  "un cambio interno no repite la preparación cinematográfica");
ok(continuidad.inmersiones() === inmersionesTrasCompletar,
  "un cambio interno no solicita de nuevo fullscreen ni orientación");

if (fallos) process.exitCode = 1;
else console.log("PREPARACIÓN PORTADA MÓVIL OK");
