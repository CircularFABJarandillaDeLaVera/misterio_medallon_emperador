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
    title: "",
    type: "",
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

function muestra(estadosPorCategoria) {
  const lista = [];
  const categorias = [
    ["sospechoso", 6],
    ["lugar", 9],
    ["objeto", 6],
  ];
  for (const [categoria, n] of categorias) {
    for (let i = 0; i < n; i += 1) {
      lista.push({
        id: `${categoria}-${i}`,
        nombre: `${categoria} ${i}`,
        categoria,
        estado: estadosPorCategoria[categoria] || "sin_informacion",
      });
    }
  }
  return lista;
}

const hojaDiv = documentStub.getElementById("hoja");

// 1. Renderiza 21 filas agrupadas 6/9/6 con cabeceras plegables.
pintarHoja(muestra({}));
const cabeceras = hojaDiv.querySelectorAll(".hoja-cabecera");
ok(cabeceras.length === 3, "tres cabeceras plegables");
ok(
  cabeceras.map((c) => c.textContent).join("|").includes("(6)") &&
    cabeceras.map((c) => c.textContent).join("|").includes("(9)"),
  "cabeceras muestran conteos 6/9/6"
);
const filas = hojaDiv.querySelectorAll(".hoja-fila");
ok(filas.length === 21, `21 filas visibles (hay ${filas.length})`);
const cuerpos = hojaDiv.querySelectorAll(".hoja-cuerpo");
ok(cuerpos.length === 3, "tres cuerpos de grupo");
ok(
  cuerpos.map((c) => c.querySelectorAll(".hoja-fila").length).join(",") ===
    "6,9,6",
  "filas por grupo 6/9/6"
);

// 2. Plegar una categoría no cierra las otras.
ok(cuerpos.every((c) => c.hidden === false), "grupos abiertos por defecto");
cabeceras[0].click();
ok(cuerpos[0].hidden === true, "SOSPECHOSOS se pliega");
ok(
  cuerpos[1].hidden === false && cuerpos[2].hidden === false,
  "plegar uno no cierra los otros"
);
ok(
  cabeceras[0].getAttribute("aria-expanded") === "false",
  "aria-expanded se actualiza"
);
cabeceras[0].click();
ok(cuerpos[0].hidden === false, "SOSPECHOSOS se despliega");

// 3. Toggle SIN INFORMACIÓN -> DESCARTADA por WebSocket.
enviados.length = 0;
filas[0].click();
ok(
  enviados.length === 1 &&
    enviados[0].accion === "marcar_investigacion" &&
    enviados[0].carta_id === "sospechoso-0" &&
    enviados[0].estado === "descartada",
  "click en SIN INFORMACIÓN envía descartada"
);

// 4. Toggle DESCARTADA -> SIN INFORMACIÓN.
pintarHoja(muestra({ sospechoso: "descartada" }));
const filaDesc = hojaDiv.querySelectorAll(".hoja-fila")[0];
enviados.length = 0;
filaDesc.click();
ok(
  enviados.length === 1 && enviados[0].estado === "sin_informacion",
  "click en DESCARTADA envía sin_informacion"
);

// 5. LA TENGO no es modificable.
pintarHoja(muestra({ sospechoso: "la_tengo" }));
const filaTengo = hojaDiv.querySelectorAll(".hoja-fila")[0];
ok(filaTengo.disabled === true, "LA TENGO deshabilitada");
enviados.length = 0;
filaTengo.click();
ok(enviados.length === 0, "LA TENGO no envía nada");
ok(
  filaTengo.textContent.includes("LA TENGO"),
  "LA TENGO muestra su estado"
);

// 6. Sin datos: aviso visible en vez de tres títulos vacíos.
pintarHoja([]);
ok(
  hojaDiv.querySelectorAll(".hoja-fila").length === 0 &&
    hojaDiv.querySelectorAll(".hoja-cabecera").length === 0 &&
    hojaDiv.textContent.includes("Cargando"),
  "sin datos se avisa en vez de mostrar grupos vacíos"
);
pintarHoja(undefined);
ok(
  hojaDiv.querySelectorAll(".hoja-fila").length === 0 &&
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
  hojaDiv.querySelectorAll(".hoja-fila").length === 22,
  "categoría inesperada también se renderiza"
);

if (fallos > 0) {
  console.log(`${fallos} FALLO(S)`);
  process.exit(1);
}
console.log("HOJA RENDER OK");
