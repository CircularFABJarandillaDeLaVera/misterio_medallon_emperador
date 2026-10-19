/* Portada videojuego (8B.15): crear/unirse/cargar + sus popups. */
"use strict";

const $ = (id) => document.getElementById(id);
const modalPreparacionMovil = $("modal-preparacion-movil");
const btnEntrarPantallaCompleta = $("btn-entrar-pantalla-completa");
const escenaPortada = document.querySelector(".portada-escena");

// Microfase 6 · Los tres popups de la portada. La lista es la ÚNICA fuente:
// abrir, cerrar con Escape, cerrar con el velo y devolver el foco salen de
// aquí, así que una ventana nueva queda registrada por las cuatro vías.
const MODALES_PORTADA = ["modal-nueva", "modal-unirse", "modal-cargar"];
const BOTON_QUE_ABRE = {
  "modal-nueva": "btn-nueva",
  "modal-unirse": "btn-unirse",
  "modal-cargar": "btn-cargar",
};
const ERROR_DE_MODAL = {
  "modal-nueva": "error-nueva",
  "modal-unirse": "error",
  "modal-cargar": "error-cargar",
};

let modoDesbloqueado = false;
let ultimoFoco = null;
let cargandoPartida = false;
let preparacionPortadaCompletada = false;
let preparacionPortadaActiva = false;

function modalAbierto() {
  for (const id of MODALES_PORTADA) {
    const modal = $(id);
    if (modal && !modal.hidden) return modal;
  }
  return null;
}

function abrirModal(idModal, idFoco) {
  const modal = $(idModal);
  if (!modal) return;
  const otro = modalAbierto();
  if (otro && otro !== modal) otro.hidden = true;
  ultimoFoco = document.activeElement || null;
  modal.hidden = false;
  const foco = $(idFoco);
  if (foco && foco.focus) foco.focus();
}

function cerrarModal(idModal) {
  const modal = $(idModal);
  if (!modal) return;
  modal.hidden = true;
  const error = $(ERROR_DE_MODAL[idModal]);
  if (error) error.textContent = "";
  // La selección de archivo no sobrevive a cancelar: se empieza de cero.
  if (idModal === "modal-cargar") limpiarArchivoElegido();
  const opener = $(BOTON_QUE_ABRE[idModal]);
  if (!modalAbierto() && opener && opener.focus) opener.focus();
}

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

function iniciarPreparacionPortadaMovil() {
  if (!esTelefonoMovil()) {
    document.documentElement.classList.remove("preparacion-movil-inicial");
    return;
  }
  if (!modalPreparacionMovil || !btnEntrarPantallaCompleta) {
    document.documentElement.classList.remove("preparacion-movil-inicial");
    return;
  }
  ajustarSuperficiePreparacionMovil();
  modalPreparacionMovil.hidden = false;
  document.documentElement.classList.add("preparacion-movil-activa");
  if (escenaPortada) escenaPortada.inert = true;
  document.documentElement.classList.remove("preparacion-movil-inicial");
  if (
    window.PreparacionPortadaInicial &&
    typeof window.PreparacionPortadaInicial.tomarControl === "function"
  ) {
    window.PreparacionPortadaInicial.tomarControl();
  }
  preparacionPortadaActiva = true;
  btnEntrarPantallaCompleta.focus();
}

function completarPreparacionPortada() {
  if (!preparacionPortadaActiva) return;
  preparacionPortadaActiva = false;
  preparacionPortadaCompletada = true;
  if (
    window.PantallaCompleta &&
    typeof window.PantallaCompleta.solicitarInmersionHorizontal === "function"
  ) {
    window.PantallaCompleta.solicitarInmersionHorizontal();
  }
  modalPreparacionMovil.hidden = true;
  document.documentElement.classList.remove("preparacion-movil-activa");
  if (escenaPortada) escenaPortada.inert = false;
  if (window.PreparacionPortadaInicial) {
    window.PreparacionPortadaInicial.activa = false;
  }
  const focoPortada = $("btn-nueva");
  if (focoPortada && focoPortada.focus) focoPortada.focus();
}

