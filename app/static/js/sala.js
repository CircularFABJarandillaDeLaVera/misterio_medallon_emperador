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
const modalRevelacionRefutacion = document.getElementById("modal-revelacion-refutacion");
const revelacionRefutador = document.getElementById("revelacion-refutador");
const revelacionCartaImagen = document.getElementById("revelacion-carta-imagen");
const revelacionCartaNombre = document.getElementById("revelacion-carta-nombre");
const btnContinuarRevelacion = document.getElementById("btn-continuar-revelacion");
const selectSospechoso = document.getElementById("sospecha-sospechoso");
const selectLugar = document.getElementById("sospecha-lugar");
const selectObjeto = document.getElementById("sospecha-objeto");
const btnResolver = document.getElementById("btn-resolver");
const modalResolver = document.getElementById("modal-resolver");
const grupoResolverSospechoso = document.getElementById("resolver-grupo-sospechoso");
const grupoResolverLugar = document.getElementById("resolver-grupo-lugar");
const grupoResolverObjeto = document.getElementById("resolver-grupo-objeto");
const btnConfirmarResolver = document.getElementById("btn-confirmar-resolver");
const modalConfirmarResolver = document.getElementById("modal-confirmar-resolver");
const btnEnviarResolver = document.getElementById("btn-enviar-resolver");
const confResolverSospechoso = document.getElementById("conf-resolver-sospechoso");
const confResolverLugar = document.getElementById("conf-resolver-lugar");
const confResolverObjeto = document.getElementById("conf-resolver-objeto");
const avisoTimeoutRefutacion = document.getElementById("aviso-timeout-refutacion");
const finalPartida = document.getElementById("final-partida");
const modoPartida = document.getElementById("modo-partida");
const resumenSala = document.getElementById("resumen-sala");
const bloqueCodigo = document.getElementById("bloque-codigo");
const bloqueJugadores = document.getElementById("bloque-jugadores");
const bloqueOrden = document.getElementById("bloque-orden");
const btnCopiarCodigo = document.getElementById("btn-copiar-codigo");
const vistaContextual = document.getElementById("vista-contextual");
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
const modalContextualTitulo = document.getElementById("modal-contextual-titulo");
const modalContextualDetalle = document.getElementById("modal-contextual-detalle");
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
let RECURSOS_VISUALES = {};
let ubicacionContextualId = null;
let revelacionDescartada = null;
let revelacionVisible = null;
const DURACION_PASO_MS = 600;
const posicionesVisuales = new Map();
const animacionesMovimiento = new Map();
let estadoVisualHidratado = false;
let ultimoMovimientoId = null;
let secuenciaAnimacion = 0;

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

// Manifiesto público (nombres e imágenes de personajes): sin secretos.
fetch("/api/recursos")
  .then((r) => r.json())
  .then((datos) => {
    RECURSOS_VISUALES = (datos && datos.recursos) || {};
    if (ultimaSala) {
      pintarRevelacionPrivada(ultimaSala);
      pintarHoja(ultimaSala.investigacion || [], ultimaSala.mis_cartas || []);
    }
  });

const protocolo = window.location.protocol === "https:" ? "wss" : "ws";
const ws = new WebSocket(
  `${protocolo}://${window.location.host}/ws/${encodeURIComponent(codigo)}/${encodeURIComponent(jugadorId)}`
);

ws.onmessage = (evento) => {
  const mensaje = JSON.parse(evento.data);
  if (mensaje.tipo === "estado_privado") {
    presentarEstadoPrivado(mensaje.sala);
  } else if (mensaje.tipo === "error") {
    error.textContent = mensaje.detalle;
  }
};

function cancelarAnimacionMovimiento(personajeId) {
  const animacion = animacionesMovimiento.get(personajeId);
  if (animacion && animacion.temporizador !== null) {
    window.clearTimeout(animacion.temporizador);
  }
  animacionesMovimiento.delete(personajeId);
  posicionesVisuales.delete(personajeId);
}

