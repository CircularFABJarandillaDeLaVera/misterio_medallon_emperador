"""8B.32 · Antibloqueo por inactividad de un humano.

El plazo de 60 s es canónico del servidor y SOLO existe mientras la partida
está bloqueada esperando una acción obligatoria de un humano concreto
(esperando_movimiento / esperando_destino / esperando_sospecha). Ni el popup
ni el reloj del navegador tienen autoridad: al vencer el plazo, el servidor
solo ofrece al ANFITRIÓN convertir ese mismo asiento en PNJ o seguir
esperando. Nunca ejecuta por su cuenta la acción pendiente.
"""
import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from app import main
from app.datos.jarandilla import CARTA_POR_ID
from app.motor.sala import (
    ESTADO_INICIADA,
    ESTADO_TERMINADA,
    INACTIVIDAD_BLOQUEO_SEGUNDOS,
    JUGADA_ESPERANDO_DESTINO,
    JUGADA_ESPERANDO_MOVIMIENTO,
    JUGADA_ESPERANDO_REFUTADOR,
    JUGADA_ESPERANDO_SOSPECHA,
    JUGADA_PRESENTANDO_SOSPECHA,
    MODO_RAPIDO,
    MODO_TABLERO,
    POSICIONES_INICIALES,
    TIPO_HUMANO,
    TIPO_PNJ,
    Sala,
)
from app.motor.tablero import TABLERO

CODIGO = "JARA-8B32"


class DadoFijo:
    def __init__(self, valor):
        self.valor = valor

    def randint(self, minimo, maximo):
        return self.valor


class RngPrimero:
    """Primera opción siempre: recorrido determinista de la lógica PNJ."""

    def choice(self, opciones):
        return opciones[0]

    def choices(self, opciones, weights=None, k=1):
        return [opciones[0]] * k

    def randint(self, minimo, maximo):
        return 1


def sala_antibloqueo(modo=MODO_TABLERO):
    """Anfitrión humano + humano que bloquea + un PNJ, partida ya iniciada.

    El turno es SIEMPRE del humano que bloquea: es el único caso en el que
    el motor puede quedarse esperando a una acción obligatoria.
    """
    sala = Sala(CODIGO, modo=modo)
    anfitrion = sala.agregar_jugador("Anfitriona", True, personaje_id="vera")
    bloqueante = sala.agregar_jugador("Bruno", personaje_id="bruno")
    pnj = sala.agregar_jugador("Lucía", tipo=TIPO_PNJ, personaje_id="lucia")
    sala.estado = ESTADO_INICIADA
    sala.misterio = {
        "sospechoso": dict(CARTA_POR_ID["mateo"]),
        "lugar": dict(CARTA_POR_ID["parador"]),
        "objeto": dict(CARTA_POR_ID["baul-imperial"]),
    }
    sala.orden_turnos = [bloqueante["id"], pnj["id"], anfitrion["id"]]
    sala.turno_actual = 0
    sala.estado_jugada = (
        JUGADA_ESPERANDO_MOVIMIENTO if modo == MODO_TABLERO else JUGADA_ESPERANDO_SOSPECHA
    )
    sala.manos = {
        bloqueante["id"]: [
            dict(CARTA_POR_ID["cantaro-barro"]),
            dict(CARTA_POR_ID["zurron-cuero"]),
        ],
        pnj["id"]: [dict(CARTA_POR_ID["lucia"])],
        anfitrion["id"]: [dict(CARTA_POR_ID["vera"])],
    }
    for jugador in sala.jugadores:
        if modo == MODO_TABLERO:
            sala.posiciones.asignar(
                jugador["id"], POSICIONES_INICIALES[jugador["personaje_id"]]
            )
    sala.posiciones_objetos = {"baul-imperial": "parador", "libro-hueco": "picota"}
    sala.vistas[bloqueante["id"]].add("cristo-humilladero")
    sala.descartes[bloqueante["id"]].add("plaza-constitucion")
    sala.marcar_bloqueo()
    return sala, anfitrion, bloqueante, pnj


def vencida(sala, segundos=INACTIVIDAD_BLOQUEO_SEGUNDOS + 1):
    """Vence el plazo canónico sin esperar en reloj real."""
    sala.bloqueo_deadline = time.monotonic() - segundos
    return sala


def tiro_que_entra_en_ubicacion(origen):
    """Primera tirada (1-6) cuya ruta legal acaba en una ubicación."""
    for puntos in range(1, 7):
        destinos = TABLERO.destinos_alcanzables(origen, puntos)
        if any(TABLERO.es_ubicacion(destino) for destino in destinos):
            return puntos
    raise AssertionError("Ninguna tirada llega a una ubicación desde ese origen.")


def aviso_de(sala, jugador_id):
    return sala.estado_privado(jugador_id).get("inactividad")


# --------------------------------------------------------------------------
# A, B, D, E, F, G · El plazo y el aviso son canónicos del servidor
# --------------------------------------------------------------------------

def test_a_59_segundos_no_hay_aviso():
    sala, anfitrion, bloqueante, _ = sala_antibloqueo()
    # El plazo sigue dentro del minuto que acaba de empezar.
    assert 0 < sala.bloqueo_deadline - time.monotonic() <= INACTIVIDAD_BLOQUEO_SEGUNDOS
    assert sala.registrar_aviso_inactividad() is False
    assert aviso_de(sala, anfitrion["id"]) is None
    assert sala.bloqueo_jugador_id == bloqueante["id"]
    assert sala.bloqueo_accion == "tirar_dado"


