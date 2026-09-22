"""Pruebas de la Microfase 3B: hoja de investigación privada."""
import json

import pytest
from fastapi.testclient import TestClient

from app.datos.jarandilla import CARTAS
from app.main import app, conexiones, gestor

cliente = TestClient(app)

PERSONAJES = ["vera", "bruno", "lucia", "alvaro", "mateo", "eulalia"]


def setup_function(_):
    gestor.salas.clear()
    conexiones.clear()


def crear_sala_con(alias_list):
    sala, anfitrion = gestor.crear_sala(alias_list[0])
    jugadores = [anfitrion]
    for alias in alias_list[1:]:
        _, jugador = gestor.unirse(sala.codigo, alias)
        jugadores.append(jugador)
    return sala, jugadores


def iniciar_con_personajes(sala, jugadores):
    for jugador, pid in zip(jugadores, PERSONAJES):
        sala.elegir_personaje(jugador["id"], pid)
    sala.iniciar(jugadores[0]["id"])


def carta_ajena(sala, jugador):
    mias = {c["id"] for c in sala.manos[jugador["id"]]}
    for carta in CARTAS:
        if carta["id"] not in mias:
            return carta["id"]
    raise AssertionError("siempre hay cartas ajenas con 18 repartidas")


# 1. La hoja contiene las 21 cartas canónicas.
def test_hoja_con_21_cartas_canonicas():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    iniciar_con_personajes(sala, jugadores)
    hoja = sala.hoja_investigacion(jugadores[0]["id"])
    assert [e["id"] for e in hoja] == [c["id"] for c in CARTAS]
    assert [e["categoria"] for e in hoja] == [c["categoria"] for c in CARTAS]
    assert (
        sum(1 for e in hoja if e["categoria"] == "sospechoso") == 6
    )
    assert sum(1 for e in hoja if e["categoria"] == "lugar") == 9
    assert sum(1 for e in hoja if e["categoria"] == "objeto") == 6
    assert "armas" not in json.dumps(hoja)


# 2. Las cartas propias aparecen como LA TENGO.
def test_cartas_propias_como_la_tengo():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    iniciar_con_personajes(sala, jugadores)
    hoja = {
        e["id"]: e["estado"]
        for e in sala.hoja_investigacion(jugadores[0]["id"])
    }
    mias = {c["id"] for c in sala.manos[jugadores[0]["id"]]}
    assert len(mias) == 6
    for cid in mias:
        assert hoja[cid] == "la_tengo"


# 3. Una carta ajena empieza como SIN INFORMACIÓN.
def test_carta_ajena_empieza_sin_informacion():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    iniciar_con_personajes(sala, jugadores)
    ajena = carta_ajena(sala, jugadores[0])
    assert sala.estado_carta(jugadores[0]["id"], ajena) == "sin_informacion"


# 4. Se puede marcar una carta como DESCARTADA.
def test_marcar_descartada():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    iniciar_con_personajes(sala, jugadores)
    ajena = carta_ajena(sala, jugadores[0])
    entrada = sala.marcar_investigacion(jugadores[0]["id"], ajena, "descartada")
    assert entrada["estado"] == "descartada"
    assert sala.estado_carta(jugadores[0]["id"], ajena) == "descartada"


# 5. Se puede devolver DESCARTADA a SIN INFORMACIÓN.
def test_devolver_descartada_a_sin_informacion():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    iniciar_con_personajes(sala, jugadores)
    ajena = carta_ajena(sala, jugadores[0])
    sala.marcar_investigacion(jugadores[0]["id"], ajena, "descartada")
    entrada = sala.marcar_investigacion(
        jugadores[0]["id"], ajena, "sin_informacion"
    )
    assert entrada["estado"] == "sin_informacion"


# 6. No se puede modificar una carta propia.
def test_no_modificar_carta_propia():
    sala, jugadores = propia = crear_sala_con(["Paco", "Ana", "Luis"])
    iniciar_con_personajes(sala, jugadores)
    propia_id = sala.manos[jugadores[0]["id"]][0]["id"]
    with pytest.raises(ValueError):
        sala.marcar_investigacion(jugadores[0]["id"], propia_id, "descartada")
    assert sala.estado_carta(jugadores[0]["id"], propia_id) == "la_tengo"


