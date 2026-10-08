"""Lógica del lobby, del misterio y de la hoja de investigación (Sprints 1-3 + 3B).

El servidor es la fuente de verdad. Todo el estado vive aquí.
Sin base de datos en este prototipo.

Seguridad:
- El misterio secreto solo existe en el servidor.
- Cada jugador solo recibe sus propias cartas (estado privado).
- La hoja de investigación es estrictamente privada: cada jugador
  solo recibe la suya; nunca viaja en estado_publico() ni en
  difusiones a otros jugadores.
- El estado público solo lleva recuentos, nunca contenido de cartas.
"""
from __future__ import annotations

import hashlib
import random
import secrets
import time
import uuid

from app.datos.jarandilla import (
    CARTA_POR_ID,
    CARTAS,
    LUGARES,
    OBJETOS,
    SOSPECHOSOS,
)
from app.motor.tablero import TABLERO, PosicionesParticipantes, tirar_dado

# Vista de solo lectura sobre los sospechosos canónicos (sin duplicar datos).
PERSONAJE_POR_ID: dict[str, dict] = {p["id"]: p for p in SOSPECHOSOS}

ESTADO_ESPERANDO = "esperando"
ESTADO_INICIADA = "iniciada"
ESTADO_TERMINADA = "terminada"

JUGADA_ESPERANDO_SOSPECHA = "esperando_sospecha"
JUGADA_ESPERANDO_REFUTADOR = "esperando_eleccion_refutador"
JUGADA_ESPERANDO_MOVIMIENTO = "esperando_movimiento"
JUGADA_ESPERANDO_DESTINO = "esperando_destino"
JUGADA_PRESENTANDO_SOSPECHA = "presentando_sospecha"

MODO_RAPIDO = "rapido"
MODO_TABLERO = "tablero"
MODOS = frozenset({MODO_RAPIDO, MODO_TABLERO})

POSICIONES_INICIALES = {
    "vera": "parador",
    "bruno": "iglesia-san-agustin",
    "lucia": "ermita-sopetran",
    "alvaro": "nuestra-senora-torre",
    "mateo": "museo-escobazos",
    "eulalia": "puente-parral",
}

MIN_JUGADORES = 1
MAX_JUGADORES = 6

TIPO_HUMANO = "humano"
TIPO_PNJ = "pnj"

# Un solo algoritmo, parametrizado por el personaje. Los pesos son preferencias,
# no conocimiento adicional: el PNJ nunca consulta el misterio.
PERFILES_PNJ = {
    "vera": {"desconocida": 50, "sospechada": 30, "conocida": 20},
    "bruno": {"desconocida": 75, "sospechada": 15, "conocida": 10},
    "lucia": {"desconocida": 65, "sospechada": 25, "conocida": 10},
    "alvaro": {"desconocida": 60, "sospechada": 20, "conocida": 20},
    "mateo": {"desconocida": 55, "sospechada": 30, "conocida": 15},
    "eulalia": {"desconocida": 50, "sospechada": 40, "conocida": 10},
}

# Timeout server-side único para cualquier refutador humano.
TIMEOUT_REFUTACION_HUMANO_SEGUNDOS = 10.0
PAUSA_PRESENTACION_PNJ_SEGUNDOS = 3.0
# Sospecha: solo hay que leer QUIÉN y QUÉ, así que 10 s es suficiente.
PAUSA_PRESENTACION_HUMANO_SEGUNDOS = 10.0
# Resultado público: hay que leer además QUIÉN refutó y el estado de las tres
# cartas sospechadas, así que necesita más tiempo de lectura.
PAUSA_PRESENTACION_RESULTADO_SEGUNDOS = 14.0

# Antibloqueo por inactividad (8B.32). Plazo CANÓNICO del servidor para un
# humano que bloquea la partida con una acción obligatoria. NO ejecuta la
# acción pendiente: solo ofrece al anfitrión convertir ese mismo asiento en
# PNJ o seguir esperando otro periodo igual.
INACTIVIDAD_BLOQUEO_SEGUNDOS = 60.0

# Únicas acciones que bloquean la partida esperando a un humano concreto.
# Derivadas de la máquina de estados: los tres estados de los que no hay
# salida sin una acción del jugador en turno. La refutación privada
# (esperando_eleccion_refutador) y la presentación sincronizada ya tienen su
# propio plazo canónico y quedan EXCLUIDAS a propósito.
ACCION_TIRAR_DADO = "tirar_dado"
ACCION_ELEGIR_DESTINO = "elegir_destino"
ACCION_FORMULAR_SOSPECHA = "formular_sospecha"
ACCION_POR_ESTADO_BLOQUEANTE = {
    JUGADA_ESPERANDO_MOVIMIENTO: ACCION_TIRAR_DADO,
    JUGADA_ESPERANDO_DESTINO: ACCION_ELEGIR_DESTINO,
    JUGADA_ESPERANDO_SOSPECHA: ACCION_FORMULAR_SOSPECHA,
}
ESTADOS_BLOQUEANTES = frozenset(ACCION_POR_ESTADO_BLOQUEANTE)

# --- Administración (Microfase 1) ---------------------------------------
# La autoridad administrativa NO depende de que un botón esté visible: se
# comprueba en el servidor, con un secreto que solo posee el anfitrión.
#
# Hay UN secreto por SALA, nunca uno por jugador. Los PNJ no lo tienen. Se
# compara en tiempo constante y jamás sale en estado_publico(),
# estado_privado() ni en ninguna difusión: solo se entrega al asiento que
# es anfitrión, por un mensaje privado al abrir su conexión.
BYTES_CREDENCIAL_ADMIN = 32  # 256 bits de entropía por sala
# Un único mensaje para toda negativa administrativa: no dice si falla el
# asiento o el secreto, para no regalar un oráculo.
MENSAJE_SIN_AUTORIDAD_ADMIN = "Solo el anfitrión puede administrar la partida."  # noqa: E501

# Velocidad de las acciones automáticas (Microfase 2). Es un AJUSTE de la sala,
# compartido por todos los participantes y modificable solo por el anfitrión.
#
# Cada espera automática conserva su duración propia: el ajuste NO reescribe
# las constantes, las desplaza todas por el MISMO delta. Con el valor inicial
# el delta es cero y el juego se comporta exactamente igual que antes.
#
#   espera(base) = base + (velocidad - VELOCIDAD_AUTOMATICA_INICIAL)
#
# Con la inicial (3): ritmo PNJ 3 s, lectura de jugada 5 s, lectura de
# sospecha PNJ 5 s, ventana de los PNJ 3 s. Los dos segundos de diferencia
# entre el ritmo y la lectura se respetan en todos los valores.
#
# NO se tocan NUNCA los plazos de decisión humana: ni la refutación, ni las
# ventanas obligatorias de lectura (sospecha 10 s, resultado 14 s), ni el
# antibloqueo de 60 s.
VELOCIDAD_AUTOMATICA_INICIAL = 3
VELOCIDAD_AUTOMATICA_MINIMA = 1
VELOCIDAD_AUTOMATICA_MAXIMA = 10

# Pausa de la partida (Microfase 3). El estado vive en la sala: sobrevive a
# recargas y reconexiones, y solo lo mueve el anfitrión, con su credencial.
#
# Congelar es DESPLAZAR los plazos: los pendientes suman la duración de la
# pausa, así que al reanudar cada uno conserva el tiempo que le quedaba.
MENSAJE_PARTIDA_EN_PAUSA = "La partida está en pausa. Espera a que el anfitrión la reanude."
MENSAJE_PARTIDA_NO_PAUSA = "La partida no está en pausa."
# Durante la pausa solo se acepta esto: ni turnos, ni sospechas, ni refutar,
# ni acusar, ni anotar. La nota privada es una acción más de partida.
ACCIONES_PERMITIDAS_EN_PAUSA = frozenset(
    {"reanudar_partida", "pedir_credencial_admin"}
)


# Hoja de investigación privada (Microfase 3B). Terminología de OBJETOS.
INV_SIN_INFORMACION = "sin_informacion"
INV_DESCARTADA = "descartada"
INV_LA_TENGO = "la_tengo"  # derivado de la mano; nunca se almacena ni se marca
INV_VISTA = "vista"  # se añade automáticamente al recibir una refutación
ESTADOS_MANUALES = frozenset({INV_SIN_INFORMACION, INV_DESCARTADA})

_ALFABETO_CODIGO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin I, O, 0, 1


def generar_codigo() -> str:
    """Genera un código corto tipo JARA-XXXX."""
    sufijo = "".join(secrets.choice(_ALFABETO_CODIGO) for _ in range(4))
    return f"JARA-{sufijo}"


def generar_credencial_admin() -> str:
    """Secreto administrativo de una sala (alfabeto URL-safe)."""
    return secrets.token_urlsafe(BYTES_CREDENCIAL_ADMIN)


def resumen_credencial_admin(credencial: str) -> str:
    """Huella del secreto: es lo que se compara en tiempo constante.

    Nunca se compara ni se registra el secreto en claro.
    """
    return hashlib.sha256(credencial.encode("utf-8")).hexdigest()


def normalizar_alias(alias: str) -> str:
    return (alias or "").strip()


def validar_alias(alias: str) -> str | None:
    """Devuelve mensaje de error o None si el alias es válido."""
    limpio = normalizar_alias(alias)
    if not limpio:
        return "El alias no puede estar vacío."
    if len(limpio) > 20:
        return "El alias no puede superar 20 caracteres."
    return None


def crear_misterio() -> dict:
    """Elige en secreto 1 sospechoso, 1 lugar y 1 objeto."""
    return {
        "sospechoso": dict(random.choice(SOSPECHOSOS)),
        "lugar": dict(random.choice(LUGARES)),
        "objeto": dict(random.choice(OBJETOS)),
    }


def repartir(cartas: list[dict], ids_jugadores: list[str]) -> dict[str, list[dict]]:
    """Baraja y reparte de forma equilibrada (round-robin)."""
    mazo = [dict(carta) for carta in cartas]
    random.shuffle(mazo)
    manos: dict[str, list[dict]] = {jid: [] for jid in ids_jugadores}
    for i, carta in enumerate(mazo):
        manos[ids_jugadores[i % len(ids_jugadores)]].append(carta)
    return manos


