/* Sala: sincronización en tiempo real por WebSocket (Microfase 4B).
   Cada conexión recibe solo su estado privado: nunca ve las
   cartas ni la hoja de investigación de otros jugadores,
   ni el misterio secreto. */
"use strict";

const codigo = document.getElementById("codigo").textContent.trim();
const jugadorId = sessionStorage.getItem("jugador_id") || "";

const estado = document.getElementById("estado");
const error = document.getElementById("error");
const btnComenzar = document.getElementById("btn-comenzar");
const lobbyPersonajes = document.getElementById("lobby-personajes");
const personajesDiv = document.getElementById("personajes");
const modalPreparacionMovil = document.getElementById("modal-preparacion-movil");
const btnEntrarPantallaCompleta = document.getElementById("btn-entrar-pantalla-completa");
const interfazSala = document.querySelector(".interfaz-sala");
const partida = document.getElementById("partida");
const barraControlesInferior = document.getElementById("barra-controles-inferior");
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
const btnHistorial = document.getElementById("btn-historial");
const btnHistorialPresentacion = document.getElementById("btn-historial-presentacion");
const btnHistorialRefutacion = document.getElementById("btn-historial-refutacion");
const btnHistorialRevelacion = document.getElementById("btn-historial-revelacion");
const modalHistorial = document.getElementById("modal-historial");
const historialLista = document.getElementById("historial-lista");
const btnCerrarHistorial = document.getElementById("btn-cerrar-historial");
const btnChat = document.getElementById("btn-chat");
const chatPendientes = document.getElementById("chat-pendientes");
const modalChat = document.getElementById("modal-chat");
const dialogoChat = modalChat
  ? modalChat.querySelector('[role="dialog"]')
  : null;
const listaMensajesChat = document.getElementById("chat-mensajes");
const formularioChat = document.getElementById("chat-formulario");
const entradaChat = document.getElementById("chat-entrada");
const estadoChat = document.getElementById("chat-estado");
const btnCerrarChat = document.getElementById("btn-cerrar-chat");
const jugadaDiv = document.getElementById("jugada");
const btnSospecha = document.getElementById("btn-sospecha");
const modalSospecha = document.getElementById("modal-sospecha");
const modalRefutacion = document.getElementById("modal-refutacion");
const opcionesRefutacion = document.getElementById("opciones-refutacion");
const refutacionTitulo = document.getElementById("refutacion-titulo");
const btnConfirmarRefutacion = document.getElementById("btn-confirmar-refutacion");
const btnContinuarRefutacion = document.getElementById("btn-continuar-refutacion");
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
const confResolverCartas = document.getElementById("conf-resolver-cartas");
const modalResolucionFallida = document.getElementById("modal-resolucion-fallida");
const resolucionFallidaCartas = document.getElementById("resolucion-fallida-cartas");
const modalVictoria = document.getElementById("modal-victoria");
const victoriaTitulo = document.getElementById("victoria-titulo");
const victoriaSubtitulo = document.getElementById("victoria-subtitulo");
const victoriaCartas = document.getElementById("victoria-cartas");
const victoriaNota = document.getElementById("victoria-nota");
const btnJugarDeNuevo = document.getElementById("btn-jugar-de-nuevo");
const btnVictoriaInvestigacion = document.getElementById("btn-victoria-investigacion");
const btnSeguirRefutando = document.getElementById("btn-seguir-refutando");
const btnRefutarAutomatico = document.getElementById("btn-refutar-automatico");
const modalPresentacionSospecha = document.getElementById("modal-presentacion-sospecha");
const presentacionSospechaTitulo = document.getElementById("presentacion-sospecha-titulo");
const presentacionSospechaCartas = document.getElementById("presentacion-sospecha-cartas");
const presentacionResultadoTexto = document.getElementById("presentacion-resultado-texto");
const presentacionResultadoCartas = document.getElementById("presentacion-resultado-cartas");
const presentacionSospechaAviso = document.getElementById("presentacion-sospecha-aviso");
const btnContinuarPresentacionSospecha = document.getElementById("btn-continuar-presentacion-sospecha");
const avisoTimeoutRefutacion = document.getElementById("aviso-timeout-refutacion");
const modalInactividad = document.getElementById("modal-inactividad");
const inactividadTexto = document.getElementById("inactividad-texto");
const btnPasarAPnj = document.getElementById("btn-pasar-a-pnj");
const btnSeguirEsperando = document.getElementById("btn-seguir-esperando");
// Microfase 2 · Ritmo de las acciones automáticas. Control provisional del
// anfitrión: la autoridad real la comprueba el servidor con la credencial.
const panelRitmo = document.getElementById("admin-ritmo");
const ritmoValor = document.getElementById("admin-ritmo-valor");
const btnRitmoMas = document.getElementById("btn-ritmo-mas");
const btnRitmoMenos = document.getElementById("btn-ritmo-menos");
// Microfase 3 · Pausa. El aviso NO es del anfitrión: lo ve todo el mundo.
const avisoPausa = document.getElementById("admin-pausa-aviso");
const btnPausarPartida = document.getElementById("btn-pausar-partida");
const btnReanudarPartida = document.getElementById("btn-reanudar-partida");
// Microfase 4 · Guardar partida.
const btnGuardarPartida = document.getElementById("btn-guardar-partida");
const estadoGuardar = document.getElementById("admin-guardar-estado");
const btnConfiguracionPartida = document.getElementById("btn-configuracion-partida");
const modalConfiguracionPartida = document.getElementById("modal-configuracion-partida");
const dialogoConfiguracionPartida = modalConfiguracionPartida
  ? modalConfiguracionPartida.querySelector('[role="dialog"]')
  : null;
const btnCerrarConfiguracionPartida = document.getElementById(
  "btn-cerrar-configuracion-partida"
);
const RITMO_MINIMO = 1;
const RITMO_MAXIMO = 10;
// 8B.32 · Último aviso de inactividad ya tratado por ESTE cliente. El plazo
// es canónico del servidor: aquí solo se recuerda qué id se ha visto para que
// una redifusión no reabra el popup (mismo patrón que la presentación).
let inactividadAvisoVisto = null;
let inactividadAvisoVigente = null;
// 8B.33B · Último estado de partida visto por ESTE cliente. Sirve para
// distinguir la transición real al final de un simple repintado.
let estadoPartidaVisto = null;
// 8B.35 · Si este cliente ya cerró el popup del final. Se reinicia al salir
// del estado terminada (revancha o salida), de modo que una recarga con la
// partida ya terminada vuelve a reconstruir el final, y una revancha muestra
// el popup de su propio final.
let victoriaDescartada = false;
const finalPartida = document.getElementById("final-partida");
const modoPartida = document.getElementById("modo-partida");
const resumenSala = document.getElementById("resumen-sala");
const bloqueCodigo = document.getElementById("bloque-codigo");
const bloqueOrden = document.getElementById("bloque-orden");
const btnCopiarCodigo = document.getElementById("btn-copiar-codigo");
const contadorJugadores = document.getElementById("contador-jugadores");
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
const btnSospechaUbicacion = document.getElementById("btn-sospecha-ubicacion");
let focoAntesDeUbicacion = null;
let destinoUbicacionModal = null;
let rendererCanvas = null;
let canvasFallido = false;

const modalesSala = document.querySelectorAll
  ? Array.from(document.querySelectorAll(".modal"))
  : [];

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
let resolucionPendienteLocal = null;
let presentacionSospechaVisibleId = null;
let presentacionSospechaDescartadaId = null;
let cartaRefutacionSeleccionadaId = null;
let focoAntesDeHistorial = null;
let focoAntesDeChat = null;
let mensajesChat = [];
let mensajesChatPendientes = 0;
let focoTrasPreparacionMovil = null;
let preparacionMovilCompletadaEnMemoria = false;
const CLAVE_PREPARACION_MOVIL = `preparacion_movil:${codigo}:${jugadorId}`;
const CLAVE_ENTRADA_PREPARACION_MOVIL = "preparacion_movil_pendiente";

