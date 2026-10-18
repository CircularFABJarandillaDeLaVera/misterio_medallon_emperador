from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
HTML = (RAIZ / "app/templates/sala.html").read_text(encoding="utf-8")
CSS = (RAIZ / "app/static/css/estilos.css").read_text(encoding="utf-8")
SALA_JS = (RAIZ / "app/static/js/sala.js").read_text(encoding="utf-8")
INICIO_JS = (RAIZ / "app/static/js/inicio.js").read_text(encoding="utf-8")
FULLSCREEN_JS = (RAIZ / "app/static/js/pantalla_completa.js").read_text(
    encoding="utf-8"
)


def test_la_escena_tiene_el_contenido_y_una_unica_accion_principal():
    inicio = HTML.index('id="modal-preparacion-movil"')
    fin = HTML.index('id="modal-resolver"', inicio)
    modal = HTML[inicio:fin]

    assert "La investigación está a punto de comenzar" in modal
    assert "Gira tu móvil y colócalo en horizontal" in modal
    assert "ENTRAR EN PANTALLA COMPLETA" in modal
    assert modal.count("<button") == 1
    assert 'aria-modal="true"' in modal


def test_la_preparacion_se_abre_antes_de_pintar_la_seleccion():
    inicio = SALA_JS.index("function presentarEstadoPrivado")
    fin = SALA_JS.index("ws.onclose", inicio)
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


def test_cargar_puede_mostrar_la_preparacion_aunque_exista_una_marca_antigua():
    inicio = SALA_JS.index("function prepararInterfazMovilAntesDeMostrar")
    fin = SALA_JS.index("if (btnEntrarPantallaCompleta)", inicio)
    preparacion = SALA_JS[inicio:fin]
    assert "entradaPendiente || debeMostrarPreparacionMovil(sala)" in preparacion
    assert "borrarEntradaPreparacionMovil();" in SALA_JS


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
