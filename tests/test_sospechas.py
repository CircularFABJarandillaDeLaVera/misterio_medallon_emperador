import pytest

from app.datos.jarandilla import CARTA_POR_ID
from app.motor.sala import (
    ESTADO_INICIADA,
    INV_VISTA,
    JUGADA_ESPERANDO_REFUTADOR,
    Sala,
)


def partida():
    sala = Sala("JARA-TEST")
    jugadores = [sala.agregar_jugador(x, i == 0) for i, x in enumerate(("A", "B", "C"))]
    sala.estado = ESTADO_INICIADA
    sala.orden_turnos = [j["id"] for j in jugadores]
    sala.turno_actual = 0
    sala.manos = {
        jugadores[0]["id"]: [CARTA_POR_ID["eulalia"]],
        jugadores[1]["id"]: [CARTA_POR_ID["bruno"]],
        jugadores[2]["id"]: [CARTA_POR_ID[x] for x in ("vera", "puente-parral", "libro-hueco")],
    }
    return sala, jugadores


def test_solo_turno_y_tres_categorias_validas():
    sala, js = partida()
    with pytest.raises(ValueError):
        sala.formular_sospecha(js[1]["id"], "vera", "puente-parral", "libro-hueco")
    for ids in (("inexistente", "puente-parral", "libro-hueco"),
                ("puente-parral", "vera", "libro-hueco"),
                ("vera", "libro-hueco", "puente-parral")):
        with pytest.raises(ValueError):
            sala.formular_sospecha(js[0]["id"], *ids)


def test_busqueda_siguiente_primero_y_circular_sin_investigador():
    sala, js = partida()
    hallado = sala.buscar_refutador(js[0]["id"], {"vera", "bruno"})
    assert hallado == (js[1]["id"], ["bruno"])
    sala.turno_actual = 2
    hallado = sala.buscar_refutador(js[2]["id"], {"bruno"})
    assert hallado == (js[1]["id"], ["bruno"])
    assert sala.buscar_refutador(js[2]["id"], {"vera"}) is None


def test_una_coincidencia_resuelve_vista_privada_y_avanza_una_vez():
    sala, js = partida()
    sala.formular_sospecha(js[0]["id"], "bruno", "parador", "baul-imperial")
    assert sala.turno_actual == 1
    assert sala.estado_carta(js[0]["id"], "bruno") == INV_VISTA
    assert sala.estado_carta(js[1]["id"], "bruno") != INV_VISTA
    publico = sala.estado_publico()
    assert "carta_id" not in repr(publico)
    assert "carta_mostrada" not in repr(publico["jugada"])
    assert "coincidencias" not in repr(publico["jugada"])
    assert sala.estado_privado(js[0]["id"])["jugada"]["carta_mostrada"]["id"] == "bruno"
    assert "carta_mostrada" not in sala.estado_privado(js[2]["id"])["jugada"]


def test_varias_coincidencias_solo_refutador_recibe_y_elige_opcion():
    sala, js = partida()
    sala.formular_sospecha(js[0]["id"], "vera", "puente-parral", "libro-hueco")
    assert sala.estado_jugada == JUGADA_ESPERANDO_REFUTADOR
    assert sala.turno_actual == 0
    opciones = sala.estado_privado(js[2]["id"])["jugada"]["opciones_refutacion"]
    assert {x["id"] for x in opciones} == {"vera", "puente-parral", "libro-hueco"}
    for j in js[:2]:
        assert "opciones_refutacion" not in sala.estado_privado(j["id"])["jugada"]
    with pytest.raises(ValueError):
        sala.mostrar_carta(js[1]["id"], "vera")
    with pytest.raises(ValueError):
        sala.mostrar_carta(js[2]["id"], "bruno")
    sala.mostrar_carta(js[2]["id"], "vera")
    assert sala.turno_actual == 1
    with pytest.raises(ValueError):
        sala.mostrar_carta(js[2]["id"], "puente-parral")
    assert sala.turno_actual == 1


def test_nadie_refuta_resultado_publico_y_vuelta_circular():
    sala, js = partida()
    sala.turno_actual = 2
    orden = list(sala.orden_turnos)
    sala.formular_sospecha(js[2]["id"], "alvaro", "parador", "baul-imperial")
    assert sala.turno_actual == 0
    assert sala.orden_turnos == orden
    jugada = sala.estado_publico()["jugada"]
    assert jugada["resultado"] == "sin_refutacion"
    assert "coincidencias" not in repr(jugada)


def test_reconexion_reconstruye_solo_lo_necesario_y_vista_gana_a_descarte():
    sala, js = partida()
    sala.descartes[js[0]["id"]].add("vera")
    sala.formular_sospecha(js[0]["id"], "vera", "puente-parral", "libro-hueco")
    assert sala.estado_privado(js[0]["id"])["jugada"]["esperando_resolucion"]
    assert "opciones_refutacion" not in sala.estado_privado(js[1]["id"])["jugada"]
    sala.mostrar_carta(js[2]["id"], "vera")
    assert sala.estado_carta(js[0]["id"], "vera") == INV_VISTA
    assert "carta_mostrada" not in sala.estado_privado(js[1]["id"])["jugada"]