if (btnEntrarPantallaCompleta) {
  btnEntrarPantallaCompleta.addEventListener("click", completarPreparacionPortada);
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

iniciarPreparacionPortadaMovil();

// Herramienta temporal de desarrollo: Ctrl+Alt+D muestra el selector
// de modo DENTRO del popup NUEVA PARTIDA (oculto por defecto).
// Solo memoria de la página: al recargar vuelve a estar oculto.
if (document.addEventListener) {
  document.addEventListener("keydown", (evento) => {
    if (evento.key === "Escape") {
      const abierto = modalAbierto();
      if (abierto) {
        if (evento.preventDefault) evento.preventDefault();
        cerrarModal(abierto.id);
      }
      return;
    }
    if (evento.key === "Enter" && modalAbierto()) return; // lo gestiona cada input
    if (!evento.ctrlKey || !evento.altKey) return;
    if (evento.key !== "d" && evento.key !== "D") return;
    if (evento.preventDefault) evento.preventDefault();
    modoDesbloqueado = !modoDesbloqueado;
    const envoltorio = $("envoltorio-modo");
    if (envoltorio) envoltorio.hidden = !modoDesbloqueado;
  });
}

async function leerError(respuesta) {
  try {
    const datos = await respuesta.json();
    return datos.detalle || "Ha ocurrido un error.";
  } catch {
    return "Ha ocurrido un error.";
  }
}

function modoActual() {
  const selector = $("modo");
  return selector && selector.value ? selector.value : "tablero";
}

const CLAVE_ENTRADA_PREPARACION_MOVIL = "preparacion_movil_pendiente";

function prepararEntradaMovil(datos, origen) {
  try {
    sessionStorage.setItem(CLAVE_ENTRADA_PREPARACION_MOVIL, JSON.stringify({
      codigo: datos.codigo,
      jugador_id: datos.jugador_id,
      origen,
      preparacion_completada: preparacionPortadaCompletada,
    }));
  } catch (errorAlGuardarEntrada) {
    // La sala conserva una deteccion de respaldo al recibir su primer estado.
  }
}

async function crearPartida() {
  const alias = $("alias").value.trim();
  $("error-nueva").textContent = "";
  if (!alias) {
    $("error-nueva").textContent = "Escribe tu alias para crear la partida.";
    return;
  }
  const boton = $("btn-crear");
  if (boton) boton.disabled = true;
  try {
    const respuesta = await fetch("/api/partidas", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ alias, modo: modoActual() }),
    });
    if (!respuesta.ok) {
      $("error-nueva").textContent = await leerError(respuesta);
      return;
    }
    const datos = await respuesta.json();
    sessionStorage.setItem("jugador_id", datos.jugador_id);
    sessionStorage.setItem("alias", datos.alias);
    // Solo quien crea la partida es anfitrión y recibe el secreto
    // administrativo. Se guarda para las futuras acciones de administración.
    if (datos.credencial_admin) {
      sessionStorage.setItem("credencial_admin", datos.credencial_admin);
    }
    prepararEntradaMovil(datos, "crear");
    window.location.href = `/sala/${datos.codigo}`;
  } finally {
    if (boton) boton.disabled = false;
  }
}

