import asyncio

import pytest

from app import main
from app.datos.jarandilla import CARTA_POR_ID
from app.motor.sala import (
    ESTADO_INICIADA,
    ESTADO_TERMINADA,
    JUGADA_ESPERANDO_MOVIMIENTO,
    JUGADA_ESPERANDO_REFUTADOR,
    MODO_TABLERO,
    POSICIONES_INICIALES,
    TIPO_PNJ,
    Sala,
)
from app.motor.tablero import TABLERO


class RngPNJ:
    def __init__(self, accion="tirar", dado=1, indice_destino=0):
        self.accion = accion
        self.dado = dado
        self.indice_destino = indice_destino
        self.pesos_accion = None

    def choices(self, opciones, weights, k):
        if opciones and isinstance(opciones[0], str):
            self.pesos_accion = (tuple(opciones), tuple(weights))
            return [self.accion]
        return [opciones[0]]

    def choice(self, opciones):
        return opciones[self.indice_destino]

    def randint(self, minimo, maximo):
        assert (minimo, maximo) == (1, 6)
        return self.dado


def sala_pnj_tablero(posicion="parador", con_segundo_pnj=False):
    sala = Sala("JARA-PNJ-TABLERO", modo=MODO_TABLERO)
    pnj = sala.agregar_jugador("Bruno", True, TIPO_PNJ, "bruno")
    humano = sala.agregar_jugador("Humano", personaje_id="vera")
    jugadores = [pnj, humano]
    if con_segundo_pnj:
        jugadores.append(
            sala.agregar_jugador("Lucía", tipo=TIPO_PNJ, personaje_id="lucia")
        )
    sala.estado = ESTADO_INICIADA
    sala.orden_turnos = [j["id"] for j in jugadores]
    sala.turno_actual = 0
    sala.estado_jugada = JUGADA_ESPERANDO_MOVIMIENTO
    sala.manos = {j["id"]: [] for j in jugadores}
    for jugador in jugadores:
        sala.posiciones.asignar(
            jugador["id"], POSICIONES_INICIALES[jugador["personaje_id"]]
        )
    sala.posiciones.asignar(pnj["id"], posicion)
    return sala, pnj, humano, jugadores[2:]


def test_pnj_ubicacion_inicial_no_sospecha_sin_mover():
    sala, pnj, humano, _ = sala_pnj_tablero()
    rng = RngPNJ("tirar", dado=1)
    sala.ejecutar_turno_pnj(rng)
    assert rng.pesos_accion == (("tirar", "pasadizo"), (60, 15))
    assert sala.posiciones.obtener(pnj["id"]) != "parador"
    assert sala.ultima_jugada["tipo"] == "movimiento"
    assert "sospecha" not in sala.ultima_jugada
    assert sala.jugador_en_turno()["id"] == humano["id"]


def test_pnj_puede_usar_pasadizo_y_sospecha_en_destino():
    sala, pnj, _, _ = sala_pnj_tablero()
    sala.ejecutar_turno_pnj(RngPNJ("pasadizo"))
    assert sala.posiciones.obtener(pnj["id"]) == "nuestra-senora-torre"
    assert sala.ultima_jugada["sospecha"]["lugar_id"] == "nuestra-senora-torre"
    assert sala.ultima_jugada["movimiento_pnj"]["accion"] == "pasadizo"


def test_pnj_desde_ubicacion_sin_pasadizo_tira_obligatoriamente():
    sala, pnj, _, _ = sala_pnj_tablero("iglesia-san-agustin")
    rng = RngPNJ("tirar", dado=4)
    legales = TABLERO.destinos_alcanzables("iglesia-san-agustin", 4)
    sala.ejecutar_turno_pnj(rng)
    assert rng.pesos_accion is None
    assert sala.posiciones.obtener(pnj["id"]) in legales
    assert TABLERO.es_ubicacion(sala.posiciones.obtener(pnj["id"]))
    assert sala.ultima_jugada["movimiento_pnj"]["tirada"] == 4
    assert sala.ultima_jugada["sospecha"]["lugar_id"] == sala.posiciones.obtener(pnj["id"])


def test_pnj_en_casilla_intermedia_tira_y_termina_en_destino_legal():
    camino = next(c for c in TABLERO.caminos.values() if c.origen == "parador")
    origen = camino.casillas[1]
    sala, pnj, humano, _ = sala_pnj_tablero(origen)
    legales = TABLERO.destinos_alcanzables(origen, 1)
    sala.ejecutar_turno_pnj(RngPNJ("sospechar", dado=1))
    assert sala.posiciones.obtener(pnj["id"]) in legales
    assert not TABLERO.es_ubicacion(sala.posiciones.obtener(pnj["id"]))
    assert sala.ultima_jugada["tipo"] == "movimiento"
    assert sala.ultima_jugada["movimiento_pnj"]["tirada"] == 1
    assert sala.jugador_en_turno()["id"] == humano["id"]