def test_b_a_60_segundos_aviso_privado_al_anfitrion():
    sala, anfitrion, bloqueante, _ = sala_antibloqueo()
    vencida(sala)
    assert sala.registrar_aviso_inactividad() is True
    aviso = aviso_de(sala, anfitrion["id"])
    assert aviso == {"aviso_id": sala.bloqueo_aviso_id, "alias": "Bruno"}
    # El aviso es único por periodo de espera.
    assert sala.registrar_aviso_inactividad() is False


def test_c_otro_humano_no_recibe_el_aviso_ni_puede_convertir():
    sala, _, bloqueante, _ = sala_antibloqueo()
    otro = sala.agregar_jugador("Carla", personaje_id="mateo")
    vencida(sala)
    sala.registrar_aviso_inactividad()
    # Ni el aviso privado ni capacidad de decisión para un humano que no es anfitrión.
    assert aviso_de(sala, otro["id"]) is None
    with pytest.raises(ValueError):
        sala.seguir_esperando(otro["id"], sala.bloqueo_aviso_id)
    with pytest.raises(ValueError):
        sala.convertir_en_pnj(otro["id"], sala.bloqueo_aviso_id)
    assert sala.jugador_por_id(bloqueante["id"])["tipo"] == TIPO_HUMANO


def test_d_anfitrion_bloqueado_no_genera_aviso_ni_intervencion():
    sala, anfitrion, _, _ = sala_antibloqueo()
    sala.orden_turnos = [anfitrion["id"], sala.orden_turnos[1], sala.orden_turnos[2]]
    sala.turno_actual = 0
    sala.marcar_bloqueo()
    vencida(sala)
    # Vencido y sin ninguna acción del anfitrión: no hay aviso.
    assert sala.registrar_aviso_inactividad() is False
    assert aviso_de(sala, anfitrion["id"]) is None
    # Y nadie más puede intervenir por él.
    with pytest.raises(ValueError):
        sala.convertir_en_pnj(anfitrion["id"], sala.bloqueo_aviso_id)
    assert sala.jugador_por_id(anfitrion["id"])["tipo"] == TIPO_HUMANO
    # El bloqueo sigue vivo: la partida continúa esperando al anfitrión.
    assert sala.jugador_bloqueante()["id"] == anfitrion["id"]


def test_e_seguir_esperando_mantiene_humano_y_renueva_otros_60_segundos():
    sala, anfitrion, bloqueante, _ = sala_antibloqueo()
    vencida(sala)
    sala.registrar_aviso_inactividad()
    aviso_viejo = sala.bloqueo_aviso_id
    estado_previo = (
        sala.estado_jugada,
        sala.tirada_pendiente,
        dict(sala.rutas_pendientes),
        sala.turno_actual,
    )
    sala.seguir_esperando(anfitrion["id"], aviso_viejo)
    # Sigue siendo humano y no cambia nada de la partida.
    assert sala.jugador_por_id(bloqueante["id"])["tipo"] == TIPO_HUMANO
    assert (
        sala.estado_jugada,
        sala.tirada_pendiente,
        dict(sala.rutas_pendientes),
        sala.turno_actual,
    ) == estado_previo
    # Nuevo plazo completo y aviso nuevo: durante el nuevo minuto no hay popup.
    restante = sala.bloqueo_deadline - time.monotonic()
    assert 0 < restante <= INACTIVIDAD_BLOQUEO_SEGUNDOS
    assert sala.bloqueo_aviso_id > aviso_viejo
    assert sala.bloqueo_aviso_emitido is False
    assert aviso_de(sala, anfitrion["id"]) is None
    # Al completarse el nuevo minuto se emite UN aviso nuevo.
    vencida(sala)
    assert sala.registrar_aviso_inactividad() is True
    assert aviso_de(sala, anfitrion["id"])["aviso_id"] == sala.bloqueo_aviso_id
    assert aviso_de(sala, anfitrion["id"])["aviso_id"] != aviso_viejo


def test_f_accion_valida_antes_del_plazo_cancela_el_bloqueo():
    sala, anfitrion, bloqueante, _ = sala_antibloqueo()
    tirada = tiro_que_entra_en_ubicacion(POSICIONES_INICIALES["bruno"])
    sala.tirar_dado_tablero(bloqueante["id"], rng=DadoFijo(tirada))
    # Tirar cambia la acción bloqueante: plazo nuevo, acción "elegir_destino".
    assert sala.bloqueo_accion == "elegir_destino"
    assert sala.estado_jugada == JUGADA_ESPERANDO_DESTINO
    vencida(sala)
    plazo_viejo = sala.bloqueo_deadline
    destino = next(iter(sala.rutas_pendientes))
    sala.mover(bloqueante["id"], destino)
    # Moverse antes de tiempo cancela el bloqueo de "elegir_destino": ese plazo
    # ya no puede abrir ningún aviso y no vuelve a spreadirlo.
    assert sala.estado_jugada == JUGADA_ESPERANDO_SOSPECHA
    assert sala.bloqueo_accion == "formular_sospecha"
    assert sala.bloqueo_deadline != plazo_viejo
    assert aviso_de(sala, anfitrion["id"]) is None
    assert sala.registrar_aviso_inactividad() is False
    # Y el bloqueo nuevo es el de la sospecha, con su minuto entero.
    assert 0 < sala.bloqueo_deadline - time.monotonic() <= INACTIVIDAD_BLOQUEO_SEGUNDOS