function continuarAnimacionMovimiento(personajeId, recorrido, indice, token) {
  const animacion = animacionesMovimiento.get(personajeId);
  if (!animacion || animacion.token !== token) return;
  if (indice < recorrido.length) {
    posicionesVisuales.set(personajeId, recorrido[indice]);
    if (ultimaSala) pintarTablero(ultimaSala);
    animacion.temporizador = window.setTimeout(
      () => continuarAnimacionMovimiento(personajeId, recorrido, indice + 1, token),
      DURACION_PASO_MS
    );
    return;
  }
  animacionesMovimiento.delete(personajeId);
  posicionesVisuales.delete(personajeId);
  if (ultimaSala) pintarTablero(ultimaSala);
}

function iniciarAnimacionMovimiento(movimiento) {
  const personajeId = movimiento.personaje_id;
  cancelarAnimacionMovimiento(personajeId);
  posicionesVisuales.set(personajeId, movimiento.origen_id);
  const token = ++secuenciaAnimacion;
  const animacion = { token, temporizador: null };
  animacionesMovimiento.set(personajeId, animacion);
  animacion.temporizador = window.setTimeout(
    () => continuarAnimacionMovimiento(personajeId, movimiento.recorrido, 0, token),
    DURACION_PASO_MS
  );
}

