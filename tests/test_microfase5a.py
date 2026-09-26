"""Microfase 5A: confirmación integrada de resolver + timeout server-side
para la refutación de humanos eliminados. Sin esperas reales de 3 s."""
import asyncio
import re
import time

import pytest
from fastapi.testclient import TestClient

from app import main
from app.datos.jarandilla import CARTA_POR_ID
from app.main import app, cerrojos, conexiones, gestor
from app.motor.sala import (
    ESTADO_INICIADA,
    INV_VISTA,
    TIMEOUT_REFUTACION_ELIMINADO_SEGUNDOS,
    TIPO_PNJ,
    Sala,
)

cliente = TestClient(app)

SOSPECHA = ("bruno", "puente-parral", "baul-imperial")


def setup_function(_):
    gestor.salas.clear()
    conexiones.clear()


def sala_refutacion(codigo="JARA-5A"):
    sala = Sala(codigo)
    inv = sala.agregar_jugador("Inv", True, personaje_id="vera")
    elim = sala.agregar_jugador("Elim", personaje_id="bruno")
    otro = sala.agregar_jugador("Otro", personaje_id="lucia")
    sala.estado = ESTADO_INICIADA
    sala.orden_turnos = [inv["id"], elim["id"], otro["id"]]
    sala.turno_actual = 0
    return sala, inv, elim, otro


def pendiente_eliminado_multi(sala, inv, elim, otro):
    """Sospecha del investigador con 2 coincidencias del eliminado."""
    elim["activo_investigacion"] = False
    sala.manos = {
        inv["id"]: [CARTA_POR_ID["vera"]],
        elim["id"]: [CARTA_POR_ID["bruno"], CARTA_POR_ID["puente-parral"]],
        otro["id"]: [CARTA_POR_ID["lucia"]],
    }
    sala.formular_sospecha(inv["id"], *SOSPECHA)
    return sala.sospecha_pendiente


class EleccionFija:
    """RNG determinista: demuestra que la carta fluye por random.choice."""

    def __init__(self, fija):
        self.fija = fija
        self.recibidas = None

    def choice(self, opciones):
        self.recibidas = list(opciones)
        return self.fija


# 1. Confirmación de resolver integrada en la UI, sin nativos.
def test_confirmacion_resolver_sin_nativos():
    sala, _ = gestor.crear_sala("Paco")
    pagina = cliente.get(f"/sala/{sala.codigo}")
    assert pagina.status_code == 200
    html = pagina.text
    for aguja in (
        'id="modal-confirmar-resolver"',
        'id="conf-resolver-cartas"',
        'id="btn-enviar-resolver"',
        'id="btn-cancelar-confirmar-resolver"',
        "¿RESOLVER EL MISTERIO?",
        "Si la acusación es incorrecta quedarás eliminado como investigador.",
        "CANCELAR",
        "RESOLVER EL MISTERIO",
        'id="aviso-timeout-refutacion"',
    ):
        assert aguja in html
    js = cliente.get("/static/js/sala.js")
    assert js.status_code == 200
    texto = js.text
    assert "modal-confirmar-resolver" in texto
    assert "btn-enviar-resolver" in texto
    assert "window.confirm" not in texto
    assert not re.search(r"[^a-zA-Z]confirm\s*\(", texto)
    assert not re.search(r"[^a-zA-Z]alert\s*\(", texto)
    assert not re.search(r"[^a-zA-Z]prompt\s*\(", texto)


def test_constante_timeout_tres_segundos():
    assert TIMEOUT_REFUTACION_ELIMINADO_SEGUNDOS == 3.0


# 2. Humano eliminado con UNA coincidencia: resolución normal inmediata.
def test_eliminado_una_coincidencia_resuelve_al_momento():
    sala, inv, elim, otro = sala_refutacion()
    elim["activo_investigacion"] = False
    sala.manos = {
        inv["id"]: [CARTA_POR_ID["vera"]],
        elim["id"]: [CARTA_POR_ID["bruno"]],
        otro["id"]: [CARTA_POR_ID["lucia"]],
    }
    sala.formular_sospecha(inv["id"], *SOSPECHA)
    assert sala.sospecha_pendiente is None
    assert sala.refutacion_deadline is None
    assert sala.turno_actual == 2  # salta al eliminado
    assert sala.estado_carta(inv["id"], "bruno") == INV_VISTA
    assert sala.ultima_jugada["refutador_id"] == elim["id"]


