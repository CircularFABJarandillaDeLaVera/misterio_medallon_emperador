/* Sala: sincronización en tiempo real por WebSocket (Microfase 4B).
   Cada conexión recibe solo su estado privado: nunca ve las
   cartas ni la hoja de investigación de otros jugadores,
   ni el misterio secreto. */
"use strict";

const codigo = document.getElementById("codigo").textContent.trim();
const jugadorId = sessionStorage.getItem("jugador_id") || "";

const lista = document.getElementById("jugadores");
const estado = document.getElementById("estado");
const error = document.getElementById("error");
const btnComenzar = document.getElementById("btn-comenzar");
const lobbyPersonajes = document.getElementById("lobby-personajes");
const personajesDiv = document.getElementById("personajes");
const partida = document.getElementById("partida");
const turnoP = document.getElementById("turno");
const ordenOl = document.getElementById("orden");
const cartasDiv = document.getElementById("mis-cartas");
const total = document.getElementById("total");
const modalCartas = document.getElementById("modal-cartas");
const modalHoja = document.getElementById("modal-hoja");
const hojaDiv = document.getElementById("hoja");
const errorHoja = document.getElementById("error-hoja");
const btnVerHoja = document.getElementById("btn-ver-hoja");
const btnVerCartas = document.getElementById("btn-ver-cartas");
const btnCerrarHoja = document.getElementById("btn-cerrar-hoja");
const btnCerrarCartas = document.getElementById("btn-cerrar-cartas");
const jugadaDiv = document.getElementById("jugada");
const btnSospecha = document.getElementById("btn-sospecha");
const modalSospecha = document.getElementById("modal-sospecha");
const modalRefutacion = document.getElementById("modal-refutacion");
const opcionesRefutacion = document.getElementById("opciones-refutacion");
const selectSospechoso = document.getElementById("sospecha-sospechoso");
const selectLugar = document.getElementById("sospecha-lugar");
const selectObjeto = document.getElementById("sospecha-objeto");
const btnResolver = document.getElementById("btn-resolver");
const modalResolver = document.getElementById("modal-resolver");
const resolverSospechoso = document.getElementById("resolver-sospechoso");
const resolverLugar = document.getElementById("resolver-lugar");
const resolverObjeto = document.getElementById("resolver-objeto");
const modalConfirmarResolver = document.getElementById("modal-confirmar-resolver");
const btnEnviarResolver = document.getElementById("btn-enviar-resolver");
const confResolverSospechoso = document.getElementById("conf-resolver-sospechoso");
const confResolverLugar = document.getElementById("conf-resolver-lugar");
const confResolverObjeto = document.getElementById("conf-resolver-objeto");
const avisoTimeoutRefutacion = document.getElementById("aviso-timeout-refutacion");
const finalPartida = document.getElementById("final-partida");
const modoPartida = document.getElementById("modo-partida");
const movimientoDiv = document.getElementById("movimiento");
const posicionActual = document.getElementById("posicion-actual");
const resultadoDado = document.getElementById("resultado-dado");
const btnTirar = document.getElementById("btn-tirar");
const btnPasadizo = document.getElementById("btn-pasadizo");
const destinosMovimiento = document.getElementById("destinos-movimiento");
const tableroVisual = document.getElementById("tablero-visual");
const tableroAyuda = document.getElementById("tablero-ayuda");
const tableroCanvasContenedor = document.getElementById("tablero-canvas-contenedor");
const tableroCanvas = document.getElementById("tablero-canvas");
const tableroCanvasAccesible = document.getElementById("tablero-canvas-accesible");
const modalUbicacion = document.getElementById("modal-ubicacion");
const modalUbicacionCaja = document.getElementById("modal-ubicacion-caja");
const imagenUbicacion = document.getElementById("imagen-ubicacion");
const btnCerrarUbicacion = document.getElementById("btn-cerrar-ubicacion");
const btnMoverUbicacionCanvas = document.getElementById("btn-mover-ubicacion-canvas");
let focoAntesDeUbicacion = null;
let destinoUbicacionModal = null;
let rendererCanvas = null;
let canvasFallido = false;

if (!jugadorId) {
  window.location.href = "/";
}

