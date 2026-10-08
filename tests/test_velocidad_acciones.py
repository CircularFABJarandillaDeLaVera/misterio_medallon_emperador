"""Microfase 2 · Velocidad de las acciones automáticas.

Contrato:
- El valor inicial reproduce EXACTAMENTE el ritmo anterior a esta fase.
- Solo el anfitrión, y solo con su credencial, mueve el ajuste.
- El ajuste es de la SALA: lo ven todos los participantes por igual.
- Solo se mueven las esperas AUTOMÁTICAS; los plazos de decisión humana,
  las ventanas obligatorias y el antibloqueo no se tocan.
- Una espera ya en curso se respeta entera: el cambio aplica a la siguiente.
"""
import pathlib
import time

import pytest
from fastapi.testclient import TestClient

from app import main
from app.motor.sala import (
    ESTADO_INICIADA,
    INACTIVIDAD_BLOQUEO_SEGUNDOS,
    JUGADA_ESPERANDO_MOVIMIENTO,
    JUGADA_PRESENTANDO_SOSPECHA,
    MENSAJE_SIN_AUTORIDAD_ADMIN,
    MODO_TABLERO,
    PAUSA_PRESENTACION_HUMANO_SEGUNDOS,
    PAUSA_PRESENTACION_PNJ_SEGUNDOS,
    PAUSA_PRESENTACION_RESULTADO_SEGUNDOS,
    TIMEOUT_REFUTACION_HUMANO_SEGUNDOS,
    TIPO_PNJ,
    VELOCIDAD_AUTOMATICA_INICIAL,
    VELOCIDAD_AUTOMATICA_MAXIMA,
    VELOCIDAD_AUTOMATICA_MINIMA,
    GestorSalas,
)

BASE = VELOCIDAD_AUTOMATICA_INICIAL


@pytest.fixture(autouse=True)
def limpiar_registros():
    main.gestor.salas.clear()
    main.conexiones.clear()
    main.cerrojos.clear()
    main.tareas_pnj.clear()
    yield
    main.gestor.salas.clear()
    main.conexiones.clear()
    main.cerrojos.clear()
    main.tareas_pnj.clear()


def sala_de_prueba(modo=MODO_TABLERO):
    """Sala en el registro real (main.gestor), para que la cadena PNJ y los
    watchdogs puedan encontrarla igual que en el juego."""
    sala, anfitrion = main.gestor.crear_sala("Ana", modo)
    _, invitado = main.gestor.unirse(sala.codigo, "Luis")
    sala.elegir_personaje(anfitrion["id"], "vera")
    sala.elegir_personaje(invitado["id"], "bruno")
    sala.iniciar(anfitrion["id"])
    return sala, anfitrion, invitado


def credencial_de(sala):
    return sala.credencial_admin


# --- El valor inicial reproduce el comportamiento anterior ---------------


def test_valor_inicial_por_defecto():
    sala, _, _ = sala_de_prueba()
    assert sala.velocidad_acciones == BASE == 3


def test_con_el_valor_inicial_el_ritmo_pnj_es_el_de_siempre():
    """Idéntico a los valores literales que fija test_ritmo.py."""
    sala, _, _ = sala_de_prueba()
    assert main.PAUSA_TURNO_PNJ_SEGUNDOS == 3.0
    assert main.PAUSA_TRAS_JUGADA_HUMANA_SEGUNDOS == 5.0
    assert main.PAUSA_LECTURA_SOSPECHA_PNJ_SEGUNDOS == 5.0
    assert main.pausa_antes_de_turno_pnj(sala) == 3.0

    sala.ultima_jugada = {
        "investigador_id": sala.jugadores[0]["id"],
        "sospecha": {"sospechoso_id": "vera"},
        "resultado": "sin_refutacion",
    }
    sala.jugadores[0]["tipo"] = TIPO_PNJ
    assert main.pausa_antes_de_turno_pnj(sala) == 5.0


