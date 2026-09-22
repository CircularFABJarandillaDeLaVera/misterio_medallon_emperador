"""Pruebas del Sprint 2: misterio secreto, mazo y reparto privado."""
import json

import pytest
from fastapi.testclient import TestClient

import app.datos.jarandilla as datos
from app.datos.jarandilla import CARTAS, LUGARES, OBJETOS, SOSPECHOSOS
from app.main import app, conexiones, gestor
from app.motor.sala import MAX_JUGADORES, repartir

cliente = TestClient(app)


def setup_function(_):
    gestor.salas.clear()
    conexiones.clear()


def crear_sala_con(alias_list):
    """Crea una sala con los alias dados; devuelve (sala, [jugadores])."""
    sala, anfitrion = gestor.crear_sala(alias_list[0])
    jugadores = [anfitrion]
    for alias in alias_list[1:]:
        _, jugador = gestor.unirse(sala.codigo, alias)
        jugadores.append(jugador)
    return sala, jugadores


PERSONAJES_PRUEBA = ["vera", "bruno", "lucia", "alvaro", "mateo", "eulalia"]


def asignar_personajes(sala, jugadores):
    """Asigna un personaje distinto a cada jugador (para poder iniciar)."""
    for jugador, pid in zip(jugadores, PERSONAJES_PRUEBA):
        sala.elegir_personaje(jugador["id"], pid)


# 1. Existen exactamente 6 sospechosos, 9 lugares, 6 objetos, 21 cartas.
def test_datos_canonicos_completos():
    assert len(SOSPECHOSOS) == 6
    assert len(LUGARES) == 9
    assert len(OBJETOS) == 6
    assert len(CARTAS) == 21
    ids = [c["id"] for c in CARTAS]
    assert len(set(ids)) == 21  # sin ids repetidos
    for carta in CARTAS:
        assert carta["categoria"] in ("sospechoso", "lugar", "objeto")
        assert carta["id"] and carta["nombre"]
    for s in SOSPECHOSOS:
        assert s["color"] and s["simbolo"]
    assert not hasattr(datos, "ARMAS")  # terminología canónica: OBJETOS


# 2. El misterio contiene 1 sospechoso, 1 lugar y 1 objeto.
def test_misterio_con_uno_de_cada_categoria():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    asignar_personajes(sala, jugadores)
    sala.iniciar(jugadores[0]["id"])
    assert sala.misterio is not None
    assert sala.misterio["sospechoso"]["categoria"] == "sospechoso"
    assert sala.misterio["lugar"]["categoria"] == "lugar"
    assert sala.misterio["objeto"]["categoria"] == "objeto"


# 3-5. Manos con las 18 restantes, sin duplicados ni cartas del misterio.
def test_reparto_sin_misterio_ni_duplicados():
    sala, jugadores = crear_sala_con(["Paco", "Ana", "Luis"])
    asignar_personajes(sala, jugadores)
    sala.iniciar(jugadores[0]["id"])
    secreto = {
        sala.misterio["sospechoso"]["id"],
        sala.misterio["lugar"]["id"],
        sala.misterio["objeto"]["id"],
    }
    en_manos = []
    for j in jugadores:
        mano = sala.manos[j["id"]]
        assert not (set(c["id"] for c in mano) & secreto)  # 3
        en_manos.extend(c["id"] for c in mano)
    assert len(en_manos) == 18  # 4
    assert len(set(en_manos)) == 18  # 5
    assert set(en_manos) == {c["id"] for c in CARTAS} - secreto  # 4


# 6. Reparto equilibrado para 3, 4, 5 y 6 jugadores.
@pytest.mark.parametrize(
    "num, esperado",
    [
        (3, [6, 6, 6]),
        (4, [5, 5, 4, 4]),
        (5, [4, 4, 4, 3, 3]),
        (6, [3, 3, 3, 3, 3, 3]),
    ],
)
def test_reparto_equilibrado(num, esperado):
    ids = [f"j{i}" for i in range(num)]
    manos = repartir(list(CARTAS)[:18], ids)
    assert sorted((len(manos[j]) for j in ids), reverse=True) == esperado


# 7. Con 2 jugadores no se puede comenzar.
def test_con_dos_jugadores_no_se_puede_comenzar():
    sala, jugadores = crear_sala_con(["Paco", "Ana"])
    assert sala.puede_iniciar(jugadores[0]["id"]) is not None
    with pytest.raises(ValueError):
        sala.iniciar(jugadores[0]["id"])
    assert sala.estado == "esperando"


# 8. No puede entrar un séptimo jugador.
def test_septimo_jugador_rechazado():
    sala, _ = crear_sala_con(["Paco", "Ana", "Luis", "Eva", "Iker", "Noa"])
    assert len(sala.jugadores) == MAX_JUGADORES
    with pytest.raises(ValueError):
        gestor.unirse(sala.codigo, "Gala")