let PERSONAJES = [];
fetch("/api/personajes")
  .then((r) => r.json())
  .then((datos) => {
    PERSONAJES = datos.personajes;
    if (ultimaSala) {
      pintarPersonajes(ultimaSala);
    }
  });

let ultimaSala = null;
let TABLERO_VISUAL = null;

const cargaTableroVisual = fetch("/api/tablero")
  .then((r) => {
    if (!r.ok) throw new Error(`GET /api/tablero: HTTP ${r.status}`);
    return r.json();
  })
  .then((datos) => {
    TABLERO_VISUAL = datos.tablero;
    if (ultimaSala) {
      pintarTablero(ultimaSala);
    }
  });
if (cargaTableroVisual && typeof cargaTableroVisual.catch === "function") {
  cargaTableroVisual.catch((fallo) => {
    console.error("No se pudo cargar el tablero visual.", fallo);
    if (ultimaSala && ultimaSala.modo === "tablero") {
      tableroVisual.hidden = false;
      tableroAyuda.textContent =
        "No se pudo cargar el tablero visual. Recarga la página para reintentarlo.";
      tableroAyuda.classList.add("error");
    }
  });
}

const protocolo = window.location.protocol === "https:" ? "wss" : "ws";
const ws = new WebSocket(
  `${protocolo}://${window.location.host}/ws/${encodeURIComponent(codigo)}/${encodeURIComponent(jugadorId)}`
);

ws.onmessage = (evento) => {
  const mensaje = JSON.parse(evento.data);
  if (mensaje.tipo === "estado_privado") {
    ultimaSala = mensaje.sala;
    pintarSala(mensaje.sala);
  } else if (mensaje.tipo === "error") {
    error.textContent = mensaje.detalle;
  }
};

ws.onclose = () => {
  estado.textContent = "Conexión perdida. Recarga la página para reintentar.";
};

const TITULOS = {
  sospechoso: "SOSPECHOSOS",
  lugar: "LUGARES",
  objeto: "OBJETOS",
};

const ETIQUETA_ESTADO = {
  sin_informacion: "SIN INFORMACIÓN",
  la_tengo: "LA TENGO",
  descartada: "DESCARTADA",
  vista: "VISTA",
};

function aliasDePersonaje(sala, personajeId) {
  const j = sala.jugadores.find((x) => x.personaje_id === personajeId);
  return j ? j.alias : null;
}

function pintarPersonajes(sala) {
  personajesDiv.innerHTML = "";
  PERSONAJES.forEach((p) => {
    const tarjeta = document.createElement("button");
    tarjeta.type = "button";
    tarjeta.className = "personaje";
    const ocupante = aliasDePersonaje(sala, p.id);
    const esMio = sala.personaje_id === p.id;

    const nombre = document.createElement("strong");
    nombre.textContent = p.nombre;
    tarjeta.appendChild(nombre);
    const detalle = document.createElement("span");
    detalle.textContent = `${p.color} · ${p.simbolo}`;
    tarjeta.appendChild(detalle);

    const situacion = document.createElement("span");
    if (esMio) {
      tarjeta.classList.add("mio");
      situacion.textContent = "TU PERSONAJE";
    } else if (ocupante) {
      tarjeta.classList.add("ocupado");
      tarjeta.disabled = true;
      situacion.textContent = `Elegido por ${ocupante}`;
    } else {
      situacion.textContent = "DISPONIBLE";
      tarjeta.addEventListener("click", () => {
        error.textContent = "";
        ws.send(JSON.stringify({ accion: "elegir_personaje", personaje_id: p.id }));
      });
    }
    tarjeta.appendChild(situacion);
    personajesDiv.appendChild(tarjeta);
  });
}

