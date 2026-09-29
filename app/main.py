"""Servidor FastAPI multijugador con mesa fija y turnos humanos/PNJ.

Cada conexión WebSocket humana recibe únicamente su estado privado. Los PNJ
no tienen conexiones simuladas y el misterio nunca sale del servidor.
"""
from __future__ import annotations

import asyncio
import time

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.datos.jarandilla import SOSPECHOSOS
from app.datos.recursos import (
    AUDIO_CLIC,
    AUDIO_FINAL,
    AUDIO_MUSICA_FONDO,
    COLORES_PERSONAJES,
    RECURSOS_VISUALES,
    RECURSO_PEON,
    RECURSO_TABLERO,
)
from app.datos.tablero_visual import TABLERO_VISUAL
from app.motor.sala import (
    ESTADO_ESPERANDO,
    ESTADO_TERMINADA,
    JUGADA_ESPERANDO_MOVIMIENTO,
    JUGADA_ESPERANDO_REFUTADOR,
    JUGADA_ESPERANDO_SOSPECHA,
    JUGADA_PRESENTANDO_SOSPECHA,
    TIPO_PNJ,
    MODO_TABLERO,
    GestorSalas,
)

app = FastAPI(title="El Misterio del Medallón")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
plantillas = Jinja2Templates(directory="app/templates")

gestor = GestorSalas()
# codigo sala -> jugador_id -> websockets abiertos de ese jugador
conexiones: dict[str, dict[str, list[WebSocket]]] = {}
cerrojos: dict[str, asyncio.Lock] = {}
tareas_pnj: dict[str, asyncio.Task] = {}
PAUSA_TURNO_PNJ_SEGUNDOS = 3.0
PAUSA_TRAS_JUGADA_HUMANA_SEGUNDOS = 5.0
PAUSA_LECTURA_SOSPECHA_PNJ_SEGUNDOS = 5.0


def pausa_antes_de_turno_pnj(sala) -> float:
    """Ritmo contextual: depende del INVESTIGADOR de la ultima jugada.

    Sospecha PNJ de tablero ya resuelta -> ~5 s de lectura. Esta pausa
    sustituye la pausa PNJ genérica, no se suma a ella. Jugada humana
    -> siguiente PNJ = ~5 s. Otro caso PNJ (o sin jugada previa) -> ~3 s.
    Nunca bloquea: solo indica la duración del asyncio.sleep exterior
    al cerrojo.
    """
    ultima = getattr(sala, "ultima_jugada", None)
    if ultima:
        investigador = sala.jugador_por_id(ultima.get("investigador_id", ""))
        if (
            sala.modo == MODO_TABLERO
            and investigador is not None
            and investigador.get("tipo") == TIPO_PNJ
            and ultima.get("sospecha")
            and ultima.get("resultado") in {"refutada", "sin_refutacion"}
        ):
            return PAUSA_LECTURA_SOSPECHA_PNJ_SEGUNDOS
        if investigador is not None and investigador.get("tipo") != TIPO_PNJ:
            return PAUSA_TRAS_JUGADA_HUMANA_SEGUNDOS
    return PAUSA_TURNO_PNJ_SEGUNDOS


async def _cadena_turnos_pnj(codigo: str) -> None:
    """Unica autoridad automatica por sala; nunca espera sosteniendo el lock."""
    tarea_actual = asyncio.current_task()
    try:
        while True:
            sala = gestor.obtener(codigo)
            if sala is None:
                return
            async with cerrojos.setdefault(codigo, asyncio.Lock()):
                jugador = sala.jugador_en_turno()
                if (
                    jugador is None
                    or jugador["tipo"] != TIPO_PNJ
                    or sala.estado_jugada != (
                        JUGADA_ESPERANDO_MOVIMIENTO
                        if sala.modo == MODO_TABLERO
                        else JUGADA_ESPERANDO_SOSPECHA
                    )
                ):
                    return
                jugador_id = jugador["id"]
                sala.pnj_pensando_id = jugador_id
                pausa = pausa_antes_de_turno_pnj(sala)
            # El resultado anterior sigue en ultima_jugada durante toda la
            # pausa. No sostenemos el cerrojo mientras los humanos lo leen.
            await asyncio.sleep(pausa)
            async with cerrojos[codigo]:
                jugador = sala.jugador_en_turno()
                if (
                    jugador is None
                    or jugador["id"] != jugador_id
                    or sala.estado_jugada != (
                        JUGADA_ESPERANDO_MOVIMIENTO
                        if sala.modo == MODO_TABLERO
                        else JUGADA_ESPERANDO_SOSPECHA
                    )
                ):
                    continue
                sala.ejecutar_turno_pnj()
            await difundir(codigo)
            if sala.estado == ESTADO_TERMINADA:
                cancelar_timeout_refutacion(codigo)
                cancelar_bloqueo(codigo)
                return
            if sala.estado_jugada == JUGADA_PRESENTANDO_SOSPECHA:
                programar_presentacion_sospecha(codigo)
                return
            # La jugada PNJ también puede dejar una refutación humana
            # pendiente: programa el watchdog con el deadline ya creado.
            programar_timeout_refutacion(codigo)
            # 8B.32: y puede dejar bloqueada a la siguiente persona humana.
            programar_bloqueo(codigo)
    finally:
        if tareas_pnj.get(codigo) is tarea_actual:
            tareas_pnj.pop(codigo, None)


