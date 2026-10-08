"""Confirmación integrada de resolver + timeout server-side de refutación."""
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
    JUGADA_ESPERANDO_REFUTADOR,
    JUGADA_ESPERANDO_SOSPECHA,
    JUGADA_PRESENTANDO_SOSPECHA,
    PAUSA_PRESENTACION_HUMANO_SEGUNDOS,
    PAUSA_PRESENTACION_PNJ_SEGUNDOS,
    PAUSA_PRESENTACION_RESULTADO_SEGUNDOS,
    TIMEOUT_REFUTACION_HUMANO_SEGUNDOS,
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
    sala.actualizar_presentacion_sospecha(ahora=float("inf"))
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


def test_seleccion_refutacion_usa_el_mismo_patron_que_sospecha():
    """La referencia canónica es FORMULAR SOSPECHA, que ya funciona.

    Sospecha: un listener por carta vía `alPulsar` que desmarca a las demás y
    marca la pulsada. La refutación usa exactamente ese patrón: sin delegación,
    sin eventos especiales y sin un segundo sistema de selección.
    """
    texto = cliente.get("/static/js/sala.js").text
    refutacion = texto[
        texto.index("const opciones = Array.isArray(jugada.opciones_refutacion)"):
        texto.index("// Aviso server-side de plazo")
    ]
    sospecha = texto[
        texto.index("function crearGrupoSelector(categoria)"):
        texto.index("const etiquetaS = document.createElement")
    ]
    # 1. El mismo patrón: `alPulsar` por carta, sin delegación.
    assert "alPulsar" in sospecha
    assert "alPulsar" in refutacion
    assert "opcionesRefutacion.addEventListener" not in refutacion
    assert "seleccionarCartaRefutacion" not in texto
    # 2. Desmarca a las demás y marca la pulsada (igual que sospecha).
    assert 'opcion.classList.remove("seleccionada")' in refutacion
    assert 'opcion.setAttribute("aria-pressed", "false")' in refutacion
    assert 'boton.classList.add("seleccionada")' in refutacion
    assert 'boton.setAttribute("aria-pressed", "true")' in refutacion
    # 3. Guarda el id y actualiza los botones.
    assert "cartaRefutacionSeleccionadaId = carta.id;" in refutacion
    assert "actualizarAccionesRefutacion(opciones.length)" in refutacion
    # 4. REFUTAR envía exactamente el id seleccionado.
    assert "carta_id: cartaRefutacionSeleccionadaId," in texto
    # 5. Con varias cartas no se preselecciona ninguna.
    assert "opciones.length === 1" in refutacion


def test_timeout_real_por_watchdog_no_deja_obligacion_al_refutador():
    """PRUEBA REAL del timeout: la cadena del watchdog, no resolver_* a mano."""
    sala, inv, ref, otro = _refutador_humano_con_dos("JARA-5A-31B-WD")
    main.gestor.salas[sala.codigo] = sala
    main.cerrojos[sala.codigo] = asyncio.Lock()
    try:
        assert main._necesita_timeout_refutacion(sala)
        assert [c["id"] for c in sala.estado_privado(ref["id"])["jugada"][
            "opciones_refutacion"
        ]] == ["bruno", "puente-parral"]

        async def watchdog():
            # Solo se adelanta el reloj: la resolución la hace main.py.
            sala.refutacion_deadline = time.monotonic() - 0.2
            main.programar_timeout_refutacion(sala.codigo)
            for _ in range(100):
                await asyncio.sleep(0.02)
                if sala.codigo not in main.tareas_refutacion:
                    return
            raise AssertionError("el watchdog no terminó")

        asyncio.run(watchdog())

        # Mismo estado canónico que después de CONTINUAR.
        assert sala.sospecha_pendiente is None
        assert sala.refutacion_deadline is None
        cerrar_resultado(sala)
        assert sala.estado_jugada == JUGADA_ESPERANDO_SOSPECHA
        assert sala.ultima_jugada["resultado"] == "refutada"
        assert sala.ultima_jugada["carta_id"] in {"bruno", "puente-parral"}
        privada = sala.estado_privado(ref["id"])["jugada"]
        assert "opciones_refutacion" not in privada
        assert "timeout_refutacion_seg" not in privada
        assert "carta_mostrada" not in privada
        # El investigador recibe la carta y el juego continúa.
        assert sala.estado_carta(inv["id"], sala.ultima_jugada["carta_id"]) == INV_VISTA
        assert sala.estado_privado(inv["id"])["jugada"]["carta_mostrada"]["id"] == (
            sala.ultima_jugada["carta_id"]
        )
        cerrar_resultado(sala)
        assert sala.turno_actual == 1
    finally:
        for registro in (gestor.salas, conexiones, cerrojos):
            registro.pop(sala.codigo, None)
        main.tareas_pnj.pop(sala.codigo, None)
        main.tareas_presentacion.pop(sala.codigo, None)
        tarea = main.tareas_refutacion.pop(sala.codigo, None)
        if tarea:
            tarea.cancel()


