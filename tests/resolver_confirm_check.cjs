/* Harness: flujo de confirmación de RESOLVER EL MISTERIO sin confirm()
   nativo, anti doble envío y aviso de timeout de refutación.
   Uso: node tests/resolver_confirm_check.cjs */
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

const fuente = fs.readFileSync(
  path.join(__dirname, "..", "app", "static", "js", "sala.js"),
  "utf8"
);
ok(!fuente.includes("window.confirm"), "sin window.confirm en sala.js");
ok(!/[^a-zA-Z]confirm\s*\(/.test(fuente), "sin llamadas confirm(...) en sala.js");
ok(!/[^a-zA-Z]alert\s*\(/.test(fuente), "sin alert(...) en sala.js");
ok(!/[^a-zA-Z]prompt\s*\(/.test(fuente), "sin prompt(...) en sala.js");
ok(fuente.includes("btn-enviar-resolver"), "existe botón de envío único");

function claseLista() {
  const clases = new Set();
  return {
    add(...cs) { cs.forEach((c) => clases.add(c)); },
    remove(...cs) { cs.forEach((c) => clases.delete(c)); },
    toggle(c, f) {
      if (f === undefined) { if (clases.has(c)) clases.delete(c); else clases.add(c); }
      else if (f) clases.add(c); else clases.delete(c);
    },
    contains(c) { return clases.has(c); },
  };
}

function makeElemento(tag) {
  const el = {
    tag,
    children: [],
    className: "",
    classList: claseLista(),
    dataset: {},
    hidden: true,
    disabled: false,
    title: "",
    type: "",
    value: "",
    options: [],
    selectedIndex: -1,
    style: {},
    _texto: "",
    _attrs: {},
    _oyentes: {},
    set textContent(v) {
      this.children = [];
      this._texto = String(v);
    },
    get textContent() {
      return this._texto + this.children.map((c) => c.textContent).join("");
    },
    set innerHTML(v) {
      this.children = [];
      this._texto = "";
      this._html = String(v);
    },
    get innerHTML() {
      return this._html || "";
    },
    appendChild(hijo) {
      this.children.push(hijo);
      return hijo;
    },
    addEventListener(evento, fn) {
      (this._oyentes[evento] = this._oyentes[evento] || []).push(fn);
    },
    setAttribute(k, v) {
      this._attrs[k] = String(v);
    },
    getAttribute(k) {
      return this._attrs[k];
    },
    click() {
      (this._oyentes.click || []).forEach((fn) => fn());
    },
  };
  return el;
}

const registro = {};
const documentStub = {
  getElementById(id) {
    if (!registro[id]) {
      registro[id] = makeElemento("div");
    }
    return registro[id];
  },
  createElement(tag) {
    return makeElemento(tag);
  },
};
registro.codigo = makeElemento("p");
registro.codigo.textContent = "JARA-TEST";

const enviados = [];
class WebSocketFalso {
  constructor() {}
  send(mensaje) {
    enviados.push(JSON.parse(mensaje));
  }
}

const sandbox = {
  console,
  document: documentStub,
  window: { location: { protocol: "http:", host: "localhost:8000" } },
  sessionStorage: { getItem: () => "jug-test", setItem: () => {} },
  fetch: () => ({ then: () => ({ then: () => {} }) }),
  WebSocket: WebSocketFalso,
};
vm.createContext(sandbox);
vm.runInContext(fuente, sandbox, { filename: "sala.js" });

const $ = (id) => documentStub.getElementById(id);

// 0. Resolver ya no usa selects; el modo rápido conserva los suyos.
const htmlSala = fs.readFileSync(
  path.join(__dirname, "..", "app", "templates", "sala.html"),
  "utf8"
);
const css = fs.readFileSync(
  path.join(__dirname, "..", "app", "static", "css", "estilos.css"),
  "utf8"
);
ok(
  !htmlSala.includes('id="resolver-sospechoso"') &&
    !htmlSala.includes('id="resolver-lugar"') &&
    !htmlSala.includes('id="resolver-objeto"'),
  "Resolver sin selects visibles"
);
ok(
  htmlSala.includes('id="sospecha-sospechoso"') &&
    htmlSala.includes('id="sospecha-lugar"') &&
    htmlSala.includes('id="sospecha-objeto"'),
  "modo rápido conserva sus selects"
);
ok(
  htmlSala.includes('id="resolver-grupo-sospechoso"') &&
    htmlSala.includes('id="resolver-grupo-lugar"') &&
    htmlSala.includes('id="resolver-grupo-objeto"'),
  "Resolver ofrece 3 grupos visuales"
);
ok(
  htmlSala.includes('id="modal-resolucion-fallida"') &&
    htmlSala.includes("TU RESOLUCIÓN HA SIDO REFUTADA") &&
    htmlSala.includes("HAS SIDO ELIMINADO COMO INVESTIGADOR") &&
    htmlSala.includes("Conservas tus cartas") &&
    htmlSala.includes("hasta el final de la partida") &&
    !htmlSala.includes("Has perdido la partida"),
  "el popup explica la eliminación como investigador sin expulsar al jugador"
);
ok(
  htmlSala.includes("¿QUIÉN ESCONDIÓ EL MEDALLÓN?") &&
    htmlSala.includes("¿EN QUÉ LUGAR?") &&
    htmlSala.includes("¿DÓNDE LO ESCONDIÓ?"),
  "Resolver formula persona, lugar y escondite con la semántica correcta"
);
ok(
  htmlSala.includes('id="btn-confirmar-resolver" class="medallon medallon-primario medallon-compacto"') &&
    htmlSala.includes('id="btn-cancelar-resolver" class="medallon medallon-fantasma medallon-compacto"') &&
    /\.modal-resolver-caja > \.medallon-compacto\s*\{[^}]*width:\s*100%[^}]*min-height:\s*38px/s.test(css) &&
    /#btn-confirmar-resolver\s*\{[^}]*grid-column:\s*1[^}]*grid-row:\s*9/s.test(css) &&
    /#btn-cancelar-resolver\s*\{[^}]*grid-column:\s*2[^}]*grid-row:\s*9/s.test(css),
  "Resolver reutiliza medallones canónicos en una fila compacta"
);
ok(
  /\.modal-resolver-caja\s*\{[^}]*width:\s*calc\(100dvw - 12px\)[^}]*height:\s*calc\(100dvh - 12px\)[^}]*grid-template-rows:[^}]*minmax\(0, 1fr\)/s.test(css) &&
    /\.selector-cartas-resolver\[data-categoria="sospechoso"\][^}]*repeat\(6, minmax\(0, 1fr\)\)/s.test(css) &&
    /\.selector-cartas-resolver\[data-categoria="lugar"\][^}]*repeat\(9, minmax\(0, 1fr\)\)/s.test(css) &&
    /\.selector-cartas-resolver\[data-categoria="objeto"\][^}]*repeat\(6, minmax\(0, 1fr\)\)/s.test(css),
  "Resolver reutiliza la geometría viewport-protagonista de Investigación"
);
ok(
  /\.modal-resolver-caja > \.resolver-pregunta[^}]*white-space:\s*nowrap/s.test(css) &&
    /\.modal-resolver-caja > \.nota-privada[^}]*font-size:\s*clamp/s.test(css),
  "cabecera, aviso y preguntas de Resolver permanecen en una línea"
);

