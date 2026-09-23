"""Pruebas del Sprint 3: personajes y sorteo de turnos."""
import json
import threading

import pytest
from fastapi.testclient import TestClient

from app.main import app, conexiones, gestor
from app.motor.sala import PERSONAJE_POR_ID

cliente = TestClient(app)

IDS_CANONICOS = ["vera", "bruno", "lucia", "alvaro", "mateo", "eulalia"]


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


# 1. Existen exactamente 6 personajes seleccionables.
def test_seis_personajes_seleccionables():
    assert sorted(PERSONAJE_POR_ID.keys()) == sorted(IDS_CANONICOS)
    respuesta = cliente.get("/api/personajes")
    assert respuesta.status_code == 200
    assert [p["id"] for p in respuesta.json()["personajes"]] == IDS_CANONICOS


# 2. Un jugador puede elegir un personaje disponible.
def test_elegir_personaje_disponible():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    sala.elegir_personaje(jugadores[0]["id"], "bruno")
    assert jugadores[0]["personaje_id"] == "bruno"


# 3. Dos jugadores no pueden tener el mismo personaje.
def test_personaje_duplicado_rechazado():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    sala.elegir_personaje(jugadores[0]["id"], "bruno")
    with pytest.raises(ValueError):
        sala.elegir_personaje(jugadores[1]["id"], "bruno")
    assert jugadores[1]["personaje_id"] is None


# 4-5. Cambiar antes de comenzar libera el anterior.
def test_cambiar_personaje_libera_el_anterior():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    sala.elegir_personaje(jugadores[0]["id"], "bruno")
    sala.elegir_personaje(jugadores[0]["id"], "vera")
    assert jugadores[0]["personaje_id"] == "vera"
    assert sala.personaje_ocupado_por("bruno") is None
    # Otro jugador ya puede coger el liberado.
    sala.elegir_personaje(jugadores[1]["id"], "bruno")
    assert jugadores[1]["personaje_id"] == "bruno"


# 6. No se puede elegir un personaje inexistente.
def test_personaje_inexistente_rechazado():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    with pytest.raises(ValueError):
        sala.elegir_personaje(jugadores[0]["id"], "napoleon")


# 7. No se puede cambiar de personaje después de comenzar.
def test_bloqueo_de_personajes_tras_comenzar():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    for jugador, pid in zip(jugadores, ["bruno", "vera", "lucia"]):
        sala.elegir_personaje(jugador["id"], pid)
    sala.iniciar(jugadores[0]["id"])
    with pytest.raises(ValueError):
        sala.elegir_personaje(jugadores[0]["id"], "alvaro")
    assert jugadores[0]["personaje_id"] == "bruno"


# 8. No se puede comenzar si falta algún personaje.
def test_no_comenzar_sin_personajes_completos():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    sala.elegir_personaje(jugadores[0]["id"], "bruno")
    sala.elegir_personaje(jugadores[1]["id"], "vera")
    error = sala.puede_iniciar(jugadores[0]["id"])
    assert error is not None and "personaje" in error
    with pytest.raises(ValueError):
        sala.iniciar(jugadores[0]["id"])
    assert sala.estado == "esperando"


# 9. Con todos asignados se puede comenzar.
def test_comenzar_con_personajes_completos():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    for jugador, pid in zip(jugadores, ["bruno", "vera", "lucia"]):
        sala.elegir_personaje(jugador["id"], pid)
    assert sala.puede_iniciar(jugadores[0]["id"]) is None
    sala.iniciar(jugadores[0]["id"])
    assert sala.estado == "iniciada"


# 10-12. Orden con todos una vez, sin duplicados, turno inicial primero.
def test_sorteo_orden_y_turno_inicial():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis", "Eva"])
    for jugador, pid in zip(jugadores, ["bruno", "vera", "lucia", "alvaro"]):
        sala.elegir_personaje(jugador["id"], pid)
    sala.iniciar(jugadores[0]["id"])
    ids = [j["id"] for j in sala.jugadores]
    assert sorted(sala.orden_turnos) == sorted(ids)  # 10
    assert len(set(sala.orden_turnos)) == len(ids)  # 11
    assert sala.turno_actual == 0
    assert sala.jugador_en_turno()["id"] == sala.orden_turnos[0]  # 12


