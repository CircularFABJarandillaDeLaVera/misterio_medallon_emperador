"""Manifiesto único de recursos visuales servidos por la aplicación.

Los originales viven en ``recursos/`` y no se sirven directamente. Las rutas
runtime usan exclusivamente IDs canónicos, minúsculas ASCII y nombres
sensibles a mayúsculas compatibles con Linux.
"""
from __future__ import annotations

from app.datos.jarandilla import LUGARES, OBJETOS, SOSPECHOSOS

URL_IMG = "/static/img"
RECURSO_PEON = f"{URL_IMG}/personajes/peon.svg"

# Correspondencia canónica explícita ID de ubicación -> imagen de tablero.
# Las claves son IDs del juego; los valores, rutas runtime. Nunca al revés.
IMAGEN_TABLERO_POR_ID = {
    "parador": f"{URL_IMG}/lugares/tablero_parador.png",
    "iglesia-san-agustin": f"{URL_IMG}/lugares/tablero_iglesia_san_agustin.png",
    "ermita-sopetran": f"{URL_IMG}/lugares/tablero_ermita_sopetran.png",
    "picota": f"{URL_IMG}/lugares/tablero_picota.png",
    "plaza-constitucion": f"{URL_IMG}/lugares/tablero_plaza_constitucion.png",
    "cristo-humilladero": f"{URL_IMG}/lugares/tablero_cristo_humilladero.png",
    "puente-parral": f"{URL_IMG}/lugares/tablero_puente_parral.png",
    "museo-escobazos": f"{URL_IMG}/lugares/tablero_museo_escobazos.png",
    "nuestra-senora-torre": f"{URL_IMG}/lugares/tablero_nuestra_senora_torre.png",
}
COLORES_PERSONAJES = {
    "vera": "#6f42a5",
    "bruno": "#3f4448",
    "lucia": "#285943",
    "alvaro": "#176b73",
    "mateo": "#c49324",
    "eulalia": "#b33a2f",
}
PERSONAJES_CON_NOMBRE = frozenset(
    {"alvaro", "bruno", "eulalia", "lucia", "mateo", "vera"}
)
EXTENSIONES_NOMBRE = {"eulalia": "jpeg"}


def _entrada(carta: dict, carpeta: str, extension: str) -> dict:
    entrada = {
        "categoria": carta["categoria"],
        "principal": f"{URL_IMG}/{carpeta}/{carta['id']}.{extension}",
    }
    if carta["id"] in PERSONAJES_CON_NOMBRE:
        extension_nombre = EXTENSIONES_NOMBRE.get(carta["id"], extension)
        entrada["nombre"] = (
            f"{URL_IMG}/{carpeta}/{carta['id']}-nombre.{extension_nombre}"
        )
    if carta["id"] in IMAGEN_TABLERO_POR_ID:
        entrada["tablero"] = IMAGEN_TABLERO_POR_ID[carta["id"]]
    return entrada


RECURSOS_VISUALES = {
    **{c["id"]: _entrada(c, "personajes", "png") for c in SOSPECHOSOS},
    **{c["id"]: _entrada(c, "lugares", "jpeg") for c in LUGARES},
    **{c["id"]: _entrada(c, "objetos", "jpeg") for c in OBJETOS},
}

RECURSO_TABLERO = f"{URL_IMG}/tablero/tablero.png"


def recurso_visual(carta_id: str) -> dict | None:
    """Resuelve un ID canónico sin depender del nombre visible."""
    recurso = RECURSOS_VISUALES.get(carta_id)
    return dict(recurso) if recurso else None
