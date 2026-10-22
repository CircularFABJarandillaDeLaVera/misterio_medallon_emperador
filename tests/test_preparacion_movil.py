from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
HTML = (RAIZ / "app/templates/sala.html").read_text(encoding="utf-8")
INICIO_HTML = (RAIZ / "app/templates/inicio.html").read_text(encoding="utf-8")
PREPARACION_HTML = (RAIZ / "app/templates/_preparacion_movil.html").read_text(
    encoding="utf-8"
)
CSS = (RAIZ / "app/static/css/estilos.css").read_text(encoding="utf-8")
SALA_JS = (RAIZ / "app/static/js/sala.js").read_text(encoding="utf-8")
INICIO_JS = (RAIZ / "app/static/js/inicio.js").read_text(encoding="utf-8")
HISTORIA_JS = (RAIZ / "app/static/js/historia.js").read_text(encoding="utf-8")
FULLSCREEN_JS = (RAIZ / "app/static/js/pantalla_completa.js").read_text(
    encoding="utf-8"
)


def test_la_escena_tiene_el_contenido_y_una_unica_accion_principal():
    modal = PREPARACION_HTML

    assert "La investigación está a punto de comenzar" in modal
    assert "Gira tu móvil y colócalo en horizontal" in modal
    assert "ENTRAR EN PANTALLA COMPLETA" in modal
    assert modal.count("<button") == 1
    assert 'aria-modal="true"' in modal
    assert '{% include "_preparacion_movil.html" %}' in HTML
    assert '{% include "_preparacion_movil.html" %}' in INICIO_HTML


def test_la_preparacion_se_abre_antes_de_pintar_la_seleccion():
    inicio = SALA_JS.index("function presentarEstadoPrivado")
    fin = SALA_JS.index("\nconst TITULOS =", inicio)
    presentacion = SALA_JS[inicio:fin]
    assert presentacion.index("prepararInterfazMovilAntesDeMostrar(sala)") < presentacion.index(
        "pintarSala(sala)"
    )

    inicio = SALA_JS.index("function pintarPersonajes")
    fin = SALA_JS.index("function crearMarcaLobby", inicio)
    seleccion = SALA_JS[inicio:fin]
    assert "debeMostrarPreparacionMovil" not in seleccion
    assert 'accion: "elegir_personaje"' in seleccion
    assert 'sala.estado === "esperando"' in SALA_JS
    assert "!sala.personaje_id" in SALA_JS
    assert "pointer: coarse" in SALA_JS
    assert "navegador.maxTouchPoints" in SALA_JS
    assert "ladoCorto <= 600" in SALA_JS


def test_la_frecuencia_se_acota_a_sesion_sala_y_jugador():
    assert "sessionStorage" in SALA_JS
    assert "`preparacion_movil:${codigo}:${jugadorId}`" in SALA_JS
    assert "preparacionMovilCompletadaEnMemoria" in SALA_JS


def test_las_entradas_reales_de_portada_dejan_una_senal_transitoria():
    assert 'prepararEntradaMovil(datos, "crear")' in INICIO_JS
    assert 'prepararEntradaMovil(datos, "unirse")' in INICIO_JS
    assert 'prepararEntradaMovil(datos, "cargar")' in INICIO_JS
    assert '"preparacion_movil_pendiente"' in INICIO_JS
    assert '"preparacion_movil_pendiente"' in SALA_JS
    assert "preparacion_completada: preparacionPortadaCompletada" in INICIO_JS


def test_cargar_puede_mostrar_la_preparacion_aunque_exista_una_marca_antigua():
    inicio = SALA_JS.index("function prepararInterfazMovilAntesDeMostrar")
    fin = SALA_JS.index("if (btnEntrarPantallaCompleta)", inicio)
    preparacion = SALA_JS[inicio:fin]
    assert "entradaPendiente || debeMostrarPreparacionMovil(sala)" in preparacion
    assert "borrarEntradaPreparacionMovil();" in SALA_JS


def test_la_portada_nace_cubierta_y_luego_recupera_sus_formularios_originales():
    cabecera = INICIO_HTML[INICIO_HTML.index("<head>"):INICIO_HTML.index("</head>")]
    assert '<html lang="es" class="preparacion-movil-inicial">' in INICIO_HTML
    assert "ladoCorto > 0 && ladoCorto <= 600" in cabecera
    assert "PreparacionPortadaInicial" in cabecera
    assert "REINTENTAR CARGA" in cabecera

    cuerpo = INICIO_HTML.index("<body")
    modal = INICIO_HTML.index('{% include "_preparacion_movil.html" %}', cuerpo)
    portada = INICIO_HTML.index('class="portada-fondo"', cuerpo)
    inicio_js = INICIO_HTML.index('/static/js/inicio.js', cuerpo)
    assert cuerpo < modal < portada < inicio_js

    apertura = INICIO_JS.index("function iniciarPreparacionPortadaMovil")
    fin_apertura = INICIO_JS.index("function completarPreparacionPortada", apertura)
    bloque_apertura = INICIO_JS[apertura:fin_apertura]
    assert (
        bloque_apertura.index("modalPreparacionMovil.hidden = false")
        < bloque_apertura.rindex('classList.remove("preparacion-movil-inicial")')
    )
    assert 'classList.add("preparacion-movil-activa")' in bloque_apertura
    assert "PreparacionPortadaInicial.tomarControl()" in bloque_apertura

    cierre = INICIO_JS.index("function completarPreparacionPortada")
    fin_cierre = INICIO_JS.index("if (btnEntrarPantallaCompleta)", cierre)
    bloque_cierre = INICIO_JS[cierre:fin_cierre]
    assert "modalPreparacionMovil.hidden = true" in bloque_cierre
    assert 'classList.remove("preparacion-movil-activa")' in bloque_cierre
    assert "solicitarInmersionHorizontal" in bloque_cierre
    assert "abrirModal(" not in bloque_cierre

    for id_modal, id_foco in (
        ("modal-nueva", "alias"),
        ("modal-unirse", "codigo"),
        ("modal-cargar", "archivo-partida"),
    ):
        assert f'abrirModal("{id_modal}", "{id_foco}")' in INICIO_JS
    assert "abrirFormularioConPreparacion" not in INICIO_JS
    assert "omitirHistoriaAutomatica" in HISTORIA_JS


