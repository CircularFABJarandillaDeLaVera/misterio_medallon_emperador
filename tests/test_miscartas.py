"""Microcorrección UX 3B: MIS CARTAS como vista/modal independiente."""
from fastapi.testclient import TestClient

from app.main import app, conexiones, gestor

cliente = TestClient(app)


def setup_function(_):
    gestor.salas.clear()
    conexiones.clear()


def test_esqueleto_modal_mis_cartas():
    sala, _ = gestor.crear_sala("Paco")
    pagina = cliente.get(f"/sala/{sala.codigo}")
    assert pagina.status_code == 200
    html = pagina.text
    for aguja in (
        'id="modal-cartas"',
        'id="mis-cartas"',
        'id="btn-ver-cartas"',
        'id="btn-cerrar-cartas"',
        "MIS CARTAS",
        "VOLVER A LA PARTIDA",
    ):
        assert aguja in html
    # Las cartas ya no ocupan permanentemente la pantalla principal.
    assert 'id="cartas"' not in html
    # La Hoja sigue intacta.
    for aguja in (
        'id="modal-hoja"',
        'id="hoja"',
        'id="btn-ver-hoja"',
        'id="btn-cerrar-hoja"',
    ):
        assert aguja in html


def test_js_modal_mis_cartas_independiente():
    js = cliente.get("/static/js/sala.js")
    assert js.status_code == 200
    texto = js.text
    assert "function pintarCartas" in texto
    assert "function abrirCartas" in texto
    assert "function cerrarCartas" in texto
    assert "mis-cartas" in texto
    assert "modal-cartas" in texto
    assert "btn-cerrar-cartas" in texto
    # MIS CARTAS usa solo mis_cartas ya recibidas: sin fetch extra.
    assert "mis_cartas" in texto
    # Hoja sigue funcionando igual.
    assert "function pintarHoja" in texto
    assert "function abrirHoja" in texto
    assert "function cerrarHoja" in texto
