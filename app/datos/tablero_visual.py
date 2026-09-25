"""Proyección pública de presentación del tablero lógico.

Las coordenadas no expresan reglas. Caminos, casillas y pasadizos se derivan
siempre de ``TABLERO`` para que la vista no mantenga una segunda topología.
"""
from __future__ import annotations

import math

from app.datos.recursos import (
    COLORES_PERSONAJES,
    IMAGEN_TABLERO_POR_ID,
    RECURSOS_VISUALES,
    RECURSO_PEON,
)
from app.motor.tablero import CENTRO_ID, EXTERIORES, TABLERO


CENTRO = (50.0, 50.0)
RADIO_ANILLO = 39.0
RADIO_UBICACION_EXTERIOR = 7.0
LONGITUD_CAMINO_VISIBLE = (
    2 * RADIO_ANILLO * math.sin(math.pi / 8)
    - 2 * RADIO_UBICACION_EXTERIOR
)
RADIO_UBICACION_CENTRAL = (
    RADIO_ANILLO - RADIO_UBICACION_EXTERIOR - LONGITUD_CAMINO_VISIBLE
)

COORDENADAS_UBICACIONES = {
    ubicacion_id: (
        round(CENTRO[0] + RADIO_ANILLO * math.cos(math.radians(-90 + 45 * i)), 3),
        round(CENTRO[1] + RADIO_ANILLO * math.sin(math.radians(-90 + 45 * i)), 3),
    )
    for i, ubicacion_id in enumerate(EXTERIORES)
}
COORDENADAS_UBICACIONES[CENTRO_ID] = CENTRO

RADIOS_UBICACIONES = {
    ubicacion_id: RADIO_UBICACION_EXTERIOR for ubicacion_id in EXTERIORES
}
RADIOS_UBICACIONES[CENTRO_ID] = RADIO_UBICACION_CENTRAL


def _interpolar(origen: tuple[float, float], destino: tuple[float, float], paso: int):
    proporcion = paso / 4
    return (
        round(origen[0] + (destino[0] - origen[0]) * proporcion, 3),
        round(origen[1] + (destino[1] - origen[1]) * proporcion, 3),
    )


def _extremos_visibles(origen_id: str, destino_id: str):
    origen = COORDENADAS_UBICACIONES[origen_id]
    destino = COORDENADAS_UBICACIONES[destino_id]
    dx, dy = destino[0] - origen[0], destino[1] - origen[1]
    distancia = math.hypot(dx, dy)
    ux, uy = dx / distancia, dy / distancia
    radio_origen = RADIOS_UBICACIONES[origen_id]
    radio_destino = RADIOS_UBICACIONES[destino_id]
    inicio = (
        round(origen[0] + ux * radio_origen, 3),
        round(origen[1] + uy * radio_origen, 3),
    )
    fin = (
        round(destino[0] - ux * radio_destino, 3),
        round(destino[1] - uy * radio_destino, 3),
    )
    return inicio, fin


def descripcion_tablero_visual() -> dict:
    """Devuelve geometría pública, sin estado de partida ni datos privados."""
    nodos = {}
    for ubicacion_id, ubicacion in TABLERO.ubicaciones.items():
        x, y = COORDENADAS_UBICACIONES[ubicacion_id]
        nodos[ubicacion_id] = {
            "id": ubicacion_id,
            "tipo": "ubicacion",
            "nombre": ubicacion["nombre"],
            "x": x,
            "y": y,
            "diametro": round(RADIOS_UBICACIONES[ubicacion_id] * 2, 3),
            # Tarjeta completa (modal HTML) e imagen de tablero (Canvas):
            # dos recursos distintos para la misma ubicación canónica.
            "imagen_tarjeta": RECURSOS_VISUALES[ubicacion_id]["principal"],
            "imagen_tablero": IMAGEN_TABLERO_POR_ID[ubicacion_id],
        }

    caminos = []
    for camino in TABLERO.caminos.values():
        origen_xy, destino_xy = _extremos_visibles(camino.origen, camino.destino)
        origen_nombre = TABLERO.ubicaciones[camino.origen]["nombre"]
        destino_nombre = TABLERO.ubicaciones[camino.destino]["nombre"]
        for indice, casilla_id in enumerate(camino.casillas, start=1):
            x, y = _interpolar(origen_xy, destino_xy, indice)
            nodos[casilla_id] = {
                "id": casilla_id,
                "tipo": "casilla",
                "nombre": (
                    f"Casilla {indice}: {origen_nombre} — {destino_nombre}"
                ),
                "x": x,
                "y": y,
            }
        caminos.append({
            "id": camino.id,
            "nodos": [camino.origen, *camino.casillas, camino.destino],
            "inicio": {"x": origen_xy[0], "y": origen_xy[1]},
            "fin": {"x": destino_xy[0], "y": destino_xy[1]},
        })

    pasadizos = [
        {"id": pasadizo.id, "origen": pasadizo.origen, "destino": pasadizo.destino}
        for pasadizo in TABLERO.pasadizos.values()
    ]
    return {
        "nodos": list(nodos.values()),
        "caminos": caminos,
        "pasadizos": pasadizos,
        "peon": RECURSO_PEON,
        "colores_personajes": dict(COLORES_PERSONAJES),
    }


TABLERO_VISUAL = descripcion_tablero_visual()
