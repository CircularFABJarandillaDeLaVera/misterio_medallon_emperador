"""Microfase 3 · Pausar y reanudar.

Contrato:
- Solo el anfitrión, con su credencial, pausa y reanuda.
- Congelar es CORRER EL RELOJ: al reanudar, cada plazo conserva el tiempo
  que le quedaba, y un PNJ que estaba esperando no actúa antes de tiempo.
- Durante la pausa el servidor rechaza toda acción de juego.
- Reanudar es idempotente y rearma sin duplicar tareas ni saltar turnos.
"""
import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from app import main
from app.motor.sala import (
    ACCIONES_PERMITIDAS_EN_PAUSA,
    ESTADO_INICIADA,
    INACTIVIDAD_BLOQUEO_SEGUNDOS,
    JUGADA_ESPERANDO_MOVIMIENTO,
    MENSAJE_PARTIDA_EN_PAUSA,
    MENSAJE_PARTIDA_NO_PAUSA,
    MENSAJE_SIN_AUTORIDAD_ADMIN,
    MODO_TABLERO,
    TIPO_HUMANO,
    TIPO_PNJ,
    VELOCIDAD_AUTOMATICA_INICIAL,
    GestorSalas,
)


@pytest.fixture(autouse=True)
def limpiar_registros():
    for tabla in (
        main.gestor.salas,
        main.conexiones,
        main.cerrojos,
        main.tareas_pnj,
        main.tareas_refutacion,
        main.tareas_presentacion,
        main.tareas_bloqueo,
    ):
        tabla.clear()
    yield
    for tabla in (
        main.gestor.salas,
        main.conexiones,
        main.cerrojos,
        main.tareas_pnj,
        main.tareas_refutacion,
        main.tareas_presentacion,
        main.tareas_bloqueo,
    ):
        tabla.clear()


def sala_en_curso(modo=MODO_TABLERO):
    sala, anfitrion = main.gestor.crear_sala("Ana", modo)
    _, invitado = main.gestor.unirse(sala.codigo, "Luis")
    sala.elegir_personaje(anfitrion["id"], "vera")
    sala.elegir_personaje(invitado["id"], "bruno")
    sala.iniciar(anfitrion["id"])
    return sala, anfitrion, invitado


def credencial(sala):
    return sala.credencial_admin


def como_host(cliente, alias="Ana", modo=MODO_TABLERO):
    creada = cliente.post(
        "/api/partidas", json={"alias": alias, "modo": modo}
    ).json()
    sala = main.gestor.obtener(creada["codigo"])
    return creada, sala


# --- Autoridad ------------------------------------------------------------


def test_solo_el_anfitrion_con_credencial_pausa():
    sala, _, invitado = sala_en_curso()
    with pytest.raises(ValueError):
        sala.pausar_partida(invitado["id"], credencial(sala))
    with pytest.raises(ValueError):
        sala.pausar_partida(invitado["id"], "inventada")
    assert sala.pausada is False


def test_el_anfitrion_sin_credencial_no_pausa():
    sala, anfitrion, _ = sala_en_curso()
    for credencial_ in (None, "", "inventada", 0, []):
        with pytest.raises(ValueError):
            sala.pausar_partida(anfitrion["id"], credencial_)
    assert sala.pausada is False


def test_el_rechazo_de_pausa_es_el_mismo_que_el_de_la_velocidad():
    sala, anfitrion, _ = sala_en_curso()
    with pytest.raises(ValueError) as pausa:
        sala.pausar_partida(anfitrion["id"], "inventada")
    with pytest.raises(ValueError) as ritmo:
        sala.ralentizar_acciones(anfitrion["id"], "inventada")
    assert str(pausa.value) == str(ritmo.value) == MENSAJE_SIN_AUTORIDAD_ADMIN


def test_un_pnj_no_pausa():
    sala, _, _ = sala_en_curso()
    pnj = next(j for j in sala.jugadores if j["tipo"] == TIPO_PNJ)
    with pytest.raises(ValueError):
        sala.pausar_partida(pnj["id"], credencial(sala))


def test_reanudar_tambien_exige_credencial():
    sala, anfitrion, invitado = sala_en_curso()
    sala.pausar_partida(anfitrion["id"], credencial(sala))
    with pytest.raises(ValueError):
        sala.reanudar_partida(invitado["id"], credencial(sala))
    with pytest.raises(ValueError):
        sala.reanudar_partida(anfitrion["id"], "inventada")
    assert sala.pausada is True