function esTelefonoMovil() {
  const navegador = typeof navigator === "undefined" ? {} : navigator;
  const indicadoPorNavegador = Boolean(
    navegador.userAgentData && navegador.userAgentData.mobile
  );
  const tactil = (navegador.maxTouchPoints || 0) > 0 || "ontouchstart" in window;
  const punteroGrueso = Boolean(
    window.matchMedia && window.matchMedia("(pointer: coarse)").matches
  );
  const anchoPantalla = (window.screen && window.screen.width) || window.innerWidth;
  const altoPantalla = (window.screen && window.screen.height) || window.innerHeight;
  const ladoCorto = Math.min(anchoPantalla || 0, altoPantalla || 0);
  return indicadoPorNavegador || (tactil && punteroGrueso && ladoCorto > 0 && ladoCorto <= 600);
}

function preparacionMovilVista() {
  if (preparacionMovilCompletadaEnMemoria) return true;
  try {
    return sessionStorage.getItem(CLAVE_PREPARACION_MOVIL) === "1";
  } catch (errorAlLeerSesion) {
    return false;
  }
}

function guardarPreparacionMovilVista() {
  preparacionMovilCompletadaEnMemoria = true;
  try {
    sessionStorage.setItem(CLAVE_PREPARACION_MOVIL, "1");
  } catch (errorAlGuardarSesion) {
    // La marca en memoria basta para no repetir la escena en esta página.
  }
}

function borrarEntradaPreparacionMovil() {
  try {
    sessionStorage.removeItem(CLAVE_ENTRADA_PREPARACION_MOVIL);
  } catch (errorAlBorrarEntrada) {
    // La marca es auxiliar y nunca debe bloquear el flujo de la sala.
  }
}

function entradaPreparacionMovilPendiente() {
  try {
    const cruda = sessionStorage.getItem(CLAVE_ENTRADA_PREPARACION_MOVIL);
    if (!cruda) return null;
    const entrada = JSON.parse(cruda);
    if (entrada.codigo !== codigo || entrada.jugador_id !== jugadorId) {
      borrarEntradaPreparacionMovil();
      return null;
    }
    return entrada;
  } catch (errorAlLeerEntrada) {
    borrarEntradaPreparacionMovil();
    return null;
  }
}

function debeMostrarPreparacionMovil(sala) {
  return Boolean(
    sala && sala.estado === "esperando" && !sala.personaje_id &&
    esTelefonoMovil() && !preparacionMovilVista()
  );
}

function ajustarSuperficiePreparacionMovil() {
  if (!modalPreparacionMovil) return;
  const vista = window.visualViewport;
  const ancho = vista ? vista.width : window.innerWidth;
  const alto = vista ? vista.height : window.innerHeight;
  const izquierda = vista ? vista.offsetLeft : 0;
  const arriba = vista ? vista.offsetTop : 0;
  modalPreparacionMovil.style.left = `${izquierda}px`;
  modalPreparacionMovil.style.top = `${arriba}px`;
  modalPreparacionMovil.style.width = `${ancho}px`;
  modalPreparacionMovil.style.height = `${alto}px`;
}

function abrirPreparacionMovil(activador) {
  if (!modalPreparacionMovil || !btnEntrarPantallaCompleta) return false;
  if (!modalPreparacionMovil.hidden) return true;
  focoTrasPreparacionMovil = activador || null;
  ajustarSuperficiePreparacionMovil();
  modalPreparacionMovil.hidden = false;
  // La escena ya está pintada por HTML/CSS. Se hace visible por estado normal
  // antes de retirar el bloqueo inicial, de modo que no existe un fotograma
  // intermedio en el que pueda aparecer la sala.
  document.documentElement.classList.add("preparacion-movil-activa");
  if (interfazSala) interfazSala.inert = true;
  document.documentElement.classList.remove("preparacion-movil-inicial");
  if (
    window.PreparacionMovilInicial &&
    typeof window.PreparacionMovilInicial.tomarControl === "function"
  ) {
    window.PreparacionMovilInicial.tomarControl();
  }
  btnEntrarPantallaCompleta.focus();
  sincronizarBarraControlesInferior();
  return true;
}

function completarPreparacionMovil() {
  guardarPreparacionMovilVista();
  borrarEntradaPreparacionMovil();
  // La petición nace directamente de este toque. Su resultado no se espera:
  // ni fullscreen ni el bloqueo horizontal pueden impedir elegir personaje.
  if (
    window.PantallaCompleta &&
    typeof window.PantallaCompleta.solicitarInmersionHorizontal === "function"
  ) {
    window.PantallaCompleta.solicitarInmersionHorizontal();
  }
  modalPreparacionMovil.hidden = true;
  document.documentElement.classList.remove("preparacion-movil-activa");
  if (interfazSala) interfazSala.inert = false;
  sincronizarBarraControlesInferior();
  if (focoTrasPreparacionMovil && focoTrasPreparacionMovil.focus) {
    focoTrasPreparacionMovil.focus();
  }
  focoTrasPreparacionMovil = null;
}

function prepararInterfazMovilAntesDeMostrar(sala, opciones = {}) {
  const entradaPendiente = entradaPreparacionMovilPendiente();
  const preparacionCompletadaEnEsteDocumento = Boolean(
    window.PreparacionPortadaMovil &&
    typeof window.PreparacionPortadaMovil.estaCompletada === "function" &&
    window.PreparacionPortadaMovil.estaCompletada()
  );
  if (opciones.cambioInterno === true || preparacionCompletadaEnEsteDocumento) {
    guardarPreparacionMovilVista();
    borrarEntradaPreparacionMovil();
    document.documentElement.classList.remove("preparacion-movil-inicial");
    document.documentElement.classList.remove("preparacion-movil-activa");
    if (interfazSala) interfazSala.inert = false;
    return false;
  }
  if (!esTelefonoMovil()) {
    if (entradaPendiente) borrarEntradaPreparacionMovil();
    document.documentElement.classList.remove("preparacion-movil-inicial");
    return false;
  }
  if (entradaPendiente && entradaPendiente.preparacion_completada === true) {
    // La misma escena ya se completó justo antes del formulario en portada.
    // Se consume la señal y se marca esta sala para que estados WebSocket
    // posteriores no vuelvan a abrirla durante esta navegación.
    guardarPreparacionMovilVista();
    borrarEntradaPreparacionMovil();
    document.documentElement.classList.remove("preparacion-movil-inicial");
    return false;
  }
  const preparacionInicialActiva = document.documentElement.classList.contains(
    "preparacion-movil-inicial"
  );
  if (preparacionInicialActiva || entradaPendiente || debeMostrarPreparacionMovil(sala)) {
    return abrirPreparacionMovil(null);
  }
  return false;
}

window.PreparacionSalaMovil = {
  actualizar: prepararInterfazMovilAntesDeMostrar,
  completar: completarPreparacionMovil,
};

if (btnEntrarPantallaCompleta) {
  btnEntrarPantallaCompleta.addEventListener("click", completarPreparacionMovil);
}
if (modalPreparacionMovil) {
  modalPreparacionMovil.addEventListener("keydown", (evento) => {
    if (evento.key !== "Tab") return;
    evento.preventDefault();
    btnEntrarPantallaCompleta.focus();
  });
}
if (window.addEventListener) {
  window.addEventListener("resize", ajustarSuperficiePreparacionMovil);
}
if (window.visualViewport && window.visualViewport.addEventListener) {
  window.visualViewport.addEventListener("resize", ajustarSuperficiePreparacionMovil);
  window.visualViewport.addEventListener("scroll", ajustarSuperficiePreparacionMovil);
}

// Las entradas iniciadas desde la portada abren la escena antes incluso del
// primer estado privado. El estado recibido mantiene debajo la vista correcta.
prepararInterfazMovilAntesDeMostrar(null);

function sincronizarBarraControlesInferior() {
  if (!barraControlesInferior) return;
  const tableroPrincipalVisible = Boolean(
    partida &&
    !partida.hidden &&
    document.body &&
    document.body.classList &&
    document.body.classList.contains("en-partida")
  );
  const modalVisible = modalesSala.some((modal) => !modal.hidden);
  barraControlesInferior.hidden = !tableroPrincipalVisible || modalVisible;
}