def test_f_accion_valida_que_pasa_el_turno_deja_la_partida_sin_bloqueo():
    sala, anfitrion, bloqueante, _ = sala_antibloqueo()
    sala.tirar_dado_tablero(bloqueante["id"], rng=DadoFijo(2))
    vencida(sala)
    # Con 2 puntos solo hay casillas de camino: el turno pasa al PNJ siguiente.
    casilla = next(
        destino
        for destino in sala.rutas_pendientes
        if not TABLERO.es_ubicacion(destino)
    )
    sala.mover(bloqueante["id"], casilla)
    sala.marcar_bloqueo()
    assert sala.jugador_en_turno()["id"] != bloqueante["id"]
    assert sala.bloqueo_deadline is None
    assert sala.bloqueo_jugador_id is None
    assert sala.registrar_aviso_inactividad() is False
    assert aviso_de(sala, anfitrion["id"]) is None
    with pytest.raises(ValueError):
        sala.convertir_en_pnj(anfitrion["id"], sala.bloqueo_aviso_id)


def test_g_recarga_no_reinicia_el_plazo_ni_el_minuto():
    sala, anfitrion, bloqueante, _ = sala_antibloqueo()
    momento = time.monotonic()
    # Un minuto canónico ya empezado: solo quedan 30 s.
    sala.bloqueo_deadline = momento + 30
    # Recargar, reconectar o redifundir NO vuelve a marcar el bloqueo.
    for _ in range(3):
        sala.marcar_bloqueo()
    assert sala.bloqueo_deadline == momento + 30
    assert aviso_de(sala, anfitrion["id"]) is None
    # Solo quedan 30 s: no hay aviso antes de tiempo ni al minuto completo.
    assert sala.registrar_aviso_inactividad(ahora=momento + 29) is False
    assert sala.registrar_aviso_inactividad(ahora=momento + 30) is True


# --------------------------------------------------------------------------
# H, I, J, K, L, M · La conversión conserva el mismo asiento
# --------------------------------------------------------------------------

def test_h_i_j_k_l_m_la_conversion_conserva_el_asiento_entero():
    sala, anfitrion, bloqueante, pnj = sala_antibloqueo()
    vencida(sala)
    sala.registrar_aviso_inactividad()
    antes = {
        "id": bloqueante["id"],
        "personaje_id": bloqueante["personaje_id"],
        "alias": bloqueante["alias"],
        "mano": [c["id"] for c in sala.manos[bloqueante["id"]]],
        "vistas": set(sala.vistas[bloqueante["id"]]),
        "descartes": set(sala.descartes[bloqueante["id"]]),
        "posicion": sala.posiciones.obtener(bloqueante["id"]),
        "orden": list(sala.orden_turnos),
        "turno_actual": sala.turno_actual,
        "activo": bloqueante["activo_investigacion"],
        "misterio": {k: v["id"] for k, v in sala.misterio.items()},
        "objetos": dict(sala.posiciones_objetos),
        "ids": [j["id"] for j in sala.jugadores],
    }
    convertido = sala.convertir_en_pnj(anfitrion["id"], sala.bloqueo_aviso_id)
    # H: mismo asiento, mismo jugador_id (no pnj-<personaje>), mismo personaje.
    assert convertido["id"] == antes["id"]
    assert not convertido["id"].startswith("pnj-")
    assert convertido["tipo"] == TIPO_PNJ
    assert convertido["personaje_id"] == antes["personaje_id"]
    assert convertido["alias"] == antes["alias"]
    # I: la mano sigue intacta y con el mismo contenido.
    assert [c["id"] for c in sala.manos[antes["id"]]] == antes["mano"]
    # J: ni la posición ni el turno se tocan.
    assert sala.posiciones.obtener(antes["id"]) == antes["posicion"]
    assert sala.turno_actual == antes["turno_actual"]
    # K: el orden de turnos no se re-baraja ni se altera.
    assert list(sala.orden_turnos) == antes["orden"]
    # L y M: el misterio y las piezas físicas son independientes.
    assert {k: v["id"] for k, v in sala.misterio.items()} == antes["misterio"]
    assert dict(sala.posiciones_objetos) == antes["objetos"]
    # El resto del asiento: vistas, descartes y estado de investigación.
    assert sala.vistas[antes["id"]] == antes["vistas"]
    assert sala.descartes[antes["id"]] == antes["descartes"]
    assert sala.jugador_por_id(antes["id"])["activo_investigacion"] == antes["activo"]
    # Ni un participante más ni una repartición nueva.
    assert [j["id"] for j in sala.jugadores] == antes["ids"]


# --------------------------------------------------------------------------
# N, T, U, V · El PNJ continúa de inmediato la acción bloqueada
# --------------------------------------------------------------------------