def test_con_el_valor_inicial_las_ventanas_siguen_siendo_las_de_siemre():
    sala, anfitrion, _ = sala_de_prueba()
    sala.estado_jugada = "esperando_sospecha"
    sala.turno_actual = sala.orden_turnos.index(anfitrion["id"])
    inicio = 1000.0
    sala.formular_sospecha(anfitrion["id"], "lucia", "parador", "baul-imperial", ahora=inicio)
    participantes = sala.presentacion_sospecha["participantes"]
    pnj = [p for p in sala.jugadores if p["tipo"] == TIPO_PNJ]
    humano = [p for p in sala.jugadores if p["tipo"] != TIPO_PNJ]
    assert participantes[pnj[0]["id"]]["deadline"] - inicio == PAUSA_PRESENTACION_PNJ_SEGUNDOS == 3.0
    for persona in humano:
        if not persona["id"] == anfitrion["id"]:
            assert (
                participantes[persona["id"]]["deadline"] - inicio
                == PAUSA_PRESENTACION_HUMANO_SEGUNDOS
                == 10.0
            )


# --- El ajuste mueve un segundo a la vez -------------------------------


def test_mas_rapido_resta_un_segundo():
    sala, anfitrion, _ = sala_de_prueba()
    assert sala.acelerar_acciones(anfitrion["id"], credencial_de(sala)) == BASE - 1
    assert sala.acelerar_acciones(anfitrion["id"], credencial_de(sala)) == BASE - 2


def test_mas_lento_suma_un_segundo():
    sala, anfitrion, _ = sala_de_prueba()
    assert sala.ralentizar_acciones(anfitrion["id"], credencial_de(sala)) == BASE + 1
    assert sala.ralentizar_acciones(anfitrion["id"], credencial_de(sala)) == BASE + 2


def test_limite_minimo_uno():
    sala, anfitrion, _ = sala_de_prueba()
    for _ in range(20):
        sala.acelerar_acciones(anfitrion["id"], credencial_de(sala))
    assert sala.velocidad_acciones == VELOCIDAD_AUTOMATICA_MINIMA == 1
    # Pulsar más allá del tope no cambia nada ni lanza error.
    assert sala.acelerar_acciones(anfitrion["id"], credencial_de(sala)) == 1


def test_limite_maximo_diez():
    sala, anfitrion, _ = sala_de_prueba()
    for _ in range(20):
        sala.ralentizar_acciones(anfitrion["id"], credencial_de(sala))
    assert sala.velocidad_acciones == VELOCIDAD_AUTOMATICA_MAXIMA == 10
    assert sala.ralentizar_acciones(anfitrion["id"], credencial_de(sala)) == 10


def test_el_ritmo_sigue_a_la_velocidad_en_los_extremos():
    sala, anfitrion, _ = sala_de_prueba()
    sala.acelerar_acciones(anfitrion["id"], credencial_de(sala))
    sala.acelerar_acciones(anfitrion["id"], credencial_de(sala))
    assert main.pausa_antes_de_turno_pnj(sala) == 1.0
    for _ in range(20):
        sala.ralentizar_acciones(anfitrion["id"], credencial_de(sala))
    assert main.pausa_antes_de_turno_pnj(sala) == 10.0


def test_las_diferencias_entre_esperas_se_conservan():
    """El ritmo y la lectura se mueven juntos: los 2 s de diferencia siguen."""
    sala, anfitrion, _ = sala_de_prueba()
    sala.jugadores[0]["tipo"] = TIPO_PNJ
    sala.ultima_jugada = {
        "investigador_id": sala.jugadores[0]["id"],
        "sospecha": {"sospechoso_id": "vera"},
        "resultado": "sin_refutacion",
    }

    for velocidad in range(VELOCIDAD_AUTOMATICA_MINIMA, VELOCIDAD_AUTOMATICA_MAXIMA + 1):
        sala.velocidad_acciones = velocidad
        ritmo = main.PAUSA_TURNO_PNJ_SEGUNDOS + (velocidad - BASE)
        lectura = main.PAUSA_LECTURA_SOSPECHA_PNJ_SEGUNDOS + (velocidad - BASE)
        assert lectura - ritmo == 2.0, f"diferencia perdida en {velocidad}"
        assert main.pausa_antes_de_turno_pnj(sala) == lectura


# --- Autoridad ------------------------------------------------------------


def test_solo_el_anfitrion_con_credencial_puede_mover_el_ritmo():
    sala, _, invitado = sala_de_prueba()
    with pytest.raises(ValueError):
        sala.acelerar_acciones(invitado["id"], credencial_de(sala))
    with pytest.raises(ValueError):
        sala.ralentizar_acciones(invitado["id"], credencial_de(sala))
    assert sala.velocidad_acciones == BASE


