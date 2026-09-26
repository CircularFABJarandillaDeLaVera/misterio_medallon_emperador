/* Pantalla inicial: crear partida o unirse a una sala. */
"use strict";

const $ = (id) => document.getElementById(id);

// Herramienta temporal de desarrollo: Ctrl+Alt+D muestra el selector
// de modo de partida (oculto por defecto). Solo memoria de la página:
// al recargar vuelve a estar oculto. No intercepta ninguna otra tecla.
let modoDesbloqueado = false;
if (document.addEventListener) {
  document.addEventListener("keydown", (evento) => {
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

$("btn-nueva").addEventListener("click", async () => {
  const alias = $("alias").value.trim();
  $("error").textContent = "";
  if (!alias) {
    $("error").textContent = "Escribe tu alias para crear la partida.";
    return;
  }
  const respuesta = await fetch("/api/partidas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ alias, modo: $("modo").value }),
  });
  if (!respuesta.ok) {
    $("error").textContent = await leerError(respuesta);
    return;
  }
  const datos = await respuesta.json();
  sessionStorage.setItem("jugador_id", datos.jugador_id);
  sessionStorage.setItem("alias", datos.alias);
  window.location.href = `/sala/${datos.codigo}`;
});

$("btn-unirse").addEventListener("click", async () => {
  const alias = $("alias").value.trim();
  const codigo = $("codigo").value.trim().toUpperCase();
  $("error").textContent = "";
  if (!alias) {
    $("error").textContent = "Escribe tu alias para unirte.";
    return;
  }
  if (!codigo) {
    $("error").textContent = "Escribe el código de la sala.";
    return;
  }
  const respuesta = await fetch(`/api/partidas/${encodeURIComponent(codigo)}/unirse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ alias }),
  });
  if (!respuesta.ok) {
    $("error").textContent = await leerError(respuesta);
    return;
  }
  const datos = await respuesta.json();
  sessionStorage.setItem("jugador_id", datos.jugador_id);
  sessionStorage.setItem("alias", datos.alias);
  window.location.href = `/sala/${datos.codigo}`;
});