def programar_turno_pnj(codigo: str) -> None:
    sala = gestor.obtener(codigo)
    if sala is None or sala.estado == ESTADO_TERMINADA:
        return
    existente = tareas_pnj.get(codigo)
    if existente is None or existente.done():
        tareas_pnj[codigo] = asyncio.create_task(_cadena_turnos_pnj(codigo))


# Watchdog server-side del timeout de refutación (Microfase 5A).
# Una sola tarea por sala; nunca duerme con el cerrojo cogido.
tareas_refutacion: dict[str, asyncio.Task] = {}


def _necesita_timeout_refutacion(sala) -> bool:
    """Toda refutación humana pendiente tiene un único timeout."""
    if (
        sala.estado_jugada != JUGADA_ESPERANDO_REFUTADOR
        or not sala.sospecha_pendiente
    ):
        return False
    refutador = sala.jugador_por_id(
        sala.sospecha_pendiente["refutador_id"]
    )
    return (
        refutador is not None
        and refutador["tipo"] != TIPO_PNJ
    )


async def _vigilar_refutacion_humana(codigo: str) -> None:
    """Espera al deadline y resuelve automáticamente si sigue pendiente.

    La carrera manual/timeout se gana bajo el cerrojo de la sala: quien
    resuelva primero (mostrar_carta o este watchdog) deja
    sospecha_pendiente a None y el otro es no-op. Solo la resolución
    ganadora difunde y programa la cadena PNJ, exactamente una vez.
    """
    tarea_actual = asyncio.current_task()
    try:
        sala = gestor.obtener(codigo)
        if sala is None or not _necesita_timeout_refutacion(sala):
            return
        deadline = sala.refutacion_deadline
        if deadline is None:
            return
        retraso = deadline - time.monotonic()
        if retraso > 0:
            await asyncio.sleep(retraso)
        async with cerrojos.setdefault(codigo, asyncio.Lock()):
            sala = gestor.obtener(codigo)
            if sala is None or sala.refutacion_deadline != deadline:
                return  # rancia: otra jugada manda o ya se resolvió
            if sala.resolver_refutacion_auto() is None:
                return  # la elección manual ganó la carrera
        await difundir(codigo)
        programar_turno_pnj(codigo)
        # 8B.31C: el timeout también abre el resultado público.
        programar_presentacion_sospecha(codigo)
    finally:
        if tareas_refutacion.get(codigo) is tarea_actual:
            tareas_refutacion.pop(codigo, None)


def programar_timeout_refutacion(codigo: str) -> None:
    """Programa el watchdog sin reiniciar jamás el deadline de la sala."""
    sala = gestor.obtener(codigo)
    if sala is None or sala.estado == ESTADO_TERMINADA:
        return
    if not _necesita_timeout_refutacion(sala):
        return
    if sala.refutacion_deadline is None:
        return
    existente = tareas_refutacion.get(codigo)
    if existente is None or existente.done():
        tareas_refutacion[codigo] = asyncio.create_task(
            _vigilar_refutacion_humana(codigo)
        )


def cancelar_timeout_refutacion(codigo: str) -> None:
    tarea = tareas_refutacion.pop(codigo, None)
    if tarea:
        tarea.cancel()


# Watchdog autoritativo de la presentación sincronizada (Microfase 8B.30).
tareas_presentacion: dict[str, asyncio.Task] = {}