function pintarSala(sala) {
  error.textContent = "";
  modoPartida.textContent = sala.modo === "tablero" ? "MODO TABLERO" : "MODO RÁPIDO";
  lista.innerHTML = "";
  sala.jugadores.forEach((j) => {
    const li = document.createElement("li");
    let texto = j.alias;
    if (j.personaje) {
      texto += ` — ${j.personaje}`;
    }
    if (sala.estado === "iniciada" || sala.estado === "terminada") {
      texto += ` · ${j.num_cartas} cartas`;
      texto += j.tipo === "pnj" ? " · PNJ" : " · HUMANO";
      texto += j.activo ? " · ACTIVO" : " · ELIMINADO";
    }
    li.textContent = texto;
    if (j.es_anfitrion) {
      const etiqueta = document.createElement("span");
      etiqueta.className = "etiqueta-anfitrion";
      etiqueta.textContent = "anfitrión";
      li.appendChild(etiqueta);
    }
    lista.appendChild(li);
  });

  if (sala.estado === "iniciada" || sala.estado === "terminada") {
    estado.textContent = "";
    btnComenzar.style.display = "none";
    lobbyPersonajes.style.display = "none";
    partida.hidden = false;
    pintarTurno(sala);
    pintarCartas(sala.mis_cartas);
    pintarHoja(sala.investigacion || []);
    pintarJugada(sala);
    pintarMovimiento(sala);
    pintarTablero(sala);
    pintarFinal(sala);
    const repartidas = sala.jugadores.reduce((n, j) => n + j.num_cartas, 0);
    total.textContent = `${repartidas} cartas han sido repartidas.`;
  } else {
    document.body.classList.remove("modo-tablero-activo");
    tableroVisual.hidden = true;
    partida.hidden = true;
    btnComenzar.style.display = "";
    lobbyPersonajes.style.display = "";
    pintarPersonajes(sala);
    btnComenzar.disabled = !sala.es_anfitrion;
    const sinPersonaje = sala.jugadores.filter((j) => !j.personaje_id).length;
    if (sinPersonaje > 0) {
      estado.textContent =
        "Todos los jugadores deben elegir un personaje antes de comenzar.";
    } else if (!sala.es_anfitrion) {
      estado.textContent = "Esperando a que el anfitrión comience…";
    } else {
      estado.textContent = "Todo listo. ¡Puedes comenzar!";
    }
  }
}

function enviarDestinoTablero(destinoId, boton) {
  if (boton.disabled || !ultimaSala) return;
  const autorizados = new Set(
    ((ultimaSala.movimiento && ultimaSala.movimiento.destinos) || [])
      .map((destino) => destino.id)
  );
  if (!autorizados.has(destinoId)) return;
  boton.disabled = true;
  ws.send(JSON.stringify({ accion: "mover", destino_id: destinoId }));
}

function abrirCartaUbicacion(nodo, activador) {
  focoAntesDeUbicacion = activador || null;
  imagenUbicacion.src = nodo.imagen;
  imagenUbicacion.alt = nodo.nombre;
  modalUbicacionCaja.setAttribute("aria-label", `Carta de ${nodo.nombre}`);
  const destinos = new Set(
    (((ultimaSala || {}).movimiento || {}).destinos || []).map((d) => d.id)
  );
  destinoUbicacionModal = destinos.has(nodo.id) ? nodo.id : null;
  btnMoverUbicacionCanvas.hidden = !destinoUbicacionModal;
  btnMoverUbicacionCanvas.disabled = false;
  if (destinoUbicacionModal) {
    btnMoverUbicacionCanvas.setAttribute("aria-label", `Mover a ${nodo.nombre}`);
  }
  modalUbicacion.hidden = false;
  if (btnCerrarUbicacion.focus) btnCerrarUbicacion.focus();
}

function cerrarCartaUbicacion() {
  modalUbicacion.hidden = true;
  imagenUbicacion.src = "";
  destinoUbicacionModal = null;
  btnMoverUbicacionCanvas.hidden = true;
  if (focoAntesDeUbicacion && focoAntesDeUbicacion.focus) {
    focoAntesDeUbicacion.focus();
  }
  focoAntesDeUbicacion = null;
}

function pintarCapaAccesibleCanvas(sala) {
  tableroCanvasAccesible.innerHTML = "";
  const estadoTurno = document.createElement("p");
  estadoTurno.textContent = sala.es_mi_turno
    ? "Es tu turno" : `Turno de ${sala.turno_alias || "—"}`;
  tableroCanvasAccesible.appendChild(estadoTurno);
  const destinos = new Set(((sala.movimiento || {}).destinos || []).map((d) => d.id));
  TABLERO_VISUAL.nodos.forEach((nodo) => {
    if (nodo.tipo === "ubicacion") {
      const consultar = document.createElement("button");
      consultar.type = "button";
      consultar.textContent = `Ver carta de ${nodo.nombre}`;
      consultar.addEventListener("click", () => abrirCartaUbicacion(nodo, consultar));
      tableroCanvasAccesible.appendChild(consultar);
      if (destinos.has(nodo.id)) {
        const mover = document.createElement("button");
        mover.type = "button";
        mover.textContent = `Mover a ${nodo.nombre}`;
        mover.addEventListener("click", () => enviarDestinoTablero(nodo.id, mover));
        tableroCanvasAccesible.appendChild(mover);
      }
    } else if (destinos.has(nodo.id)) {
      const mover = document.createElement("button");
      mover.type = "button";
      mover.textContent = `Mover a ${nodo.nombre}`;
      mover.addEventListener("click", () => enviarDestinoTablero(nodo.id, mover));
      tableroCanvasAccesible.appendChild(mover);
    }
  });
}

