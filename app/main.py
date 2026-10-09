"""Servidor FastAPI multijugador con mesa fija y turnos humanos/PNJ.

Cada conexión WebSocket humana recibe únicamente su estado privado. Los PNJ
no tienen conexiones simuladas y el misterio nunca sale del servidor.
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import deque

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, Response
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
from app.motor import persistencia
from app.motor.sala import (
    ESTADO_ESPERANDO,
    ESTADO_INICIADA,
    ESTADO_TERMINADA,
    JUGADA_ESPERANDO_MOVIMIENTO,
    JUGADA_ESPERANDO_REFUTADOR,
    JUGADA_ESPERANDO_SOSPECHA,
    JUGADA_PRESENTANDO_SOSPECHA,
    TIPO_HUMANO,
    TIPO_PNJ,
    MODO_TABLERO,
    MENSAJE_SIN_AUTORIDAD_ADMIN,
    GestorSalas,
)

app = FastAPI(title="El Misterio del Medallón")

# Cabecera con la credencial administrativa. En la URL nunca: una URL queda
# en el historial, en los registros del servidor y en el Referer.
CABECERA_CREDENCIAL_ADMIN = "X-Token-Admin"

# Tope del archivo de guardado al cargarlo. Una partida de 6 personas ocupa
# unos pocos kilobytes; 2 MB es de sobra y corta cualquier abuso.
TAMANO_MAXIMO_CARGA = 2 * 1024 * 1024

app.mount("/static", StaticFiles(directory="app/static"), name="static")
plantillas = Jinja2Templates(directory="app/templates")

gestor = GestorSalas()
# codigo sala -> jugador_id -> websockets abiertos de ese jugador
conexiones: dict[str, dict[str, list[WebSocket]]] = {}
cerrojos: dict[str, asyncio.Lock] = {}
tareas_pnj: dict[str, asyncio.Task] = {}
HISTORIAL_CHAT_MAXIMO = 100
LONGITUD_MENSAJE_CHAT_MAXIMA = 300
VENTANA_CHAT_SEGUNDOS = 10.0
MENSAJES_CHAT_POR_VENTANA = 5
# El chat vive en memoria, separado de Sala y de la lista blanca de guardado.
historial_chat: dict[str, deque[dict[str, str]]] = {}
envios_chat: dict[str, dict[str, deque[float]]] = {}
cerrojos_chat: dict[str, asyncio.Lock] = {}
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

    Microfase 2: las tres duraciones son esperas AUTOMÁTICAS y siguen la
    velocidad de la sala. Sus diferencias entre sí (los 2 s de lectura)
    se conservan porque se desplazan por el mismo delta. Con la velocidad
    inicial el resultado es idéntico al de antes.
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
            return sala.espera_automatica(PAUSA_LECTURA_SOSPECHA_PNJ_SEGUNDOS)
        if investigador is not None and investigador.get("tipo") != TIPO_PNJ:
            return sala.espera_automatica(PAUSA_TRAS_JUGADA_HUMANA_SEGUNDOS)
    return sala.espera_automatica(PAUSA_TURNO_PNJ_SEGUNDOS)


async def _esperar_turno_pnj(sala, segundos: float) -> None:
    """La ÚNICA espera de la cadena de PNJ, envuelta para poder congelarla.

    Registra lo que queda en curso para que una pausa no lo pierda al
    cancelar la tarea. El `asyncio.sleep` sigue siendo UNO solo, con su
    duración ya calculada: no se trocea en fracciones ni se relee la
    velocidad a mitad de espera.
    """
    inicio = time.monotonic()
    sala.espera_pnj_en_curso = {"segundos": segundos, "inicio": inicio}
    try:
        await asyncio.sleep(segundos)
    finally:
        sala.espera_pnj_en_curso = None


async def _cadena_turnos_pnj(codigo: str) -> None:
    """Unica autoridad automatica por sala; nunca espera sosteniendo el lock."""
    tarea_actual = asyncio.current_task()
    try:
        while True:
            sala = gestor.obtener(codigo)
            if sala is None:
                return
            async with cerrojos.setdefault(codigo, asyncio.Lock()):
                if sala.pausada:
                    return
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
                # Microfase 3: si la pausa interrumpió una espera, se retoma
                # con el tiempo que le QUEDABA, no con uno nuevo. Nadie acts
                # antes de tiempo; y si ya había-consumerado su espera, actúa
                # de inmediato, que es lo que le correspondía.
                restante = sala.turno_pnj_espera_restante
                if restante is not None:
                    sala.turno_pnj_espera_restante = None
                    pausa = max(0.0, restante)
                else:
                    pausa = pausa_antes_de_turno_pnj(sala)
            # El resultado anterior sigue en ultima_jugada durante toda la
            # pausa. No sostenemos el cerrojo mientras los humanos lo leen.
            await _esperar_turno_pnj(sala, pausa)
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
    # Microfase 3: con la partida en pausa no arranca ninguna tarea
    # automática. Es la ÚNICA puerta de arranque, así que vale también para
    # una reconexión o para una acción que llegue durante la pausa.
    if sala.pausada:
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
    if sala.pausada:
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
        or sala.pausada
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
    if sala.pausada:
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


# --- Pausa de la partida (Microfase 3) ------------------------------------
# La sala congela sus propios plazos (desplazar_plazos) y aquí se detienen
# las CUATRO tareas automáticas. Se reanudan con los mismos chores de
# programación de siempre: son idempotentes y nunca reinician un plazo, que
# es justo lo que hace falta para no saltarse ni duplicar nada.


def detener_tareas_automaticas(codigo: str) -> None:
    """Cancela la cadena PNJ y los tres watchdogs de la sala."""
    tarea = tareas_pnj.pop(codigo, None)
    try:
        actual = asyncio.current_task()
    except RuntimeError:
        actual = None
    if tarea and tarea is not actual:
        tarea.cancel()
    cancelar_timeout_refutacion(codigo)
    cancelar_presentacion_sospecha(codigo)
    cancelar_bloqueo(codigo)


def pausar_partida(sala) -> None:
    """Detiene la sala: primero conserva lo pendiente, después corta tareas."""
    if not sala.pausada:
        return
    # Un PNJ que ya estaba esperando sigue esperando lo que le quedaba: se
    # calcula ANTES de cancelar la tarea, que es cuando desaparece el dato.
    en_curso = sala.espera_pnj_en_curso
    sala.turno_pnj_espera_restante = (
        max(0.0, en_curso["segundos"] - (time.monotonic() - en_curso["inicio"]))
        if en_curso
        else None
    )
    sala.pnj_pensando_id = None
    detener_tareas_automaticas(sala.codigo)


def reanudar_partida(sala) -> None:
    """Rearma las tareas que hagan falta. Los plazos ya vienen desplazados."""
    if sala.pausada:
        return
    codigo = sala.codigo
    programar_turno_pnj(codigo)
    programar_timeout_refutacion(codigo)
    programar_presentacion_sospecha(codigo)
    programar_bloqueo(codigo)


def registrar_sala(sala) -> None:
    """Prepara las estructuras internas de una sala recién importada.

    Solo el cerrojo y el registro de conexiones: NUNCA las tareas. Importar no
    es jugar, y arrancar aquí una cadena de PNJ sería ejecutar una acción que
    el administrador no ha pedido.
    """
    conexiones.setdefault(sala.codigo, {})
    cerrojos.setdefault(sala.codigo, asyncio.Lock())


def reactivar_sala(sala) -> None:
    """Vuelve a armar las tareas automáticas de una sala importada.

    Los cuatro `programar_*` son idempotentes y respetan la pausa, así que
    llamarlos dos veces no duplica nada y una sala en pausa no arranca nada.
    """
    if sala.estado == ESTADO_TERMINADA:
        return
    programar_turno_pnj(sala.codigo)
    programar_timeout_refutacion(sala.codigo)
    programar_presentacion_sospecha(sala.codigo)
    programar_bloqueo(sala.codigo)


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


async def _enviar_privado(
    sala, jugador_id: str, ws: WebSocket, incluir_chat: bool = False
) -> bool:
    """Envía a una conexión el estado privado de su jugador."""
    contenido = sala.estado_privado(jugador_id)
    jugador = sala.jugador_por_id(jugador_id)
    if incluir_chat and jugador and jugador["tipo"] == TIPO_HUMANO:
        contenido["chat_historial"] = list(historial_chat.setdefault(
            sala.codigo, deque(maxlen=HISTORIAL_CHAT_MAXIMO)
        ))
    try:
        await ws.send_json({"tipo": "estado_privado", "sala": contenido})
        return True
    except Exception:
        return False


async def _enviar_credencial_admin(sala, jugador_id: str, ws: WebSocket) -> bool:
    """Entrega el secreto administrativo solo al asiento anfitrión.

    Va en un mensaje propio, dirigido únicamente a esa conexión. Nunca entra
    en estado_privado(), en estado_publico() ni en difundir(), de modo que
    ningún otro jugador puede recibirlo por el WebSocket.

    No se empuja al conectar: solo se entrega si el propio anfitrión lo
    pide, para que recuperar el secreto tras una recarga no altere el flujo
    de mensajes de ninguna otra acción.
    """
    credencial = sala.credencial_admin_de(jugador_id)
    if credencial is None:
        return False
    try:
        await ws.send_json(
            {"tipo": "credencial_admin", "credencial": credencial}
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


async def _difundir_mensaje_chat(sala, mensaje: dict[str, str]) -> None:
    """Entrega chat solo a conexiones humanas de esta sala."""
    for jugador_id, pantallas in list(conexiones.get(sala.codigo, {}).items()):
        jugador = sala.jugador_por_id(jugador_id)
        if not jugador or jugador["tipo"] != TIPO_HUMANO:
            continue
        for ws in list(pantallas):
            try:
                await ws.send_json({"tipo": "chat_mensaje", "mensaje": mensaje})
            except Exception:
                _desconectar_ws(sala.codigo, jugador_id, ws)


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
    # Quien crea la partida ES el anfitrión: es el único que recibe el
    # secreto administrativo, y solo en esta respuesta.
    return {
        "codigo": sala.codigo,
        "jugador_id": anfitrion["id"],
        "alias": anfitrion["alias"],
        "credencial_admin": sala.credencial_admin_de(anfitrion["id"]),
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
    # Quien se une no es anfitrión: no recibe ninguna credencial administrativa.
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


@app.post("/api/cargar")
async def cargar_partida(request: Request):
    """Restaura una partida guardada (Microfase 6).

    El CUERPO de la petición ES el archivo de guardado, en JSON. Se lee en
    crudo y con límite de tamaño antes de hacer nada: un archivo enorme se
    rechaza sin llegar a analizarlo.

    Quien carga el archivo demuestra tener la copia, y eso autoriza a
    restaurar ESA copia. La credencial que viaja dentro solo vale para la
    sala que se reconstruye aquí: nunca para otra sala activa distinta, que
    tiene su propio secreto.

    Las tareas NO se reactivan aquí: eso ocurre cuando el anfitrión abre su
    sala y se conecta. Así ninguna acción automática puede dispararse antes
    de que haya recuperado su sesión.
    """
    cuerpo = await request.body()
    if len(cuerpo) > TAMANO_MAXIMO_CARGA:
        return _respuesta_error(
            "El archivo es demasiado grande para ser una partida guardada.", 413
        )
    if not cuerpo.strip():
        return _respuesta_error("No has elegido ningún archivo.", 400)
    try:
        datos = json.loads(cuerpo)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _respuesta_error("El archivo no es un JSON válido.", 400)
    try:
        sala, reenumerada = gestor.importar_partida(datos)
    except ValueError as exc:
        # El mensaje del motor ya es claro y no incluye cartas ni secretos.
        return _respuesta_error(str(exc), 400)
    registrar_sala(sala)
    anfitrion = sala.anfitrion()
    return {
        "codigo": sala.codigo,
        "jugador_id": anfitrion["id"],
        "alias": anfitrion["alias"],
        "credencial_admin": sala.credencial_admin,
        "codigo_original": datos.get("estado", {}).get("codigo", sala.codigo),
        "codigo_reenumerado": reenumerada,
        "resumen": datos.get("resumen", {}),
        "sala": sala.estado_publico(),
    }


@app.get("/api/partidas/{codigo}/guardar")
async def guardar_partida(codigo: str, request: Request):
    """Descarga el archivo de guardado de la sala (Microfase 4).

    La credencial del anfitrión viaja en la CABECERA `X-Token-Admin`, nunca
    en la URL: una URL queda en el historial del navegador, en los registros
    y en el `Referer`. Sin esa cabecera no se descarga nada, aunque se conozca
    el código de la sala.

    El volcado se hace dentro del cerrojo para que sea coherente, y nunca se
    manda por el WebSocket: el archivo lleva la solución, las manos y las
    notas privadas, así que sale solo por aquí y con `no-store`.
    """
    sala = gestor.obtener(codigo)
    if sala is None:
        return _respuesta_error("La sala no existe. Revisa el código.", 404)
    credencial = request.headers.get(CABECERA_CREDENCIAL_ADMIN)
    if not sala.credencial_admin_valida(credencial):
        return _respuesta_error(MENSAJE_SIN_AUTORIDAD_ADMIN, 403)
    async with cerrojos.setdefault(sala.codigo, asyncio.Lock()):
        archivo = persistencia.exportar(sala)
    return Response(
        content=persistencia.a_json(archivo),
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{persistencia.nombre_archivo(sala.codigo)}"'
            ),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@app.websocket("/ws/{codigo}/{jugador_id}")
async def websocket_sala(ws: WebSocket, codigo: str, jugador_id: str):
    sala = gestor.obtener(codigo)
    if sala is None or sala.jugador_por_id(jugador_id) is None:
        await ws.close(code=4404)
        return
    await ws.accept()
    # Reconexión: el jugador conserva su id, su mano y su rol.
    conexiones.setdefault(sala.codigo, {}).setdefault(jugador_id, []).append(ws)
    await _enviar_privado(sala, jugador_id, ws, incluir_chat=True)
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
            if not isinstance(datos, dict):
                await ws.send_json({
                    "tipo": "error_chat",
                    "detalle": "El mensaje de chat no es válido.",
                })
                continue
            accion = datos.get("accion")
            if accion == "chat":
                jugador = sala.jugador_por_id(jugador_id)
                texto = datos.get("texto")
                if not jugador or jugador["tipo"] != TIPO_HUMANO:
                    await ws.send_json({
                        "tipo": "error_chat",
                        "detalle": "Solo los jugadores humanos pueden usar el chat.",
                    })
                    continue
                if not isinstance(texto, str) or not texto.strip():
                    await ws.send_json({
                        "tipo": "error_chat",
                        "detalle": "Escribe un mensaje antes de enviarlo.",
                    })
                    continue
                texto = texto.strip()
                if len(texto) > LONGITUD_MENSAJE_CHAT_MAXIMA:
                    await ws.send_json({
                        "tipo": "error_chat",
                        "detalle": "El mensaje no puede superar 300 caracteres.",
                    })
                    continue

                async with cerrojos_chat.setdefault(
                    sala.codigo, asyncio.Lock()
                ):
                    ahora = time.monotonic()
                    por_jugador = envios_chat.setdefault(sala.codigo, {})
                    marcas = por_jugador.setdefault(jugador_id, deque())
                    while marcas and ahora - marcas[0] >= VENTANA_CHAT_SEGUNDOS:
                        marcas.popleft()
                    if len(marcas) >= MENSAJES_CHAT_POR_VENTANA:
                        await ws.send_json({
                            "tipo": "error_chat",
                            "detalle": "Espera un momento antes de enviar más mensajes.",
                        })
                        continue
                    marcas.append(ahora)
                    mensaje_chat = {
                        "jugador_id": jugador_id,
                        "alias": jugador["alias"],
                        "texto": texto,
                    }
                    historial_chat.setdefault(
                        sala.codigo, deque(maxlen=HISTORIAL_CHAT_MAXIMO)
                    ).append(mensaje_chat)
                    await _difundir_mensaje_chat(sala, mensaje_chat)
                continue
            # Microfase 3: con la partida en pausa el servidor RECHAZA toda
            # acción de juego, venga del botón que venga. Solo se acepta
            # reanudar (y pedir la credencial). Va antes de tocar nada.
            try:
                sala.comprobar_accion_en_pausa(accion)
            except ValueError as exc:
                await ws.send_json({"tipo": "error", "detalle": str(exc)})
                continue
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
            elif accion in ("pausar_partida", "reanudar_partida"):
                # Microfase 3. Ambas pasan por la credencial del anfitrión.
                # Pausar congela los plazos y corta las cuatro tareas; reanudar
                # las rearma con los plazos ya desplazados.
                credencial = datos.get("credencial_admin")
                try:
                    async with cerrojos.setdefault(sala.codigo, asyncio.Lock()):
                        if accion == "pausar_partida":
                            if sala.pausar_partida(jugador_id, credencial):
                                pausar_partida(sala)
                        else:
                            if sala.reanudar_partida(jugador_id, credencial):
                                reanudar_partida(sala)
                except ValueError as exc:
                    await ws.send_json({"tipo": "error", "detalle": str(exc)})
                    continue
                await difundir(sala.codigo)
            elif accion in ("acelerar_acciones", "ralentizar_acciones"):
                # Microfase 2. La velocidad es de la SALA: se valida con la
                # credencial del anfitrión (nunca por el botón) y se difunde
                # a todos para que el ritmo sea el mismo en cada pantalla.
                #
                # No se recalcula una espera ya en curso: la cadena PNJ tomó
                # su duración ANTES de dormir y la respeta entera. Solo la
                # siguiente espera usa el valor nuevo. Así un MÁS RÁPIDO no
                # puede adelantar un PNJ por encima de la lectura pendiente y
                # provocar una carrera o un turno duplicado.
                credencial = datos.get("credencial_admin")
                try:
                    mover = (
                        sala.acelerar_acciones
                        if accion == "acelerar_acciones"
                        else sala.ralentizar_acciones
                    )
                    mover(jugador_id, credencial)
                except ValueError as exc:
                    await ws.send_json({"tipo": "error", "detalle": str(exc)})
                    continue
                await difundir(sala.codigo)
            elif accion == "pedir_credencial_admin":
                # Recuperar el secreto tras una recarga no altera el estado
                # de la partida. Solo se lo pide el propio anfitrión, desde
                # esta misma conexión, y solo se le responde a él.
                if not sala.es_anfitrion(jugador_id):
                    await ws.send_json(
                        {"tipo": "error", "detalle": MENSAJE_SIN_AUTORIDAD_ADMIN}
                    )
                    continue
                await _enviar_credencial_admin(sala, jugador_id, ws)
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
                historial_chat.pop(sala.codigo, None)
                envios_chat.pop(sala.codigo, None)
                cerrojos_chat.pop(sala.codigo, None)
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
