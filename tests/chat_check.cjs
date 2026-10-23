/* Harness del chat: render seguro, pendientes, envío y cierre accesible.
   Uso: node tests/chat_check.cjs */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const raiz = path.join(__dirname, "..");
const leer = (...partes) => fs.readFileSync(path.join(raiz, ...partes), "utf8");
const salaJs = leer("app", "static", "js", "sala.js");
const salaHtml = leer("app", "templates", "_sala_interfaz.html");
const css = leer("app", "static", "css", "estilos.css");

let fallos = 0;
function ok(condicion, nombre) {
  console.log(`${condicion ? "PASS" : "FAIL"} ${nombre}`);
  if (!condicion) fallos += 1;
}

function elemento(tag = "div", id = "") {
  const atributos = {};
  const clases = new Set();
  const el = {
    tag, id, children: [], hidden: false, disabled: false, value: "",
    textContent: "", innerHTML: "", scrollHeight: 0, scrollTop: 0,
    oyentes: {},
    classList: {
      add: (...items) => items.forEach((item) => clases.add(item)),
      remove: (...items) => items.forEach((item) => clases.delete(item)),
      contains: (item) => clases.has(item),
      toggle: (item, fuerza) => {
        if (fuerza === undefined ? !clases.has(item) : fuerza) clases.add(item);
        else clases.delete(item);
      },
    },
    appendChild(hijo) {
      this.children.push(hijo);
      this.scrollHeight = this.children.length;
      return hijo;
    },
    addEventListener(tipo, fn) {
      (this.oyentes[tipo] || (this.oyentes[tipo] = [])).push(fn);
    },
    setAttribute(nombre, valor) { atributos[nombre] = String(valor); },
    getAttribute(nombre) { return atributos[nombre]; },
    querySelector(selector) {
      if (selector === '[role="dialog"]') {
        if (!this._dialogo) this._dialogo = elemento("section");
        return this._dialogo;
      }
      return null;
    },
    querySelectorAll() { return []; },
    focus() { documento.activeElement = this; },
    click() {
      (this.oyentes.click || []).forEach((fn) =>
        fn({ target: this, preventDefault() {} })
      );
    },
    emitir(tipo, evento = {}) {
      (this.oyentes[tipo] || []).forEach((fn) =>
        fn({ target: this, preventDefault() {}, ...evento })
      );
    },
  };
  Object.defineProperty(el, "textContent", {
    get() {
      return this._texto || "";
    },
    set(valor) {
      this.children = [];
      this._texto = String(valor);
    },
  });
  Object.defineProperty(el, "innerHTML", {
    get() {
      return this._html || "";
    },
    set(valor) {
      this.children = [];
      this._html = String(valor);
    },
  });
  if (id === "modal-chat" || id.startsWith("modal-")) el.hidden = true;
  if (id === "chat-pendientes") el.hidden = true;
  return el;
}

const registro = {};
const documento = {
  body: elemento("body"),
  documentElement: elemento("html"),
  activeElement: null,
  oyentes: {},
  getElementById(id) {
    if (!registro[id]) registro[id] = elemento("div", id);
    return registro[id];
  },
  createElement(tag) { return elemento(tag); },
  querySelectorAll(selector) {
    return selector === ".modal" ? [this.getElementById("modal-chat")] : [];
  },
  querySelector(selector) {
    return selector === ".barra-controles-inferior"
      ? this.getElementById("barra-controles-inferior")
      : null;
  },
  addEventListener(tipo, fn) {
    (this.oyentes[tipo] || (this.oyentes[tipo] = [])).push(fn);
  },
  emitir(tipo, evento) {
    (this.oyentes[tipo] || []).forEach((fn) => fn(evento));
  },
};
documento.body.classList.add("en-partida");
documento.getElementById("partida").hidden = false;
documento.getElementById("barra-controles-inferior").hidden = false;

const enviados = [];
class WebSocketFalso {
  constructor() {
    this.readyState = WebSocketFalso.OPEN;
    WebSocketFalso.instancia = this;
  }
  send(texto) { enviados.push(JSON.parse(texto)); }
}
WebSocketFalso.OPEN = 1;

