"""Datos canónicos del juego (Sprint 2).

21 cartas definitivas con terminología canónica:
SOSPECHOSOS, LUGARES y OBJETOS.

Las cartas no dependen de que existan imágenes.
"""
from __future__ import annotations

CATEGORIA_SOSPECHOSO = "sospechoso"
CATEGORIA_LUGAR = "lugar"
CATEGORIA_OBJETO = "objeto"

SOSPECHOSOS: list[dict] = [
    {"id": "vera", "nombre": "Vera, la fotógrafa", "categoria": CATEGORIA_SOSPECHOSO,
     "color": "morado", "simbolo": "cámara"},
    {"id": "bruno", "nombre": "Bruno, el cantero", "categoria": CATEGORIA_SOSPECHOSO,
     "color": "gris antracita", "simbolo": "maza y cincel"},
    {"id": "lucia", "nombre": "Lucía, la boticaria", "categoria": CATEGORIA_SOSPECHOSO,
     "color": "verde oscuro", "simbolo": "mortero y mano"},
    {"id": "alvaro", "nombre": "Álvaro, el guardabosques", "categoria": CATEGORIA_SOSPECHOSO,
     "color": "azul petróleo", "simbolo": "brújula"},
    {"id": "mateo", "nombre": "Mateo, el escobero", "categoria": CATEGORIA_SOSPECHOSO,
     "color": "amarillo ocre", "simbolo": "escobón tradicional"},
    {"id": "eulalia", "nombre": "Eulalia, la pimentonera", "categoria": CATEGORIA_SOSPECHOSO,
     "color": "rojo pimentón", "simbolo": "pimientos secos"},
]

LUGARES: list[dict] = [
    {"id": "parador", "nombre": "Parador", "categoria": CATEGORIA_LUGAR},
    {"id": "iglesia-san-agustin", "nombre": "Iglesia de San Agustín", "categoria": CATEGORIA_LUGAR},
    {"id": "ermita-sopetran", "nombre": "Ermita de Sopetrán", "categoria": CATEGORIA_LUGAR},
    {"id": "picota", "nombre": "La Picota", "categoria": CATEGORIA_LUGAR},
    {"id": "plaza-constitucion", "nombre": "Plaza de la Constitución", "categoria": CATEGORIA_LUGAR},
    {"id": "cristo-humilladero", "nombre": "Cristo del Humilladero", "categoria": CATEGORIA_LUGAR},
    {"id": "puente-parral", "nombre": "Puente Parral", "categoria": CATEGORIA_LUGAR},
    {"id": "museo-escobazos", "nombre": "Museo de los Escobazos", "categoria": CATEGORIA_LUGAR},
    {"id": "nuestra-senora-torre", "nombre": "Ntra. Sra. de la Torre", "categoria": CATEGORIA_LUGAR},
]

OBJETOS: list[dict] = [
    {"id": "baul-imperial", "nombre": "Baúl imperial", "categoria": CATEGORIA_OBJETO},
    {"id": "cantaro-barro", "nombre": "Cántaro de barro", "categoria": CATEGORIA_OBJETO},
    {"id": "saco-pimenton", "nombre": "Saco de pimentón", "categoria": CATEGORIA_OBJETO},
    {"id": "zurron-cuero", "nombre": "Zurrón de cuero", "categoria": CATEGORIA_OBJETO},
    {"id": "caja-herramientas", "nombre": "Caja de herramientas", "categoria": CATEGORIA_OBJETO},
    {"id": "libro-hueco", "nombre": "Libro hueco", "categoria": CATEGORIA_OBJETO},
]

CARTAS: list[dict] = SOSPECHOSOS + LUGARES + OBJETOS

CARTA_POR_ID: dict[str, dict] = {carta["id"]: carta for carta in CARTAS}