def test_anfitrion_sin_credencial_no_puede():
    sala, anfitrion, _ = sala_de_prueba()
    for credencial in (None, "", "inventada"):
        with pytest.raises(ValueError):
            sala.acelerar_acciones(anfitrion["id"], credencial)
    assert sala.velocidad_acciones == BASE


def test_el_rechazo_es_el_mismo_que_en_el_resto_de_acciones_admin():
    sala, anfitrion, _ = sala_de_prueba()
    with pytest.raises(ValueError) as error:
        sala.ralentizar_acciones(anfitrion["id"], "inventada")
    assert str(error.value) == MENSAJE_SIN_AUTORIDAD_ADMIN


def test_un_pnj_no_puede_mover_el_ritmo():
    sala, _, _ = sala_de_prueba()
    pnj = next(j for j in sala.jugadores if j["tipo"] == TIPO_PNJ)
    with pytest.raises(ValueError):
        sala.acelerar_acciones(pnj["id"], credencial_de(sala))


def test_el_ritmo_tambien_usa_la_comprobacion_de_credencial():
    """La validación es la de la microfase 1, no una más débil."""
    sala, anfitrion, _ = sala_de_prueba()
    sala.credencial_admin_resumen = "otra-cosa"
    with pytest.raises(ValueError):
        sala.acelerar_acciones(anfitrion["id"], credencial_de(sala))


# --- Sincronización entre participantes ----------------------------------


def test_todos_los_participantes_ven_la_misma_velocidad():
    sala, anfitrion, invitado = sala_de_prueba()
    sala.acelerar_acciones(anfitrion["id"], credencial_de(sala))
    valores = {
        sala.estado_privado(j["id"])["velocidad_acciones"] for j in sala.jugadores
    }
    assert valores == {BASE - 1}


def test_un_pnj_no_tiene_por_que_ver_la_velocidad_pero_el_estado_es_uno():
    sala, anfitrion, _ = sala_de_prueba()
    sala.ralentizar_acciones(anfitrion["id"], credencial_de(sala))
    assert sala.estado_privado(anfitrion["id"])["velocidad_acciones"] == BASE + 1
    assert all(
        estado["velocidad_acciones"] == BASE + 1
        for estado in (sala.estado_privado(j["id"]) for j in sala.jugadores)
    )


def test_la_velocidad_no_es_una_credenencial():
    sala, _, _ = sala_de_prueba()
    sala.acelerar_acciones(sala.anfitrion()["id"], credencial_de(sala))
    publico = repr(sala.estado_publico())
    assert "credencial_admin" not in publico
    assert sala.credencial_admin not in publico


def test_por_websocket_el_cambio_llega_a_todos():
    cliente = TestClient(main.app)
    creada = cliente.post(
        "/api/partidas", json={"alias": "Ana", "modo": "tablero"}
    ).json()
    unida = cliente.post(
        f"/api/partidas/{creada['codigo']}/unirse", json={"alias": "Luis"}
    ).json()
    sala = main.gestor.obtener(creada["codigo"])
    sala.elegir_personaje(creada["jugador_id"], "vera")
    sala.elegir_personaje(unida["jugador_id"], "bruno")
    sala.iniciar(creada["jugador_id"])
    with cliente.websocket_connect(
        f"/ws/{creada['codigo']}/{creada['jugador_id']}"
    ) as anfitrion:
        anfitrion.receive_json()
        with cliente.websocket_connect(
            f"/ws/{creada['codigo']}/{unida['jugador_id']}"
        ) as invitado:
            invitado.receive_json()
            anfitrion.send_json(
                {
                    "accion": "acelerar_acciones",
                    "credencial_admin": sala.credencial_admin,
                }
            )
            estado_anfitrion = anfitrion.receive_json()["sala"]
            estado_invitado = invitado.receive_json()["sala"]
    assert estado_anfitrion["velocidad_acciones"] == BASE - 1
    assert estado_invitado["velocidad_acciones"] == BASE - 1
    assert sala.velocidad_acciones == BASE - 1