# 7. No se puede marcar manualmente LA TENGO.
def test_no_marcar_la_tengo_manualmente():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    iniciar_con_personajes(sala, jugadores)
    ajena = carta_ajena(sala, jugadores[0])
    with pytest.raises(ValueError):
        sala.marcar_investigacion(jugadores[0]["id"], ajena, "la_tengo")


# 8. No se puede marcar manualmente VISTA.
def test_no_marcar_vista_manualmente():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    iniciar_con_personajes(sala, jugadores)
    ajena = carta_ajena(sala, jugadores[0])
    with pytest.raises(ValueError):
        sala.marcar_investigacion(jugadores[0]["id"], ajena, "vista")
    assert sala.estado_carta(jugadores[0]["id"], ajena) == "sin_informacion"


# 9. No se acepta un estado arbitrario.
def test_estado_arbitrario_rechazado():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    iniciar_con_personajes(sala, jugadores)
    ajena = carta_ajena(sala, jugadores[0])
    with pytest.raises(ValueError):
        sala.marcar_investigacion(jugadores[0]["id"], ajena, "posible_misterio")


# 10. No se acepta un carta_id inexistente.
def test_carta_inexistente_rechazada():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    iniciar_con_personajes(sala, jugadores)
    with pytest.raises(ValueError):
        sala.marcar_investigacion(
            jugadores[0]["id"], "napoleon", "descartada"
        )


# 11. Un jugador no modifica la hoja de otro.
def test_hojas_independientes_entre_jugadores():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    iniciar_con_personajes(sala, jugadores)
    # Carta que Paco no tiene pero Ana sí (si existe); si no, carta ajena
    # a ambos: en todo caso debe existir una carta descartable por Paco
    # que no altere la hoja de Ana salvo que Ana la tenga (LA TENGO).
    ajena_paco = carta_ajena(sala, jugadores[0])
    sala.marcar_investigacion(jugadores[0]["id"], ajena_paco, "descartada")
    hoja_ana = {
        e["id"]: e["estado"]
        for e in sala.hoja_investigacion(jugadores[1]["id"])
    }
    if ajena_paco in {c["id"] for c in sala.manos[jugadores[1]["id"]]}:
        assert hoja_ana[ajena_paco] == "la_tengo"
    else:
        assert hoja_ana[ajena_paco] == "sin_informacion"


# 12. estado_publico() no contiene investigación privada.
def test_publico_sin_investigacion():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    iniciar_con_personajes(sala, jugadores)
    sala.marcar_investigacion(
        jugadores[0]["id"], carta_ajena(sala, jugadores[0]), "descartada"
    )
    texto = json.dumps(sala.estado_publico())
    assert "investigacion" not in texto
    assert "descartada" not in texto
    assert "sin_informacion" not in texto


# 13. estado_privado(A) no contiene la investigación de B.
def test_privado_sin_hoja_ajena():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    iniciar_con_personajes(sala, jugadores)
    ajena_b = carta_ajena(sala, jugadores[1])
    sala.marcar_investigacion(jugadores[1]["id"], ajena_b, "descartada")
    privado_a = sala.estado_privado(jugadores[0]["id"])
    hoja_a = {e["id"]: e["estado"] for e in privado_a["investigacion"]}
    mias_a = {c["id"] for c in sala.manos[jugadores[0]["id"]]}
    if ajena_b in mias_a:
        assert hoja_a[ajena_b] == "la_tengo"
    else:
        assert hoja_a[ajena_b] == "sin_informacion"
    # Su propia marca sí aparece en su privado.
    privado_b = sala.estado_privado(jugadores[1]["id"])
    assert {
        e["id"]: e["estado"] for e in privado_b["investigacion"]
    }[ajena_b] == "descartada"