def test_timeout_humano_unico_de_diez_segundos():
    assert TIMEOUT_REFUTACION_HUMANO_SEGUNDOS == 10.0


# 2. Humano eliminado con UNA coincidencia: resolución normal inmediata.
def test_eliminado_una_coincidencia_tiene_timeout_y_puede_confirmar():
    sala, inv, elim, otro = sala_refutacion()
    elim["activo_investigacion"] = False
    sala.manos = {
        inv["id"]: [CARTA_POR_ID["vera"]],
        elim["id"]: [CARTA_POR_ID["bruno"]],
        otro["id"]: [CARTA_POR_ID["lucia"]],
    }
    sala.formular_sospecha(inv["id"], *SOSPECHA)
    sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    assert sala.sospecha_pendiente is not None
    assert 0 < sala.refutacion_deadline - time.monotonic() <= 10.0
    cerrar_resultado(sala)
    assert sala.turno_actual == 0
    assert [
        carta["id"]
        for carta in sala.estado_privado(elim["id"])["jugada"]["opciones_refutacion"]
    ] == ["bruno"]
    assert "opciones_refutacion" not in sala.estado_privado(inv["id"])["jugada"]
    assert sala.estado_carta(inv["id"], "bruno") != INV_VISTA

    sala.mostrar_carta(elim["id"], "bruno")
    assert sala.sospecha_pendiente is None
    cerrar_resultado(sala)
    assert sala.turno_actual == 2  # salta al eliminado
    assert sala.estado_carta(inv["id"], "bruno") == INV_VISTA
    assert sala.ultima_jugada["refutador_id"] == elim["id"]


def test_activo_una_coincidencia_refuta_automaticamente_a_los_diez_segundos():
    sala, inv, refutador, otro = sala_refutacion()
    sala.manos = {
        inv["id"]: [CARTA_POR_ID["vera"]],
        refutador["id"]: [CARTA_POR_ID["bruno"]],
        otro["id"]: [CARTA_POR_ID["lucia"]],
    }
    sala.formular_sospecha(inv["id"], *SOSPECHA)
    sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    assert sala.refutacion_deadline is not None
    sala.refutacion_deadline = time.monotonic() - 0.01

    assert sala.resolver_refutacion_auto() == "bruno"
    assert sala.sospecha_pendiente is None
    assert sala.estado_carta(inv["id"], "bruno") == INV_VISTA
    cerrar_resultado(sala)
    assert sala.turno_actual == 1


# 3. Humano eliminado con VARIAS: pendiente + deadline + opciones.
def test_eliminado_varias_pendiente_con_deadline_y_opciones():
    sala, inv, elim, otro = sala_refutacion()
    pendiente_eliminado_multi(sala, inv, elim, otro)
    assert sala.sospecha_pendiente is not None
    cerrar_resultado(sala)
    assert sala.turno_actual == 0  # aún no avanza
    restante = sala.refutacion_deadline - time.monotonic()
    assert 0 < restante <= TIMEOUT_REFUTACION_HUMANO_SEGUNDOS
    privada = sala.estado_privado(elim["id"])
    assert {c["id"] for c in privada["jugada"]["opciones_refutacion"]} == {
        "bruno",
        "puente-parral",
    }
    assert privada["jugada"]["timeout_refutacion_seg"] == 10.0
    # El investigador aún no ve nada; nadie más ve opciones ni plazo.
    assert "opciones_refutacion" not in sala.estado_privado(inv["id"])["jugada"]
    assert "timeout_refutacion_seg" not in sala.estado_privado(inv["id"])["jugada"]
    assert "opciones_refutacion" not in sala.estado_privado(otro["id"])["jugada"]