async def _vigilar_presentacion_sospecha(codigo: str) -> None:
    tarea_actual = asyncio.current_task()
    try:
        while True:
            sala = gestor.obtener(codigo)
            presentacion = getattr(sala, "presentacion_sospecha", None) if sala else None
            if sala is None or presentacion is None:
                return
            presentacion_id = presentacion["id"]
            pendientes = [
                estado["deadline"]
                for estado in presentacion["participantes"].values()
                if not estado["listo"]
            ]
            if not pendientes:
                retraso = 0
            else:
                retraso = max(0.0, min(pendientes) - time.monotonic())
            if retraso:
                await asyncio.sleep(retraso)
            async with cerrojos.setdefault(codigo, asyncio.Lock()):
                sala = gestor.obtener(codigo)
                actual = getattr(sala, "presentacion_sospecha", None) if sala else None
                if actual is None or actual["id"] != presentacion_id:
                    return
                completada = sala.actualizar_presentacion_sospecha()
            await difundir(codigo)
            if completada:
                programar_timeout_refutacion(codigo)
                programar_turno_pnj(codigo)
                # 8B.31C: resolver la refutación abre la presentación PÚBLICA
                # de resultado. Se sigue vigilando en la MISMA tarea (identidad
                # y plazo viven en la sala): nunca un watchdog duplicado.
                if getattr(gestor.obtener(codigo), "presentacion_sospecha", None):
                    continue
                return
    finally:
        if tareas_presentacion.get(codigo) is tarea_actual:
            tareas_presentacion.pop(codigo, None)


def programar_presentacion_sospecha(codigo: str) -> None:
    sala = gestor.obtener(codigo)
    if (
        sala is None
        or sala.estado == ESTADO_TERMINADA
        or sala.estado_jugada != JUGADA_PRESENTANDO_SOSPECHA
        or sala.presentacion_sospecha is None
    ):
        return
    existente = tareas_presentacion.get(codigo)
    if existente is None or existente.done():
        tareas_presentacion[codigo] = asyncio.create_task(
            _vigilar_presentacion_sospecha(codigo)
        )


def cancelar_presentacion_sospecha(codigo: str) -> None:
    tarea = tareas_presentacion.pop(codigo, None)
    try:
        actual = asyncio.current_task()
    except RuntimeError:
        actual = None
    if tarea and tarea is not actual:
        tarea.cancel()


# Antibloqueo por inactividad (8B.32). Un plazo canónico de 60 s por acción
# bloqueante de un humano. NO ejecuta la acción pendiente: al vencer solo
# abre el aviso privado del ANFITRIÓN, que decide entre PASAR A PNJ y
# SEGUIR ESPERANDO. Mismo patrón y misma carrera que el timeout de
# refutación: una sola tarea por sala, nunca duerme con el cerrojo cogido y
# la identidad del aviso vive en la sala, no en la tarea.
tareas_bloqueo: dict[str, asyncio.Task] = {}


def _necesita_bloqueo(sala) -> bool:
    return bool(sala.bloqueo_deadline is not None and sala.jugador_bloqueante())


async def _vigilar_bloqueo(codigo: str) -> None:
    """Espera al deadline y abre el aviso si el bloqueo sigue vivo.

    La carrera se gana bajo el cerrojo de la sala y contra la IDENTIDAD del
    plazo: si la acción se resolvió, si el plazo se renovó o si ya se emitió
    el aviso, esta tarea es no-op y la que siga viva manda. Nunca reinicia
    el minuto: el plazo se crea en el motor, al entrar en la acción
    bloqueante, y solo lo cambia SEGUIR ESPERANDO.
    """
    tarea_actual = asyncio.current_task()
    try:
        sala = gestor.obtener(codigo)
        if sala is None or not _necesita_bloqueo(sala):
            return
        deadline = sala.bloqueo_deadline
        if deadline is None:
            return
        retraso = deadline - time.monotonic()
        if retraso > 0:
            await asyncio.sleep(retraso)
        async with cerrojos.setdefault(codigo, asyncio.Lock()):
            sala = gestor.obtener(codigo)
            if sala is None or sala.bloqueo_deadline != deadline:
                return  # rancia: la acción se resolvió o el plazo se renovó
            if not sala.registrar_aviso_inactividad():
                return  # ya emitido, o el que bloquea es el anfitrión
        # Solo se difunde el aviso: nadie ejecuta la acción pendiente.
        await difundir(codigo)
    finally:
        if tareas_bloqueo.get(codigo) is tarea_actual:
            tareas_bloqueo.pop(codigo, None)