def test_la_sala_no_repite_la_preparacion_terminada_en_portada():
    assert "entrada.preparacion_completada === true" in HTML
    inicio = SALA_JS.index("function prepararInterfazMovilAntesDeMostrar")
    fin = SALA_JS.index("if (btnEntrarPantallaCompleta)", inicio)
    preparacion = SALA_JS[inicio:fin]
    assert "entradaPendiente.preparacion_completada === true" in preparacion
    assert "guardarPreparacionMovilVista();" in preparacion
    assert "borrarEntradaPreparacionMovil();" in preparacion
    assert "window.PreparacionPortadaMovil" in INICIO_JS
    assert "preparacionCompletadaEnEsteDocumento" in SALA_JS
    assert "window.PreparacionSalaMovil" in SALA_JS


def test_fullscreen_y_orientacion_son_mejoras_progresivas():
    assert "requestFullscreen" not in SALA_JS
    assert "solicitarInmersionHorizontal" in SALA_JS
    assert 'orientacion.lock("landscape")' in FULLSCREEN_JS
    assert ".catch(() => false)" in FULLSCREEN_JS
    assert "modalPreparacionMovil.hidden = true" in SALA_JS


def test_el_estilo_esta_aislado_y_responde_a_viewport_y_movimiento_reducido():
    assert '.modal.preparacion-movil {' in CSS
    assert 'url("/static/img/lugares/parador.jpeg")' in CSS
    assert "window.visualViewport" in SALA_JS
    assert "orientation: landscape" in CSS
    assert "max-height: 430px" in CSS
    assert "orientation: portrait" in CSS
    assert "prefers-reduced-motion: reduce" in CSS
    assert "preparacion-girar-telefono" in CSS


def test_la_preparacion_se_pinta_antes_del_primer_paint_en_movil():
    """El estado y el componente nacen antes que la interfaz y que sala.js."""
    inicio = HTML.index("<head>")
    fin = HTML.index("</head>", inicio)
    cabecera = HTML[inicio:fin]
    assert '<html lang="es" class="preparacion-movil-inicial">' in HTML
    assert "preparacion_movil_pendiente" in cabecera
    assert "ladoCorto > 0 && ladoCorto <= 600" in cabecera
    assert "PreparacionMovilInicial" in cabecera
    assert "REINTENTAR CARGA" in cabecera

    cuerpo = HTML.index("<body>")
    modal = HTML.index('{% include "_preparacion_movil.html" %}', cuerpo)
    interfaz = HTML.index('class="contenedor lobby-contenedor interfaz-sala"', cuerpo)
    sala_js = HTML.index('/static/js/sala.js', cuerpo)
    assert cuerpo < modal < interfaz < sala_js

    # La fuerza de pintado es exclusiva de móvil, vence a hidden y elimina la
    # interfaz del layout hasta que el JS principal asume el control.
    regla = CSS.index("html.preparacion-movil-inicial .modal.preparacion-movil[hidden]")
    bloque_media = CSS[CSS.rindex("@media", 0, regla):regla]
    assert "pointer: coarse" in bloque_media
    assert "hover: none" in bloque_media
    assert "max-width: 600px" in bloque_media
    assert "max-height: 600px" in bloque_media
    assert "html.preparacion-movil-inicial .interfaz-sala" in CSS
    assert "html.preparacion-movil-activa .interfaz-sala" in CSS
    assert CSS.count("html.preparacion-movil-inicial .modal.preparacion-movil[hidden]") == 1
    assert ".modal[hidden] {" in CSS

    # sala.js convierte el estado inicial en el estado normal del mismo modal
    # antes de retirar la clase que mantiene oculta la interfaz.
    apertura = SALA_JS.index("function abrirPreparacionMovil")
    fin_apertura = SALA_JS.index("function completarPreparacionMovil", apertura)
    bloque_apertura = SALA_JS[apertura:fin_apertura]
    assert (
        bloque_apertura.index("modalPreparacionMovil.hidden = false")
        < bloque_apertura.index('classList.remove("preparacion-movil-inicial")')
    )
    assert "PreparacionMovilInicial.tomarControl()" in bloque_apertura
    assert 'classList.add("preparacion-movil-activa")' in bloque_apertura
    assert "interfazSala.inert = true" in bloque_apertura

    cierre = SALA_JS.index("function completarPreparacionMovil")
    fin_cierre = SALA_JS.index("function prepararInterfazMovilAntesDeMostrar", cierre)
    bloque_cierre = SALA_JS[cierre:fin_cierre]
    assert 'classList.remove("preparacion-movil-activa")' in bloque_cierre
    assert "interfazSala.inert = false" in bloque_cierre
