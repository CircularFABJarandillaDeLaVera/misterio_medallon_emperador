"""Piezas físicas de objetos: estado público independiente de las cartas."""

import copy

import pytest

from app.datos.jarandilla import CARTA_POR_ID, OBJETOS
from app.motor.sala import (
    JUGADA_ESPERANDO_SOSPECHA,
    MODO_RAPIDO,
    MODO_TABLERO,
    TIPO_PNJ,
    Sala,
)
from app.motor.tablero import TABLERO


def partida_tablero():
    sala = Sala("JARA-OBJETOS", modo=MODO_TABLERO)
    humano = sala.agregar_jugador("Humano", True, personaje_id="vera")
    sala.iniciar(humano["id"])
    sala.orden_turnos = [humano["id"]] + [
        jugador["id"] for jugador in sala.jugadores if jugador["id"] != humano["id"]
    ]
    sala.turno_actual = 0
    return sala, humano


def preparar_sospecha(sala, jugador, lugar="parador"):
    sala.turno_actual = sala.orden_turnos.index(jugador["id"])
    sala.posiciones.asignar(jugador["id"], lugar)
    sala.estado_jugada = JUGADA_ESPERANDO_SOSPECHA


def test_inicio_distribuye_los_seis_objetos_en_seis_ubicaciones():
    sala, _ = partida_tablero()
    posiciones = sala.posiciones_objetos
    ids_objetos = {objeto["id"] for objeto in OBJETOS}

    assert set(posiciones) == ids_objetos
    assert len(posiciones) == len(set(posiciones.values())) == 6
    assert set(posiciones.values()) <= set(TABLERO.ubicaciones)
    assert len(set(TABLERO.ubicaciones) - set(posiciones.values())) == 3
    assert all(TABLERO.es_ubicacion(posicion) for posicion in posiciones.values())


def test_piezas_son_independientes_de_reparto_y_misterio():
    sala, _ = partida_tablero()
    secreto_antes = copy.deepcopy(sala.misterio)
    manos_antes = copy.deepcopy(sala.manos)
    objeto_secreto = sala.misterio["objeto"]["id"]

    assert objeto_secreto in sala.posiciones_objetos
    sala.posiciones_objetos[objeto_secreto] = "picota"
    assert sala.misterio == secreto_antes
    assert sala.manos == manos_antes
    assert sum(len(mano) for mano in sala.manos.values()) == 18


def test_sospecha_humana_mueve_solo_el_objeto_elegido():
    sala, humano = partida_tablero()
    preparar_sospecha(sala, humano)
    sala.manos = {jugador["id"]: [] for jugador in sala.jugadores}
    antes = dict(sala.posiciones_objetos)

    sala.formular_sospecha(humano["id"], "bruno", "parador", "cantaro-barro")

    assert sala.posiciones_objetos["cantaro-barro"] == "parador"
    assert {
        objeto: posicion for objeto, posicion in sala.posiciones_objetos.items()
        if objeto != "cantaro-barro"
    } == {objeto: posicion for objeto, posicion in antes.items() if objeto != "cantaro-barro"}


def test_objeto_se_mueve_aunque_la_sospecha_sea_refutada():
    sala, humano = partida_tablero()
    preparar_sospecha(sala, humano, "picota")
    refutador = sala.jugador_por_id(sala.orden_turnos[1])
    sala.manos = {jugador["id"]: [] for jugador in sala.jugadores}
    sala.manos[refutador["id"]] = [CARTA_POR_ID["baul-imperial"]]

    sala.formular_sospecha(humano["id"], "bruno", "picota", "baul-imperial")

    assert sala.ultima_jugada["resultado"] == "refutada"
    assert sala.posiciones_objetos["baul-imperial"] == "picota"


def test_objeto_se_mueve_si_nadie_refuta_y_persiste_tras_turnos():
    sala, humano = partida_tablero()
    preparar_sospecha(sala, humano, "ermita-sopetran")
    sala.manos = {jugador["id"]: [] for jugador in sala.jugadores}

    sala.formular_sospecha(humano["id"], "bruno", "ermita-sopetran", "libro-hueco")
    assert sala.ultima_jugada["resultado"] == "sin_refutacion"
    assert sala.posiciones_objetos["libro-hueco"] == "ermita-sopetran"
    sala.avanzar_turno()
    assert sala.estado_publico()["posiciones_objetos"]["libro-hueco"] == "ermita-sopetran"
    assert sala.estado_privado(humano["id"])["posiciones_objetos"]["libro-hueco"] == "ermita-sopetran"


