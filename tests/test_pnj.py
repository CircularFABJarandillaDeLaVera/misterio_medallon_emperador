import random

import pytest

from app.datos.jarandilla import CARTA_POR_ID, SOSPECHOSOS
from app.motor.sala import (


    ESTADO_INICIADA,
    JUGADA_ESPERANDO_REFUTADOR,
    PERFILES_PNJ,
    TIPO_HUMANO,
    TIPO_PNJ,
    Sala,
)

def cerrar_resultado(sala):
    """8B.31C: el turno avanza al cerrarse la presentacion del resultado.

    No-op si no hay resultado publico pendiente: las aserciones intermedias
    siguen viendo el turno sin avanzar.
    """
    presentacion = getattr(sala, "presentacion_sospecha", None)
    if presentacion and presentacion.get("tipo") == "resultado":
        assert sala.actualizar_presentacion_sospecha(ahora=float("inf"))


def iniciar_mesa(num_humanos):
    sala = Sala("JARA-PNJ")
    humanos = [sala.agregar_jugador(f"H{i}", i == 0) for i in range(num_humanos)]
    for jugador, personaje in zip(humanos, SOSPECHOSOS):
        sala.elegir_personaje(jugador["id"], personaje["id"])
    sala.iniciar(humanos[0]["id"])
    return sala, humanos


@pytest.mark.parametrize("humanos,pnj", [(1, 5), (2, 4), (3, 3), (6, 0)])
def test_mesa_fija_seis(humanos, pnj):
    sala, originales = iniciar_mesa(humanos)
    assert len(sala.jugadores) == 6
    assert sum(j["tipo"] == TIPO_PNJ for j in sala.jugadores) == pnj
    assert sum(j["tipo"] == TIPO_HUMANO for j in sala.jugadores) == humanos
    assert len({j["personaje_id"] for j in sala.jugadores}) == 6
    assert len(sala.orden_turnos) == 6
    assert len(set(sala.orden_turnos)) == 6
    assert all(len(sala.manos[j["id"]]) == 3 for j in sala.jugadores)
    assert len(originales) == humanos


def test_no_hay_pnj_en_lobby_y_orden_no_se_resortea():
    sala = Sala("JARA-PNJ")
    humano = sala.agregar_jugador("Paco", True)
    sala.elegir_personaje(humano["id"], "vera")
    assert len(sala.jugadores) == 1
    assert all(j["tipo"] == TIPO_HUMANO for j in sala.jugadores)
    sala.iniciar(humano["id"])
    orden = list(sala.orden_turnos)
    sala.avanzar_turno()
    assert sala.orden_turnos == orden


def test_pnj_puede_ser_primero_y_cadena_avanza_hasta_humano(monkeypatch):
    sala = Sala("JARA-CADENA")
    humano = sala.agregar_jugador("Paco", True)
    sala.elegir_personaje(humano["id"], "vera")
    # completar_con_pnj ocurre antes de sample; colocamos dos PNJ delante.
    monkeypatch.setattr(
        random,
        "sample",
        lambda ids, n: [next(x for x in ids if x == "pnj-bruno"),
                        next(x for x in ids if x == "pnj-lucia"),
                        humano["id"]] + [x for x in ids if x not in {"pnj-bruno", "pnj-lucia", humano["id"]}],
    )
    sala.iniciar(humano["id"])
    assert sala.jugador_en_turno()["tipo"] == TIPO_PNJ
    # Aislamos manos para que ambas sospechas deterministas queden sin refutar.
    sala.manos = {j["id"]: [] for j in sala.jugadores}
    rng = RngPrimero()
    sala.ejecutar_turno_pnj(rng)
    sala.actualizar_presentacion_sospecha(ahora=float("inf"), rng=rng)
    cerrar_resultado(sala)
    assert sala.turno_actual == 1
    sala.ejecutar_turno_pnj(rng)
    sala.actualizar_presentacion_sospecha(ahora=float("inf"), rng=rng)
    cerrar_resultado(sala)
    assert sala.turno_actual == 2
    assert sala.jugador_en_turno()["id"] == humano["id"]


def test_reparto_completo_sin_misterio_duplicados_ni_manos_pnj_publicas():
    sala, _ = iniciar_mesa(2)
    ids = [c["id"] for mano in sala.manos.values() for c in mano]
    secreto = {c["id"] for c in sala.misterio.values()}
    assert len(ids) == 18 == len(set(ids))
    assert not secreto.intersection(ids)
    publico = repr(sala.estado_publico())
    for pnj in (j for j in sala.jugadores if j["tipo"] == TIPO_PNJ):
        assert "mis_cartas" not in publico
        assert "investigacion" not in publico
        assert "vistas" not in publico
        assert "descartes" not in publico


class RngPrimero:
    def __init__(self):
        self.pesos = []

    def choices(self, opciones, weights, k):
        self.pesos.append(list(weights))
        return [opciones[0]]

    def choice(self, opciones):
        return opciones[-1]