function pintarTablero(sala) {
  const esTablero = sala.modo === "tablero";
  document.body.classList.toggle("modo-tablero-activo", esTablero);
  tableroVisual.hidden = !esTablero;
  if (!esTablero || !TABLERO_VISUAL) return;
  tableroAyuda.classList.remove("error");
  tableroAyuda.textContent =
    "Las posiciones resaltadas son destinos permitidos por el servidor.";
  tableroCanvasContenedor.hidden = false;
  pintarCapaAccesibleCanvas(sala);
  if (canvasFallido) return;
  try {
    if (!window.TableroCanvas || !tableroCanvas || !tableroCanvas.getContext) {
      throw new Error("Canvas 2D no está disponible");
    }
    if (!rendererCanvas) {
      rendererCanvas = new window.TableroCanvas(tableroCanvas, TABLERO_VISUAL, {
        consultar: abrirCartaUbicacion,
        mover: enviarDestinoTablero,
      });
    }
    rendererCanvas.actualizar(sala, TABLERO_VISUAL);
  } catch (fallo) {
    canvasFallido = true;
    console.error("No se pudo inicializar el tablero Canvas.", fallo);
    tableroAyuda.classList.add("error");
    tableroAyuda.textContent =
      "No se pudo mostrar el tablero. Recarga la página para reintentarlo.";
  }
}

btnCerrarUbicacion.addEventListener("click", cerrarCartaUbicacion);
btnMoverUbicacionCanvas.addEventListener("click", () => {
  if (!destinoUbicacionModal) return;
  enviarDestinoTablero(destinoUbicacionModal, btnMoverUbicacionCanvas);
});
modalUbicacion.addEventListener("click", (evento) => {
  if (evento.target === modalUbicacion) cerrarCartaUbicacion();
});
if (document.addEventListener) {
  document.addEventListener("keydown", (evento) => {
    if (evento.key === "Escape" && !modalUbicacion.hidden) cerrarCartaUbicacion();
  });
}

function pintarTurno(sala) {
  ordenOl.innerHTML = "";
  sala.orden.forEach((entrada, i) => {
    const li = document.createElement("li");
    li.textContent = `${entrada.alias} — ${entrada.personaje} · ${entrada.tipo === "pnj" ? "PNJ" : "HUMANO"} · ${entrada.activo ? "ACTIVO" : "ELIMINADO"}`;
    if (entrada.alias === sala.turno_alias) {
      li.classList.add("en-turno");
    }
    ordenOl.appendChild(li);
  });
  if (sala.estado === "terminada") {
    turnoP.textContent = "PARTIDA TERMINADA";
  } else if (sala.pnj_pensando_alias) {
    turnoP.textContent = `${sala.pnj_pensando_alias} ESTÁ PENSANDO...`;
  } else if (sala.es_mi_turno) {
    turnoP.textContent = "ES TU TURNO";
  } else {
    const tipoTurno = sala.turno_tipo === "pnj" ? " · PNJ" : "";
    turnoP.textContent = `TURNO DE ${(sala.turno_alias || "").toUpperCase()}${tipoTurno}`;
  }
}

function llenarSelect(select, cartas, categoria) {
  select.innerHTML = '<option value="">-- Selecciona --</option>';
  cartas.filter((c) => c.categoria === categoria).forEach((c) => {
    const opcion = document.createElement("option");
    opcion.value = c.id;
    opcion.textContent = c.nombre;
    select.appendChild(opcion);
  });
}

