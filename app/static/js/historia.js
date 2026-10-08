/* Fase 3B · Introducción narrativa local de la portada.
   No conoce el juego, no realiza peticiones y no toca los formularios. */
"use strict";

(() => {
  const historia = document.getElementById("historia-intro");
  const btnVer = document.getElementById("btn-ver-historia");
  const btnSaltar = document.getElementById("btn-saltar-historia");
  const btnPausar = document.getElementById("btn-pausar-historia");
  const btnAvanzar = document.getElementById("btn-avanzar-historia");
  const contador = document.getElementById("historia-contador");
  const barra = document.getElementById("historia-barra");
  if (!historia || !btnVer || !btnSaltar || !btnPausar || !btnAvanzar) return;

  const escenas = Array.from(historia.querySelectorAll("[data-historia-escena]"));
  const progreso = historia.querySelector("[role='progressbar']");
  const CLAVE_VISTA = "historia_intro_vista";
  const DURACION_ESCENA_MS = 6500;
  let escenaActual = 0;
  let temporizador = null;
  let focoAnterior = null;
  let pausada = false;

  function prefiereMovimientoReducido() {
    return typeof window !== "undefined" && window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function elementosEnfocables() {
    return [btnSaltar, btnPausar, btnAvanzar].filter((elemento) => !elemento.hidden);
  }

  function guardarVista() {
    try { sessionStorage.setItem(CLAVE_VISTA, "1"); }
    catch (error) { /* Sesión sin almacenamiento: la portada sigue funcionando. */ }
  }

  function yaVista() {
    try { return sessionStorage.getItem(CLAVE_VISTA) === "1"; }
    catch (error) { return false; }
  }

  function cancelarAutomatico() {
    if (temporizador !== null) clearTimeout(temporizador);
    temporizador = null;
  }

  function programarAutomatico() {
    cancelarAutomatico();
    if (pausada) return;
    temporizador = setTimeout(() => {
      if (escenaActual < escenas.length - 1) mostrarEscena(escenaActual + 1);
      else cerrarHistoria();
    }, DURACION_ESCENA_MS);
  }

  function mostrarEscena(indice) {
    escenaActual = Math.max(0, Math.min(escenas.length - 1, indice));
    escenas.forEach((escena, posicion) => {
      const activa = posicion === escenaActual;
      escena.hidden = !activa;
      escena.classList.toggle("historia-escena-activa", activa);
    });
    const numero = escenaActual + 1;
    contador.textContent = `${numero} DE ${escenas.length}`;
    progreso.setAttribute("aria-valuenow", String(numero));
    barra.style.width = `${(numero / escenas.length) * 100}%`;
    btnAvanzar.textContent = escenaActual === escenas.length - 1
      ? "ENTRAR AL MISTERIO" : "AVANZAR";
    programarAutomatico();
  }

  function abrirHistoria(evento) {
    focoAnterior = evento && evento.currentTarget ? evento.currentTarget : document.activeElement;
    historia.hidden = false;
    document.body.classList.add("historia-abierta");
    pausada = prefiereMovimientoReducido();
    btnPausar.textContent = pausada ? "REPRODUCIR" : "PAUSAR";
    btnPausar.setAttribute("aria-pressed", pausada ? "true" : "false");
    mostrarEscena(0);
    if (btnSaltar.focus) btnSaltar.focus();
  }

  function cerrarHistoria() {
    cancelarAutomatico();
    historia.hidden = true;
    document.body.classList.remove("historia-abierta");
    guardarVista();
    if (focoAnterior && focoAnterior.focus) focoAnterior.focus();
    focoAnterior = null;
  }

  btnVer.addEventListener("click", abrirHistoria);
  btnSaltar.addEventListener("click", cerrarHistoria);
  btnPausar.addEventListener("click", () => {
    pausada = !pausada;
    btnPausar.textContent = pausada ? "REANUDAR" : "PAUSAR";
    btnPausar.setAttribute("aria-pressed", pausada ? "true" : "false");
    if (pausada) cancelarAutomatico();
    else programarAutomatico();
  });
  btnAvanzar.addEventListener("click", () => {
    if (escenaActual === escenas.length - 1) cerrarHistoria();
    else mostrarEscena(escenaActual + 1);
  });
  document.addEventListener("keydown", (evento) => {
    if (historia.hidden) return;
    if (evento.key === "Escape") {
      evento.preventDefault();
      evento.stopImmediatePropagation();
      cerrarHistoria();
    } else if (evento.key === "ArrowRight") {
      evento.preventDefault();
      btnAvanzar.click();
    } else if (evento.key === "Tab") {
      const enfocables = elementosEnfocables();
      if (enfocables.length === 0) return;
      const primero = enfocables[0];
      const ultimo = enfocables[enfocables.length - 1];
      if (evento.shiftKey && document.activeElement === primero) {
        evento.preventDefault();
        ultimo.focus();
      } else if (!evento.shiftKey && document.activeElement === ultimo) {
        evento.preventDefault();
        primero.focus();
      }
    }
  }, true);

  if (!yaVista()) abrirHistoria();
})();
