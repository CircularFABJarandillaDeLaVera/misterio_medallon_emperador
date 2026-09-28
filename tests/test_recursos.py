from pathlib import Path, PurePosixPath
import re

from fastapi.testclient import TestClient

from app.datos.jarandilla import CARTAS
from app.datos.recursos import (
    AUDIO_CLIC,
    AUDIO_FINAL,
    AUDIO_MUSICA_FONDO,
    COLORES_PERSONAJES,
    PERSONAJES_CON_NOMBRE,
    RECURSOS_VISUALES,
    RECURSO_PEON,
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


def test_los_seis_personajes_tienen_variante_nombre():
    ids_con_variante = {
        cid for cid, recurso in RECURSOS_VISUALES.items() if "nombre" in recurso
    }
    assert ids_con_variante == PERSONAJES_CON_NOMBRE
    assert ids_con_variante == {
        "alvaro",
        "bruno",
        "eulalia",
        "lucia",
        "mateo",
        "vera",
    }
    for cid in ids_con_variante:
        ruta = ruta_runtime(RECURSOS_VISUALES[cid]["nombre"])
        assert ruta.is_file()
        extension = "jpeg" if cid == "eulalia" else "png"
        assert ruta.name == f"{cid}-nombre.{extension}"


def test_rutas_son_unicas_ascii_minusculas_y_sin_colisiones_de_case():
    rutas = [
        valor
        for recurso in RECURSOS_VISUALES.values()
        for clave, valor in recurso.items()
        if clave in {"principal", "nombre", "tablero"}
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
        for clave in ("principal", "nombre", "tablero"):
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
    assert datos["peon"] == RECURSO_PEON
    assert datos["colores_personajes"] == COLORES_PERSONAJES
    assert "misterio" not in repr(datos).lower()


def test_peon_svg_canonico_runtime_es_copia_unica_recoloreable():
    original = RAIZ / "recursos" / "personajes" / "peon.svg"
    runtime = ruta_runtime(RECURSO_PEON)
    assert original.is_file() and runtime.is_file()
    assert original.read_bytes() == runtime.read_bytes()
    contenido = runtime.read_text(encoding="utf-8")
    assert contenido.count("<svg") == 1
    assert "currentColor" in contenido
    assert set(COLORES_PERSONAJES) == {
        "vera", "bruno", "lucia", "alvaro", "mateo", "eulalia"
    }


def test_musica_fondo_runtime_es_copia_byte_a_byte_del_original():
    """8B.33: `recursos/` es la fuente canonica y el runtime una copia
    integra: ni se renombra, ni se recomprime, ni se sirve el original."""
    original = RAIZ / "recursos" / "sonidos" / "musica_fondo.mp3"
    runtime = ruta_runtime(AUDIO_MUSICA_FONDO)
    assert original.is_file() and runtime.is_file()
    assert original.read_bytes() == runtime.read_bytes()
    assert AUDIO_MUSICA_FONDO == "/static/audio/musica_fondo.mp3"
    assert ruta_runtime(AUDIO_MUSICA_FONDO).name == ruta_runtime(
        AUDIO_MUSICA_FONDO
    ).name.lower()


def test_efectos_runtime_son_copias_byte_a_byte_del_original():
    """8B.33B: clic y final siguen exactamente el patron de musica_fondo."""
    for constante, nombre in ((AUDIO_CLIC, "clic"), (AUDIO_FINAL, "final")):
        original = RAIZ / "recursos" / "sonidos" / f"{nombre}.mp3"
        runtime = ruta_runtime(constante)
        assert original.is_file(), original
        assert runtime.is_file(), constante
        assert constante == f"/static/audio/{nombre}.mp3"
        assert original.read_bytes() == runtime.read_bytes()
        # MP3 real: sin recomprimir y con la firma del contenedor.
        cabecera = runtime.read_bytes()[:2]
        assert cabecera in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"ID"}


def test_api_publica_el_audio_y_sirve_los_mp3_sin_tocar_los_originales():
    cliente = TestClient(app)
    datos = cliente.get("/api/recursos").json()
    assert datos["audio"] == {
        "musica_fondo": AUDIO_MUSICA_FONDO,
        "clic": AUDIO_CLIC,
        "final": AUDIO_FINAL,
    }
    assert "misterio" not in repr(datos).lower()
    for constante in (AUDIO_MUSICA_FONDO, AUDIO_CLIC, AUDIO_FINAL):
        respuesta = cliente.get(constante)
        assert respuesta.status_code == 200, constante
        assert respuesta.headers["content-type"].startswith("audio/mpeg")
        nombre = Path(constante).name
        original = RAIZ / "recursos" / "sonidos" / nombre
        assert respuesta.content == original.read_bytes()