# 3. Humano eliminado con VARIAS: pendiente + deadline + opciones.
def test_eliminado_varias_pendiente_con_deadline_y_opciones():
    sala, inv, elim, otro = sala_refutacion()
    pendiente_eliminado_multi(sala, inv, elim, otro)
    assert sala.sospecha_pendiente is not None
    assert sala.turno_actual == 0  # aún no avanza
    restante = sala.refutacion_deadline - time.monotonic()
    assert 0 < restante <= TIMEOUT_REFUTACION_ELIMINADO_SEGUNDOS
    privada = sala.estado_privado(elim["id"])
    assert {c["id"] for c in privada["jugada"]["opciones_refutacion"]} == {
        "bruno",
        "puente-parral",
    }
    assert privada["jugada"]["timeout_refutacion_seg"] == 3.0
    # El investigador aún no ve nada; nadie más ve opciones ni plazo.
    assert "opciones_refutacion" not in sala.estado_privado(inv["id"])["jugada"]
    assert "timeout_refutacion_seg" not in sala.estado_privado(inv["id"])["jugada"]
    assert "opciones_refutacion" not in sala.estado_privado(otro["id"])["jugada"]


# 4. Puede elegir antes del timeout (manual gana).
def test_eliminado_varias_elige_antes_del_timeout():
    sala, inv, elim, otro = sala_refutacion()
    pendiente_eliminado_multi(sala, inv, elim, otro)
    assert sala.resolver_refutacion_eliminado_auto() is None  # plazo vigente
    sala.mostrar_carta(elim["id"], "puente-parral")
    assert sala.sospecha_pendiente is None
    assert sala.refutacion_deadline is None
    assert sala.turno_actual == 2
    assert sala.estado_carta(inv["id"], "puente-parral") == INV_VISTA
    assert sala.estado_privado(inv["id"])["jugada"]["carta_mostrada"]["id"] == (
        "puente-parral"
    )


# 5. Sin respuesta: el servidor elige entre las coincidencias.
def test_timeout_elige_entre_coincidencias_y_registra_vista():
    sala, inv, elim, otro = sala_refutacion()
    pendiente_eliminado_multi(sala, inv, elim, otro)
    sala.refutacion_deadline = time.monotonic() - 5  # plazo vencido
    rng = EleccionFija("puente-parral")
    elegida = sala.resolver_refutacion_eliminado_auto(rng=rng)
    assert elegida == "puente-parral"
    assert set(rng.recibidas) == {"bruno", "puente-parral"}  # pasa por choice
    assert sala.sospecha_pendiente is None
    assert sala.refutacion_deadline is None
    assert sala.turno_actual == 2
    assert sala.estado_carta(inv["id"], "puente-parral") == INV_VISTA
    assert sala.estado_carta(inv["id"], "bruno") != INV_VISTA


# 6. La carta automática es privada del investigador.
def test_timeout_no_expone_otras_opciones_ni_carta():
    sala, inv, elim, otro = sala_refutacion()
    pendiente_eliminado_multi(sala, inv, elim, otro)
    sala.refutacion_deadline = time.monotonic() - 5
    elegida = sala.resolver_refutacion_eliminado_auto(rng=EleccionFija("bruno"))
    assert elegida in {"bruno", "puente-parral"}
    publico = repr(sala.estado_publico())
    assert "carta_id" not in publico and "carta_mostrada" not in publico
    assert sala.estado_privado(inv["id"])["jugada"]["carta_mostrada"]["id"] == elegida
    for j in (elim, otro):
        assert "carta_mostrada" not in sala.estado_privado(j["id"])["jugada"]
        assert "opciones_refutacion" not in sala.estado_privado(j["id"])["jugada"]


# 7a. Carrera: la manual gana, la automática es no-op (un solo turno).
def test_carrera_manual_gana_auto_es_noop():
    sala, inv, elim, _ = sala_refutacion()
    pendiente_eliminado_multi(sala, inv, elim, sala.jugador_por_id(sala.orden_turnos[2]))
    sala.mostrar_carta(elim["id"], "bruno")
    turno = sala.turno_actual
    assert turno == 2
    assert sala.resolver_refutacion_eliminado_auto() is None
    assert sala.turno_actual == turno
    assert sala.ultima_jugada["carta_id"] == "bruno"


