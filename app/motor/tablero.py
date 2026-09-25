"""Grafo lógico del tablero de Cluedo Jarandilla.

Independiente de Sala, WebSocket y cualquier representación visual. Un camino
normal tiene cuatro cuadros de movimiento: ubicación -> c1 -> c2 -> c3 ->
ubicación. El cuarto cuadro representa el acceso final, no una posición
intermedia adicional. Cada arista consume un punto y entrar termina el movimiento.

En esta fase no hay bloqueo: varias fichas pueden compartir cualquier nodo.
"""
from __future__ import annotations

from dataclasses import dataclass
import random

from app.datos.jarandilla import LUGARES

CENTRO_ID = "parador"
PLAZA_ID = "plaza-constitucion"
EXTERIORES = (
    "plaza-constitucion",
    "iglesia-san-agustin",
    "ermita-sopetran",
    "cristo-humilladero",
    "nuestra-senora-torre",
    "museo-escobazos",
    "puente-parral",
    "picota",
)

PAREJAS_PERIMETRALES = tuple(
    (EXTERIORES[i], EXTERIORES[(i + 1) % len(EXTERIORES)])
    for i in range(len(EXTERIORES))
)
PAREJAS_RADIALES = tuple((exterior, CENTRO_ID) for exterior in EXTERIORES)
PAREJAS_PASADIZOS = (
    ("plaza-constitucion", "nuestra-senora-torre"),
    ("ermita-sopetran", "puente-parral"),
)


@dataclass(frozen=True)
class Camino:
    id: str
    origen: str
    destino: str
    casillas: tuple[str, ...]
    tipo: str = "camino"


@dataclass(frozen=True)
class Pasadizo:
    id: str
    origen: str
    destino: str
    tipo: str = "pasadizo"


@dataclass(frozen=True)
class Ruta:
    origen: str
    destino: str
    posiciones: tuple[str, ...]
    conexiones: tuple[str, ...]
    puntos_usados: int
    termina_en_ubicacion: bool


def tirar_dado(rng=None) -> int:
    """Tirada server-side inyectable en tests."""
    resultado = (rng or random).randint(1, 6)
    if not isinstance(resultado, int) or isinstance(resultado, bool) or not 1 <= resultado <= 6:
        raise ValueError("El dado debe producir un valor entre 1 y 6.")
    return resultado