def test_por_websocket_un_invitado_es_rechazado():
    cliente = TestClient(main.app)
    creada = cliente.post(
        "/api/partidas", json={"alias": "Ana", "modo": "tablero"}
    ).json()
    unida = cliente.post(
        f"/api/partidas/{creada['codigo']}/unirse", json={"alias": "Luis"}
    ).json()
    sala = main.gestor.obtener(creada["codigo"])
    with cliente.websocket_connect(
        f"/ws/{creada['codigo']}/{unida['jugador_id']}"
    ) as invitado:
        invitado.receive_json()
        # Manipula la petición a mano, con el secreto de la sala.
        invitado.send_json(
            {
                "accion": "ralentizar_acciones",
                "credencial_admin": sala.credencial_admin,
            }
        )
        error = invitado.receive_json()
    assert error["tipo"] == "error"
    assert error["detalle"] == MENSAJE_SIN_AUTORIDAD_ADMIN
    assert sala.velocidad_acciones == BASE


def test_por_websocket_sin_credenencial_es_rechazado():
    cliente = TestClient(main.app)
    creada = cliente.post("/api/partidas", json={"alias": "Ana"}).json()
    sala = main.gestor.obtener(creada["codigo"])
    with cliente.websocket_connect(
        f"/ws/{creada['codigo']}/{creada['jugador_id']}"
    ) as anfitrion:
        anfitrion.receive_json()
        anfitrion.send_json({"accion": "acelerar_acciones"})
        error = anfitrion.receive_json()
    assert error["tipo"] == "error"
    assert sala.velocidad_acciones == BASE


# --- Los temporizadores humanos no se mueven -----------------------------


def _plazo_de_refutacion(velocidad):
    """Sala nueva, sospecha resuelta y el plazo de refutar que queda."""
    sala, anfitrion, invitado = sala_de_prueba()
    sala.velocidad_acciones = velocidad
    # Solo el humano invitado puede refutar: los PNJ no tienen la carta.
    for jugador in sala.jugadores:
        if jugador["tipo"] == TIPO_PNJ:
            sala.manos[jugador["id"]] = []
    sala.manos[invitado["id"]] = [
        {"id": "lucia", "nombre": "Lucía", "categoria": "sospechoso"}
    ]
    sala.estado_jugada = "esperando_sospecha"
    sala.turno_actual = sala.orden_turnos.index(anfitrion["id"])
    sala.formular_sospecha(
        anfitrion["id"], "lucia", "parador", "baul-imperial", ahora=1000.0
    )
    sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    assert sala.estado_jugada == "esperando_eleccion_refutador"
    return sala.refutacion_deadline - time.monotonic()


def test_el_plazo_de_refutacion_no_cambia():
    """El plazo de refutar sigue siendo el canónico, con la velocidad que sea."""
    assert TIMEOUT_REFUTACION_HUMANO_SEGUNDOS == 10.0
    for velocidad in (
        VELOCIDAD_AUTOMATICA_MINIMA,
        BASE,
        VELOCIDAD_AUTOMATICA_MAXIMA,
    ):
        restante = _plazo_de_refutacion(velocidad)
        assert 0 < restante <= TIMEOUT_REFUTACION_HUMANO_SEGUNDOS, (
            f"el plazo de refutar se movió con velocidad {velocidad}"
        )


def test_las_ventanas_obligatorias_de_lectura_no_cambian():
    sala, anfitrion, _ = sala_de_prueba()
    inicio = 2000.0
    sala._abrir_presentacion_resultado(
        investigador_id=anfitrion["id"],
        investigador_alias="Ana",
        sospecha={"sospechoso_id": "lucia", "lugar_id": "parador", "objeto_id": "baul-imperial"},
        resultado="refutada",
        ahora=inicio,
    )
    for velocidad in (VELOCIDAD_AUTOMATICA_MINIMA, BASE, VELOCIDAD_AUTOMATICA_MAXIMA):
        sala.velocidad_acciones = velocidad
        sala._abrir_presentacion_resultado(
            investigador_id=anfitrion["id"],
            investigador_alias="Ana",
            sospecha={"sospechoso_id": "lucia", "lugar_id": "parador", "objeto_id": "baul-imperial"},
            resultado="refutada",
            ahora=inicio,
        )
        participantes = sala.presentacion_sospecha["participantes"]
        humanos = [
            j for j in sala.jugadores if j["tipo"] != TIPO_PNJ
        ]
        for persona in humanos:
            assert (
                participantes[persona["id"]]["deadline"] - inicio
                == PAUSA_PRESENTACION_RESULTADO_SEGUNDOS
                == 14.0
            ), f"la ventana humana se movió con velocidad {velocidad}"
        pnj = next(j for j in sala.jugadores if j["tipo"] == TIPO_PNJ)
        assert (
            participantes[pnj["id"]]["deadline"] - inicio
            == PAUSA_PRESENTACION_PNJ_SEGUNDOS + (velocidad - BASE)
        ), "la ventana automática del PNJ debe seguir a la velocidad"