def test_pnj_prefiere_ubicacion_frente_a_intermedia_si_es_alcanzable():
    camino = next(c for c in TABLERO.caminos.values() if c.origen == "parador")
    origen = camino.casillas[0]
    sala, pnj, _, _ = sala_pnj_tablero(origen)
    rutas = TABLERO.rutas_legales(origen, 2)
    assert any(TABLERO.es_ubicacion(r.destino) for r in rutas)
    assert any(not TABLERO.es_ubicacion(r.destino) for r in rutas)
    sala.ejecutar_turno_pnj(RngPNJ(dado=2))
    assert TABLERO.es_ubicacion(sala.posiciones.obtener(pnj["id"]))
    assert sala.ultima_jugada["sospecha"]["lugar_id"] == sala.posiciones.obtener(pnj["id"])


def test_pnj_elige_entre_varias_ubicaciones_con_rng_inyectado():
    camino = next(c for c in TABLERO.caminos.values() if c.origen == "parador")
    origen = camino.casillas[1]
    sala, pnj, _, _ = sala_pnj_tablero(origen)
    ubicaciones = [
        r.destino for r in TABLERO.rutas_legales(origen, 2)
        if TABLERO.es_ubicacion(r.destino)
    ]
    assert len(ubicaciones) == 2
    sala.ejecutar_turno_pnj(RngPNJ(dado=2, indice_destino=-1))
    assert sala.posiciones.obtener(pnj["id"]) == ubicaciones[-1]


def test_pnj_tablero_refutacion_pnj_automatica_y_humana_detiene_turno():
    sala, pnj, humano, otros = sala_pnj_tablero(con_segundo_pnj=True)
    segundo = otros[0]
    sala.orden_turnos = [pnj["id"], segundo["id"], humano["id"]]
    sala.manos[segundo["id"]] = [CARTA_POR_ID["vera"]]
    sala.ejecutar_turno_pnj(RngPNJ("pasadizo"))
    assert "vera" in sala.vistas[pnj["id"]]
    assert sala.jugador_en_turno()["id"] == segundo["id"]

    sala, pnj, humano, _ = sala_pnj_tablero()
    sala.manos[humano["id"]] = [
        CARTA_POR_ID["vera"],
        CARTA_POR_ID["baul-imperial"],
    ]
    sala.ejecutar_turno_pnj(RngPNJ("pasadizo"))
    assert sala.estado_jugada == JUGADA_ESPERANDO_REFUTADOR
    assert sala.jugador_en_turno()["id"] == pnj["id"]
    assert sala.refutacion_deadline is None


def test_pnj_tablero_humano_eliminado_multimatch_crea_timeout():
    sala, pnj, humano, _ = sala_pnj_tablero()
    humano["activo_investigacion"] = False
    sala.manos[humano["id"]] = [
        CARTA_POR_ID["vera"],
        CARTA_POR_ID["baul-imperial"],
    ]
    sala.ejecutar_turno_pnj(RngPNJ("pasadizo"))
    assert sala.estado_jugada == JUGADA_ESPERANDO_REFUTADOR
    assert sala.refutacion_deadline is not None
    assert main._necesita_timeout_refutacion(sala)


def test_pnj_eliminado_no_recibe_turno_pero_sigue_refutando():
    sala, pnj, humano, otros = sala_pnj_tablero(con_segundo_pnj=True)
    eliminado = otros[0]
    eliminado["activo_investigacion"] = False
    posicion_eliminado = sala.posiciones.obtener(eliminado["id"])
    sala.orden_turnos = [humano["id"], eliminado["id"], pnj["id"]]
    sala.turno_actual = 0
    sala.avanzar_turno()
    assert sala.jugador_en_turno()["id"] == pnj["id"]
    assert sala.posiciones.obtener(eliminado["id"]) == posicion_eliminado

    sala.orden_turnos = [pnj["id"], eliminado["id"], humano["id"]]
    sala.turno_actual = 0
    sala.estado_jugada = JUGADA_ESPERANDO_MOVIMIENTO
    sala.manos[eliminado["id"]] = [CARTA_POR_ID["vera"]]
    sala.ejecutar_turno_pnj(RngPNJ("pasadizo"))
    assert "vera" in sala.vistas[pnj["id"]]
    assert sala.jugador_en_turno()["id"] == humano["id"]
    assert sala.posiciones.obtener(eliminado["id"]) == posicion_eliminado