def programar_bloqueo(codigo: str) -> None:
    """Programa el watchdog sin reiniciar jamás el deadline de la sala."""
    sala = gestor.obtener(codigo)
    if sala is None or sala.estado == ESTADO_TERMINADA:
        return
    if not _necesita_bloqueo(sala):
        return
    existente = tareas_bloqueo.get(codigo)
    if existente is None or existente.done():
        tareas_bloqueo[codigo] = asyncio.create_task(_vigilar_bloqueo(codigo))


def cancelar_bloqueo(codigo: str) -> None:
    tarea = tareas_bloqueo.pop(codigo, None)
    try:
        actual = asyncio.current_task()
    except RuntimeError:
        actual = None
    if tarea and tarea is not actual:
        tarea.cancel()


class EntradaAlias(BaseModel):
    alias: str = ""
    modo: str = "rapido"


class EntradaUnirse(BaseModel):
    alias: str = ""
    codigo: str = ""


def _respuesta_error(mensaje: str, estado: int = 400):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=estado, content={"detalle": mensaje})


def _desconectar_ws(codigo: str, jugador_id: str, ws: WebSocket) -> None:
    pantallas = conexiones.get(codigo, {}).get(jugador_id, [])
    if ws in pantallas:
        pantallas.remove(ws)
    if not pantallas:
        conexiones.get(codigo, {}).pop(jugador_id, None)
    if not conexiones.get(codigo):
        conexiones.pop(codigo, None)


async def _enviar_privado(sala, jugador_id: str, ws: WebSocket) -> bool:
    """Envía a una conexión solo el estado privado de su jugador."""
    try:
        await ws.send_json(
            {"tipo": "estado_privado", "sala": sala.estado_privado(jugador_id)}
        )
        return True
    except Exception:
        return False


async def difundir(codigo: str) -> None:
    """Envía a cada conexión únicamente su estado privado."""
    sala = gestor.obtener(codigo)
    if sala is None:
        return
    for jugador_id, pantallas in list(conexiones.get(codigo, {}).items()):
        vivas = []
        for ws in pantallas:
            if await _enviar_privado(sala, jugador_id, ws):
                vivas.append(ws)
        if vivas:
            conexiones[codigo][jugador_id] = vivas
        else:
            conexiones[codigo].pop(jugador_id, None)


@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    return plantillas.TemplateResponse(request, "inicio.html")


@app.get("/sala/{codigo}", response_class=HTMLResponse)
def ver_sala(request: Request, codigo: str):
    sala = gestor.obtener(codigo)
    if sala is None:
        # Sala caducada o inexistente: portada limpia sin error inicial.
        # El error solo aparece tras pulsar UNIRSE con un código fallido.
        return RedirectResponse(url="/", status_code=303)
    return plantillas.TemplateResponse(
        request, "sala.html", {"codigo": sala.codigo}
    )


@app.post("/api/partidas")
async def crear_partida(entrada: EntradaAlias):
    try:
        sala, anfitrion = gestor.crear_sala(entrada.alias, entrada.modo)
    except ValueError as exc:
        return _respuesta_error(str(exc))
    conexiones.setdefault(sala.codigo, {})
    cerrojos.setdefault(sala.codigo, asyncio.Lock())
    return {
        "codigo": sala.codigo,
        "jugador_id": anfitrion["id"],
        "alias": anfitrion["alias"],
        "sala": sala.estado_publico(),
    }


@app.post("/api/partidas/{codigo}/unirse")
async def unirse_partida(codigo: str, entrada: EntradaUnirse):
    alias = entrada.alias or ""
    try:
        sala, jugador = gestor.unirse(codigo, alias)
    except LookupError as exc:
        return _respuesta_error(str(exc), 404)
    except ValueError as exc:
        return _respuesta_error(str(exc))
    await difundir(sala.codigo)
    return {
        "codigo": sala.codigo,
        "jugador_id": jugador["id"],
        "alias": jugador["alias"],
        "sala": sala.estado_publico(),
    }


@app.get("/api/personajes")
def listar_personajes():
    """Los 6 sospechosos seleccionables (dato público, no secreto)."""
    return {"personajes": SOSPECHOSOS}