class Sala:
    def __init__(self, codigo: str, modo: str = MODO_RAPIDO):
        if modo not in MODOS:
            raise ValueError("Modo de partida no válido.")
        self.codigo = codigo
        self.modo = modo
        self.estado = ESTADO_ESPERANDO
        self.jugadores: list[dict] = []  # humanos y PNJ comparten estructura
        # Autoridad administrativa de la sala. El secreto en claro se conserva
        # para poder reentregárselo al anfitrión cuando reconecta; la
        # comparación de las futuras acciones se hace contra el resumen, en
        # tiempo constante. No viaja en ningún estado ni en ninguna difusión.
        self.credencial_admin = generar_credencial_admin()
        self.credencial_admin_resumen = resumen_credencial_admin(
            self.credencial_admin
        )
        # Espera automática configurada para TODA la sala, en segundos. Vive en
        # la sala (no en el navegador): cada participante ve el mismo número y
        # el anfitrión es el único que puede moverlo.
        self.velocidad_acciones = VELOCIDAD_AUTOMATICA_INICIAL
        # Microfase 3 · Pausa. `pausa_marca` es el instante monotónico en el
        # que empezó; `turno_pnj_espera_restante` conserva lo que le quedaba
        # a un PNJ que ya estaba esperando cuando se pausó.
        self.pausada = False
        self.pausa_marca: float | None = None
        self.turno_pnj_espera_restante: float | None = None
        # Datos de la espera del PNJ en curso, los escribe la orquestación.
        # Vive en la sala (como `pnj_pensando_id`) para que una pausa pueda
        # calcular lo que le quedaba antes de cancelar la tarea.
        self.espera_pnj_en_curso: dict | None = None
        self.misterio: dict | None = None  # SECRETO: nunca sale del servidor
        self.manos: dict[str, list[dict]] = {}  # jugador_id -> sus cartas
        self.orden_turnos: list[str] = []  # jugador_ids sorteados una sola vez
        self.turno_actual: int = 0
        # Número humano del turno real de la partida. A diferencia de
        # `turno_actual` (índice circular), es monotónico y también cuenta los
        # turnos de PNJ o los turnos que terminan sin sospecha.
        self.numero_turno: int = 1
        # Hoja privada: solo descartes manuales + vistas automáticas
        # por refutaciones. LA TENGO se deriva de la mano y
        # SIN INFORMACIÓN es la ausencia de marca. Nada de esto es público.
        self.descartes: dict[str, set[str]] = {}  # jugador_id -> carta_ids
        self.vistas: dict[str, set[str]] = {}  # jugador_id -> carta_ids (Sprint 4)
        self.estado_jugada = JUGADA_ESPERANDO_SOSPECHA
        self.sospecha_pendiente: dict | None = None
        self.presentacion_sospecha: dict | None = None
        self.secuencia_presentacion = 0
        self.ultima_jugada: dict | None = None
        # Registro público, cronológico y deliberadamente JSON-serializable.
        # Solo contiene hechos ya públicos; nunca cartas mostradas ni manos.
        self.secuencia_historial = 0
        self.historial: list[dict] = []
        # Deadline monotónico de la refutación humana pendiente. Vive en
        # la sala y sobrevive a recargas/reconexiones: solo cambia con una
        # nueva sospecha o al resolver la actual.
        self.refutacion_deadline: float | None = None
        # Antibloqueo por inactividad (8B.32). Identidad y plazo del humano
        # que bloquea la partida, más el aviso ya emitido. Vive en la sala:
        # sobrevive a reload, redifusiones y reconexiones, y solo cambia al
        # entrar en una acción bloqueante nueva o al pedir el anfitrión que
        # siga esperando.
        self._reiniciar_bloqueo()
        # El identificador de aviso es monótono durante toda la partida.
        self.bloqueo_aviso_id = 0
        self.cartas_sospechadas: set[str] = set()  # memoria exclusivamente publica
        self.pnj_pensando_id: str | None = None
        self.resultado_final: str | None = None
        self.ganador_id: str | None = None
        # Conocimiento privado deducido sin consultar el misterio.
        self.soluciones_deducidas: dict[str, dict] = {}
        self.posiciones = PosicionesParticipantes(TABLERO)
        # Piezas físicas públicas, independientes de cartas, manos y misterio.
        # Solo existen en modo tablero: objeto_id -> ubicacion_id.
        self.posiciones_objetos: dict[str, str] = {}
        self.tirada_pendiente: int | None = None
        self.rutas_pendientes: dict[str, tuple[str, ...]] = {}
        # Descripción pública del último desplazamiento resuelto. El
        # contador permite al cliente distinguir un movimiento nuevo de una
        # redifusión posterior del mismo estado.
        self.secuencia_movimiento = 0
        self.movimiento_resuelto: dict | None = None

    def jugador_por_id(self, jugador_id: str) -> dict | None:
        for j in self.jugadores:
            if j["id"] == jugador_id:
                return j
        return None

    # --- Autoridad administrativa (Microfase 1) ---------------------------
    # Base de las acciones administrativas de las próximas fases (pausar,
    # velocidad, guardar). La comprobación vive aquí, no en la interfaz: un
    # jugador que manipule la petición desde el navegador recibe el mismo
    # rechazo que si el botón no existiera.

    def anfitrion(self) -> dict | None:
        """El asiento que hoy administra la sala, o None si no queda ninguno."""
        for j in self.jugadores:
            if j["es_anfitrion"]:
                return j
        return None

    def es_anfitrion(self, jugador_id: str) -> bool:
        jugador = self.jugador_por_id(jugador_id)
        return bool(jugador is not None and jugador["es_anfitrion"])

    def rotar_credencial_admin(self, jugador_id: str) -> str:
        """Emite un secreto nuevo para el anfitrión indicado.

        Se usa cuando el rol cambia de manos (herencia al irse el
        anfitrión): el secreto anterior deja de valer para todo el mundo.
        """
        self.credencial_admin = generar_credencial_admin()
        self.credencial_admin_resumen = resumen_credencial_admin(
            self.credencial_admin
        )
        return self.credencial_admin

    def credencial_admin_de(self, jugador_id: str) -> str | None:
        """Entrega el secreto SOLO al asiento anfitrión. Nadie más lo recibe."""
        if not self.es_anfitrion(jugador_id):
            return None
        return self.credencial_admin

    def credencial_admin_valida(self, credencial) -> bool:
        """Compara el secreto recibido con el de la sala, en tiempo constante."""
        if not isinstance(credencial, str) or not credencial:
            return False
        return secrets.compare_digest(
            resumen_credencial_admin(credencial), self.credencial_admin_resumen
        )

    def exigir_credencial_admin(self, jugador_id: str, credencial) -> None:
        """Exige a la vez el ASIENTO y el SECRETO del anfitrión.

        WebSocket: `datos.get("token_admin")` del mensaje de la acción.
        HTTP: la cabecera `X-Token-Admin` de la petición. En ninguno de los
        dos casos la credencial viaja en la URL.

        El rechazo es el mismo para un jugador sin rol y para un secreto
        equivocado, y no distingue cuál de los dos falla.
        """
        if not self.es_anfitrion(jugador_id):
            raise ValueError(MENSAJE_SIN_AUTORIDAD_ADMIN)
        if not self.credencial_admin_valida(credencial):
            raise ValueError(MENSAJE_SIN_AUTORIDAD_ADMIN)

    # --- Velocidad de las acciones automáticas (Microfase 2) --------------
    # El ajuste es de la SALA, no de cada navegador. Solo lo mueve el
    # anfitrión, y solo con su credencial: ocultar los botones no es la
    # protección, la validación del servidor sí.

    def espera_automatica(self, base: float) -> float:
        """Espera automática de la sala a partir de la base canónica.

        `base` es la constante original (3 s del ritmo PNJ, 5 s de lectura,
        3 s de la ventana de los PNJ). Todas se desplazan por el MISMO delta,
        de modo que sus diferencias entre sí se conservan siempre y con la
        velocidad inicial el juego se comporta como antes de esta fase.
        """
        return base + (self.velocidad_acciones - VELOCIDAD_AUTOMATICA_INICIAL)

    def acelerar_acciones(self, jugador_id: str, credencial) -> int:
        """MÁS RÁPIDO: un segundo menos de espera automática."""
        return self._mover_velocidad(jugador_id, credencial, -1)

    def ralentizar_acciones(self, jugador_id: str, credencial) -> int:
        """MÁS LENTO: un segundo más de espera automática."""
        return self._mover_velocidad(jugador_id, credencial, +1)

    def _mover_velocidad(self, jugador_id: str, credencial, paso: int) -> int:
        self.exigir_credencial_admin(jugador_id, credencial)
        self.velocidad_acciones = min(
            VELOCIDAD_AUTOMATICA_MAXIMA,
            max(VELOCIDAD_AUTOMATICA_MINIMA, self.velocidad_acciones + paso),
        )
        return self.velocidad_acciones

    # --- Pausa y reanudación (Microfase 3) -------------------------------
    # Congelar no es cancelar: es correr el reloj. Todos los plazos
    # pendientes suman la duración de la pausa, así que al reanudar cada
    # operación conserva exactamente el tiempo que le quedaba.

    def desplazar_plazos(self, delta: float) -> None:
        """Suma `delta` (segundos) a TODOS los plazos vivos de la sala.

        Único sitio donde se tocan los relojes: presentación (inicio y el
        deadline de cada participante), refutación pendiente y antibloqueo.
        Los que no están en marcha se quedan como están.
        """
        if delta <= 0:
            return
        if self.refutacion_deadline is not None:
            self.refutacion_deadline += delta
        if self.bloqueo_deadline is not None:
            self.bloqueo_deadline += delta
        presentacion = self.presentacion_sospecha
        if presentacion is not None:
            presentacion["inicio"] += delta
            for datos in presentacion["participantes"].values():
                if datos.get("deadline") is not None:
                    datos["deadline"] += delta

    def pausar_partida(self, jugador_id: str, credencial, ahora=None) -> bool:
        """Detiene la partida. Idempotente: pausar dos veces no hace nada.

        Devuelve True si esta llamada ha sido la que la ha pausado.
        """
        self.exigir_credencial_admin(jugador_id, credencial)
        if self.estado != ESTADO_INICIADA:
            raise ValueError("Solo se puede pausar una partida en curso.")
        if self.pausada:
            return False
        self.pausada = True
        self.pausa_marca = time.monotonic() if ahora is None else ahora
        return True

    def reanudar_partida(self, jugador_id: str, credencial, ahora=None) -> bool:
        """Continúa desde el estado anterior, con los tiempos que quedaban."""
        self.exigir_credencial_admin(jugador_id, credencial)
        if self.estado != ESTADO_INICIADA:
            raise ValueError("Solo se puede reanudar una partida en curso.")
        if not self.pausada:
            raise ValueError(MENSAJE_PARTIDA_NO_PAUSA)
        instante = time.monotonic() if ahora is None else ahora
        marca = self.pausa_marca if self.pausa_marca is not None else instante
        self.desplazar_plazos(max(0.0, instante - marca))
        self.pausa_marca = None
        self.pausada = False
        return True

    def comprobar_accion_en_pausa(self, accion) -> None:
        """El servidor rechaza toda acción de partida mientras está en pausa.

        Se llama al entrar en el WebSocket, antes de tocar nada: no depende
        de que el botón esté visible ni de lo que haya en el navegador.
        """
        if self.pausada and accion not in ACCIONES_PERMITIDAS_EN_PAUSA:
            raise ValueError(MENSAJE_PARTIDA_EN_PAUSA)

    def cambiar_modo(self, modo: str) -> None:
        if self.estado != ESTADO_ESPERANDO:
            raise ValueError("El modo no puede cambiarse después de iniciar.")
        if modo not in MODOS:
            raise ValueError("Modo de partida no válido.")
        self.modo = modo

    def alias_existe(self, alias: str) -> bool:
        limpio = normalizar_alias(alias).lower()
        return any(j["alias"].lower() == limpio for j in self.jugadores)

    def agregar_jugador(
        self,
        alias: str,
        es_anfitrion: bool = False,
        tipo: str = TIPO_HUMANO,
        personaje_id: str | None = None,
    ) -> dict:
        jugador = {
            "id": f"pnj-{personaje_id}" if tipo == TIPO_PNJ else uuid.uuid4().hex[:12],
            "alias": normalizar_alias(alias),
            "es_anfitrion": es_anfitrion,
            "personaje_id": personaje_id,
            "tipo": tipo,
            "activo_investigacion": True,
            # Preferencia privada del humano eliminado. No cambia su tipo,
            # identidad ni participacion en la busqueda de refutadores.
            "refutacion_automatica": False,
            "decision_refutacion_pendiente": False,
            "resolucion_fallida": None,
        }
        self.jugadores.append(jugador)
        self.descartes.setdefault(jugador["id"], set())
        self.vistas.setdefault(jugador["id"], set())
        return jugador

    def quitar_jugador(self, jugador_id: str) -> dict | None:
        for i, j in enumerate(self.jugadores):
            if j["id"] == jugador_id:
                eliminado = self.jugadores.pop(i)
                self.manos.pop(jugador_id, None)
                self.descartes.pop(jugador_id, None)
                self.vistas.pop(jugador_id, None)
                self.soluciones_deducidas.pop(jugador_id, None)
                # Si se va el anfitrión, el más antiguo hereda el rol.
                if eliminado["es_anfitrion"] and self.jugadores:
                    self.jugadores[0]["es_anfitrion"] = True
                    # El rol cambia de manos, así que también cambia el
                    # secreto: el anfitrión saliente deja de poder
                    # administrar la sala.
                    self.rotar_credencial_admin(self.jugadores[0]["id"])
                return eliminado
        return None

    def num_cartas(self, jugador_id: str) -> int:
        return len(self.manos.get(jugador_id, []))

    def puede_volver_al_lobby(self, jugador_id: str) -> str | None:
        """Misma autoridad que COMENZAR PARTIDA: la del anfitrión.

        Idempotente por estado canónico: si la sala ya está en espera, la
        revancha ya se pidió y no hay nada que hacer.
        """
        jugador = self.jugador_por_id(jugador_id)
        if jugador is None:
            return "Jugador desconocido en esta sala."
        if self.estado == ESTADO_ESPERANDO:
            return None
        if self.estado != ESTADO_TERMINADA:
            raise ValueError("Solo se puede pedir la revancha con la partida terminada.")
        if not jugador["es_anfitrion"]:
            return "Solo el anfitrión puede empezar una revancha."
        return None

    def volver_al_lobby(self, jugador_id: str) -> bool:
        """Vuelve a la MISMA sala en preparación para una revancha limpia.

        Conserva código, modo, humanos conectados, alias y anfitrión. Reinicia
        por completo todo lo que pertenece a la partida: misterio, reparto,
        investigación, vistas y descartes, eliminaciones, refutación
        automática, personajes elegidos, PNJ, orden y turno, fases,
        movimientos, posiciones de fichas y de objetos, presentaciones,
        refutaciones, plazos, resultado y ganador.

        No reinicia los contadores monotonos de secuencia (presentación,
        movimiento y aviso de inactividad): no son conocimiento de juego, solo
        identidad interna para que el cliente detecte que un mensaje es nuevo,
        y reiniciarlos podría hacer que un cliente reabriera un modal viejo.
        """
        error = self.puede_volver_al_lobby(jugador_id)
        if error:
            raise ValueError(error)
        if self.estado == ESTADO_ESPERANDO:
            return False   # ya se pidió: idempotente, sin doble transición
        # Los PNJ eran de la partida anterior: desaparecen de la sala y de
        # todas sus estructuras. `completar_con_pnj` los volvera a crear al
        # comenzar la siguiente, con la logica canonica.
        for jugador in [j for j in self.jugadores if j["tipo"] == TIPO_PNJ]:
            self._olvidar_jugador(jugador["id"])
        self.jugadores = [j for j in self.jugadores if j["tipo"] != TIPO_PNJ]
        # Cada humano vuelve a empezar sin nada de la partida anterior.
        for jugador in self.jugadores:
            self._olvidar_jugador(jugador["id"])
            jugador["personaje_id"] = None
            jugador["activo_investigacion"] = True
            jugador["refutacion_automatica"] = False
            jugador["decision_refutacion_pendiente"] = False
            jugador["resolucion_fallida"] = None
        # Estado de sala equivalente al de una recien creada.
        self.estado = ESTADO_ESPERANDO
        self.misterio = None
        self.manos = {}
        self.orden_turnos = []
        self.turno_actual = 0
        self.numero_turno = 1
        self.descartes = {}
        self.vistas = {}
        self.estado_jugada = JUGADA_ESPERANDO_SOSPECHA
        self.sospecha_pendiente = None
        self.presentacion_sospecha = None
        self.ultima_jugada = None
        self.historial = []
        self.refutacion_deadline = None
        self.cartas_sospechadas.clear()
        self.pnj_pensando_id = None
        self.resultado_final = None
        self.ganador_id = None
        self.soluciones_deducidas.clear()
        self.posiciones = PosicionesParticipantes(TABLERO)
        self.posiciones_objetos = {}
        self.tirada_pendiente = None
        self.rutas_pendientes = {}
        self.movimiento_resuelto = None
        self._reiniciar_bloqueo()
        return True

    def _olvidar_jugador(self, jugador_id: str) -> None:
        """Borra todo lo que la sala guardaba de un participante."""
        self.manos.pop(jugador_id, None)
        self.descartes.pop(jugador_id, None)
        self.vistas.pop(jugador_id, None)
        self.soluciones_deducidas.pop(jugador_id, None)

    def personaje_ocupado_por(self, personaje_id: str) -> dict | None:
        """Jugador que ya tiene ese personaje, o None si está libre."""
        for j in self.jugadores:
            if j["personaje_id"] == personaje_id:
                return j
        return None

    def personajes_completos(self) -> bool:
        return bool(self.jugadores) and all(
            j["personaje_id"] for j in self.jugadores
        )

    def elegir_personaje(self, jugador_id: str, personaje_id: str) -> dict:
        """Asignación libre con exclusividad validada en backend."""
        jugador = self.jugador_por_id(jugador_id)
        if jugador is None:
            raise ValueError("Jugador desconocido en esta sala.")
        if self.estado != ESTADO_ESPERANDO:
            raise ValueError("La partida ya comenzó. Los personajes están bloqueados.")
        pid = (personaje_id or "").strip().lower()
        if pid not in PERSONAJE_POR_ID:
            raise ValueError("Ese personaje no existe.")
        ocupante = self.personaje_ocupado_por(pid)
        if ocupante is not None and ocupante["id"] != jugador_id:
            raise ValueError(
                f"Ese personaje ya lo ha elegido {ocupante['alias']}."
            )
        jugador["personaje_id"] = pid  # el anterior, si había, queda libre
        return jugador

    def jugador_en_turno(self) -> dict | None:
        if self.estado != ESTADO_INICIADA or not self.orden_turnos:
            return None
        return self.jugador_por_id(self.orden_turnos[self.turno_actual])

    def puede_iniciar(self, jugador_id: str) -> str | None:
        jugador = self.jugador_por_id(jugador_id)
        if jugador is None:
            return "Jugador desconocido en esta sala."
        if not jugador["es_anfitrion"]:
            return "Solo el anfitrión puede comenzar la partida."
        if self.estado == ESTADO_INICIADA:
            return "La partida ya está iniciada."
        if len(self.jugadores) < MIN_JUGADORES:
            return (
                f"Se necesitan al menos {MIN_JUGADORES} jugadores para comenzar "
                f"(máximo {MAX_JUGADORES})."
            )
        if not self.personajes_completos():
            return "Todos los jugadores deben elegir un personaje antes de comenzar."
        return None

    def completar_con_pnj(self) -> None:
        """Crea exactamente un PNJ por personaje que no eligio un humano."""
        ocupados = {j["personaje_id"] for j in self.jugadores}
        for personaje in SOSPECHOSOS:
            if personaje["id"] not in ocupados:
                self.agregar_jugador(
                    personaje["nombre"],
                    tipo=TIPO_PNJ,
                    personaje_id=personaje["id"],
                )

    def iniciar(self, jugador_id: str) -> None:
        """Valida, bloquea personajes, crea el misterio, reparte y sortea."""
        error = self.puede_iniciar(jugador_id)
        if error:
            raise ValueError(error)
        self.completar_con_pnj()
        self.misterio = crear_misterio()
        apartadas = {
            self.misterio["sospechoso"]["id"],
            self.misterio["lugar"]["id"],
            self.misterio["objeto"]["id"],
        }
        resto = [c for c in CARTAS if c["id"] not in apartadas]
        self.manos = repartir(resto, [j["id"] for j in self.jugadores])
        # Sorteo único del orden de turnos: no se repite nunca más.
        self.orden_turnos = random.sample(
            [j["id"] for j in self.jugadores], len(self.jugadores)
        )
        self.turno_actual = 0
        self.numero_turno = 1
        self.estado = ESTADO_INICIADA
        self.estado_jugada = (
            JUGADA_ESPERANDO_MOVIMIENTO
            if self.modo == MODO_TABLERO
            else JUGADA_ESPERANDO_SOSPECHA
        )
        self.sospecha_pendiente = None
        self.ultima_jugada = None
        self.historial = []
        self.refutacion_deadline = None
        self.cartas_sospechadas.clear()
        self.pnj_pensando_id = None
        self.resultado_final = None
        self.ganador_id = None
        self.soluciones_deducidas.clear()
        self.tirada_pendiente = None
        self.rutas_pendientes = {}
        self.posiciones_objetos = {}
        if self.modo == MODO_TABLERO:
            ubicaciones_objetos = random.sample(
                list(TABLERO.ubicaciones), len(OBJETOS)
            )
            self.posiciones_objetos = {
                objeto["id"]: ubicacion
                for objeto, ubicacion in zip(OBJETOS, ubicaciones_objetos)
            }
        for j in self.jugadores:
            self.descartes.setdefault(j["id"], set())
            self.vistas.setdefault(j["id"], set())
            if self.modo == MODO_TABLERO:
                self.posiciones.asignar(
                    j["id"], POSICIONES_INICIALES[j["personaje_id"]]
                )
        # 8B.32: el primer turno arranca el primer plazo bloqueante.
        self.marcar_bloqueo()

    @staticmethod
    def _validar_carta_categoria(carta_id: str, categoria: str) -> str:
        cid = (carta_id or "").strip().lower()
        carta = CARTA_POR_ID.get(cid)
        if carta is None or carta["categoria"] != categoria:
            raise ValueError(f"{categoria.capitalize()} no valido.")
        return cid

    def buscar_refutador(
        self, investigador_id: str, ids_sospecha: set[str]
    ) -> tuple[str, list[str]] | None:
        """Primer rival con coincidencias, recorriendo el orden circular."""
        if investigador_id not in self.orden_turnos:
            return None
        inicio = self.orden_turnos.index(investigador_id)
        for salto in range(1, len(self.orden_turnos)):
            candidato = self.orden_turnos[(inicio + salto) % len(self.orden_turnos)]
            coincidencias = [
                carta["id"]
                for carta in self.manos.get(candidato, [])
                if carta["id"] in ids_sospecha
            ]
            if coincidencias:
                return candidato, coincidencias
        return None

    def avanzar_turno(self) -> None:
        if self.estado == ESTADO_INICIADA and self.orden_turnos:
            for salto in range(1, len(self.orden_turnos) + 1):
                indice = (self.turno_actual + salto) % len(self.orden_turnos)
                candidato = self.jugador_por_id(self.orden_turnos[indice])
                if candidato and candidato["activo_investigacion"]:
                    self.turno_actual = indice
                    self.numero_turno += 1
                    break
        self.sospecha_pendiente = None
        self.presentacion_sospecha = None
        self.estado_jugada = (
            JUGADA_ESPERANDO_MOVIMIENTO
            if self.modo == MODO_TABLERO
            else JUGADA_ESPERANDO_SOSPECHA
        )
        self.pnj_pensando_id = None
        self.tirada_pendiente = None
        self.rutas_pendientes = {}
        # 8B.32: nuevo turno = posible acción bloqueante nueva (plazo nuevo).
        self.marcar_bloqueo()

    def _participante_en_turno_para_mover(self, jugador_id: str) -> dict:
        if self.modo != MODO_TABLERO or self.estado != ESTADO_INICIADA:
            raise ValueError("El movimiento solo está disponible en modo tablero.")
        jugador = self.jugador_en_turno()
        if jugador is None or jugador["id"] != jugador_id:
            raise ValueError("Solo el jugador en turno puede mover.")
        if not jugador["activo_investigacion"]:
            raise ValueError("Este participante está eliminado.")
        return jugador

    def _tirar_dado_tablero(self, jugador_id: str, rng=None) -> int:
        self._participante_en_turno_para_mover(jugador_id)
        if self.estado_jugada != JUGADA_ESPERANDO_MOVIMIENTO:
            raise ValueError("No puedes tirar el dado en este momento.")
        posicion = self.posiciones.obtener(jugador_id)
        tirada = tirar_dado(rng)
        rutas = TABLERO.rutas_legales(posicion, tirada)
        self.tirada_pendiente = tirada
        self.rutas_pendientes = {}
        for ruta in rutas:
            self.rutas_pendientes.setdefault(ruta.destino, ruta.posiciones)
        self.estado_jugada = JUGADA_ESPERANDO_DESTINO
        # 8B.32: desde la tirada espera la ELECCIÓN de destino.
        self.marcar_bloqueo()
        return tirada

    def tirar_dado_tablero(self, jugador_id: str, rng=None) -> int:
        jugador = self._participante_en_turno_para_mover(jugador_id)
        if jugador["tipo"] != TIPO_HUMANO:
            raise ValueError("Este participante no puede realizar movimiento humano.")
        return self._tirar_dado_tablero(jugador_id, rng)

    def _mover(self, jugador_id: str, destino_id: str) -> None:
        self._participante_en_turno_para_mover(jugador_id)
        if self.estado_jugada != JUGADA_ESPERANDO_DESTINO:
            raise ValueError("No hay una tirada pendiente.")
        ruta = self.rutas_pendientes.get(destino_id)
        origen = self.posiciones.obtener(jugador_id)
        if ruta is None or not TABLERO.validar_movimiento(
            origen, destino_id, self.tirada_pendiente, ruta
        ):
            raise ValueError("Destino de movimiento no válido.")
        self.posiciones.asignar(jugador_id, destino_id)
        self._registrar_movimiento(
            jugador_id, "normal", origen, destino_id, ruta
        )
        self.tirada_pendiente = None
        self.rutas_pendientes = {}
        if TABLERO.es_ubicacion(destino_id):
            self.estado_jugada = JUGADA_ESPERANDO_SOSPECHA
            # 8B.32: entrar en una ubicación abre la sospecha obligatoria.
            self.marcar_bloqueo()
        else:
            self.avanzar_turno()

    def mover(self, jugador_id: str, destino_id: str) -> None:
        jugador = self._participante_en_turno_para_mover(jugador_id)
        if jugador["tipo"] != TIPO_HUMANO:
            raise ValueError("Este participante no puede realizar movimiento humano.")
        self._mover(jugador_id, destino_id)

    def _usar_pasadizo(self, jugador_id: str) -> str:
        self._participante_en_turno_para_mover(jugador_id)
        if self.estado_jugada != JUGADA_ESPERANDO_MOVIMIENTO:
            raise ValueError("No puedes usar un pasadizo en este momento.")
        origen = self.posiciones.obtener(jugador_id)
        destinos = TABLERO.destinos_pasadizo(origen)
        if len(destinos) != 1:
            raise ValueError("No hay un pasadizo disponible desde esta ubicación.")
        destino = TABLERO.usar_pasadizo(origen, destinos[0])
        self.posiciones.asignar(jugador_id, destino)
        self._registrar_movimiento(
            jugador_id, "pasadizo", origen, destino, (destino,)
        )
        self.estado_jugada = JUGADA_ESPERANDO_SOSPECHA
        # 8B.32: el pasadizo también desemboca en la sospecha obligatoria.
        self.marcar_bloqueo()
        return destino

    def _registrar_movimiento(
        self,
        jugador_id: str,
        tipo: str,
        origen_id: str,
        destino_id: str,
        recorrido: tuple[str, ...],
    ) -> None:
        """Conserva el recorrido exacto ya resuelto, sin recalcular reglas."""
        jugador = self.jugador_por_id(jugador_id)
        self.secuencia_movimiento += 1
        self.movimiento_resuelto = {
            "movimiento_id": self.secuencia_movimiento,
            "personaje_id": jugador["personaje_id"],
            "origen_id": origen_id,
            "destino_id": destino_id,
            "recorrido": list(recorrido),
            "tipo": tipo,
        }

    def usar_pasadizo(self, jugador_id: str) -> str:
        jugador = self._participante_en_turno_para_mover(jugador_id)
        if jugador["tipo"] != TIPO_HUMANO:
            raise ValueError("Este participante no puede realizar movimiento humano.")
        return self._usar_pasadizo(jugador_id)

    def investigadores_activos(self) -> list[dict]:
        return [j for j in self.jugadores if j["activo_investigacion"]]

    def deducir_solucion_pnj(self, jugador_id: str) -> dict | None:
        """Deduce solo desde mano, VISTA o una conclusión privada ya obtenida."""
        jugador = self.jugador_por_id(jugador_id)
        if jugador is None or jugador["tipo"] != TIPO_PNJ:
            return None
        explicita = self.soluciones_deducidas.get(jugador_id)
        if explicita:
            return dict(explicita)
        excluidas = self.mano_ids(jugador_id) | self.vistas.get(jugador_id, set())
        categorias = (
            ("sospechoso_id", SOSPECHOSOS),
            ("lugar_id", LUGARES),
            ("objeto_id", OBJETOS),
        )
        candidatas = {
            clave: [c["id"] for c in cartas if c["id"] not in excluidas]
            for clave, cartas in categorias
        }
        if all(len(ids) == 1 for ids in candidatas.values()):
            return {clave: ids[0] for clave, ids in candidatas.items()}
        return None

    def resolver_misterio(
        self, jugador_id: str, sospechoso_id: str, lugar_id: str, objeto_id: str
    ) -> bool:
        """Valida una acusación ya formada y realiza una única transición."""
        if self.estado != ESTADO_INICIADA:
            raise ValueError("La partida no admite nuevas acusaciones.")
        jugador = self.jugador_por_id(jugador_id)
        en_turno = self.jugador_en_turno()
        if jugador is None or en_turno is None or en_turno["id"] != jugador_id:
            raise ValueError("Solo el jugador en turno puede resolver el misterio.")
        if not jugador["activo_investigacion"]:
            raise ValueError("Estas eliminado como investigador.")
        fases_resolver = {JUGADA_ESPERANDO_SOSPECHA}
        if self.modo == MODO_TABLERO:
            fases_resolver.add(JUGADA_ESPERANDO_MOVIMIENTO)
        if self.estado_jugada not in fases_resolver:
            raise ValueError("Hay una refutacion pendiente.")
        acusacion = {
            "sospechoso_id": self._validar_carta_categoria(sospechoso_id, "sospechoso"),
            "lugar_id": self._validar_carta_categoria(lugar_id, "lugar"),
            "objeto_id": self._validar_carta_categoria(objeto_id, "objeto"),
        }
        correcta = all(
            acusacion[f"{categoria}_id"] == self.misterio[categoria]["id"]
            for categoria in ("sospechoso", "lugar", "objeto")
        )
        self.sospecha_pendiente = None
        self.pnj_pensando_id = None
        if correcta:
            self.estado = ESTADO_TERMINADA
            self.resultado_final = "resuelto"
            self.ganador_id = jugador_id
            self.ultima_jugada = {
                "tipo": "acusacion",
                "investigador_id": jugador_id,
                "investigador_alias": jugador["alias"],
                "resultado": "resuelto",
            }
            return True
        jugador["activo_investigacion"] = False
        if jugador["tipo"] == TIPO_HUMANO:
            jugador["decision_refutacion_pendiente"] = True
            jugador["resolucion_fallida"] = dict(acusacion)
        self.ultima_jugada = {
            "tipo": "acusacion",
            "investigador_id": jugador_id,
            "investigador_alias": jugador["alias"],
            "resultado": "acusacion_incorrecta",
            "acusacion": dict(acusacion),
        }
        if not self.investigadores_activos():
            self.estado = ESTADO_TERMINADA
            self.resultado_final = "sin_resolver"
            self.ganador_id = None
            self.ultima_jugada = {
                "tipo": "final",
                "resultado": "sin_resolver",
            }
        else:
            self.avanzar_turno()
        return False

    def peso_carta_pnj(self, jugador_id: str, carta_id: str) -> int:
        jugador = self.jugador_por_id(jugador_id)
        if jugador is None or jugador["tipo"] != TIPO_PNJ:
            raise ValueError("El jugador no es un PNJ.")
        perfil = PERFILES_PNJ[jugador["personaje_id"]]
        conocida = carta_id in self.mano_ids(jugador_id) or carta_id in self.vistas.get(
            jugador_id, set()
        )
        peso = perfil["conocida" if conocida else "desconocida"]
        if carta_id in self.cartas_sospechadas:
            peso += perfil["sospechada"]
        return peso

    def elegir_sospecha_pnj(
        self, jugador_id: str, rng=None, lugar_id: str | None = None
    ) -> dict:
        """Seleccion ponderada usando solo mano, VISTA y memoria publica."""
        rng = rng or random
        elegidas = {}
        categorias = [
            ("sospechoso_id", SOSPECHOSOS),
            ("objeto_id", OBJETOS),
        ]
        if lugar_id is None:
            categorias.insert(1, ("lugar_id", LUGARES))
        for categoria, cartas in categorias:
            elegidas[categoria] = rng.choices(
                cartas,
                weights=[self.peso_carta_pnj(jugador_id, c["id"]) for c in cartas],
                k=1,
            )[0]["id"]
        if lugar_id is not None:
            elegidas["lugar_id"] = self._validar_carta_categoria(lugar_id, "lugar")
        return elegidas

    def _adjuntar_movimiento_pnj(self, movimiento: dict) -> None:
        if self.presentacion_sospecha is not None:
            self.presentacion_sospecha["movimiento_pnj"] = movimiento
        elif self.sospecha_pendiente is not None:
            self.sospecha_pendiente["movimiento_pnj"] = movimiento
        elif self.ultima_jugada is not None:
            self.ultima_jugada["movimiento_pnj"] = movimiento

    def _formular_sospecha_pnj_tablero(
        self, jugador_id: str, posicion: str, movimiento: dict, rng
    ) -> None:
        sospecha = self.elegir_sospecha_pnj(
            jugador_id, rng=rng, lugar_id=posicion
        )
        self.formular_sospecha(jugador_id, **sospecha, rng=rng)
        self._adjuntar_movimiento_pnj(movimiento)

    def _ejecutar_turno_pnj_tablero(self, jugador: dict, rng) -> None:
        jugador_id = jugador["id"]
        posicion_origen = self.posiciones.obtener(jugador_id)
        pasadizos = TABLERO.destinos_pasadizo(posicion_origen)
        accion = (
            rng.choices(["tirar", "pasadizo"], weights=[60, 15], k=1)[0]
            if pasadizos else "tirar"
        )

        origen = self.describir_posicion(posicion_origen)["nombre"]
        if accion == "pasadizo":
            destino_id = self._usar_pasadizo(jugador_id)
            destino = self.describir_posicion(destino_id)["nombre"]
            self._formular_sospecha_pnj_tablero(
                jugador_id,
                destino_id,
                {"accion": "pasadizo", "origen": origen, "destino": destino},
                rng,
            )
            return

        tirada = self._tirar_dado_tablero(jugador_id, rng)
        destinos_ubicacion = [
            destino for destino in self.rutas_pendientes if TABLERO.es_ubicacion(destino)
        ]
        candidatos = destinos_ubicacion or list(self.rutas_pendientes)
        destino_id = rng.choice(candidatos)
        self._elegir_destino_y_continuar_pnj_tablero(
            jugador, destino_id, tirada, rng
        )

    def _elegir_destino_y_continuar_pnj_tablero(
        self, jugador: dict, destino_id: str, tirada: int, rng
    ) -> None:
        """Cola común de un PNJ de tablero: mueve con la tirada ya resuelta
        y, si entra en una ubicación, formula la sospecha. La comparten el
        turno PNJ completo y la continuación de una tirada que un humano dejó
        sin elegir destino (8B.32): misma lógica, sin duplicarla."""
        jugador_id = jugador["id"]
        origen = self.describir_posicion(self.posiciones.obtener(jugador_id))["nombre"]
        destino = self.describir_posicion(destino_id)["nombre"]
        movimiento = {
            "accion": "movimiento",
            "tirada": tirada,
            "origen": origen,
            "destino": destino,
        }
        self._mover(jugador_id, destino_id)
        if TABLERO.es_ubicacion(destino_id):
            self._formular_sospecha_pnj_tablero(
                jugador_id, destino_id, movimiento, rng
            )
        else:
            self.ultima_jugada = {
                "tipo": "movimiento",
                "investigador_id": jugador_id,
                "investigador_alias": jugador["alias"],
                "movimiento_pnj": movimiento,
            }

    def ejecutar_turno_pnj(self, rng=None) -> None:
        rng = rng or random
        jugador = self.jugador_en_turno()
        if jugador is None or jugador["tipo"] != TIPO_PNJ:
            raise ValueError("El turno actual no pertenece a un PNJ.")
        fase_esperada = (
            JUGADA_ESPERANDO_MOVIMIENTO
            if self.modo == MODO_TABLERO
            else JUGADA_ESPERANDO_SOSPECHA
        )
        if self.estado_jugada != fase_esperada:
            raise ValueError("La jugada anterior aun no esta resuelta.")
        solucion = self.deducir_solucion_pnj(jugador["id"])
        if solucion:
            self.resolver_misterio(jugador["id"], **solucion)
        elif self.modo == MODO_TABLERO:
            self._ejecutar_turno_pnj_tablero(jugador, rng)
        else:
            sospecha = self.elegir_sospecha_pnj(jugador["id"], rng=rng)
            self.formular_sospecha(jugador["id"], **sospecha, rng=rng)

    def _resolver_refutacion(self, carta_id: str) -> None:
        pendiente = self.sospecha_pendiente
        if pendiente is None:
            raise ValueError("No hay una refutacion pendiente.")
        investigador_id = pendiente["investigador_id"]
        self.vistas.setdefault(investigador_id, set()).add(carta_id)
        self.ultima_jugada = {
            "sospecha": dict(pendiente["sospecha"]),
            "investigador_id": investigador_id,
            "investigador_alias": self.jugador_por_id(investigador_id)["alias"],
            "resultado": "refutada",
            "refutador_id": pendiente["refutador_id"],
            "refutador_alias": self.jugador_por_id(pendiente["refutador_id"])["alias"],
            "carta_id": carta_id,  # solo se serializa para el investigador
        }
        if pendiente.get("movimiento_pnj"):
            self.ultima_jugada["movimiento_pnj"] = dict(
                pendiente["movimiento_pnj"]
            )
        self.refutacion_deadline = None
        self._abrir_presentacion_resultado(
            investigador_id=investigador_id,
            investigador_alias=self.jugador_por_id(investigador_id)["alias"],
            sospecha=pendiente["sospecha"],
            resultado="refutada",
            refutador_id=pendiente["refutador_id"],
            refutador_alias=self.jugador_por_id(pendiente["refutador_id"])["alias"],
            movimiento_pnj=pendiente.get("movimiento_pnj"),
        )

    def _completar_refutacion_automatica(self, rng=None) -> str | None:
        """Ruta interna única de "no elijo yo" (CONTINUAR y timeout).

        Elige una coincidencia válida al azar y completa la refutación con la
        MISMA transición que la elección manual (`_resolver_refutacion`): un
        solo VISTA, un solo avance de turno y ninguna vuelta a la elección.
        Devuelve la carta elegida o None si no procede.
        """
        if self.estado_jugada != JUGADA_ESPERANDO_REFUTADOR:
            return None
        pendiente = self.sospecha_pendiente
        if pendiente is None:
            return None
        coincidencias = list(pendiente["coincidencias"])
        if not coincidencias:
            return None
        elegida = (
            coincidencias[0]
            if len(coincidencias) == 1
            else (rng or random).choice(coincidencias)
        )
        self._resolver_refutacion(elegida)
        return elegida

    def continuar_refutacion(self, jugador_id: str, rng=None) -> str | None:
        """CONTINUAR del refutador humano: renuncia a elegir carta.

        El servidor elige una coincidencia válida al azar y completa la
        refutación por la misma ruta interna que el timeout. No devuelve al
        refutador a la elección ni pide una segunda confirmación. Devuelve la
        carta elegida.
        """
        pendiente = self.sospecha_pendiente
        if self.estado_jugada != JUGADA_ESPERANDO_REFUTADOR or pendiente is None:
            raise ValueError("No hay una refutacion pendiente.")
        if pendiente["refutador_id"] != jugador_id:
            raise ValueError("No puedes resolver esta refutacion.")
        elegida = self._completar_refutacion_automatica(rng=rng)
        if elegida is None:
            raise ValueError("No tienes ninguna carta valida para refutar.")
        return elegida

    def resolver_refutacion_auto(self, rng=None) -> str | None:
        """Resolución automática server-side al vencer el plazo humano.

        Con una coincidencia usa esa carta; con varias elige mediante
        random.choice. Comparte la resolución autoritativa con la elección
        manual: una sola carta, una sola transición y un solo VISTA.
        Devuelve la carta elegida o None si no procede.
        """
        if self.estado_jugada != JUGADA_ESPERANDO_REFUTADOR:
            return None
        pendiente = self.sospecha_pendiente
        if pendiente is None:
            return None
        refutador = self.jugador_por_id(pendiente["refutador_id"])
        if (
            refutador is None
            or refutador["tipo"] == TIPO_PNJ
        ):
            return None
        if (
            self.refutacion_deadline is None
            or time.monotonic() < self.refutacion_deadline
        ):
            return None
        return self._completar_refutacion_automatica(rng=rng)

    def elegir_modo_refutacion(self, jugador_id: str, automatica: bool) -> None:
        """Guarda la decision privada del humano tras una acusacion fallida."""
        jugador = self._exigir_humano(jugador_id)
        if jugador["activo_investigacion"]:
            raise ValueError("Solo un investigador eliminado puede elegir este modo.")
        jugador["refutacion_automatica"] = bool(automatica)
        jugador["decision_refutacion_pendiente"] = False
        jugador["resolucion_fallida"] = None

    def formular_sospecha_humano(
        self,
        jugador_id: str,
        sospechoso_id: str,
        lugar_id: str,
        objeto_id: str,
        rng=None,
    ) -> None:
        """Ruta humana de la sospecha. Tras 8B.32 un asiento convertido en
        PNJ conserva su jugador_id: sin esta comprobación recuperaría el
        control del asiento al reconectar. Los PNJ usan `formular_sospecha`.
        """
        self._exigir_humano(jugador_id)
        self.formular_sospecha(
            jugador_id, sospechoso_id, lugar_id, objeto_id, rng=rng
        )

    def resolver_misterio_humano(
        self,
        jugador_id: str,
        sospechoso_id: str,
        lugar_id: str,
        objeto_id: str,
    ) -> bool:
        """Ruta humana de la acusación, con la misma protección."""
        self._exigir_humano(jugador_id)
        return self.resolver_misterio(
            jugador_id, sospechoso_id, lugar_id, objeto_id
        )

    def _exigir_humano(self, jugador_id: str) -> dict:
        jugador = self.jugador_por_id(jugador_id)
        if jugador is None:
            raise ValueError("Jugador desconocido en esta sala.")
        if jugador["tipo"] != TIPO_HUMANO:
            raise ValueError("Este participante ya no lo controla ningún humano.")
        return jugador

    def formular_sospecha(
        self,
        jugador_id: str,
        sospechoso_id: str,
        lugar_id: str,
        objeto_id: str,
        rng=None,
        ahora: float | None = None,
    ) -> None:
        if self.estado != ESTADO_INICIADA:
            raise ValueError("La partida no esta iniciada.")
        en_turno = self.jugador_en_turno()
        if en_turno is None or en_turno["id"] != jugador_id:
            raise ValueError("Solo el jugador en turno puede formular una sospecha.")
        if not en_turno["activo_investigacion"]:
            raise ValueError("Estas eliminado como investigador.")
        if self.estado_jugada != JUGADA_ESPERANDO_SOSPECHA:
            raise ValueError("Ya hay una sospecha pendiente.")
        sospecha = {
            "sospechoso_id": self._validar_carta_categoria(sospechoso_id, "sospechoso"),
            "lugar_id": self._validar_carta_categoria(lugar_id, "lugar"),
            "objeto_id": self._validar_carta_categoria(objeto_id, "objeto"),
        }
        if self.modo == MODO_TABLERO:
            posicion = self.posiciones.obtener(jugador_id)
            if not TABLERO.es_ubicacion(posicion) or sospecha["lugar_id"] != posicion:
                raise ValueError("La sospecha debe realizarse en tu ubicación actual.")
            self.posiciones_objetos[sospecha["objeto_id"]] = sospecha["lugar_id"]
        # Consumir la alternativa inicial antes de entrar en refutación
        # impide dado o pasadizo incluso tras recargar/reconectar.
        self.estado_jugada = JUGADA_PRESENTANDO_SOSPECHA
        self.cartas_sospechadas.update(sospecha.values())
        self.pnj_pensando_id = None
        self.ultima_jugada = None
        self.sospecha_pendiente = None
        self.refutacion_deadline = None
        # 8B.32: la presentación sincronizada tiene su propio plazo canónico.
        self._reiniciar_bloqueo()
        inicio = time.monotonic() if ahora is None else ahora
        self.secuencia_presentacion += 1
        participantes = {}
        for participante in self.jugadores:
            es_autor = participante["id"] == jugador_id
            # Solo la espera automática de los PNJ sigue la velocidad de la
            # sala. La ventana del humano (10 s) es obligatoria y no se toca.
            espera = (
                self.espera_automatica(PAUSA_PRESENTACION_PNJ_SEGUNDOS)
                if participante["tipo"] == TIPO_PNJ
                else PAUSA_PRESENTACION_HUMANO_SEGUNDOS
            )
            participantes[participante["id"]] = {
                "listo": es_autor,
                "deadline": inicio if es_autor else inicio + espera,
            }
        self.presentacion_sospecha = {
            "id": self.secuencia_presentacion,
            "inicio": inicio,
            "investigador_id": jugador_id,
            "investigador_alias": en_turno["alias"],
            "sospecha": sospecha,
            "participantes": participantes,
        }

    def confirmar_presentacion_sospecha(
        self, jugador_id: str, presentacion_id: int, ahora: float | None = None
    ) -> bool:
        presentacion = self.presentacion_sospecha
        if (
            self.estado_jugada != JUGADA_PRESENTANDO_SOSPECHA
            or presentacion is None
            or presentacion["id"] != presentacion_id
        ):
            raise ValueError("La presentacion de sospecha ya no esta activa.")
        participante = self.jugador_por_id(jugador_id)
        if participante is None or participante["tipo"] == TIPO_PNJ:
            raise ValueError("Solo un participante humano puede confirmar.")
        estado = presentacion["participantes"].get(jugador_id)
        if estado is None:
            raise ValueError("No formas parte de esta presentacion.")
        if jugador_id == presentacion["investigador_id"] and presentacion.get("tipo") != "resultado":
            # El autor de 8B.30 ya está listo de salida. En el resultado
            # público (8B.31C) TODOS los humanos, investigador incluido,
            # ven el popup y su CONTINUAR cuenta igual que el de los demás.
            return False
        estado["listo"] = True
        return self.actualizar_presentacion_sospecha(ahora=ahora)

    def actualizar_presentacion_sospecha(
        self, ahora: float | None = None, rng=None
    ) -> bool:
        presentacion = self.presentacion_sospecha
        if self.estado_jugada != JUGADA_PRESENTANDO_SOSPECHA or presentacion is None:
            return False
        instante = time.monotonic() if ahora is None else ahora
        for estado in presentacion["participantes"].values():
            if not estado["listo"] and instante >= estado["deadline"]:
                estado["listo"] = True
        if not all(estado["listo"] for estado in presentacion["participantes"].values()):
            return False
        if presentacion.get("tipo") == "resultado":
            # Cierre público de la sospecha: aquí avanza el turno, una sola vez.
            self.avanzar_turno()
            return True
        self._comenzar_refutacion_presentada(rng=rng)
        return True

    def _abrir_presentacion_resultado(
        self,
        *,
        investigador_id: str,
        investigador_alias: str,
        sospecha: dict,
        resultado: str,
        refutador_id: str | None = None,
        refutador_alias: str | None = None,
        movimiento_pnj: dict | None = None,
        ahora: float | None = None,
    ) -> None:
        """Cierre PÚBLICO y síncrono de la sospecha (8B.31C).

        Reutiliza la presentación sincronizada de 8B.30 con
        `tipo: "resultado"`: mismos participantes, mismo CONTINUAR, mismos
        plazos y el mismo watchdog autoritativo. Solo se publica quién
        formuló, quién refutó y que la sospecha quedó refutada: la carta
        mostrada sigue siendo privada del investigador.

        Plazos: 14 s de lectura para cada humano (autor incluido, que aquí sí
        confirma) y 3 s para los PNJ, igual que en la presentación de sospecha.
        El turno NO avanza aquí: avanza al cerrarse la presentación, de modo
        que el resultado forma parte del flujo canónico y avanza UNA sola vez.
        """
        inicio = time.monotonic() if ahora is None else ahora
        self._registrar_historial_sospecha(
            investigador_id=investigador_id,
            sospecha=sospecha,
            resultado=resultado,
            refutador_id=refutador_id,
        )
        # La refutación ya está resuelta: nadie puede volver a refutar.
        self.sospecha_pendiente = None
        self.refutacion_deadline = None
        self.pnj_pensando_id = None
        # 8B.32: la refutación y el resultado público se rigen por sus propios
        # plazos canónicos; aquí no hay acción bloqueante de antibloqueo.
        self._reiniciar_bloqueo()
        self.secuencia_presentacion += 1
        participantes = {}
        for participante in self.jugadores:
            # Ni el investigador ni el resto quedan listos de salida: TODOS los
            # humanos confirman la lectura del resultado, autor incluido. Los
            # PNJ no ven la ventana, pero tampoco avanzan de inmediato: su
            # pausa es la MISMA que en la presentación de sospecha y, al ser
            # menor que el plazo de lectura humano, no añade ninguna espera
            # adicional: el resultado avanza cuando todos o el plazo lo digan.
            espera = (
                self.espera_automatica(PAUSA_PRESENTACION_PNJ_SEGUNDOS)
                if participante["tipo"] == TIPO_PNJ
                else PAUSA_PRESENTACION_RESULTADO_SEGUNDOS
            )
            participantes[participante["id"]] = {
                "listo": False,
                "deadline": inicio + espera,
            }
        self.presentacion_sospecha = {
            "id": self.secuencia_presentacion,
            "tipo": "resultado",
            "inicio": inicio,
            "investigador_id": investigador_id,
            "investigador_alias": investigador_alias,
            "sospecha": dict(sospecha),
            "resultado": resultado,
            "participantes": participantes,
        }
        if refutador_alias:
            self.presentacion_sospecha["refutador_alias"] = refutador_alias
        if movimiento_pnj:
            self.presentacion_sospecha["movimiento_pnj"] = dict(movimiento_pnj)
        self.estado_jugada = JUGADA_PRESENTANDO_SOSPECHA

    def _comenzar_refutacion_presentada(self, rng=None) -> None:
        presentacion = self.presentacion_sospecha
        if presentacion is None:
            raise ValueError("No hay una sospecha presentada.")
        jugador_id = presentacion["investigador_id"]
        sospecha = dict(presentacion["sospecha"])
        movimiento_pnj = presentacion.get("movimiento_pnj")
        self.presentacion_sospecha = None
        hallazgo = self.buscar_refutador(jugador_id, set(sospecha.values()))
        if hallazgo is None:
            self.ultima_jugada = {
                "sospecha": sospecha,
                "investigador_id": jugador_id,
                "investigador_alias": presentacion["investigador_alias"],
                "resultado": "sin_refutacion",
            }
            if movimiento_pnj:
                self.ultima_jugada["movimiento_pnj"] = dict(movimiento_pnj)
            investigador = self.jugador_por_id(jugador_id)
            if (
                investigador["tipo"] == TIPO_PNJ
                and not set(sospecha.values()).intersection(self.mano_ids(jugador_id))
            ):
                self.soluciones_deducidas[jugador_id] = dict(sospecha)
            self._abrir_presentacion_resultado(
                investigador_id=jugador_id,
                investigador_alias=presentacion["investigador_alias"],
                sospecha=sospecha,
                resultado="sin_refutacion",
                movimiento_pnj=movimiento_pnj,
            )
            return
        refutador_id, coincidencias = hallazgo
        self.sospecha_pendiente = {
            "investigador_id": jugador_id,
            "refutador_id": refutador_id,
            "sospecha": sospecha,
            "coincidencias": coincidencias,
        }
        if movimiento_pnj:
            self.sospecha_pendiente["movimiento_pnj"] = dict(movimiento_pnj)
        refutador = self.jugador_por_id(refutador_id)
        if refutador["tipo"] == TIPO_PNJ or refutador.get("refutacion_automatica", False):
            # PNJ y humano con preferencia automatica comparten exactamente
            # la ruta canónica de CONTINUAR/timeout: valida las coincidencias,
            # elige una sola y resuelve con la misma transicion privada.
            self.estado_jugada = JUGADA_ESPERANDO_REFUTADOR
            self._completar_refutacion_automatica(rng=rng)
        else:
            self.estado_jugada = JUGADA_ESPERANDO_REFUTADOR
            # Un único plazo canónico para todo humano. Vive en la sala y
            # no cambia por selección local, redifusión ni reconexión.
            self.refutacion_deadline = (
                time.monotonic() + TIMEOUT_REFUTACION_HUMANO_SEGUNDOS
            )
            # 8B.32: la refutación privada tiene su propio timeout de 10 s y
            # queda EXCLUIDA del antibloqueo por inactividad.
            self._reiniciar_bloqueo()

    def mostrar_carta(self, jugador_id: str, carta_id: str) -> None:
        pendiente = self.sospecha_pendiente
        if self.estado_jugada != JUGADA_ESPERANDO_REFUTADOR or pendiente is None:
            raise ValueError("No hay una refutacion pendiente.")
        if pendiente["refutador_id"] != jugador_id:
            raise ValueError("No puedes resolver esta refutacion.")
        cid = (carta_id or "").strip().lower()
        if cid not in pendiente["coincidencias"] or cid not in self.mano_ids(jugador_id):
            raise ValueError("La carta elegida no es una opcion valida.")
        self._resolver_refutacion(cid)

    def mano_ids(self, jugador_id: str) -> set[str]:
        return {c["id"] for c in self.manos.get(jugador_id, [])}

    def estado_carta(self, jugador_id: str, carta_id: str) -> str:
        """LA TENGO se deriva de la mano; el misterio nunca influye."""
        if carta_id in self.mano_ids(jugador_id):
            return INV_LA_TENGO
        if carta_id in self.vistas.get(jugador_id, set()):
            return INV_VISTA
        if carta_id in self.descartes.get(jugador_id, set()):
            return INV_DESCARTADA
        return INV_SIN_INFORMACION

    def hoja_investigacion(self, jugador_id: str) -> list[dict]:
        """Las 21 cartas canónicas con su estado privado (orden canónico)."""
        if self.jugador_por_id(jugador_id) is None:
            return []
        hoja = []
        for carta in CARTAS:
            hoja.append(
                {
                    "id": carta["id"],
                    "nombre": carta["nombre"],
                    "categoria": carta["categoria"],
                    "estado": self.estado_carta(jugador_id, carta["id"]),
                }
            )
        return hoja

    def marcar_investigacion(
        self, jugador_id: str, carta_id: str, estado: str
    ) -> dict:
        """Marca manual privada: solo descartada/sin_informacion, solo
        partida iniciada, solo su propia hoja, nunca sobre carta propia."""
        jugador = self.jugador_por_id(jugador_id)
        if jugador is None:
            raise ValueError("Jugador desconocido en esta sala.")
        if self.estado != ESTADO_INICIADA:
            raise ValueError(
                "La investigación solo está disponible una vez iniciada la partida."
            )
        cid = (carta_id or "").strip().lower()
        if cid not in CARTA_POR_ID:
            raise ValueError("Esa carta no existe.")
        est = (estado or "").strip().lower()
        if est in (INV_LA_TENGO, INV_VISTA):
            raise ValueError("Ese estado no puede marcarse manualmente.")
        if est not in ESTADOS_MANUALES:
            raise ValueError("Estado de investigación no válido.")
        if cid in self.mano_ids(jugador_id):
            raise ValueError(
                "Esa carta es tuya (LA TENGO) y no puede modificarse."
            )
        self.descartes.setdefault(jugador_id, set())
        self.vistas.setdefault(jugador_id, set())
        if est == INV_DESCARTADA:
            self.descartes[jugador_id].add(cid)
        else:  # sin_informacion: retira el descarte manual (nunca la vista)
            self.descartes[jugador_id].discard(cid)
        carta = CARTA_POR_ID[cid]
        return {
            "id": carta["id"],
            "nombre": carta["nombre"],
            "categoria": carta["categoria"],
            "estado": self.estado_carta(jugador_id, cid),
        }

    def _reiniciar_bloqueo(self) -> None:
        """Deja la sala sin bloqueo. El identificador de aviso nunca se
        reinicia: es monótono y permite descartar avisos antiguos."""
        self.bloqueo_jugador_id = None
        self.bloqueo_accion = None
        self.bloqueo_deadline = None
        self.bloqueo_aviso_emitido = False

    def jugador_bloqueante(self) -> dict | None:
        """Único humano cuya acción OBLIGATORIA detiene la partida, o None.

        Se deriva siempre del estado real: si la partida ya no está
        bloqueada por esa acción, no hay bloqueo (ni deadline) que mantener.
        La refutación privada y la presentación sincronizada, con su propio
        plazo canónico, no aparecen aquí nunca.
        """
        if self.estado != ESTADO_INICIADA:
            return None
        if self.estado_jugada not in ESTADOS_BLOQUEANTES:
            return None
        jugador = self.jugador_en_turno()
        if (
            jugador is None
            or jugador["tipo"] != TIPO_HUMANO
            or not jugador["activo_investigacion"]
        ):
            return None
        return jugador

    def marcar_bloqueo(self, ahora: float | None = None) -> None:
        """Fija el plazo canónico al ENTRAR en una acción bloqueante.

        Solo renueva el minuto cuando cambia de verdad el jugador o la
        acción bloqueante: redifusiones, recarga o reconexión no lo tocan.
        """
        instante = time.monotonic() if ahora is None else ahora
        jugador = self.jugador_bloqueante()
        if jugador is None:
            self._reiniciar_bloqueo()
            return
        accion = ACCION_POR_ESTADO_BLOQUEANTE[self.estado_jugada]
        if (
            self.bloqueo_jugador_id == jugador["id"]
            and self.bloqueo_accion == accion
            and self.bloqueo_deadline is not None
        ):
            return
        self.bloqueo_jugador_id = jugador["id"]
        self.bloqueo_accion = accion
        self.bloqueo_deadline = instante + INACTIVIDAD_BLOQUEO_SEGUNDOS
        self.bloqueo_aviso_emitido = False

    def registrar_aviso_inactividad(self, ahora: float | None = None) -> bool:
        """Vence el plazo y abre el aviso del anfitrión. Devuelve True una
        sola vez por periodo de espera.

        El anfitrión bloqueado NUNCA genera aviso: la partida sigue
        esperándolo indefinidamente y nadie más interviene.
        """
        if self.bloqueo_deadline is None or self.bloqueo_aviso_emitido:
            return False
        jugador = self.jugador_bloqueante()
        if jugador is None or jugador["id"] != self.bloqueo_jugador_id:
            return False
        if jugador["es_anfitrion"]:
            return False
        instante = time.monotonic() if ahora is None else ahora
        if instante < self.bloqueo_deadline:
            return False
        self.bloqueo_aviso_emitido = True
        return True

    def _aviso_inactividad_activo(self, jugador_id: str, aviso_id) -> None:
        """Valida que quien actúa es el anfitrión y que el aviso que tiene
        delante es el vigente (nunca uno ya resuelto o antiguo)."""
        anfitrion = self.jugador_por_id(jugador_id)
        if anfitrion is None or not anfitrion["es_anfitrion"]:
            raise ValueError("Solo el anfitrión puede decidir sobre la inactividad.")
        if not self.bloqueo_aviso_emitido or self.bloqueo_deadline is None:
            raise ValueError("No hay ningún aviso de inactividad activo.")
        if self.jugador_bloqueante() is None:
            raise ValueError("Ya no hay ninguna acción bloqueante pendiente.")
        if aviso_id is None or int(aviso_id) != self.bloqueo_aviso_id:
            raise ValueError("Ese aviso ya no está activo.")

    def seguir_esperando(
        self, jugador_id: str, aviso_id, ahora: float | None = None
    ) -> None:
        """Mantiene al jugador como humano y abre un NUEVO periodo de 60 s."""
        self._aviso_inactividad_activo(jugador_id, aviso_id)
        instante = time.monotonic() if ahora is None else ahora
        self.bloqueo_deadline = instante + INACTIVIDAD_BLOQUEO_SEGUNDOS
        self.bloqueo_aviso_id += 1
        self.bloqueo_aviso_emitido = False

    def convertir_en_pnj(self, jugador_id: str, aviso_id) -> dict:
        """El MISMO asiento pasa a controlado automáticamente.

        Se conserva jugador_id, personaje, alias, mano, vistas, descartes,
        conocimiento, posición, turno, orden, estado de eliminación, el
        misterio y las posiciones físicas de los objetos. No reparte, no
        reinicia nada y no crea un séptimo participante.
        """
        self._aviso_inactividad_activo(jugador_id, aviso_id)
        bloqueante = self.jugador_bloqueante()
        if bloqueante["id"] != self.bloqueo_jugador_id:
            raise ValueError("Ese jugador no es quien bloquea la partida.")
        if bloqueante["id"] == jugador_id:
            raise ValueError("El anfitrión no puede convertirse en PNJ.")
        bloqueante["tipo"] = TIPO_PNJ
        self._reiniciar_bloqueo()
        return bloqueante

    def continuar_bloqueo_como_pnj(self, rng=None) -> None:
        """Resuelve de inmediato la acción que el humano dejó bloqueada.

        Solo actúa si la acción pendiente NO la cubre ya la cadena PNJ
        canónica: la tirada ya realizada (`esperando_destino`) y la sospecha
        pendiente de una ubicación. `esperando_movimiento` la toma
        `ejecutar_turno_pnj` sin tocar nada aquí.
        """
        rng = rng or random
        jugador = self.jugador_en_turno()
        if jugador is None or jugador["tipo"] != TIPO_PNJ:
            raise ValueError("No hay ninguna acción bloqueante de un PNJ.")
        if self.estado != ESTADO_INICIADA:
            raise ValueError("La partida no admite nuevas jugadas.")
        if self.estado_jugada == JUGADA_ESPERANDO_DESTINO and self.tirada_pendiente is not None:
            # Ya se había tirado: se USA esa tirada, nunca otra.
            destinos_ubicacion = [
                destino
                for destino in self.rutas_pendientes
                if TABLERO.es_ubicacion(destino)
            ]
            candidatos = destinos_ubicacion or list(self.rutas_pendientes)
            if not candidatos:
                raise ValueError("No hay destinos válidos para la tirada pendiente.")
            self._elegir_destino_y_continuar_pnj_tablero(
                jugador, rng.choice(candidatos), self.tirada_pendiente, rng
            )
            return
        if self.estado_jugada == JUGADA_ESPERANDO_SOSPECHA:
            solucion = self.deducir_solucion_pnj(jugador["id"])
            if solucion:
                self.resolver_misterio(jugador["id"], **solucion)
                return
            lugar_id = (
                self.posiciones.obtener(jugador["id"])
                if self.modo == MODO_TABLERO
                else None
            )
            sospecha = self.elegir_sospecha_pnj(
                jugador["id"], rng=rng, lugar_id=lugar_id
            )
            self.formular_sospecha(jugador["id"], **sospecha, rng=rng)

    def nombre_personaje(self, personaje_id: str | None) -> str | None:
        if not personaje_id:
            return None
        personaje = PERSONAJE_POR_ID.get(personaje_id)
        return personaje["nombre"] if personaje else None

    def _identidad_publica_historial(self, jugador_id: str) -> dict:
        """Identidad pública estable, simple y apta para un futuro JSON."""
        jugador = self.jugador_por_id(jugador_id)
        if jugador is None:
            raise ValueError("Jugador desconocido al registrar el historial.")
        personaje_id = jugador["personaje_id"]
        return {
            "personaje_id": personaje_id,
            "nombre": self.nombre_personaje(personaje_id),
            "tipo": jugador["tipo"],
        }

    def _registrar_historial_sospecha(
        self,
        *,
        investigador_id: str,
        sospecha: dict,
        resultado: str,
        refutador_id: str | None = None,
    ) -> None:
        """Añade una sospecha ya resuelta exactamente una vez.

        La entrada contiene únicamente tipos JSON básicos y solo información
        pública. Se crea en la transición autoritativa al resultado, nunca al
        serializar o difundir el estado.
        """
        self.secuencia_historial += 1
        entrada = {
            "id": self.secuencia_historial,
            "turno": self.numero_turno,
            "investigador": self._identidad_publica_historial(investigador_id),
            "sospecha": self._sospecha_publica(sospecha),
            "resultado": resultado,
            "refutador": (
                self._identidad_publica_historial(refutador_id)
                if refutador_id else None
            ),
        }
        self.historial.append(entrada)

    def historial_publico(self) -> list[dict]:
        """Copia pública en orden de consulta: más reciente primero."""
        return [
            {
                "id": entrada["id"],
                "turno": entrada["turno"],
                "investigador": dict(entrada["investigador"]),
                "sospecha": {
                    clave: dict(carta)
                    for clave, carta in entrada["sospecha"].items()
                },
                "resultado": entrada["resultado"],
                "refutador": (
                    dict(entrada["refutador"])
                    if entrada["refutador"] is not None else None
                ),
            }
            for entrada in reversed(self.historial)
        ]

    def describir_posicion(self, posicion: str | None) -> dict | None:
        if not posicion:
            return None
        if posicion in TABLERO.ubicaciones:
            return {
                "id": posicion,
                "nombre": TABLERO.ubicaciones[posicion]["nombre"],
                "tipo": "ubicacion",
            }
        for camino in TABLERO.caminos.values():
            if posicion in camino.casillas:
                numero = camino.casillas.index(posicion) + 1
                origen = TABLERO.ubicaciones[camino.origen]["nombre"]
                destino = TABLERO.ubicaciones[camino.destino]["nombre"]
                return {
                    "id": posicion,
                    "nombre": f"Camino {origen} ↔ {destino} · {numero}/4",
                    "tipo": "casilla",
                }
        return None

    def _sospecha_publica(self, datos: dict) -> dict:
        return {
            clave: {"id": cid, "nombre": CARTA_POR_ID[cid]["nombre"]}
            for clave, cid in datos.items()
        }

    def jugada_publica(self) -> dict:
        """Estado visible de la jugada, sin opciones ni carta mostrada."""
        fuente = self.presentacion_sospecha or self.sospecha_pendiente or self.ultima_jugada
        if fuente is None:
            return {"estado": self.estado_jugada}
        resultado = fuente.get("resultado", "pendiente")
        if fuente.get("tipo") == "movimiento":
            return {
                "estado": self.estado_jugada,
                "tipo": "movimiento",
                "investigador_alias": fuente["investigador_alias"],
                "movimiento_pnj": dict(fuente["movimiento_pnj"]),
            }
        if fuente.get("tipo") in {"acusacion", "final"}:
            publico = {
                "estado": self.estado_jugada,
                "tipo": fuente["tipo"],
                "resultado": resultado,
            }
            if fuente.get("investigador_alias"):
                publico["investigador_alias"] = fuente["investigador_alias"]
            return publico
        publico = {
            "estado": self.estado_jugada,
            "investigador_alias": fuente["investigador_alias"]
            if "investigador_alias" in fuente
            else self.jugador_por_id(fuente["investigador_id"])["alias"],
            "sospecha": self._sospecha_publica(fuente["sospecha"]),
            "resultado": resultado,
        }
        if resultado == "refutada":
            publico["refutador_alias"] = fuente["refutador_alias"]
        if fuente.get("movimiento_pnj"):
            publico["movimiento_pnj"] = dict(fuente["movimiento_pnj"])
        if fuente is self.presentacion_sospecha and fuente.get("tipo") == "resultado":
            # El frontend distingue el cierre público de la presentación de
            # 8B.30 (que no lleva `tipo`). No añade información privada.
            publico["presentacion_tipo"] = "resultado"
        return publico

    def jugada_privada(self, jugador_id: str) -> dict:
        privada = dict(self.jugada_publica())
        presentacion = self.presentacion_sospecha
        if presentacion is not None:
            participante = presentacion["participantes"].get(jugador_id)
            privada["presentacion_id"] = presentacion["id"]
            privada["presentacion_pendiente"] = bool(
                participante
                and not participante["listo"]
                and (
                    jugador_id != presentacion["investigador_id"]
                    or presentacion.get("tipo") == "resultado"
                )
                and (self.jugador_por_id(jugador_id) or {}).get("tipo") == TIPO_HUMANO
            )
            if privada["presentacion_pendiente"]:
                privada["presentacion_restante_seg"] = max(
                    0.0, participante["deadline"] - time.monotonic()
                )
        pendiente = self.sospecha_pendiente
        if pendiente and pendiente["investigador_id"] == jugador_id:
            privada["esperando_resolucion"] = True
        if pendiente and pendiente["refutador_id"] == jugador_id:
            privada["opciones_refutacion"] = [
                dict(CARTA_POR_ID[cid]) for cid in pendiente["coincidencias"]
            ]
            # Aviso informativo; la autoridad y el deadline viven en servidor.
            if self.refutacion_deadline is not None:
                privada["timeout_refutacion_seg"] = (
                    TIMEOUT_REFUTACION_HUMANO_SEGUNDOS
                )
        jugador = self.jugador_por_id(jugador_id)
        if (
            jugador
            and jugador.get("decision_refutacion_pendiente")
            and jugador.get("resolucion_fallida")
        ):
            privada["resolucion_fallida"] = [
                dict(CARTA_POR_ID[jugador["resolucion_fallida"][f"{categoria}_id"]])
                for categoria in ("sospechoso", "lugar", "objeto")
            ]
        ultima = self.ultima_jugada
        if ultima and ultima.get("carta_id") and ultima["investigador_id"] == jugador_id:
            privada["carta_mostrada"] = dict(CARTA_POR_ID[ultima["carta_id"]])
        return privada

    def estado_publico(self) -> dict:
        """Seguro para todos: personajes, orden y recuentos. Nunca cartas."""
        en_turno = self.jugador_en_turno()
        return {
            "codigo": self.codigo,
            "estado": self.estado,
            "modo": self.modo,
            "jugadores": [
                {
                    "alias": j["alias"],
                    "es_anfitrion": j["es_anfitrion"],
                    "num_cartas": self.num_cartas(j["id"]),
                    "personaje_id": j["personaje_id"],
                    "personaje": self.nombre_personaje(j["personaje_id"]),
                    "tipo": j["tipo"],
                    "activo": j["activo_investigacion"],
                    **(
                        {"posicion": self.describir_posicion(
                            self.posiciones.obtener(j["id"])
                        )}
                        if self.modo == MODO_TABLERO else {}
                    ),
                }
                for j in self.jugadores
            ],
            "orden": [
                {
                    "alias": self.jugador_por_id(jid)["alias"],
                    "personaje": self.nombre_personaje(
                        self.jugador_por_id(jid)["personaje_id"]
                    ),
                    "tipo": self.jugador_por_id(jid)["tipo"],
                    "activo": self.jugador_por_id(jid)["activo_investigacion"],
                }
                for jid in self.orden_turnos
            ],
            "turno_alias": en_turno["alias"] if en_turno else None,
            "turno_tipo": en_turno["tipo"] if en_turno else None,
            "pnj_pensando_alias": (
                self.jugador_por_id(self.pnj_pensando_id)["alias"]
                if self.pnj_pensando_id else None
            ),
            "movimiento_resuelto": (
                dict(self.movimiento_resuelto)
                if self.movimiento_resuelto is not None else None
            ),
            **(
                {"posiciones_objetos": dict(self.posiciones_objetos)}
                if self.modo == MODO_TABLERO else {}
            ),
            "fase_tablero": self.estado_jugada if self.modo == MODO_TABLERO else None,
            "tirada": self.tirada_pendiente,
            "jugada": self.jugada_publica(),
            "historial": self.historial_publico(),
            "resultado_final": self.resultado_final,
            "ganador_alias": (
                self.jugador_por_id(self.ganador_id)["alias"]
                if self.ganador_id else None
            ),
            **(
                {"solucion": {
                    categoria: {
                        "id": carta["id"],
                        "nombre": carta["nombre"],
                    }
                    for categoria, carta in self.misterio.items()
                }}
                if self.estado == ESTADO_TERMINADA and self.misterio
                else {}
            ),
        }

    def estado_privado(self, jugador_id: str) -> dict:
        """Solo para la conexión de ese jugador: incluye sus cartas
        y su propia hoja de investigación (nunca las de otros)."""
        jugador = self.jugador_por_id(jugador_id)
        en_turno = self.jugador_en_turno()
        publico = self.estado_publico()
        return {
            "codigo": self.codigo,
            "estado": self.estado,
            "modo": self.modo,
            "alias": jugador["alias"] if jugador else "",
            "es_anfitrion": bool(jugador and jugador["es_anfitrion"]),
            # Espera automática compartida: la ven todos para que el ritmo
            # sea el mismo en todas las pantallas. No es una credencial.
            "velocidad_acciones": self.velocidad_acciones,
            # Microfase 3: todos ven que la partida está detenida.
            "pausada": self.pausada,
            "personaje_id": jugador["personaje_id"] if jugador else None,
            "personaje": self.nombre_personaje(
                jugador["personaje_id"] if jugador else None
            ),
            "mis_cartas": [dict(c) for c in self.manos.get(jugador_id, [])],
            "investigacion": self.hoja_investigacion(jugador_id),
            "es_mi_turno": bool(en_turno and en_turno["id"] == jugador_id),
            "activo_investigacion": bool(
                jugador and jugador["activo_investigacion"]
            ),
            "refutacion_automatica": bool(
                jugador and jugador.get("refutacion_automatica", False)
            ),
            "jugadores": publico["jugadores"],
            "orden": publico["orden"],
            "turno_alias": publico["turno_alias"],
            "turno_tipo": publico["turno_tipo"],
            "pnj_pensando_alias": publico["pnj_pensando_alias"],
            "movimiento_resuelto": publico["movimiento_resuelto"],
            **(
                {"posiciones_objetos": publico["posiciones_objetos"]}
                if "posiciones_objetos" in publico else {}
            ),
            "jugada": self.jugada_privada(jugador_id),
            "historial": publico["historial"],
            # 8B.32: el aviso de inactividad es privado del ANFITRIÓN y solo
            # travels con su alias. Nunca mano, ni opciones, ni conocimiento.
            "inactividad": self._inactividad_privada(jugador_id),
            "posicion": self.describir_posicion(
                self.posiciones.obtener(jugador_id)
            ),
            "movimiento": self._movimiento_privado(jugador_id),
            "resultado_final": publico["resultado_final"],
            "ganador_alias": publico["ganador_alias"],
            **(
                {"solucion": publico["solucion"]}
                if "solucion" in publico else {}
            ),
        }

    def _inactividad_privada(self, jugador_id: str) -> dict | None:
        """Aviso de antibloqueo: solo para el anfitrión y solo con el alias
        del jugador que bloquea. `null` para todos los demás, siempre."""
        jugador = self.jugador_por_id(jugador_id)
        if jugador is None or not jugador["es_anfitrion"]:
            return None
        if not self.bloqueo_aviso_emitido or self.bloqueo_deadline is None:
            return None
        bloqueante = self.jugador_bloqueante()
        if bloqueante is None or bloqueante["id"] != self.bloqueo_jugador_id:
            return None
        return {"aviso_id": self.bloqueo_aviso_id, "alias": bloqueante["alias"]}

    def _movimiento_privado(self, jugador_id: str) -> dict:
        if self.modo != MODO_TABLERO:
            return {}
        jugador = self.jugador_por_id(jugador_id)
        en_turno = self.jugador_en_turno()
        es_turno_humano = bool(
            jugador
            and en_turno
            and en_turno["id"] == jugador_id
            and jugador["tipo"] == TIPO_HUMANO
            and jugador["activo_investigacion"]
        )
        datos = {
            "fase": self.estado_jugada,
            "puede_tirar": es_turno_humano
            and self.estado_jugada == JUGADA_ESPERANDO_MOVIMIENTO,
            "tirada": self.tirada_pendiente,
            "puede_sospechar": es_turno_humano
            and self.estado_jugada == JUGADA_ESPERANDO_SOSPECHA,
        }
        if es_turno_humano and self.estado_jugada == JUGADA_ESPERANDO_MOVIMIENTO:
            posicion = self.posiciones.obtener(jugador_id)
            destinos = TABLERO.destinos_pasadizo(posicion)
            if destinos:
                datos["pasadizo"] = self.describir_posicion(destinos[0])
        if es_turno_humano and self.estado_jugada == JUGADA_ESPERANDO_DESTINO:
            datos["destinos"] = [
                self.describir_posicion(destino)
                for destino in self.rutas_pendientes
            ]
        return datos