# 4. Puede elegir antes del timeout (manual gana).
def test_eliminado_varias_elige_antes_del_timeout():
    sala, inv, elim, otro = sala_refutacion()
    pendiente_eliminado_multi(sala, inv, elim, otro)
    assert sala.resolver_refutacion_auto() is None  # plazo vigente
    sala.mostrar_carta(elim["id"], "puente-parral")
    assert sala.sospecha_pendiente is None
    assert sala.refutacion_deadline is None
    cerrar_resultado(sala)
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
    elegida = sala.resolver_refutacion_auto(rng=rng)
    assert elegida == "puente-parral"
    assert set(rng.recibidas) == {"bruno", "puente-parral"}  # pasa por choice
    assert sala.sospecha_pendiente is None
    assert sala.refutacion_deadline is None
    cerrar_resultado(sala)
    assert sala.turno_actual == 2
    assert sala.estado_carta(inv["id"], "puente-parral") == INV_VISTA
    assert sala.estado_carta(inv["id"], "bruno") != INV_VISTA


# 6. La carta automática es privada del investigador.
def test_timeout_no_expone_otras_opciones_ni_carta():
    sala, inv, elim, otro = sala_refutacion()
    pendiente_eliminado_multi(sala, inv, elim, otro)
    sala.refutacion_deadline = time.monotonic() - 5
    elegida = sala.resolver_refutacion_auto(rng=EleccionFija("bruno"))
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
    cerrar_resultado(sala)
    turno = sala.turno_actual
    assert turno == 2
    assert sala.resolver_refutacion_auto() is None
    cerrar_resultado(sala)
    assert sala.turno_actual == turno
    assert sala.ultima_jugada["carta_id"] == "bruno"


# 7b. Carrera: la automática gana, la manual es rechazada (un solo turno).
def test_carrera_auto_gana_manual_rechazada():
    sala, inv, elim, _ = sala_refutacion()
    pendiente_eliminado_multi(sala, inv, elim, sala.jugador_por_id(sala.orden_turnos[2]))
    sala.refutacion_deadline = time.monotonic() - 5
    assert sala.resolver_refutacion_auto(rng=EleccionFija("bruno")) == "bruno"
    cerrar_resultado(sala)
    turno = sala.turno_actual
    assert turno == 2
    with pytest.raises(ValueError):
        sala.mostrar_carta(elim["id"], "puente-parral")
    cerrar_resultado(sala)
    assert sala.turno_actual == turno
    assert sala.ultima_jugada["carta_id"] == "bruno"


# 8. Humano ACTIVO con varias: mismo timeout canónico.
def test_activo_varias_tiene_timeout_y_auto():
    sala, inv, elim, otro = sala_refutacion()
    sala.manos = {
        inv["id"]: [CARTA_POR_ID["vera"]],
        elim["id"]: [CARTA_POR_ID["bruno"], CARTA_POR_ID["puente-parral"]],
        otro["id"]: [CARTA_POR_ID["lucia"]],
    }
    sala.formular_sospecha(inv["id"], *SOSPECHA)
    sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    assert 0 < sala.refutacion_deadline - time.monotonic() <= 10.0
    assert sala.resolver_refutacion_auto() is None
    cerrar_resultado(sala)
    assert sala.turno_actual == 0
    privada = sala.estado_privado(elim["id"])
    assert "opciones_refutacion" in privada["jugada"]
    assert privada["jugada"]["timeout_refutacion_seg"] == 10.0
    sala.mostrar_carta(elim["id"], "bruno")  # manual intacta
    cerrar_resultado(sala)
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
            main.cancelar_presentacion_sospecha(codigo)
            srv.actualizar_presentacion_sospecha(ahora=float("inf"))
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
            assert jugada["timeout_refutacion_seg"] == 10.0
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
        cerrar_resultado(sala)
        assert sala.turno_actual == 2
        assert sala.codigo not in main.tareas_refutacion

    asyncio.run(escenario())
    main.gestor.salas.pop("JARA-5A-WD", None)
    main.cerrojos.pop("JARA-5A-WD", None)
    main.tareas_refutacion.pop("JARA-5A-WD", None)