def test_objetos_pueden_acumularse_sin_redistribuirse():
    sala, humano = partida_tablero()
    preparar_sospecha(sala, humano)
    sala.manos = {jugador["id"]: [] for jugador in sala.jugadores}
    sala.posiciones_objetos["baul-imperial"] = "parador"
    sala.posiciones_objetos["libro-hueco"] = "parador"
    sala.posiciones_objetos["cantaro-barro"] = "picota"
    antes = dict(sala.posiciones_objetos)
    acumulados_antes = sum(
        posicion == "parador" for posicion in sala.posiciones_objetos.values()
    )

    sala.formular_sospecha(humano["id"], "bruno", "parador", "cantaro-barro")

    assert sum(
        posicion == "parador" for posicion in sala.posiciones_objetos.values()
    ) == acumulados_antes + 1
    assert sala.posiciones_objetos["baul-imperial"] == antes["baul-imperial"]
    assert sala.posiciones_objetos["libro-hueco"] == antes["libro-hueco"]


def test_sospecha_invalida_no_mueve_objetos():
    sala, humano = partida_tablero()
    preparar_sospecha(sala, humano, "parador")
    antes = dict(sala.posiciones_objetos)

    with pytest.raises(ValueError, match="ubicación actual"):
        sala.formular_sospecha(humano["id"], "bruno", "picota", "cantaro-barro")

    assert sala.posiciones_objetos == antes


def test_sospecha_valida_de_pnj_mueve_el_objeto_sin_mover_sospechoso():
    sala, _ = partida_tablero()
    pnj = next(jugador for jugador in sala.jugadores if jugador["tipo"] == TIPO_PNJ)
    preparar_sospecha(sala, pnj, "puente-parral")
    sala.manos = {jugador["id"]: [] for jugador in sala.jugadores}
    posiciones_personajes = {
        jugador["id"]: sala.posiciones.obtener(jugador["id"])
        for jugador in sala.jugadores
    }

    sala.formular_sospecha(pnj["id"], "eulalia", "puente-parral", "saco-pimenton")

    assert sala.posiciones_objetos["saco-pimenton"] == "puente-parral"
    assert {
        jugador["id"]: sala.posiciones.obtener(jugador["id"])
        for jugador in sala.jugadores
    } == posiciones_personajes


def test_pnj_no_usa_posiciones_fisicas_como_conocimiento():
    class RngPrimero:
        def __init__(self):
            self.pesos = []

        def choices(self, opciones, weights, k):
            self.pesos.append(tuple(weights))
            return [opciones[0]]

    sala, _ = partida_tablero()
    pnj = next(jugador for jugador in sala.jugadores if jugador["tipo"] == TIPO_PNJ)
    primer_rng = RngPrimero()
    primera = sala.elegir_sospecha_pnj(pnj["id"], rng=primer_rng)
    sala.posiciones_objetos = {
        objeto["id"]: "parador" for objeto in OBJETOS
    }
    segundo_rng = RngPrimero()
    segunda = sala.elegir_sospecha_pnj(pnj["id"], rng=segundo_rng)

    assert segunda == primera
    assert segundo_rng.pesos == primer_rng.pesos


def test_estado_publico_expone_solo_posiciones_fisicas_y_rapido_las_omite():
    sala, humano = partida_tablero()
    publico = sala.estado_publico()
    privado = sala.estado_privado(humano["id"])

    assert publico["posiciones_objetos"] == sala.posiciones_objetos
    assert privado["posiciones_objetos"] == sala.posiciones_objetos
    assert len(publico["posiciones_objetos"]) == 6
    assert "misterio" not in publico and "manos" not in publico and "mis_cartas" not in publico
    assert "carta_mostrada" not in publico["jugada"]

    rapida = Sala("JARA-RAPIDA", modo=MODO_RAPIDO)
    anfitrion = rapida.agregar_jugador("Humano", True, personaje_id="vera")
    rapida.iniciar(anfitrion["id"])
    assert rapida.posiciones_objetos == {}
    assert "posiciones_objetos" not in rapida.estado_publico()
