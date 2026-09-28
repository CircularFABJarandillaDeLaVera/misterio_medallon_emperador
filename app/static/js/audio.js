/* Audio de partida y efectos (Fases 8B.33 y 8B.33B).
   Un unico modulo, en el mismo espirito que pantalla_completa.js: sin
   dependencias, sin segundo `Audio` por efecto y sin errores visibles.

   - La musica ambiental es UNA pista en loop, propiedad de este cliente.
      El volumen es una preferencia LOCAL del dispositivo (localStorage):
      nunca viaja por WebSocket ni pertenece a la Sala.
   - El navegador puede rechazar `play()` sin gesto previo. NO se intenta
     forzar: la pista queda preparada y arranca en la primera interaccion
     real del jugador (el propio control, el tablero o cualquier accion
     valida). Un rechazo es un no-op silencioso.
   - Los EFECTOS (clic, final) son pistas cortas propias, con su propia
     ruta runtime y su propio volumen relativo al del jugador. El clic
     existe desde la portada; la musica, solo durante la partida.
   - `reproducirEfecto(nombre)` es el anclaje ya preparado: registro de
     efectos, instancias perezosas (una por efecto, se reinician) y
     ningun sistema de audio paralelo. */(function () {
  "use strict";

  const CLAVE_VOLUMEN = "volumen_musica";
  const VOLUMEN_POR_DEFECTO = 0.15;
  const NOMBRE_TRACK = "musica_fondo";
  const NOMBRE_CLIC = "clic";
  const NOMBRE_FINAL = "final";

  // Rutas por defecto. El manifiesto canonico las confirma al cargar; asi el
  // modulo no depende del orden de carga de `/api/recursos`.
  let urlMusica = "/static/audio/musica_fondo.mp3";
  let urlClic = "/static/audio/clic.mp3";
  let urlFinal = "/static/audio/final.mp3";

  // Mixaje: musica ambiental muy suave, clic claramente perceptible pero
  // discreto y final algo mas protagonista. Multiplicadores sobre el volumen
  // elegido por el jugador: no se modifica ningun archivo de audio.
  const VUELO_MUSICA = 1;
  const VUELO_CLIC = 2.2;
  const VUELO_FINAL = 3;

  // La pista musical se crea LAZILY: cargar el modulo en la portada no
  // descarga ni reproduce musica_fondo (8B.33B).
  let musica = null;
  function obtenerMusica() {
    if (musica) return musica;
    musica = new Audio();
    // El lobby no reproduce nada y el MP3 pesa: solo se pide su metadato
    // hasta que la partida pide musica de verdad. Al sonar, el navegador
    // descarga el resto. Es una decision de este cliente, no del servidor.
    musica.preload = "metadata";
    musica.loop = true;
    musica.volume = volumen * VUELO_MUSICA;
    musica.src = urlMusica;
    return musica;
  }

  // Efectos: una instancia por nombre, creada al primer uso y REINICIADA
  // en cada disparo. Nunca se acumulan objetos Audio con clics seguidos.
  const efectos = new Map([
    [NOMBRE_CLIC, { url: () => urlClic, vuelo: VUELO_CLIC, instancia: null }],
    [NOMBRE_FINAL, { url: () => urlFinal, vuelo: VUELO_FINAL, instancia: null }],
  ]);
  const finalYaReproducido = { valor: false };

  let volumen = VOLUMEN_POR_DEFECTO;
  let deseada = false;   // la partida pide musica
  let sonando = false;   // la pista esta realmente reproduciendo
  let enCurso = false;   // hay un play() pendiente de resolverse
  let generacion = 0;    // invalida los play() que quedaron en el aire
  let gestoReservado = false;

  function leerVolumen() {
    try {
      const guardado = window.localStorage.getItem(CLAVE_VOLUMEN);
      if (guardado === null) return VOLUMEN_POR_DEFECTO;
      const valor = Number(guardado);
      if (!Number.isFinite(valor)) return VOLUMEN_POR_DEFECTO;
      return Math.min(1, Math.max(0, valor));
    } catch (error) {
      // Almacenamiento bloqueado (modo privado): preferencia de sesion.
      return VOLUMEN_POR_DEFECTO;
    }
  }

  function guardarVolumen() {
    try {
      window.localStorage.setItem(CLAVE_VOLUMEN, String(volumen));
    } catch (error) {
      /* Sin persistencia: el volumen sigue valiendo en esta pestana. */
    }
  }

  function aplicarVolumen() {
    // El mismo mando gobierna musica y efectos. Con volumen 0 calla todo.
    if (musica) musica.volume = Math.min(1, volumen * VUELO_MUSICA);
    efectos.forEach(function (efecto) {
      if (efecto.instancia) {
        efecto.instancia.volume = Math.min(1, volumen * efecto.vuelo);
      }
    });
  }

  function fijarVolumen(valor) {
    const numero = Number(valor);
    if (!Number.isFinite(numero)) return volumen;
    volumen = Math.min(1, Math.max(0, numero));
    aplicarVolumen();
    guardarVolumen();
    sincronizarControl();
    // Tocar el control tambien cuenta como gesto: intenta unlocking.
    if (deseada) intentarReproducir();
    return volumen;
  }

  /* --- Efectos (8B.33B) --- */
  function reproducirEfecto(nombre) {
    const efecto = efectos.get(nombre);
    if (!efecto) return null;
    // Mute compartido: con volumen 0 no suena musica ni ningun efecto.
    if (volumen === 0) return null;
    // El final representa el MOMENTO del final: una sola vez por pagina.
    if (nombre === NOMBRE_FINAL && finalYaReproducido.valor) return null;
    if (!efecto.instancia) {
      const pista = new Audio();
      pista.preload = "auto";
      pista.loop = false;
      pista.volume = Math.min(1, volumen * efecto.vuelo);
      pista.src = efecto.url();
      efecto.instancia = pista;
    }
    // Reinicio: un clic tras otro responde al instante sin acumular
    // objetos Audio ni apilar reproducciones.
    const pista = efecto.instancia;
    pista.volume = Math.min(1, volumen * efecto.vuelo);
    pista.currentTime = 0;
    if (nombre === NOMBRE_FINAL) finalYaReproducido.valor = true;
    try {
      const intento = pista.play();
      if (intento && typeof intento.catch === "function") {
        // Sin gesto previo o politica del navegador: silencio, sin error.
        intento.catch(function () {});
      }
    } catch (error) {
      /* Sin excepciones visibles. */
    }
    return pista;
  }

  function intentarReproducir() {
    // Idempotente: ni los repintados, ni un gesto repetido, ni varias
    // redifusiones seguidas abren una segunda reproduccion.
    if (sonando || enCurso) return true;
    if (volumen === 0) return false;
    const pista = obtenerMusica();
    const mio = generacion;
    let intento;
    try {
      intento = pista.play();
    } catch (error) {
      return false;   // sin excepciones visibles
    }
    if (intento && typeof intento.then === "function") {
      enCurso = true;
      intento.then(
        function () {
          enCurso = false;
          // Si la partida termino mientras PLAY estaba en vuelo, el estado
          // final manda: la musica no continua detras de la pantalla final.
          if (mio === generacion) sonando = true;
        },
        function () {
          enCurso = false;   // autoplay bloqueado: sin aviso, sin error
        }
      );
      return true;
    }
    sonando = true;
    return true;
  }

  // Primera interaccion real del jugador: gesto legitimo del navegador para
  // desbloquear el audio. Se instala una sola vez y solo mientras la partida
  // pide musica, de modo que no intercepta nada.
  function reservarGesto() {
    if (gestoReservado) return;
    gestoReservado = true;
    const eventos = ["pointerdown", "keydown", "touchend"];
    function alInteractuar() {
      eventos.forEach(function (evento) {
        document.removeEventListener(evento, alInteractuar);
      });
      gestoReservado = false;
      if (deseada) intentarReproducir();
    }
    eventos.forEach(function (evento) {
      document.addEventListener(evento, alInteractuar, { passive: true });
    });
  }

  function iniciar() {
    // Idempotente: se llama en cada repintado y solo la primera vez cambia
    // algo. Nunca crea una segunda pista.
    deseada = true;
    aplicarVolumen();
    if (volumen === 0) {
      sincronizarControl();
      return;
    }
    reservarGesto();
    intentarReproducir();
    sincronizarControl();
  }

  function detener() {
    // Fin de partida: la musica no continua detras de la pantalla final.
    // En portada/lobby la pista puede no existir todavia: es un no-op.
    deseada = false;
    generacion += 1;
    enCurso = false;
    if (musica) {
      musica.pause();
      musica.currentTime = 0;
    }
    sonando = false;
    sincronizarControl();
  }

  /* --- Clic: una interaccion manual valida = un clic sonoro (8B.33B) ---
     Delegado en fase de captura sobre el documento, pero SOLO sobre la
     estructura real de controles: botones y medallones, campos de
     formulario, casillas con rol, el canvas del tablero y las miniaturas
     de carta. Nunca sobre texto, zonas decorativas o estados que el
     servidor redibuja: los WebSocket, los repintados, las jugadas PNJ y
     las aperturas automaticas de modal no pasan por aqui. */
  const doc = document;
  const ES_CONTROL = "button, a[href], input, select, textarea, label, canvas, " +
    "[role=button], .carta-visual-compacta, .carta-selector-sospecha";

  function esControlInteractivo(destino) {
    let nodo = destino;
    while (nodo && nodo.nodeType === 1) {
      if (nodo.disabled === true) return false;
      if (nodo.getAttribute && nodo.getAttribute("aria-disabled") === "true") return false;
      if (nodo.matches && nodo.matches(ES_CONTROL)) return true;
      nodo = nodo.parentElement;
    }
    return false;
  }

  doc.addEventListener("click", function (evento) {
    if (!esControlInteractivo(evento.target)) return;
    reproducirEfecto(NOMBRE_CLIC);
  }, true);

  /* --- Control compacto junto al de pantalla completa --- */
  const enPortada = doc.body && doc.body.classList
    && doc.body.classList.contains("portada");
  const boton = doc.createElement("button");
  boton.type = "button";
  boton.className = "medallon medallon-fantasma control-sonido";
  const icono = doc.createElement("span");
  icono.className = "control-pantalla-icono";
  const SVG_SONIDO =
    '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
    '<path d="M4 9v6h4l5 4V5L8 9H4z" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linejoin="round"/>' +
    '<path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12" fill="none" ' +
    'stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
  const SVG_SILENCIO =
    '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
    '<path d="M4 9v6h4l5 4V5L8 9H4z" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linejoin="round"/>' +
    '<path d="M16 9.5l5 5M21 9.5l-5 5" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linecap="round"/></svg>';
  icono.innerHTML = SVG_SONIDO;
  boton.appendChild(icono);

  const panel = doc.createElement("div");
  panel.className = "control-sonido-panel";
  panel.hidden = true;
  const etiqueta = doc.createElement("label");
  etiqueta.className = "control-sonido-etiqueta";
  etiqueta.textContent = "Volumen";
  const slider = doc.createElement("input");
  slider.type = "range";
  slider.min = "0";
  slider.max = "100";
  slider.step = "1";
  slider.className = "control-sonido-slider";
  slider.setAttribute("aria-label", "Volumen de la música");
  const valor = doc.createElement("span");
  valor.className = "control-sonido-valor";
  etiqueta.appendChild(slider);
  panel.appendChild(etiqueta);
  panel.appendChild(valor);

  function sincronizarControl() {
    const silenciado = volumen === 0;
    icono.innerHTML = silenciado ? SVG_SILENCIO : SVG_SONIDO;
    boton.classList.toggle("silenciado", silenciado);
    const texto = silenciado ? "Sonido silenciado" : "Sonido";
    boton.setAttribute("aria-label", `${texto}. Volumen ${Math.round(volumen * 100)}%`);
    boton.setAttribute("title", `${texto}: ${Math.round(volumen * 100)}%`);
    boton.setAttribute("aria-pressed", silenciado ? "false" : "true");
    boton.setAttribute("aria-expanded", panel.hidden ? "false" : "true");
    if (document.activeElement !== slider) {
      slider.value = String(Math.round(volumen * 100));
    }
    valor.textContent = `${Math.round(volumen * 100)}%`;
  }

  boton.addEventListener("click", function () {
    panel.hidden = !panel.hidden;
    boton.setAttribute("aria-expanded", panel.hidden ? "false" : "true");
    // El propio control es gesto: intenta la musica si la partida la pide.
    if (deseada) intentarReproducir();
    sincronizarControl();
  });

  slider.addEventListener("input", function () {
    fijarVolumen(Number(slider.value) / 100);
  });

  // Cerrar el panel al pulsar fuera, sin capturar el resto de la interfaz.
  doc.addEventListener("pointerdown", function (evento) {
    if (panel.hidden) return;
    if (panel.contains(evento.target) || boton.contains(evento.target)) return;
    panel.hidden = true;
    sincronizarControl();
  });

  // El control vive junto al de pantalla completa, en el marco de la vista
  // de PARTIDA. En portada el modulo se carga para el clic, pero no pinta
  // nada: alli no hay musica que gobernar ni debe cambiar la pantalla.
  if (!enPortada) {
    const referencia = doc.querySelector(".control-pantalla-completa");
    const anfitrion =
      (referencia && referencia.parentElement) ||
      doc.querySelector(".tarjeta") ||
      doc.body;
    boton.appendChild(panel);
    anfitrion.appendChild(boton);
  }

  volumen = leerVolumen();
  aplicarVolumen();
  sincronizarControl();

  // El manifiesto canonico confirma las rutas cuando llega. Solo se usan si
  // la pista o el efecto aun no han empezado: nunca se cambia una fuente
  // en mitad de la reproduccion ni se reinicia el audio.
  fetch("/api/recursos")
    .then(function (respuesta) { return respuesta.json(); })
    .then(function (datos) {
      const audio = (datos && datos.audio) || {};
      if (audio[NOMBRE_TRACK] && audio[NOMBRE_TRACK] !== urlMusica) {
        urlMusica = audio[NOMBRE_TRACK];
        if (musica && !sonando && musica.currentTime === 0) musica.src = urlMusica;
      }
      if (audio[NOMBRE_CLIC]) urlClic = audio[NOMBRE_CLIC];
      if (audio[NOMBRE_FINAL]) urlFinal = audio[NOMBRE_FINAL];
    })
    .catch(function () {
      /* Manifiesto no disponible: se mantienen las rutas por defecto. */
    });

  window.AudioFondo = {
    iniciar: iniciar,
    detener: detener,
    fijarVolumen: fijarVolumen,
    volumenActual: function () { return volumen; },
    isSonando: function () { return sonando; },
    // Anclaje de efectos (8B.33B): "clic" y "final" ya estan registrados.
    reproducirEfecto: reproducirEfecto,
  };
})();