// 1. Abrir selección y pasar a confirmación con los nombres visibles.
vm.runInContext(`ultimaSala = {
  investigacion: [
    { id: "vera", nombre: "Vera", categoria: "sospechoso", estado: "sin_informacion" },
    { id: "bruno", nombre: "Bruno", categoria: "sospechoso", estado: "sin_informacion" },
    { id: "parador", nombre: "Parador", categoria: "lugar", estado: "sin_informacion" },
    { id: "picota", nombre: "Picota", categoria: "lugar", estado: "sin_informacion" },
    { id: "baul-imperial", nombre: "Baúl Imperial", categoria: "objeto", estado: "sin_informacion" },
    { id: "libro-hueco", nombre: "Libro Hueco", categoria: "objeto", estado: "sin_informacion" }
  ],
  mis_cartas: [{ id: "vera", nombre: "Vera", categoria: "sospechoso" }]
};`, sandbox);
function pulsarCarta(grupoId, indice = 0) {
  const botones = $(grupoId).children.filter((h) => h.tag === "button");
  botones[indice].click();
  return botones;
}
$("modal-resolver").hidden = true;
$("modal-confirmar-resolver").hidden = true;
$("btn-resolver").click();
ok($("modal-resolver").hidden === false, "RESOLVER abre el modal de selección");
ok($("btn-confirmar-resolver").disabled === true, "CONTINUAR exige las tres selecciones");
const cartasS = pulsarCarta("resolver-grupo-sospechoso", 0);
ok(cartasS.length === 2, "el grupo muestra los sospechosos disponibles");
pulsarCarta("resolver-grupo-lugar", 0);
ok($("btn-confirmar-resolver").disabled === true, "con dos selecciones sigue bloqueado");
pulsarCarta("resolver-grupo-objeto", 0);
ok($("btn-confirmar-resolver").disabled === false, "con tres selecciones se habilita");
// Exclusividad: una nueva selección sustituye a la anterior.
pulsarCarta("resolver-grupo-sospechoso", 1);
ok(
  cartasS.filter((b) => b.classList.contains("seleccionada")).length === 1,
  "una sola carta seleccionada por categoría"
);
pulsarCarta("resolver-grupo-sospechoso", 0);
ok(
  $("resolver-grupo-sospechoso").textContent.includes("TU CARTA"),
  "la carta propia se identifica y sigue seleccionable"
);
$("btn-confirmar-resolver").click();
ok(enviados.length === 0, "CONTINUAR no envía WebSocket");
ok($("modal-resolver").hidden === true, "CONTINUAR cierra la selección");
ok(
  $("modal-confirmar-resolver").hidden === false,
  "CONTINUAR abre la confirmación integrada"
);
const figuras = $("conf-resolver-cartas").children;
ok(figuras.length === 3, "la confirmación muestra exactamente 3 cartas");
ok(
  figuras.every((f) => f.tag === "div"),
  "las cartas de confirmación no son seleccionables"
);
ok(
  figuras[0].getAttribute("aria-label") === "Vera" &&
    figuras[1].getAttribute("aria-label") === "Parador" &&
    figuras[2].getAttribute("aria-label") === "Baúl Imperial",
  "las cartas corresponden a los tres IDs en orden sospechoso/lugar/escondite"
);
ok(
  !$("conf-resolver-cartas").textContent.includes("TU CARTA") &&
    !$("conf-resolver-cartas").textContent.includes("VISTA") &&
    !$("conf-resolver-cartas").textContent.includes("DESCARTADA"),
  "la confirmación no muestra insignias de conocimiento"
);

