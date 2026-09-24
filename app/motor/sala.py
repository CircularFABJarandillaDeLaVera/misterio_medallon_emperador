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

# Timeout server-side para refutación de humano eliminado (Microfase 5A).
# Solo HUMANO + ELIMINADO + VARIAS coincidencias. Segundos aproximados.
TIMEOUT_REFUTACION_ELIMINADO_SEGUNDOS = 3.0

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
        self.misterio: dict | None = None  # SECRETO: nunca sale del servidor
        self.manos: dict[str, list[dict]] = {}  # jugador_id -> sus cartas
        self.orden_turnos: list[str] = []  # jugador_ids sorteados una sola vez
        self.turno_actual: int = 0
        # Hoja privada: solo descartes manuales + vistas automáticas
        # por refutaciones. LA TENGO se deriva de la mano y
        # SIN INFORMACIÓN es la ausencia de marca. Nada de esto es público.
        self.descartes: dict[str, set[str]] = {}  # jugador_id -> carta_ids
        self.vistas: dict[str, set[str]] = {}  # jugador_id -> carta_ids (Sprint 4)
        self.estado_jugada = JUGADA_ESPERANDO_SOSPECHA
        self.sospecha_pendiente: dict | None = None
        self.ultima_jugada: dict | None = None
        # Deadline monotónico de la refutación pendiente de un humano
        # eliminado (Microfase 5A). Vive en la sala: sobrevive a
        # recargas y reconexiones porque nunca se reinicia salvo
        # nueva sospecha o resolución.
        self.refutacion_deadline: float | None = None
        self.cartas_sospechadas: set[str] = set()  # memoria exclusivamente publica
        self.pnj_pensando_id: str | None = None
        self.resultado_final: str | None = None
        self.ganador_id: str | None = None
        # Conocimiento privado deducido sin consultar el misterio.
        self.soluciones_deducidas: dict[str, dict] = {}
        self.posiciones = PosicionesParticipantes(TABLERO)
        self.tirada_pendiente: int | None = None
        self.rutas_pendientes: dict[str, tuple[str, ...]] = {}

    def jugador_por_id(self, jugador_id: str) -> dict | None:
        for j in self.jugadores:
            if j["id"] == jugador_id:
                return j
        return None

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
        self.estado = ESTADO_INICIADA
        self.estado_jugada = (
            JUGADA_ESPERANDO_MOVIMIENTO
            if self.modo == MODO_TABLERO
            else JUGADA_ESPERANDO_SOSPECHA
        )
        self.sospecha_pendiente = None
        self.ultima_jugada = None
        self.refutacion_deadline = None
        self.cartas_sospechadas.clear()
        self.pnj_pensando_id = None
        self.resultado_final = None
        self.ganador_id = None
        self.soluciones_deducidas.clear()
        self.tirada_pendiente = None
        self.rutas_pendientes = {}
        for j in self.jugadores:
            self.descartes.setdefault(j["id"], set())
            self.vistas.setdefault(j["id"], set())
            if self.modo == MODO_TABLERO:
                self.posiciones.asignar(
                    j["id"], POSICIONES_INICIALES[j["personaje_id"]]
                )

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
                    break
        self.sospecha_pendiente = None
        self.estado_jugada = (
            JUGADA_ESPERANDO_MOVIMIENTO
            if self.modo == MODO_TABLERO
            else JUGADA_ESPERANDO_SOSPECHA
        )
        self.pnj_pensando_id = None
        self.tirada_pendiente = None
        self.rutas_pendientes = {}

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
        self.tirada_pendiente = None
        self.rutas_pendientes = {}
        if TABLERO.es_ubicacion(destino_id):
            self.estado_jugada = JUGADA_ESPERANDO_SOSPECHA
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
        self.estado_jugada = JUGADA_ESPERANDO_SOSPECHA
        return destino

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
        self.ultima_jugada = {
            "tipo": "acusacion",
            "investigador_id": jugador_id,
            "investigador_alias": jugador["alias"],
            "resultado": "acusacion_incorrecta",
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
        if self.sospecha_pendiente is not None:
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
        self.avanzar_turno()

    def resolver_refutacion_eliminado_auto(self, rng=None) -> str | None:
        """Resolución automática server-side por timeout (Microfase 5A).

        Solo HUMANO + ELIMINADO + VARIAS coincidencias con plazo vencido.
        La elección es random.choice(coincidencias), nunca la primera por
        defecto, y sigue el mismo _resolver_refutacion autoritativo que
        la elección manual (una sola resolución, un solo turno, un VISTA).
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
            or refutador["activo_investigacion"]
            or len(pendiente["coincidencias"]) <= 1
        ):
            return None
        if (
            self.refutacion_deadline is None
            or time.monotonic() < self.refutacion_deadline
        ):
            return None
        elegida = (rng or random).choice(list(pendiente["coincidencias"]))
        self._resolver_refutacion(elegida)
        return elegida

    def formular_sospecha(
        self,
        jugador_id: str,
        sospechoso_id: str,
        lugar_id: str,
        objeto_id: str,
        rng=None,
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
        # Consumir la alternativa inicial antes de entrar en refutación
        # impide dado o pasadizo incluso tras recargar/reconectar.
        self.estado_jugada = JUGADA_ESPERANDO_SOSPECHA
        self.cartas_sospechadas.update(sospecha.values())
        self.pnj_pensando_id = None
        self.ultima_jugada = None
        hallazgo = self.buscar_refutador(jugador_id, set(sospecha.values()))
        if hallazgo is None:
            self.ultima_jugada = {
                "sospecha": sospecha,
                "investigador_id": jugador_id,
                "investigador_alias": en_turno["alias"],
                "resultado": "sin_refutacion",
            }
            investigador = self.jugador_por_id(jugador_id)
            if (
                investigador["tipo"] == TIPO_PNJ
                and not set(sospecha.values()).intersection(self.mano_ids(jugador_id))
            ):
                self.soluciones_deducidas[jugador_id] = dict(sospecha)
            self.avanzar_turno()
            return
        refutador_id, coincidencias = hallazgo
        self.sospecha_pendiente = {
            "investigador_id": jugador_id,
            "refutador_id": refutador_id,
            "sospecha": sospecha,
            "coincidencias": coincidencias,
        }
        refutador = self.jugador_por_id(refutador_id)
        if len(coincidencias) == 1 or refutador["tipo"] == TIPO_PNJ:
            elegida = (
                coincidencias[0]
                if len(coincidencias) == 1
                else (rng or random).choice(coincidencias)
            )
            self._resolver_refutacion(elegida)
        else:
            self.estado_jugada = JUGADA_ESPERANDO_REFUTADOR
            # Timeout SOLO para humano eliminado con varias opciones: el
            # plazo vive en la sala y no se reinicia por reconexiones.
            if not refutador["activo_investigacion"]:
                self.refutacion_deadline = (
                    time.monotonic() + TIMEOUT_REFUTACION_ELIMINADO_SEGUNDOS
                )
            else:
                self.refutacion_deadline = None

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

    def nombre_personaje(self, personaje_id: str | None) -> str | None:
        if not personaje_id:
            return None
        personaje = PERSONAJE_POR_ID.get(personaje_id)
        return personaje["nombre"] if personaje else None

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
        fuente = self.sospecha_pendiente or self.ultima_jugada
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
        return publico

    def jugada_privada(self, jugador_id: str) -> dict:
        privada = dict(self.jugada_publica())
        pendiente = self.sospecha_pendiente
        if pendiente and pendiente["investigador_id"] == jugador_id:
            privada["esperando_resolucion"] = True
        if pendiente and pendiente["refutador_id"] == jugador_id:
            privada["opciones_refutacion"] = [
                dict(CARTA_POR_ID[cid]) for cid in pendiente["coincidencias"]
            ]
            # Aviso server-side de plazo (solo humano eliminado con varias
            # opciones): el cliente lo muestra, pero la autoridad es el
            # servidor. Ninguna otra carta ni deadline viaja aquí.
            if self.refutacion_deadline is not None:
                privada["timeout_refutacion_seg"] = (
                    TIMEOUT_REFUTACION_ELIMINADO_SEGUNDOS
                )
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
            "fase_tablero": self.estado_jugada if self.modo == MODO_TABLERO else None,
            "tirada": self.tirada_pendiente,
            "jugada": self.jugada_publica(),
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
            "jugadores": publico["jugadores"],
            "orden": publico["orden"],
            "turno_alias": publico["turno_alias"],
            "turno_tipo": publico["turno_tipo"],
            "pnj_pensando_alias": publico["pnj_pensando_alias"],
            "jugada": self.jugada_privada(jugador_id),
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
