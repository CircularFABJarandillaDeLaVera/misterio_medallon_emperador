/* Control global de pantalla completa (Fase 8B.19).
   Un solo módulo para portada, lobby y partida: se inyecta en el
   documento y usa la Fullscreen API estándar. Si el navegador no la
   soporta, el control no se muestra y la aplicación sigue igual.
   Escape lo resuelve el navegador: el evento fullscreenchange
   resincroniza siempre el estado visual. */
(function () {
  "use strict";

  const servicioExistente = globalThis.PantallaCompleta;
  if (servicioExistente && servicioExistente.__servicioCompartido === true) {
    servicioExistente.inicializar();
    return;
  }

  const doc = document;
  const raiz = doc.documentElement;
  const pedir = raiz.requestFullscreen || raiz.webkitRequestFullscreen;
  const salir = doc.exitFullscreen || doc.webkitExitFullscreen;
  const CLAVE_CONTINUIDAD = "pantalla_completa_pendiente";

  const enPantallaCompleta = () =>
    Boolean(doc.fullscreenElement || doc.webkitFullscreenElement);

  function registrarContinuidad(datos) {
    if (!datos || !datos.codigo || !datos.jugador_id) return false;
    try {
      if (!enPantallaCompleta()) {
        sessionStorage.removeItem(CLAVE_CONTINUIDAD);
        return false;
      }
      sessionStorage.setItem(CLAVE_CONTINUIDAD, JSON.stringify({
        codigo: datos.codigo,
        jugador_id: datos.jugador_id,
      }));
      return true;
    } catch (error) {
      // La continuidad es una mejora progresiva: nunca bloquea la sala.
      return false;
    }
  }

  function consumirContinuidadDeEstaSala() {
    const codigoSala = doc.getElementById && doc.getElementById("codigo");
    if (!codigoSala) return false;
    try {
      const cruda = sessionStorage.getItem(CLAVE_CONTINUIDAD);
      if (!cruda) return false;
      sessionStorage.removeItem(CLAVE_CONTINUIDAD);
      const pendiente = JSON.parse(cruda);
      const jugadorId = sessionStorage.getItem("jugador_id") || "";
      return pendiente.codigo === codigoSala.textContent.trim()
        && pendiente.jugador_id === jugadorId;
    } catch (error) {
      try {
        sessionStorage.removeItem(CLAVE_CONTINUIDAD);
      } catch (errorAlLimpiar) {
        // Sin almacenamiento disponible tampoco puede quedar una señal activa.
      }
      return false;
    }
  }

  function intentarOrientacionHorizontal() {
    const orientacion = typeof screen !== "undefined" ? screen.orientation : null;
    if (!orientacion || typeof orientacion.lock !== "function") {
      return Promise.resolve(false);
    }
    try {
      const bloqueo = orientacion.lock("landscape");
      return Promise.resolve(bloqueo).then(() => true).catch(() => false);
    } catch (error) {
      return Promise.resolve(false);
    }
  }

  function solicitarInmersionHorizontal() {
    let solicitud = Promise.resolve(enPantallaCompleta());
    if (!enPantallaCompleta() && typeof pedir === "function") {
      try {
        solicitud = Promise.resolve(pedir.call(raiz))
          .then(() => true)
          .catch(() => false);
      } catch (error) {
        solicitud = Promise.resolve(false);
      }
    }
    // El bloqueo horizontal es una mejora progresiva. También se intenta si
    // fullscreen no existe o se rechaza, y nunca condiciona el juego.
    return solicitud.then(() => intentarOrientacionHorizontal());
  }

  let boton = null;
  let faseVisual = null;
  let anfitrionExplicito = null;

  function anfitrionActual() {
    if (anfitrionExplicito) return anfitrionExplicito;
    const portada = doc.querySelector(".portada-escena");
    const lobby = doc.querySelector(".lobby-sala-linea");
    const barra = doc.querySelector(".barra-controles-inferior");
    const marco = doc.querySelector(".tarjeta");
    if (faseVisual === "portada") return portada || marco || doc.body;
    if (faseVisual === "seleccion" || faseVisual === "lobby") {
      return lobby || marco || barra || doc.body;
    }
    if (faseVisual === "tablero") return barra || marco || doc.body;
    if (portada) return portada;
    if (
      barra && doc.body && doc.body.classList &&
      doc.body.classList.contains("en-partida")
    ) {
      return barra;
    }
    return lobby || barra || marco || doc.body;
  }

  function colocarControl() {
    const anfitrion = anfitrionActual();
    if (boton && anfitrion && boton.parentNode !== anfitrion) {
      anfitrion.appendChild(boton);
    }
  }

  function actualizarFase(fase, anfitrion) {
    faseVisual = fase || null;
    anfitrionExplicito = anfitrion || null;
    return inicializar();
  }

  function inicializar() {
    if (!boton) return null;
    colocarControl();
    sincronizar();
    return boton;
  }

  globalThis.PantallaCompleta = {
    __servicioCompartido: true,
    solicitarInmersionHorizontal,
    registrarContinuidad,
    inicializar,
    actualizarFase,
    obtenerControl: () => boton,
  };

  if (typeof pedir !== "function" || typeof salir !== "function") return;

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

  boton = doc.createElement("button");
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
  const etiquetaRecuperacion = doc.createElement("span");
  etiquetaRecuperacion.className = "control-pantalla-recuperacion";
  etiquetaRecuperacion.textContent = "CONTINUAR EN PANTALLA COMPLETA";
  etiquetaRecuperacion.hidden = true;
  boton.appendChild(iconoEntrar);
  boton.appendChild(iconoSalir);
  boton.appendChild(etiquetaRecuperacion);

  let recuperacionPendiente = consumirContinuidadDeEstaSala();

  function sincronizar() {
    const activo = enPantallaCompleta();
    if (activo) recuperacionPendiente = false;
    iconoEntrar.hidden = activo;
    iconoSalir.hidden = !activo;
    const lobby = doc.querySelector(".lobby-sala-linea");
    const recuperando = recuperacionPendiente && !activo && anfitrionActual() === lobby;
    etiquetaRecuperacion.hidden = !recuperando;
    boton.classList.toggle("control-pantalla-recuperar", recuperando);
    const texto = activo
      ? "Salir de pantalla completa"
      : recuperando ? "Continuar en pantalla completa" : "Pantalla completa";
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
    const entrada = solicitarInmersionHorizontal();
    if (entrada && typeof entrada.catch === "function") {
      // Navegador sin permiso o política de gestos: sin aviso técnico.
      entrada.then(sincronizar, sincronizar);
    }
  });

  function alCambiarFullscreen() {
    colocarControl();
    sincronizar();
  }

  doc.addEventListener("fullscreenchange", alCambiarFullscreen);
  doc.addEventListener("webkitfullscreenchange", alCambiarFullscreen);
  doc.addEventListener("fullscreenerror", alCambiarFullscreen);

  // En el lobby permanece junto al código de sala; cuando empieza la partida
  // el mismo nodo pasa a la barra flexible de accesos.
  if (typeof MutationObserver !== "undefined" && doc.body) {
    const observadorAnfitrion = new MutationObserver(() => {
      colocarControl();
      sincronizar();
    });
    observadorAnfitrion.observe(doc.body, {
      attributes: true,
      attributeFilter: ["class"],
    });
  }
  inicializar();
})();
