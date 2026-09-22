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

import random
import secrets
import uuid

from app.datos.jarandilla import (
    CARTA_POR_ID,
    CARTAS,
    LUGARES,
    OBJETOS,
    SOSPECHOSOS,
)

# Vista de solo lectura sobre los sospechosos canónicos (sin duplicar datos).
PERSONAJE_POR_ID: dict[str, dict] = {p["id"]: p for p in SOSPECHOSOS}

ESTADO_ESPERANDO = "esperando"
ESTADO_INICIADA = "iniciada"

MIN_JUGADORES = 3
MAX_JUGADORES = 6

# Hoja de investigación privada (Microfase 3B). Terminología de OBJETOS.
INV_SIN_INFORMACION = "sin_informacion"
INV_DESCARTADA = "descartada"
INV_LA_TENGO = "la_tengo"  # derivado de la mano; nunca se almacena ni se marca
INV_VISTA = "vista"  # reservado para Sprint 4 (refutaciones); sin lógica aún
ESTADOS_MANUALES = frozenset({INV_SIN_INFORMACION, INV_DESCARTADA})

_ALFABETO_CODIGO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin I, O, 0, 1


def generar_codigo() -> str:
    """Genera un código corto tipo JARA-XXXX."""
    sufijo = "".join(secrets.choice(_ALFABETO_CODIGO) for _ in range(4))
    return f"JARA-{sufijo}"


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
    def __init__(self, codigo: str):
        self.codigo = codigo
        self.estado = ESTADO_ESPERANDO
        self.jugadores: list[dict] = []  # {id, alias, es_anfitrion, personaje_id}
        self.misterio: dict | None = None  # SECRETO: nunca sale del servidor
        self.manos: dict[str, list[dict]] = {}  # jugador_id -> sus cartas
        self.orden_turnos: list[str] = []  # jugador_ids sorteados una sola vez
        self.turno_actual: int = 0
        # Hoja privada: solo descartes manuales + vistas automáticas
        # (reservadas para Sprint 4). LA TENGO se deriva de la mano y
        # SIN INFORMACIÓN es la ausencia de marca. Nada de esto es público.
        self.descartes: dict[str, set[str]] = {}  # jugador_id -> carta_ids
        self.vistas: dict[str, set[str]] = {}  # jugador_id -> carta_ids (Sprint 4)

    def jugador_por_id(self, jugador_id: str) -> dict | None:
        for j in self.jugadores:
            if j["id"] == jugador_id:
                return j
        return None

    def alias_existe(self, alias: str) -> bool:
        limpio = normalizar_alias(alias).lower()
        return any(j["alias"].lower() == limpio for j in self.jugadores)

    def agregar_jugador(self, alias: str, es_anfitrion: bool = False) -> dict:
        jugador = {
            "id": uuid.uuid4().hex[:12],
            "alias": normalizar_alias(alias),
            "es_anfitrion": es_anfitrion,
            "personaje_id": None,
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
                # Si se va el anfitrión, el más antiguo hereda el rol.
                if eliminado["es_anfitrion"] and self.jugadores:
                    self.jugadores[0]["es_anfitrion"] = True
                return eliminado
        return None

    def num_cartas(self, jugador_id: str) -> int:
        return len(self.manos.get(jugador_id, []))

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

    def iniciar(self, jugador_id: str) -> None:
        """Valida, bloquea personajes, crea el misterio, reparte y sortea."""
        error = self.puede_iniciar(jugador_id)
        if error:
            raise ValueError(error)
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
        self.estado = ESTADO_INICIADA
        for j in self.jugadores:
            self.descartes.setdefault(j["id"], set())
            self.vistas.setdefault(j["id"], set())

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

    def nombre_personaje(self, personaje_id: str | None) -> str | None:
        if not personaje_id:
            return None
        personaje = PERSONAJE_POR_ID.get(personaje_id)
        return personaje["nombre"] if personaje else None

    def estado_publico(self) -> dict:
        """Seguro para todos: personajes, orden y recuentos. Nunca cartas."""
        en_turno = self.jugador_en_turno()
        return {
            "codigo": self.codigo,
            "estado": self.estado,
            "jugadores": [
                {
                    "alias": j["alias"],
                    "es_anfitrion": j["es_anfitrion"],
                    "num_cartas": self.num_cartas(j["id"]),
                    "personaje_id": j["personaje_id"],
                    "personaje": self.nombre_personaje(j["personaje_id"]),
                }
                for j in self.jugadores
            ],
            "orden": [
                {
                    "alias": self.jugador_por_id(jid)["alias"],
                    "personaje": self.nombre_personaje(
                        self.jugador_por_id(jid)["personaje_id"]
                    ),
                }
                for jid in self.orden_turnos
            ],
            "turno_alias": en_turno["alias"] if en_turno else None,
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
            "alias": jugador["alias"] if jugador else "",
            "es_anfitrion": bool(jugador and jugador["es_anfitrion"]),
            "personaje_id": jugador["personaje_id"] if jugador else None,
            "personaje": self.nombre_personaje(
                jugador["personaje_id"] if jugador else None
            ),
            "mis_cartas": [dict(c) for c in self.manos.get(jugador_id, [])],
            "investigacion": self.hoja_investigacion(jugador_id),
            "es_mi_turno": bool(en_turno and en_turno["id"] == jugador_id),
            "jugadores": publico["jugadores"],
            "orden": publico["orden"],
            "turno_alias": publico["turno_alias"],
        }


class GestorSalas:
    """Registro en memoria de todas las salas."""

    def __init__(self):
        self.salas: dict[str, Sala] = {}

    def crear_sala(self, alias: str) -> tuple[Sala, dict]:
        error = validar_alias(alias)
        if error:
            raise ValueError(error)
        codigo = generar_codigo()
        while codigo in self.salas:
            codigo = generar_codigo()
        sala = Sala(codigo)
        anfitrion = sala.agregar_jugador(alias, es_anfitrion=True)
        self.salas[codigo] = sala
        return sala, anfitrion

    def obtener(self, codigo: str) -> Sala | None:
        if not codigo:
            return None
        return self.salas.get(codigo.strip().upper())

    def unirse(self, codigo: str, alias: str) -> tuple[Sala, dict]:
        sala = self.obtener(codigo)
        if sala is None:
            raise LookupError("La sala no existe. Revisa el código.")
        if sala.estado == ESTADO_INICIADA:
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
