from pathlib import Path, PurePosixPath
import re

from fastapi.testclient import TestClient

from app.datos.jarandilla import CARTAS
from app.datos.recursos import (
    PERSONAJES_CON_NOMBRE,
    RECURSOS_VISUALES,
    RECURSO_TABLERO,
    recurso_visual,
)
from app.main import app


RAIZ = Path(__file__).parents[1]
STATIC = RAIZ / "app" / "static"
ID_RUNTIME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def ruta_runtime(url: str) -> Path:
    assert url.startswith("/static/")
    return STATIC / url.removeprefix("/static/")


def test_manifiesto_cubre_exactamente_los_21_ids_canonicos():
    canonicos = {carta["id"] for carta in CARTAS}
    assert len(canonicos) == 21
    assert set(RECURSOS_VISUALES) == canonicos
    assert all(recurso_visual(cid) == RECURSOS_VISUALES[cid] for cid in canonicos)
    assert recurso_visual("id-desconocido") is None


def test_todos_los_recursos_principales_existen_con_case_linux_exacto():
    for carta_id, recurso in RECURSOS_VISUALES.items():
        assert ID_RUNTIME.fullmatch(carta_id)
        ruta = ruta_runtime(recurso["principal"])
        assert ruta.is_file(), recurso["principal"]
        assert ruta.name == ruta.name.lower()
        assert ruta.name.startswith(carta_id + ".")
        assert ruta.suffix in {".png", ".jpeg"}


def test_variantes_nombre_son_opcionales_y_solo_existen_las_reales():
    ids_con_variante = {
        cid for cid, recurso in RECURSOS_VISUALES.items() if "nombre" in recurso
    }
    assert ids_con_variante == PERSONAJES_CON_NOMBRE
    assert ids_con_variante == {"alvaro", "bruno", "lucia", "mateo", "vera"}
    assert "nombre" not in RECURSOS_VISUALES["eulalia"]
    for cid in ids_con_variante:
        ruta = ruta_runtime(RECURSOS_VISUALES[cid]["nombre"])
        assert ruta.is_file()
        assert ruta.name == f"{cid}-nombre.png"


def test_rutas_son_unicas_ascii_minusculas_y_sin_colisiones_de_case():
    rutas = [
        valor
        for recurso in RECURSOS_VISUALES.values()
        for clave, valor in recurso.items()
        if clave in {"principal", "nombre"}
    ] + [RECURSO_TABLERO]
    assert len(rutas) == len(set(rutas))
    assert len(rutas) == len({ruta.casefold() for ruta in rutas})
    for ruta in rutas:
        assert ruta == ruta.lower()
        assert ruta.isascii()
        assert "\\" not in ruta
        assert ".." not in PurePosixPath(ruta).parts
        assert ruta_runtime(ruta).is_file()


def test_extensiones_coinciden_con_firmas_reales():
    for recurso in RECURSOS_VISUALES.values():
        for clave in ("principal", "nombre"):
            if clave not in recurso:
                continue
            ruta = ruta_runtime(recurso[clave])
            cabecera = ruta.read_bytes()[:8]
            if ruta.suffix == ".png":
                assert cabecera == b"\x89PNG\r\n\x1a\n"
            else:
                assert cabecera[:2] == b"\xff\xd8"


def test_api_publica_el_mismo_manifiesto_sin_datos_de_juego_privados():
    respuesta = TestClient(app).get("/api/recursos")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["recursos"] == RECURSOS_VISUALES
    assert datos["tablero"] == RECURSO_TABLERO
    assert "misterio" not in repr(datos).lower()