async function unirsePartida() {
  const alias = $("alias-unirse").value.trim();
  const codigo = $("codigo").value.trim().toUpperCase();
  $("error").textContent = "";
  if (!alias) {
    $("error").textContent = "Escribe tu alias para unirte.";
    return;
  }
  if (!codigo) {
    $("error").textContent = "INTRODUCE UN CÓDIGO DE SALA.";
    return;
  }
  const boton = $("btn-confirmar-unirse");
  if (boton) boton.disabled = true;
  try {
    const respuesta = await fetch(`/api/partidas/${encodeURIComponent(codigo)}/unirse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ alias }),
    });
    if (!respuesta.ok) {
      $("error").textContent = respuesta.status === 404
        ? "LA SALA NO EXISTE. REVISA EL CÓDIGO."
        : await leerError(respuesta);
      return;
    }
    const datos = await respuesta.json();
    sessionStorage.setItem("jugador_id", datos.jugador_id);
    sessionStorage.setItem("alias", datos.alias);
    prepararEntradaMovil(datos, "unirse");
    window.location.href = `/sala/${datos.codigo}`;
  } finally {
    if (boton) boton.disabled = false;
  }
}

// --- Microfase 6 · CARGAR PARTIDA -----------------------------------------
// Se elige un archivo local y se manda TAL CUAL al servidor, que es quien
// lo valida entero. Aquí no se interpreta nada del contenido.

function archivoElegido() {
  const campo = $("archivo-partida");
  return campo && campo.files && campo.files.length ? campo.files[0] : null;
}

function limpiarArchivoElegido() {
  const campo = $("archivo-partida");
  if (campo) campo.value = "";
  const elegido = $("archivo-elegido");
  if (elegido) {
    elegido.hidden = true;
    elegido.textContent = "";
  }
}

function marcarArchivoElegido() {
  const archivo = archivoElegido();
  const elegido = $("archivo-elegido");
  if (!elegido) return;
  if (!archivo) {
    elegido.hidden = true;
    elegido.textContent = "";
    return;
  }
  elegido.textContent = `ARCHIVO ELEGIDO: ${archivo.name}`;
  elegido.hidden = false;
}

async function cargarPartida() {
  if (cargandoPartida) return; // sin envíos duplicados mientras se procesa
  const error = $("error-cargar");
  if (error) error.textContent = "";
  const archivo = archivoElegido();
  if (!archivo) {
    if (error) error.textContent = "ELIGE EL ARCHIVO DE LA PARTIDA GUARDADA.";
    return;
  }
  const boton = $("btn-confirmar-cargar");
  cargandoPartida = true;
  if (boton) boton.disabled = true;
  try {
    const texto = await archivo.text();
    const respuesta = await fetch("/api/cargar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: texto,
    });
    if (!respuesta.ok) {
      if (error) error.textContent = await leerError(respuesta);
      return;
    }
    const datos = await respuesta.json();
    // Recupera su identidad original: no es un jugador nuevo y no se
    // reparten cartas. Solo vuelve a su propio asiento.
    sessionStorage.setItem("jugador_id", datos.jugador_id);
    sessionStorage.setItem("alias", datos.alias);
    if (datos.credencial_admin) {
      sessionStorage.setItem("credencial_admin", datos.credencial_admin);
    }
    prepararEntradaMovil(datos, "cargar");
    window.location.href = `/sala/${datos.codigo}`;
  } catch (e) {
    if (error) error.textContent = "NO SE PUDO LEER EL ARCHIVO.";
  } finally {
    cargandoPartida = false;
    if (boton) boton.disabled = false;
  }
}

$("btn-cargar").addEventListener("click", () => {
  if ($("error-cargar")) $("error-cargar").textContent = "";
  limpiarArchivoElegido();
  abrirModal("modal-cargar", "archivo-partida");
});

$("btn-cancelar-cargar").addEventListener("click", () => cerrarModal("modal-cargar"));

$("btn-confirmar-cargar").addEventListener("click", cargarPartida);

if ($("archivo-partida") && $("archivo-partida").addEventListener) {
  $("archivo-partida").addEventListener("change", marcarArchivoElegido);
}

$("btn-nueva").addEventListener("click", () => {
  if ($("error-nueva")) $("error-nueva").textContent = "";
  abrirModal("modal-nueva", "alias");
});

$("btn-unirse").addEventListener("click", () => {
  if ($("error")) $("error").textContent = "";
  abrirModal("modal-unirse", "codigo");
});

$("btn-cancelar-nueva").addEventListener("click", () => cerrarModal("modal-nueva"));
$("btn-cancelar-unirse").addEventListener("click", () => cerrarModal("modal-unirse"));

$("btn-crear").addEventListener("click", crearPartida);
$("btn-confirmar-unirse").addEventListener("click", unirsePartida);

// Clic en el velo (fuera de la caja) equivale a CANCELAR: sin fetch.
for (const idModal of MODALES_PORTADA) {
  const modal = $(idModal);
  if (modal && modal.addEventListener) {
    modal.addEventListener("click", (evento) => {
      if (evento.target === modal) cerrarModal(idModal);
    });
  }
}

// Enter dentro de cada popup confirma sin recargar.
if ($("alias") && $("alias").addEventListener) {
  $("alias").addEventListener("keydown", (evento) => {
    if (evento.key === "Enter") {
      if (evento.preventDefault) evento.preventDefault();
      crearPartida();
    }
  });
}
for (const idCampo of ["codigo", "alias-unirse"]) {
  const campo = $(idCampo);
  if (campo && campo.addEventListener) {
    campo.addEventListener("keydown", (evento) => {
      if (evento.key === "Enter") {
        if (evento.preventDefault) evento.preventDefault();
        unirsePartida();
      }
    });
  }
}
