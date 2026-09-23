"""Servidor FastAPI del juego multijugador (Sprints 1, 2, 3 + Microfase 3B).

Microfase 3B: hoja de investigación privada por jugador. Cada conexión
WebSocket recibe únicamente su estado privado (cartas + su hoja).
El misterio nunca sale del servidor.
"""
from __future__ import annotations

import asyncio

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.datos.jarandilla import SOSPECHOSOS
from app.motor.sala import ESTADO_ESPERANDO, GestorSalas

app = FastAPI(title="Cluedo Jarandilla — El misterio del medallón imperial")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
plantillas = Jinja2Templates(directory="app/templates")

gestor = GestorSalas()
# codigo sala -> jugador_id -> websockets abiertos de ese jugador
conexiones: dict[str, dict[str, list[WebSocket]]] = {}
cerrojos: dict[str, asyncio.Lock] = {}


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
            elif accion == "elegir_personaje":
                try:
                    sala.elegir_personaje(jugador_id, datos.get("personaje_id", ""))
                except ValueError as exc:
                    await ws.send_json({"tipo": "error", "detalle": str(exc)})
                    continue
                await difundir(sala.codigo)
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
            elif accion == "mostrar_carta":
                try:
                    async with cerrojos.setdefault(sala.codigo, asyncio.Lock()):
                        sala.mostrar_carta(jugador_id, datos.get("carta_id", ""))
                except ValueError as exc:
                    await ws.send_json({"tipo": "error", "detalle": str(exc)})
                    continue
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
            else:
                await difundir(sala.codigo)
        # En partida iniciada el jugador y su mano se conservan
        # para que pueda reconectar con su jugador_id.
