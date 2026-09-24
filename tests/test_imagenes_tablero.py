"""Microfase 7E: imágenes dedicadas tablero_*.png para el Canvas.

Tarjeta completa (modal) e imagen de tablero (medallón Canvas) son dos
recursos distintos para la misma ubicación canónica.
"""
import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from app.datos.jarandilla import LUGARES
from app.datos.recursos import IMAGEN_TABLERO_POR_ID, RECURSOS_VISUALES
from app.datos.tablero_visual import TABLERO_VISUAL
from app.main import app
from app.motor.sala import (
    ESTADO_INICIADA,
    JUGADA_ESPERANDO_MOVIMIENTO,
    MODO_RAPIDO,
    MODO_TABLERO,
    POSICIONES_INICIALES,
    Sala,
)
from app.motor.tablero import TABLERO

cliente = TestClient(app)
RAIZ = Path(__file__).parents[1]
STATIC_LUGARES = RAIZ / "app" / "static" / "img" / "lugares"
ORIGEN_LUGARES = RAIZ / "recursos" / "lugares"

CORRESPONDENCIA = {
    "parador": "tablero_parador.png",
    "iglesia-san-agustin": "tablero_iglesia_san_agustin.png",
    "ermita-sopetran": "tablero_ermita_sopetran.png",
    "picota": "tablero_picota.png",
    "plaza-constitucion": "tablero_plaza_constitucion.png",
    "cristo-humilladero": "tablero_cristo_humilladero.png",
    "puente-parral": "tablero_puente_parral.png",
    "museo-escobazos": "tablero_museo_escobazos.png",
    "nuestra-senora-torre": "tablero_nuestra_senora_torre.png",
}
FIRMA_PNG = b"\x89PNG\r\n\x1a\n"


def ids_ubicacion():
    return [u["id"] for u in LUGARES]


def test_1_nueve_png_canonicos_con_firma_real():
    assert set(CORRESPONDENCIA) == set(ids_ubicacion())
    assert len(IMAGEN_TABLERO_POR_ID) == 9
    for uid, nombre in CORRESPONDENCIA.items():
        assert IMAGEN_TABLERO_POR_ID[uid] == f"/static/img/lugares/{nombre}"
        assert nombre.startswith("tablero_") and nombre.endswith(".png")
        assert nombre == nombre.lower() and nombre.isascii()


def test_2_cada_id_tiene_imagen_tablero_y_3_mantiene_tarjeta():
    nodos = {
        n["id"]: n for n in TABLERO_VISUAL["nodos"] if n["tipo"] == "ubicacion"
    }
    assert set(nodos) == set(ids_ubicacion())
    for uid in ids_ubicacion():
        assert nodos[uid]["imagen_tablero"] == IMAGEN_TABLERO_POR_ID[uid]
        assert nodos[uid]["imagen_tarjeta"] == RECURSOS_VISUALES[uid]["principal"]
        assert "imagen" not in nodos[uid]


def test_4_urls_tablero_y_tarjeta_diferentes():
    for uid in ids_ubicacion():
        assert IMAGEN_TABLERO_POR_ID[uid] != RECURSOS_VISUALES[uid]["principal"]
    assert len(set(IMAGEN_TABLERO_POR_ID.values())) == 9


def test_5_runtime_existen_y_6_son_identicos_al_original():
    for uid, nombre in CORRESPONDENCIA.items():
        runtime = STATIC_LUGARES / nombre
        original = ORIGEN_LUGARES / uid / nombre
        assert runtime.is_file(), nombre
        assert original.is_file(), original.as_posix()
        assert runtime.read_bytes()[:8] == FIRMA_PNG
        assert hashlib.sha256(runtime.read_bytes()).hexdigest() == (
            hashlib.sha256(original.read_bytes()).hexdigest()
        )


def test_7_api_tablero_entrega_ambos_recursos():
    respuesta = cliente.get("/api/tablero")
    assert respuesta.status_code == 200
    nodos = {
        n["id"]: n
        for n in respuesta.json()["tablero"]["nodos"]
        if n["tipo"] == "ubicacion"
    }
    assert set(nodos) == set(ids_ubicacion())
    for uid in ids_ubicacion():
        assert nodos[uid]["imagen_tablero"] == IMAGEN_TABLERO_POR_ID[uid]
        assert nodos[uid]["imagen_tarjeta"] == RECURSOS_VISUALES[uid]["principal"]
    for url in list(IMAGEN_TABLERO_POR_ID.values()) + [
        RECURSOS_VISUALES[uid]["principal"] for uid in ids_ubicacion()
    ]:
        assert cliente.get(url).status_code == 200, url


def test_8_manifiesto_recursos_integra_tablero_sin_romper_tarjetas():
    for uid in ids_ubicacion():
        assert RECURSOS_VISUALES[uid]["tablero"] == IMAGEN_TABLERO_POR_ID[uid]
        assert RECURSOS_VISUALES[uid]["principal"].endswith(".jpeg")
    respuesta = cliente.get("/api/recursos")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    for uid in ids_ubicacion():
        assert datos["recursos"][uid]["tablero"] == IMAGEN_TABLERO_POR_ID[uid]
        assert datos["recursos"][uid]["principal"] == (
            RECURSOS_VISUALES[uid]["principal"]
        )


def test_15_topologia_y_16_colores_intactos():
    assert sum(1 for n in TABLERO_VISUAL["nodos"] if n["tipo"] == "ubicacion") == 9
    assert sum(1 for n in TABLERO_VISUAL["nodos"] if n["tipo"] == "casilla") == 48
    assert len(TABLERO_VISUAL["caminos"]) == 16
    assert len(TABLERO_VISUAL["pasadizos"]) == 2
    assert set(TABLERO_VISUAL["colores_personajes"]) == {
        "vera", "bruno", "lucia", "alvaro", "mateo", "eulalia"
    }


def test_17_modo_rapido_no_afectado():
    sala = Sala("JARA-7E-R", modo=MODO_RAPIDO)
    humano = sala.agregar_jugador("R", True, personaje_id="vera")
    sala.estado = ESTADO_INICIADA
    sala.orden_turnos = [humano["id"]]
    sala.manos = {humano["id"]: []}
    privado = sala.estado_privado(humano["id"])
    assert privado["modo"] == MODO_RAPIDO
    assert "imagen_tablero" not in repr(privado)


def test_18_sospecha_inicial_sigue_prohibida():
    sala = Sala("JARA-7E-S", modo=MODO_TABLERO)
    a = sala.agregar_jugador("A", True, personaje_id="vera")
    sala.agregar_jugador("B", personaje_id="bruno")
    sala.estado = ESTADO_INICIADA
    sala.orden_turnos = [j["id"] for j in sala.jugadores]
    sala.turno_actual = 0
    sala.estado_jugada = JUGADA_ESPERANDO_MOVIMIENTO
    for j in sala.jugadores:
        sala.posiciones.asignar(j["id"], POSICIONES_INICIALES[j["personaje_id"]])
    sala.manos = {j["id"]: [] for j in sala.jugadores}
    assert TABLERO.es_ubicacion(sala.posiciones.obtener(a["id"]))
    movimiento = sala.estado_privado(a["id"])["movimiento"]
    assert not movimiento.get("puede_sospechar_aqui", False)
    assert movimiento["puede_tirar"] is True
