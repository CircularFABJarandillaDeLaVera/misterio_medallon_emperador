"""Fase 8A: interfaz responsive con tablero protagonista y panel contextual."""
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app, gestor

cliente = TestClient(app)
RAIZ = Path(__file__).parents[1]
SALA_DOCUMENTO = (RAIZ / "app" / "templates" / "sala.html").read_text(
    encoding="utf-8"
)
SALA_INTERFAZ = (RAIZ / "app" / "templates" / "_sala_interfaz.html").read_text(
    encoding="utf-8"
)
INCLUSION_SALA = '{% include "_sala_interfaz.html" %}'
SALA_HTML = SALA_DOCUMENTO.replace(INCLUSION_SALA, SALA_INTERFAZ)
SALA_JS = (RAIZ / "app" / "static" / "js" / "sala.js").read_text(encoding="utf-8")
CSS = (RAIZ / "app" / "static" / "css" / "estilos.css").read_text(encoding="utf-8")


def test_plantilla_de_sala_extrae_una_unica_interfaz_reutilizable():
    assert SALA_DOCUMENTO.count(INCLUSION_SALA) == 1
    preparacion = '{% include "_preparacion_movil.html" %}'
    assert SALA_DOCUMENTO.index(preparacion) < SALA_DOCUMENTO.index(INCLUSION_SALA)
    assert SALA_INTERFAZ.count(
        '<main class="contenedor lobby-contenedor interfaz-sala">'
    ) == 1
    assert "<!DOCTYPE" not in SALA_INTERFAZ
    assert "<html" not in SALA_INTERFAZ
    assert "<body" not in SALA_INTERFAZ
    assert "<script" not in SALA_INTERFAZ
    assert '{% include "_preparacion_movil.html" %}' not in SALA_INTERFAZ
    assert '{% include "_aprender_a_jugar.html" %}' in SALA_INTERFAZ
    scripts = re.findall(r'<script src="([^?"]+)[^"]*"', SALA_DOCUMENTO)
    assert scripts == [
        "/static/js/tablero_canvas.js",
        "/static/js/audio.js",
        "/static/js/sala.js",
        "/static/js/aprender_a_jugar.js",
        "/static/js/pantalla_completa.js",
    ]


def test_sala_renderizada_conserva_codigo_elementos_e_ids_unicos():
    sala, _ = gestor.crear_sala("Plantilla", "tablero")
    try:
        respuesta = cliente.get(f"/sala/{sala.codigo}")
    finally:
        gestor.salas.pop(sala.codigo, None)

    assert respuesta.status_code == 200
    html = respuesta.text
    assert f'id="codigo">{sala.codigo}</span>' in html
    for elemento in (
        "lobby-personajes",
        "personajes",
        "btn-comenzar",
        "partida",
        "tablero-canvas",
        "barra-controles-inferior",
    ):
        assert f'id="{elemento}"' in html
    ids = re.findall(r'\bid="([^"]+)"', html)
    assert len(ids) == len(set(ids))


def test_1_layout_escritorio_tablero_mas_panel():
    assert 'id="zona-juego"' in SALA_HTML
    assert 'id="tablero-visual"' in SALA_HTML
    assert 'id="panel-contextual"' in SALA_HTML
    assert 'id="vista-contextual"' in SALA_HTML
    assert re.search(r"#zona-juego\s*\{[^}]*display:\s*flex", CSS)
    assert re.search(
        r"@media\s*\(min-width:\s*768px\)[\s\S]*?#zona-juego\s*\{[\s\S]*?display:\s*grid",
        CSS,
    )
    assert re.search(
        r"@media\s*\(min-width:\s*768px\)[\s\S]*?grid-template-columns:[^;]*minmax",
        CSS,
    )
    assert CSS.count("@media (min-width: 768px)") == 3


def test_control_global_de_pantalla_completa_en_portada_y_sala():
    """8B.19: un único control global compartido por ambas pantallas."""
    inicio = (RAIZ / "app" / "templates" / "inicio.html").read_text(encoding="utf-8")
    script = "/static/js/pantalla_completa.js?v=8b19"
    assert script in inicio
    assert script in SALA_HTML
    control = (
        RAIZ / "app" / "static" / "js" / "pantalla_completa.js"
    ).read_text(encoding="utf-8")
    # Fullscreen API estándar, sincronía por evento y degradación sin soporte.
    assert "requestFullscreen" in control
    assert "fullscreenchange" in control
    assert "Pantalla completa" in control
    assert "Salir de pantalla completa" in control
    # Un solo módulo: no se reimplementa dentro de inicio.js ni sala.js.
    assert "requestFullscreen" not in SALA_JS
    assert "requestFullscreen" not in (
        RAIZ / "app" / "static" / "js" / "inicio.js"
    ).read_text(encoding="utf-8")


