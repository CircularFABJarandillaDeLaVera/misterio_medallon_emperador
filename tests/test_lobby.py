"""Pruebas básicas de las reglas del lobby (Sprint 1)."""
from fastapi.testclient import TestClient

from app.main import app, conexiones, gestor

cliente = TestClient(app)


def setup_function(_):
    gestor.salas.clear()
    conexiones.clear()


def crear(alias="Paco"):
    respuesta = cliente.post("/api/partidas", json={"alias": alias})
    assert respuesta.status_code == 200
    return respuesta.json()


def test_crear_sala_genera_codigo_y_anfitrion():
    datos = crear("Paco")
    assert datos["codigo"].startswith("JARA-")
    assert datos["alias"] == "Paco"
    sala = gestor.obtener(datos["codigo"])
    assert sala.estado == "esperando"
    assert sala.jugadores[0]["es_anfitrion"] is True


def test_no_permite_alias_vacio_al_crear():
    respuesta = cliente.post("/api/partidas", json={"alias": "   "})
    assert respuesta.status_code == 400


def test_no_entrar_en_sala_inexistente():
    respuesta = cliente.post("/api/partidas/JARA-ZZZZ/unirse", json={"alias": "Ana"})
    assert respuesta.status_code == 404


def test_no_permite_alias_vacio_al_unirse():
    datos = crear()
    respuesta = cliente.post(f"/api/partidas/{datos['codigo']}/unirse", json={"alias": "  "})
    assert respuesta.status_code == 400


def test_evita_alias_duplicado_en_la_misma_sala():
    datos = crear("Paco")
    respuesta = cliente.post(
        f"/api/partidas/{datos['codigo']}/unirse", json={"alias": "paco"}
    )
    assert respuesta.status_code == 400


def test_unirse_actualiza_lista_de_jugadores():
    datos = crear("Paco")
    respuesta = cliente.post(
        f"/api/partidas/{datos['codigo']}/unirse", json={"alias": "Ana"}
    )
    assert respuesta.status_code == 200
    estado = cliente.get(f"/api/partidas/{datos['codigo']}").json()["sala"]
    assert [j["alias"] for j in estado["jugadores"]] == ["Paco", "Ana"]


def test_solo_anfitrion_puede_iniciar_y_cambia_estado():
    datos = crear("Paco")
    unida = cliente.post(
        f"/api/partidas/{datos['codigo']}/unirse", json={"alias": "Ana"}
    ).json()
    luis = cliente.post(
        f"/api/partidas/{datos['codigo']}/unirse", json={"alias": "Luis"}
    ).json()
    codigo = datos["codigo"]
    sala = gestor.obtener(codigo)
    sala.elegir_personaje(datos["jugador_id"], "bruno")
    sala.elegir_personaje(unida["jugador_id"], "vera")
    sala.elegir_personaje(luis["jugador_id"], "lucia")

    # La no anfitriona intenta iniciar -> recibe error por WS.
    # (Ambas conexiones se mantienen abiertas a la vez para no vaciar el lobby.)
    with cliente.websocket_connect(f"/ws/{codigo}/{unida['jugador_id']}") as ws_ana:
        with cliente.websocket_connect(
            f"/ws/{codigo}/{datos['jugador_id']}"
        ) as ws_paco:
            ws_ana.receive_json()  # estado inicial
            ws_paco.receive_json()
            ws_ana.send_json({"accion": "iniciar"})
            mensaje = ws_ana.receive_json()
            assert mensaje["tipo"] == "error"
            assert gestor.obtener(codigo).estado == "esperando"

            # El anfitrión inicia -> cambia a iniciada y recibe sus cartas.
            ws_paco.send_json({"accion": "iniciar"})
            mensaje = ws_paco.receive_json()
            assert mensaje["tipo"] == "estado_privado"
            assert mensaje["sala"]["estado"] == "iniciada"
            assert len(mensaje["sala"]["mis_cartas"]) == 6  # 3 jugadores: 6/6/6


def test_sincronizacion_ws_llega_a_todos():
    datos = crear("Paco")
    codigo = datos["codigo"]
    with cliente.websocket_connect(f"/ws/{codigo}/{datos['jugador_id']}") as ws_paco:
        ws_paco.receive_json()
        cliente.post(f"/api/partidas/{codigo}/unirse", json={"alias": "Luis"})
        mensaje = ws_paco.receive_json()
        assert mensaje["tipo"] == "estado_privado"
        assert "Luis" in [j["alias"] for j in mensaje["sala"]["jugadores"]]


def test_con_menos_de_3_no_se_puede_comenzar():
    datos = crear("Paco")
    cliente.post(f"/api/partidas/{datos['codigo']}/unirse", json={"alias": "Ana"})
    codigo = datos["codigo"]
    with cliente.websocket_connect(f"/ws/{codigo}/{datos['jugador_id']}") as ws_paco:
        ws_paco.receive_json()
        ws_paco.send_json({"accion": "iniciar"})
        mensaje = ws_paco.receive_json()
        assert mensaje["tipo"] == "error"
        assert "3 jugadores" in mensaje["detalle"]
    assert gestor.obtener(codigo).estado == "esperando"


def test_sala_llena_rechaza_nuevos_jugadores():
    datos = crear("Paco")
    codigo = datos["codigo"]
    for alias in ["Ana", "Luis", "Eva", "Iker", "Noa"]:
        respuesta = cliente.post(f"/api/partidas/{codigo}/unirse", json={"alias": alias})
        assert respuesta.status_code == 200
    septimo = cliente.post(f"/api/partidas/{codigo}/unirse", json={"alias": "Gala"})
    assert septimo.status_code == 400