def test_no_se_puede_pausar_en_el_lobby_ni_tras_terminar():
    sala, anfitrion = main.gestor.crear_sala("Ana")
    with pytest.raises(ValueError):
        sala.pausar_partida(anfitrion["id"], credencial(sala))

    sala, anfitrion, _ = sala_en_curso()
    sala.estado = "terminada"
    with pytest.raises(ValueError):
        sala.pausar_partida(anfitrion["id"], credencial(sala))


def test_reanudar_sin_pausa_da_error_explicito():
    sala, anfitrion, _ = sala_en_curso()
    with pytest.raises(ValueError) as error:
        sala.reanudar_partida(anfitrion["id"], credencial(sala))
    assert str(error.value) == MENSAJE_PARTIDA_NO_PAUSA


# --- Congelación de plazos ----------------------------------------------


def test_desplazar_plazos_toca_los_cuatro_relojes():
    sala, anfitrion, _ = sala_en_curso()
    sala.presentacion_sospecha = {
        "id": 1,
        "inicio": 100.0,
        "participantes": {
            "a": {"listo": False, "deadline": 110.0},
            "b": {"listo": True, "deadline": 100.0},
        },
    }
    sala.refutacion_deadline = 120.0
    sala.bloqueo_deadline = 130.0
    sala.desplazar_plazos(45.0)
    assert sala.presentacion_sospecha["inicio"] == 145.0
    assert sala.presentacion_sospecha["participantes"]["a"]["deadline"] == 155.0
    assert sala.presentacion_sospecha["participantes"]["b"]["deadline"] == 145.0
    assert sala.refutacion_deadline == 165.0
    assert sala.bloqueo_deadline == 175.0


def test_desplazar_plazos_ignora_los_relojes_apagados():
    sala, _, _ = sala_en_curso()
    sala.refutacion_deadline = None
    sala.bloqueo_deadline = None
    sala.presentacion_sospecha = None
    sala.desplazar_plazos(30.0)
    assert sala.refutacion_deadline is None
    assert sala.bloqueo_deadline is None


def test_desplazar_plazos_ignora_un_delta_negativo():
    sala, anfitrion, _ = sala_en_curso()
    sala.refutacion_deadline = 100.0
    sala.desplazar_plazos(-5.0)
    assert sala.refutacion_deadline == 100.0


def test_la_refutacion_pendiente_conserva_su_tiempo_restante(monkeypatch):
    """El caso crítico: el refutador sigue teniendo sus segundos."""
    reloj = {"t": 1000.0}
    monkeypatch.setattr(time, "monotonic", lambda: reloj["t"])
    sala, anfitrion, _ = sala_en_curso()
    sala.sospecha_pendiente = {
        "investigador_id": anfitrion["id"],
        "refutador_id": next(
            j["id"]
            for j in sala.jugadores
            if j["tipo"] == TIPO_HUMANO and j["id"] != anfitrion["id"]
        ),
        "sospecha": {},
        "coincidencias": ["parador"],
    }
    sala.estado_jugada = "esperando_eleccion_refutador"
    sala.refutacion_deadline = reloj["t"] + 10.0

    # Se consumen 3 s de lectura y se pausa durante 30 s.
    reloj["t"] += 3.0
    sala.pausar_partida(anfitrion["id"], credencial(sala))
    assert sala.refutacion_deadline - reloj["t"] == 7.0
    reloj["t"] += 30.0
    sala.reanudar_partida(anfitrion["id"], credencial(sala))
    # Vuelve a quedar 7 s, no 7-30 ni 10.
    assert sala.refutacion_deadline - reloj["t"] == 7.0