def test_2_movil_vertical_sin_overflow():
    assert re.search(r"@media\s*\(min-width:\s*900px\)", CSS)
    assert "min-height: 44px" in CSS
    assert "max-width: 100%" in CSS
    assert "overflow-x" not in CSS or "hidden" in CSS


def test_3_listados_tecnicos_no_permanentes_y_4_sala_modo_discretos():
    for aguja in (
        'id="contador-jugadores"',
        'id="bloque-orden"',
        'id="bloque-codigo"',
        'id="resumen-sala"',
        'id="btn-copiar-codigo"',
    ):
        assert aguja in SALA_HTML
    # Los datos siguen en el estado interno (payload intacto).
    assert '"jugadores"' in SALA_JS or "sala.jugadores" in SALA_JS
    assert "contadorJugadores" in SALA_JS
    zonas_partida = re.search(r"const zonasPartida = \[(.*?)\n\];", SALA_JS, re.S)
    assert zonas_partida
    assert re.search(
        r'\{ id: "bloque-orden", propiedad: "hidden", valor: true \}',
        zonas_partida.group(1),
    )
    pantallas = re.search(
        r"const elementosPorPantalla = \{(.*?)\n\};", SALA_JS, re.S
    )
    assert pantallas
    assert re.search(r"partida:\s*\[\s*\.\.\.zonasPartida", pantallas.group(1))
    assert "resumenSala" in SALA_JS and "Modo" in SALA_JS


def test_5_vera_la_cronista():
    datos = cliente.get("/api/personajes").json()["personajes"]
    vera = next(p for p in datos if p["id"] == "vera")
    assert vera["nombre"] == "Vera, la cronista"
    assert "fotógrafa" not in repr(datos)


def test_6_7_peon_activo_y_reduced_motion():
    assert "escalaTurno" in SALA_JS or "escalaTurno" in (
        RAIZ / "app" / "static" / "js" / "tablero_canvas.js"
    ).read_text(encoding="utf-8")
    canvas = (RAIZ / "app" / "static" / "js" / "tablero_canvas.js").read_text(
        encoding="utf-8"
    )
    assert "prefers-reduced-motion" in canvas
    assert "prefers-reduced-motion" in CSS


def test_17_sin_nombres_concretos_en_logica():
    for nombre in (
        "Lucía",
        "Bruno",
        "Álvaro",
        "Mateo",
        "Eulalia",
        "Picota",
        "Parador",
        "Baúl",
    ):
        assert nombre not in SALA_JS, nombre
    assert "Vera, la cronista" not in SALA_JS


def test_21_22_23_24_herramientas_y_modal_rapido_intactos():
    for aguja in (
        'id="barra-herramientas"',
        'id="btn-ver-cartas"',
        'id="btn-ver-hoja"',
        'id="btn-resolver"',
        'id="modal-sospecha"',
        'id="sospecha-sospechoso"',
        'id="sospecha-lugar"',
        'id="sospecha-objeto"',
        'id="modal-ubicacion"',
        'id="tablero-canvas-accesible"',
    ):
        assert aguja in SALA_HTML


def test_28_29_png_tablero_y_jpeg_modal():
    assert "urlTablero" in (
        RAIZ / "app" / "static" / "js" / "tablero_canvas.js"
    ).read_text(encoding="utf-8")
    assert "/static/img/lugares/${idUbicacion}.jpeg" in SALA_JS
    assert "imagenUbicacion.src = urlTarjeta" in SALA_JS


def test_popup_contextual_limitado_al_viewport_sin_deformar_imagen():
    assert "height: 100dvh" in CSS
    assert re.search(r"\.modal\s*\{[^}]*overflow:\s*hidden", CSS, re.DOTALL)
    assert re.search(r"\.modal-caja\s*\{[^}]*max-height:[^;]*100dvh", CSS, re.DOTALL)
    assert re.search(r"\.modal-caja\s*\{[^}]*overflow-y:\s*auto", CSS, re.DOTALL)
    assert re.search(
        r"\.modal-carta-revelacion\s*>\s*img\s*\{[^}]*width:\s*auto"
        r"[^}]*max-width:\s*100%[^}]*height:\s*auto[^}]*object-fit:\s*contain",
        CSS,
        re.DOTALL,
    )
    assert "max-height: min(44dvh, 400px" in CSS


def test_movil_horizontal_reserva_barra_sin_recuperar_mis_cartas():
    """Microfase móvil 1: el ajuste no alcanza escritorio ni vertical."""
    consulta = (
        "@media (orientation: landscape) and (min-width: 768px) "
        "and (max-width: 960px)\n"
        "  and (max-height: 440px) and (pointer: coarse) {"
    )
    assert consulta in CSS
    bloque = CSS[CSS.index(consulta):]
    assert "height: calc(100dvh - 80px - env(safe-area-inset-bottom))" in bloque
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in bloque
    assert "#btn-ver-cartas[hidden]" not in bloque
    assert "min-height: 44px" in bloque
    assert "#destinos-movimiento" in bloque and "overflow-y: auto" in bloque