def test_t_esperando_movimiento_sin_tirar_dado_el_pnj_continua():
    sala, anfitrion, bloqueante, _ = sala_antibloqueo()
    assert sala.estado_jugada == JUGADA_ESPERANDO_MOVIMIENTO
    # El humano NO pulsa TIRAR DADO.
    vencida(sala)
    sala.registrar_aviso_inactividad()
    sala.convertir_en_pnj(anfitrion["id"], sala.bloqueo_aviso_id)
    # converting no ejecuta nada: la cadena PNJ canónica sigue siendo la que
    # tira, mueve y sospecha.
    assert sala.estado_jugada == JUGADA_ESPERANDO_MOVIMIENTO
    assert sala.jugador_bloqueante() is None
    sala.ejecutar_turno_pnj(RngPrimero())
    # Ha tirado y ha elegido destino con su propia lógica PNJ.
    assert sala.jugada_publica().get("movimiento_pnj") is not None
    assert sala.secuencia_movimiento == 1


def test_u_esperando_destino_conserva_la_tirada_y_no_vuelve_a_tirar():
    sala, anfitrion, bloqueante, _ = sala_antibloqueo()
    origen = POSICIONES_INICIALES["bruno"]
    tirada = tiro_que_entra_en_ubicacion(origen)
    sala.tirar_dado_tablero(bloqueante["id"], rng=DadoFijo(tirada))
    assert sala.estado_jugada == JUGADA_ESPERANDO_DESTINO
    assert sala.tirada_pendiente == tirada
    destinos = set(sala.rutas_pendientes)
    vencida(sala)
    sala.registrar_aviso_inactividad()
    sala.convertir_en_pnj(anfitrion["id"], sala.bloqueo_aviso_id)
    # La conversión NO reinicia el turno ni vuelve a tirar.
    assert sala.tirada_pendiente == tirada
    assert sala.turno_actual == 0
    assert sala.jugador_en_turno()["id"] == bloqueante["id"]
    sala.continuar_bloqueo_como_pnj(RngPrimero())
    # Usa ESA MISMA tirada: se mueve a un destino legal de ella y la gasta.
    assert sala.posiciones.obtener(bloqueante["id"]) in destinos
    assert sala.tirada_pendiente is None
    assert sala.rutas_pendientes == {}
    movimiento = sala.movimiento_resuelto
    assert movimiento["origen_id"] == origen
    assert movimiento["destino_id"] == sala.posiciones.obtener(bloqueante["id"])
    # Entró en una ubicación: la sospecha PNJ continúa el flujo canónico.
    if TABLERO.es_ubicacion(movimiento["destino_id"]):
        assert sala.estado_jugada == JUGADA_PRESENTANDO_SOSPECHA
        assert sala.presentacion_sospecha["sospecha"]["lugar_id"] == movimiento["destino_id"]
    else:
        assert sala.estado_jugada == JUGADA_ESPERANDO_MOVIMIENTO


def test_v_esperando_sospecha_el_pnj_formula_la_sospecha():
    sala, anfitrion, bloqueante, _ = sala_antibloqueo()
    origen = POSICIONES_INICIALES["bruno"]
    tirada = tiro_que_entra_en_ubicacion(origen)
    sala.tirar_dado_tablero(bloqueante["id"], rng=DadoFijo(tirada))
    destino = next(
        d for d in sala.rutas_pendientes if TABLERO.es_ubicacion(d)
    )
    sala.mover(bloqueante["id"], destino)
    # Entró en una ubicación y la máquina espera su sospecha obligatoria.
    assert sala.estado_jugada == JUGADA_ESPERANDO_SOSPECHA
    assert sala.bloqueo_accion == "formular_sospecha"
    vencida(sala)
    sala.registrar_aviso_inactividad()
    sala.convertir_en_pnj(anfitrion["id"], sala.bloqueo_aviso_id)
    assert sala.estado_jugada == JUGADA_ESPERANDO_SOSPECHA
    sala.continuar_bloqueo_como_pnj(RngPrimero())
    # La lógica PNJ formula la sospecha en la ubicación actual.
    assert sala.estado_jugada == JUGADA_PRESENTANDO_SOSPECHA
    assert sala.presentacion_sospecha["investigador_id"] == bloqueante["id"]
    assert sala.presentacion_sospecha["sospecha"]["lugar_id"] == destino
    # Y la refutación/presentación siguen su curso canónico.
    sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    assert sala.estado_jugada == JUGADA_ESPERANDO_REFUTADOR
    assert sala.sospecha_pendiente is not None


def test_n_la_conversion_no_deja_bloqueo_ni_plazo_colgando():
    sala, anfitrion, bloqueante, _ = sala_antibloqueo()
    vencida(sala)
    sala.registrar_aviso_inactividad()
    sala.convertir_en_pnj(anfitrion["id"], sala.bloqueo_aviso_id)
    assert sala.bloqueo_deadline is None
    assert sala.bloqueo_jugador_id is None
    assert sala.jugador_bloqueante() is None
    assert aviso_de(sala, anfitrion["id"]) is None
    # Un aviso antiguo no sirve para nada.
    with pytest.raises(ValueError):
        sala.convertir_en_pnj(anfitrion["id"], sala.bloqueo_aviso_id)
    with pytest.raises(ValueError):
        sala.seguir_esperando(anfitrion["id"], sala.bloqueo_aviso_id)


# --------------------------------------------------------------------------
# O, W, X · La conversión es definitiva para ese asiento
# --------------------------------------------------------------------------