class Tablero:
    def __init__(self) -> None:
        self.ubicaciones = {lugar["id"]: dict(lugar) for lugar in LUGARES}
        if set(self.ubicaciones) != {CENTRO_ID, *EXTERIORES}:
            raise ValueError("Las ubicaciones canónicas no coinciden con el tablero.")
        self.caminos: dict[str, Camino] = {}
        self.pasadizos: dict[str, Pasadizo] = {}
        # nodo -> [(vecino, conexión)]. Solo incluye movimiento normal.
        self._adyacencia: dict[str, list[tuple[str, str]]] = {
            ubicacion: [] for ubicacion in self.ubicaciones
        }
        for origen, destino in PAREJAS_PERIMETRALES + PAREJAS_RADIALES:
            self._crear_camino(origen, destino)
        for origen, destino in PAREJAS_PASADIZOS:
            pid = f"pasadizo-{origen}-{destino}"
            self.pasadizos[pid] = Pasadizo(pid, origen, destino)

    def _crear_camino(self, origen: str, destino: str) -> None:
        camino_id = f"camino-{origen}-{destino}"
        # Tres posiciones intermedias; el cuarto cuadro físico es el acceso
        # final a la ubicación destino.
        casillas = tuple(f"{camino_id}-{i}" for i in range(1, 4))
        camino = Camino(camino_id, origen, destino, casillas)
        self.caminos[camino_id] = camino
        for casilla in casillas:
            self._adyacencia[casilla] = []
        secuencia = (origen, *casillas, destino)
        for actual, siguiente in zip(secuencia, secuencia[1:]):
            self._adyacencia[actual].append((siguiente, camino_id))
            self._adyacencia[siguiente].append((actual, camino_id))

    @property
    def casillas(self) -> frozenset[str]:
        return frozenset(
            casilla for camino in self.caminos.values() for casilla in camino.casillas
        )

    @property
    def posiciones_validas(self) -> frozenset[str]:
        return frozenset(self.ubicaciones) | self.casillas

    def es_ubicacion(self, posicion: str) -> bool:
        return posicion in self.ubicaciones

    def vecinos_normales(self, posicion: str) -> tuple[str, ...]:
        self._validar_posicion(posicion)
        return tuple(vecino for vecino, _ in self._adyacencia[posicion])

    def distancia_normal(self, origen: str, destino: str) -> int | None:
        """Distancia de una conexión normal directa, o None si no existe."""
        self._validar_posicion(origen)
        self._validar_posicion(destino)
        if not self.es_ubicacion(origen) or not self.es_ubicacion(destino):
            return None
        for camino in self.caminos.values():
            if {camino.origen, camino.destino} == {origen, destino}:
                return len(camino.casillas) + 1
        return None

    def _validar_posicion(self, posicion: str) -> None:
        if posicion not in self.posiciones_validas:
            raise ValueError("Posición de tablero desconocida.")

    def rutas_legales(self, origen: str, puntos: int) -> list[Ruta]:
        """Rutas normales sin nodos repetidos.

        Una ruta termina al gastar todos los puntos o al entrar en una
        ubicación. La ubicación de origen solo actúa como inicio y puede tener
        varias salidas; nunca se puede volver a ella durante el movimiento.
        """
        self._validar_posicion(origen)
        if not isinstance(puntos, int) or isinstance(puntos, bool) or not 1 <= puntos <= 6:
            raise ValueError("Los puntos de movimiento deben estar entre 1 y 6.")
        rutas: list[Ruta] = []

        def recorrer(
            actual: str,
            posiciones: tuple[str, ...],
            conexiones: tuple[str, ...],
            visitadas: frozenset[str],
        ) -> None:
            usados = len(posiciones)
            entro = usados > 0 and self.es_ubicacion(actual)
            if entro or usados == puntos:
                rutas.append(
                    Ruta(
                        origen,
                        actual,
                        posiciones,
                        conexiones,
                        usados,
                        entro,
                    )
                )
                return
            for vecino, conexion in self._adyacencia[actual]:
                if vecino not in visitadas:
                    recorrer(
                        vecino,
                        posiciones + (vecino,),
                        conexiones + (conexion,),
                        visitadas | {vecino},
                    )

        recorrer(origen, (), (), frozenset({origen}))
        return rutas

    def destinos_alcanzables(self, origen: str, puntos: int) -> frozenset[str]:
        return frozenset(ruta.destino for ruta in self.rutas_legales(origen, puntos))

    def validar_movimiento(
        self,
        origen: str,
        destino: str,
        puntos: int,
        posiciones: tuple[str, ...] | list[str] | None = None,
    ) -> bool:
        """Reconstruye la legalidad; opcionalmente valida la ruta completa."""
        try:
            rutas = self.rutas_legales(origen, puntos)
        except ValueError:
            return False
        if posiciones is None:
            return any(ruta.destino == destino for ruta in rutas)
        propuesta = tuple(posiciones)
        return any(
            ruta.destino == destino and ruta.posiciones == propuesta for ruta in rutas
        )

    def destinos_pasadizo(self, origen: str) -> tuple[str, ...]:
        if not self.es_ubicacion(origen):
            return ()
        destinos = []
        for pasadizo in self.pasadizos.values():
            if pasadizo.origen == origen:
                destinos.append(pasadizo.destino)
            elif pasadizo.destino == origen:
                destinos.append(pasadizo.origen)
        return tuple(destinos)

    def usar_pasadizo(self, origen: str, destino: str) -> str:
        """Movimiento especial directo; no tira dado ni admite continuación."""
        self._validar_posicion(origen)
        if destino not in self.destinos_pasadizo(origen):
            raise ValueError("Ese pasadizo no puede utilizarse desde esta posición.")
        return destino


class PosicionesParticipantes:
    """Una única posición lógica por participante, sin reglas de ocupación."""

    def __init__(self, tablero: Tablero):
        self.tablero = tablero
        self._posiciones: dict[str, str] = {}

    def asignar(self, participante_id: str, posicion: str) -> None:
        self.tablero._validar_posicion(posicion)
        self._posiciones[participante_id] = posicion

    def obtener(self, participante_id: str) -> str | None:
        return self._posiciones.get(participante_id)


TABLERO = Tablero()