def test_los_plazos_conservan_su_diferencia_en_presentacion(monkeypatch):
    reloj = {"t": 1000.0}
    monkeypatch.setattr(time, "monotonic", lambda: reloj["t"])
    sala, anfitrion, _ = sala_en_curso()
    sala.presentacion_sospecha = {
        "id": 1,
        "inicio": reloj["t"],
        "participantes": {
            "a": {"listo": False, "deadline": reloj["t"] + 3.0},
            "b": {"listo": False, "deadline": reloj["t"] + 10.0},
        },
    }
    antes = {
        clave: datos["deadline"] - sala.presentacion_sospecha["inicio"]
        for clave, datos in sala.presentacion_sospecha["participantes"].items()
    }
    sala.pausar_partida(anfitrion["id"], credencial(sala))
    reloj["t"] += 12.0
    sala.reanudar_partida(anfitrion["id"], credencial(sala))
    despues = {
        clave: datos["deadline"] - sala.presentacion_sospecha["inicio"]
        for clave, datos in sala.presentacion_sospecha["participantes"].items()
    }
    assert antes == despues == {"a": 3.0, "b": 10.0}


def test_el_antibloqueo_conserva_su_plazo(monkeypatch):
    reloj = {"t": 1000.0}
    monkeypatch.setattr(time, "monotonic", lambda: reloj["t"])
    sala, anfitrion, _ = sala_en_curso()
    sala.estado_jugada = JUGADA_ESPERANDO_MOVIMIENTO
    sala.turno_actual = sala.orden_turnos.index(anfitrion["id"])
    sala.marcar_bloqueo()
    assert sala.bloqueo_deadline - reloj["t"] == INACTIVIDAD_BLOQUEO_SEGUNDOS

    sala.pausar_partida(anfitrion["id"], credencial(sala))
    reloj["t"] += 45.0
    sala.reanudar_partida(anfitrion["id"], credencial(sala))
    # El minuto de antibloqueo sigue siendo de 60 s: la pausa no lo consume.
    assert sala.bloqueo_deadline - reloj["t"] == INACTIVIDAD_BLOQUEO_SEGUNDOS


# --- Pausas repetidas ----------------------------------------------------


def test_pausa_y_reanudacion_repetidas_conservan_el_tiempo(monkeypatch):
    reloj = {"t": 1000.0}
    monkeypatch.setattr(time, "monotonic", lambda: reloj["t"])
    sala, anfitrion, _ = sala_en_curso()
    sala.refutacion_deadline = reloj["t"] + 10.0
    for _ in range(5):
        assert sala.pausar_partida(anfitrion["id"], credencial(sala)) is True
        reloj["t"] += 2.0
        assert sala.reanudar_partida(anfitrion["id"], credencial(sala)) is True
    # Cinco pausas de 2 s: el refutador conserva sus 10 s intactos.
    assert sala.refutacion_deadline - reloj["t"] == 10.0


def test_pausar_dos_veces_es_idempotente():
    sala, anfitrion, _ = sala_en_curso()
    assert sala.pausar_partida(anfitrion["id"], credencial(sala)) is True
    marca = sala.pausa_marca
    assert sala.pausar_partida(anfitrion["id"], credencial(sala)) is False
    assert sala.pausa_marca == marca, "la segunda pausa no reinicia el reloj"


def test_reanudar_dos_veces_no_desplaza_dos_veces(monkeypatch):
    reloj = {"t": 1000.0}
    monkeypatch.setattr(time, "monotonic", lambda: reloj["t"])
    sala, anfitrion, _ = sala_en_curso()
    sala.refutacion_deadline = reloj["t"] + 10.0
    sala.pausar_partida(anfitrion["id"], credencial(sala))
    reloj["t"] += 7.0
    sala.reanudar_partida(anfitrion["id"], credencial(sala))
    with pytest.raises(ValueError):
        sala.reanudar_partida(anfitrion["id"], credencial(sala))
    assert sala.refutacion_deadline - reloj["t"] == 10.0


# --- Acciones rechazadas durante la pausa --------------------------------


def test_ninguna_accion_de_juego_pasa_durante_la_pausa():
    sala, anfitrion, invitado = sala_en_curso()
    sala.pausar_partida(anfitrion["id"], credencial(sala))
    for accion in (
        "iniciar",
        "tirar_dado",
        "mover",
        "usar_pasadizo",
        "formular_sospecha",
        "mostrar_carta",
        "continuar_refutacion",
        "resolver_misterio",
        "confirmar_presentacion_sospecha",
        "marcar_investigacion",
        "elegir_personaje",
        "volver_al_lobby",
        "seguir_esperando",
        "pasar_a_pnj",
        "acelerar_acciones",
        "ralentizar_acciones",
    ):
        with pytest.raises(ValueError) as error:
            sala.comprobar_accion_en_pausa(accion)
        assert str(error.value) == MENSAJE_PARTIDA_EN_PAUSA