// 2. Un solo envío aunque haya doble clic.
enviados.length = 0;
$("btn-enviar-resolver").click();
$("btn-enviar-resolver").click();
const acusaciones = enviados.filter((m) => m.accion === "resolver_misterio");
ok(acusaciones.length === 1, "doble clic envía exactamente una acusación");
ok(
  acusaciones[0].sospechoso_id === "vera" &&
    acusaciones[0].lugar_id === "parador" &&
    acusaciones[0].objeto_id === "baul-imperial",
  "la acusación lleva los valores elegidos"
);
ok(
  $("modal-confirmar-resolver").hidden === true,
  "enviar cierra la confirmación"
);

// El estado canónico confirma el fallo local: se reutilizan exactamente
// las tres cartas enviadas, sin recibir ni inferir la solución real.
$('modal-resolucion-fallida').hidden = true;
sandbox.presentarResolucionFallida({
  activo_investigacion: false,
  jugada: { tipo: "acusacion", resultado: "acusacion_incorrecta" },
});
ok(
  $("modal-resolucion-fallida").hidden === false &&
    $("resolucion-fallida-cartas").children.length === 3,
  "el fallo local abre el popup con exactamente tres cartas"
);
ok(
  $("resolucion-fallida-cartas").children.map((c) => c.getAttribute("aria-label")).join("|") ===
    "Vera|Parador|Baúl Imperial",
  "el popup reconstruye la combinación local enviada"
);
ok(
  !$("resolucion-fallida-cartas").textContent.includes("✓") &&
    !$("resolucion-fallida-cartas").textContent.includes("✗"),
  "el popup no identifica aciertos ni fallos parciales"
);
$("btn-continuar-resolucion-fallida").click();
ok(
  $("modal-resolucion-fallida").hidden === true,
  "CONTINUAR solo cierra el popup y devuelve al tablero"
);

