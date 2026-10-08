"""Fase 2: historial público, persistente en Sala y sin datos privados."""

import json

from app.datos.jarandilla import CARTA_POR_ID
from app.motor.sala import ESTADO_INICIADA, Sala, TIPO_PNJ


SOSPECHA_1 = ("bruno", "parador", "baul-imperial")
SOSPECHA_2 = ("mateo", "picota", "zurron-cuero")


def mesa_humana():
    sala = Sala("JARA-HISTORIAL")
    vera = sala.agregar_jugador("Alicia", True, personaje_id="vera")
    lucia = sala.agregar_jugador("Bea", personaje_id="lucia")
    eulalia = sala.agregar_jugador("Eulalia", tipo=TIPO_PNJ, personaje_id="eulalia")
    sala.estado = ESTADO_INICIADA
    sala.orden_turnos = [vera["id"], lucia["id"], eulalia["id"]]
    sala.turno_actual = 0
    sala.manos = {
        vera["id"]: [],
        lucia["id"]: [CARTA_POR_ID["bruno"]],
        eulalia["id"]: [],
    }
    return sala, vera, lucia, eulalia


def presentar(sala, jugador, sospecha):
    sala.formular_sospecha(jugador["id"], *sospecha)
    assert sala.actualizar_presentacion_sospecha(ahora=float("inf"))


def cerrar_resultado(sala):
    assert sala.actualizar_presentacion_sospecha(ahora=float("inf"))


def test_historial_refutado_es_publico_json_y_no_duplica_por_redifusion():
    sala, vera, lucia, eulalia = mesa_humana()
    presentar(sala, vera, SOSPECHA_1)
    sala.mostrar_carta(lucia["id"], "bruno")

    publico = sala.estado_publico()["historial"]
    assert len(publico) == 1
    entrada = publico[0]
    assert entrada["turno"] == 1
    assert entrada["investigador"] == {
        "personaje_id": "vera",
        "nombre": "Vera, la cronista",
        "tipo": "humano",
    }
    assert entrada["sospecha"]["lugar_id"]["nombre"] == "Parador"
    assert entrada["sospecha"]["objeto_id"]["nombre"] == "Baúl imperial"
    assert entrada["resultado"] == "refutada"
    assert entrada["refutador"]["personaje_id"] == "lucia"

    # Estructura preparada para guardado futuro: solo tipos JSON básicos.
    json.dumps(sala.historial, ensure_ascii=False)

    # Serializar, difundir o reconstruir estados privados nunca registra otra vez.
    for _ in range(4):
        assert len(sala.estado_publico()["historial"]) == 1
        assert sala.estado_privado(vera["id"])["historial"] == publico
        assert sala.estado_privado(lucia["id"])["historial"] == publico
        assert sala.estado_privado(eulalia["id"])["historial"] == publico
    assert len(sala.historial) == 1

    cerrar_resultado(sala)
    assert not sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    assert len(sala.historial) == 1


def test_historial_usa_turnos_reales_y_devuelve_mas_reciente_primero():
    sala, vera, lucia, _ = mesa_humana()
    presentar(sala, vera, SOSPECHA_1)
    sala.mostrar_carta(lucia["id"], "bruno")
    cerrar_resultado(sala)
    assert sala.numero_turno == 2

    # Turno 2, ahora de Lucía, sin ninguna carta capaz de refutar.
    sala.manos = {jugador["id"]: [] for jugador in sala.jugadores}
    presentar(sala, lucia, SOSPECHA_2)

    historial = sala.estado_publico()["historial"]
    assert [entrada["turno"] for entrada in historial] == [2, 1]
    assert [entrada["resultado"] for entrada in historial] == [
        "sin_refutacion",
        "refutada",
    ]
    assert historial[0]["refutador"] is None


def test_turno_pnj_cuenta_y_se_identifica_sin_depender_del_alias():
    sala = Sala("JARA-PNJ")
    humano = sala.agregar_jugador("Nombre de usuario", True, personaje_id="vera")
    sala.completar_con_pnj()
    eulalia = next(j for j in sala.jugadores if j["personaje_id"] == "eulalia")
    sala.estado = ESTADO_INICIADA
    sala.orden_turnos = [humano["id"], eulalia["id"]] + [
        j["id"] for j in sala.jugadores if j["id"] not in {humano["id"], eulalia["id"]}
    ]
    sala.turno_actual = 0
    sala.manos = {jugador["id"]: [] for jugador in sala.jugadores}

    # Termina el turno humano: el PNJ ocupa el turno real número 2.
    sala.avanzar_turno()
    assert sala.jugador_en_turno()["id"] == eulalia["id"]
    presentar(sala, eulalia, SOSPECHA_2)

    entrada = sala.estado_publico()["historial"][0]
    assert entrada["turno"] == 2
    assert entrada["investigador"]["nombre"] == "Eulalia, la pimentonera"
    assert entrada["investigador"]["tipo"] == "pnj"


def test_historial_no_contiene_carta_mostrada_manos_ni_misterio():
    sala, vera, lucia, eulalia = mesa_humana()
    presentar(sala, vera, SOSPECHA_1)
    sala.mostrar_carta(lucia["id"], "bruno")

    texto = repr(sala.estado_publico()["historial"])
    for clave_privada in (
        "carta_id",
        "carta_mostrada",
        "coincidencias",
        "opciones_refutacion",
        "manos",
        "misterio",
        "solucion",
    ):
        assert clave_privada not in texto

    assert sala.estado_privado(vera["id"])["jugada"]["carta_mostrada"]["id"] == "bruno"
    assert "carta_mostrada" not in sala.estado_privado(eulalia["id"])["jugada"]


def test_revancha_limpia_historial_y_reinicia_numero_de_turno():
    sala, vera, lucia, _ = mesa_humana()
    presentar(sala, vera, SOSPECHA_1)
    sala.mostrar_carta(lucia["id"], "bruno")
    sala.estado = "terminada"

    assert sala.volver_al_lobby(vera["id"])
    assert sala.historial == []
    assert sala.numero_turno == 1