def test_durante_la_pausa_solo_se_acepta_reanudar():
    sala, anfitrion, _ = sala_en_curso()
    sala.pausar_partida(anfitrion["id"], credencial(sala))
    assert "reanudar_partida" in ACCIONES_PERMITIDAS_EN_PAUSA
    sala.comprobar_accion_en_pausa("reanudar_partida")
    sala.comprobar_accion_en_pausa("pedir_credencial_admin")


def test_sin_pausa_no_se_filtra_nada():
    sala, _, _ = sala_en_curso()
    for accion in ("tirar_dado", "marcar_investigacion", "volver_al_lobby"):
        sala.comprobar_accion_en_pausa(accion)


def test_el_motor_rechaza_una_sospecha_durante_la_pausa():
    """Defense en profundidad: aunque alguien saltase el WebSocket."""
    sala, anfitrion, _ = sala_en_curso()
    sala.estado_jugada = "esperando_sospecha"
    sala.turno_actual = sala.orden_turnos.index(anfitrion["id"])
    sala.pausar_partida(anfitrion["id"], credencial(sala))
    with pytest.raises(ValueError):
        sala.comprobar_accion_en_pausa("formular_sospecha")
    assert sala.estado_jugada == "esperando_sospecha"
    assert sala.presentacion_sospecha is None


# --- Orquestación: tareas detenidas y rearmadas -------------------------


def test_pausar_hoquea_las_cuatro_tareas(monkeypatch):
    sala, anfitrion, _ = sala_en_curso()

    async def dormir(segundos):
        return None

    monkeypatch.setattr(main.asyncio, "sleep", dormir)

    async def escenario():
        sala.sospecha_pendiente = {
            "investigador_id": anfitrion["id"],
            "refutador_id": next(
                j["id"] for j in sala.jugadores if j["tipo"] == TIPO_HUMANO and j["id"] != anfitrion["id"]
            ),
            "sospecha": {},
            "coincidencias": [],
        }
        sala.estado_jugada = "esperando_eleccion_refutador"
        sala.refutacion_deadline = time.monotonic() + 10.0
        sala.presentacion_sospecha = {
            "id": 1,
            "tipo": "resultado",
            "inicio": time.monotonic(),
            "participantes": {anfitrion["id"]: {"listo": False, "deadline": time.monotonic() + 14.0}},
        }
        sala.estado_jugada = "presentando_sospecha"
        sala.pausar_partida(anfitrion["id"], credencial(sala))
        main.pausar_partida(sala)
        await asyncio.sleep(0)
        assert main.tareas_pnj.get(sala.codigo) is None
        assert main.tareas_refutacion.get(sala.codigo) is None
        assert main.tareas_presentacion.get(sala.codigo) is None
        assert main.tareas_bloqueo.get(sala.codigo) is None
        main.reanudar_partida(sala)

    asyncio.run(escenario())


def test_reanudar_rearma_las_tareas_que_hacen_falta():
    sala, anfitrion, _ = sala_en_curso()

    async def escenario():
        sala.sospecha_pendiente = {
            "investigador_id": anfitrion["id"],
            "refutador_id": next(
                j["id"] for j in sala.jugadores if j["tipo"] == TIPO_HUMANO and j["id"] != anfitrion["id"]
            ),
            "sospecha": {},
            "coincidencias": [],
        }
        sala.estado_jugada = "esperando_eleccion_refutador"
        sala.refutacion_deadline = time.monotonic() + 10.0
        sala.pausar_partida(anfitrion["id"], credencial(sala))
        main.pausar_partida(sala)
        sala.reanudar_partida(anfitrion["id"], credencial(sala))
        main.reanudar_partida(sala)
        # La tarea se crea aquí mismo: se comprueba antes de que arranque.
        assert main.tareas_refutacion.get(sala.codigo) is not None
        for nombre in ("tareas_pnj", "tareas_refutacion", "tareas_presentacion", "tareas_bloqueo"):
            tarea = getattr(main, nombre).get(sala.codigo)
            if tarea is not None:
                tarea.cancel()
                try:
                    await tarea
                except asyncio.CancelledError:
                    pass

    asyncio.run(escenario())