// Sin una acusación pendiente local (recarga, rival o PNJ), el mismo
// resultado público no abre información detallada.
sandbox.presentarResolucionFallida({
  activo_investigacion: false,
  jugada: { tipo: "acusacion", resultado: "acusacion_incorrecta" },
});
ok(
  $("modal-resolucion-fallida").hidden === true,
  "recarga, rival o PNJ no abren el popup local"
);

// 3. CANCELAR no envía nada y conserva la selección.
enviados.length = 0;
$("btn-resolver").click();
pulsarCarta("resolver-grupo-sospechoso", 0);
pulsarCarta("resolver-grupo-lugar", 0);
pulsarCarta("resolver-grupo-objeto", 0);
$("btn-confirmar-resolver").click();
$("btn-cancelar-confirmar-resolver").click();
ok(
  enviados.filter((m) => m.accion === "resolver_misterio").length === 0,
  "CANCELAR no modifica ningún estado ni envía"
);
ok(
  $("modal-confirmar-resolver").hidden === true &&
    $("modal-resolver").hidden === false,
  "CANCELAR vuelve a la selección conservando valores"
);

// 4. Reconfirmar rearma el envío único.
enviados.length = 0;
$("btn-confirmar-resolver").click();
$("btn-enviar-resolver").click();
ok(
  enviados.filter((m) => m.accion === "resolver_misterio").length === 1,
  "reconfirmar permite un nuevo envío único"
);
sandbox.presentarResolucionFallida({
  activo_investigacion: true,
  jugada: { tipo: "acusacion", resultado: "resuelto" },
});
ok(
  $("modal-resolucion-fallida").hidden === true,
  "una resolución correcta conserva el flujo final y no abre el popup de fallo"
);

// 5. Aviso de timeout solo con plazo server-side.
const pintarJugada = sandbox.pintarJugada;
ok(typeof pintarJugada === "function", "pintarJugada existe en sala.js");
function salaBase(jugada) {
  return {
    jugada,
    jugadores: [],
    orden: [],
    estado: "iniciada",
    es_mi_turno: false,
    activo_investigacion: false,
    turno_alias: "X",
  };
}
pintarJugada(
  salaBase({
    estado: "esperando_eleccion_refutador",
    opciones_refutacion: [{ id: "vera", nombre: "Vera" }],
    timeout_refutacion_seg: 3,
  })
);
ok(
  $("aviso-timeout-refutacion").hidden === false &&
    $("aviso-timeout-refutacion").textContent.includes("servidor"),
  "con plazo se avisa del timeout server-side"
);
pintarJugada(
  salaBase({
    estado: "esperando_eleccion_refutador",
    opciones_refutacion: [{ id: "vera", nombre: "Vera" }],
  })
);
ok(
  $("aviso-timeout-refutacion").hidden === true,
  "sin plazo no hay aviso de timeout"
);

// 6. Revelación visual: solo aparece cuando el privado incluye carta_mostrada.
enviados.length = 0;
pintarJugada(salaBase({
  estado: "esperando_eleccion_refutador",
  opciones_refutacion: [{ id: "vera", nombre: "Vera", categoria: "sospechoso" }],
}));
ok($("modal-refutacion").hidden === false, "una coincidencia abre la refutacion visual");
ok(
  $("opciones-refutacion").children.length === 1 &&
    $("opciones-refutacion").children[0].classList.contains("seleccionada"),
  "la unica carta queda preseleccionada"
);
ok($("btn-confirmar-refutacion").disabled === false, "REFUTAR queda disponible con una carta");
ok(enviados.length === 0, "una coincidencia humana no se envia automaticamente");
$("opciones-refutacion").children[0].click();
ok(
  $("modal-refutacion").hidden === false &&
    $("modal-revelacion-refutacion").hidden === true &&
    $("opciones-refutacion").children.length === 1 && enviados.length === 0,
  "pulsar la unica carta conserva el mismo popup y no abre una confirmacion"
);
$("btn-confirmar-refutacion").click();
ok(
  enviados.length === 1 && enviados[0].accion === "mostrar_carta" &&
    enviados[0].carta_id === "vera",
  "REFUTAR envia la unica carta una sola vez"
);
$("btn-confirmar-refutacion").click();
ok(enviados.length === 1, "REFUTAR bloquea el doble envio");