# 7b. Carrera: la automática gana, la manual es rechazada (un solo turno).
def test_carrera_auto_gana_manual_rechazada():
    sala, inv, elim, _ = sala_refutacion()
    pendiente_eliminado_multi(sala, inv, elim, sala.jugador_por_id(sala.orden_turnos[2]))
    sala.refutacion_deadline = time.monotonic() - 5
    assert sala.resolver_refutacion_eliminado_auto(rng=EleccionFija("bruno")) == "bruno"
    turno = sala.turno_actual
    assert turno == 2
    with pytest.raises(ValueError):
        sala.mostrar_carta(elim["id"], "puente-parral")
    assert sala.turno_actual == turno
    assert sala.ultima_jugada["carta_id"] == "bruno"


# 8. Humano ACTIVO con varias: sin timeout (comportamiento actual).
def test_activo_varias_sin_timeout_ni_auto():
    sala, inv, elim, otro = sala_refutacion()
    sala.manos = {
        inv["id"]: [CARTA_POR_ID["vera"]],
        elim["id"]: [CARTA_POR_ID["bruno"], CARTA_POR_ID["puente-parral"]],
        otro["id"]: [CARTA_POR_ID["lucia"]],
    }
    sala.formular_sospecha(inv["id"], *SOSPECHA)
    assert sala.refutacion_deadline is None
    assert sala.resolver_refutacion_eliminado_auto() is None
    assert sala.turno_actual == 0
    privada = sala.estado_privado(elim["id"])
    assert "opciones_refutacion" in privada["jugada"]
    assert "timeout_refutacion_seg" not in privada["jugada"]
    sala.mostrar_carta(elim["id"], "bruno")  # manual intacta
    assert sala.turno_actual == 1  # el refutador activo sigue en la rueda


# 9. El plazo no se reinicia por reconexión ( deadline estable + opciones ).
def test_timeout_no_se_reinicia_por_reconexion():
    sala = cliente.post("/api/partidas", json={"alias": "Paco"}).json()
    ana = cliente.post(
        f"/api/partidas/{sala['codigo']}/unirse", json={"alias": "Ana"}
    ).json()
    luis = cliente.post(
        f"/api/partidas/{sala['codigo']}/unirse", json={"alias": "Luis"}
    ).json()
    codigo = sala["codigo"]
    try:
        srv = gestor.obtener(codigo)
        srv.elegir_personaje(sala["jugador_id"], "vera")
        srv.elegir_personaje(ana["jugador_id"], "bruno")
        srv.elegir_personaje(luis["jugador_id"], "lucia")
        with cliente.websocket_connect(
            f"/ws/{codigo}/{sala['jugador_id']}"
        ) as ws_paco:
            ws_paco.receive_json()
            ws_paco.send_json({"accion": "iniciar"})
            ws_paco.receive_json()
            # Mesa determinista: Ana eliminada con 2 coincidencias.
            ids = {j["alias"]: j["id"] for j in srv.jugadores}
            srv.jugador_por_id(ids["Ana"])["activo_investigacion"] = False
            srv.manos = {jid: [] for jid in srv.orden_turnos}
            srv.manos[ids["Ana"]] = [
                CARTA_POR_ID["bruno"],
                CARTA_POR_ID["puente-parral"],
            ]
            srv.orden_turnos = [ids["Paco"], ids["Ana"], ids["Luis"]] + [
                jid for jid in srv.orden_turnos if jid not in ids.values()
            ]
            srv.turno_actual = 0
            ws_paco.send_json(
                {
                    "accion": "formular_sospecha",
                    "sospechoso_id": "bruno",
                    "lugar_id": "puente-parral",
                    "objeto_id": "baul-imperial",
                }
            )
            ws_paco.receive_json()
            assert srv.sospecha_pendiente is not None
            deadline_antes = srv.refutacion_deadline
            assert deadline_antes is not None
        # Reconexión de la eliminada: recibe opciones con el mismo plazo.
        with cliente.websocket_connect(
            f"/ws/{codigo}/{ana['jugador_id']}"
        ) as ws_ana:
            jugada = ws_ana.receive_json()["sala"]["jugada"]
            assert {c["id"] for c in jugada["opciones_refutacion"]} == {
                "bruno",
                "puente-parral",
            }
            assert jugada["timeout_refutacion_seg"] == 3.0
        assert srv.refutacion_deadline == deadline_antes
        assert srv.sospecha_pendiente is not None
    finally:
        for registro in (gestor.salas, conexiones, cerrojos):
            registro.pop(codigo, None)
        main.tareas_pnj.pop(codigo, None)
        tarea = main.tareas_refutacion.pop(codigo, None)
        if tarea:
            tarea.cancel()


