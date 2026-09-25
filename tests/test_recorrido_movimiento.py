"""Contrato público del recorrido canónico resuelto por el motor."""

from app.motor.sala import (
    ESTADO_INICIADA,
    JUGADA_ESPERANDO_MOVIMIENTO,
    MODO_TABLERO,
    TIPO_PNJ,
    Sala,
)
from app.motor.tablero import TABLERO


class DadoFijo:
    def __init__(self, valor):
        self.valor = valor

    def randint(self, minimo, maximo):
        assert (minimo, maximo) == (1, 6)
        return self.valor


class RngPNJ:
    def choices(self, opciones, weights, k):
        if opciones and isinstance(opciones[0], str):
            return ["tirar"]
        return [opciones[0]]

    def choice(self, opciones):
        return opciones[0]

    def randint(self, minimo, maximo):
        assert (minimo, maximo) == (1, 6)
        return 4


def sala_humana(origen="parador"):
    sala = Sala("JARA-RECORRIDO", modo=MODO_TABLERO)
    humano = sala.agregar_jugador("Humano", True, personaje_id="vera")
    otro = sala.agregar_jugador("Otro", personaje_id="bruno")
    sala.estado = ESTADO_INICIADA
    sala.orden_turnos = [humano["id"], otro["id"]]
    sala.turno_actual = 0
    sala.estado_jugada = JUGADA_ESPERANDO_MOVIMIENTO
    sala.manos = {humano["id"]: [], otro["id"]: []}
    sala.posiciones.asignar(humano["id"], origen)
    sala.posiciones.asignar(otro["id"], "iglesia-san-agustin")
    return sala, humano, otro


def test_carga_inicial_no_publica_movimiento_inexistente():
    sala, humano, _ = sala_humana()
    assert sala.estado_publico()["movimiento_resuelto"] is None
    assert sala.estado_privado(humano["id"])["movimiento_resuelto"] is None


def test_humano_publica_la_ruta_exacta_que_estaba_pendiente():
    sala, humano, otro = sala_humana()
    sala.tirar_dado_tablero(humano["id"], DadoFijo(4))
    destino = "iglesia-san-agustin"
    recorrido_motor = sala.rutas_pendientes[destino]

    sala.mover(humano["id"], destino)

    contrato = sala.estado_publico()["movimiento_resuelto"]
    assert contrato == {
        "movimiento_id": 1,
        "personaje_id": "vera",
        "origen_id": "parador",
        "destino_id": destino,
        "recorrido": list(recorrido_motor),
        "tipo": "normal",
    }
    assert contrato["recorrido"] == [
        "camino-iglesia-san-agustin-parador-3",
        "camino-iglesia-san-agustin-parador-2",
        "camino-iglesia-san-agustin-parador-1",
        "iglesia-san-agustin",
    ]
    assert contrato["recorrido"][0] != contrato["origen_id"]
    assert contrato["recorrido"][-1] == contrato["destino_id"]
    assert sala.estado_privado(otro["id"])["movimiento_resuelto"] == contrato


def test_redifundir_estado_conserva_identidad_y_no_crea_otro_movimiento():
    sala, humano, _ = sala_humana()
    sala.tirar_dado_tablero(humano["id"], DadoFijo(1))
    destino = next(iter(sala.rutas_pendientes))
    sala.mover(humano["id"], destino)

    primero = sala.estado_publico()["movimiento_resuelto"]
    segundo = sala.estado_publico()["movimiento_resuelto"]
    privado = sala.estado_privado(humano["id"])["movimiento_resuelto"]
    assert primero == segundo == privado
    assert primero["movimiento_id"] == 1


def test_pnj_normal_publica_el_mismo_contrato_canonico():
    sala = Sala("JARA-RECORRIDO-PNJ", modo=MODO_TABLERO)
    pnj = sala.agregar_jugador("Bruno", True, TIPO_PNJ, "bruno")
    humano = sala.agregar_jugador("Humano", personaje_id="vera")
    sala.estado = ESTADO_INICIADA
    sala.orden_turnos = [pnj["id"], humano["id"]]
    sala.turno_actual = 0
    sala.estado_jugada = JUGADA_ESPERANDO_MOVIMIENTO
    sala.manos = {pnj["id"]: [], humano["id"]: []}
    origen = "iglesia-san-agustin"
    sala.posiciones.asignar(pnj["id"], origen)
    sala.posiciones.asignar(humano["id"], "parador")

    sala.ejecutar_turno_pnj(RngPNJ())

    contrato = sala.estado_publico()["movimiento_resuelto"]
    rutas = TABLERO.rutas_legales(origen, 4)
    recorrido_motor = next(
        ruta.posiciones for ruta in rutas if ruta.destino == contrato["destino_id"]
    )
    assert contrato["tipo"] == "normal"
    assert contrato["personaje_id"] == "bruno"
    assert contrato["origen_id"] == origen
    assert contrato["recorrido"] == list(recorrido_motor)
    assert contrato["recorrido"][-1] == contrato["destino_id"]


def test_pasadizo_publica_solo_el_destino_y_su_tipo_real():
    sala, humano, otro = sala_humana("plaza-constitucion")

    destino = sala.usar_pasadizo(humano["id"])

    contrato = sala.estado_publico()["movimiento_resuelto"]
    assert contrato == {
        "movimiento_id": 1,
        "personaje_id": "vera",
        "origen_id": "plaza-constitucion",
        "destino_id": "nuestra-senora-torre",
        "recorrido": ["nuestra-senora-torre"],
        "tipo": "pasadizo",
    }
    assert destino == contrato["destino_id"]
    assert sala.estado_privado(otro["id"])["movimiento_resuelto"] == contrato


def test_contrato_publico_no_mezcla_datos_privados():
    sala, humano, _ = sala_humana()
    sala.tirar_dado_tablero(humano["id"], DadoFijo(1))
    sala.mover(humano["id"], next(iter(sala.rutas_pendientes)))
    contrato = sala.estado_publico()["movimiento_resuelto"]

    assert set(contrato) == {
        "movimiento_id",
        "personaje_id",
        "origen_id",
        "destino_id",
        "recorrido",
        "tipo",
    }
    texto = repr(contrato).lower()
    for privado in ("carta", "mano", "misterio", "investigacion", "secreto"):
        assert privado not in texto