@app.get("/api/recursos")
def listar_recursos_visuales():
    """Manifiesto público de imágenes; solo contiene IDs y rutas estáticas."""
    return {
        "recursos": RECURSOS_VISUALES,
        "tablero": RECURSO_TABLERO,
        "peon": RECURSO_PEON,
        "colores_personajes": COLORES_PERSONAJES,
        "audio": {
            "musica_fondo": AUDIO_MUSICA_FONDO,
            "clic": AUDIO_CLIC,
            "final": AUDIO_FINAL,
        },
    }


@app.get("/api/tablero")
def obtener_tablero_visual():
    """Geometría pública de presentación derivada del motor lógico."""
    return {"tablero": TABLERO_VISUAL}


@app.get("/api/partidas/{codigo}")
def estado_partida(codigo: str):
    sala = gestor.obtener(codigo)
    if sala is None:
        return _respuesta_error("La sala no existe. Revisa el código.", 404)
    return {"sala": sala.estado_publico()}


@app.websocket("/ws/{codigo}/{jugador_id}")
async def websocket_sala(ws: WebSocket, codigo: str, jugador_id: str):
    sala = gestor.obtener(codigo)
    if sala is None or sala.jugador_por_id(jugador_id) is None:
        await ws.close(code=4404)
        return
    await ws.accept()
    # Reconexión: el jugador conserva su id, su mano y su rol.
    conexiones.setdefault(sala.codigo, {}).setdefault(jugador_id, []).append(ws)
    await _enviar_privado(sala, jugador_id, ws)
    programar_turno_pnj(sala.codigo)
    # Reconexión con refutación pendiente: rearma el watchdog con el
    # deadline existente de la sala, sin reiniciar el plazo.
    programar_timeout_refutacion(sala.codigo)
    programar_presentacion_sospecha(sala.codigo)
    # 8B.32: idem con el antibloqueo. El plazo vive en la sala: recargar o
    # volver a conectarse NO lo reinicia ni reinicia el minuto.
    programar_bloqueo(sala.codigo)
    try:
        while True:
            datos = await ws.receive_json()
            accion = datos.get("accion")
            if accion == "iniciar":
                try:
                    async with cerrojos.setdefault(sala.codigo, asyncio.Lock()):
                        sala.iniciar(jugador_id)
                except ValueError as exc:
                    await ws.send_json({"tipo": "error", "detalle": str(exc)})
                    continue
                await difundir(sala.codigo)
                programar_turno_pnj(sala.codigo)
                programar_bloqueo(sala.codigo)
            elif accion == "confirmar_presentacion_sospecha":
                try:
                    async with cerrojos.setdefault(sala.codigo, asyncio.Lock()):
                        completada = sala.confirmar_presentacion_sospecha(
                            jugador_id, datos.get("presentacion_id")
                        )
                except ValueError as exc:
                    await ws.send_json({"tipo": "error", "detalle": str(exc)})
                    continue
                if completada:
                    cancelar_presentacion_sospecha(sala.codigo)
                await difundir(sala.codigo)
                if completada:
                    programar_timeout_refutacion(sala.codigo)
                    programar_turno_pnj(sala.codigo)
                    programar_bloqueo(sala.codigo)
            elif accion == "elegir_personaje":
                try:
                    sala.elegir_personaje(jugador_id, datos.get("personaje_id", ""))
                except ValueError as exc:
                    await ws.send_json({"tipo": "error", "detalle": str(exc)})
                    continue
                await difundir(sala.codigo)
                programar_turno_pnj(sala.codigo)
            elif accion == "formular_sospecha":
                try:
                    async with cerrojos.setdefault(sala.codigo, asyncio.Lock()):
                        sala.formular_sospecha_humano(
                            jugador_id,
                            datos.get("sospechoso_id", ""),
                            datos.get("lugar_id", ""),
                            datos.get("objeto_id", ""),
                        )
                except ValueError as exc:
                    await ws.send_json({"tipo": "error", "detalle": str(exc)})
                    continue
                await difundir(sala.codigo)
                cancelar_bloqueo(sala.codigo)
                programar_presentacion_sospecha(sala.codigo)
            elif accion == "tirar_dado":
                try:
                    async with cerrojos.setdefault(sala.codigo, asyncio.Lock()):
                        sala.tirar_dado_tablero(jugador_id)
                except ValueError as exc:
                    await ws.send_json({"tipo": "error", "detalle": str(exc)})
                    continue
                await difundir(sala.codigo)
                # La tirada abre la elección de destino: nuevo plazo bloqueante.
                programar_bloqueo(sala.codigo)
            elif accion == "mover":
                try:
                    async with cerrojos.setdefault(sala.codigo, asyncio.Lock()):
                        sala.mover(jugador_id, datos.get("destino_id", ""))
                except ValueError as exc:
                    await ws.send_json({"tipo": "error", "detalle": str(exc)})
                    continue
                await difundir(sala.codigo)
                programar_turno_pnj(sala.codigo)
                programar_bloqueo(sala.codigo)
            elif accion == "usar_pasadizo":
                try:
                    async with cerrojos.setdefault(sala.codigo, asyncio.Lock()):
                        sala.usar_pasadizo(jugador_id)
                except ValueError as exc:
                    await ws.send_json({"tipo": "error", "detalle": str(exc)})
                    continue
                await difundir(sala.codigo)
                programar_timeout_refutacion(sala.codigo)
                programar_bloqueo(sala.codigo)
            elif accion == "resolver_misterio":
                try:
                    async with cerrojos.setdefault(sala.codigo, asyncio.Lock()):
                        sala.resolver_misterio_humano(
                            jugador_id,
                            datos.get("sospechoso_id", ""),
                            datos.get("lugar_id", ""),
                            datos.get("objeto_id", ""),
                        )
                except ValueError as exc:
                    await ws.send_json({"tipo": "error", "detalle": str(exc)})
                    continue
                if sala.estado == ESTADO_TERMINADA:
                    tarea = tareas_pnj.pop(sala.codigo, None)
                    if tarea and tarea is not asyncio.current_task():
                        tarea.cancel()
                    cancelar_timeout_refutacion(sala.codigo)
                    cancelar_presentacion_sospecha(sala.codigo)
                    cancelar_bloqueo(sala.codigo)
                await difundir(sala.codigo)
                programar_turno_pnj(sala.codigo)
                programar_bloqueo(sala.codigo)
            elif accion == "mostrar_carta":
                try:
                    async with cerrojos.setdefault(sala.codigo, asyncio.Lock()):
                        sala.mostrar_carta(jugador_id, datos.get("carta_id", ""))
                except ValueError as exc:
                    await ws.send_json({"tipo": "error", "detalle": str(exc)})
                    continue
                # La elección manual ganó: el watchdog pendiente es no-op.
                cancelar_timeout_refutacion(sala.codigo)
                cancelar_presentacion_sospecha(sala.codigo)
                cancelar_bloqueo(sala.codigo)
                await difundir(sala.codigo)
                programar_turno_pnj(sala.codigo)
                # 8B.31C: la refutación abre el resultado público.
                programar_presentacion_sospecha(sala.codigo)
            elif accion == "continuar_refutacion":
                try:
                    async with cerrojos.setdefault(sala.codigo, asyncio.Lock()):
                        sala.continuar_refutacion(jugador_id)
                except ValueError as exc:
                    await ws.send_json({"tipo": "error", "detalle": str(exc)})
                    continue
                # El servidor completa la refutación: el watchdog es no-op.
                cancelar_timeout_refutacion(sala.codigo)
                cancelar_presentacion_sospecha(sala.codigo)
                cancelar_bloqueo(sala.codigo)
                await difundir(sala.codigo)
                programar_turno_pnj(sala.codigo)
                # 8B.31C: la refutación abre el resultado público.
                programar_presentacion_sospecha(sala.codigo)
            elif accion == "elegir_modo_refutacion":
                try:
                    async with cerrojos.setdefault(sala.codigo, asyncio.Lock()):
                        sala.elegir_modo_refutacion(
                            jugador_id, datos.get("automatica") is True
                        )
                except ValueError as exc:
                    await ws.send_json({"tipo": "error", "detalle": str(exc)})
                    continue
                # Preferencia estrictamente privada: no se difunde al resto.
                await _enviar_privado(sala, jugador_id, ws)
            elif accion == "seguir_esperando":
                # 8B.32: nuevo periodo canónico de 60 s para la MISMA acción
                # bloqueante. El watchdog anterior dormía sobre el plazo
                # viejo: se cancela y se rearma con el nuevo, sin tocar nada
                # más de la partida.
                try:
                    async with cerrojos.setdefault(sala.codigo, asyncio.Lock()):
                        sala.seguir_esperando(jugador_id, datos.get("aviso_id"))
                except ValueError as exc:
                    await ws.send_json({"tipo": "error", "detalle": str(exc)})
                    continue
                cancelar_bloqueo(sala.codigo)
                await difundir(sala.codigo)
                programar_bloqueo(sala.codigo)
            elif accion == "pasar_a_pnj":
                # 8B.32: el MISMO asiento pasa a controlado automáticamente y
                # resuelve de inmediato la acción que tenía bloqueada. Conversión
                # y continuación, juntas y bajo el mismo cerrojo: una única
                # transición canónica.
                try:
                    async with cerrojos.setdefault(sala.codigo, asyncio.Lock()):
                        sala.convertir_en_pnj(jugador_id, datos.get("aviso_id"))
                        sala.continuar_bloqueo_como_pnj()
                except ValueError as exc:
                    await ws.send_json({"tipo": "error", "detalle": str(exc)})
                    continue
                cancelar_bloqueo(sala.codigo)
                if sala.estado == ESTADO_TERMINADA:
                    tarea = tareas_pnj.pop(sala.codigo, None)
                    if tarea and tarea is not asyncio.current_task():
                        tarea.cancel()
                    cancelar_timeout_refutacion(sala.codigo)
                    cancelar_presentacion_sospecha(sala.codigo)
                await difundir(sala.codigo)
                # La continuación puede haber movido, sospechado o resuelto:
                # se reprograma todo lo que corresponda, igual que tras una
                # jugada normal de un PNJ.
                programar_turno_pnj(sala.codigo)
                programar_presentacion_sospecha(sala.codigo)
                programar_timeout_refutacion(sala.codigo)
                programar_bloqueo(sala.codigo)
            elif accion == "volver_al_lobby":
                # 8B.35 · Revancha canónica en servidor. Es idempotente y
                # protegida por el cerrojo de la sala, igual que el inicio de
                # partida: si dos pulsan casi a la vez, solo uno transiciona.
                try:
                    async with cerrojos.setdefault(sala.codigo, asyncio.Lock()):
                        reinicio = sala.volver_al_lobby(jugador_id)
                except ValueError as exc:
                    await ws.send_json({"tipo": "error", "detalle": str(exc)})
                    continue
                if reinicio:
                    # La partida anterior y la siguiente no comparten ninguna
                    # tarea: se detienen los cuatro watchdogs de la sala.
                    tarea_pnj = tareas_pnj.pop(sala.codigo, None)
                    if tarea_pnj and tarea_pnj is not asyncio.current_task():
                        tarea_pnj.cancel()
                    cancelar_timeout_refutacion(sala.codigo)
                    cancelar_presentacion_sospecha(sala.codigo)
                    cancelar_bloqueo(sala.codigo)
                # Todos los clientes vuelven al lobby de la MISMA sala.
                await difundir(sala.codigo)
            elif accion == "marcar_investigacion":
                try:
                    sala.marcar_investigacion(
                        jugador_id,
                        datos.get("carta_id", ""),
                        datos.get("estado", ""),
                    )
                except ValueError as exc:
                    await ws.send_json({"tipo": "error", "detalle": str(exc)})
                    continue
                # Privado: solo se actualiza al autor, nunca al resto.
                await _enviar_privado(sala, jugador_id, ws)
            else:
                # Ante mensajes desconocidos se reenvía su estado privado.
                await _enviar_privado(sala, jugador_id, ws)
    except WebSocketDisconnect:
        pass
    finally:
        _desconectar_ws(sala.codigo, jugador_id, ws)
        if sala.estado == ESTADO_ESPERANDO:
            # En el lobby la salida sí elimina al jugador.
            sala.quitar_jugador(jugador_id)
            if not sala.jugadores:
                gestor.salas.pop(sala.codigo, None)
                conexiones.pop(sala.codigo, None)
                cerrojos.pop(sala.codigo, None)
                tarea = tareas_pnj.pop(sala.codigo, None)
                if tarea:
                    tarea.cancel()
                cancelar_timeout_refutacion(sala.codigo)
                cancelar_presentacion_sospecha(sala.codigo)
                cancelar_bloqueo(sala.codigo)
            else:
                await difundir(sala.codigo)
        # En partida iniciada el jugador y su mano se conservan
        # para que pueda reconectar con su jugador_id.
