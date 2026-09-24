"""Fase 8A: interfaz responsive con tablero protagonista y panel contextual."""
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

cliente = TestClient(app)
RAIZ = Path(__file__).parents[1]
SALA_HTML = (RAIZ / "app" / "templates" / "sala.html").read_text(encoding="utf-8")
SALA_JS = (RAIZ / "app" / "static" / "js" / "sala.js").read_text(encoding="utf-8")
CSS = (RAIZ / "app" / "static" / "css" / "estilos.css").read_text(encoding="utf-8")


def test_1_layout_escritorio_tablero_mas_panel():
    assert 'id="zona-juego"' in SALA_HTML
    assert 'id="tablero-visual"' in SALA_HTML
    assert 'id="panel-contextual"' in SALA_HTML
    assert 'id="vista-contextual"' in SALA_HTML
    assert re.search(r"#zona-juego\s*\{[^}]*display:\s*flex", CSS)
    assert re.search(
        r"@media\s*\(min-width:\s*900px\)[\s\S]*?#zona-juego\s*\{[\s\S]*?display:\s*grid",
        CSS,
    )
    assert re.search(
        r"@media\s*\(min-width:\s*900px\)[\s\S]*?grid-template-columns:[^;]*minmax",
        CSS,
    )


def test_2_movil_vertical_sin_overflow():
    assert re.search(r"@media\s*\(min-width:\s*900px\)", CSS)
    assert "min-height: 44px" in CSS
    assert "max-width: 100%" in CSS
    assert "overflow-x" not in CSS or "hidden" in CSS


def test_3_listados_tecnicos_no_permanentes_y_4_sala_modo_discretos():
    for aguja in (
        'id="bloque-jugadores"',
        'id="bloque-orden"',
        'id="bloque-codigo"',
        'id="resumen-sala"',
        'id="btn-copiar-codigo"',
    ):
        assert aguja in SALA_HTML
    # Los datos siguen en el estado interno (payload intacto).
    assert '"jugadores"' in SALA_JS or "sala.jugadores" in SALA_JS
    assert "bloqueJugadores.hidden = true" in SALA_JS
    assert "bloqueOrden.hidden = true" in SALA_JS
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
    assert "imagen_tarjeta" in SALA_JS
    assert "tarjeta-contextual" in SALA_JS
