import json
import math

from fastapi.testclient import TestClient

from app.datos.tablero_visual import (
    COORDENADAS_UBICACIONES,
    RADIOS_UBICACIONES,
    TABLERO_VISUAL,
)
from app.main import app
from app.motor.tablero import EXTERIORES, TABLERO


def test_descriptor_visual_cubre_exactamente_todos_los_nodos_reales():
    nodos = {nodo["id"] for nodo in TABLERO_VISUAL["nodos"]}
    assert nodos == set(TABLERO.posiciones_validas)
    assert set(COORDENADAS_UBICACIONES) == set(TABLERO.ubicaciones)
    assert sum(n["tipo"] == "ubicacion" for n in TABLERO_VISUAL["nodos"]) == 9
    assert sum(n["tipo"] == "casilla" for n in TABLERO_VISUAL["nodos"]) == 48


def test_caminos_visuales_derivan_los_16_caminos_y_sus_tres_casillas():
    caminos = {camino["id"]: camino for camino in TABLERO_VISUAL["caminos"]}
    assert set(caminos) == set(TABLERO.caminos)
    assert len(caminos) == 16
    for camino_id, visual in caminos.items():
        logico = TABLERO.caminos[camino_id]
        assert visual["nodos"] == [logico.origen, *logico.casillas, logico.destino]
        assert len(logico.casillas) == 3


def test_octagono_regular_y_caminos_visibles_de_longitud_equivalente():
    centro = COORDENADAS_UBICACIONES["plaza-constitucion"]
    exteriores = list(EXTERIORES)
    radios = [math.dist(COORDENADAS_UBICACIONES[uid], centro) for uid in exteriores]
    lados = [
        math.dist(
            COORDENADAS_UBICACIONES[exteriores[i]],
            COORDENADAS_UBICACIONES[exteriores[(i + 1) % 8]],
        )
        for i in range(8)
    ]
    assert max(radios) - min(radios) < 0.002
    assert max(lados) - min(lados) < 0.002

    longitudes = [
        math.dist(
            (camino["inicio"]["x"], camino["inicio"]["y"]),
            (camino["fin"]["x"], camino["fin"]["y"]),
        )
        for camino in TABLERO_VISUAL["caminos"]
    ]
    assert max(longitudes) - min(longitudes) < 0.003


def test_casillas_se_interpolan_25_50_75_por_ciento_entre_bordes():
    nodos = {nodo["id"]: nodo for nodo in TABLERO_VISUAL["nodos"]}
    for visual in TABLERO_VISUAL["caminos"]:
        logico = TABLERO.caminos[visual["id"]]
        inicio = (visual["inicio"]["x"], visual["inicio"]["y"])
        fin = (visual["fin"]["x"], visual["fin"]["y"])
        assert math.isclose(
            math.dist(COORDENADAS_UBICACIONES[logico.origen], inicio),
            RADIOS_UBICACIONES[logico.origen], abs_tol=0.002,
        )
        assert math.isclose(
            math.dist(COORDENADAS_UBICACIONES[logico.destino], fin),
            RADIOS_UBICACIONES[logico.destino], abs_tol=0.002,
        )
        for paso, casilla_id in enumerate(logico.casillas, start=1):
            esperado = (
                inicio[0] + (fin[0] - inicio[0]) * paso / 4,
                inicio[1] + (fin[1] - inicio[1]) * paso / 4,
            )
            real = (nodos[casilla_id]["x"], nodos[casilla_id]["y"])
            assert math.dist(real, esperado) < 0.002


def test_pasadizos_visuales_son_exactamente_los_del_motor():
    visuales = {
        (p["id"], frozenset((p["origen"], p["destino"])))
        for p in TABLERO_VISUAL["pasadizos"]
    }
    logicos = {
        (p.id, frozenset((p.origen, p.destino)))
        for p in TABLERO.pasadizos.values()
    }
    assert visuales == logicos


def test_descriptor_publico_usa_runtime_y_no_expone_datos_privados():
    respuesta = TestClient(app).get("/api/tablero")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"tablero": TABLERO_VISUAL}
    texto = json.dumps(respuesta.json()).lower()
    for prohibido in ("misterio", "mano", "vista", "deduccion", "candidato"):
        assert prohibido not in texto
    ubicaciones = [n for n in TABLERO_VISUAL["nodos"] if n["tipo"] == "ubicacion"]
    assert all(
        n["imagen_tarjeta"].startswith("/static/img/lugares/")
        and n["imagen_tablero"].startswith("/static/img/lugares/")
        and n["imagen_tarjeta"] != n["imagen_tablero"]
        for n in ubicaciones
    )
    assert TABLERO_VISUAL["peon"] == "/static/img/personajes/peon.svg"
    assert set(TABLERO_VISUAL["colores_personajes"]) == {
        "vera", "bruno", "lucia", "alvaro", "mateo", "eulalia"
    }
    assert "personajes" not in TABLERO_VISUAL
