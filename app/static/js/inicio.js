/* Pantalla inicial: crear partida o unirse a una sala. */
"use strict";

const $ = (id) => document.getElementById(id);

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