def test_ninguna_tarea_arranca_mientras_esta_pausada():
    sala, anfitrion, _ = sala_en_curso()

    async def escenario():
        sala.pausar_partida(anfitrion["id"], credencial(sala))
        main.programar_turno_pnj(sala.codigo)
        main.programar_timeout_refutacion(sala.codigo)
        main.programar_presentacion_sospecha(sala.codigo)
        main.programar_bloqueo(sala.codigo)
        await asyncio.sleep(0)
        assert main.tareas_pnj.get(sala.codigo) is None
        assert main.tareas_refutacion.get(sala.codigo) is None
        assert main.tareas_presentacion.get(sala.codigo) is None
        assert main.tareas_bloqueo.get(sala.codigo) is None

    asyncio.run(escenario())


def test_reconectar_en_pausa_no_arranca_nada():
    sala, anfitrion, _ = sala_en_curso()

    async def escenario():
        sala.pausar_partida(anfitrion["id"], credencial(sala))
        # El acceptor rearma las cuatro tareas en cada conexión.
        main.programar_turno_pnj(sala.codigo)
        main.programar_timeout_refutacion(sala.codigo)
        main.programar_presentacion_sospecha(sala.codigo)
        main.programar_bloqueo(sala.codigo)
        await asyncio.sleep(0)
        assert not main.tareas_pnj
        assert not main.tareas_refutacion
        assert not main.tareas_presentacion
        assert not main.tareas_bloqueo

    asyncio.run(escenario())


def test_la_cadena_pnj_no_actua_si_encuentra_la_sala_pausada():
    sala, anfitrion, _ = sala_en_curso()
    pnj = next(j for j in sala.jugadores if j["tipo"] == TIPO_PNJ)
    sala.orden_turnos = [pnj["id"], anfitrion["id"]]
    sala.turno_actual = 0
    sala.estado_jugada = JUGADA_ESPERANDO_MOVIMIENTO
    sala.pausar_partida(anfitrion["id"], credencial(sala))
    numero = sala.numero_turno

    async def dormir(segundos):  # pragma: no cover - no debe llamarse
        raise AssertionError("la cadena no debe dormir con la partida en pausa")

    original = main.asyncio.sleep
    main.asyncio.sleep = dormir
    try:
        asyncio.run(main._cadena_turnos_pnj(sala.codigo))
    finally:
        main.asyncio.sleep = original
    assert sala.numero_turno == numero


# --- La espera del PNJ interrupted and resumed -------------------------


def _sala_con_pnj_en_turno():
    sala, anfitrion, _ = sala_en_curso()
    pnj = next(j for j in sala.jugadores if j["tipo"] == TIPO_PNJ)
    sala.orden_turnos = [pnj["id"], anfitrion["id"]]
    sala.turno_actual = 0
    sala.estado_jugada = JUGADA_ESPERANDO_MOVIMIENTO
    return sala, anfitrion


def _grabar_esperas_del_pnj(monkeypatch):
    """Registra SOLO las esperas de la cadena PNJ, no las de los watchdogs."""
    esperas = []
    original = main._esperar_turno_pnj

    async def grabado(sala, segundos):
        esperas.append(segundos)
        return await original(sala, segundos)

    monkeypatch.setattr(main, "_esperar_turno_pnj", grabado)
    return esperas


def test_la_espera_en_curso_del_pnj_se_congela(monkeypatch):
    """Qué ocurre exactamente al pausar durante una acción automática.

    El PNJ estaba esperando 3 s; cuando se pulsa PAUSAR le quedaban 0,5 s.
    Se conservan esos 0,5 s: ni 0 (no actúa antes de tiempo) ni 3 (no
    reinicia su espera).
    """
    sala, anfitrion = _sala_con_pnj_en_turno()
    reloj = {"t": 500.0}
    monkeypatch.setattr(main.time, "monotonic", lambda: reloj["t"])
    esperas = _grabar_esperas_del_pnj(monkeypatch)

    async def dormir(segundos):
        # Se consumen 2,5 s de los 3 s y entonces se pulsa PAUSAR.
        reloj["t"] += 2.5
        sala.pausar_partida(anfitrion["id"], credencial(sala))
        main.pausar_partida(sala)
        # En el juego, pausar_partida cancela esta misma tarea: la espera se
        # corta aquí y el PNJ todavía no ha actuado.
        raise asyncio.CancelledError

    monkeypatch.setattr(main.asyncio, "sleep", dormir)

    async def escenario():
        try:
            await main._cadena_turnos_pnj(sala.codigo)
        except asyncio.CancelledError:
            pass

    asyncio.run(escenario())
    assert esperas == [3.0]
    assert sala.pausada is True
    assert sala.turno_pnj_espera_restante == pytest.approx(0.5, abs=0.05)


