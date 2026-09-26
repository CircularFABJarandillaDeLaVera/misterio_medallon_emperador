/* Control global de pantalla completa (Fase 8B.19).
   Un solo módulo para portada, lobby y partida: se inyecta en el
   documento y usa la Fullscreen API estándar. Si el navegador no la
   soporta, el control no se muestra y la aplicación sigue igual.
   Escape lo resuelve el navegador: el evento fullscreenchange
   resincroniza siempre el estado visual. */
(function () {
  "use strict";

  const doc = document;
  const raiz = doc.documentElement;
  const pedir = raiz.requestFullscreen || raiz.webkitRequestFullscreen;
  const salir = doc.exitFullscreen || doc.webkitExitFullscreen;
  if (typeof pedir !== "function" || typeof salir !== "function") return;

  const enPantallaCompleta = () =>
    Boolean(doc.fullscreenElement || doc.webkitFullscreenElement);

  const SVG_ENTRAR =
    '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
    '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" fill="none" ' +
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
    'stroke-linejoin="round"/></svg>';
  const SVG_SALIR =
    '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
    '<path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" fill="none" ' +
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
    'stroke-linejoin="round"/></svg>';

  const boton = doc.createElement("button");
  boton.type = "button";
  // Familia medallón reutilizada: mismo chaflán y filete, formato cuadrado.
  boton.className = "medallon medallon-fantasma control-pantalla-completa";
  const iconoEntrar = doc.createElement("span");
  iconoEntrar.className = "control-pantalla-icono";
  iconoEntrar.innerHTML = SVG_ENTRAR;
  const iconoSalir = doc.createElement("span");
  iconoSalir.className = "control-pantalla-icono";
  iconoSalir.innerHTML = SVG_SALIR;
  iconoSalir.hidden = true;
  boton.appendChild(iconoEntrar);
  boton.appendChild(iconoSalir);

  function sincronizar() {
    const activo = enPantallaCompleta();
    iconoEntrar.hidden = activo;
    iconoSalir.hidden = !activo;
    const texto = activo ? "Salir de pantalla completa" : "Pantalla completa";
    boton.setAttribute("aria-label", texto);
    boton.setAttribute("title", texto);
    boton.setAttribute("aria-pressed", activo ? "true" : "false");
  }

  boton.addEventListener("click", () => {
    if (enPantallaCompleta()) {
      const salida = salir.call(doc);
      if (salida && typeof salida.catch === "function") {
        salida.catch(() => sincronizar());
      }
      return;
    }
    const entrada = pedir.call(raiz);
    if (entrada && typeof entrada.catch === "function") {
      // Navegador sin permiso o política de gestos: sin aviso técnico.
      entrada.catch(() => sincronizar());
    }
  });

  doc.addEventListener("fullscreenchange", sincronizar);
  doc.addEventListener("webkitfullscreenchange", sincronizar);
  doc.addEventListener("fullscreenerror", sincronizar);

  // El control pertenece al marco canónico de la vista (portada o sala),
  // nunca al flujo del documento: así no reserva altura ni genera scroll.
  const anfitrion =
    doc.querySelector(".portada-escena") ||
    doc.querySelector(".tarjeta") ||
    doc.body;
  anfitrion.appendChild(boton);
  sincronizar();
})();
