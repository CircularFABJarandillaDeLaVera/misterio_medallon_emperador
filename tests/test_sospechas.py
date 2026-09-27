from pathlib import Path

import pytest

from app.datos.jarandilla import CARTA_POR_ID
from app.motor.sala import (


    ESTADO_INICIADA,
    INV_VISTA,
    JUGADA_ESPERANDO_REFUTADOR,
    Sala,
)

def cerrar_resultado(sala):
    """8B.31C: el turno avanza al cerrarse la presentacion del resultado.

    No-op si no hay resultado publico pendiente: las aserciones intermedias
    siguen viendo el turno sin avanzar.
    """
    presentacion = getattr(sala, "presentacion_sospecha", None)
    if presentacion and presentacion.get("tipo") == "resultado":
        assert sala.actualizar_presentacion_sospecha(ahora=float("inf"))


def partida():
    sala = Sala("JARA-TEST")
    jugadores = [sala.agregar_jugador(x, i == 0) for i, x in enumerate(("A", "B", "C"))]
    sala.estado = ESTADO_INICIADA
    sala.orden_turnos = [j["id"] for j in jugadores]
    sala.turno_actual = 0
    sala.manos = {
        jugadores[0]["id"]: [CARTA_POR_ID["eulalia"]],
        jugadores[1]["id"]: [CARTA_POR_ID["bruno"]],
        jugadores[2]["id"]: [CARTA_POR_ID[x] for x in ("vera", "puente-parral", "libro-hueco")],
    }
    return sala, jugadores


def completar_presentacion(sala):
    assert sala.actualizar_presentacion_sospecha(ahora=float("inf"))


def test_solo_turno_y_tres_categorias_validas():
    sala, js = partida()
    with pytest.raises(ValueError):
        sala.formular_sospecha(js[1]["id"], "vera", "puente-parral", "libro-hueco")
    for ids in (("inexistente", "puente-parral", "libro-hueco"),
                ("puente-parral", "vera", "libro-hueco"),
                ("vera", "libro-hueco", "puente-parral")):
        with pytest.raises(ValueError):
            sala.formular_sospecha(js[0]["id"], *ids)


def test_busqueda_siguiente_primero_y_circular_sin_investigador():
    sala, js = partida()
    hallado = sala.buscar_refutador(js[0]["id"], {"vera", "bruno"})
    assert hallado == (js[1]["id"], ["bruno"])
    sala.turno_actual = 2
    hallado = sala.buscar_refutador(js[2]["id"], {"bruno"})
    assert hallado == (js[1]["id"], ["bruno"])
    assert sala.buscar_refutador(js[2]["id"], {"vera"}) is None


def test_una_coincidencia_humana_espera_confirmacion_privada_y_avanza_una_vez():
    sala, js = partida()
    sala.formular_sospecha(js[0]["id"], "bruno", "parador", "baul-imperial")
    completar_presentacion(sala)
    assert sala.estado_jugada == JUGADA_ESPERANDO_REFUTADOR
    cerrar_resultado(sala)
    assert sala.turno_actual == 0
    assert [
        carta["id"]
        for carta in sala.estado_privado(js[1]["id"])["jugada"]["opciones_refutacion"]
    ] == ["bruno"]
    assert "opciones_refutacion" not in sala.estado_privado(js[0]["id"])["jugada"]
    assert "opciones_refutacion" not in sala.estado_privado(js[2]["id"])["jugada"]
    assert sala.estado_carta(js[0]["id"], "bruno") != INV_VISTA

    sala.mostrar_carta(js[1]["id"], "bruno")
    cerrar_resultado(sala)
    assert sala.turno_actual == 1
    assert sala.estado_carta(js[0]["id"], "bruno") == INV_VISTA
    assert sala.estado_carta(js[1]["id"], "bruno") != INV_VISTA
    publico = sala.estado_publico()
    assert "carta_id" not in repr(publico)
    assert "carta_mostrada" not in repr(publico["jugada"])
    assert "coincidencias" not in repr(publico["jugada"])
    assert sala.estado_privado(js[0]["id"])["jugada"]["carta_mostrada"]["id"] == "bruno"
    assert "carta_mostrada" not in sala.estado_privado(js[2]["id"])["jugada"]