# 14. La hoja privada no expone el misterio.
def test_hoja_no_expone_misterio():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    iniciar_con_personajes(sala, jugadores)
    secreto = {
        sala.misterio["sospechoso"]["id"],
        sala.misterio["lugar"]["id"],
        sala.misterio["objeto"]["id"],
    }
    for jugador in jugadores:
        hoja = sala.hoja_investigacion(jugador["id"])
        mias = {c["id"] for c in sala.manos[jugador["id"]]}
        for entrada in hoja:
            if entrada["id"] in secreto - mias:
                assert entrada["estado"] == "sin_informacion"
        assert "misterio" not in json.dumps(hoja)


# 15. Las marcas sobreviven a la reconexión (WS + estado privado).
def test_marcas_sobreviven_reconexion_ws():
    sala = cliente.post("/api/partidas", json={"alias": "Paco"}).json()
    ana = cliente.post(
        f"/api/partidas/{sala['codigo']}/unirse", json={"alias": "Ana"}
    ).json()
    luis = cliente.post(
        f"/api/partidas/{sala['codigo']}/unirse", json={"alias": "Luis"}
    ).json()
    codigo = sala["codigo"]
    srv = gestor.obtener(codigo)
    srv.elegir_personaje(sala["jugador_id"], "bruno")
    srv.elegir_personaje(ana["jugador_id"], "vera")
    srv.elegir_personaje(luis["jugador_id"], "lucia")

    with cliente.websocket_connect(f"/ws/{codigo}/{sala['jugador_id']}") as ws:
        ws.receive_json()
        ws.send_json({"accion": "iniciar"})
        privado = ws.receive_json()["sala"]
        mias = {c["id"] for c in privado["mis_cartas"]}
        ajena = next(c["id"] for c in CARTAS if c["id"] not in mias)
        ws.send_json(
            {
                "accion": "marcar_investigacion",
                "carta_id": ajena,
                "estado": "descartada",
            }
        )
        actualizado = ws.receive_json()["sala"]
        assert {
            e["id"]: e["estado"] for e in actualizado["investigacion"]
        }[ajena] == "descartada"
    # Reconexión con el mismo jugador_id conserva la marca.
    with cliente.websocket_connect(f"/ws/{codigo}/{sala['jugador_id']}") as ws2:
        rec = ws2.receive_json()["sala"]
        assert {
            e["id"]: e["estado"] for e in rec["investigacion"]
        }[ajena] == "descartada"
        assert {c["id"] for c in rec["mis_cartas"]} == mias


# 16. Las marcas no alteran mano, personaje, orden ni turno.
def test_marcas_no_alteran_resto_del_estado():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    iniciar_con_personajes(sala, jugadores)
    antes_mano = [c["id"] for c in sala.manos[jugadores[0]["id"]]]
    antes_personaje = jugadores[0]["personaje_id"]
    antes_orden = list(sala.orden_turnos)
    sala.marcar_investigacion(
        jugadores[0]["id"], carta_ajena(sala, jugadores[0]), "descartada"
    )
    assert [c["id"] for c in sala.manos[jugadores[0]["id"]]] == antes_mano
    assert jugadores[0]["personaje_id"] == antes_personaje
    assert sala.orden_turnos == antes_orden
    assert sala.turno_actual == 0


# 17. Solo se puede marcar una vez iniciada la partida.
def test_no_marcar_antes_de_iniciar():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    sala.elegir_personaje(jugadores[0]["id"], "bruno")
    with pytest.raises(ValueError):
        sala.marcar_investigacion(jugadores[0]["id"], "vera", "descartada")
    # Por WS también responde error.
    datos = cliente.post("/api/partidas", json={"alias": "Solo"}).json()
    codigo = datos["codigo"]
    with cliente.websocket_connect(
        f"/ws/{codigo}/{datos['jugador_id']}"
    ) as ws:
        ws.receive_json()
        ws.send_json(
            {
                "accion": "marcar_investigacion",
                "carta_id": "vera",
                "estado": "descartada",
            }
        )
        assert ws.receive_json()["tipo"] == "error"