function actualizarIndicadorChat() {
  if (!btnChat || !chatPendientes) return;
  chatPendientes.hidden = mensajesChatPendientes === 0;
  chatPendientes.textContent = mensajesChatPendientes > 99
    ? "99+"
    : String(mensajesChatPendientes);
  const etiqueta = mensajesChatPendientes
    ? `Chat, ${mensajesChatPendientes} mensajes nuevos`
    : "Chat";
  btnChat.setAttribute("aria-label", etiqueta);
  btnChat.setAttribute("title", etiqueta);
}

function pintarMensajesChat() {
  if (!listaMensajesChat) return;
  listaMensajesChat.innerHTML = "";
  if (!mensajesChat.length) {
    const vacio = document.createElement("p");
    vacio.className = "chat-vacio";
    vacio.textContent = "Todavía no hay mensajes en esta partida.";
    listaMensajesChat.appendChild(vacio);
  } else {
    mensajesChat.slice(-100).forEach((mensaje) => {
      const articulo = document.createElement("article");
      const esPropio = mensaje.jugador_id === jugadorId;
      articulo.className = esPropio
        ? "chat-mensaje chat-mensaje-propio"
        : "chat-mensaje chat-mensaje-recibido";
      const alias = document.createElement("strong");
      alias.className = "chat-mensaje-alias";
      alias.textContent = mensaje.alias || "Jugador";
      const texto = document.createElement("p");
      texto.className = "chat-mensaje-texto";
      texto.textContent = mensaje.texto || "";
      articulo.appendChild(alias);
      articulo.appendChild(texto);
      listaMensajesChat.appendChild(articulo);
    });
  }
  listaMensajesChat.scrollTop = listaMensajesChat.scrollHeight;
}

function abrirChat() {
  if (!modalChat || !btnChat || btnChat.hidden) return;
  focoAntesDeChat = document.activeElement || btnChat;
  modalChat.hidden = false;
  mensajesChatPendientes = 0;
  actualizarIndicadorChat();
  pintarMensajesChat();
  btnChat.setAttribute("aria-expanded", "true");
  sincronizarBarraControlesInferior();
  if (entradaChat && entradaChat.focus) entradaChat.focus();
}

function cerrarChat() {
  if (!modalChat || modalChat.hidden) return;
  modalChat.hidden = true;
  btnChat.setAttribute("aria-expanded", "false");
  sincronizarBarraControlesInferior();
  if (focoAntesDeChat && focoAntesDeChat.focus) focoAntesDeChat.focus();
}

function enviarMensajeChat(evento) {
  evento.preventDefault();
  if (!entradaChat || !ws || ws.readyState !== WebSocket.OPEN) {
    if (estadoChat) estadoChat.textContent = "El chat no está conectado.";
    return;
  }
  const texto = entradaChat.value.trim();
  if (!texto) {
    if (estadoChat) estadoChat.textContent = "Escribe un mensaje antes de enviarlo.";
    return;
  }
  ws.send(JSON.stringify({ accion: "chat", texto }));
  entradaChat.value = "";
  if (estadoChat) estadoChat.textContent = "";
}

if (btnChat) btnChat.addEventListener("click", abrirChat);
if (btnCerrarChat) btnCerrarChat.addEventListener("click", cerrarChat);
if (modalChat) {
  modalChat.addEventListener("click", (evento) => {
    if (evento.target === modalChat) cerrarChat();
  });
}
if (formularioChat) {
  formularioChat.addEventListener("submit", enviarMensajeChat);
}
if (document.addEventListener) {
  document.addEventListener("keydown", (evento) => {
    if (!modalChat || modalChat.hidden) return;
    if (evento.key === "Escape") {
      evento.preventDefault();
      cerrarChat();
      return;
    }
    if (evento.key !== "Tab" || !dialogoChat) return;
    const controles = Array.from(
      dialogoChat.querySelectorAll(
        "button:not([hidden]):not([disabled]), input:not([hidden]):not([disabled])"
      )
    );
    if (!controles.length) {
      evento.preventDefault();
      dialogoChat.focus();
      return;
    }
    const primero = controles[0];
    const ultimo = controles[controles.length - 1];
    if (evento.shiftKey && document.activeElement === primero) {
      evento.preventDefault();
      ultimo.focus();
    } else if (!evento.shiftKey && document.activeElement === ultimo) {
      evento.preventDefault();
      primero.focus();
    }
  });
}
actualizarIndicadorChat();

window.sincronizarBarraControlesInferior =
  sincronizarBarraControlesInferior;
sincronizarBarraControlesInferior();
if (typeof MutationObserver !== "undefined" && document.body) {
  const observadorBarraControles = new MutationObserver(
    sincronizarBarraControlesInferior
  );
  observadorBarraControles.observe(document.body, {
    attributes: true,
    attributeFilter: ["class"],
  });
  if (partida) {
    observadorBarraControles.observe(partida, {
      attributes: true,
      attributeFilter: ["hidden"],
    });
  }
  modalesSala.forEach((modal) => {
    observadorBarraControles.observe(modal, {
      attributes: true,
      attributeFilter: ["hidden"],
    });
  });
}

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
      // El lobby puede haberse pintado antes de que llegara el manifiesto:
      // sin este repintado las cartas quedan con src vacío (imagen rota).
      pintarPersonajes(ultimaSala);
      pintarSala(ultimaSala);
    }
  });

const protocolo = window.location.protocol === "https:" ? "wss" : "ws";
const ws = new WebSocket(
  `${protocolo}://${window.location.host}/ws/${encodeURIComponent(codigo)}/${encodeURIComponent(jugadorId)}`
);

ws.onmessage = (evento) => {
  const mensaje = JSON.parse(evento.data);
  if (mensaje.tipo === "chat_mensaje") {
    if (
      mensaje.mensaje &&
      typeof mensaje.mensaje.alias === "string" &&
      typeof mensaje.mensaje.texto === "string"
    ) {
      mensajesChat.push(mensaje.mensaje);
      mensajesChat = mensajesChat.slice(-100);
      if (modalChat && modalChat.hidden) mensajesChatPendientes += 1;
      else mensajesChatPendientes = 0;
      actualizarIndicadorChat();
      pintarMensajesChat();
    }
  } else if (mensaje.tipo === "error_chat") {
    if (estadoChat) estadoChat.textContent = mensaje.detalle;
  } else if (mensaje.tipo === "estado_privado") {
    if (Array.isArray(mensaje.sala.chat_historial)) {
      mensajesChat = mensaje.sala.chat_historial.slice(-100);
      mensajesChatPendientes = 0;
      actualizarIndicadorChat();
      pintarMensajesChat();
    }
    // El anfitrión recupera su secreto si aún no lo tiene (por ejemplo
    // tras abrir la sala en una pestaña nueva). Nadie más lo pide y la
    // petición no altera el estado de la partida.
    if (
      mensaje.sala.es_anfitrion &&
      !sessionStorage.getItem("credencial_admin")
    ) {
      ws.send(JSON.stringify({ accion: "pedir_credencial_admin" }));
    }
    presentarEstadoPrivado(mensaje.sala);
  } else if (mensaje.tipo === "credencial_admin") {
    sessionStorage.setItem("credencial_admin", mensaje.credencial);
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
  abrirLlegadaContextual(animacion.movimiento);
}

function iniciarAnimacionMovimiento(movimiento) {
  const personajeId = movimiento.personaje_id;
  cancelarAnimacionMovimiento(personajeId);
  posicionesVisuales.set(personajeId, movimiento.origen_id);
  const token = ++secuenciaAnimacion;
  const animacion = { token, temporizador: null, movimiento };
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
    prepararInterfazMovilAntesDeMostrar(sala);
    pintarSala(sala);
    presentarResolucionFallida(sala);
    presentarVictoria(sala);
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
    presentarResolucionFallida(sala);
    presentarVictoria(sala);
    return;
  }
  if (esMovimientoNuevo && movimiento && movimiento.personaje_id) {
    cancelarAnimacionMovimiento(movimiento.personaje_id);
  }
  ultimaSala = sala;
  prepararInterfazMovilAntesDeMostrar(sala);
  pintarSala(sala);
  presentarResolucionFallida(sala);
  presentarVictoria(sala);
  if (esMovimientoNuevo && movimiento && movimiento.tipo === "pasadizo") {
    abrirLlegadaContextual(movimiento);
  }
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
    const ocupante = aliasDePersonaje(sala, p.id);
    const esMio = sala.personaje_id === p.id;
    const carta = { id: p.id, nombre: p.nombre, categoria: "sospechoso" };
    if (esMio) {
      const tarjeta = crearCartaVisual(carta, { seleccionada: true, mostrarNombre: false });
      tarjeta.appendChild(crearMarcaLobby("TU PERSONAJE", "marca-propia"));
      tarjeta.addEventListener("click", () => {
        error.textContent = "";
      });
      personajesDiv.appendChild(tarjeta);
    } else if (ocupante) {
      const tarjeta = crearCartaVisual(carta, { mostrarNombre: false });
      tarjeta.classList.add("lobby-ocupada");
      tarjeta.appendChild(crearMarcaLobby("ELEGIDO"));
      personajesDiv.appendChild(tarjeta);
    } else {
      const tarjeta = crearCartaVisual(carta, {
        mostrarNombre: false,
        alPulsar: () => {
          error.textContent = "";
          ws.send(JSON.stringify({ accion: "elegir_personaje", personaje_id: p.id }));
        },
      });
      tarjeta.appendChild(crearMarcaLobby("DISPONIBLE", "marca-suave"));
      personajesDiv.appendChild(tarjeta);
    }
  });
}