def test_o_w_x_el_antiguo_humano_no_recupera_el_control():
    sala, anfitrion, bloqueante, _ = sala_antibloqueo()
    vencida(sala)
    sala.registrar_aviso_inactividad()
    sala.convertir_en_pnj(anfitrion["id"], sala.bloqueo_aviso_id)
    sala.continuar_bloqueo_como_pnj(RngPrimero())
    # Sigue siendo el mismo jugador_id, ya no puede formular la sospecha.
    with pytest.raises(ValueError):
        sala.formular_sospecha_humano(bloqueante["id"], "mateo", "parador", "baul-imperial")
    # X: tampoco puede resolver el misterio.
    with pytest.raises(ValueError):
        sala.resolver_misterio_humano(bloqueante["id"], "mateo", "parador", "baul-imperial")
    # Y las rutas humanas de movimiento siguen rechazadas desde 8B.32.
    for accion in (
        lambda: sala.tirar_dado_tablero(bloqueante["id"]),
        lambda: sala.mover(bloqueante["id"], "parador"),
        lambda: sala.usar_pasadizo(bloqueante["id"]),
    ):
        with pytest.raises(ValueError):
            accion()


def test_o_el_turno_sigue_siendo_del_convertido_y_lo_toma_el_pnj():
    sala, anfitrion, bloqueante, pnj = sala_antibloqueo()
    vencida(sala)
    sala.registrar_aviso_inactividad()
    sala.convertir_en_pnj(anfitrion["id"], sala.bloqueo_aviso_id)
    assert sala.jugador_en_turno()["id"] == bloqueante["id"]
    assert sala.jugador_en_turno()["tipo"] == TIPO_PNJ
    # La cadena PNJ canónica lo juega sin esperar otro turno.
    sala.ejecutar_turno_pnj(RngPrimero())
    assert sala.secuencia_movimiento == 1


# --------------------------------------------------------------------------
# P · Privacidad
# --------------------------------------------------------------------------

def test_p_la_conversion_no_filtra_informacion_privada():
    sala, anfitrion, bloqueante, pnj = sala_antibloqueo()
    mano = [c["id"] for c in sala.manos[bloqueante["id"]]]
    vencida(sala)
    sala.registrar_aviso_inactividad()
    aviso = aviso_de(sala, anfitrion["id"])
    assert set(aviso) == {"aviso_id", "alias"}
    sala.convertir_en_pnj(anfitrion["id"], sala.bloqueo_aviso_id)
    publico = sala.estado_publico()
    # Lo único público es que ese asiento pasa a controlado automáticamente.
    tipos = {j["alias"]: j["tipo"] for j in publico["jugadores"]}
    assert tipos["Bruno"] == TIPO_PNJ
    # Ni cartas, ni mano, ni conocimiento, ni razón del PNJ.
    serializado = repr(publico)
    for carta in mano:
        assert carta not in serializado
    assert "inactividad" not in publico
    assert "aviso_id" not in serializado
    assert "soluciones_deducidas" not in serializado
    # El aviso tampoco viaja a otros jugadores.
    for destinatario in (pnj["id"], bloqueante["id"]):
        assert aviso_de(sala, destinatario) is None
    # La hoja de investigación sigue siendo privada de cada quien.
    assert sala.estado_privado(anfitrion["id"])["investigacion"]


# --------------------------------------------------------------------------
# Q, R, S · No interviene con 8B.30/8B.31 ni con los PNJ ni con el final
# --------------------------------------------------------------------------

def test_q_no_interfiere_con_los_plazos_de_8b30_y_8b31():
    sala, anfitrion, bloqueante, _ = sala_antibloqueo()
    refutador = sala.agregar_jugador("Carla", personaje_id="mateo")
    sala.manos[refutador["id"]] = [dict(CARTA_POR_ID["baul-imperial"])]
    sala.orden_turnos.append(refutador["id"])
    sala.estado_jugada = JUGADA_ESPERANDO_SOSPECHA
    sala.formular_sospecha(bloqueante["id"], "mateo", "iglesia-san-agustin", "baul-imperial")
    # Presentación 8B.30: con su propio plazo, sin antibloqueo.
    assert sala.estado_jugada == JUGADA_PRESENTANDO_SOSPECHA
    assert sala.bloqueo_deadline is None
    assert sala.refutacion_deadline is None
    sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    # 8B.31: refutación humana con su timeout canónico, sin antibloqueo.
    assert sala.estado_jugada == JUGADA_ESPERANDO_REFUTADOR
    assert sala.sospecha_pendiente["refutador_id"] == refutador["id"]
    assert sala.refutacion_deadline is not None
    assert sala.bloqueo_deadline is None
    sala.registrar_aviso_inactividad(ahora=float("inf"))
    assert aviso_de(sala, anfitrion["id"]) is None
    # El resultado público 8B.31C tampoco abre el antibloqueo.
    sala.mostrar_carta(refutador["id"], "baul-imperial")
    assert sala.presentacion_sospecha["tipo"] == "resultado"
    assert sala.bloqueo_deadline is None
    assert sala.jugador_bloqueante() is None


def test_r_un_turno_normal_de_pnj_nunca_genera_aviso():
    sala, anfitrion, _, pnj = sala_antibloqueo()
    sala.orden_turnos = [pnj["id"], sala.orden_turnos[0], sala.orden_turnos[2]]
    sala.turno_actual = 0
    sala.marcar_bloqueo()
    assert sala.jugador_bloqueante() is None
    assert sala.bloqueo_deadline is None
    vencida(sala)
    assert sala.registrar_aviso_inactividad() is False
    assert aviso_de(sala, anfitrion["id"]) is None