# 9-10. Privacidad por WebSocket y en estado público.
def test_privacidad_manos_y_misterio_por_websocket():
    sala = cliente.post("/api/partidas", json={"alias": "Paco"}).json()
    ana = cliente.post(
        f"/api/partidas/{sala['codigo']}/unirse", json={"alias": "Ana"}
    ).json()
    luis = cliente.post(
        f"/api/partidas/{sala['codigo']}/unirse", json={"alias": "Luis"}
    ).json()
    codigo = sala["codigo"]
    sala_srv = gestor.obtener(codigo)
    sala_srv.elegir_personaje(sala["jugador_id"], "bruno")
    sala_srv.elegir_personaje(ana["jugador_id"], "vera")
    sala_srv.elegir_personaje(luis["jugador_id"], "lucia")

    with cliente.websocket_connect(f"/ws/{codigo}/{sala['jugador_id']}") as ws_paco:
        with cliente.websocket_connect(f"/ws/{codigo}/{ana['jugador_id']}") as ws_ana:
            with cliente.websocket_connect(
                f"/ws/{codigo}/{luis['jugador_id']}"
            ) as ws_luis:
                ws_paco.receive_json()
                ws_ana.receive_json()
                ws_luis.receive_json()
                ws_paco.send_json({"accion": "iniciar"})
                privado_paco = ws_paco.receive_json()
                privado_ana = ws_ana.receive_json()
                privado_luis = ws_luis.receive_json()

    for privado in (privado_paco, privado_ana, privado_luis):
        assert privado["tipo"] == "estado_privado"

    manos = [
        {c["id"] for c in privado_paco["sala"]["mis_cartas"]},
        {c["id"] for c in privado_ana["sala"]["mis_cartas"]},
        {c["id"] for c in privado_luis["sala"]["mis_cartas"]},
    ]
    # 9a. Cada jugador ve cartas distintas y solo las suyas.
    assert sum(len(m) for m in manos) == 18
    assert len(manos[0] | manos[1] | manos[2]) == 18

    # 9b-10. El misterio no aparece en ningún mensaje ni en estado público.
    # (Los campos públicos de personaje se excluyen: un jugador puede
    # haber elegido al mismo sospechoso del misterio, y eso no es secreto.)
    secreto = {
        gestor.obtener(codigo).misterio["sospechoso"]["id"],
        gestor.obtener(codigo).misterio["lugar"]["id"],
        gestor.obtener(codigo).misterio["objeto"]["id"],
    }

    def sin_personajes(mensaje):
        copia = json.loads(json.dumps(mensaje))
        for bloque in ("sala",):
            s = copia.get(bloque, copia)
            # Campos propios de personaje (nivel superior del privado
            # y listas públicas): pueden coincidir con el sospechoso
            # del misterio sin que eso sea una filtración.
            s["personaje_id"] = None
            s["personaje"] = None
            for j in s.get("jugadores", []):
                j["personaje_id"] = None
                j["personaje"] = None
            for e in s.get("orden", []):
                e["personaje"] = None
            # Microfase 3B: la hoja privada lista las 21 cartas por diseño
            # (uniforme para todos, sin saber cuál es el misterio). Se
            # neutraliza aquí: lo que no debe filtrarse son las manos
            # ajenas y el misterio como tal, no el listado uniforme.
            for e in s.get("investigacion", []):
                e["id"] = None
                e["nombre"] = None
        return json.dumps(copia)

    textos = [
        sin_personajes(privado_paco),
        sin_personajes(privado_ana),
        sin_personajes(privado_luis),
        sin_personajes(cliente.get(f"/api/partidas/{codigo}").json()),
    ]
    for texto in textos:
        for carta_id in secreto:
            assert carta_id not in texto
    # 10b. El estado público lleva recuentos y personajes, nunca cartas.
    publico = cliente.get(f"/api/partidas/{codigo}").json()["sala"]
    for j in publico["jugadores"]:
        assert set(j.keys()) == {
            "alias",
            "es_anfitrion",
            "num_cartas",
            "personaje_id",
            "personaje",
        }
    assert "misterio" not in json.dumps(publico)


# 11-12. Desconexión y reconexión conservan la mano.
def test_desconexion_y_reconexion_conservan_la_mano():
    sala = cliente.post("/api/partidas", json={"alias": "Paco"}).json()
    ana = cliente.post(
        f"/api/partidas/{sala['codigo']}/unirse", json={"alias": "Ana"}
    ).json()
    luis = cliente.post(
        f"/api/partidas/{sala['codigo']}/unirse", json={"alias": "Luis"}
    ).json()
    codigo = sala["codigo"]
    sala_srv0 = gestor.obtener(codigo)
    sala_srv0.elegir_personaje(sala["jugador_id"], "bruno")
    sala_srv0.elegir_personaje(ana["jugador_id"], "vera")
    sala_srv0.elegir_personaje(luis["jugador_id"], "lucia")

    with cliente.websocket_connect(f"/ws/{codigo}/{sala['jugador_id']}") as ws:
        ws.receive_json()
        ws.send_json({"accion": "iniciar"})
        mano_original = ws.receive_json()["sala"]["mis_cartas"]
        assert len(mano_original) == 6
    # 11. Tras cerrar la conexión, el jugador y su mano siguen en el servidor.
    sala_srv = gestor.obtener(codigo)
    assert sala_srv.jugador_por_id(sala["jugador_id"]) is not None
    assert [c["id"] for c in sala_srv.manos[sala["jugador_id"]]] == [
        c["id"] for c in mano_original
    ]

    # 12. Al reconectar con el mismo jugador_id recupera su estado privado.
    with cliente.websocket_connect(f"/ws/{codigo}/{sala['jugador_id']}") as ws2:
        recuperado = ws2.receive_json()
        assert recuperado["tipo"] == "estado_privado"
        assert recuperado["sala"]["estado"] == "iniciada"
        assert [c["id"] for c in recuperado["sala"]["mis_cartas"]] == [
            c["id"] for c in mano_original
        ]