function pintarJugada(sala) {
  const jugada = sala.jugada || {};
  jugadaDiv.innerHTML = "";
  const puedeSospechar = sala.estado === "iniciada" && sala.activo_investigacion &&
    sala.es_mi_turno && jugada.estado === "esperando_sospecha";
  btnSospecha.hidden = !puedeSospechar;
  const puedeResolver = sala.estado === "iniciada" && sala.activo_investigacion &&
    sala.es_mi_turno && (jugada.estado === "esperando_sospecha" ||
      (sala.modo === "tablero" && jugada.estado === "esperando_movimiento"));
  btnResolver.hidden = !puedeResolver;
  if (jugada.movimiento_pnj) {
    const movimientoPnj = document.createElement("p");
    const m = jugada.movimiento_pnj;
    if (m.accion === "sospecha_aqui") {
      movimientoPnj.textContent =
        `${jugada.investigador_alias} decide investigar ${m.origen} sin moverse.`;
    } else if (m.accion === "pasadizo") {
      movimientoPnj.textContent =
        `${jugada.investigador_alias} usa el pasadizo desde ${m.origen} hasta ${m.destino}.`;
    } else {
      movimientoPnj.textContent =
        `${jugada.investigador_alias} ha tirado un ${m.tirada} y se mueve desde ${m.origen} hasta ${m.destino}.`;
    }
    jugadaDiv.appendChild(movimientoPnj);
  }
  if (jugada.sospecha) {
    const titulo = document.createElement("strong");
    titulo.textContent = `${jugada.investigador_alias} HA FORMULADO UNA SOSPECHA`;
    jugadaDiv.appendChild(titulo);
    ["sospechoso", "lugar", "objeto"].forEach((categoria) => {
      const linea = document.createElement("p");
      linea.textContent = `${TITULOS[categoria]}: ${jugada.sospecha[`${categoria}_id`].nombre}`;
      jugadaDiv.appendChild(linea);
    });
  }
  const resultado = document.createElement("p");
  if (jugada.resultado === "sin_refutacion") {
    resultado.textContent = "NADIE HA PODIDO REFUTAR LA SOSPECHA";
  } else if (jugada.resultado === "refutada") {
    resultado.textContent = `SOSPECHA REFUTADA POR ${jugada.refutador_alias}`;
  } else if (jugada.esperando_resolucion) {
    resultado.textContent = "ESPERANDO RESPUESTA...";
  } else if (jugada.resultado === "pendiente") {
    resultado.textContent = "RESOLVIENDO SOSPECHA...";
  } else if (jugada.resultado === "acusacion_incorrecta") {
    resultado.textContent = `${jugada.investigador_alias} HA INTENTADO RESOLVER EL MISTERIO. LA ACUSACIÓN ERA INCORRECTA. QUEDA ELIMINADO COMO INVESTIGADOR.`;
  } else if (jugada.resultado === "resuelto") {
    resultado.textContent = `${jugada.investigador_alias} HA RESUELTO EL MISTERIO.`;
  } else if (jugada.resultado === "sin_resolver") {
    resultado.textContent = "NO QUEDAN INVESTIGADORES ACTIVOS. EL MISTERIO QUEDA SIN RESOLVER.";
  }
  if (jugada.carta_mostrada) {
    resultado.textContent += ` ${jugada.refutador_alias} TE HA MOSTRADO: ${jugada.carta_mostrada.nombre}`;
  }
  jugadaDiv.appendChild(resultado);

  const opciones = Array.isArray(jugada.opciones_refutacion)
    ? jugada.opciones_refutacion : [];
  modalRefutacion.hidden = opciones.length === 0;
  opcionesRefutacion.innerHTML = "";
  opciones.forEach((carta) => {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.textContent = carta.nombre;
    boton.addEventListener("click", () => {
      boton.disabled = true;
      ws.send(JSON.stringify({ accion: "mostrar_carta", carta_id: carta.id }));
    });
    opcionesRefutacion.appendChild(boton);
  });
  // Aviso server-side de plazo (humano eliminado): informativo, la
  // autoridad es el servidor y resuelve aunque se ignore este aviso.
  if (avisoTimeoutRefutacion) {
    if (opciones.length > 0 && jugada.timeout_refutacion_seg) {
      avisoTimeoutRefutacion.hidden = false;
      avisoTimeoutRefutacion.textContent =
        `Tienes unos ${jugada.timeout_refutacion_seg} segundos para elegir. ` +
        "Si no respondes, el servidor mostrará una carta al azar.";
    } else {
      avisoTimeoutRefutacion.hidden = true;
      avisoTimeoutRefutacion.textContent = "";
    }
  }
}

