"""Servidor FastAPI multijugador con mesa fija y turnos humanos/PNJ.

Cada conexión WebSocket humana recibe únicamente su estado privado. Los PNJ
no tienen conexiones simuladas y el misterio nunca sale del servidor.
"""
from __future__ import annotations

import asyncio

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.datos.jarandilla import SOSPECHOSOS
from app.motor.sala import (
    ESTADO_ESPERANDO,
    JUGADA_ESPERANDO_SOSPECHA,
    TIPO_PNJ,
    GestorSalas,
)

app = FastAPI(title="Cluedo Jarandilla — El misterio del medallón imperial")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
plantillas = Jinja2Templates(directory="app/templates")

gestor = GestorSalas()
# codigo sala -> jugador_id -> websockets abiertos de ese jugador
conexiones: dict[str, dict[str, list[WebSocket]]] = {}
cerrojos: dict[str, asyncio.Lock] = {}
tareas_pnj: dict[str, asyncio.Task] = {}
PAUSA_TURNO_PNJ_SEGUNDOS = 3.0
PAUSA_TRAS_JUGADA_HUMANA_SEGUNDOS = 5.0


def pausa_antes_de_turno_pnj(sala) -> float:
    """Ritmo contextual: depende del INVESTIGADOR de la ultima jugada.

    Jugada humana -> siguiente PNJ = ~5 s (tiempo de lectura del
    refutador y de la carta privada). Jugada PNJ (o sin jugada previa)
    -> siguiente PNJ = ~3 s. Nunca bloquea: solo indica la duracion
    del asyncio.sleep exterior al cerrojo.
    """
    ultima = getattr(sala, "ultima_jugada", None)
    if ultima:
        investigador = sala.jugador_por_id(ultima.get("investigador_id", ""))
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
                    or sala.estado_jugada != JUGADA_ESPERANDO_SOSPECHA
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
                    or sala.estado_jugada != JUGADA_ESPERANDO_SOSPECHA
                ):
                    continue
                sala.ejecutar_turno_pnj()
            await difundir(codigo)
    finally:
        if tareas_pnj.get(codigo) is tarea_actual:
            tareas_pnj.pop(codigo, None)


def programar_turno_pnj(codigo: str) -> None:
    existente = tareas_pnj.get(codigo)
    if existente is None or existente.done():
        tareas_pnj[codigo] = asyncio.create_task(_cadena_turnos_pnj(codigo))


class EntradaAlias(BaseModel):
    alias: str = ""


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
        return plantillas.TemplateResponse(
            request,
            "inicio.html",
            {"error": "La sala no existe. Revisa el código."},
            status_code=404,
        )
    return plantillas.TemplateResponse(
        request, "sala.html", {"codigo": sala.codigo}
    )


@app.post("/api/partidas")
async def crear_partida(entrada: EntradaAlias):
    try:
        sala, anfitrion = gestor.crear_sala(entrada.alias)
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
                        sala.formular_sospecha(
                            jugador_id,
                            datos.get("sospechoso_id", ""),
                            datos.get("lugar_id", ""),
                            datos.get("objeto_id", ""),
                        )
                except ValueError as exc:
                    await ws.send_json({"tipo": "error", "detalle": str(exc)})
                    continue
                await difundir(sala.codigo)
                programar_turno_pnj(sala.codigo)
            elif accion == "mostrar_carta":
                try:
                    async with cerrojos.setdefault(sala.codigo, asyncio.Lock()):
                        sala.mostrar_carta(jugador_id, datos.get("carta_id", ""))
                except ValueError as exc:
                    await ws.send_json({"tipo": "error", "detalle": str(exc)})
                    continue
                await difundir(sala.codigo)
                programar_turno_pnj(sala.codigo)
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
            else:
                await difundir(sala.codigo)
        # En partida iniciada el jugador y su mano se conservan
        # para que pueda reconectar con su jugador_id.