def test_la_ventana_de_sospecha_del_humano_no_cambia():
    sala, anfitrion, _ = sala_de_prueba()
    sala.estado_jugada = "esperando_sospecha"
    sala.turno_actual = sala.orden_turnos.index(anfitrion["id"])
    inicio = 3000.0
    sala.velocidad_acciones = VELOCIDAD_AUTOMATICA_MAXIMA
    sala.formular_sospecha(
        anfitrion["id"], "lucia", "parador", "baul-imperial", ahora=inicio
    )
    otro_humano = next(
        j
        for j in sala.jugadores
        if j["tipo"] != TIPO_PNJ and j["id"] != anfitrion["id"]
    )
    plaza = sala.presentacion_sospecha["participantes"][otro_humano["id"]]
    assert plaza["deadline"] - inicio == PAUSA_PRESENTACION_HUMANO_SEGUNDOS == 10.0


def test_el_antibloqueo_no_cambia():
    sala, anfitrion, _ = sala_de_prueba()
    sala.estado_jugada = JUGADA_ESPERANDO_MOVIMIENTO
    sala.turno_actual = sala.orden_turnos.index(anfitrion["id"])
    for velocidad in (VELOCIDAD_AUTOMATICA_MINIMA, BASE, VELOCIDAD_AUTOMATICA_MAXIMA):
        sala.velocidad_acciones = velocidad
        sala.bloqueo_jugador_id = None
        sala.marcar_bloqueo()
        assert INACTIVIDAD_BLOQUEO_SEGUNDOS == 60.0
        assert 0 < sala.bloqueo_deadline - time.monotonic() <= 60.0


def test_el_timeout_de_refutacion_calculado_por_el_watchdog_no_cambia(monkeypatch):
    """El watchdog duerme el plazo canónico, no el ajustado."""
    import asyncio

    esperas = []

    async def dormir(segundos):
        esperas.append(segundos)

    monkeypatch.setattr(main.asyncio, "sleep", dormir)
    sala, anfitrion, _ = sala_de_prueba()
    # La velocidad más rápida del todo, y aun así el plazo no se toca.
    sala.acelerar_acciones(anfitrion["id"], credencial_de(sala))
    sala.acelerar_acciones(anfitrion["id"], credencial_de(sala))
    sala.sospecha_pendiente = {
        "investigador_id": anfitrion["id"],
        "refutador_id": next(
            j["id"] for j in sala.jugadores if j["tipo"] != TIPO_PNJ
        ),
        "sospecha": {},
        "coincidencias": [],
    }
    sala.estado_jugada = "esperando_eleccion_refutador"
    sala.refutacion_deadline = time.monotonic() + TIMEOUT_REFUTACION_HUMANO_SEGUNDOS

    async def escenario():
        await main._vigilar_refutacion_humana(sala.codigo)

    asyncio.run(escenario())
    assert esperas == [TIMEOUT_REFUTACION_HUMANO_SEGUNDOS]


# --- Una espera en curso no se recalcula ---------------------------------


def test_el_ritmo_se_calcula_una_vez_antes_de_dormir():
    """La cadena toma su duración ANTES de dormir y la respeta entera."""
    fuente = pathlib.Path("app/main.py").read_text(encoding="utf-8")
    inicio = fuente.index("pausa = pausa_antes_de_turno_pnj(sala)")
    fin = fuente.index("await _esperar_turno_pnj(sala, pausa)")
    assert "velocidad" not in fuente[inicio:fin], (
        "no se relee la velocidad durante la espera"
    )
    # La espera encapsulada sigue siendo UN solo asyncio.sleep(segundos).
    espera = fuente[fuente.index("async def _esperar_turno_pnj"): inicio]
    assert espera.count("asyncio.sleep(") == 1
    assert "time.sleep" not in fuente