# 19. La hoja del estado privado se agrupa como el frontend: 6/9/6.
def test_hoja_agrupable_6_9_6_como_el_frontend():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    iniciar_con_personajes(sala, jugadores)
    for jugador in jugadores:
        hoja = sala.estado_privado(jugador["id"])["investigacion"]
        # Misma agrupación que pintarHoja() en sala.js.
        grupos = {"sospechoso": 0, "lugar": 0, "objeto": 0}
        for entrada in hoja:
            grupos[entrada["categoria"]] += 1
        assert grupos == {"sospechoso": 6, "lugar": 9, "objeto": 6}
        assert len(hoja) == 21
        for entrada in hoja:
            assert set(entrada.keys()) == {"id", "nombre", "categoria", "estado"}


# 20. El servidor sirve el esqueleto de la hoja (HTML + JS con pintarHoja).
def test_esqueleto_hoja_servido_en_html_y_js():
    sala, _ = crear_sala_con(["Paco", "Ana", "Luis"])
    pagina = cliente.get(f"/sala/{sala.codigo}")
    assert pagina.status_code == 200
    html = pagina.text
    for aguja in (
        'id="hoja"',
        'id="modal-hoja"',
        'id="btn-ver-hoja"',
        'id="btn-cerrar-hoja"',
    ):
        assert aguja in html
    js = cliente.get("/static/js/sala.js")
    assert js.status_code == 200
    assert "function pintarHoja" in js.text
    assert "marcar_investigacion" in js.text


# 18. WS: errores no filtran secreto y la marca solo llega al autor.
def test_ws_privacidad_marcas_y_errores():
    sala = cliente.post("/api/partidas", json={"alias": "Paco"}).json()
    ana = cliente.post(
        f"/api/partidas/{sala['codigo']}/unirse", json={"alias": "Ana"}
    ).json()
    luis = cliente.post(
        f"/api/partidas/{sala['codigo']}/unirse", json={"alias": "Luis"}
    ).json()
    codigo = sala["codigo"]
    srv = gestor.obtener(codigo)
    srv.elegir_personaje(sala["jugador_id"], "bruno")
    srv.elegir_personaje(ana["jugador_id"], "vera")
    srv.elegir_personaje(luis["jugador_id"], "lucia")

    with cliente.websocket_connect(f"/ws/{codigo}/{sala['jugador_id']}") as a:
        with cliente.websocket_connect(f"/ws/{codigo}/{ana['jugador_id']}") as b:
            a.receive_json()
            b.receive_json()
            a.send_json({"accion": "iniciar"})
            pa = a.receive_json()
            pb = b.receive_json()
            assert pa["sala"]["estado"] == "iniciada"
            mias_a = {c["id"] for c in pa["sala"]["mis_cartas"]}
            ajena = next(c["id"] for c in CARTAS if c["id"] not in mias_a)
            # Marcar carta propia por WS -> error sin secreto.
            propia = next(iter(mias_a))
            a.send_json(
                {
                    "accion": "marcar_investigacion",
                    "carta_id": propia,
                    "estado": "descartada",
                }
            )
            err = a.receive_json()
            assert err["tipo"] == "error"
            assert "misterio" not in json.dumps(err)
            # Marca válida: solo el autor recibe el privado actualizado.
            a.send_json(
                {
                    "accion": "marcar_investigacion",
                    "carta_id": ajena,
                    "estado": "descartada",
                }
            )
            actualizado = a.receive_json()
            assert actualizado["tipo"] == "estado_privado"
            assert {
                e["id"]: e["estado"]
                for e in actualizado["sala"]["investigacion"]
            }[ajena] == "descartada"
            # B recibió su privado al iniciar (antes de la marca de A):
            # su hoja no refleja el descarte de A (salvo LA TENGO propia).
            hoja_b = {
                e["id"]: e["estado"] for e in pb["sala"]["investigacion"]
            }
            mias_b = {c["id"] for c in pb["sala"]["mis_cartas"]}
            esperado_b = "la_tengo" if ajena in mias_b else "sin_informacion"
            assert hoja_b[ajena] == esperado_b