# 11. La elección manual cancela el watchdog pendiente.
def test_watchdog_resuelve_humano_activo_con_una_coincidencia(monkeypatch):
    async def escenario():
        sala, inv, refutador, otro = sala_refutacion("JARA-5A-WD1")
        sala.manos = {
            inv["id"]: [CARTA_POR_ID["vera"]],
            refutador["id"]: [CARTA_POR_ID["bruno"]],
            otro["id"]: [CARTA_POR_ID["lucia"]],
        }
        sala.formular_sospecha(inv["id"], *SOSPECHA)
        sala.actualizar_presentacion_sospecha(ahora=float("inf"))
        sala.refutacion_deadline = time.monotonic() - 0.01
        main.gestor.salas[sala.codigo] = sala
        main.cerrojos[sala.codigo] = asyncio.Lock()
        monkeypatch.setattr(main, "programar_turno_pnj", lambda _codigo: None)
        main.programar_timeout_refutacion(sala.codigo)
        tarea = main.tareas_refutacion.get(sala.codigo)
        assert tarea is not None
        await asyncio.wait_for(tarea, timeout=2)
        assert sala.sospecha_pendiente is None
        assert sala.ultima_jugada["carta_id"] == "bruno"
        assert sala.estado_carta(inv["id"], "bruno") == INV_VISTA

    asyncio.run(escenario())
    main.gestor.salas.pop("JARA-5A-WD1", None)
    main.cerrojos.pop("JARA-5A-WD1", None)
    main.tareas_refutacion.pop("JARA-5A-WD1", None)


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