function crearMarcaLobby(texto, modificador) {
  const marca = document.createElement("span");
  marca.className = "carta-selector-marca" + (modificador ? ` ${modificador}` : "");
  marca.textContent = texto;
  return marca;
}

function pintarInactividad(sala) {
  // 8B.32 · El aviso llega solo al anfitrión y solo con el alias. Nunca
  // reejecuta nada: el servidor decide. Un aviso ya visto no se reabre.
  const aviso = (sala && sala.inactividad) || null;
  if (!aviso || aviso.aviso_id === inactividadAvisoVisto) {
    modalInactividad.hidden = true;
    inactividadAvisoVigente = null;
    if (!aviso) inactividadAvisoVisto = null;
    return;
  }
  inactividadAvisoVisto = aviso.aviso_id;
  inactividadAvisoVigente = aviso.aviso_id;
  inactividadTexto.textContent =
    `${aviso.alias} lleva más de un minuto sin realizar la acción necesaria para continuar.`;
  modalInactividad.hidden = false;
  if (btnSeguirEsperando.focus) btnSeguirEsperando.focus();
}

function cerrarInactividad() {
  modalInactividad.hidden = true;
  inactividadAvisoVigente = null;
}

function pintarRitmo(sala) {
  // Microfase 3: el aviso de pausa es para TODOS. El panel con los botones
  // es solo del anfitrión. Un jugador normal puede ver el aviso, pero no
  // tocar nada: el servidor rechaza sus acciones con o sin botones.
  const pausada = Boolean(sala && sala.pausada);
  if (avisoPausa) avisoPausa.hidden = !pausada;
  if (document.body && document.body.classList) {
    document.body.classList.toggle("partida-en-pausa", pausada);
  }
  if (!panelRitmo) return;
  const esAnfitrion = Boolean(sala && sala.es_anfitrion);
  const partidaActiva = Boolean(
    sala && (sala.estado === "iniciada" || sala.estado === "terminada")
  );
  const puedeConfigurar = esAnfitrion && partidaActiva;
  if (btnConfiguracionPartida) btnConfiguracionPartida.hidden = !puedeConfigurar;
  if (!puedeConfigurar && modalConfiguracionPartida) {
    modalConfiguracionPartida.hidden = true;
    if (btnConfiguracionPartida) {
      btnConfiguracionPartida.setAttribute("aria-expanded", "false");
    }
  }
  panelRitmo.hidden = !puedeConfigurar;
  // Solo se muestra la acción que toca: pausada -> REANUDAR. Y solo el
  // anfitrión tiene alguna de las dos.
  if (btnPausarPartida) btnPausarPartida.hidden = !puedeConfigurar || pausada;
  if (btnReanudarPartida) btnReanudarPartida.hidden = !puedeConfigurar || !pausada;
  // GUARDAR también es solo del anfitrión, y se puede usar en pausa.
  if (btnGuardarPartida) btnGuardarPartida.hidden = !puedeConfigurar;
  if (!puedeConfigurar) return;
  const valor = Number(sala.velocidad_acciones) || 1;
  ritmoValor.textContent = `${valor} S`;
  // Los topes se muestran como deshabilitados: el servidor vuelve a validar.
  // Durante la pausa se pueden ajustar: no provoca ningún avance.
  if (btnRitmoMas) btnRitmoMas.disabled = valor >= RITMO_MAXIMO;
  if (btnRitmoMenos) btnRitmoMenos.disabled = valor <= RITMO_MINIMO;
}

function cerrarConfiguracionPartida(devolverFoco = true) {
  if (!modalConfiguracionPartida || modalConfiguracionPartida.hidden) return;
  modalConfiguracionPartida.hidden = true;
  sincronizarBarraControlesInferior();
  if (btnConfiguracionPartida) {
    btnConfiguracionPartida.setAttribute("aria-expanded", "false");
    if (devolverFoco && !btnConfiguracionPartida.hidden) {
      btnConfiguracionPartida.focus();
    }
  }
}

function abrirConfiguracionPartida() {
  if (
    !btnConfiguracionPartida ||
    btnConfiguracionPartida.hidden ||
    !panelRitmo ||
    panelRitmo.hidden ||
    !modalConfiguracionPartida
  ) {
    return;
  }
  modalConfiguracionPartida.hidden = false;
  sincronizarBarraControlesInferior();
  btnConfiguracionPartida.setAttribute("aria-expanded", "true");
  if (btnCerrarConfiguracionPartida) btnCerrarConfiguracionPartida.focus();
}

if (btnConfiguracionPartida) {
  btnConfiguracionPartida.addEventListener("click", abrirConfiguracionPartida);
}
if (btnCerrarConfiguracionPartida) {
  btnCerrarConfiguracionPartida.addEventListener("click", () =>
    cerrarConfiguracionPartida()
  );
}
if (modalConfiguracionPartida) {
  modalConfiguracionPartida.addEventListener("click", (evento) => {
    if (evento.target === modalConfiguracionPartida) {
      cerrarConfiguracionPartida();
    }
  });
}
if (document.addEventListener) {
  document.addEventListener("keydown", (evento) => {
    if (!modalConfiguracionPartida || modalConfiguracionPartida.hidden) return;
    if (evento.key === "Escape") {
      evento.preventDefault();
      cerrarConfiguracionPartida();
      return;
    }
    if (evento.key !== "Tab" || !dialogoConfiguracionPartida) return;
    const botones = Array.from(
      dialogoConfiguracionPartida.querySelectorAll(
        "button:not([hidden]):not([disabled])"
      )
    );
    if (!botones.length) {
      evento.preventDefault();
      dialogoConfiguracionPartida.focus();
      return;
    }
    const primero = botones[0];
    const ultimo = botones[botones.length - 1];
    if (evento.shiftKey && document.activeElement === primero) {
      evento.preventDefault();
      ultimo.focus();
    } else if (!evento.shiftKey && document.activeElement === ultimo) {
      evento.preventDefault();
      primero.focus();
    }
  });
}

function moverRitmo(accion) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(
    JSON.stringify({
      accion,
      credencial_admin: sessionStorage.getItem("credencial_admin"),
    })
  );
}

// Microfase 3 · Pausar y reanudar. Solo envían: el estado congelado lo
// decide el servidor, y el botón visible depende de lo que diga la sala.
if (btnPausarPartida) {
  btnPausarPartida.addEventListener("click", () => moverRitmo("pausar_partida"));
}
if (btnReanudarPartida) {
  btnReanudarPartida.addEventListener("click", () => moverRitmo("reanudar_partida"));
}

// --- Microfase 4 · Guardar partida ---------------------------------------
// El archivo lleva la solución, las manos y las notas privadas: se descarga
// por HTTP y NO se manda por el WebSocket. La credencial viaja en una
// CABECERA, nunca en la URL.
function avisarGuardado(texto, esError) {
  if (!estadoGuardar) return;
  estadoGuardar.textContent = texto;
  estadoGuardar.hidden = !texto;
  estadoGuardar.classList.toggle("error", Boolean(esError));
}