function pintarMovimiento(sala) {
  movimientoDiv.hidden = sala.modo !== "tablero";
  if (sala.modo !== "tablero") return;
  const movimiento = sala.movimiento || {};
  posicionActual.textContent = `POSICIÓN ACTUAL: ${(sala.posicion && sala.posicion.nombre) || "—"}`;
  resultadoDado.textContent = movimiento.tirada ? `HAS SACADO: ${movimiento.tirada}` : "";
  btnTirar.disabled = false;
  btnPasadizo.disabled = false;
  btnTirar.hidden = !movimiento.puede_tirar;
  btnPasadizo.hidden = !movimiento.pasadizo;
  if (movimiento.pasadizo) {
    btnPasadizo.textContent = `🌀 USAR PASADIZO A ${movimiento.pasadizo.nombre}`;
  }
  destinosMovimiento.innerHTML = "";
  (movimiento.destinos || []).forEach((destino) => {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.textContent = destino.nombre;
    boton.addEventListener("click", () => {
      boton.disabled = true;
      ws.send(JSON.stringify({ accion: "mover", destino_id: destino.id }));
    });
    destinosMovimiento.appendChild(boton);
  });
}

function pintarFinal(sala) {
  finalPartida.hidden = sala.estado !== "terminada";
  finalPartida.innerHTML = "";
  if (sala.estado !== "terminada" || !sala.solucion) return;
  const titulo = document.createElement("h2");
  titulo.textContent = sala.resultado_final === "resuelto"
    ? "🏆 MISTERIO RESUELTO" : "🔒 EL MISTERIO QUEDA SIN RESOLVER";
  finalPartida.appendChild(titulo);
  if (sala.ganador_alias) {
    const ganador = document.createElement("p");
    ganador.textContent = `Ganador: ${sala.ganador_alias}`;
    finalPartida.appendChild(ganador);
  }
  ["sospechoso", "lugar", "objeto"].forEach((categoria) => {
    const linea = document.createElement("p");
    linea.textContent = `${TITULOS[categoria]}: ${sala.solucion[categoria].nombre}`;
    finalPartida.appendChild(linea);
  });
}

function pintarCartas(misCartas) {
  if (!cartasDiv) {
    return;
  }
  cartasDiv.innerHTML = "";
  const lista = Array.isArray(misCartas) ? misCartas : [];
  ["sospechoso", "lugar", "objeto"].forEach((categoria) => {
    const mias = lista.filter((c) => c.categoria === categoria);
    if (mias.length === 0) {
      return;
    }
    const grupo = document.createElement("div");
    grupo.className = "grupo-cartas";
    const titulo = document.createElement("h3");
    titulo.textContent = `${TITULOS[categoria]} (${mias.length})`;
    grupo.appendChild(titulo);
    const ul = document.createElement("ul");
    mias.forEach((carta) => {
      const li = document.createElement("li");
      li.textContent = carta.nombre;
      ul.appendChild(li);
    });
    grupo.appendChild(ul);
    cartasDiv.appendChild(grupo);
  });
}

btnComenzar.addEventListener("click", () => {
  error.textContent = "";
  ws.send(JSON.stringify({ accion: "iniciar" }));
});

function filaHoja(entrada) {
  const fila = document.createElement("button");
  fila.type = "button";
  fila.className = `hoja-fila estado-${entrada.estado}`;
  const nombre = document.createElement("span");
  nombre.className = "hoja-nombre";
  nombre.textContent = entrada.nombre;
  fila.appendChild(nombre);
  const marca = document.createElement("span");
  marca.className = "hoja-estado";
  marca.textContent = ETIQUETA_ESTADO[entrada.estado] || entrada.estado;
  fila.appendChild(marca);
  if (entrada.estado === "la_tengo" || entrada.estado === "vista") {
    fila.disabled = true;
    fila.title =
      entrada.estado === "la_tengo"
        ? "Es una de tus cartas: no se puede modificar."
        : "Carta vista: se conserva automáticamente.";
  } else {
    fila.addEventListener("click", () => {
      if (errorHoja) {
        errorHoja.textContent = "";
      }
      ws.send(
        JSON.stringify({
          accion: "marcar_investigacion",
          carta_id: entrada.id,
          estado:
            entrada.estado === "descartada" ? "sin_informacion" : "descartada",
        })
      );
    });
  }
  return fila;
}