function presentarEstadoPrivado(sala) {
  const movimiento = sala.movimiento_resuelto;
  const movimientoId = movimiento && Number.isInteger(movimiento.movimiento_id)
    ? movimiento.movimiento_id
    : null;

  if (!estadoVisualHidratado) {
    estadoVisualHidratado = true;
    ultimoMovimientoId = movimientoId;
    ultimaSala = sala;
    pintarSala(sala);
    return;
  }
  if (movimientoId !== null && ultimoMovimientoId !== null && movimientoId < ultimoMovimientoId) {
    return;
  }

  const esMovimientoNuevo = movimientoId !== null && movimientoId !== ultimoMovimientoId;
  if (esMovimientoNuevo) ultimoMovimientoId = movimientoId;
  if (esMovimientoNuevo && movimiento && movimiento.tipo === "normal"
      && movimiento.personaje_id && movimiento.origen_id
      && Array.isArray(movimiento.recorrido) && movimiento.recorrido.length) {
    iniciarAnimacionMovimiento(movimiento);
    ultimaSala = sala;
    pintarSala(sala);
    return;
  }
  if (esMovimientoNuevo && movimiento && movimiento.personaje_id) {
    cancelarAnimacionMovimiento(movimiento.personaje_id);
  }
  ultimaSala = sala;
  pintarSala(sala);
}

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
  // Modo de partida
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
    if (document.body && document.body.classList) {
      document.body.classList.add("en-partida");
    }
    // Cabecera compacta: el detalle técnico deja la vista principal.
    if (bloqueCodigo) bloqueCodigo.hidden = true;
    if (bloqueJugadores) bloqueJugadores.hidden = true;
    if (bloqueOrden) bloqueOrden.hidden = true;
    total.hidden = true;
    if (resumenSala) {
      resumenSala.hidden = false;
      resumenSala.textContent = `Sala ${sala.codigo}`;
    }
    pintarTurno(sala);
    pintarCartas(sala.mis_cartas);
    pintarHoja(sala.investigacion || [], sala.mis_cartas || []);
    pintarJugada(sala);
    pintarMovimiento(sala);
    pintarTablero(sala);
    pintarPanel(sala);
    pintarFinal(sala);
    const repartidas = sala.jugadores.reduce((n, j) => n + j.num_cartas, 0);
    total.textContent = `${repartidas} cartas han sido repartidas.`;
  } else {
    if (document.body && document.body.classList) {
      document.body.classList.remove("en-partida");
    }
    if (bloqueCodigo) bloqueCodigo.hidden = false;
    if (bloqueJugadores) bloqueJugadores.hidden = false;
    if (bloqueOrden) bloqueOrden.hidden = false;
    total.hidden = false;
    if (resumenSala) resumenSala.hidden = true;
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
  if (modalUbicacion.hidden) focoAntesDeUbicacion = activador || null;
  // El modal muestra siempre la tarjeta completa derivada del ID canónico
  // (guiones intactos), nunca tablero_*.png.
  const idUbicacion = nodo.id;
  const urlTarjeta = `/static/img/lugares/${idUbicacion}.jpeg`;
  imagenUbicacion.src = urlTarjeta;
  imagenUbicacion.alt = nodo.nombre;
  imagenUbicacion.hidden = false;
  ubicacionContextualId = nodo.id;
  btnCerrarUbicacion.hidden = false;
  modalContextualTitulo.textContent = nodo.nombre;
  modalContextualDetalle.innerHTML = "";
  modalContextualDetalle.classList.remove("modo-sospecha-compacta");
  modalUbicacionCaja.setAttribute("aria-label", `Información de ${nodo.nombre}`);
  const cabecera = document.createElement("p");
  cabecera.textContent = "PERSONAJES AQUÍ";
  modalContextualDetalle.appendChild(cabecera);
  const ocupantes = ((ultimaSala || {}).jugadores || []).filter(
    (j) => j.posicion && j.posicion.id === nodo.id
  );
  if (ocupantes.length === 0) {
    const vacio = document.createElement("p");
    vacio.className = "estado";
    vacio.textContent = "No hay personajes aquí.";
    modalContextualDetalle.appendChild(vacio);
  } else {
    const grupo = document.createElement("div");
    grupo.className = "ocupantes";
    ocupantes.forEach((j) => {
      const boton = document.createElement("button");
      boton.type = "button";
      boton.textContent = j.alias;
      boton.addEventListener("click", () => verPersonaje(j.personaje_id));
      grupo.appendChild(boton);
    });
    modalContextualDetalle.appendChild(grupo);
  }
  const destinos = new Set(
    (((ultimaSala || {}).movimiento || {}).destinos || []).map((d) => d.id)
  );
  destinoUbicacionModal = destinos.has(nodo.id) ? nodo.id : null;
  btnMoverUbicacionCanvas.hidden = !destinoUbicacionModal;
  btnMoverUbicacionCanvas.disabled = false;
  if (destinoUbicacionModal) {
    btnMoverUbicacionCanvas.setAttribute("aria-label", `Mover a ${nodo.nombre}`);
  }
  const puedeSospecharAqui = puedeSospecharServidor(ultimaSala) &&
    ultimaSala.posicion && ultimaSala.posicion.id === nodo.id;
  if (puedeSospecharAqui) {
    const sospechar = document.createElement("button");
    sospechar.type = "button";
    sospechar.textContent = "FORMULAR SOSPECHA";
    sospechar.addEventListener("click", () => verSospecha(nodo.id));
    modalContextualDetalle.appendChild(sospechar);
  }
  if (ultimaSala) pintarPanel(ultimaSala);
  modalUbicacion.hidden = false;
  if (btnCerrarUbicacion.focus) btnCerrarUbicacion.focus();
}

function consultarUbicacion(nodo, activador) {
  abrirCartaUbicacion(nodo, activador);
}

function verPersonajeCanvas(info, activador) {
  if (info && info.personaje_id) verPersonaje(info.personaje_id, activador);
}