# 10. Watchdog: una sola tarea, resuelve y programa la cadena una vez.
def test_watchdog_unica_tarea_resuelve_y_programa_una_vez(monkeypatch):
    async def escenario():
        sala, inv, elim, otro = sala_refutacion("JARA-5A-WD")
        pendiente_eliminado_multi(sala, inv, elim, otro)
        sala.refutacion_deadline = time.monotonic() - 5  # ya vencido
        main.gestor.salas[sala.codigo] = sala
        main.cerrojos[sala.codigo] = asyncio.Lock()
        main.programar_timeout_refutacion(sala.codigo)
        main.programar_timeout_refutacion(sala.codigo)
        tarea = main.tareas_refutacion.get(sala.codigo)
        assert tarea is not None and not tarea.done()
        llamadas = []
        monkeypatch.setattr(
            main, "programar_turno_pnj", lambda c: llamadas.append(c)
        )
        await asyncio.wait_for(tarea, timeout=2)
        assert llamadas == [sala.codigo]
        assert sala.sospecha_pendiente is None
        assert sala.turno_actual == 2
        assert sala.codigo not in main.tareas_refutacion

    asyncio.run(escenario())
    main.gestor.salas.pop("JARA-5A-WD", None)
    main.cerrojos.pop("JARA-5A-WD", None)
    main.tareas_refutacion.pop("JARA-5A-WD", None)


# 11. La elección manual cancela el watchdog pendiente.
def test_manual_cancela_watchdog():
    async def escenario():
        sala, inv, elim, otro = sala_refutacion("JARA-5A-CX")
        pendiente_eliminado_multi(sala, inv, elim, otro)
        main.gestor.salas[sala.codigo] = sala
        main.cerrojos[sala.codigo] = asyncio.Lock()
        main.programar_timeout_refutacion(sala.codigo)
        tarea = main.tareas_refutacion.get(sala.codigo)
        assert tarea is not None
        main.cancelar_timeout_refutacion(sala.codigo)
        assert sala.codigo not in main.tareas_refutacion
        try:
            await tarea
        except asyncio.CancelledError:
            pass
        # Sin tarea viva, reprogramar es posible pero no duplica.
        main.programar_timeout_refutacion(sala.codigo)
        assert sala.codigo in main.tareas_refutacion
        main.cancelar_timeout_refutacion(sala.codigo)

    asyncio.run(escenario())
    main.gestor.salas.pop("JARA-5A-CX", None)
    main.cerrojos.pop("JARA-5A-CX", None)
    main.tareas_refutacion.pop("JARA-5A-CX", None)


# 12. No se programa watchdog cuando no procede.
def test_sin_watchdog_si_no_procede():
    async def escenario():
        sala, inv, elim, otro = sala_refutacion("JARA-5A-NO")
        main.gestor.salas[sala.codigo] = sala
        main.programar_timeout_refutacion(sala.codigo)  # sin pendiente
        assert sala.codigo not in main.tareas_refutacion
        # Activo con varias: pendiente pero sin deadline ni tarea.
        sala.manos = {
            inv["id"]: [CARTA_POR_ID["vera"]],
            elim["id"]: [CARTA_POR_ID["bruno"], CARTA_POR_ID["puente-parral"]],
            otro["id"]: [CARTA_POR_ID["lucia"]],
        }
        sala.formular_sospecha(inv["id"], *SOSPECHA)
        main.programar_timeout_refutacion(sala.codigo)
        assert sala.codigo not in main.tareas_refutacion

    asyncio.run(escenario())
    main.gestor.salas.pop("JARA-5A-NO", None)


def _mesa_pnj_contra_eliminado(codigo="JARA-5A-PNJ"):
    """PNJ en turno que sospechará contra un humano eliminado con 2 cartas."""
    sala = Sala(codigo)
    pnj = sala.agregar_jugador("PnjInv", tipo=TIPO_PNJ, personaje_id="lucia")
    elim = sala.agregar_jugador("Elim", personaje_id="bruno")
    otro = sala.agregar_jugador("Otro", personaje_id="vera")
    sala.estado = ESTADO_INICIADA
    sala.orden_turnos = [pnj["id"], elim["id"], otro["id"]]
    sala.turno_actual = 0
    elim["activo_investigacion"] = False
    sala.manos = {
        pnj["id"]: [CARTA_POR_ID["parador"]],
        elim["id"]: [CARTA_POR_ID["bruno"], CARTA_POR_ID["puente-parral"]],
        otro["id"]: [CARTA_POR_ID["lucia"]],
    }
    return sala, pnj, elim, otro