const CATEGORIAS_HOJA = ["sospechoso", "lugar", "objeto"];
// Grupos independientes: plegar uno nunca cierra los otros.
const GRUPO_ABIERTO = { sospechoso: true, lugar: true, objeto: true };

function categoriaDe(entrada) {
  return String((entrada && entrada.categoria) || "")
    .trim()
    .toLowerCase();
}

function pintarHoja(investigacion) {
  if (!hojaDiv) {
    return;
  }
  hojaDiv.innerHTML = "";
  if (errorHoja) {
    errorHoja.textContent = "";
  }
  const lista = Array.isArray(investigacion) ? investigacion : [];
  if (lista.length === 0) {
    // Nunca mostrar los tres títulos vacíos en silencio: avisar.
    const aviso = document.createElement("p");
    aviso.className = "estado";
    aviso.textContent =
      "Cargando tu hoja de investigación… si las cartas no aparecen, recarga la página.";
    hojaDiv.appendChild(aviso);
    return;
  }
  CATEGORIAS_HOJA.forEach((categoria) => {
    const entradas = lista.filter((e) => categoriaDe(e) === categoria);
    const grupo = document.createElement("div");
    grupo.className = "grupo-cartas grupo-hoja";
    const cabecera = document.createElement("button");
    cabecera.type = "button";
    cabecera.className = "hoja-cabecera";
    const titulo = document.createElement("span");
    titulo.textContent = `${TITULOS[categoria]} (${entradas.length})`;
    cabecera.appendChild(titulo);
    const flecha = document.createElement("span");
    flecha.className = "hoja-flecha";
    flecha.textContent = GRUPO_ABIERTO[categoria] ? "▾" : "▸";
    cabecera.appendChild(flecha);
    cabecera.setAttribute(
      "aria-expanded",
      GRUPO_ABIERTO[categoria] ? "true" : "false"
    );
    const cuerpo = document.createElement("div");
    cuerpo.className = "hoja-cuerpo";
    cuerpo.hidden = !GRUPO_ABIERTO[categoria];
    entradas.forEach((entrada) => {
      cuerpo.appendChild(filaHoja(entrada));
    });
    cabecera.addEventListener("click", () => {
      GRUPO_ABIERTO[categoria] = !GRUPO_ABIERTO[categoria];
      cuerpo.hidden = !GRUPO_ABIERTO[categoria];
      flecha.textContent = GRUPO_ABIERTO[categoria] ? "▾" : "▸";
      cabecera.setAttribute(
        "aria-expanded",
        GRUPO_ABIERTO[categoria] ? "true" : "false"
      );
    });
    grupo.appendChild(cabecera);
    grupo.appendChild(cuerpo);
    hojaDiv.appendChild(grupo);
  });
  // Entradas con categoría inesperada: mostrarlas, nunca ocultarlas.
  const resto = lista.filter((e) => !CATEGORIAS_HOJA.includes(categoriaDe(e)));
  if (resto.length > 0) {
    const grupo = document.createElement("div");
    grupo.className = "grupo-cartas grupo-hoja";
    const titulo = document.createElement("h3");
    titulo.textContent = `OTRAS (${resto.length})`;
    grupo.appendChild(titulo);
    resto.forEach((entrada) => {
      grupo.appendChild(filaHoja(entrada));
    });
    hojaDiv.appendChild(grupo);
  }
}

function abrirHoja() {
  if (modalHoja) {
    modalHoja.hidden = false;
  }
}

function cerrarHoja() {
  if (modalHoja) {
    modalHoja.hidden = true;
  }
}

function abrirCartas() {
  if (modalCartas) {
    modalCartas.hidden = false;
  }
}

function cerrarCartas() {
  if (modalCartas) {
    modalCartas.hidden = true;
  }
}