class GestorSalas:
    """Registro en memoria de todas las salas."""

    def __init__(self):
        self.salas: dict[str, Sala] = {}

    def crear_sala(self, alias: str, modo: str = MODO_RAPIDO) -> tuple[Sala, dict]:
        error = validar_alias(alias)
        if error:
            raise ValueError(error)
        codigo = generar_codigo()
        while codigo in self.salas:
            codigo = generar_codigo()
        sala = Sala(codigo, modo=modo)
        anfitrion = sala.agregar_jugador(alias, es_anfitrion=True)
        self.salas[codigo] = sala
        return sala, anfitrion

    def obtener(self, codigo: str) -> Sala | None:
        if not codigo:
            return None
        return self.salas.get(codigo.strip().upper())

    def importar_partida(self, datos) -> tuple[Sala, bool]:
        """Reconstruye una partida guardada (Microfase 5).

        Devuelve la sala y si ha habido que renumerar su código.

        Es ATÓMICA: primero valida y luego construye la sala entera en local.
        Si algo falla no queda ninguna sala a medias, y una partida que ya
        existe no se toca nunca. Si el código está ocupado se genera otro y
        se avisa con el segundo valor, sin alterar la partida en marcha.

        NO reparte cartas, NO genera misterio y NO rearma tareas: eso es
        trabajo de quien la abre, con los mecanismos de siempre.
        """
        # Importación diferida: persistencia necesita a Sala, y no puede
        # importarse arriba sin formar un círculo.
        from app.motor import persistencia

        estado = dict(persistencia.validar(datos))
        codigo_original = estado["codigo"]
        reenumerada = codigo_original in self.salas
        if reenumerada:
            codigo = generar_codigo()
            while codigo in self.salas:
                codigo = generar_codigo()
            estado["codigo"] = codigo
        # Hasta aquí no existe nada en el registro: si `restaurar_sala`
        # falla, la excepción sale y el registro sigue como estaba.
        sala = persistencia.restaurar_sala(estado)
        self.salas[sala.codigo] = sala
        return sala, reenumerada

    def unirse(self, codigo: str, alias: str) -> tuple[Sala, dict]:
        sala = self.obtener(codigo)
        if sala is None:
            raise LookupError("La sala no existe. Revisa el código.")
        if sala.estado != ESTADO_ESPERANDO:
            raise ValueError("La partida ya comenzó. No se admiten más jugadores.")
        if len(sala.jugadores) >= MAX_JUGADORES:
            raise ValueError(
                f"La sala está completa (máximo {MAX_JUGADORES} jugadores)."
            )
        error = validar_alias(alias)
        if error:
            raise ValueError(error)
        if sala.alias_existe(alias):
            raise ValueError("Ese alias ya está en uso en esta sala.")
        jugador = sala.agregar_jugador(alias)
        return sala, jugador