def test_motor_ponderado_tres_categorias_solapamiento_y_perfiles():
    sala, _ = iniciar_mesa(1)
    pnj = next(j for j in sala.jugadores if j["tipo"] == TIPO_PNJ)
    propia = sala.manos[pnj["id"]][0]["id"]
    desconocida = next(c["id"] for c in CARTA_POR_ID.values() if c["id"] not in sala.mano_ids(pnj["id"]))
    base = sala.peso_carta_pnj(pnj["id"], desconocida)
    sala.cartas_sospechadas.add(desconocida)
    assert sala.peso_carta_pnj(pnj["id"], desconocida) == base + PERFILES_PNJ[pnj["personaje_id"]]["sospechada"]
    assert sala.peso_carta_pnj(pnj["id"], propia) == PERFILES_PNJ[pnj["personaje_id"]]["conocida"]
    rng = RngPrimero()
    elegida = sala.elegir_sospecha_pnj(pnj["id"], rng)
    assert set(elegida) == {"sospechoso_id", "lugar_id", "objeto_id"}
    assert len(rng.pesos) == 3
    assert PERFILES_PNJ["vera"] != PERFILES_PNJ["bruno"]


def sala_controlada():
    sala = Sala("JARA-CONTROL")
    h = sala.agregar_jugador("Humano", True, personaje_id="vera")
    p1 = sala.agregar_jugador("Bruno", tipo=TIPO_PNJ, personaje_id="bruno")
    p2 = sala.agregar_jugador("Lucia", tipo=TIPO_PNJ, personaje_id="lucia")
    sala.estado = ESTADO_INICIADA
    sala.orden_turnos = [h["id"], p1["id"], p2["id"]]
    sala.manos = {
        h["id"]: [CARTA_POR_ID["vera"], CARTA_POR_ID["parador"]],
        p1["id"]: [CARTA_POR_ID["bruno"], CARTA_POR_ID["puente-parral"]],
        p2["id"]: [CARTA_POR_ID["lucia"], CARTA_POR_ID["libro-hueco"]],
    }
    return sala, h, p1, p2


def test_pnj_refuta_automaticamente_varias_y_solo_investigador_aprende():
    sala, h, p1, p2 = sala_controlada()
    sala.formular_sospecha(h["id"], "bruno", "puente-parral", "baul-imperial", rng=RngPrimero())
    sala.actualizar_presentacion_sospecha(ahora=float("inf"), rng=RngPrimero())
    cerrar_resultado(sala)
    assert sala.turno_actual == 1
    assert "puente-parral" in sala.vistas[h["id"]]
    assert "carta_mostrada" not in sala.estado_privado(p2["id"])["jugada"]
    assert "carta_mostrada" not in repr(sala.estado_publico())


def test_humano_refuta_a_pnj_y_actualiza_vista_del_pnj():
    sala, h, p1, _ = sala_controlada()
    sala.turno_actual = 1
    sala.formular_sospecha(p1["id"], "vera", "parador", "baul-imperial")
    sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    assert sala.estado_jugada == JUGADA_ESPERANDO_REFUTADOR
    opciones = sala.estado_privado(h["id"])["jugada"]["opciones_refutacion"]
    assert {c["id"] for c in opciones} == {"vera", "parador"}
    sala.mostrar_carta(h["id"], "vera")
    assert "vera" in sala.vistas[p1["id"]]
    assert "carta_mostrada" not in sala.estado_privado(h["id"])["jugada"]


def test_pnj_contra_pnj_aprende_sin_filtrar_a_humano():
    sala, h, p1, p2 = sala_controlada()
    sala.turno_actual = 1
    sala.formular_sospecha(p1["id"], "lucia", "parador", "libro-hueco", rng=RngPrimero())
    sala.actualizar_presentacion_sospecha(ahora=float("inf"), rng=RngPrimero())
    assert "libro-hueco" in sala.vistas[p1["id"]]
    privado_h = repr(sala.estado_privado(h["id"]))
    assert "carta_mostrada" not in privado_h
    assert "opciones_refutacion" not in privado_h


def test_seleccion_aleatoria_puede_elegir_conocida_y_desconocida():
    sala, _ = iniciar_mesa(1)
    pnj = next(j for j in sala.jugadores if j["tipo"] == TIPO_PNJ)
    categoria = "sospechoso"
    conocidas = [c for c in sala.manos[pnj["id"]] if c["categoria"] == categoria]
    # La propiedad importante es que ninguna alternativa recibe peso cero.
    assert all(sala.peso_carta_pnj(pnj["id"], c["id"]) > 0 for c in SOSPECHOSOS)
    if conocidas:
        assert sala.peso_carta_pnj(pnj["id"], conocidas[0]["id"]) > 0
    desconocidas = [c for c in SOSPECHOSOS if c["id"] not in sala.mano_ids(pnj["id"])]
    assert desconocidas and sala.peso_carta_pnj(pnj["id"], desconocidas[0]["id"]) > 0