if (btnVerHoja) {
  btnVerHoja.addEventListener("click", abrirHoja);
}
if (btnVerCartas) {
  btnVerCartas.addEventListener("click", abrirCartas);
}
if (btnCerrarHoja) {
  btnCerrarHoja.addEventListener("click", cerrarHoja);
}
if (btnCerrarCartas) {
  btnCerrarCartas.addEventListener("click", cerrarCartas);
}

function abrirSospecha() {
  const cartas = (ultimaSala && ultimaSala.investigacion) || [];
  llenarSelect(selectSospechoso, cartas, "sospechoso");
  llenarSelect(selectLugar, cartas, "lugar");
  llenarSelect(selectObjeto, cartas, "objeto");
  const modoTablero = ultimaSala && ultimaSala.modo === "tablero";
  selectLugar.parentElement.hidden = modoTablero;
  selectLugar.disabled = modoTablero;
  if (modoTablero && ultimaSala.posicion) {
    selectLugar.value = ultimaSala.posicion.id;
  }
  modalSospecha.hidden = false;
}

btnSospecha.addEventListener("click", abrirSospecha);
btnTirar.addEventListener("click", () => {
  btnTirar.disabled = true;
  ws.send(JSON.stringify({ accion: "tirar_dado" }));
});
btnPasadizo.addEventListener("click", () => {
  btnPasadizo.disabled = true;
  ws.send(JSON.stringify({ accion: "usar_pasadizo" }));
});
document.getElementById("btn-cancelar-sospecha").addEventListener("click", () => {
  modalSospecha.hidden = true;
});
document.getElementById("btn-confirmar-sospecha").addEventListener("click", () => {
  if (!selectSospechoso.value || !selectLugar.value || !selectObjeto.value) {
    error.textContent = "Selecciona sospechoso, lugar y objeto.";
    return;
  }
  ws.send(JSON.stringify({
    accion: "formular_sospecha",
    sospechoso_id: selectSospechoso.value,
    lugar_id: selectLugar.value,
    objeto_id: selectObjeto.value,
  }));
  modalSospecha.hidden = true;
});

btnResolver.addEventListener("click", () => {
  const cartas = (ultimaSala && ultimaSala.investigacion) || [];
  llenarSelect(resolverSospechoso, cartas, "sospechoso");
  llenarSelect(resolverLugar, cartas, "lugar");
  llenarSelect(resolverObjeto, cartas, "objeto");
  modalResolver.hidden = false;
});
document.getElementById("btn-cancelar-resolver").addEventListener("click", () => {
  modalResolver.hidden = true;
});
function nombreSeleccionado(select) {
  if (!select || !select.value) {
    return "";
  }
  const opciones = select.options || [];
  const elegida = opciones[select.selectedIndex];
  return elegida ? elegida.textContent : select.value;
}

document.getElementById("btn-confirmar-resolver").addEventListener("click", () => {
  if (!resolverSospechoso.value || !resolverLugar.value || !resolverObjeto.value) {
    error.textContent = "Selecciona sospechoso, lugar y objeto.";
    return;
  }
  confResolverSospechoso.textContent = `Sospechoso: ${nombreSeleccionado(resolverSospechoso)}`;
  confResolverLugar.textContent = `Lugar: ${nombreSeleccionado(resolverLugar)}`;
  confResolverObjeto.textContent = `Objeto: ${nombreSeleccionado(resolverObjeto)}`;
  modalResolver.hidden = true;
  // Rearme para un único envío: CANCELAR no envía nada y volver a
  // confirmar reactiva el botón.
  btnEnviarResolver.disabled = false;
  modalConfirmarResolver.hidden = false;
});
document.getElementById("btn-cancelar-confirmar-resolver").addEventListener("click", () => {
  // CANCELAR no modifica ningún estado: conserva la selección previa.
  modalConfirmarResolver.hidden = true;
  modalResolver.hidden = false;
});
btnEnviarResolver.addEventListener("click", () => {
  // Anti doble clic/doble envío: el servidor además solo acepta una
  // acusación por transición válida.
  if (btnEnviarResolver.disabled) {
    return;
  }
  btnEnviarResolver.disabled = true;
  ws.send(JSON.stringify({
    accion: "resolver_misterio",
    sospechoso_id: resolverSospechoso.value,
    lugar_id: resolverLugar.value,
    objeto_id: resolverObjeto.value,
  }));
  modalConfirmarResolver.hidden = true;
});