async function guardarPartida() {
  if (btnGuardarPartida) btnGuardarPartida.disabled = true;
  avisarGuardado("GUARDANDO...", false);
  try {
    const credencial = sessionStorage.getItem("credencial_admin");
    const respuesta = await fetch(`/api/partidas/${encodeURIComponent(codigo)}/guardar`, {
      headers: { "X-Token-Admin": credencial || "" },
    });
    if (!respuesta.ok) {
      let detalle = "NO SE PUDO GUARDAR LA PARTIDA.";
      try {
        const cuerpo = await respuesta.json();
        if (cuerpo && cuerpo.detalle) detalle = cuerpo.detalle.toUpperCase();
      } catch (e) {
        /* respuesta sin cuerpo JSON: se queda el texto por defecto */
      }
      avisarGuardado(detalle, true);
      return;
    }
    const texto = await respuesta.text();
    const url = URL.createObjectURL(
      new Blob([texto], { type: "application/json" })
    );
    const enlace = document.createElement("a");
    enlace.href = url;
    enlace.download = `misterio-medallon-${codigo}.json`;
    document.body.appendChild(enlace);
    enlace.click();
    document.body.removeChild(enlace);
    URL.revokeObjectURL(url);
    avisarGuardado("PARTIDA GUARDADA.", false);
  } catch (e) {
    avisarGuardado("NO SE PUDO GUARDAR LA PARTIDA.", true);
  } finally {
    if (btnGuardarPartida) btnGuardarPartida.disabled = false;
  }
}

if (btnGuardarPartida) {
  btnGuardarPartida.addEventListener("click", guardarPartida);
}

function pintarSala(sala) {
  error.textContent = "";
  // Modo de partida
  modoPartida.textContent = sala.modo === "tablero" ? "MODO TABLERO" : "MODO RÁPIDO";
  if (contadorJugadores) {
    const humanos = sala.jugadores.filter((j) => j.tipo !== "pnj").length;
    contadorJugadores.textContent = `👥 ${humanos}/6`;
  }

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
    if (bloqueOrden) bloqueOrden.hidden = true;
    total.hidden = true;
    if (resumenSala) {
      resumenSala.hidden = false;
      resumenSala.textContent = `Sala ${sala.codigo}`;
    }
    pintarTurno(sala);
    pintarCartas(sala.mis_cartas);
    pintarHoja(sala.investigacion || [], sala.mis_cartas || []);
    pintarHistorial(sala.historial || []);
    pintarJugada(sala);
    pintarMovimiento(sala);
    pintarTablero(sala);
    pintarPanel(sala);
    pintarFinal(sala);
    pintarInactividad(sala);
    pintarRitmo(sala);
    const repartidas = sala.jugadores.reduce((n, j) => n + j.num_cartas, 0);
    total.textContent = `${repartidas} cartas han sido repartidas.`;
  } else {
    if (document.body && document.body.classList) {
      document.body.classList.remove("en-partida");
    }
    if (bloqueCodigo) bloqueCodigo.hidden = false;
    if (bloqueOrden) bloqueOrden.hidden = false;
    total.hidden = false;
    if (resumenSala) resumenSala.hidden = true;
    partida.hidden = true;
    pintarRitmo(sala);
    btnComenzar.style.display = "";
    lobbyPersonajes.style.display = "";
    pintarPersonajes(sala);
    const sinPersonaje = sala.jugadores.filter((j) => !j.personaje_id).length;
    btnComenzar.disabled = !sala.es_anfitrion || sinPersonaje > 0;
    // Sin explicaciones permanentes: el botón deshabilitado ya comunica
    // el estado al anfitrión. Solo se informa a quien espera sin poder actuar.
    if (!sala.es_anfitrion) {
      estado.textContent = "Esperando a que el anfitrión comience…";
    } else {
      estado.textContent = "";
    }
  }
  if (
    window.PantallaCompleta &&
    typeof window.PantallaCompleta.actualizarFase === "function"
  ) {
    window.PantallaCompleta.actualizarFase(
      sala.estado === "esperando" ? "seleccion" : "tablero"
    );
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
  if (!modalUbicacion.hidden) cerrarCartaUbicacion();
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
  modalUbicacionCaja.classList.add("modo-ubicacion");
  modalUbicacionCaja.setAttribute("aria-label", `Información de ${nodo.nombre}`);
  const franja = document.createElement("div");
  franja.className = "presencias-contextuales";
  const zonaPersonajes = document.createElement("section");
  zonaPersonajes.className = "presencia-contextual";
  const grupoPersonajes = document.createElement("div");
  grupoPersonajes.className = "fichas-contextuales ocupantes";
  zonaPersonajes.appendChild(grupoPersonajes);
  franja.appendChild(zonaPersonajes);
  const ocupantes = ((ultimaSala || {}).jugadores || []).filter(
    (j) => j.posicion && j.posicion.id === nodo.id
  );
  if (ocupantes.length > 0) {
    ocupantes.forEach((j) => {
      grupoPersonajes.appendChild(crearFichaContextual({
        id: j.personaje_id,
        nombre: j.personaje || j.personaje_id,
      }, {
        alias: j.tipo === "humano" ? j.alias : "",
        alPulsar: () => verPersonaje(j.personaje_id),
      }));
    });
  }
  const zonaObjetos = document.createElement("section");
  zonaObjetos.className = "presencia-contextual";
  const grupoObjetos = document.createElement("div");
  grupoObjetos.className = "fichas-contextuales objetos-contextuales";
  zonaObjetos.appendChild(grupoObjetos);
  franja.appendChild(zonaObjetos);
  const posicionesObjetos = (ultimaSala && ultimaSala.posiciones_objetos) || {};
  const objetosAqui = Object.entries(posicionesObjetos)
    .filter(([, ubicacionId]) => ubicacionId === nodo.id)
    .map(([objetoId]) =>
      ((ultimaSala && ultimaSala.investigacion) || []).find((carta) => carta.id === objetoId) ||
      { id: objetoId, nombre: objetoId }
    );
  if (objetosAqui.length > 0) {
    objetosAqui.forEach((objeto) => grupoObjetos.appendChild(crearFichaContextual(objeto)));
  }
  modalContextualDetalle.appendChild(franja);
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
  btnSospechaUbicacion.hidden = !puedeSospecharAqui;
  if (ultimaSala) pintarPanel(ultimaSala);
  modalUbicacion.hidden = false;
  if (btnCerrarUbicacion.focus) btnCerrarUbicacion.focus();
}