enviados.length = 0;
const jugadaRefutacionMultiple = {
  estado: "esperando_eleccion_refutador",
  opciones_refutacion: [
    { id: "vera", nombre: "Vera", categoria: "sospechoso" },
    { id: "parador", nombre: "Parador", categoria: "lugar" },
    { id: "cantaro-barro", nombre: "Cantaro", categoria: "objeto" },
  ],
};
pintarJugada(salaBase(jugadaRefutacionMultiple));
ok($("btn-confirmar-refutacion").disabled === true, "varias cartas exigen elegir una");
$("opciones-refutacion").children[0].click();
ok(
  $("modal-refutacion").hidden === false &&
    $("modal-revelacion-refutacion").hidden === true &&
    $("opciones-refutacion").children.length === 3 &&
    $("btn-confirmar-refutacion").disabled === false && enviados.length === 0,
  "seleccionar mantiene todas las cartas en el unico popup y habilita REFUTAR"
);
pintarJugada(salaBase(jugadaRefutacionMultiple));
ok(
  $("opciones-refutacion").children[0].classList.contains("seleccionada") &&
    $("btn-confirmar-refutacion").disabled === false,
  "una redifusion conserva la seleccion local mientras siga siendo valida"
);
$("opciones-refutacion").children[2].click();
ok(
  !$("opciones-refutacion").children[0].classList.contains("seleccionada") &&
    $("opciones-refutacion").children[2].classList.contains("seleccionada") &&
    $("opciones-refutacion").children.length === 3 &&
    $("modal-refutacion").hidden === false &&
    $("modal-revelacion-refutacion").hidden === true && enviados.length === 0,
  "la seleccion de refutacion es exclusiva"
);
$("btn-confirmar-refutacion").click();
ok(
  enviados.length === 1 && enviados[0].carta_id === "cantaro-barro",
  "REFUTAR envia solo la carta elegida"
);
pintarJugada(salaBase({ estado: "presentando_sospecha", resultado: "pendiente" }));
ok($("modal-refutacion").hidden === true, "8B.30 no abre la refutacion antes de tiempo");

vm.runInContext(`RECURSOS_VISUALES = {
  vera: { principal: "/static/img/personajes/vera.png", nombre: "/static/img/personajes/vera-nombre.png" },
  parador: { principal: "/static/img/lugares/parador.jpeg" },
  "cantaro-barro": { principal: "/static/img/objetos/cantaro-barro.jpeg" }
};`, sandbox);

function jugadaRefutada(carta, refutador = "Bruno") {
  return {
    estado: "esperando_movimiento",
    resultado: "refutada",
    investigador_alias: "Yo",
    refutador_alias: refutador,
    sospecha: {
      sospechoso_id: { id: "vera", nombre: "Vera" },
      lugar_id: { id: "parador", nombre: "Parador" },
      objeto_id: { id: "cantaro-barro", nombre: "Cántaro de barro" },
    },
    carta_mostrada: carta,
  };
}

const revelacionPersonaje = jugadaRefutada({
  id: "vera", nombre: "Vera, la cronista", categoria: "sospechoso",
});
pintarJugada(salaBase(revelacionPersonaje));
ok(
  $("modal-revelacion-refutacion").hidden === false &&
    $("revelacion-refutador").textContent === "BRUNO REFUTA TU SOSPECHA",
  "investigador ve quién refuta"
);
ok(
  $("revelacion-carta-imagen").src === "/static/img/personajes/vera-nombre.png" &&
    $("revelacion-carta-nombre").textContent === "Vera, la cronista",
  "personaje revelado usa la variante con nombre"
);
const enviosAntesContinuar = enviados.length;
$("btn-continuar-revelacion").click();
ok(
  $("modal-revelacion-refutacion").hidden && enviados.length === enviosAntesContinuar,
  "CONTINUAR solo cierra la presentación"
);
pintarJugada(salaBase(revelacionPersonaje));
ok($("modal-revelacion-refutacion").hidden, "el mismo estado no reabre la revelación descartada");

