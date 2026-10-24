/* Instrucciones locales compartidas por portada y sala. No conoce ni modifica
   el estado de la partida y nunca envía acciones de red. */
"use strict";

(() => {
  const modal = document.getElementById("modal-aprender");
  const abrir = Array.from(document.querySelectorAll("[data-abrir-aprender]"));
  if (!modal || abrir.length === 0) return;

  const indices = Array.from(modal.querySelectorAll("[data-aprender-paso]"));
  const paneles = Array.from(modal.querySelectorAll("[data-aprender-panel]"));
  const anterior = document.getElementById("btn-anterior-aprender");
  const siguiente = document.getElementById("btn-siguiente-aprender");
  const cerrar = document.getElementById("btn-cerrar-aprender");
  const progreso = document.getElementById("aprender-progreso");
  let paso = 0;
  let focoAnterior = null;

  function elementosEnfocables() {
    return Array.from(modal.querySelectorAll("button:not([disabled])"))
      .filter((elemento) => !elemento.hidden);
  }

  function mostrarPaso(nuevoPaso, enfocarIndice = false) {
    paso = Math.max(0, Math.min(paneles.length - 1, nuevoPaso));
    paneles.forEach((panel, indice) => {
      panel.hidden = indice !== paso;
    });
    indices.forEach((boton, indice) => {
      if (indice === paso) boton.setAttribute("aria-current", "step");
      else boton.removeAttribute("aria-current");
    });
    anterior.disabled = paso === 0;
    siguiente.hidden = paso === paneles.length - 1;
    progreso.textContent = `${paso + 1} DE ${paneles.length}`;
    const contenido = document.getElementById("aprender-contenido");
    if (contenido) contenido.scrollTop = 0;
    if (enfocarIndice && indices[paso] && indices[paso].focus) indices[paso].focus();
  }

  function abrirInstrucciones(evento) {
    focoAnterior = evento && evento.target && evento.target.closest
      ? evento.target.closest("[data-abrir-aprender]") || document.activeElement
      : document.activeElement;
    mostrarPaso(0);
    modal.hidden = false;
    sincronizarBarraSala();
    if (cerrar.focus) cerrar.focus();
  }

  function cerrarInstrucciones() {
    modal.hidden = true;
    sincronizarBarraSala();
    if (focoAnterior && focoAnterior.focus) focoAnterior.focus();
    focoAnterior = null;
  }

  function sincronizarBarraSala() {
    if (
      typeof window !== "undefined" &&
      typeof window.sincronizarBarraControlesInferior === "function"
    ) {
      window.sincronizarBarraControlesInferior();
    }
  }

  // El montaje de sala sustituye el contenido de <body>, pero conserva este
  // modal y crea un activador nuevo. Delegar en document mantiene accesibles
  // ambos activadores durante ese cambio de árbol.
  document.addEventListener("click", (evento) => {
    const boton = evento.target && evento.target.closest
      ? evento.target.closest("[data-abrir-aprender]")
      : null;
    if (boton) abrirInstrucciones(evento);
  });
  indices.forEach((boton) => boton.addEventListener("click", () => {
    mostrarPaso(Number(boton.dataset.aprenderPaso), true);
  }));
  anterior.addEventListener("click", () => mostrarPaso(paso - 1));
  siguiente.addEventListener("click", () => mostrarPaso(paso + 1));
  cerrar.addEventListener("click", cerrarInstrucciones);
  modal.addEventListener("click", (evento) => {
    if (evento.target === modal) cerrarInstrucciones();
  });
  document.addEventListener("keydown", (evento) => {
    if (modal.hidden) return;
    if (evento.key === "Escape") {
      evento.preventDefault();
      evento.stopImmediatePropagation();
      cerrarInstrucciones();
      return;
    }
    if (evento.key !== "Tab") return;
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
  }, true);

  mostrarPaso(0);
})();