# 13-15. Reconexión conserva orden, turno y personaje.
def test_reconexion_conserva_orden_turno_y_personaje():
    sala = cliente.post("/api/partidas", json={"alias": "Paco"}).json()
    ana = cliente.post(
        f"/api/partidas/{sala['codigo']}/unirse", json={"alias": "Ana"}
    ).json()
    luis = cliente.post(
        f"/api/partidas/{sala['codigo']}/unirse", json={"alias": "Luis"}
    ).json()
    codigo = sala["codigo"]

    with cliente.websocket_connect(f"/ws/{codigo}/{sala['jugador_id']}") as ws_paco:
        with cliente.websocket_connect(f"/ws/{codigo}/{ana['jugador_id']}") as ws_ana:
            with cliente.websocket_connect(
                f"/ws/{codigo}/{luis['jugador_id']}"
            ) as ws_luis:
                for ws in (ws_paco, ws_ana, ws_luis):
                    ws.receive_json()
                # Elección por WebSocket (Paco=bruno, Ana=vera, Luis=lucia).
                for ws, pid in ((ws_paco, "bruno"), (ws_ana, "vera"), (ws_luis, "lucia")):
                    ws.send_json({"accion": "elegir_personaje", "personaje_id": pid})
                for ws in (ws_paco, ws_ana, ws_luis):
                    for _ in range(3):
                        ws.receive_json()  # 3 difusiones, una por elección
                # Ocupado por WS: Ana intenta el de Paco -> error claro.
                ws_ana.send_json({"accion": "elegir_personaje", "personaje_id": "bruno"})
                assert ws_ana.receive_json()["tipo"] == "error"
                ws_paco.send_json({"accion": "iniciar"})
                privado = [ws_paco.receive_json(), ws_ana.receive_json(), ws_luis.receive_json()]
    assert all(p["sala"]["estado"] == "iniciada" for p in privado)
    orden = [e["alias"] for e in privado[0]["sala"]["orden"]]
    turno = privado[0]["sala"]["turno_alias"]
    assert orden and turno in orden
    assert all(p["sala"]["orden"] == privado[0]["sala"]["orden"] for p in privado)

    # 13-15. Recarga: mismo orden, mismo turno y mismo personaje.
    with cliente.websocket_connect(f"/ws/{codigo}/{ana['jugador_id']}") as ws2:
        rec = ws2.receive_json()["sala"]
        assert [e["alias"] for e in rec["orden"]] == orden  # 13
        assert rec["turno_alias"] == turno  # 14
        assert rec["personaje_id"] == "vera"  # 15
        assert rec["personaje"] == "Vera, la fotógrafa"


# 16-17. estado_publico() con personajes y orden, sin manos ni misterio.
def test_estado_publico_con_personajes_sin_secretos():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    for jugador, pid in zip(jugadores, ["bruno", "vera", "lucia"]):
        sala.elegir_personaje(jugador["id"], pid)
    sala.iniciar(jugadores[0]["id"])
    publico = sala.estado_publico()
    assert {j["personaje_id"] for j in publico["jugadores"]} == {
        "bruno", "vera", "lucia", "alvaro", "mateo", "eulalia"
    }
    assert len(publico["orden"]) == 6  # 16
    texto = json.dumps(publico)
    assert "mis_cartas" not in texto and "manos" not in texto  # 16
    assert "misterio" not in texto
    # 17. El misterio no se filtra fuera de los campos públicos de
    # personaje (un jugador puede haber elegido al sospechoso secreto).
    copia = json.loads(texto)
    for j in copia["jugadores"]:
        j["personaje_id"] = None
        j["personaje"] = None
    for e in copia["orden"]:
        e["personaje"] = None
    texto_limpio = json.dumps(copia)
    secreto = {
        sala.misterio["sospechoso"]["id"],
        sala.misterio["lugar"]["id"],
        sala.misterio["objeto"]["id"],
    }
    for carta_id in secreto:
        assert carta_id not in texto_limpio  # 17


# 18. Los mensajes privados siguen sin cartas ajenas.
def test_privados_sin_cartas_ajenas_ni_misterio():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    for jugador, pid in zip(jugadores, ["bruno", "vera", "lucia"]):
        sala.elegir_personaje(jugador["id"], pid)
    sala.iniciar(jugadores[0]["id"])
    secreto = {
        sala.misterio["sospechoso"]["id"],
        sala.misterio["lugar"]["id"],
        sala.misterio["objeto"]["id"],
    }
    for jugador in jugadores:
        privado = sala.estado_privado(jugador["id"])
        mias = {c["id"] for c in privado["mis_cartas"]}
        assert mias == {c["id"] for c in sala.manos[jugador["id"]]}
        ajenas = {
            c["id"] for jid, mano in sala.manos.items() if jid != jugador["id"] for c in mano
        }
        assert not (mias & ajenas)
        assert not (mias & secreto)
        assert "misterio" not in json.dumps(privado)


# 19. Intentos simultáneos: solo uno consigue el personaje.
def test_eleccion_simultanea_sin_duplicados():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    barrera = threading.Barrier(2)
    resultados = []

    def intentar(jugador_id):
        barrera.wait(timeout=5)
        try:
            sala.elegir_personaje(jugador_id, "bruno")
            resultados.append(jugador_id)
        except ValueError:
            pass

    hilos = [
        threading.Thread(target=intentar, args=(jugadores[0]["id"],)),
        threading.Thread(target=intentar, args=(jugadores[1]["id"],)),
    ]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=10)
    assert len(resultados) == 1
    assert sala.personaje_ocupado_por("bruno")["id"] == resultados[0]
