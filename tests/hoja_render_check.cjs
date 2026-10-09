/* Harness: ejecuta la función REAL pintarHoja() de app/static/js/sala.js
   con un DOM mínimo y verifica agrupación 6/9/6, plegables y toggles.
   Uso: node tests/hoja_render_check.cjs */
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

function makeElemento(tag) {
  const el = {
    tag,
    children: [],
    className: "",
    hidden: false,
    disabled: false,
    dataset: {},
    title: "",
    type: "",
    style: {},
    _texto: "",
    _attrs: {},
    _oyentes: {},
    classList: {
      add(clase) { if (!el.className.split(/\s+/).includes(clase)) el.className += ` ${clase}`; },
      remove(clase) { el.className = el.className.split(/\s+/).filter((c) => c && c !== clase).join(" "); },
      contains(clase) { return el.className.split(/\s+/).includes(clase); },
    },
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
    querySelector(selector) {
      return selector === '[role="dialog"]' ? makeElemento("section") : null;
    },
    click() {
      (this._oyentes.click || []).forEach((fn) => fn());
    },
    querySelectorAll(selector) {
      const encontrados = [];
      const esClase = selector.startsWith(".");
      const nombre = esClase ? selector.slice(1) : selector;
      const visita = (nodo) => {
        for (const hijo of nodo.children) {
          const coincide = esClase
            ? String(hijo.className || "").split(" ").includes(nombre)
            : hijo.tag === nombre;
          if (coincide) {
            encontrados.push(hijo);
          }
          visita(hijo);
        }
      };
      visita(this);
      return encontrados;
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
const rutaSala = path.join(__dirname, "..", "app", "static", "js", "sala.js");
vm.runInContext(fs.readFileSync(rutaSala, "utf8"), sandbox, {
  filename: "sala.js",
});

const pintarHoja = sandbox.pintarHoja;
ok(typeof pintarHoja === "function", "pintarHoja existe en sala.js");
const css = fs.readFileSync(path.join(__dirname, "..", "app", "static", "css", "estilos.css"), "utf8");
ok(/nth-child\(1\)[^}]*repeat\(6, minmax\(0, 1fr\)\)/s.test(css) &&
  /nth-child\(2\)[^}]*repeat\(9, minmax\(0, 1fr\)\)/s.test(css) &&
  /nth-child\(3\)[^}]*repeat\(6, minmax\(0, 1fr\)\)/s.test(css),
  "grids de Investigación distribuyen 6/9/6 sin overflow horizontal");
ok(/#modal-hoja \.modal-caja\s*\{[^}]*width:\s*calc\(100dvw - 12px\)[^}]*height:\s*calc\(100dvh - 12px\)[^}]*grid-template-rows:\s*auto auto minmax\(0, 1fr\) auto auto/s.test(css) &&
  /#modal-hoja #hoja\s*\{[^}]*grid-template-rows:\s*repeat\(3, minmax\(0, 1fr\)\)/s.test(css),
  "Investigación limita el contenedor por viewport y cede el resto a las tres zonas");
ok(/\.selector-cartas-sospecha\s*\{[^}]*repeat\(6, minmax\(0, 170px\)\)/s.test(css) &&
  /data-categoria="sospechoso"[^}]*height:\s*125px/s.test(css) &&
  /data-categoria="objeto"[^}]*height:\s*115px/s.test(css),
  "el selector de sospecha usa 6 columnas grandes controladas");
ok(/\.carta-visual-compacta\s*\{[^}]*height:\s*100%/s.test(css) &&
  /\.carta-visual-compacta img\s*\{[^}]*height:\s*100%/s.test(css) &&
  !/#hoja[^}]*\.carta-visual-compacta img\s*\{[^}]*height:\s*(?:80|84|78)px/s.test(css),
  "Investigación deja crecer las cartas con su zona sin alturas fijas por categoría");
ok(/\.carta-visual-compacta img\s*\{[^}]*aspect-ratio:\s*auto[^}]*object-fit:\s*contain/s.test(css),
  "miniaturas compactas no se deforman ni heredan la proporción alta");

function muestra(estadosPorCategoria) {
  const lista = [];
  const categorias = [
    ["sospechoso", ["vera", "bruno", "lucia", "alvaro", "mateo", "eulalia"]],
    ["lugar", ["parador", "iglesia-san-agustin", "ermita-sopetran", "picota", "plaza-constitucion", "cristo-humilladero", "puente-parral", "museo-escobazos", "nuestra-senora-torre"]],
    ["objeto", ["baul-imperial", "cantaro-barro", "saco-pimenton", "zurron-cuero", "caja-herramientas", "libro-hueco"]],
  ];
  for (const [categoria, ids] of categorias) {
    for (const id of ids) {
      lista.push({
        id,
        nombre: id,
        categoria,
        estado: estadosPorCategoria[categoria] || "sin_informacion",
      });
    }
  }
  return lista;
}

const hojaDiv = documentStub.getElementById("hoja");