def test_s_partida_terminada_nunca_genera_aviso():
    sala, anfitrion, bloqueante, _ = sala_antibloqueo()
    sala.misterio = {
        "sospechoso": dict(CARTA_POR_ID["bruno"]),
        "lugar": dict(CARTA_POR_ID["iglesia-san-agustin"]),
        "objeto": dict(CARTA_POR_ID["baul-imperial"]),
    }
    sala.estado_jugada = JUGADA_ESPERANDO_SOSPECHA
    sala.marcar_bloqueo()
    assert sala.resolver_misterio_humano(
        bloqueante["id"], "bruno", "iglesia-san-agustin", "baul-imperial"
    )
    assert sala.estado == ESTADO_TERMINADA
    assert sala.jugador_bloqueante() is None
    assert sala.registrar_aviso_inactividad(ahora=float("inf")) is False
    assert aviso_de(sala, anfitrion["id"]) is None


def test_eliminados_y_lobby_no_bloquean():
    sala, anfitrion, bloqueante, pnj = sala_antibloqueo()
    bloqueante["activo_investigacion"] = False
    sala.marcar_bloqueo()
    assert sala.jugador_bloqueante() is None
    assert sala.bloqueo_deadline is None
    # En el lobby tampoco hay antibloqueo.
    sala.estado = "esperando"
    sala.estado_jugada = JUGADA_ESPERANDO_MOVIMIENTO
    sala.marcar_bloqueo()
    assert sala.bloqueo_deadline is None


# --------------------------------------------------------------------------
# 11 · Carreras contra el watchdog del servidor
# --------------------------------------------------------------------------

def test_watchdog_espera_al_plazo_y_avisa_una_sola_vez(monkeypatch):
    async def escenario(plazo, dormir_antes):
        sala, anfitrion, bloqueante, _ = sala_antibloqueo()
        sala.bloqueo_deadline = time.monotonic() + plazo
        main.gestor.salas[sala.codigo] = sala
        lock = asyncio.Lock()
        main.cerrojos[sala.codigo] = lock
        eventos = []

        async def difundir(_codigo):
            eventos.append(("difundir", aviso_de(sala, anfitrion["id"])))

        async def dormir(segundos):
            eventos.append(("esperar", round(segundos), lock.locked()))
            if dormir_antes is not None:
                dormir_antes(sala, bloqueante, anfitrion)
        monkeypatch.setattr(main, "difundir", difundir)
        monkeypatch.setattr(main.asyncio, "sleep", dormir)
        try:
            await main._vigilar_bloqueo(sala.codigo)
            return eventos, sala
        finally:
            main.gestor.salas.pop(sala.codigo, None)
            main.cerrojos.pop(sala.codigo, None)
            main.tareas_bloqueo.pop(sala.codigo, None)

    # 1. Plazo pendiente: duerme EXACTAMENTE lo que falta y SIN coger el
    #    cerrojo. Y como el minuto aún no se ha cumplido, no avisa.
    eventos, _ = asyncio.run(escenario(30, None))
    assert eventos == [("esperar", 30, False)]

    # 2. Plazo ya vencido: avisa una sola vez y difunde.
    eventos, _ = asyncio.run(escenario(-1, None))
    assert eventos == [("difundir", {"aviso_id": 0, "alias": "Bruno"})]


def test_watchdog_no_avisa_si_la_accion_gano_la_carrera(monkeypatch):
    async def escenario():
        sala, anfitrion, bloqueante, _ = sala_antibloqueo()
        sala.tirar_dado_tablero(bloqueante["id"], rng=DadoFijo(2))
        sala.bloqueo_deadline = time.monotonic() + 30
        main.gestor.salas[sala.codigo] = sala
        main.cerrojos[sala.codigo] = asyncio.Lock()
        avisos = []

        async def difundir(_codigo):
            avisos.append(aviso_de(sala, anfitrion["id"]))

        def el_humano_actua(sala, bloqueante, _anfitrion):
            # El humano actúa mientras el watchdog duerme: gana la carrera.
            casilla = next(
                destino
                for destino in sala.rutas_pendientes
                if not TABLERO.es_ubicacion(destino)
            )
            sala.mover(bloqueante["id"], casilla)

        async def dormir(segundos):
            el_humano_actua(sala, bloqueante, anfitrion)

        monkeypatch.setattr(main, "difundir", difundir)
        monkeypatch.setattr(main.asyncio, "sleep", dormir)
        try:
            await main._vigilar_bloqueo(sala.codigo)
            assert avisos == []
        finally:
            main.gestor.salas.pop(sala.codigo, None)
            main.cerrojos.pop(sala.codigo, None)
            main.tareas_bloqueo.pop(sala.codigo, None)

    asyncio.run(escenario())