const sandbox = {
  console,
  document: documento,
  window: {
    location: { protocol: "http:", host: "localhost" },
    setTimeout,
    clearTimeout,
  },
  sessionStorage: {
    getItem: (clave) => (clave === "jugador_id" ? "jugador-local" : null),
    setItem() {},
  },
  fetch: () => ({ then() { return this; } }),
  WebSocket: WebSocketFalso,
  setTimeout,
  clearTimeout,
};
vm.createContext(sandbox);
vm.runInContext(salaJs, sandbox, { filename: "sala.js" });

const btnChat = documento.getElementById("btn-chat");
const modalChat = documento.getElementById("modal-chat");
const pendientes = documento.getElementById("chat-pendientes");
const mensajes = documento.getElementById("chat-mensajes");
const formulario = documento.getElementById("chat-formulario");
const entrada = documento.getElementById("chat-entrada");
const dialogo = modalChat.querySelector('[role="dialog"]');
const botonCerrar = documento.getElementById("btn-cerrar-chat");
const botonEnviar = elemento("button");
dialogo.querySelectorAll = () => [botonCerrar, entrada, botonEnviar];
const textoNoSeguro = "<img src=x onerror=alert(1)>";

WebSocketFalso.instancia.onmessage({
  data: JSON.stringify({
    tipo: "chat_mensaje",
    mensaje: {
      jugador_id: "otro-jugador",
      alias: "Bea",
      texto: textoNoSeguro,
    },
  }),
});
ok(pendientes.textContent === "1" && !pendientes.hidden,
  "un mensaje con el chat cerrado activa el indicador");
ok(mensajes.children[0].children[1].textContent === textoNoSeguro
  && mensajes.children[0].children[1].innerHTML === "",
  "el contenido HTML se representa como texto plano");
ok(mensajes.children[0].className === "chat-mensaje chat-mensaje-recibido",
  "los mensajes recibidos se distinguen de los propios");
ok(mensajes.scrollTop === mensajes.scrollHeight,
  "la lista se desplaza hasta el mensaje reciente");

btnChat.click();
ok(!modalChat.hidden && pendientes.hidden
  && btnChat.getAttribute("aria-expanded") === "true",
  "abrir el chat limpia pendientes y actualiza el estado accesible");
botonCerrar.focus();
documento.emitir("keydown", {
  key: "Tab",
  shiftKey: true,
  preventDefault() { this.prevenido = true; },
});
ok(documento.activeElement === botonEnviar,
  "la navegación por teclado queda contenida en el diálogo");
ok(documento.getElementById("barra-controles-inferior").hidden,
  "la barra inferior se oculta mientras el modal está abierto");

entrada.value = "Mensaje con Intro";
formulario.emitir("submit");
ok(enviados.some((mensaje) =>
  mensaje.accion === "chat" && mensaje.texto === "Mensaje con Intro"),
"el formulario envía texto por el WebSocket existente");

documento.emitir("keydown", {
  key: "Escape",
  preventDefault() { this.prevenido = true; },
});
ok(modalChat.hidden && btnChat.getAttribute("aria-expanded") === "false",
  "Escape cierra el chat sin destruir el historial");
ok(!documento.getElementById("barra-controles-inferior").hidden,
  "cerrar el chat vuelve a mostrar la barra");

btnChat.click();
modalChat.emitir("click", { target: modalChat });
ok(modalChat.hidden, "pulsar fuera del diálogo cierra el chat");

WebSocketFalso.instancia.onmessage({
  data: JSON.stringify({
    tipo: "chat_mensaje",
    mensaje: {
      jugador_id: "jugador-local",
      alias: "Ana",
      texto: "Mensaje propio",
    },
  }),
});
ok(mensajes.children.length === 2
  && mensajes.children[1].className === "chat-mensaje chat-mensaje-propio",
  "los mensajes propios conservan una apariencia diferenciada");

ok(salaHtml.includes('id="btn-chat"')
  && salaHtml.includes('maxlength="300"')
  && salaHtml.includes('aria-labelledby="chat-titulo"'),
"la plantilla incluye un botón accesible y un campo limitado a 300 caracteres");
ok(css.includes(".modal-chat-caja")
  && css.includes("100dvh")
  && css.includes(".control-chat"),
"el chat usa el viewport y comparte la barra adaptable del tablero");

if (fallos) process.exit(1);