def test_al_reanudar_el_pnj_retoma_con_el_resto(monkeypatch):
    """La cadena rearmada duerme lo que le faltaba, no una espera nueva."""
    sala, anfitrion = _sala_con_pnj_en_turno()
    reloj = {"t": 500.0}
    monkeypatch.setattr(main.time, "monotonic", lambda: reloj["t"])
    esperas = _grabar_esperas_del_pnj(monkeypatch)

    async def dormir(segundos):
        if len(esperas) == 1:
            # Un segundo de los tres, y se pulsa PAUSAR.
            reloj["t"] += 1.0
            sala.pausar_partida(anfitrion["id"], credencial(sala))
            main.pausar_partida(sala)
        raise asyncio.CancelledError

    monkeypatch.setattr(main.asyncio, "sleep", dormir)

    async def esperar_tarea(codigo):
        try:
            tarea = main.tareas_pnj.get(codigo)
            if tarea is not None:
                await tarea
        except asyncio.CancelledError:
            pass

    async def escenario():
        await _cadena_directa(sala)
        # Pausa de 30 s de reloj y reanudación.
        reloj["t"] += 30.0
        sala.reanudar_partida(anfitrion["id"], credencial(sala))
        main.reanudar_partida(sala)
        await esperar_tarea(sala.codigo)

    asyncio.run(escenario())
    assert esperas[0] == 3.0, "la espera en curso se respeta entera"
    assert len(esperas) == 2, "la cadena vuelve a arrancar una sola vez"
    assert esperas[1] == pytest.approx(2.0, abs=0.05), (
        "retoma con el resto, no con una espera nueva"
    )
    assert sala.turno_pnj_espera_restante is None, "el resto se gasta una vez"


async def _cadena_directa(sala):
    try:
        await main._cadena_turnos_pnj(sala.codigo)
    except asyncio.CancelledError:
        pass


def test_el_resto_conservado_se_consume_una_sola_vez(monkeypatch):
    sala, anfitrion = _sala_con_pnj_en_turno()
    sala.turno_pnj_espera_restante = 2.0
    esperas = _grabar_esperas_del_pnj(monkeypatch)

    async def dormir(segundos):
        raise asyncio.CancelledError

    monkeypatch.setattr(main.asyncio, "sleep", dormir)

    async def escenario():
        main.programar_turno_pnj(sala.codigo)
        try:
            await main.tareas_pnj.get(sala.codigo)
        except asyncio.CancelledError:
            pass

    asyncio.run(escenario())
    assert esperas == [2.0]
    assert sala.turno_pnj_espera_restante is None


def test_sin_espera_en_curso_no_se_guarda_un_resto_fantasma():
    sala, anfitrion, _ = sala_en_curso()
    sala.pausar_partida(anfitrion["id"], credencial(sala))
    main.pausar_partida(sala)
    assert sala.turno_pnj_espera_restante is None


def test_pausar_limpia_el_estado_de_piensa_del_pnj():
    sala, anfitrion, _ = sala_en_curso()
    sala.pnj_pensando_id = "pnj-vera"
    sala.pausar_partida(anfitrion["id"], credencial(sala))
    main.pausar_partida(sala)
    assert sala.pnj_pensando_id is None


# --- Estado visible ------------------------------------------------------


def test_el_estado_privado_avisa_de_la_pausa_a_todos():
    sala, anfitrion, invitado = sala_en_curso()
    sala.pausar_partida(anfitrion["id"], credencial(sala))
    for jugador in sala.jugadores:
        assert sala.estado_privado(jugador["id"])["pausada"] is True


def test_al_reanudar_el_estado_vuelve_a_cero():
    sala, anfitrion, _ = sala_en_curso()
    sala.pausar_partida(anfitrion["id"], credencial(sala))
    sala.reanudar_partida(anfitrion["id"], credencial(sala))
    for jugador in sala.jugadores:
        assert sala.estado_privado(jugador["id"])["pausada"] is False