# 13. Regresión del bug real: PNJ investiga, eliminado no responde y el
# servidor resuelve solo. Reloj virtual: sin esperas reales, pero con la
# cadena, el watchdog y la resolución reales encadenados.
def test_timeout_real_dispara_en_flujo_pnj(monkeypatch):
    reloj = {"t": 1000.0}
    duraciones = []
    sueño_real = asyncio.sleep

    async def falso_sleep(seg):
        duraciones.append(seg)
        reloj["t"] += seg
        await sueño_real(0)  # cede el turno, sin espera real

    monkeypatch.setattr(time, "monotonic", lambda: reloj["t"])
    monkeypatch.setattr(asyncio, "sleep", falso_sleep)

    async def escenario():
        sala, pnj, elim, otro = _mesa_pnj_contra_eliminado()
        # Sospecha determinista; formular/buscar/resolver siguen reales.
        monkeypatch.setattr(
            sala,
            "elegir_sospecha_pnj",
            lambda jugador_id, rng=None: {
                "sospechoso_id": "bruno",
                "lugar_id": "puente-parral",
                "objeto_id": "baul-imperial",
            },
        )
        main.gestor.salas[sala.codigo] = sala
        main.cerrojos[sala.codigo] = asyncio.Lock()
        llamadas = []
        programar_real = main.programar_timeout_refutacion
        monkeypatch.setattr(
            main,
            "programar_timeout_refutacion",
            lambda c: (llamadas.append(c), programar_real(c)),
        )
        cadena = asyncio.create_task(main._cadena_turnos_pnj(sala.codigo))
        await asyncio.wait_for(cadena, timeout=5)
        # El watchdog se programó solo desde el flujo PNJ, sin ningún WS.
        assert llamadas == [sala.codigo]
        assert main.conexiones.get(sala.codigo) is None
        # Drena watchdog + cadena reanudada (tareas reales, tiempo virtual).
        for _ in range(10):
            vivas = [
                t
                for t in (
                    main.tareas_refutacion.get(sala.codigo),
                    main.tareas_pnj.get(sala.codigo),
                )
                if t is not None and not t.done()
            ]
            if not vivas:
                break
            await asyncio.wait_for(
                asyncio.gather(*vivas, return_exceptions=True), timeout=5
            )
        return sala

    codigo = "JARA-5A-PNJ"
    try:
        sala = asyncio.run(escenario())
    finally:
        main.gestor.salas.pop(codigo, None)
        main.cerrojos.pop(codigo, None)
        main.tareas_pnj.pop(codigo, None)
        main.tareas_refutacion.pop(codigo, None)

    # Sin respuesta humana: una coincidencia válida, VISTA solo del PNJ.
    ultima = sala.ultima_jugada
    assert ultima["resultado"] == "refutada"
    assert ultima["investigador_id"] == sala.jugador_por_id(
        sala.orden_turnos[0]
    )["id"]
    assert ultima["refutador_id"] == sala.jugador_por_id(
        sala.orden_turnos[1]
    )["id"]
    assert ultima["carta_id"] in {"bruno", "puente-parral"}
    assert sala.vistas[sala.orden_turnos[0]] == {ultima["carta_id"]}
    # Un solo avance, sin pendiente ni deadline, cadena reanudada y quieta.
    assert sala.turno_actual == 2
    assert sala.sospecha_pendiente is None
    assert sala.refutacion_deadline is None
    assert sala.codigo not in main.tareas_refutacion
    assert sala.codigo not in main.tareas_pnj
    # Dos pausas y nada más: ritmo PNJ + timeout (sin reinicios ni dobles).
    assert len(duraciones) == 2
    assert duraciones[0] == pytest.approx(3.0)
    assert duraciones[1] == pytest.approx(3.0)


# 14. Con investigador PNJ la elección manual previa también gana.
def test_pnj_investigador_manual_gana_antes_del_timeout():
    sala, pnj, elim, _ = _mesa_pnj_contra_eliminado("JARA-5A-PNJM")
    sala.formular_sospecha(pnj["id"], *SOSPECHA)  # vía real de la cadena
    assert sala.refutacion_deadline is not None
    sala.mostrar_carta(elim["id"], "bruno")
    assert sala.sospecha_pendiente is None
    assert sala.refutacion_deadline is None
    assert sala.turno_actual == 2
    assert sala.estado_carta(pnj["id"], "bruno") == INV_VISTA
    assert sala.estado_privado(pnj["id"])["jugada"]["carta_mostrada"]["id"] == (
        "bruno"
    )