// Un estado sin carta privada limpia el ciclo y no revela nada a terceros.
pintarJugada(salaBase({
  estado: "esperando_movimiento", resultado: "refutada",
  investigador_alias: "Otra", refutador_alias: "Bruno",
}));
ok($("modal-revelacion-refutacion").hidden, "otro cliente no ve la carta mostrada");

const revelacionLugar = jugadaRefutada({
  id: "parador", nombre: "Parador", categoria: "lugar",
});
pintarJugada(salaBase(revelacionLugar));
ok(
  $("revelacion-carta-imagen").src === "/static/img/lugares/parador.jpeg",
  "lugar revelado usa su JPEG original"
);
$("btn-continuar-revelacion").click();
pintarJugada(salaBase({ estado: "esperando_movimiento", resultado: "sin_refutacion" }));
ok($("modal-revelacion-refutacion").hidden, "sospecha sin refutación no abre revelación");

const revelacionPnj = jugadaRefutada({
  id: "cantaro-barro", nombre: "Cántaro de barro", categoria: "objeto",
}, "Mateo PNJ");
pintarJugada(salaBase(revelacionPnj));
ok(
  $("revelacion-refutador").textContent === "MATEO PNJ REFUTA TU SOSPECHA" &&
    $("revelacion-carta-imagen").src === "/static/img/objetos/cantaro-barro.jpeg",
  "PNJ produce la misma revelación privada con la imagen del objeto"
);

// 8B.30: presentación pública previa a la refutación, con confirmación
// asociada inequívocamente al id canónico del servidor.
function jugadaPresentacion(id, pendiente = true) {
  return {
    estado: "presentando_sospecha",
    investigador_alias: "Bruno",
    presentacion_id: id,
    presentacion_pendiente: pendiente,
    sospecha: {
      sospechoso_id: { id: "vera", nombre: "Vera" },
      lugar_id: { id: "parador", nombre: "Parador" },
      objeto_id: { id: "baul-imperial", nombre: "Baúl Imperial" },
    },
  };
}

enviados.length = 0;
pintarJugada(salaBase(jugadaPresentacion(41)));
ok(
  $("modal-presentacion-sospecha").hidden === false &&
    $("presentacion-sospecha-titulo").textContent === "SOSPECHA DE BRUNO" &&
    $("presentacion-sospecha-cartas").children.length === 3,
  "humano ajeno ve autor y las tres cartas de la sospecha"
);
$("btn-continuar-presentacion-sospecha").click();
$("btn-continuar-presentacion-sospecha").click();
ok(
  enviados.filter((m) => m.accion === "confirmar_presentacion_sospecha").length === 1 &&
    enviados.at(-1).presentacion_id === 41 &&
    $("modal-presentacion-sospecha").hidden,
  "CONTINUAR envía una sola confirmación ligada a la presentación y cierra"
);
pintarJugada(salaBase(jugadaPresentacion(41)));
ok($("modal-presentacion-sospecha").hidden, "una redifusión no reabre tras confirmar");
pintarJugada(salaBase(jugadaPresentacion(42, false)));
ok($("modal-presentacion-sospecha").hidden, "el autor o un humano ya listo no ve popup");
pintarJugada(salaBase(jugadaPresentacion(43)));
ok($("modal-presentacion-sospecha").hidden === false, "otra presentación tiene identidad independiente");
pintarJugada(salaBase({ estado: "esperando_sospecha", resultado: "sin_refutacion" }));
ok($("modal-presentacion-sospecha").hidden, "avance canónico o timeout retira el popup");

if (fallos > 0) {
  console.log(`${fallos} FALLO(S)`);
  process.exit(1);
}
console.log("RESOLVER CONFIRM OK");