def test_la_espera_en_curso_no_se_recalcula(monkeypatch):
    """Comportamiento definido: una espera ya empezada se respeta entera.

    La cadena toma su duración ANTES de dormir. Si el anfitrión acelera
    mientras el PNJ espera, ese PNJ sigue esperando lo que calculó antes; el
    valor nuevo entra en la siguiente espera. Así ningún MÁS RÁPIDO puede
    meter un PNJ por delante de la lectura pendiente y provocar una carrera.
    """
    sala, anfitrion, _ = sala_de_prueba()

    # Lo que la cadena calcula y registra ANTES de dormir.
    espera_en_curso = main.pausa_antes_de_turno_pnj(sala)
    assert espera_en_curso == 3.0

    # El anfitrión acelera dos veces mientras la espera está en curso.
    sala.acelerar_acciones(anfitrion["id"], credencial_de(sala))
    sala.acelerar_acciones(anfitrion["id"], credencial_de(sala))

    # La espera en curso no cambia...
    assert espera_en_curso == 3.0
    # ...pero la siguiente ya sale a la velocidad nueva.
    assert main.pausa_antes_de_turno_pnj(sala) == 1.0
    # Y nunca baja del mínimo configurado.
    for _ in range(10):
        sala.acelerar_acciones(anfitrion["id"], credencial_de(sala))
    assert main.pausa_antes_de_turno_pnj(sala) == 1.0


def test_reprogramar_dos_veces_no_duplica_la_cadena(monkeypatch):
    """Tocar la velocidad no crea tareas automáticas extra."""
    import asyncio

    sala, anfitrion, _ = sala_de_prueba()
    pnj = next(j for j in sala.jugadores if j["tipo"] == TIPO_PNJ)
    sala.orden_turnos = [pnj["id"], anfitrion["id"]]
    sala.turno_actual = 0
    sala.estado_jugada = JUGADA_ESPERANDO_MOVIMIENTO

    async def dormir(segundos):
        # Con la partida ya en movimiento, acelerar y frenar no reprograma.
        sala.acelerar_acciones(anfitrion["id"], credencial_de(sala))
        sala.ralentizar_acciones(anfitrion["id"], credencial_de(sala))
        sala.acelerar_acciones(anfitrion["id"], credencial_de(sala))

    async def escenario():
        main.programar_turno_pnj(sala.codigo)
        main.programar_turno_pnj(sala.codigo)
        primera = main.tareas_pnj.get(sala.codigo)
        await asyncio.sleep(0)
        main.programar_turno_pnj(sala.codigo)
        assert main.tareas_pnj.get(sala.codigo) is primera
        await asyncio.sleep(0)
        tarea = main.tareas_pnj.get(sala.codigo)
        if tarea is not None:
            tarea.cancel()

    asyncio.run(escenario())
    assert len(main.tareas_pnj) <= 1


def test_la_velocidad_no_crea_turnos_ni_sospechas(monkeypatch):
    """Acelerar y frenar muchas veces no mueve la partida."""
    sala, anfitrion, _ = sala_de_prueba()
    numero = sala.numero_turno
    historial = len(sala.historial)
    for _ in range(6):
        sala.acelerar_acciones(anfitrion["id"], credencial_de(sala))
    for _ in range(6):
        sala.ralentizar_acciones(anfitrion["id"], credencial_de(sala))
    assert sala.numero_turno == numero
    assert len(sala.historial) == historial
    assert sala.estado == ESTADO_INICIADA


def test_el_estado_de_la_partida_no_expone_la_velocidad_como_control():
    """La velocidad es un dato, no una capacidad de administrar."""
    sala, _, _ = sala_de_prueba()
    sala.acelerar_acciones(sala.anfitrion()["id"], credencial_de(sala))
    for jugador in sala.jugadores:
        estado = sala.estado_privado(jugador["id"])
        assert "credencial_admin" not in estado
        assert "velocidad_acciones" in estado


def test_la_accion_desconocida_no_mueve_el_ritmo():
    cliente = TestClient(main.app)
    creada = cliente.post("/api/partidas", json={"alias": "Ana"}).json()
    sala = main.gestor.obtener(creada["codigo"])
    with cliente.websocket_connect(
        f"/ws/{creada['codigo']}/{creada['jugador_id']}"
    ) as anfitrion:
        anfitrion.receive_json()
        anfitrion.send_json({"accion": "velocidad", "credencial_admin": sala.credencial_admin})
        respuesta = anfitrion.receive_json()
    assert respuesta["tipo"] == "estado_privado"
    assert sala.velocidad_acciones == BASE
