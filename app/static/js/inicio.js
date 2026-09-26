/* Portada videojuego (8B.15): dos acciones + popups de crear/unirse. */
"use strict";

const $ = (id) => document.getElementById(id);

let modoDesbloqueado = false;
let ultimoFoco = null;

function modalAbierto() {
  for (const id of ["modal-nueva", "modal-unirse"]) {
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
  if (idModal === "modal-nueva" && $("error-nueva")) $("error-nueva").textContent = "";
  if (idModal === "modal-unirse" && $("error")) $("error").textContent = "";
  const opener = idModal === "modal-nueva" ? $("btn-nueva") : $("btn-unirse");
  if (!modalAbierto() && opener && opener.focus) opener.focus();
}

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
    window.location.href = `/sala/${datos.codigo}`;
  } finally {
    if (boton) boton.disabled = false;
  }
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
for (const idModal of ["modal-nueva", "modal-unirse"]) {
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