def test_la_pausa_no_filtra_ninguna_credencial():
    sala, anfitrion, _ = sala_en_curso()
    sala.pausar_partida(anfitrion["id"], credencial(sala))
    for jugador in sala.jugadores:
        estado = repr(sala.estado_privado(jugador["id"]))
        assert sala.credencial_admin not in estado


# --- Velocidad conservada -------------------------------------------------


def test_la_velocidad_sobrevive_a_la_pausa():
    sala, anfitrion, _ = sala_en_curso()
    sala.ralentizar_acciones(anfitrion["id"], credencial(sala))
    assert sala.velocidad_acciones == VELOCIDAD_AUTOMATICA_INICIAL + 1
    sala.pausar_partida(anfitrion["id"], credencial(sala))
    sala.pausa_marca -= 25.0
    sala.reanudar_partida(anfitrion["id"], credencial(sala))
    assert sala.velocidad_acciones == VELOCIDAD_AUTOMATICA_INICIAL + 1


def test_se_puede_ajustar_el_ritmo_durante_la_pausa_sin_avanzar():
    sala, anfitrion, _ = sala_en_curso()
    sala.pausar_partida(anfitrion["id"], credencial(sala))
    numero = sala.numero_turno
    historial = len(sala.historial)
    sala.acelerar_acciones(anfitrion["id"], credencial(sala))
    sala.ralentizar_acciones(anfitrion["id"], credencial(sala))
    assert sala.velocidad_acciones == VELOCIDAD_AUTOMATICA_INICIAL
    assert sala.numero_turno == numero
    assert len(sala.historial) == historial


# --- Por WebSocket -------------------------------------------------------


def test_por_websocket_el_invitado_no_puede_pausar():
    cliente = TestClient(main.app)
    creada, sala = como_host(cliente)
    unida = cliente.post(
        f"/api/partidas/{creada['codigo']}/unirse", json={"alias": "Luis"}
    ).json()
    sala.elegir_personaje(creada["jugador_id"], "vera")
    sala.elegir_personaje(unida["jugador_id"], "bruno")
    sala.iniciar(creada["jugador_id"])
    with cliente.websocket_connect(
        f"/ws/{creada['codigo']}/{unida['jugador_id']}"
    ) as invitado:
        invitado.receive_json()
        # Manipula la petición con el secreto de la sala en la mano.
        invitado.send_json(
            {"accion": "pausar_partida", "credencial_admin": sala.credencial_admin}
        )
        error = invitado.receive_json()
    assert error["tipo"] == "error"
    assert error["detalle"] == MENSAJE_SIN_AUTORIDAD_ADMIN
    assert sala.pausada is False


def test_por_websocket_una_accion_de_juego_durante_la_pausa_se_rechaza():
    cliente = TestClient(main.app)
    creada, sala = como_host(cliente)
    sala.elegir_personaje(creada["jugador_id"], "vera")
    sala.iniciar(creada["jugador_id"])
    sala.pausar_partida(creada["jugador_id"], sala.credencial_admin)
    main.pausar_partida(sala)
    with cliente.websocket_connect(
        f"/ws/{creada['codigo']}/{creada['jugador_id']}"
    ) as anfitrion:
        anfitrion.receive_json()
        for accion in ("tirar_dado", "marcar_investigacion", "volver_al_lobby"):
            anfitrion.send_json({"accion": accion})
            error = anfitrion.receive_json()
            assert error["tipo"] == "error"
            assert error["detalle"] == MENSAJE_PARTIDA_EN_PAUSA
    # La partida no se ha movido.
    assert sala.pausada is True


def test_por_websocket_pausar_y_reanudar_manda_el_estado_a_todos():
    cliente = TestClient(main.app)
    creada, sala = como_host(cliente)
    unida = cliente.post(
        f"/api/partidas/{creada['codigo']}/unirse", json={"alias": "Luis"}
    ).json()
    sala.elegir_personaje(creada["jugador_id"], "vera")
    sala.elegir_personaje(unida["jugador_id"], "bruno")
    sala.iniciar(creada["jugador_id"])
    credencial = sala.credencial_admin
    with cliente.websocket_connect(
        f"/ws/{creada['codigo']}/{creada['jugador_id']}"
    ) as anfitrion:
        anfitrion.receive_json()
        with cliente.websocket_connect(
            f"/ws/{creada['codigo']}/{unida['jugador_id']}"
        ) as invitado:
            invitado.receive_json()
            anfitrion.send_json(
                {"accion": "pausar_partida", "credencial_admin": credencial}
            )
            assert anfitrion.receive_json()["sala"]["pausada"] is True
            assert invitado.receive_json()["sala"]["pausada"] is True
            anfitrion.send_json(
                {"accion": "reanudar_partida", "credencial_admin": credencial}
            )
            assert anfitrion.receive_json()["sala"]["pausada"] is False
            assert invitado.receive_json()["sala"]["pausada"] is False
    assert sala.pausada is False