def test_pnj_resuelve_por_deduccion_legitima_antes_de_mover():
    sala, pnj, _, _ = sala_pnj_tablero()
    sala.misterio = {
        "sospechoso": CARTA_POR_ID["vera"],
        "lugar": CARTA_POR_ID["parador"],
        "objeto": CARTA_POR_ID["libro-hueco"],
    }
    sala.soluciones_deducidas[pnj["id"]] = {
        "sospechoso_id": "vera",
        "lugar_id": "parador",
        "objeto_id": "libro-hueco",
    }
    posicion = sala.posiciones.obtener(pnj["id"])
    sala.ejecutar_turno_pnj(RngPNJ("pasadizo"))
    assert sala.estado == ESTADO_TERMINADA
    assert sala.posiciones.obtener(pnj["id"]) == posicion


def test_trampa_mismo_conocimiento_y_tablero_distinto_misterio_misma_decision():
    resultados = []
    for sospechoso_misterio in ("alvaro", "eulalia"):
        sala, pnj, _, _ = sala_pnj_tablero()
        sala.misterio = {
            "sospechoso": CARTA_POR_ID[sospechoso_misterio],
            "lugar": CARTA_POR_ID["picota"],
            "objeto": CARTA_POR_ID["cantaro-barro"],
        }
        sala.ejecutar_turno_pnj(RngPNJ("pasadizo"))
        resultados.append(
            (
                sala.posiciones.obtener(pnj["id"]),
                sala.ultima_jugada["sospecha"],
                sala.ultima_jugada["movimiento_pnj"],
            )
        )
    assert resultados[0] == resultados[1]


def test_cadena_tablero_cinco_pnj_alcanza_humano_sin_bloqueo(monkeypatch):
    async def escenario():
        sala = Sala("JARA-CADENA-TABLERO", modo=MODO_TABLERO)
        humano = sala.agregar_jugador("Humano", True, personaje_id="vera")
        sala.iniciar(humano["id"])
        pnjs = [j for j in sala.jugadores if j["tipo"] == TIPO_PNJ]
        sala.orden_turnos = [j["id"] for j in pnjs] + [humano["id"]]
        sala.turno_actual = 0
        sala.estado_jugada = JUGADA_ESPERANDO_MOVIMIENTO
        sala.manos = {j["id"]: [] for j in sala.jugadores}
        main.gestor.salas[sala.codigo] = sala
        main.cerrojos[sala.codigo] = asyncio.Lock()
        monkeypatch.setattr(main, "PAUSA_TURNO_PNJ_SEGUNDOS", 0)
        monkeypatch.setattr(main, "PAUSA_TRAS_JUGADA_HUMANA_SEGUNDOS", 0)
        try:
            await main._cadena_turnos_pnj(sala.codigo)
            assert sala.jugador_en_turno()["id"] == humano["id"]
            assert all(sala.posiciones.obtener(j["id"]) for j in pnjs)
        finally:
            main.gestor.salas.pop(sala.codigo, None)
            main.cerrojos.pop(sala.codigo, None)
            main.tareas_pnj.pop(sala.codigo, None)

    asyncio.run(escenario())


def test_programar_dos_veces_en_tablero_no_duplica_tarea_ni_accion(monkeypatch):
    async def escenario():
        sala, pnj, _, _ = sala_pnj_tablero()
        main.gestor.salas[sala.codigo] = sala
        main.cerrojos[sala.codigo] = asyncio.Lock()
        monkeypatch.setattr(main, "PAUSA_TURNO_PNJ_SEGUNDOS", 0)
        llamadas = 0
        original = sala.ejecutar_turno_pnj

        def contar(*args, **kwargs):
            nonlocal llamadas
            llamadas += 1
            return original(RngPNJ("pasadizo"))

        monkeypatch.setattr(sala, "ejecutar_turno_pnj", contar)
        try:
            main.programar_turno_pnj(sala.codigo)
            primera = main.tareas_pnj[sala.codigo]
            main.programar_turno_pnj(sala.codigo)
            assert main.tareas_pnj[sala.codigo] is primera
            await primera
            assert llamadas == 1
            assert sala.jugador_en_turno()["id"] != pnj["id"]
        finally:
            main.gestor.salas.pop(sala.codigo, None)
            main.cerrojos.pop(sala.codigo, None)
            tarea = main.tareas_pnj.pop(sala.codigo, None)
            if tarea and not tarea.done():
                tarea.cancel()

    asyncio.run(escenario())