function abrirLlegadaContextual(movimiento) {
  if (!ultimaSala || !movimiento || movimiento.personaje_id !== ultimaSala.personaje_id ||
      !ultimaSala.posicion || ultimaSala.posicion.id !== movimiento.destino_id) return;
  const jugadorLocal = (ultimaSala.jugadores || []).find(
    (jugador) => jugador.personaje_id === ultimaSala.personaje_id
  );
  if (!jugadorLocal || jugadorLocal.tipo === "pnj") return;
  const destino = nodoUbicacion(movimiento.destino_id);
  if (destino) abrirCartaUbicacion(destino, null);
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
  modalUbicacionCaja.classList.remove("modo-ubicacion");
  imagenUbicacion.src = "";
  imagenUbicacion.alt = "";
  imagenUbicacion.hidden = false;
  ubicacionContextualId = null;
  destinoUbicacionModal = null;
  btnMoverUbicacionCanvas.hidden = true;
  btnSospechaUbicacion.hidden = true;
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
btnSospechaUbicacion.addEventListener("click", () => {
  if (ubicacionContextualId) verSospecha(ubicacionContextualId);
});
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

// Con carta seleccionada la acción es REFUTAR. Sin selección, CONTINUAR
// significa "no elijo yo": el servidor elige una coincidencia válida y
// completa la refutación (misma ruta interna que el timeout). Nunca se
// vuelve a pedir REFUTAR.
function actualizarAccionesRefutacion(totalOpciones) {
  const haySeleccion = Boolean(cartaRefutacionSeleccionadaId);
  btnConfirmarRefutacion.disabled = !haySeleccion;
  btnContinuarRefutacion.disabled = false;
  btnContinuarRefutacion.hidden = haySeleccion || totalOpciones === 0;
}

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
  pintarPresentacionSospecha(sala);

  const opciones = Array.isArray(jugada.opciones_refutacion)
    ? jugada.opciones_refutacion : [];
  const seleccionPreviaValida = opciones.some(
    (carta) => carta.id === cartaRefutacionSeleccionadaId
  );
  cartaRefutacionSeleccionadaId = opciones.length === 1
    ? opciones[0].id
    : seleccionPreviaValida ? cartaRefutacionSeleccionadaId : null;
  modalRefutacion.hidden = opciones.length === 0;
  opcionesRefutacion.innerHTML = "";
  opcionesRefutacion.dataset.total = String(opciones.length);
  refutacionTitulo.textContent = opciones.length === 1
    ? "PUEDES REFUTAR"
    : "ELIGE UNA CARTA PARA REFUTAR";
  opciones.forEach((carta) => {
    // Patrón IDÉNTICO al selector de FORMULAR SOSPECHA (el que funciona):
    // un listener por carta vía `alPulsar`, la pulsada se marca y las demás
    // se desmarcan. Sin delegación ni eventos especiales.
    const boton = crearCartaVisual(carta, {
      esPropia: true,
      mostrarNombre: false,
      seleccionada: carta.id === cartaRefutacionSeleccionadaId,
      alPulsar: () => {
        Array.from(opcionesRefutacion.children).forEach((opcion) => {
          opcion.classList.remove("seleccionada");
          opcion.setAttribute("aria-pressed", "false");
        });
        boton.classList.add("seleccionada");
        boton.setAttribute("aria-pressed", "true");
        cartaRefutacionSeleccionadaId = carta.id;
        actualizarAccionesRefutacion(opciones.length);
      },
    });
    // La categoría solo se marca AQUÍ, en las opciones de refutación, para que
    // el CSS pueda distinguir un objeto sin tocar `crearCartaVisual` (que es
    // compartido por el resto de modales). No cambia nada más.
    boton.dataset.categoria = carta.categoria;
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

// 8B.32 · Antibloqueo por inactividad. El plazo es canónico del servidor:
// aquí solo se le manda la decisión del anfitrión con el aviso que tiene
// delante. El popup se cierra al decidir: durante el nuevo minuto no
// reaparece y la redifusión no lo vuelve a abrir.
btnSeguirEsperando.addEventListener("click", () => {
  if (modalInactividad.hidden || inactividadAvisoVigente === null) return;
  const avisoId = inactividadAvisoVigente;
  cerrarInactividad();
  ws.send(JSON.stringify({ accion: "seguir_esperando", aviso_id: avisoId }));
});

// Microfase 2 · Los dos botones solo envían; el valor llega del servidor.
if (btnRitmoMas) {
  btnRitmoMas.addEventListener("click", () => moverRitmo("acelerar_acciones"));
}
if (btnRitmoMenos) {
  btnRitmoMenos.addEventListener("click", () => moverRitmo("ralentizar_acciones"));
}

btnPasarAPnj.addEventListener("click", () => {
  if (modalInactividad.hidden || inactividadAvisoVigente === null) return;
  const avisoId = inactividadAvisoVigente;
  cerrarInactividad();
  ws.send(JSON.stringify({ accion: "pasar_a_pnj", aviso_id: avisoId }));
});

btnConfirmarRefutacion.addEventListener("click", () => {
  if (!cartaRefutacionSeleccionadaId || btnConfirmarRefutacion.disabled) return;
  btnConfirmarRefutacion.disabled = true;
  ws.send(JSON.stringify({
    accion: "mostrar_carta",
    carta_id: cartaRefutacionSeleccionadaId,
  }));
  modalRefutacion.hidden = true;
  cartaRefutacionSeleccionadaId = null;
});

btnContinuarRefutacion.addEventListener("click", () => {
  if (btnContinuarRefutacion.hidden || cartaRefutacionSeleccionadaId) return;
  btnContinuarRefutacion.disabled = true;
  ws.send(JSON.stringify({ accion: "continuar_refutacion" }));
  modalRefutacion.hidden = true;
  cartaRefutacionSeleccionadaId = null;
});

// 8B.31D · Las tres cartas sospechadas y, bajo cada una, lo que ESTE
// cliente ya sabía de ella. Se deriva solo de `sala.investigacion` y
// `sala.mis_cartas` (TU CARTA / VISTA / DESCARTADA / ?). Sin deducciones
// automáticas y sin ninguna información nueva: la carta que mostró el
// refutador NO se enseña ni se insinúa.
function pintarResultadoConocimiento(sala, sospecha) {
  if (!presentacionResultadoCartas) return;
  presentacionResultadoCartas.innerHTML = "";
  const cartasPropias = new Set((sala.mis_cartas || []).map((carta) => carta.id));
  const investigacion = new Map(
    (sala.investigacion || []).map((entrada) => [entrada.id, entrada])
  );
  [
    { clave: "sospechoso_id", categoria: "sospechoso" },
    { clave: "lugar_id", categoria: "lugar" },
    { clave: "objeto_id", categoria: "objeto" },
  ].forEach(({ clave, categoria }) => {
    const carta = sospecha[clave];
    if (!carta || !carta.id) return;
    const entrada = investigacion.get(carta.id);
    const esPropia = cartasPropias.has(carta.id);
    const fueVista = Boolean(entrada && entrada.estado === "vista");
    const descartada = Boolean(entrada && entrada.estado === "descartada");
    const columna = document.createElement("div");
    columna.className = "presentacion-resultado-columna";
    // Informativas, no seleccionables: sin `alPulsar` (mismo criterio 8B.30).
    columna.appendChild(
      crearCartaVisual(
        { id: carta.id, nombre: carta.nombre, categoria },
        { esPropia, fueVista, descartada, compacta: true, mostrarNombre: false }
      )
    );
    const estado = document.createElement("p");
    estado.className =
      "presentacion-resultado-estado " +
      (esPropia ? "es-propia" : fueVista ? "es-vista" : descartada ? "es-descartada" : "es-desconocida");
    estado.textContent = esPropia
      ? "TU CARTA"
      : fueVista
        ? "VISTA"
        : descartada
          ? "DESCARTADA"
          : "?";
    columna.appendChild(estado);
    presentacionResultadoCartas.appendChild(columna);
  });
}

function pintarPresentacionSospecha(sala) {
  const jugada = (sala && sala.jugada) || {};
  const id = jugada.presentacion_id;
  if (!jugada.presentacion_pendiente || !id || id === presentacionSospechaDescartadaId) {
    modalPresentacionSospecha.hidden = true;
    presentacionSospechaVisibleId = null;
    if (jugada.estado !== "presentando_sospecha") {
      presentacionSospechaDescartadaId = null;
    }
    return;
  }
  const sospecha = jugada.sospecha || {};
  if (jugada.presentacion_tipo === "resultado") {
    // 8B.31C · Cierre PÚBLICO. No se enseña ninguna carta: solo quién
    // formuló, quién refutó y el resultado. La carta concreta sigue siendo
    // privada del investigador (modal-revelacion-refutacion).
    presentacionSospechaCartas.hidden = true;
    presentacionSospechaCartas.innerHTML = "";
    presentacionResultadoTexto.hidden = false;
    presentacionResultadoCartas.hidden = false;
    // El cierre público nunca es fase informativa de este tipo: aquí la
    // refutación ya está resuelta y este aviso no aplica.
    presentacionSospechaAviso.hidden = true;
    pintarResultadoConocimiento(sala, sospecha);
    const refutada = jugada.resultado === "refutada";
    presentacionSospechaTitulo.textContent = refutada
      ? "SOSPECHA REFUTADA"
      : "NADIE HA PODIDO REFUTAR LA SOSPECHA";
    presentacionResultadoTexto.textContent = refutada
      ? `${(jugada.refutador_alias || "ALGUIEN").toUpperCase()} HA REFUTADO ` +
        `LA SOSPECHA DE ${(jugada.investigador_alias || "INVESTIGADOR").toUpperCase()}.`
      : "Ningún jugador ha mostrado una carta.";
    presentacionSospechaVisibleId = id;
    btnContinuarPresentacionSospecha.disabled = false;
    modalPresentacionSospecha.hidden = false;
    if (btnContinuarPresentacionSospecha.focus) btnContinuarPresentacionSospecha.focus();
    return;
  }
  presentacionSospechaCartas.hidden = false;
  presentacionResultadoCartas.hidden = true;
  presentacionResultadoCartas.innerHTML = "";
  presentacionResultadoTexto.hidden = true;
  presentacionResultadoTexto.textContent = "";
  // Esta presentación es informativa para TODOS los participantes: la
  // elección de cartas para refutar llega después, en su propia ventana. Aquí
  // no hay nada que elegir, así que el aviso se muestra siempre.
  presentacionSospechaAviso.hidden = false;
  const cartas = [
    { ...sospecha.sospechoso_id, categoria: "sospechoso" },
    { ...sospecha.lugar_id, categoria: "lugar" },
    { ...sospecha.objeto_id, categoria: "objeto" },
  ];
  pintarCartasResolucion(presentacionSospechaCartas, cartas, {
    sospechoso: cartas[0].id,
    lugar: cartas[1].id,
    objeto: cartas[2].id,
  });
  presentacionSospechaTitulo.textContent =
    `SOSPECHA DE ${(jugada.investigador_alias || "INVESTIGADOR").toUpperCase()}`;
  presentacionSospechaVisibleId = id;
  btnContinuarPresentacionSospecha.disabled = false;
  modalPresentacionSospecha.hidden = false;
  if (btnContinuarPresentacionSospecha.focus) btnContinuarPresentacionSospecha.focus();
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
    boton.className = "medallon medallon-primario medallon-compacto";
    boton.textContent = destino.nombre;
    boton.addEventListener("click", () => enviarDestinoTablero(destino.id, boton));
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
  modalUbicacionCaja.classList.remove("modo-ubicacion");
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
    investigacion.className = "medallon medallon-secundario medallon-compacto";
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

function crearFichaContextual(carta, opciones = {}) {
  const interactiva = typeof opciones.alPulsar === "function";
  const ficha = document.createElement(interactiva ? "button" : "div");
  if (interactiva) ficha.type = "button";
  ficha.className = `ficha-contextual${interactiva ? " ficha-contextual-interactiva" : ""}`;
  ficha.setAttribute("aria-label", opciones.alias
    ? `${carta.nombre || carta.id}, ${opciones.alias}`
    : (carta.nombre || carta.id));
  const recurso = RECURSOS_VISUALES[carta.id] || {};
  const imagen = document.createElement("img");
  imagen.src = recurso.nombre || recurso.principal || "";
  imagen.alt = carta.nombre || carta.id;
  imagen.hidden = !imagen.src;
  ficha.appendChild(imagen);
  if (opciones.alias) {
    const alias = document.createElement("small");
    alias.className = "ficha-contextual-alias";
    alias.textContent = opciones.alias;
    ficha.appendChild(alias);
  }
  if (interactiva) ficha.addEventListener("click", opciones.alPulsar);
  return ficha;
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
      linea.textContent = "Has llegado.";
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
  modalUbicacionCaja.classList.remove("modo-ubicacion");
  imagenUbicacion.src = "";
  imagenUbicacion.alt = "";
  imagenUbicacion.hidden = true;
  btnMoverUbicacionCanvas.hidden = true;
  btnSospechaUbicacion.hidden = true;
  btnCerrarUbicacion.hidden = true;
  modalUbicacionCaja.setAttribute("aria-label", modalContextualTitulo.textContent);
  // La ubicación la fija el servidor (lugar de entrada): solo se piden
  // sospechoso y objeto, con datos canónicos de la propia hoja privada.
  const cartas = sala.investigacion || [];
  const cartasPropias = new Set((sala.mis_cartas || []).map((carta) => carta.id));
  let sospechosoSeleccionado = "";
  let objetoSeleccionado = "";
  // Aviso DENTRO del selector: `#error` vive en el lobby (oculto mientras se
  // juega), así que un fallo de validación no le llegaba a ver a nadie y el
  // botón quedaba muerto. Reutiliza la clase .error ya existente.
  const aviso = document.createElement("p");
  aviso.className = "error";
  aviso.setAttribute("role", "alert");

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
        aviso.textContent = "";
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
  modalContextualDetalle.appendChild(aviso);
  const confirmar = document.createElement("button");
  confirmar.type = "button";
  confirmar.className = "medallon medallon-primario medallon-compacto";
  confirmar.textContent = "CONFIRMAR SOSPECHA";
  // El botón no nace `disabled`: un control deshabilitado se traga el toque
  // sin hacer nada. Valida al pulsar y explica qué falta, aquí mismo.
  confirmar.disabled = false;
  confirmar.addEventListener("click", () => {
    const falta = [];
    if (!sospechosoSeleccionado) falta.push("un sospechoso");
    if (!objetoSeleccionado) falta.push("dónde lo escondió");
    if (!sala.posicion) falta.push("estar en una ubicación");
    if (falta.length) {
      aviso.textContent = `Para confirmar elige ${falta.join(" y ")}.`;
      return;
    }
    aviso.textContent = "";
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
  volver.className = "medallon medallon-fantasma medallon-compacto";
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
  // 8B.33/8B.33B/8B.33C · La musica ambiental acompaña portada, lobby y
  // partida desde el propio modulo de audio; aqui solo se le avisa del
  // cambio de FASE (nivel de partida al empezar) y del FINAL, que la detiene
  // y dispara su efecto UNA sola vez. Un repintado, un WebSocket repetido o
  // una recarga con la pantalla final ya visible no vuelven a dispararlo:
  // representa el momento del final, no estar mirandolo. Nada de esto toca
  // Sala: es estado local.
  const anterior = estadoPartidaVisto;
  estadoPartidaVisto = sala.estado;
  if (window.AudioFondo) {
    if (sala.estado === "terminada") {
      window.AudioFondo.detener();
      if (anterior && anterior !== "terminada") {
        window.AudioFondo.reproducirEfecto("final");
      }
    } else if (sala.estado === "iniciada") {
      window.AudioFondo.iniciar();
    } else if (sala.estado === "esperando" && anterior === "terminada"
      && typeof window.AudioFondo.reanudarAmbiental === "function") {
      // 8B.35: la revancha devuelve la sala al lobby y la musica ambiental
      // vuelve a acompanar, sin reiniciar su propia arquitectura.
      window.AudioFondo.reanudarAmbiental();
    }
  }
  finalPartida.hidden = sala.estado !== "terminada" || hayFinalDeVictoria(sala);
  finalPartida.innerHTML = "";
  // El popup final es la presentacion protagonista: mientras esta abierto, el
  // panel derecho NO duplica la misma informacion. Este bloque sigue siendo el
  // resumen que queda cuando el jugador cierra el popup.
  if (sala.estado !== "terminada" || !sala.solucion || hayFinalDeVictoria(sala)) return;
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

function hayFinalDeVictoria(sala) {
  // Unica fuente de verdad de "el popup del final debe verse ahora". La
  // comparten el popup y el bloque resumen del panel, para que nunca se
  // muestren los dos a la vez.
  return Boolean(
    sala && sala.estado === "terminada" && sala.solucion && !victoriaDescartada
  );
}

function cerrarVictoria() {
  if (modalVictoria) modalVictoria.hidden = true;
}

// 8B.35 · FINAL DE VICTORIA. Protagonista de la partida terminada y visible
// para TODOS los humanos conectados: la solucion ya es publica y cada
// cliente la recibe en su propio estado privado. Reutiliza el render de tres
// cartas y el aspecto del popup de 8B.34; la revancha es canonica del
// servidor, aqui solo se pide.
function presentarVictoria(sala) {
  if (!sala || sala.estado !== "terminada") {
    // Revancha o salida del final: el popup se cierra y vuelve a estar
    // disponible para el siguiente final de esta misma sala.
    victoriaDescartada = false;
    cerrarVictoria();
    return;
  }
  if (victoriaDescartada || !sala.solucion) {
    cerrarVictoria();
    return;
  }
  // Las tres cartas reales de la solucion, con su recurso canonico. La
  // solucion publica trae id y nombre; la categoria la fija la propia funcion.
  const cartas = [
    Object.assign({ categoria: "sospechoso" }, sala.solucion.sospechoso),
    Object.assign({ categoria: "lugar" }, sala.solucion.lugar),
    Object.assign({ categoria: "objeto" }, sala.solucion.objeto),
  ];
  pintarCartasResolucion(victoriaCartas, cartas, {
    sospechoso: sala.solucion.sospechoso.id,
    lugar: sala.solucion.lugar.id,
    objeto: sala.solucion.objeto.id,
  });
  victoriaTitulo.textContent = sala.resultado_final === "resuelto"
    ? "MISTERIO RESUELTO" : "EL MISTERIO QUEDA SIN RESOLVER";
  victoriaSubtitulo.textContent = sala.ganador_alias
    ? `${sala.ganador_alias} HA RESUELTO EL MISTERIO`
    : "NINGÚN INVESTIGADOR RESOLVIÓ EL MISTERIO";
  victoriaNota.textContent = "Tu investigación y tus cartas siguen disponibles "
    + "hasta que empiece la siguiente partida.";
  // Misma autoridad que COMENZAR PARTIDA: el botón se ve para todos, pero solo
  // el anfitrión puede pedir la revancha (el servidor lo exige igual).
  if (btnJugarDeNuevo) {
    btnJugarDeNuevo.disabled = !sala.es_anfitrion;
    btnJugarDeNuevo.title = sala.es_anfitrion
      ? "Volver al lobby de esta sala para una revancha"
      : "Solo el anfitrión puede empezar una revancha";
  }
  modalVictoria.hidden = false;
  if (btnJugarDeNuevo.focus) btnJugarDeNuevo.focus();
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

function pintarHistorial(historial) {
  historialLista.innerHTML = "";
  if (!Array.isArray(historial) || historial.length === 0) {
    const vacio = document.createElement("p");
    vacio.className = "historial-vacio";
    vacio.textContent = "Todavía no hay movimientos registrados en la investigación";
    historialLista.appendChild(vacio);
    return;
  }
  historial.forEach((entrada) => {
    const investigador = entrada.investigador || {};
    const sospecha = entrada.sospecha || {};
    const articulo = document.createElement("article");
    articulo.className = "historial-entrada";

    const titulo = document.createElement("h3");
    const marcaPnj = investigador.tipo === "pnj" ? " (PNJ)" : "";
    titulo.textContent = `Turno ${entrada.turno} — ${investigador.nombre || "Investigador"}${marcaPnj}`;
    articulo.appendChild(titulo);

    const detalle = document.createElement("p");
    const sospechoso = sospecha.sospechoso_id && sospecha.sospechoso_id.nombre;
    const lugar = sospecha.lugar_id && sospecha.lugar_id.nombre;
    const objeto = sospecha.objeto_id && sospecha.objeto_id.nombre;
    detalle.textContent = `Sospecha: ${sospechoso} escondió el medallón en ${lugar}, dentro de ${objeto}.`;
    articulo.appendChild(detalle);

    const resultado = document.createElement("p");
    resultado.className = "historial-resultado";
    resultado.textContent = entrada.resultado === "refutada" && entrada.refutador
      ? `Resultado: ${entrada.refutador.nombre} pudo refutar la sospecha.`
      : "Resultado: Nadie pudo refutar la sospecha.";
    articulo.appendChild(resultado);
    historialLista.appendChild(articulo);
  });
}

function abrirHistorial(evento) {
  focoAntesDeHistorial = evento && evento.currentTarget
    ? evento.currentTarget : document.activeElement;
  pintarHistorial((ultimaSala && ultimaSala.historial) || []);
  modalHistorial.hidden = false;
  if (btnCerrarHistorial.focus) btnCerrarHistorial.focus();
}

function cerrarHistorial() {
  modalHistorial.hidden = true;
  // El estado recibido mientras esta capa estaba abierta ya se ha pintado
  // detrás de ella. No se confirma ni se reabre ninguna ventana de juego.
  if (focoAntesDeHistorial && focoAntesDeHistorial.focus) {
    focoAntesDeHistorial.focus();
  }
  focoAntesDeHistorial = null;
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
[
  btnHistorial,
  btnHistorialPresentacion,
  btnHistorialRefutacion,
  btnHistorialRevelacion,
].forEach((boton) => {
  if (boton) boton.addEventListener("click", abrirHistorial);
});
if (btnCerrarHistorial) {
  btnCerrarHistorial.addEventListener("click", cerrarHistorial);
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

function pintarCartasResolucion(contenedor, cartas, seleccion) {
  contenedor.innerHTML = "";
  // Solo lectura: las figuras son <div> sin oyentes; para cambiar la
  // acusación hay que CANCELAR y volver al selector.
  [
    { categoria: "sospechoso", id: seleccion.sospechoso },
    { categoria: "lugar", id: seleccion.lugar },
    { categoria: "objeto", id: seleccion.objeto },
  ].forEach(({ categoria, id }) => {
    const carta = (cartas || []).find(
      (entrada) => entrada.id === id && entrada.categoria === categoria
    );
    if (!carta) return;
    const boton = crearCartaVisual(carta, { mostrarNombre: false });
    const figura = document.createElement("div");
    figura.className = `${boton.className} carta-confirmacion-resolver carta-confirmacion-${categoria}`;
    figura.setAttribute("aria-label", carta.nombre);
    figura.title = carta.nombre;
    while (boton.firstChild) figura.appendChild(boton.firstChild);
    contenedor.appendChild(figura);
  });
}

function pintarConfirmacionResolver(cartas) {
  pintarCartasResolucion(confResolverCartas, cartas, resolverSeleccion);
}

function presentarResolucionFallida(sala) {
  const jugada = (sala && sala.jugada) || {};
  const cartas = Array.isArray(jugada.resolucion_fallida)
    ? jugada.resolucion_fallida : [];
  if (cartas.length !== 3 || sala.activo_investigacion !== false) {
    return;
  }
  const seleccion = Object.fromEntries(cartas.map((carta) => [carta.categoria, carta.id]));
  pintarCartasResolucion(
    resolucionFallidaCartas,
    cartas,
    seleccion
  );
  resolucionPendienteLocal = null;
  modalResolucionFallida.hidden = false;
  if (btnSeguirRefutando.focus) btnSeguirRefutando.focus();
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
  pintarConfirmacionResolver(cartas);
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
  resolucionPendienteLocal = {
    seleccion: { ...resolverSeleccion },
    cartas: ((ultimaSala && ultimaSala.investigacion) || []).map((carta) => ({ ...carta })),
  };
  ws.send(JSON.stringify({
    accion: "resolver_misterio",
    sospechoso_id: resolverSeleccion.sospechoso,
    lugar_id: resolverSeleccion.lugar,
    objeto_id: resolverSeleccion.objeto,
  }));
  modalConfirmarResolver.hidden = true;
});

function elegirModoRefutacion(automatica) {
  ws.send(JSON.stringify({ accion: "elegir_modo_refutacion", automatica }));
  modalResolucionFallida.hidden = true;
}

// 8B.35 · Las dos acciones del final. JUGAR DE NUEVO pide la revancha al
// servidor, que es quien decide; INVESTIGACION deja el popup y abre la hoja,
// y el resumen del final sigue disponible en el panel derecho.
if (btnJugarDeNuevo) {
  btnJugarDeNuevo.addEventListener("click", () => {
    if (modalVictoria.hidden) return;
    ws.send(JSON.stringify({ accion: "volver_al_lobby" }));
  });
}
if (btnVictoriaInvestigacion) {
  btnVictoriaInvestigacion.addEventListener("click", () => {
    victoriaDescartada = true;
    cerrarVictoria();
    abrirHoja();
  });
}

btnSeguirRefutando.addEventListener("click", () => elegirModoRefutacion(false));
btnRefutarAutomatico.addEventListener("click", () => elegirModoRefutacion(true));

btnContinuarPresentacionSospecha.addEventListener("click", () => {
  if (!presentacionSospechaVisibleId || btnContinuarPresentacionSospecha.disabled) return;
  btnContinuarPresentacionSospecha.disabled = true;
  presentacionSospechaDescartadaId = presentacionSospechaVisibleId;
  ws.send(JSON.stringify({
    accion: "confirmar_presentacion_sospecha",
    presentacion_id: presentacionSospechaVisibleId,
  }));
  modalPresentacionSospecha.hidden = true;
  presentacionSospechaVisibleId = null;
});