function cerrarCartaUbicacion() {
  modalUbicacion.hidden = true;
  modalContextualTitulo.textContent = "";
  modalContextualDetalle.innerHTML = "";
  modalContextualDetalle.classList.remove("modo-sospecha-compacta");
  imagenUbicacion.src = "";
  imagenUbicacion.alt = "";
  imagenUbicacion.hidden = false;
  ubicacionContextualId = null;
  destinoUbicacionModal = null;
  btnMoverUbicacionCanvas.hidden = true;
  btnCerrarUbicacion.hidden = false;
  if (ultimaSala) pintarPanel(ultimaSala);
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
      consultar.addEventListener("click", () => consultarUbicacion(nodo, consultar));
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
  tableroAyuda.textContent = "";
  tableroCanvasContenedor.hidden = false;
  pintarCapaAccesibleCanvas(sala);
  if (canvasFallido) return;
  try {
    if (!window.TableroCanvas || !tableroCanvas || !tableroCanvas.getContext) {
      throw new Error("Canvas 2D no está disponible");
    }
    if (!rendererCanvas) {
      rendererCanvas = new window.TableroCanvas(tableroCanvas, TABLERO_VISUAL, {
        consultar: consultarUbicacion,
        mover: enviarDestinoTablero,
        personaje: verPersonajeCanvas,
      });
    }
    rendererCanvas.actualizar(sala, TABLERO_VISUAL, posicionesVisuales);
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

function firmaRevelacion(jugada) {
  if (!jugada || !jugada.carta_mostrada) return null;
  const sospecha = jugada.sospecha || {};
  return [
    jugada.investigador_alias || "",
    jugada.refutador_alias || "",
    jugada.carta_mostrada.id || "",
    ...["sospechoso_id", "lugar_id", "objeto_id"].map(
      (clave) => (sospecha[clave] || {}).id || ""
    ),
  ].join("|");
}

function imagenRevelacion(carta) {
  const recurso = (carta && RECURSOS_VISUALES[carta.id]) || {};
  return carta && carta.categoria === "sospechoso"
    ? (recurso.nombre || recurso.principal || "")
    : (recurso.principal || "");
}

function pintarRevelacionPrivada(sala) {
  const jugada = (sala && sala.jugada) || {};
  const firma = firmaRevelacion(jugada);
  if (!firma) {
    revelacionDescartada = null;
    revelacionVisible = null;
    modalRevelacionRefutacion.hidden = true;
    return;
  }
  if (firma === revelacionDescartada) return;
  const carta = jugada.carta_mostrada;
  revelacionVisible = firma;
  revelacionRefutador.textContent =
    `${(jugada.refutador_alias || "ALGUIEN").toUpperCase()} REFUTA TU SOSPECHA`;
  revelacionCartaImagen.src = imagenRevelacion(carta);
  revelacionCartaImagen.alt = carta.nombre || "Carta mostrada";
  revelacionCartaImagen.hidden = !revelacionCartaImagen.src;
  revelacionCartaNombre.textContent = carta.nombre || "";
  modalRevelacionRefutacion.hidden = false;
  if (btnContinuarRevelacion.focus) btnContinuarRevelacion.focus();
}

btnContinuarRevelacion.addEventListener("click", () => {
  revelacionDescartada = revelacionVisible;
  revelacionVisible = null;
  modalRevelacionRefutacion.hidden = true;
});

function pintarJugada(sala) {
  const jugada = sala.jugada || {};
  jugadaDiv.innerHTML = "";
  const puedeSospechar = sala.estado === "iniciada" && sala.activo_investigacion &&
    sala.es_mi_turno && jugada.estado === "esperando_sospecha";
  // En tablero la sospecha vive en el panel contextual; en rápido usa el modal.
  btnSospecha.hidden = !puedeSospechar || sala.modo === "tablero";
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
  jugadaDiv.appendChild(resultado);
  pintarRevelacionPrivada(sala);

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
  posicionActual.textContent = (sala.posicion && sala.posicion.nombre) || "—";
  resultadoDado.textContent = movimiento.tirada ? `HAS SACADO: ${movimiento.tirada}` : "";
  btnTirar.disabled = false;
  btnPasadizo.disabled = false;
  btnTirar.hidden = !movimiento.puede_tirar;
  btnPasadizo.hidden = !movimiento.pasadizo;
  if (movimiento.pasadizo) {
    btnPasadizo.textContent = `PASADIZO → ${movimiento.pasadizo.nombre}`;
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

function puedeSospecharServidor(sala) {
  return Boolean(
    sala.estado === "iniciada" && (sala.movimiento || {}).puede_sospechar
  );
}

function verUbicacion(ubicacionId) {
  if (!ultimaSala || !ubicacionId) return;
  const nodo = nodoUbicacion(ubicacionId);
  if (nodo) abrirCartaUbicacion(nodo, null);
}

function verPersonaje(personajeId, activador) {
  if (!ultimaSala || !personajeId) return;
  if (modalUbicacion.hidden) focoAntesDeUbicacion = activador || null;
  const jugador = (ultimaSala.jugadores || []).find((j) => j.personaje_id === personajeId);
  const datos = (PERSONAJES || []).find((p) => p.id === personajeId) || {};
  const nombre = (jugador && jugador.personaje) || datos.nombre || personajeId;
  modalContextualTitulo.textContent = nombre;
  modalContextualDetalle.innerHTML = "";
  modalContextualDetalle.classList.remove("modo-sospecha-compacta");
  imagenUbicacion.src = (RECURSOS_VISUALES[personajeId] || {}).principal || "";
  imagenUbicacion.alt = nombre;
  imagenUbicacion.hidden = false;
  ubicacionContextualId = null;
  btnCerrarUbicacion.hidden = false;
  modalUbicacionCaja.setAttribute("aria-label", `Información de ${nombre}`);
  if (jugador && jugador.alias) {
    const linea = document.createElement("p");
    linea.textContent = jugador.alias;
    modalContextualDetalle.appendChild(linea);
  }
  const esPersonajePropio = jugador && jugador.tipo !== "pnj" &&
    jugador.personaje_id === ultimaSala.personaje_id;
  if (esPersonajePropio) {
    const investigacion = document.createElement("button");
    investigacion.type = "button";
    investigacion.textContent = "INVESTIGACIÓN";
    investigacion.addEventListener("click", abrirHoja);
    modalContextualDetalle.appendChild(investigacion);
  }
  destinoUbicacionModal = null;
  btnMoverUbicacionCanvas.hidden = true;
  pintarPanel(ultimaSala);
  modalUbicacion.hidden = false;
  if (btnCerrarUbicacion.focus) btnCerrarUbicacion.focus();
}

function verSospecha(ubicacionId) {
  if (!ultimaSala || ultimaSala.modo !== "tablero" ||
      !puedeSospecharServidor(ultimaSala) || !ultimaSala.posicion ||
      ultimaSala.posicion.id !== ubicacionId) return;
  pintarVistaSospecha(ultimaSala, ubicacionId);
}

function nodoUbicacion(ubicacionId) {
  const nodos = (TABLERO_VISUAL && TABLERO_VISUAL.nodos) || [];
  return nodos.find((n) => n.id === ubicacionId && n.tipo === "ubicacion") || null;
}

function crearCartaVisual(carta, opciones = {}) {
  const recurso = RECURSOS_VISUALES[carta.id] || {};
  const esPropia = Boolean(opciones.esPropia);
  const fueVista = Boolean(opciones.fueVista);
  const descartada = Boolean(opciones.descartada);
  const boton = document.createElement("button");
  boton.type = "button";
  boton.className = `carta-selector-sospecha${opciones.compacta ? " carta-visual-compacta" : ""}${descartada ? " descartada" : ""}`;
  boton.dataset.cartaId = carta.id;
  boton.setAttribute("aria-pressed", opciones.seleccionada ? "true" : "false");
  if (opciones.seleccionada) boton.classList.add("seleccionada");
  const estado = esPropia ? "tu carta" : fueVista ? "vista" : descartada ? "descartada" : "sin información";
  boton.setAttribute("aria-label", `${carta.nombre}, ${estado}`);
  const imagen = document.createElement("img");
  imagen.src = carta.categoria === "sospechoso"
    ? (recurso.nombre || recurso.principal || "")
    : (recurso.principal || "");
  imagen.alt = "";
  imagen.hidden = !imagen.src;
  boton.appendChild(imagen);
  if (opciones.mostrarNombre !== false) {
    const nombre = document.createElement("span");
    nombre.className = "carta-selector-nombre";
    nombre.textContent = carta.nombre;
    boton.appendChild(nombre);
  }
  if (esPropia || fueVista || descartada) {
    const marca = document.createElement("span");
    marca.className = `carta-selector-marca ${esPropia ? "es-propia" : fueVista ? "es-vista" : "es-descartada"}`;
    marca.textContent = esPropia ? "✓ TU CARTA" : fueVista ? "◉ VISTA" : "× DESCARTADA";
    boton.appendChild(marca);
  }
  if (opciones.alPulsar) boton.addEventListener("click", () => opciones.alPulsar(boton));
  else boton.setAttribute("aria-disabled", "true");
  return boton;
}

function pintarVistaInfo(sala) {
  const linea = document.createElement("p");
  if (sala.estado === "terminada") {
    linea.textContent = "Partida terminada.";
  } else if (sala.es_mi_turno) {
    const movimiento = sala.movimiento || {};
    if (movimiento.fase === "esperando_destino" ||
        (movimiento.destinos || []).length > 0) {
      linea.textContent = "Elige una ubicación disponible.";
    } else if (movimiento.puede_sospechar) {
      linea.textContent = "Has llegado. Pulsa la ubicación para ver tus opciones.";
    } else if (movimiento.puede_tirar && movimiento.pasadizo) {
      linea.textContent = "Tira el dado o usa el pasadizo disponible.";
    } else if (movimiento.puede_tirar) {
      linea.textContent = "Tira el dado.";
    } else {
      linea.textContent = "TU TURNO";
    }
  } else {
    linea.textContent =
      `Turno de ${sala.turno_alias || "—"}. Pulsa una ubicación o un peón para consultar.`;
  }
  vistaContextual.appendChild(linea);
}

function pintarVistaSospecha(sala, ubicacionId) {
  const nodo = nodoUbicacion(ubicacionId);
  const aqui = (nodo && nodo.nombre) || (sala.posicion && sala.posicion.nombre) || "";
  ubicacionContextualId = ubicacionId;
  modalContextualTitulo.textContent = aqui
    ? `SOSPECHA EN ${aqui.toUpperCase()}` : "FORMULAR SOSPECHA";
  modalContextualDetalle.innerHTML = "";
  modalContextualDetalle.classList.add("modo-sospecha-compacta");
  imagenUbicacion.src = "";
  imagenUbicacion.alt = "";
  imagenUbicacion.hidden = true;
  btnMoverUbicacionCanvas.hidden = true;
  btnCerrarUbicacion.hidden = true;
  modalUbicacionCaja.setAttribute("aria-label", modalContextualTitulo.textContent);
  // La ubicación la fija el servidor (lugar de entrada): solo se piden
  // sospechoso y objeto, con datos canónicos de la propia hoja privada.
  const cartas = sala.investigacion || [];
  const cartasPropias = new Set((sala.mis_cartas || []).map((carta) => carta.id));
  let sospechosoSeleccionado = "";
  let objetoSeleccionado = "";

  function crearGrupoSelector(categoria) {
    const grupo = document.createElement("div");
    grupo.className = "selector-cartas-sospecha";
    grupo.dataset.categoria = categoria;
    grupo.setAttribute("role", "group");
    cartas.filter((carta) => carta.categoria === categoria).forEach((carta) => {
      const esPropia = cartasPropias.has(carta.id);
      const fueVista = carta.estado === "vista";
      const boton = crearCartaVisual(carta, { esPropia, fueVista, mostrarNombre: false, alPulsar: () => {
        Array.from(grupo.children).forEach((opcion) => {
          opcion.classList.remove("seleccionada");
          opcion.setAttribute("aria-pressed", "false");
        });
        boton.classList.add("seleccionada");
        boton.setAttribute("aria-pressed", "true");
        if (categoria === "sospechoso") sospechosoSeleccionado = carta.id;
        else objetoSeleccionado = carta.id;
        confirmar.disabled = !sospechosoSeleccionado || !objetoSeleccionado;
      } });
      boton.classList.add("carta-sospecha-compacta");
      grupo.appendChild(boton);
    });
    return grupo;
  }

  const etiquetaS = document.createElement("label");
  etiquetaS.textContent = "¿QUIÉN ESCONDIÓ EL MEDALLÓN?";
  modalContextualDetalle.appendChild(etiquetaS);
  const grupoSospechosos = crearGrupoSelector("sospechoso");
  grupoSospechosos.setAttribute("aria-label", "Selecciona un sospechoso");
  modalContextualDetalle.appendChild(grupoSospechosos);
  const etiquetaO = document.createElement("label");
  etiquetaO.textContent = "¿DÓNDE ESCONDIÓ EL MEDALLÓN?";
  modalContextualDetalle.appendChild(etiquetaO);
  const grupoObjetos = crearGrupoSelector("objeto");
  grupoObjetos.setAttribute("aria-label", "Selecciona un objeto");
  modalContextualDetalle.appendChild(grupoObjetos);
  const confirmar = document.createElement("button");
  confirmar.type = "button";
  confirmar.textContent = "CONFIRMAR SOSPECHA";
  confirmar.disabled = true;
  confirmar.addEventListener("click", () => {
    if (!sospechosoSeleccionado || !objetoSeleccionado || !sala.posicion) {
      error.textContent = "Selecciona sospechoso y objeto.";
      return;
    }
    confirmar.disabled = true;
    ws.send(JSON.stringify({
      accion: "formular_sospecha",
      sospechoso_id: sospechosoSeleccionado,
      lugar_id: sala.posicion.id,
      objeto_id: objetoSeleccionado,
    }));
    cerrarCartaUbicacion();
  });
  modalContextualDetalle.appendChild(confirmar);
  const volver = document.createElement("button");
  volver.type = "button";
  volver.className = "secundario";
  volver.textContent = "VOLVER";
  volver.addEventListener("click", () => {
    const ubicacion = nodoUbicacion(ubicacionContextualId);
    if (ubicacion) abrirCartaUbicacion(ubicacion, focoAntesDeUbicacion);
  });
  modalContextualDetalle.appendChild(volver);
  pintarPanel(sala);
  modalUbicacion.hidden = false;
  if (volver.focus) volver.focus();
}

function pintarPanel(sala) {
  if (!vistaContextual) return;
  vistaContextual.innerHTML = "";
  vistaContextual.hidden = false;
  pintarVistaInfo(sala);
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

if (btnCopiarCodigo) {
  btnCopiarCodigo.addEventListener("click", () => {
    const marcar = () => {
      btnCopiarCodigo.textContent = "¡COPIADO!";
    };
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(codigo).then(marcar, marcar);
      } else if (document.execCommand) {
        const area = document.createElement("textarea");
        area.value = codigo;
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        document.body.removeChild(area);
        marcar();
      }
    } catch (fallo) {
      error.textContent = "No se pudo copiar el código.";
    }
  });
}

function cartaHoja(entrada, cartasPropias) {
  const esPropia = cartasPropias.has(entrada.id);
  const fueVista = entrada.estado === "vista";
  return crearCartaVisual(entrada, {
    esPropia,
    fueVista,
    descartada: entrada.estado === "descartada",
    compacta: true,
    mostrarNombre: false,
    alPulsar: esPropia || fueVista ? null : () => {
      if (errorHoja) errorHoja.textContent = "";
      ws.send(JSON.stringify({
        accion: "marcar_investigacion",
        carta_id: entrada.id,
        estado: entrada.estado === "descartada" ? "sin_informacion" : "descartada",
      }));
    },
  });
}

const CATEGORIAS_HOJA = ["sospechoso", "lugar", "objeto"];
// Grupos independientes: plegar uno nunca cierra los otros.
const GRUPO_ABIERTO = { sospechoso: true, lugar: true, objeto: true };

function categoriaDe(entrada) {
  return String((entrada && entrada.categoria) || "")
    .trim()
    .toLowerCase();
}

function pintarHoja(investigacion, misCartas = []) {
  if (!hojaDiv) {
    return;
  }
  hojaDiv.innerHTML = "";
  if (errorHoja) {
    errorHoja.textContent = "";
  }
  const lista = Array.isArray(investigacion) ? investigacion : [];
  const cartasPropias = new Set((misCartas || []).map((carta) => carta.id));
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
    const titulo = document.createElement("h3");
    titulo.textContent = `${TITULOS[categoria]} (${entradas.length})`;
    grupo.appendChild(titulo);
    const cuerpo = document.createElement("div");
    cuerpo.className = "hoja-cuerpo hoja-grid-cartas";
    entradas.forEach((entrada) => {
      cuerpo.appendChild(cartaHoja(entrada, cartasPropias));
    });
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
      grupo.appendChild(cartaHoja(entrada, cartasPropias));
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

const resolverSeleccion = { sospechoso: "", lugar: "", objeto: "" };

function nombreCartaResolver(cartas, cartaId) {
  const carta = (cartas || []).find((entrada) => entrada.id === cartaId);
  return carta ? carta.nombre : "";
}

function pintarGrupoResolver(contenedor, cartas, categoria, clave) {
  contenedor.innerHTML = "";
  const cartasPropias = new Set(((ultimaSala && ultimaSala.mis_cartas) || []).map((carta) => carta.id));
  cartas.filter((carta) => carta.categoria === categoria).forEach((carta) => {
    const boton = crearCartaVisual(carta, {
      esPropia: cartasPropias.has(carta.id),
      fueVista: carta.estado === "vista",
      mostrarNombre: false,
      seleccionada: resolverSeleccion[clave] === carta.id,
      alPulsar: () => {
        resolverSeleccion[clave] = carta.id;
        Array.from(contenedor.children).forEach((opcion) => {
          const activa = opcion.dataset.cartaId === carta.id;
          opcion.classList.toggle("seleccionada", activa);
          opcion.setAttribute("aria-pressed", activa ? "true" : "false");
        });
        btnConfirmarResolver.disabled = !resolverSeleccion.sospechoso ||
          !resolverSeleccion.lugar || !resolverSeleccion.objeto;
      },
    });
    contenedor.appendChild(boton);
  });
}

function abrirResolver() {
  const cartas = (ultimaSala && ultimaSala.investigacion) || [];
  resolverSeleccion.sospechoso = "";
  resolverSeleccion.lugar = "";
  resolverSeleccion.objeto = "";
  pintarGrupoResolver(grupoResolverSospechoso, cartas, "sospechoso", "sospechoso");
  pintarGrupoResolver(grupoResolverLugar, cartas, "lugar", "lugar");
  pintarGrupoResolver(grupoResolverObjeto, cartas, "objeto", "objeto");
  btnConfirmarResolver.disabled = true;
  modalResolver.hidden = false;
}

btnResolver.addEventListener("click", abrirResolver);
document.getElementById("btn-cancelar-resolver").addEventListener("click", () => {
  modalResolver.hidden = true;
});

document.getElementById("btn-confirmar-resolver").addEventListener("click", () => {
  const cartas = (ultimaSala && ultimaSala.investigacion) || [];
  if (!resolverSeleccion.sospechoso || !resolverSeleccion.lugar || !resolverSeleccion.objeto) {
    error.textContent = "Selecciona sospechoso, lugar y objeto.";
    return;
  }
  confResolverSospechoso.textContent = `Sospechoso: ${nombreCartaResolver(cartas, resolverSeleccion.sospechoso)}`;
  confResolverLugar.textContent = `Lugar: ${nombreCartaResolver(cartas, resolverSeleccion.lugar)}`;
  confResolverObjeto.textContent = `Objeto: ${nombreCartaResolver(cartas, resolverSeleccion.objeto)}`;
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
    sospechoso_id: resolverSeleccion.sospechoso,
    lugar_id: resolverSeleccion.lugar,
    objeto_id: resolverSeleccion.objeto,
  }));
  modalConfirmarResolver.hidden = true;
});
