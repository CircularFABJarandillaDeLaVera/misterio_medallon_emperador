import copy

import pytest

from app.datos.jarandilla import CARTAS, CARTA_POR_ID
from app.motor.sala import (
    ESTADO_INICIADA,
    ESTADO_TERMINADA,
    INV_VISTA,
    TIPO_PNJ,
    Sala,
)


SOLUCION = {"sospechoso": CARTA_POR_ID["vera"], "lugar": CARTA_POR_ID["parador"], "objeto": CARTA_POR_ID["baul-imperial"]}


def sala_controlada():
    sala = Sala("JARA-FINAL")
    a = sala.agregar_jugador("A", True, personaje_id="vera")
    b = sala.agregar_jugador("B", personaje_id="bruno")
    c = sala.agregar_jugador("C", tipo=TIPO_PNJ, personaje_id="lucia")
    sala.estado = ESTADO_INICIADA
    sala.orden_turnos = [a["id"], b["id"], c["id"]]
    sala.turno_actual = 0
    sala.misterio = copy.deepcopy(SOLUCION)
    sala.manos = {
        a["id"]: [CARTA_POR_ID["eulalia"]],
        b["id"]: [CARTA_POR_ID["bruno"], CARTA_POR_ID["puente-parral"]],
        c["id"]: [CARTA_POR_ID["lucia"], CARTA_POR_ID["libro-hueco"]],
    }
    return sala, a, b, c


def acusar(sala, jugador, sospechoso="vera", lugar="parador", objeto="baul-imperial"):
    return sala.resolver_misterio(jugador["id"], sospechoso, lugar, objeto)


def test_humano_resuelve_y_solucion_solo_aparece_despues_del_final():
    sala, a, _, _ = sala_controlada()
    assert "solucion" not in sala.estado_publico()
    assert "baul-imperial" not in repr(sala.estado_publico())
    assert acusar(sala, a) is True
    publico = sala.estado_publico()
    assert sala.estado == ESTADO_TERMINADA
    assert publico["resultado_final"] == "resuelto"
    assert publico["ganador_alias"] == "A"
    assert publico["solucion"]["objeto"]["id"] == "baul-imperial"
    assert sala.jugador_en_turno() is None


def test_fallo_elimina_sin_revelar_partes_y_salta_turno():
    sala, a, b, c = sala_controlada()
    assert acusar(sala, a, sospechoso="bruno") is False
    assert not a["activo_investigacion"]
    assert sala.jugador_en_turno()["id"] == b["id"]
    texto = repr(sala.estado_publico())
    assert "solucion" not in texto
    assert "aciertos" not in texto and "fallos" not in texto
    assert c["activo_investigacion"]


def test_eliminado_humano_y_pnj_siguen_refutando():
    sala, a, b, c = sala_controlada()
    a["activo_investigacion"] = False
    c["activo_investigacion"] = False
    hallado = sala.buscar_refutador(b["id"], {"libro-hueco"})
    assert hallado == (c["id"], ["libro-hueco"])
    sala.turno_actual = 2
    hallado = sala.buscar_refutador(c["id"], {"eulalia"})
    assert hallado == (a["id"], ["eulalia"])


def test_humano_que_falla_conserva_mano_y_refuta_despues_con_una_coincidencia():
    sala, a, b, _ = sala_controlada()
    mano = copy.deepcopy(sala.manos[a["id"]])

    assert acusar(sala, a, sospechoso="bruno") is False
    assert not a["activo_investigacion"]
    assert sala.manos[a["id"]] == mano

    sala.formular_sospecha(b["id"], "eulalia", "picota", "baul-imperial")
    assert sala.ultima_jugada["refutador_id"] == a["id"]
    assert sala.ultima_jugada["carta_id"] == "eulalia"
    assert sala.estado_privado(b["id"])["jugada"]["carta_mostrada"]["id"] == "eulalia"
    assert "carta_mostrada" not in sala.estado_privado(a["id"])["jugada"]
    assert "carta_mostrada" not in sala.estado_publico()["jugada"]


def test_humano_que_falla_conserva_eleccion_privada_si_puede_refutar_varias():
    sala, a, b, c = sala_controlada()
    sala.manos[a["id"]] = [CARTA_POR_ID["eulalia"], CARTA_POR_ID["picota"]]

    assert acusar(sala, a, sospechoso="bruno") is False
    sala.formular_sospecha(b["id"], "eulalia", "picota", "baul-imperial")

    privada_a = sala.estado_privado(a["id"])["jugada"]
    assert {carta["id"] for carta in privada_a["opciones_refutacion"]} == {
        "eulalia", "picota"
    }
    assert "opciones_refutacion" not in sala.estado_privado(b["id"])["jugada"]
    assert "opciones_refutacion" not in sala.estado_privado(c["id"])["jugada"]

    sala.mostrar_carta(a["id"], "picota")
    assert sala.estado_privado(b["id"])["jugada"]["carta_mostrada"]["id"] == "picota"
    assert "carta_mostrada" not in sala.estado_privado(c["id"])["jugada"]
    assert "carta_mostrada" not in sala.estado_publico()["jugada"]
    assert "opciones_refutacion" not in sala.estado_publico()["jugada"]


def test_ultimo_no_gana_automaticamente_y_si_falla_queda_sin_resolver():
    sala, a, b, c = sala_controlada()
    b["activo_investigacion"] = False
    c["activo_investigacion"] = False
    assert sala.estado == ESTADO_INICIADA
    assert sala.investigadores_activos() == [a]
    acusar(sala, a, sospechoso="bruno")
    assert sala.estado == ESTADO_TERMINADA
    assert sala.resultado_final == "sin_resolver"
    assert sala.ganador_id is None
    assert sala.estado_publico()["solucion"] is not None