def test_por_websocket_reconexion_mientras_esta_pausada():
    cliente = TestClient(main.app)
    creada, sala = como_host(cliente)
    sala.elegir_personaje(creada["jugador_id"], "vera")
    sala.iniciar(creada["jugador_id"])
    sala.pausar_partida(creada["jugador_id"], sala.credencial_admin)
    main.pausar_partida(sala)

    with cliente.websocket_connect(
        f"/ws/{creada['codigo']}/{creada['jugador_id']}"
    ) as ws:
        estado = ws.receive_json()["sala"]
    assert estado["pausada"] is True
    # Reconectar no ha arrancado ninguna tarea automática.
    assert main.tareas_pnj.get(sala.codigo) is None
    assert main.tareas_refutacion.get(sala.codigo) is None
    assert main.tareas_presentacion.get(sala.codigo) is None
    assert main.tareas_bloqueo.get(sala.codigo) is None


def test_el_refutador_responde_despues_de_reanudar():
    """El caso que se pedía comprobar: la ventana sigue viva y se responde."""
    cliente = TestClient(main.app)
    creada, sala = como_host(cliente, modo="rapido")
    unida = cliente.post(
        f"/api/partidas/{creada['codigo']}/unirse", json={"alias": "Luis"}
    ).json()
    sala.elegir_personaje(creada["jugador_id"], "vera")
    sala.elegir_personaje(unida["jugador_id"], "bruno")
    sala.iniciar(creada["jugador_id"])
    for jugador in sala.jugadores:
        if jugador["tipo"] == TIPO_PNJ:
            sala.manos[jugador["id"]] = []
    sala.manos[unida["jugador_id"]] = [
        {"id": "lucia", "nombre": "Lucía", "categoria": "sospechoso"}
    ]
    sala.turno_actual = sala.orden_turnos.index(creada["jugador_id"])
    sala.estado_jugada = "esperando_sospecha"
    sala.formular_sospecha(
        creada["jugador_id"], "lucia", "parador", "baul-imperial", ahora=1000.0
    )
    sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    assert sala.estado_jugada == "esperando_eleccion_refutador"
    credencial = sala.credencial_admin

    with cliente.websocket_connect(
        f"/ws/{creada['codigo']}/{creada['jugador_id']}"
    ) as anfitrion:
        anfitrion.receive_json()
        anfitrion.send_json({"accion": "pausar_partida", "credencial_admin": credencial})
        assert anfitrion.receive_json()["sala"]["pausada"] is True

        # Durante la pausa el refutador no puede actuar...
        with cliente.websocket_connect(
            f"/ws/{creada['codigo']}/{unida['jugador_id']}"
        ) as refutador:
            refutador.receive_json()
            refutador.send_json({"accion": "mostrar_carta", "carta_id": "lucia"})
            error = refutador.receive_json()
            assert error["detalle"] == MENSAJE_PARTIDA_EN_PAUSA
            assert sala.sospecha_pendiente is not None

            # ...pero al reanudar sí, y con su ventana intacta.
            anfitrion.send_json(
                {"accion": "reanudar_partida", "credencial_admin": credencial}
            )
            assert anfitrion.receive_json()["sala"]["pausada"] is False
            # El refutador recibe la difusión de la reanudación...
            assert refutador.receive_json()["sala"]["pausada"] is False
            assert 0 < sala.refutacion_deadline - time.monotonic() <= 10.0
            # ...y ahora sí puede responder.
            refutador.send_json({"accion": "mostrar_carta", "carta_id": "lucia"})
            estado = refutador.receive_json()["sala"]
            assert estado["jugada"]["estado"] == "presentando_sospecha"