# 12. No se programa watchdog sin una refutación humana pendiente.
def test_sin_watchdog_si_no_procede():
    async def escenario():
        sala, inv, elim, otro = sala_refutacion("JARA-5A-NO")
        main.gestor.salas[sala.codigo] = sala
        main.programar_timeout_refutacion(sala.codigo)  # sin pendiente
        assert sala.codigo not in main.tareas_refutacion
        # Activo con varias: ahora sí comparte deadline y watchdog.
        sala.manos = {
            inv["id"]: [CARTA_POR_ID["vera"]],
            elim["id"]: [CARTA_POR_ID["bruno"], CARTA_POR_ID["puente-parral"]],
            otro["id"]: [CARTA_POR_ID["lucia"]],
        }
        sala.formular_sospecha(inv["id"], *SOSPECHA)
        sala.actualizar_presentacion_sospecha(ahora=float("inf"))
        main.programar_timeout_refutacion(sala.codigo)
        assert sala.codigo in main.tareas_refutacion
        main.cancelar_timeout_refutacion(sala.codigo)

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
        # Flujo canónico encadenado: PRESENTACIÓN (8B.30) → REFUTACIÓN con
        # timeout → RESULTADO PÚBLICO (8B.31C) → avance de turno. Con reloj
        # virtual ya no se mira el registro a mitad de vuelo (la tarea de
        # presentación puede ya haber terminado): se drena hasta la calma.
        for _ in range(12):
            vivas = [
                t
                for t in (
                    main.tareas_presentacion.get(sala.codigo),
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
        # El watchdog se programó solo desde el flujo PNJ, sin ningún WS.
        # Dos llamadas: al cerrar la presentación de sospecha (8B.30) y al
        # cerrar la de resultado (8B.31C), donde ya es un no-op porque no
        # queda refutación pendiente.
        assert set(llamadas) == {sala.codigo}
        assert len(llamadas) == 2
        assert main.conexiones.get(sala.codigo) is None
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
    cerrar_resultado(sala)
    assert sala.turno_actual == 2
    assert sala.sospecha_pendiente is None
    assert sala.refutacion_deadline is None
    assert sala.codigo not in main.tareas_refutacion
    assert sala.codigo not in main.tareas_pnj
    # Ritmo PNJ + presentación de sospecha + timeout de refutación + los dos
    # tramos del plazo del resultado público, sin reinicios. El watchdog
    # duerme siempre hasta el deadline pendiente MÁS PRÓXIMO: primero el de
    # los PNJ (3 s) y después el que le queda al humano (14 s − 3 s ya
    # consumidos). Los 10 s de la sospecha y los 10 s de la refutación
    # siguen siendo los de antes.
    assert duraciones == [
        3.0,
        PAUSA_PRESENTACION_HUMANO_SEGUNDOS,
        TIMEOUT_REFUTACION_HUMANO_SEGUNDOS,
        PAUSA_PRESENTACION_PNJ_SEGUNDOS,
        PAUSA_PRESENTACION_RESULTADO_SEGUNDOS - PAUSA_PRESENTACION_PNJ_SEGUNDOS,
    ]


# 14. Con investigador PNJ la elección manual previa también gana.
def test_pnj_investigador_manual_gana_antes_del_timeout():
    sala, pnj, elim, _ = _mesa_pnj_contra_eliminado("JARA-5A-PNJM")
    sala.formular_sospecha(pnj["id"], *SOSPECHA)  # vía real de la cadena
    sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    assert sala.refutacion_deadline is not None
    sala.mostrar_carta(elim["id"], "bruno")
    assert sala.sospecha_pendiente is None
    assert sala.refutacion_deadline is None
    cerrar_resultado(sala)
    assert sala.turno_actual == 2
    assert sala.estado_carta(pnj["id"], "bruno") == INV_VISTA
    assert sala.estado_privado(pnj["id"])["jugada"]["carta_mostrada"]["id"] == (
        "bruno"
    )


# ---------------------------------------------------------------------------
# 8B.31B · CONTINUAR sin elegir = refutación automática FINAL.
# Tres caminos de salida del mismo popup (elegir+REFUTAR, CONTINUAR, timeout)
# terminan la refutación por la misma ruta interna. Ninguno devuelve al
# refutador a la elección ni le abre un segundo popup.
# ---------------------------------------------------------------------------


def _refutador_humano_con_dos(codigo="JARA-5A-31B"):
    """Humano refutador ACTIVO con dos coincidencias (A=bruno, B=puente-parral)."""
    sala, inv, ref, otro = sala_refutacion(codigo)
    sala.manos = {
        inv["id"]: [CARTA_POR_ID["vera"]],
        ref["id"]: [CARTA_POR_ID["bruno"], CARTA_POR_ID["puente-parral"]],
        otro["id"]: [CARTA_POR_ID["lucia"]],
    }
    sala.formular_sospecha(inv["id"], *SOSPECHA)
    sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    return sala, inv, ref, otro


def test_continuar_sin_elegir_completa_y_no_vuelve_a_pedir_refutar():
    """Reproduce el bug real: humano con 2 cartas pulsa CONTINUAR sin elegir.

    Antes el servidor no tenía esta salida: el popup se quedaba abierto y
    volvía a pedir REFUTAR. Ahora CONTINUAR es una refutación YA RESUELTA.
    """
    sala, inv, ref, _ = _refutador_humano_con_dos()
    # 1-2. Refutador humano con dos coincidencias y NINGUNA seleccionada.
    assert sala.estado_jugada == JUGADA_ESPERANDO_REFUTADOR
    assert sala.jugador_por_id(ref["id"])["tipo"] == TIPO_HUMANO
    pendientes = {"bruno", "puente-parral"}
    opciones = sala.estado_privado(ref["id"])["jugada"]["opciones_refutacion"]
    assert {c["id"] for c in opciones} == pendientes

    # 3-6. El servidor elige una válida al azar y completa con ella.
    elegida = sala.continuar_refutacion(ref["id"], rng=EleccionFija("puente-parral"))
    assert elegida in pendientes
    assert sala.ultima_jugada["resultado"] == "refutada"
    assert sala.ultima_jugada["refutador_id"] == ref["id"]
    # 7. La refutación queda COMPLETADA, sin pendiente ni plazo.
    assert sala.sospecha_pendiente is None
    assert sala.refutacion_deadline is None
    # 8B.31C: queda el cierre público pendiente; el turno aún no avanza.
    assert sala.presentacion_sospecha["tipo"] == "resultado"
    assert sala.estado_jugada == JUGADA_PRESENTANDO_SOSPECHA
    cerrar_resultado(sala)
    # 8. El refutador ya NO está esperando elección.
    assert sala.estado_jugada == JUGADA_ESPERANDO_SOSPECHA
    # 9. Su estado privado no trae un nuevo selector con una sola carta.
    privada = sala.estado_privado(ref["id"])["jugada"]
    assert "opciones_refutacion" not in privada
    assert "timeout_refutacion_seg" not in privada
    assert "carta_mostrada" not in privada
    # 10. NO se vuelve a pedir REFUTAR por ninguna vía.
    with pytest.raises(ValueError):
        sala.continuar_refutacion(ref["id"])
    with pytest.raises(ValueError):
        sala.mostrar_carta(ref["id"], elegida)
    assert sala.resolver_refutacion_auto() is None
    # 11. El investigador recibe exactamente la carta elegida.
    assert sala.estado_carta(inv["id"], elegida) == INV_VISTA
    for no_elegida in pendientes - {elegida}:
        assert sala.estado_carta(inv["id"], no_elegida) != INV_VISTA
    privada_inv = sala.estado_privado(inv["id"])["jugada"]
    assert privada_inv["carta_mostrada"]["id"] == elegida
    # 12. El flujo continúa con el refutador en turno.
    cerrar_resultado(sala)
    assert sala.turno_actual == 1
    assert "carta_id" not in repr(sala.estado_publico()["jugada"])


def test_continuar_sin_elegir_es_equivalente_a_elegir_y_al_timeout():
    """Los tres caminos dejan el MISMO estado final; solo cambia quién elige."""
    finales = []
    for camino in ("elegir", "continuar", "timeout"):
        sala, inv, ref, _ = _refutador_humano_con_dos(f"JARA-5A-31B-{camino}")
        if camino == "elegir":
            sala.mostrar_carta(ref["id"], "bruno")  # A, la misma que el azar elige
        elif camino == "continuar":
            assert sala.continuar_refutacion(ref["id"], rng=EleccionFija("bruno")) == (
                "bruno"
            )
        else:
            sala.refutacion_deadline = time.monotonic() - 5
            assert sala.resolver_refutacion_auto(rng=EleccionFija("bruno")) == "bruno"
        finales.append(
            (
                sala.ultima_jugada["resultado"],
                sala.ultima_jugada["carta_id"],
                # Alias y no id: cada camino usa una sala nueva con ids nuevos.
                sala.jugador_por_id(sala.ultima_jugada["investigador_id"])["alias"],
                sala.jugador_por_id(sala.ultima_jugada["refutador_id"])["alias"],
                sala.sospecha_pendiente,
                sala.refutacion_deadline,
                sala.estado_jugada,
                sala.turno_actual,
                sala.estado_carta(inv["id"], "bruno"),
                sala.estado_privado(inv["id"])["jugada"]["carta_mostrada"]["id"],
                "opciones_refutacion" in sala.estado_privado(ref["id"])["jugada"],
            )
        )
    assert finales[0] == finales[1] == finales[2]


def test_continuar_ignora_el_plazo_vigente_y_respeta_al_que_no_es_refutador():
    sala, inv, ref, otro = _refutador_humano_con_dos("JARA-5A-31B-GUARD")
    assert sala.resolver_refutacion_auto() is None  # el plazo sigue vigente
    for intruso in (inv, otro):
        with pytest.raises(ValueError):
            sala.continuar_refutacion(intruso["id"])
    assert sala.estado_jugada == JUGADA_ESPERANDO_REFUTADOR
    assert sala.sospecha_pendiente is not None


def test_continuar_con_una_sola_coincidencia_usa_esa_carta_y_termina():
    """Sin pasos nuevos: con una carta, CONTINUAR equivale a completarla."""
    sala, inv, ref, otro = sala_refutacion("JARA-5A-31B-UNA")
    sala.manos = {
        inv["id"]: [CARTA_POR_ID["vera"]],
        ref["id"]: [CARTA_POR_ID["bruno"]],
        otro["id"]: [CARTA_POR_ID["lucia"]],
    }
    sala.formular_sospecha(inv["id"], *SOSPECHA)
    sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    assert [
        c["id"] for c in sala.estado_privado(ref["id"])["jugada"]["opciones_refutacion"]
    ] == ["bruno"]
    assert sala.continuar_refutacion(ref["id"]) == "bruno"
    assert sala.sospecha_pendiente is None
    assert "opciones_refutacion" not in sala.estado_privado(ref["id"])["jugada"]
    assert sala.estado_carta(inv["id"], "bruno") == INV_VISTA


def test_continuar_usa_random_choice_entre_las_coincidencias():
    sala, inv, ref, _ = _refutador_humano_con_dos("JARA-5A-31B-RNG")
    rng = EleccionFija("bruno")
    assert sala.continuar_refutacion(ref["id"], rng=rng) == "bruno"
    assert set(rng.recibidas) == {"bruno", "puente-parral"}


def test_carrera_continuar_gana_al_timeout_y_el_timeout_queda_noop():
    sala, inv, ref, _ = _refutador_humano_con_dos("JARA-5A-31B-CARRERA")
    sala.continuar_refutacion(ref["id"], rng=EleccionFija("bruno"))
    sala.refutacion_deadline = time.monotonic() - 5  # aunque venza después
    assert sala.resolver_refutacion_auto() is None
    cerrar_resultado(sala)
    assert sala.turno_actual == 1
    assert sala.ultima_jugada["carta_id"] == "bruno"


def test_ui_continuar_sin_eleccion_y_accion_de_renunciar():
    """El popup ofrece CONTINUAR solo si no hay carta elegida."""
    sala, _ = gestor.crear_sala("Paco")
    try:
        pagina = cliente.get(f"/sala/{sala.codigo}")
        assert pagina.status_code == 200
        html = pagina.text
    finally:
        gestor.salas.pop(sala.codigo, None)
    assert 'id="btn-confirmar-refutacion"' in html
    assert 'id="btn-continuar-refutacion"' in html
    assert 'id="modal-revelacion-refutacion"' in html  # intacto: es del investigador
    texto = cliente.get("/static/js/sala.js").text
    assert 'accion: "continuar_refutacion"' in texto
    assert "actualizarAccionesRefutacion" in texto
    assert not re.search(r"[^a-zA-Z]confirm\s*\(", texto)
    assert not re.search(r"[^a-zA-Z]alert\s*\(", texto)


def test_continuar_por_ws_completa_y_no_reabre_el_popup():
    """PRUEBA REAL por socket: el refutador humano pulsa CONTINUAR."""
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
        with cliente.websocket_connect(f"/ws/{codigo}/{sala['jugador_id']}") as ws_paco:
            ws_paco.receive_json()
            ws_paco.send_json({"accion": "iniciar"})
            ws_paco.receive_json()
            ids = {j["alias"]: j["id"] for j in srv.jugadores}
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
            main.cancelar_presentacion_sospecha(codigo)
            srv.actualizar_presentacion_sospecha(ahora=float("inf"))
        main.cancelar_timeout_refutacion(codigo)
        main.cancelar_presentacion_sospecha(codigo)
        # Ana (refutadora humana) ve las dos opciones y NO elige ninguna.
        with cliente.websocket_connect(f"/ws/{codigo}/{ana['jugador_id']}") as ws_ana:
            jugada = ws_ana.receive_json()["sala"]["jugada"]
            assert {c["id"] for c in jugada["opciones_refutacion"]} == {
                "bruno",
                "puente-parral",
            }
            ws_ana.send_json({"accion": "continuar_refutacion"})
            # El refutador ya no recibe un selector nuevo.
            jugada = ws_ana.receive_json()["sala"]["jugada"]
            assert "opciones_refutacion" not in jugada
            assert srv.sospecha_pendiente is None
            assert srv.estado_jugada != JUGADA_ESPERANDO_REFUTADOR
        # El investigador recibe exactamente una carta, y es válida.
        with cliente.websocket_connect(f"/ws/{codigo}/{sala['jugador_id']}") as ws_paco:
            jugada = ws_paco.receive_json()["sala"]["jugada"]
            mostrada = jugada["carta_mostrada"]
            assert mostrada["id"] in {"bruno", "puente-parral"}
            assert srv.estado_carta(sala["jugador_id"], mostrada["id"]) == INV_VISTA
        # Nadie más ve la carta ni puede refutar otra vez.
        assert "carta_mostrada" not in srv.estado_privado(
            luis["jugador_id"]
        )["jugada"]
        assert "opciones_refutacion" not in srv.estado_privado(
            luis["jugador_id"]
        )["jugada"]
    finally:
        for registro in (gestor.salas, conexiones, cerrojos):
            registro.pop(codigo, None)
        main.tareas_pnj.pop(codigo, None)
        tarea = main.tareas_refutacion.pop(codigo, None)
        if tarea:
            tarea.cancel()