def test_doble_resolver_y_acciones_despues_del_final_no_transicionan():
    sala, a, _, _ = sala_controlada()
    acusar(sala, a)
    ultima = copy.deepcopy(sala.ultima_jugada)
    with pytest.raises(ValueError):
        acusar(sala, a)
    with pytest.raises(ValueError):
        sala.formular_sospecha(a["id"], "vera", "parador", "baul-imperial")
    assert sala.ultima_jugada == ultima


def test_pnj_deduce_sospecha_propia_no_refutada_y_acusa_despues():
    sala, _, _, pnj = sala_controlada()
    sala.turno_actual = 2
    sala.manos = {j["id"]: [] for j in sala.jugadores}
    sala.formular_sospecha(pnj["id"], "vera", "parador", "baul-imperial")
    assert sala.soluciones_deducidas[pnj["id"]] == {
        "sospechoso_id": "vera", "lugar_id": "parador", "objeto_id": "baul-imperial"
    }
    sala.turno_actual = 2
    sala.ejecutar_turno_pnj()
    assert sala.estado == ESTADO_TERMINADA
    assert sala.ganador_id == pnj["id"]


def test_pnj_no_aprende_de_sospecha_ajena_no_refutada():
    sala, a, _, pnj = sala_controlada()
    sala.manos = {j["id"]: [] for j in sala.jugadores}
    sala.formular_sospecha(a["id"], "vera", "parador", "baul-imperial")
    assert pnj["id"] not in sala.soluciones_deducidas


def test_deduccion_general_usa_solo_la_tengo_y_vista():
    sala, _, _, pnj = sala_controlada()
    candidatas = {"vera", "parador", "baul-imperial"}
    conocidas = {c["id"] for c in CARTAS} - candidatas
    sala.manos[pnj["id"]] = []
    sala.vistas[pnj["id"]] = conocidas
    assert sala.deducir_solucion_pnj(pnj["id"]) == {
        "sospechoso_id": "vera", "lugar_id": "parador", "objeto_id": "baul-imperial"
    }
    assert all(sala.estado_carta(pnj["id"], cid) == INV_VISTA for cid in conocidas)


def test_trampa_mismo_conocimiento_misterios_distintos_misma_decision():
    sala1, _, _, p1 = sala_controlada()
    sala2, _, _, p2 = sala_controlada()
    conocidas = {c["id"] for c in CARTAS} - {"vera", "parador", "baul-imperial"}
    for sala, pnj in ((sala1, p1), (sala2, p2)):
        sala.manos[pnj["id"]] = []
        sala.vistas[pnj["id"]] = set(conocidas)
    sala2.misterio = {
        "sospechoso": CARTA_POR_ID["bruno"],
        "lugar": CARTA_POR_ID["picota"],
        "objeto": CARTA_POR_ID["libro-hueco"],
    }
    assert sala1.deducir_solucion_pnj(p1["id"]) == sala2.deducir_solucion_pnj(p2["id"])


def test_estado_privado_reconexion_conserva_eliminacion_y_final():
    sala, a, _, _ = sala_controlada()
    acusar(sala, a, sospechoso="bruno")
    privado = sala.estado_privado(a["id"])
    assert not privado["activo_investigacion"]
    assert "solucion" not in privado
    # Una sala terminada reconstruye solución y resultado para cualquier conexión.
    sala.estado = ESTADO_TERMINADA
    sala.resultado_final = "sin_resolver"
    privado = sala.estado_privado(a["id"])
    assert privado["solucion"]["sospechoso"]["id"] == "vera"
    assert "soluciones_deducidas" not in repr(privado)


def test_acusacion_fuera_de_turno_categoria_cruzada_y_eliminado_rechazadas():
    sala, a, b, _ = sala_controlada()
    with pytest.raises(ValueError):
        acusar(sala, b)
    with pytest.raises(ValueError):
        acusar(sala, a, sospechoso="parador")
    a["activo_investigacion"] = False
    with pytest.raises(ValueError):
        acusar(sala, a)


def test_pnj_sin_deduccion_suficiente_sigue_formulando_sospecha():
    sala, _, _, pnj = sala_controlada()
    sala.turno_actual = 2

    class Primero:
        def choices(self, opciones, weights, k):
            return [opciones[0]]

        def choice(self, opciones):
            return opciones[0]

    assert sala.deducir_solucion_pnj(pnj["id"]) is None
    sala.ejecutar_turno_pnj(rng=Primero())
    assert sala.estado == ESTADO_INICIADA
    assert sala.ultima_jugada["resultado"] in {"refutada", "sin_refutacion"}


def test_pnj_falla_se_elimina_pero_conserva_mano_y_refuta():
    sala, a, _, pnj = sala_controlada()
    sala.turno_actual = 2
    mano = list(sala.manos[pnj["id"]])
    sala.soluciones_deducidas[pnj["id"]] = {
        "sospechoso_id": "bruno", "lugar_id": "picota", "objeto_id": "libro-hueco"
    }
    sala.ejecutar_turno_pnj()
    assert not pnj["activo_investigacion"]
    assert sala.manos[pnj["id"]] == mano
    assert sala.buscar_refutador(a["id"], {"libro-hueco"}) == (
        pnj["id"], ["libro-hueco"]
    )


def test_no_se_programa_cadena_automatica_tras_final():
    from app import main

    sala, a, _, _ = sala_controlada()
    main.gestor.salas[sala.codigo] = sala
    acusar(sala, a)
    main.tareas_pnj.pop(sala.codigo, None)
    main.programar_turno_pnj(sala.codigo)
    assert sala.codigo not in main.tareas_pnj
    main.gestor.salas.pop(sala.codigo, None)
