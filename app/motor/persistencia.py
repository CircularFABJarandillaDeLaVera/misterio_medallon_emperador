"""Guardado de una partida en un archivo portable (Microfase 4).

SOLO EXPORTACIÓN. Cargar la partida es otra fase.

Reglas de este módulo:

- Lista blanca explícita. Se guarda lo que se nombra aquí y nada más: si
  mañana se añade un campo a la sala, este archivo NO lo guarda hasta que se
  añada también a la lista.
- SIN MUTAR LA SALA. `exportar()` solo lee y copia.
- Los tiempos se guardan como RESTANTE, nunca como instantes absolutos.
  `time.monotonic()` no significa nada en otro proceso ni en otro ordenador.
- Sin `pickle`, sin `eval`, sin `exec`: el archivo es JSON puro y la carga
  del futuro solo copiará campos de una lista blanca. Un archivo manipulado
  no puede ejecutar nada porque nunca se interpreta código.

El archivo contiene información secreta (la solución, las manos, las
anotaciones privadas y el secreto administrativo). Por eso NUNCA viaja por
el WebSocket ni entra en `estado_publico()`: solo se descarga por HTTP, con
la credencial del anfitrión en una cabecera.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from datetime import datetime, timezone

from app.datos.jarandilla import CARTA_POR_ID, CARTAS, LUGARES, OBJETOS, SOSPECHOSOS
from app.motor.sala import (
    ESTADO_ESPERANDO,
    ESTADO_INICIADA,
    ESTADO_TERMINADA,
    JUGADA_ESPERANDO_REFUTADOR,
    JUGADA_PRESENTANDO_SOSPECHA,
    MODOS,
    TIPO_HUMANO,
    TIPO_PNJ,
    VELOCIDAD_AUTOMATICA_MAXIMA,
    VELOCIDAD_AUTOMATICA_MINIMA,
    Sala,
    generar_codigo,
    resumen_credencial_admin,
    validar_alias,
)
from app.motor.tablero import TABLERO

FORMATO_PARTIDA = "misterio-medallon/partida"
VERSION_PARTIDA = 1
NOMBRE_ARCHIVO_BASE = "misterio-medallon"

# Campos del estado de la sala que se guardan, en texto llano. Es la lista
# blanca: lo que no aparece aquí, no viaja.
CAMPOS_DE_SALA = (
    "codigo",
    "modo",
    "estado",
    "estado_jugada",
    "numero_turno",
    "turno_actual",
    "secuencia_presentacion",
    "secuencia_historial",
    "secuencia_movimiento",
    "bloqueo_aviso_id",
    "resultado_final",
    "ganador_id",
    "pnj_pensando_id",
    "velocidad_acciones",
    "tirada_pendiente",
)

# Claves del jugador que se guardan. Las nueve actuales del motor.
CAMPOS_DE_JUGADOR = (
    "id",
    "alias",
    "es_anfitrion",
    "personaje_id",
    "tipo",
    "activo_investigacion",
    "refutacion_automatica",
    "decision_refutacion_pendiente",
    "resolucion_fallida",
)


def _copia(valor):
    """Copia profunda de datos JSON, sin compartir nada con la sala."""
    if isinstance(valor, dict):
        return {clave: _copia(contenido) for clave, contenido in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_copia(contenido) for contenido in valor]
    if isinstance(valor, set):
        return sorted(valor)
    return valor


def _restante(deadline: float | None, ahora: float) -> float | None:
    """Segundos que quedan. Nunca un instante absoluto."""
    if deadline is None:
        return None
    return round(max(0.0, deadline - ahora), 3)


def exportar_jugadores(sala) -> list[dict]:
    return [{campo: _copia(jugador[campo]) for campo in CAMPOS_DE_JUGADOR} for jugador in sala.jugadores]


def exportar_posiciones(sala) -> dict[str, str]:
    """`posiciones` es un objeto del motor, no un dict: se aplana."""
    return {
        jugador["id"]: posicion
        for jugador in sala.jugadores
        if (posicion := sala.posiciones.obtener(jugador["id"])) is not None
    }


def exportar_presentacion(sala, ahora: float) -> dict | None:
    """La presentación con sus tiempos como restante y su edad."""
    presentacion = sala.presentacion_sospecha
    if presentacion is None:
        return None
    datos = {
        "id": presentacion["id"],
        "tipo": presentacion.get("tipo", "sospecha"),
        # Cuánto lleva abierta: permite reconstruir `inicio` en la carga.
        "inicio_restante": round(max(0.0, ahora - presentacion["inicio"]), 3),
        "investigador_id": presentacion["investigador_id"],
        "investigador_alias": presentacion.get("investigador_alias"),
        "sospecha": _copia(presentacion.get("sospecha", {})),
        "participantes": {
            jugador_id: {
                "listo": bool(estado.get("listo")),
                "restante": _restante(estado.get("deadline"), ahora),
            }
            for jugador_id, estado in presentacion["participantes"].items()
        },
    }
    for opcional in ("resultado", "refutador_alias", "movimiento_pnj"):
        if presentacion.get(opcional) is not None:
            datos[opcional] = _copia(presentacion[opcional])
    return datos


def exportar_bloqueo(sala, ahora: float) -> dict:
    """El aviso de inactividad, con su plazo como restante."""
    return {
        "jugador_id": sala.bloqueo_jugador_id,
        "accion": sala.bloqueo_accion,
        "restante": _restante(sala.bloqueo_deadline, ahora),
        "aviso_emitido": bool(sala.bloqueo_aviso_emitido),
    }


def exportar_pausa(sala, ahora: float) -> dict:
    """La pausa, con lo que lleva durando, no con su instante."""
    return {
        "pausada": bool(sala.pausada),
        "duracion": (
            round(max(0.0, ahora - sala.pausa_marca), 3)
            if sala.pausada and sala.pausa_marca is not None
            else 0.0
        ),
    }


def exportar_espera_pnj(sala, ahora: float) -> dict:
    """Lo que le quedaba a un PNJ que ya estaba esperando."""
    en_curso = sala.espera_pnj_en_curso
    if en_curso:
        restante = en_curso["segundos"] - (ahora - en_curso["inicio"])
    elif sala.turno_pnj_espera_restante is not None:
        restante = sala.turno_pnj_espera_restante
    else:
        restante = None
    return {
        "restante": round(max(0.0, restante), 3) if restante is not None else None,
        "turno_pnj_espera_restante": (
            round(sala.turno_pnj_espera_restante, 3)
            if sala.turno_pnj_espera_restante is not None
            else None
        ),
    }


def exportar_estado(sala, ahora: float) -> dict:
    """El estado completo de la sala. Todo lo que la lista blanca nombra."""
    estado = {campo: _copia(getattr(sala, campo)) for campo in CAMPOS_DE_SALA}
    estado.update(
        {
            # --- identidades y autoridad ------------------------------
            # El secreto viaja en claro a propósito: quien tiene el archivo
            # ES el anfitrión en cualquier ordenador, sin depender de esta
            # instalación. El archivo es confidencial.
            "jugadores": exportar_jugadores(sala),
            "credencial_admin": sala.credencial_admin,
            # --- reparto y conocimiento --------------------------------
            "misterio": _copia(sala.misterio),
            "manos": {jid: _copia(cartas) for jid, cartas in sala.manos.items()},
            "descartes": {jid: sorted(ids) for jid, ids in sala.descartes.items()},
            "vistas": {jid: sorted(ids) for jid, ids in sala.vistas.items()},
            "soluciones_deducidas": _copia(sala.soluciones_deducidas),
            "cartas_sospechadas": sorted(sala.cartas_sospechadas),
            # --- turnos y tablero -------------------------------------
            "orden_turnos": list(sala.orden_turnos),
            "posiciones": exportar_posiciones(sala),
            "posiciones_objetos": dict(sala.posiciones_objetos),
            "rutas_pendientes": {
                jid: list(ruta) for jid, ruta in sala.rutas_pendientes.items()
            },
            "movimiento_resuelto": _copia(sala.movimiento_resuelto),
            # --- jugada en curso --------------------------------------
            "ultima_jugada": _copia(sala.ultima_jugada),
            "sospecha_pendiente": _copia(sala.sospecha_pendiente),
            "presentacion_sospecha": exportar_presentacion(sala, ahora),
            # --- registro y avisos ------------------------------------
            "historial": _copia(sala.historial),
            "bloqueo": exportar_bloqueo(sala, ahora),
            "pausa": exportar_pausa(sala, ahora),
            "espera_pnj": exportar_espera_pnj(sala, ahora),
            # --- tiempos pendientes -----------------------------------
            "refutacion_restante": _restante(sala.refutacion_deadline, ahora),
        }
    )
    return estado


def resumen_legible(sala) -> dict:
    """Lo primero que se lee al abrir el archivo. Sin datos privados."""
    en_turno = sala.jugador_en_turno()
    return {
        "codigo": sala.codigo,
        "modo": sala.modo,
        "estado": sala.estado,
        "fase": sala.estado_jugada,
        "turno": en_turno["alias"] if en_turno else None,
        "turno_tipo": en_turno["tipo"] if en_turno else None,
        "anfitrion": (
            sala.anfitrion()["alias"] if sala.anfitrion() else None
        ),
        "participantes": len(sala.jugadores),
        "humanos": sum(1 for j in sala.jugadores if j["tipo"] != "pnj"),
        "turno_numero": sala.numero_turno,
        "velocidad_acciones": sala.velocidad_acciones,
        "pausada": bool(sala.pausada),
        "terminada": sala.estado == "terminada",
    }


def huella(estado: dict) -> str:
    """SHA-256 del estado en forma canónica.

    Detecta corrupción o edición del archivo. No es autenticación: no lleva
    clave, solo comprueba que el contenido llegó íntegro.
    """
    canonico = json.dumps(
        estado, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def exportar(sala, ahora: float | None = None) -> dict:
    """Construye el archivo de guardado. NO modifica la sala.

    El llamante debe sostener el cerrojo de la sala mientras dura la llamada,
    para que el volcado sea coherente.
    """
    instante = time.monotonic() if ahora is None else ahora
    estado = exportar_estado(sala, instante)
    return {
        "formato": FORMATO_PARTIDA,
        "version": VERSION_PARTIDA,
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "resumen": resumen_legible(sala),
        "integridad": {"algoritmo": "sha-256", "valor": huella(estado)},
        "estado": estado,
    }


def a_json(datos: dict) -> str:
    return json.dumps(datos, indent=2, ensure_ascii=False, sort_keys=True)


def nombre_archivo(codigo: str) -> str:
    limpio = "".join(
        caracter for caracter in (codigo or "sala") if caracter.isalnum() or caracter == "-"
    )
    return f"{NOMBRE_ARCHIVO_BASE}-{limpio or 'sala'}.json"


# --- Validación del formato ---------------------------------------------
# AVISO IMPORTANTE sobre la integridad: el SHA-256 detecta alterações
# ACCIDENTALES (un archivo truncado o corrupto). NO es una firma de
# seguridad: cualquiera que edite el archivo puede recalcular la huella. No
# debe tratarse como prueba de que el archivo viene de una fuente fiable.

CLAVES_OBLIGATORIAS = (
    "formato",
    "version",
    "generado",
    "resumen",
    "integridad",
    "estado",
)

CLAVES_OBLIGATORIAS_ESTADO = (
    "jugadores",
    "credencial_admin",
    "misterio",
    "manos",
    "descartes",
    "vistas",
    "soluciones_deducidas",
    "cartas_sospechadas",
    "orden_turnos",
    "posiciones",
    "posiciones_objetos",
    "rutas_pendientes",
    "movimiento_resuelto",
    "ultima_jugada",
    "sospecha_pendiente",
    "presentacion_sospecha",
    "historial",
    "bloqueo",
    "pausa",
    "espera_pnj",
    "refutacion_restante",
    "velocidad_acciones",
)

CLAVES_DE_CARTA = ("id", "nombre", "categoria")
CATEGORIAS = ("sospechoso", "lugar", "objeto")
IDS_CATEGORIA = {
    "sospechoso": {carta["id"] for carta in SOSPECHOSOS},
    "lugar": {carta["id"] for carta in LUGARES},
    "objeto": {carta["id"] for carta in OBJETOS},
}
TIPOS_DE_JUGADOR = (TIPO_HUMANO, TIPO_PNJ)
ESTADOS_JUGADA = (
    "esperando_sospecha",
    "esperando_eleccion_refutador",
    "esperando_movimiento",
    "esperando_destino",
    "presentando_sospecha",
)
RESULTADOS_FINALES = ("resuelto", "sin_resolver")
MAX_SEGUNDOS_RESTANTES = 86400.0  # un día: cota de sanidad, no de juego

# Claves que nunca pueden entrar en un archivo: son de la clase, no del
# estado. No se instrospecciona nada, pero se rechazan por si acaso.
CLAVES_PROHIBIDAS = frozenset(
    {
        "__class__",
        "__reduce__",
        "__reduce_ex__",
        "__init__",
        "__globals__",
        "__builtins__",
        "__dict__",
        "__module__",
    }
)


def _error(mensaje: str) -> None:
    """Error de carga. Nunca incluye cartas ni notas privadas: solo la
    clave que falla, para no filtrar información de la partida por el
    mensaje."""
    raise ValueError(mensaje)


def _es_numero(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def _es_restante(valor) -> bool:
    if valor is None:
        return True
    if not _es_numero(valor) or not math.isfinite(valor):
        return False
    return 0.0 <= valor <= MAX_SEGUNDOS_RESTANTES


def _sin_claves_prohibidas(valor, profundidad: int = 0) -> None:
    """Recorre el archivo y rechaza cualquier clave de clase o metadato."""
    if profundidad > 12:
        _error("El archivo tiene una estructura demasiado anidada.")
    if isinstance(valor, dict):
        for clave, contenido in valor.items():
            if not isinstance(clave, str):
                _error("El archivo tiene una clave que no es texto.")
            if clave in CLAVES_PROHIBIDAS or clave.startswith("__"):
                _error("El archivo contiene una clave no permitida.")
            _sin_claves_prohibidas(contenido, profundidad + 1)
    elif isinstance(valor, list):
        for contenido in valor:
            _sin_claves_prohibidas(contenido, profundidad + 1)


def _validar_carta(carta, contexto: str) -> str:
    if not isinstance(carta, dict):
        _error(f"{contexto}: una carta no es un objeto.")
    for clave in CLAVES_DE_CARTA:
        if clave not in carta:
            _error(f"{contexto}: a una carta le falta '{clave}'.")
    identificador = carta["id"]
    if identificador not in CARTA_POR_ID:
        _error(f"{contexto}: hay una carta que no existe en el juego.")
    if carta["categoria"] != CARTA_POR_ID[identificador]["categoria"]:
        _error(f"{contexto}: una carta no es de la categoría que dice.")
    return identificador


def _validar_jugadores(estado) -> dict[str, dict]:
    jugadores = estado["jugadores"]
    if not isinstance(jugadores, list) or not jugadores:
        _error("La partida no tiene participantes.")
    por_id: dict[str, dict] = {}
    personajes: set[str] = set()
    anfitriones = 0
    for jugador in jugadores:
        if not isinstance(jugador, dict):
            _error("Un participante no es un objeto.")
        for campo in CAMPOS_DE_JUGADOR:
            if campo not in jugador:
                _error(f"Un participante no tiene '{campo}'.")
        if set(jugador) - set(CAMPOS_DE_JUGADOR):
            _error("Un participante tiene campos que no se guardan.")
        identificador = jugador["id"]
        if not isinstance(identificador, str) or not identificador:
            _error("Un participante no tiene identificador.")
        if identificador in por_id:
            _error("Hay dos participantes con el mismo identificador.")
        por_id[identificador] = jugador

        if jugador["tipo"] not in TIPOS_DE_JUGADOR:
            _error("Un participante tiene un tipo que no existe.")
        if not isinstance(jugador["es_anfitrion"], bool):
            _error("El rol de anfitrión no es un sí o un no.")
        if not isinstance(jugador["activo_investigacion"], bool):
            _error("La eliminación de un participante no es un sí o un no.")
        anfitriones += 1 if jugador["es_anfitrion"] else 0

        # El alias largo y con acentos es el de los PNJ: son nombres
        # canónicos, no alias escritos por una persona. El límite de 20
        # caracteres solo aplica a los humanos.
        alias = jugador["alias"]
        if not isinstance(alias, str) or not alias.strip():
            _error("Un participante no tiene alias.")
        if jugador["tipo"] == TIPO_HUMANO and validar_alias(alias):
            _error("Un participante tiene un alias que no vale.")
        personaje = jugador["personaje_id"]
        if personaje is None:
            # Solo en el lobby se entra sin personaje. En una partida empezada
            # o terminada, todo el mundo tiene el suyo.
            if estado["estado"] != ESTADO_ESPERANDO:
                _error("Un participante no tiene personaje.")
        elif personaje not in IDS_CATEGORIA["sospechoso"]:
            _error("Un participante tiene un personaje que no existe.")
        else:
            if personaje in personajes:
                _error("Hay dos participantes con el mismo personaje.")
            personajes.add(personaje)

        if jugador["tipo"] == TIPO_PNJ and not identificador.startswith("pnj-"):
            _error("Un PNJ no tiene un identificador de PNJ.")
        if not isinstance(jugador["refutacion_automatica"], bool):
            _error("La preferencia de refutación no es un sí o un no.")
        if not isinstance(jugador["decision_refutacion_pendiente"], bool):
            _error("La decisión de refutación no es un sí o un no.")
        if jugador["resolucion_fallida"] is not None and not isinstance(
            jugador["resolucion_fallida"], dict
        ):
            _error("Una acusación fallida no tiene la forma correcta.")
    if anfitriones != 1:
        _error("La partida debe tener exactamente un anfitrión.")
    return por_id


def _validar_credencial(estado) -> None:
    credencial = estado["credencial_admin"]
    if not isinstance(credencial, str) or len(credencial) < 32:
        _error("El archivo no trae una credencial de anfitrión válida.")
    if credencial != credencial.strip() or any(
        caracter.isspace() for caracter in credencial
    ):
        _error("La credencial de anfitrión no tiene la forma correcta.")


def _validar_misterio_y_reparto(estado, por_id) -> None:
    """La solución no puede estar repartida, y cada carta se da una vez."""
    misterio = estado["misterio"]
    if estado["estado"] == ESTADO_ESPERANDO:
        if misterio is not None:
            _error("Una partida sin empezar no tiene solución.")
        if any(manos for manos in estado["manos"].values()):
            _error("Una partida sin empezar no tiene cartas repartidas.")
        return

    if not isinstance(misterio, dict):
        _error("La partida no tiene solución.")
    solucion = set()
    for categoria in CATEGORIAS:
        if categoria not in misterio:
            _error("La solución está incompleta.")
        carta = misterio[categoria]
        if not isinstance(carta, dict):
            _error("La solución tiene una entrada que no es una carta.")
        identificador = _validar_carta(carta, "La solución")
        if identificador not in IDS_CATEGORIA[categoria]:
            _error("La solución tiene una carta de otra categoría.")
        if identificador in solucion:
            _error("La solución repite una carta.")
        solucion.add(identificador)
    if len(solucion) != 3:
        _error("La solución no tiene las tres cartas.")

    repartidas: set[str] = set()
    manos = estado["manos"]
    if not isinstance(manos, dict):
        _error("El reparto no es un objeto.")
    for jugador_id, cartas in manos.items():
        if jugador_id not in por_id:
            _error("El reparto cita a un participante que no está.")
        if not isinstance(cartas, list) or not cartas:
            _error("Un participante no tiene cartas.")
        for carta in cartas:
            identificador = _validar_carta(carta, "Una mano")
            if identificador in solucion:
                _error("Una carta de la solución está repartida.")
            if identificador in repartidas:
                _error("Una carta está repartida dos veces.")
            repartidas.add(identificador)

    # 21 cartas canónicas: 18 repartidas y 3 guardadas.
    esperadas = len(CARTAS) - len(solucion)
    if len(repartidas) != esperadas:
        _error("El reparto no cuadra con las cartas del juego.")


def _validar_investigacion(estado, por_id) -> None:
    for clave in ("descartes", "vistas", "soluciones_deducidas"):
        contenido = estado[clave]
        if not isinstance(contenido, dict):
            _error(f"'{clave}' no es un objeto.")
        for jugador_id, valor in contenido.items():
            if jugador_id not in por_id:
                _error(f"'{clave}' cita a un participante que no está.")
            if clave == "soluciones_deducidas":
                if not isinstance(valor, dict) or set(valor) != {
                    "sospechoso_id",
                    "lugar_id",
                    "objeto_id",
                }:
                    _error("Una deducción de PNJ no tiene la forma correcta.")
                continue
            if not isinstance(valor, list) or any(
                carta not in CARTA_POR_ID for carta in valor
            ):
                _error("Una hoja de investigación cita una carta que no existe.")
    if not isinstance(estado["cartas_sospechadas"], list):
        _error("La memoria de sospechas no es una lista.")
    if any(carta not in CARTA_POR_ID for carta in estado["cartas_sospechadas"]):
        _error("La memoria de sospechas cita una carta que no existe.")
    if len(set(estado["cartas_sospechadas"])) != len(estado["cartas_sospechadas"]):
        _error("La memoria de sospechas repite una carta.")


def _validar_turnos(estado, por_id) -> None:
    orden = estado["orden_turnos"]
    if not isinstance(orden, list):
        _error("El orden de turnos no es una lista.")
    if estado["estado"] == ESTADO_ESPERANDO:
        if orden:
            _error("Una partida sin empezar no tiene orden de turnos.")
    else:
        if sorted(orden) != sorted(por_id):
            _error("El orden de turnos no incluye a todos los participantes.")
        actual = estado["turno_actual"]
        if not isinstance(actual, int) or isinstance(actual, bool):
            _error("El turno actual no es un número.")
        if not 0 <= actual < len(orden):
            _error("El turno actual está fuera de rango.")
    if not isinstance(estado["numero_turno"], int) or estado["numero_turno"] < 1:
        _error("El número de turno no es válido.")


def _validar_tablero(estado) -> None:
    posiciones = estado["posiciones"]
    if not isinstance(posiciones, dict):
        _error("Las posiciones no son un objeto.")
    for jugador_id, posicion in posiciones.items():
        if posicion not in TABLERO.posiciones_validas:
            _error("Hay una posición que no existe en el tablero.")
    objetos = estado["posiciones_objetos"]
    if not isinstance(objetos, dict):
        _error("La colocación de los objetos no es un objeto.")
    for objeto_id, ubicacion in objetos.items():
        if objeto_id not in IDS_CATEGORIA["objeto"]:
            _error("Hay una pieza que no es un objeto del juego.")
        if not TABLERO.es_ubicacion(ubicacion):
            _error("Hay una pieza colocada donde no se puede.")
    rutas = estado["rutas_pendientes"]
    if not isinstance(rutas, dict):
        _error("Las rutas pendientes no son un objeto.")
    for ruta in rutas.values():
        if not isinstance(ruta, list) or not ruta:
            _error("Una ruta pendiente está vacía o mal formada.")
        for casilla in ruta:
            if casilla not in TABLERO.posiciones_validas:
                _error("Una ruta pendiente pasa por una casilla que no existe.")
    tirada = estado["tirada_pendiente"]
    if tirada is not None and (
        not isinstance(tirada, int) or isinstance(tirada, bool) or not 1 <= tirada <= 6
    ):
        _error("La tirada pendiente no está entre 1 y 6.")


def _validar_fase(estado, por_id) -> None:
    if estado["modo"] not in MODOS:
        _error("El modo de partida no es válido.")
    if estado["estado"] not in (ESTADO_ESPERANDO, ESTADO_INICIADA, ESTADO_TERMINADA):
        _error("El estado de la partida no es válido.")
    if estado["estado_jugada"] not in ESTADOS_JUGADA:
        _error("La fase de la partida no es válida.")

    # Una partida terminada lo dice con su resultado, y solo una.
    if estado["estado"] == ESTADO_TERMINADA:
        if estado["resultado_final"] not in RESULTADOS_FINALES:
            _error("Una partida terminada necesita un resultado final.")
        if (
            estado["resultado_final"] == "sin_resolver"
            and estado["ganador_id"] is not None
        ):
            _error("Una partida sin resolver no tiene ganador.")
        if estado["ganador_id"] is not None and estado["ganador_id"] not in por_id:
            _error("El ganador no es un participante de la partida.")
    elif estado["resultado_final"] is not None or estado["ganador_id"] is not None:
        _error("Una partida en curso no tiene resultado final.")

    # Sospecha pendiente y presentación son excluyentes: una u otra.
    sospecha = estado["sospecha_pendiente"]
    presentacion = estado["presentacion_sospecha"]
    if sospecha is not None and presentacion is not None:
        _error("No puede haber sospecha y presentación a la vez.")
    if sospecha is not None:
        if not isinstance(sospecha, dict):
            _error("La sospecha pendiente no tiene la forma correcta.")
        for clave in ("investigador_id", "refutador_id"):
            if sospecha.get(clave) not in por_id:
                _error("La sospecha pendiente cita a alguien que no está.")
        if sospecha["investigador_id"] == sospecha["refutador_id"]:
            _error("Uno no se refuta a sí mismo.")
        if estado["estado_jugada"] != JUGADA_ESPERANDO_REFUTADOR:
            _error("Hay una sospecha pendiente en una fase que no la admite.")
        if not isinstance(sospecha.get("coincidencias"), list):
            _error("La sospecha pendiente no tiene sus coincidencias.")
        if any(
            carta not in CARTA_POR_ID for carta in sospecha["coincidencias"]
        ):
            _error("Una coincidencia de refutación no es una carta del juego.")

    if presentacion is not None:
        if not isinstance(presentacion, dict):
            _error("La presentación no tiene la forma correcta.")
        for clave in ("id", "inicio_restante", "participantes"):
            if clave not in presentacion:
                _error(f"La presentación no tiene '{clave}'.")
        if not _es_restante(presentacion["inicio_restante"]):
            _error("La presentación no tiene una edad válida.")
        participantes = presentacion["participantes"]
        if not isinstance(participantes, dict) or not participantes:
            _error("La presentación no tiene participantes.")
        for jugador_id, datos in participantes.items():
            if jugador_id not in por_id:
                _error("La presentación cita a alguien que no está.")
            if not isinstance(datos, dict) or "listo" not in datos:
                _error("Un participante de la presentación está mal formado.")
            if not isinstance(datos["listo"], bool):
                _error("Un participante de la presentación no está listo o sí.")
            if not _es_restante(datos.get("restante")):
                _error("Un participante de la presentación tiene un plazo raro.")
        if presentacion.get("investigador_id") not in por_id:
            _error("La presentación cita a un investigador que no está.")
        if estado["estado_jugada"] != JUGADA_PRESENTANDO_SOSPECHA:
            _error("Hay una presentación en una fase que no la admite.")

    # Y la fase se deduce de lo que hay pendiente.
    if estado["estado"] == ESTADO_INICIADA:
        if (
            estado["estado_jugada"] == JUGADA_ESPERANDO_REFUTADOR
            and sospecha is None
        ):
            _error("La fase pide una refutación pero no hay sospecha pendiente.")
        if (
            estado["estado_jugada"] == JUGADA_PRESENTANDO_SOSPECHA
            and presentacion is None
        ):
            _error("La fase pide una presentación pero no hay ninguna.")
        if sospecha is not None and not _es_restante(estado["refutacion_restante"]):
            _error("Hay una refutación pendiente sin tiempo restante válido.")
        if sospecha is None and estado["refutacion_restante"] is not None:
            _error("Hay tiempo de refutación sin ninguna refutación pendiente.")


def _validar_bloqueo_pausa_y_esperas(estado, por_id) -> None:
    velocidad = estado["velocidad_acciones"]
    if not isinstance(velocidad, int) or isinstance(velocidad, bool):
        _error("La velocidad de acciones no es un número entero.")
    if not VELOCIDAD_AUTOMATICA_MINIMA <= velocidad <= VELOCIDAD_AUTOMATICA_MAXIMA:
        _error("La velocidad de acciones está fuera de rango.")

    if not _es_restante(estado["refutacion_restante"]):
        _error("El tiempo restante de refutación no es válido.")

    bloqueo = estado["bloqueo"]
    if not isinstance(bloqueo, dict):
        _error("El aviso de inactividad no tiene la forma correcta.")
    if bloqueo.get("jugador_id") is not None and bloqueo["jugador_id"] not in por_id:
        _error("El aviso de inactividad cita a alguien que no está.")
    if not isinstance(bloqueo.get("aviso_emitido"), bool):
        _error("El aviso de inactividad no está bien formado.")
    if not _es_restante(bloqueo.get("restante")):
        _error("El aviso de inactividad tiene un plazo raro.")
    if bloqueo.get("restante") is None and bloqueo.get("jugador_id") is not None:
        _error("Hay un bloqueo sin tiempo restante.")

    pausa = estado["pausa"]
    if not isinstance(pausa, dict) or not isinstance(pausa.get("pausada"), bool):
        _error("El estado de pausa no tiene la forma correcta.")
    if not _es_numero(pausa.get("duracion")) or pausa["duracion"] < 0:
        _error("La duración de la pausa no es válida.")
    if pausa["pausada"] and estado["estado"] != ESTADO_INICIADA:
        _error("Una partida que no está en curso no puede estar en pausa.")

    espera = estado["espera_pnj"]
    if not isinstance(espera, dict):
        _error("La espera del PNJ no tiene la forma correcta.")
    for clave in ("restante", "turno_pnj_espera_restante"):
        if clave not in espera:
            _error(f"La espera del PNJ no tiene '{clave}'.")
        if not _es_restante(espera[clave]):
            _error("La espera del PNJ tiene un plazo raro.")


def _validar_historial(estado) -> None:
    historial = estado["historial"]
    if not isinstance(historial, list):
        _error("El historial no es una lista.")
    vistos: set[int] = set()
    for entrada in historial:
        if not isinstance(entrada, dict):
            _error("Una entrada del historial no es un objeto.")
        if "id" not in entrada or not isinstance(entrada["id"], int):
            _error("Una entrada del historial no tiene número.")
        if entrada["id"] in vistos:
            _error("El historial tiene dos entradas con el mismo número.")
        vistos.add(entrada["id"])
    ultima = estado["ultima_jugada"]
    if ultima is not None and not isinstance(ultima, dict):
        _error("La última jugada no tiene la forma correcta.")
    if estado["movimiento_resuelto"] is not None and not isinstance(
        estado["movimiento_resuelto"], dict
    ):
        _error("El movimiento resuelto no tiene la forma correcta.")


def validar(datos) -> dict:
    """Comprueba el archivo entero y devuelve su estado. Lanza ValueError.

    Solo mira forma, tipos y coherencia entre datos. Nunca interpreta
    contenido ni reconstruye objetos a partir de claves arbitrarias: no hay
    `pickle`, ni `eval`, ni `setattr` dinámico.
    """
    if not isinstance(datos, dict):
        _error("El archivo no es un objeto de partida.")
    for clave in CLAVES_OBLIGATORIAS:
        if clave not in datos:
            _error(f"El archivo no tiene la clave '{clave}'.")
    if datos["formato"] != FORMATO_PARTIDA:
        _error("El archivo no es una partida de El misterio del medallón.")
    if not isinstance(datos["version"], int) or isinstance(datos["version"], bool):
        _error("La versión del archivo no es un número.")
    if datos["version"] != VERSION_PARTIDA:
        _error(
            f"Versión de partida no soportada: {datos['version']}. "
            f"Esta versión del juego entiende la {VERSION_PARTIDA}."
        )
    if not isinstance(datos["resumen"], dict):
        _error("El resumen del archivo no es un objeto.")

    estado = datos["estado"]
    if not isinstance(estado, dict):
        _error("El estado de la partida no es un objeto.")
    for clave in CLAVES_OBLIGATORIAS_ESTADO:
        if clave not in estado:
            _error(f"El estado no tiene la clave '{clave}'.")
    faltan = set(estado) - (set(CLAVES_OBLIGATORIAS_ESTADO) | set(CAMPOS_DE_SALA))
    if faltan:
        _error("El estado tiene claves que no se guardan.")

    _sin_claves_prohibidas(estado)

    integridad = datos["integridad"]
    if not isinstance(integridad, dict) or "valor" not in integridad:
        _error("El archivo no trae huella de integridad.")
    if integridad["valor"] != huella(estado):
        _error("El archivo está dañado: la huella no coincide.")

    por_id = _validar_jugadores(estado)
    _validar_credencial(estado)
    _validar_misterio_y_reparto(estado, por_id)
    _validar_investigacion(estado, por_id)
    _validar_turnos(estado, por_id)
    _validar_tablero(estado)
    _validar_fase(estado, por_id)
    _validar_bloqueo_pausa_y_esperas(estado, por_id)
    _validar_historial(estado)
    return estado


# --- Reconstrucción ------------------------------------------------------
# Copia campo a campo DESDE LA LISTA BLANCA. Nunca `setattr` con una clave
# leída del archivo, y nunca `**datos`: un archivo manipulado no puede
# introducir atributos ni código en la sala.

VUELO_A_RESTANTE = {
    "refutacion_deadline": "refutacion_restante",
    "bloqueo_deadline": ("bloqueo", "restante"),
}


def _deadline(restante, ahora: float) -> float | None:
    return None if restante is None else ahora + restante


def restaurar_sala(estado: dict, ahora: float | None = None) -> Sala:
    """Construye una sala nueva a partir de un estado YA validADO.

    No reparte cartas ni genera misterio: copia lo que había. Los tiempos se
    reconstruyen como `ahora + restante`, sin descontar nada.
    """
    instante = time.monotonic() if ahora is None else ahora
    sala = Sala(estado["codigo"], modo=estado["modo"])

    for campo in CAMPOS_DE_SALA:
        setattr(sala, campo, _copia(estado[campo]))
    sala.pausada = False
    sala.pausa_marca = None
    sala.espera_pnj_en_curso = None

    # --- identidades y autoridad ---
    sala.jugadores = [
        {campo: _copia(jugador[campo]) for campo in CAMPOS_DE_JUGADOR}
        for jugador in estado["jugadores"]
    ]
    sala.credencial_admin = estado["credencial_admin"]
    sala.credencial_admin_resumen = resumen_credencial_admin(sala.credencial_admin)

    # --- reparto y conocimiento ---
    sala.misterio = _copia(estado["misterio"])
    sala.manos = {
        jugador_id: [_copia(carta) for carta in cartas]
        for jugador_id, cartas in estado["manos"].items()
    }
    sala.descartes = {
        jugador_id: set(cartas) for jugador_id, cartas in estado["descartes"].items()
    }
    sala.vistas = {
        jugador_id: set(cartas) for jugador_id, cartas in estado["vistas"].items()
    }
    sala.soluciones_deducidas = _copia(estado["soluciones_deducidas"])
    sala.cartas_sospechadas = set(estado["cartas_sospechadas"])

    # --- turnos y tablero ---
    sala.orden_turnos = list(estado["orden_turnos"])
    sala.posiciones_objetos = dict(estado["posiciones_objetos"])
    sala.rutas_pendientes = {
        jugador_id: tuple(casillas)
        for jugador_id, casillas in estado["rutas_pendientes"].items()
    }
    sala.movimiento_resuelto = _copia(estado["movimiento_resuelto"])

    # --- jugada en curso ---
    sala.ultima_jugada = _copia(estado["ultima_jugada"])
    sala.sospecha_pendiente = _copia(estado["sospecha_pendiente"])
    sala.historial = _copia(estado["historial"])
    sala.secuencia_historial = estado["secuencia_historial"]
    sala.secuencia_presentacion = estado["secuencia_presentacion"]
    sala.secuencia_movimiento = estado["secuencia_movimiento"]
    sala.bloqueo_aviso_id = estado["bloqueo_aviso_id"]

    # --- posiciones: se reasignan por la API del tablero, no a lo bruto ---
    for jugador_id, posicion in estado["posiciones"].items():
        sala.posiciones.asignar(jugador_id, posicion)

    # --- tiempos pendientes ---
    sala.refutacion_deadline = _deadline(estado["refutacion_restante"], instante)
    bloqueo = estado["bloqueo"]
    sala.bloqueo_jugador_id = bloqueo["jugador_id"]
    sala.bloqueo_accion = bloqueo["accion"]
    sala.bloqueo_deadline = _deadline(bloqueo["restante"], instante)
    sala.bloqueo_aviso_emitido = bool(bloqueo["aviso_emitido"])

    presentacion = estado["presentacion_sospecha"]
    if presentacion is not None:
        inicio = instante - presentacion["inicio_restante"]
        sala.presentacion_sospecha = {
            clave: _copia(presentacion[clave])
            for clave in ("id", "tipo", "investigador_id", "investigador_alias", "sospecha")
            if clave in presentacion
        }
        sala.presentacion_sospecha["tipo"] = presentacion.get("tipo", "sospecha")
        sala.presentacion_sospecha["inicio"] = inicio
        sala.presentacion_sospecha["participantes"] = {
            jugador_id: {
                "listo": bool(datos["listo"]),
                "deadline": (
                    inicio if datos["restante"] is None
                    else instante + datos["restante"]
                ),
            }
            for jugador_id, datos in presentacion["participantes"].items()
        }
        for opcional in ("resultado", "refutador_alias", "movimiento_pnj"):
            if presentacion.get(opcional) is not None:
                sala.presentacion_sospecha[opcional] = _copia(presentacion[opcional])
    else:
        sala.presentacion_sospecha = None

    # --- lo que le quedaba a un PNJ esperando ---
    espera = estado["espera_pnj"]
    sala.turno_pnj_espera_restante = (
        espera["turno_pnj_espera_restante"]
        if espera["turno_pnj_espera_restante"] is not None
        else espera["restante"]
    )

    # --- pausa: se restaura pausada, sin arrastrar la duración antigua ---
    if estado["pausa"]["pausada"]:
        sala.pausada = True
        sala.pausa_marca = instante

    return sala