def test_varias_coincidencias_solo_refutador_recibe_y_elige_opcion():
    sala, js = partida()
    sala.formular_sospecha(js[0]["id"], "vera", "puente-parral", "libro-hueco")
    completar_presentacion(sala)
    assert sala.estado_jugada == JUGADA_ESPERANDO_REFUTADOR
    cerrar_resultado(sala)
    assert sala.turno_actual == 0
    opciones = sala.estado_privado(js[2]["id"])["jugada"]["opciones_refutacion"]
    assert {x["id"] for x in opciones} == {"vera", "puente-parral", "libro-hueco"}
    for j in js[:2]:
        assert "opciones_refutacion" not in sala.estado_privado(j["id"])["jugada"]
    with pytest.raises(ValueError):
        sala.mostrar_carta(js[1]["id"], "vera")
    with pytest.raises(ValueError):
        sala.mostrar_carta(js[2]["id"], "bruno")
    sala.mostrar_carta(js[2]["id"], "vera")
    cerrar_resultado(sala)
    assert sala.turno_actual == 1
    with pytest.raises(ValueError):
        sala.mostrar_carta(js[2]["id"], "puente-parral")
    cerrar_resultado(sala)
    assert sala.turno_actual == 1


def test_nadie_refuta_resultado_publico_y_vuelta_circular():
    sala, js = partida()
    sala.turno_actual = 2
    orden = list(sala.orden_turnos)
    sala.formular_sospecha(js[2]["id"], "alvaro", "parador", "baul-imperial")
    completar_presentacion(sala)
    cerrar_resultado(sala)
    assert sala.turno_actual == 0
    assert sala.orden_turnos == orden
    jugada = sala.estado_publico()["jugada"]
    assert jugada["resultado"] == "sin_refutacion"
    assert "coincidencias" not in repr(jugada)


def test_reconexion_reconstruye_solo_lo_necesario_y_vista_gana_a_descarte():
    sala, js = partida()
    sala.descartes[js[0]["id"]].add("vera")
    sala.formular_sospecha(js[0]["id"], "vera", "puente-parral", "libro-hueco")
    completar_presentacion(sala)
    assert sala.estado_privado(js[0]["id"])["jugada"]["esperando_resolucion"]
    assert "opciones_refutacion" not in sala.estado_privado(js[1]["id"])["jugada"]
    sala.mostrar_carta(js[2]["id"], "vera")
    assert sala.estado_carta(js[0]["id"], "vera") == INV_VISTA
    assert "carta_mostrada" not in sala.estado_privado(js[1]["id"])["jugada"]


def test_confirmar_sospecha_no_es_un_boton_muerto():
    """El fallo era silencioso: el aviso se escribia donde no se ve.

    `#error` vive en el lobby (oculto durante la partida) y CONFIRMAR SOSPECHA
    nacia `disabled`, de modo que un toque se tragaba sin hacer nada ni explicar
    nada. Ahora valida al pulsar y explica dentro del propio selector.
    """
    js = (Path(__file__).resolve().parents[1] / "app/static/js/sala.js").read_text(
        encoding="utf-8"
    )
    bloque = js[
        js.index("function pintarVistaSospecha"):js.index("function pintarPanel")
    ]
    # El aviso se pinta DENTRO del selector, no en el lobby.
    assert 'aviso.className = "error"' in bloque
    assert "modalContextualDetalle.appendChild(aviso)" in bloque
    assert "error.textContent" not in bloque
    # El botón nace habilitado y valida en el clic.
    antes_del_clic = bloque.split("confirmar.addEventListener")[0]
    assert "confirmar.disabled = true;" not in antes_del_clic
    assert "confirmar.disabled = false;" in antes_del_clic
    assert 'accion: "formular_sospecha"' in bloque