def test_watchdog_descartado_si_el_plazo_ya_renovado(monkeypatch):
    async def escenario():
        sala, anfitrion, bloqueante, _ = sala_antibloqueo()
        sala.bloqueo_deadline = time.monotonic() + 30
        main.gestor.salas[sala.codigo] = sala
        main.cerrojos[sala.codigo] = asyncio.Lock()
        avisos = []

        async def difundir(_codigo):
            avisos.append(aviso_de(sala, anfitrion["id"]))

        def el_anfitrion_renueva(sala, _bloqueante, anfitrion):
            # SEGUIR ESPERANDO gana la carrera: cambia la identidad del plazo.
            vencida(sala)
            sala.registrar_aviso_inactividad()
            sala.seguir_esperando(anfitrion["id"], sala.bloqueo_aviso_id)

        async def dormir(_segundos):
            el_anfitrion_renueva(sala, bloqueante, anfitrion)

        monkeypatch.setattr(main, "difundir", difundir)
        monkeypatch.setattr(main.asyncio, "sleep", dormir)
        try:
            await main._vigilar_bloqueo(sala.codigo)
            assert avisos == []
            assert aviso_de(sala, anfitrion["id"]) is None
            assert 0 < sala.bloqueo_deadline - time.monotonic() <= INACTIVIDAD_BLOQUEO_SEGUNDOS
        finally:
            main.gestor.salas.pop(sala.codigo, None)
            main.cerrojos.pop(sala.codigo, None)
            main.tareas_bloqueo.pop(sala.codigo, None)

    asyncio.run(escenario())


def test_doble_clic_y_aviso_antiguo_de_dos_pestanas():
    sala, anfitrion, bloqueante, _ = sala_antibloqueo()
    vencida(sala)
    sala.registrar_aviso_inactividad()
    aviso = aviso_de(sala, anfitrion["id"])["aviso_id"]
    # Primera pestaña: SEGUIR ESPERANDO.
    sala.seguir_esperando(anfitrion["id"], aviso)
    # Segunda pestaña con el MISMO aviso: no renueva otra vez.
    with pytest.raises(ValueError):
        sala.seguir_esperando(anfitrion["id"], aviso)
    vencida(sala)
    sala.registrar_aviso_inactividad()
    nuevo = aviso_de(sala, anfitrion["id"])["aviso_id"]
    assert nuevo != aviso
    # La primera pestaña, con su aviso viejo, ya no puede convertir.
    with pytest.raises(ValueError):
        sala.convertir_en_pnj(anfitrion["id"], aviso)
    # La segunda sí: y es la única transición.
    sala.convertir_en_pnj(anfitrion["id"], nuevo)
    with pytest.raises(ValueError):
        sala.convertir_en_pnj(anfitrion["id"], nuevo)
    assert sala.jugador_por_id(bloqueante["id"])["tipo"] == TIPO_PNJ
    assert len(sala.jugadores) == 3


# --------------------------------------------------------------------------
# 13 · Secuencia funcional completa
# --------------------------------------------------------------------------

def test_secuencia_funcional_tirar_dado_bloqueo_y_pasar_a_pnj():
    """Humano tira, no elige destino, se bloquea, el anfitrión lo convierte y
    el PNJ usa ESA tirada, entra en ubicación y formula la sospecha."""
    sala, anfitrion, bloqueante, _ = sala_antibloqueo()
    origen = POSICIONES_INICIALES["bruno"]
    tirada = tiro_que_entra_en_ubicacion(origen)
    sala.tirar_dado_tablero(bloqueante["id"], rng=DadoFijo(tirada))
    assert sala.estado_jugada == JUGADA_ESPERANDO_DESTINO
    # El humano no hace nada más.
    vencida(sala)
    assert sala.registrar_aviso_inactividad() is True
    aviso = aviso_de(sala, anfitrion["id"])
    assert aviso["alias"] == "Bruno"
    # PASAR A PNJ
    sala.convertir_en_pnj(anfitrion["id"], aviso["aviso_id"])
    sala.continuar_bloqueo_como_pnj(RngPrimero())
    # Movimiento normal con la tirada original.
    assert sala.movimiento_resuelto["destino_id"] in set(sala.rutas_pendientes) | {
        sala.posiciones.obtener(bloqueante["id"])
    }
    assert sala.posiciones.obtener(bloqueante["id"]) != origen
    if TABLERO.es_ubicacion(sala.movimiento_resuelto["destino_id"]):
        # Sospecha PNJ -> presentación -> refutación.
        assert sala.estado_jugada == JUGADA_PRESENTANDO_SOSPECHA
        sala.actualizar_presentacion_sospecha(ahora=float("inf"))
        assert sala.estado_jugada == JUGADA_ESPERANDO_REFUTADOR
        refutador = sala.sospecha_pendiente["refutador_id"]
        if sala.jugador_por_id(refutador)["tipo"] == TIPO_PNJ:
            sala.continuar_refutacion(refutador)
            sala.actualizar_presentacion_sospecha(ahora=float("inf"))
        else:
            sala.mostrar_carta(refutador, sala.sospecha_pendiente["coincidencias"][0])
        # Cierre público y siguiente turno.
        sala.actualizar_presentacion_sospecha(ahora=float("inf"))
        assert sala.jugador_en_turno()["id"] != bloqueante["id"]
    else:
        # Entró en una casilla de camino: el turno avanza al siguiente.
        assert sala.estado_jugada == JUGADA_ESPERANDO_MOVIMIENTO
        assert sala.jugador_en_turno()["id"] != bloqueante["id"]