const lista = muestra({});
const recursos = Object.fromEntries(lista.map((carta) => [carta.id, {
  nombre: carta.categoria === "sospechoso" ? `/static/img/personajes/${carta.id}-nombre.png` : undefined,
  principal: `/static/img/${carta.categoria === "objeto" ? "objetos" : carta.categoria === "lugar" ? "lugares" : "personajes"}/${carta.id}.${carta.categoria === "sospechoso" ? "png" : "jpeg"}`,
}]));
vm.runInContext(`RECURSOS_VISUALES = ${JSON.stringify(recursos)}`, sandbox);
const propias = [lista[0]];

// 1. Renderiza 21 cartas visuales agrupadas 6/9/6.
pintarHoja(lista, propias);
const cartas = hojaDiv.querySelectorAll(".carta-visual-compacta");
ok(cartas.length === 21, `21 cartas visuales (hay ${cartas.length})`);
const cuerpos = hojaDiv.querySelectorAll(".hoja-cuerpo");
ok(cuerpos.length === 3, "tres cuerpos de grupo");
ok(
  cuerpos.map((c) => c.querySelectorAll(".carta-visual-compacta").length).join(",") ===
    "6,9,6",
  "cartas por grupo 6/9/6"
);
ok(cuerpos.every((c) => c.hidden === false), "los tres grupos quedan visibles");
ok(cartas[0].children[0].src === "/static/img/personajes/vera-nombre.png" &&
  cartas[1].children[0].src === "/static/img/personajes/bruno-nombre.png", "Vera y Bruno reciben sus URLs runtime finales");
ok(cartas[6].children[0].src === "/static/img/lugares/parador.jpeg" &&
  cartas[7].children[0].src === "/static/img/lugares/iglesia-san-agustin.jpeg" &&
  !cartas[6].children[0].src.includes("tablero_"), "Parador e Iglesia usan JPEG runtime original");
ok(cartas[15].children[0].src === "/static/img/objetos/baul-imperial.jpeg" &&
  cartas[16].children[0].src === "/static/img/objetos/cantaro-barro.jpeg", "Baúl y Cántaro reciben sus recursos runtime finales");
ok(cartas.every((carta) => carta.classList.contains("carta-visual-compacta")), "Investigación usa exclusivamente la variante compacta");
ok(hojaDiv.querySelectorAll(".carta-selector-nombre").length === 0 &&
  cartas.every((carta) => String(carta.getAttribute("aria-label") || "").length > 0),
  "Investigación elimina nombres visibles sin perder nombres accesibles");
ok(cartas[0].textContent.includes("TU CARTA"), "TU CARTA procede de mis_cartas");

// 3. Toggle SIN INFORMACIÓN -> DESCARTADA por WebSocket.
enviados.length = 0;
cartas[1].click();
ok(
  enviados.length === 1 &&
    enviados[0].accion === "marcar_investigacion" &&
    enviados[0].carta_id === "bruno" &&
    enviados[0].estado === "descartada",
  "click en SIN INFORMACIÓN envía descartada"
);

// 4. Toggle DESCARTADA -> SIN INFORMACIÓN.
pintarHoja(muestra({ sospechoso: "descartada" }), []);
const filaDesc = hojaDiv.querySelectorAll(".carta-visual-compacta")[0];
enviados.length = 0;
filaDesc.click();
ok(
  enviados.length === 1 && enviados[0].estado === "sin_informacion",
  "click en DESCARTADA envía sin_informacion"
);
ok(filaDesc.classList.contains("descartada") && filaDesc.textContent.includes("DESCARTADA") && !filaDesc.children[0].hidden,
  "DESCARTADA conserva imagen reconocible y marca visual");

// 5. TU CARTA y VISTA no son modificables.
pintarHoja(lista.map((c, i) => i === 1 ? { ...c, estado: "vista" } : c), propias);
const confirmadas = hojaDiv.querySelectorAll(".carta-visual-compacta");
enviados.length = 0;
confirmadas[0].click();
confirmadas[1].click();
ok(enviados.length === 0, "TU CARTA y VISTA no envían cambios");
ok(confirmadas[0].textContent.includes("TU CARTA") && confirmadas[1].textContent.includes("VISTA"), "estados confirmados permanecen visibles");

// 6. Sin datos: aviso visible en vez de tres títulos vacíos.
pintarHoja([]);
ok(
  hojaDiv.querySelectorAll(".carta-visual-compacta").length === 0 &&
    hojaDiv.textContent.includes("Cargando"),
  "sin datos se avisa en vez de mostrar grupos vacíos"
);
pintarHoja(undefined);
ok(
  hojaDiv.querySelectorAll(".carta-visual-compacta").length === 0 &&
    hojaDiv.textContent.includes("Cargando"),
  "investigacion ausente también avisa"
);

// 7. Categoría inesperada: se muestra, no se oculta.
const rara = muestra({});
rara.push({
  id: "rara-1",
  nombre: "Rara",
  categoria: "pasadizo",
  estado: "sin_informacion",
});
pintarHoja(rara);
ok(
  hojaDiv.querySelectorAll(".carta-visual-compacta").length === 22,
  "categoría inesperada también se renderiza"
);

if (fallos > 0) {
  console.log(`${fallos} FALLO(S)`);
  process.exit(1);
}
console.log("HOJA RENDER OK");