def test_secuencia_funcional_seguir_esperando_renueva_el_minuto():
    sala, anfitrion, bloqueante, _ = sala_antibloqueo()
    momento = time.monotonic()
    vencida(sala)
    sala.registrar_aviso_inactividad()
    sala.seguir_esperando(anfitrion["id"], sala.bloqueo_aviso_id)
    # Durante el nuevo minuto no hay aviso en absoluto.
    for segundo in (1, 30, 59):
        assert sala.registrar_aviso_inactividad(ahora=momento + segundo) is False
    assert aviso_de(sala, anfitrion["id"]) is None
    # Completa el nuevo minuto: aviso nuevo.
    assert sala.registrar_aviso_inactividad(ahora=momento + 60) is True
    aviso = aviso_de(sala, anfitrion["id"])
    assert aviso is not None
    # Sigue siendo humano y la partida no se ha movido.
    assert sala.jugador_por_id(bloqueante["id"])["tipo"] == TIPO_HUMANO
    assert sala.estado_jugada == JUGADA_ESPERANDO_MOVIMIENTO
    assert sala.secuencia_movimiento == 0


# --------------------------------------------------------------------------
# Extremo a extremo por WebSocket: el aviso y las dos decisiones del anfitrión
# --------------------------------------------------------------------------

def test_por_ws_solo_el_anfitrion_recibe_el_aviso_y_puede_decidir():
    cliente = TestClient(main.app)
    gestor, conexiones = main.gestor, main.conexiones
    gestor.salas.clear()
    conexiones.clear()
    codigo = None
    try:
        datos = cliente.post("/api/partidas", json={"alias": "Anfitriona", "modo": "tablero"}).json()
        codigo = datos["codigo"]
        anfitrion_id = datos["jugador_id"]
        unido = cliente.post(
            f"/api/partidas/{codigo}/unirse", json={"alias": "Bruno"}
        ).json()
        bloqueante_id = unido["jugador_id"]
        sala = gestor.obtener(codigo)
        sala.elegir_personaje(anfitrion_id, "vera")
        sala.elegir_personaje(bloqueante_id, "bruno")
        with cliente.websocket_connect(f"/ws/{codigo}/{bloqueante_id}") as ws_bloqueante:
            with cliente.websocket_connect(f"/ws/{codigo}/{anfitrion_id}") as ws_anfitrion:
                ws_bloqueante.receive_json()
                ws_anfitrion.receive_json()
                ws_anfitrion.send_json({"accion": "iniciar"})
                assert ws_anfitrion.receive_json()["sala"]["estado"] == "iniciada"
                # El turno puede no ser el del humano; se fuerza al bloqueante.
                sala.orden_turnos = [bloqueante_id] + [
                    jid for jid in sala.orden_turnos if jid != bloqueante_id
                ]
                sala.turno_actual = 0
                sala.estado_jugada = JUGADA_ESPERANDO_MOVIMIENTO
                sala.marcar_bloqueo()
                vencida(sala)
                assert sala.registrar_aviso_inactividad() is True
                aviso_id = aviso_de(sala, anfitrion_id)["aviso_id"]
                # El bloqueante no tiene ninguna capacidad de inactividad.
                assert _aviso_por_ws(ws_bloqueante) is None
                # Un humano que no es anfitrión no puede decidir nada.
                ws_bloqueante.send_json({"accion": "pasar_a_pnj", "aviso_id": aviso_id})
                error = ws_bloqueante.receive_json()
                assert error["tipo"] == "error"
                assert sala.jugador_por_id(bloqueante_id)["tipo"] == TIPO_HUMANO
                # SEGUIR ESPERANDO renueva el plazo y cierra el aviso.
                ws_anfitrion.send_json({"accion": "seguir_esperando", "aviso_id": aviso_id})
                assert _aviso_por_ws(ws_anfitrion) is None
                assert 0 < sala.bloqueo_deadline - time.monotonic() <= INACTIVIDAD_BLOQUEO_SEGUNDOS
                # Un aviso antiguo ya no sirve.
                ws_anfitrion.send_json({"accion": "pasar_a_pnj", "aviso_id": aviso_id})
                assert ws_anfitrion.receive_json()["tipo"] == "error"
                # Vence el nuevo minuto: PASAR A PNJ sobre el aviso vigente.
                vencida(sala)
                assert sala.registrar_aviso_inactividad() is True
                nuevo = aviso_de(sala, anfitrion_id)["aviso_id"]
                assert nuevo != aviso_id
                ws_anfitrion.send_json({"accion": "pasar_a_pnj", "aviso_id": nuevo})
                estado = _sala_por_ws(ws_anfitrion)
                asiento = next(j for j in estado["jugadores"] if j["alias"] == "Bruno")
                assert asiento["tipo"] == TIPO_PNJ
                # El asiento conservado es el mismo y ya no es humano.
                assert sala.jugador_en_turno()["id"] == bloqueante_id
                # Doble clic: el segundo intento es un error, no un segundo PNJ.
                ws_anfitrion.send_json({"accion": "pasar_a_pnj", "aviso_id": nuevo})
                assert ws_anfitrion.receive_json()["tipo"] == "error"
                assert len(sala.jugadores) == 6
        if codigo:
            main.cancelar_bloqueo(codigo)
    finally:
        if codigo:
            main.cancelar_bloqueo(codigo)
        gestor.salas.clear()
        conexiones.clear()


def _sala_por_ws(ws):
    return ws.receive_json()["sala"]


def _aviso_por_ws(ws):
    return _sala_por_ws(ws).get("inactividad")
