"""Contratos actuales para preparar la navegacion continua.

Estas pruebas no definen todavia una arquitectura nueva. Fijan que ocurre al
entrar, salir y reconectar a la sala para que la futura inicializacion por
vistas no duplique conexiones, jugadores ni tareas del servidor.
"""
import asyncio

import pytest
from fastapi.testclient import TestClient

from app import main


TABLAS_GLOBALES = (
    main.gestor.salas,
    main.conexiones,
    main.cerrojos,
    main.historial_chat,
    main.envios_chat,
    main.cerrojos_chat,
    main.tareas_pnj,
    main.tareas_refutacion,
    main.tareas_presentacion,
    main.tareas_bloqueo,
)


@pytest.fixture(autouse=True)
def limpiar_estado_global():
    for tabla in TABLAS_GLOBALES:
        tabla.clear()
    yield
    for tabla in (
        main.tareas_pnj,
        main.tareas_refutacion,
        main.tareas_presentacion,
        main.tareas_bloqueo,
    ):
        for tarea in list(tabla.values()):
            if isinstance(tarea, asyncio.Task) and not tarea.done():
                tarea.cancel()
    for tabla in TABLAS_GLOBALES:
        tabla.clear()


@pytest.fixture
def cliente():
    return TestClient(main.app)


def crear(cliente, alias="Ana", modo="tablero"):
    respuesta = cliente.post(
        "/api/partidas", json={"alias": alias, "modo": modo}
    )
    assert respuesta.status_code == 200
    return respuesta.json()


def test_desconectar_ultimo_jugador_del_lobby_elimina_la_sala(cliente):
    datos = crear(cliente)
    codigo = datos["codigo"]
    jugador_id = datos["jugador_id"]

    with cliente.websocket_connect(f"/ws/{codigo}/{jugador_id}") as ws:
        assert ws.receive_json()["sala"]["estado"] == "esperando"
        assert len(main.conexiones[codigo][jugador_id]) == 1

    assert main.gestor.obtener(codigo) is None
    assert codigo not in main.conexiones
    assert codigo not in main.cerrojos


def test_desconectar_invitado_del_lobby_conserva_sala_y_anfitrion(cliente):
    anfitrion = crear(cliente)
    codigo = anfitrion["codigo"]
    invitado = cliente.post(
        f"/api/partidas/{codigo}/unirse", json={"alias": "Luis"}
    ).json()

    with cliente.websocket_connect(
        f"/ws/{codigo}/{invitado['jugador_id']}"
    ) as ws:
        assert ws.receive_json()["sala"]["estado"] == "esperando"

    sala = main.gestor.obtener(codigo)
    assert sala is not None
    assert sala.jugador_por_id(invitado["jugador_id"]) is None
    assert sala.jugador_por_id(anfitrion["jugador_id"])["es_anfitrion"] is True
    assert len(sala.jugadores) == 1


def test_seleccion_por_websocket_pasa_al_tablero_sin_crear_otro_jugador(cliente):
    datos = crear(cliente)
    codigo = datos["codigo"]
    jugador_id = datos["jugador_id"]

    with cliente.websocket_connect(f"/ws/{codigo}/{jugador_id}") as ws:
        inicial = ws.receive_json()["sala"]
        assert inicial["estado"] == "esperando"
        assert inicial["personaje_id"] is None

        ws.send_json({"accion": "elegir_personaje", "personaje_id": "vera"})
        seleccion = ws.receive_json()["sala"]
        assert seleccion["estado"] == "esperando"
        assert seleccion["personaje_id"] == "vera"

        ws.send_json({"accion": "iniciar"})
        tablero = ws.receive_json()["sala"]
        assert tablero["estado"] == "iniciada"
        assert tablero["modo"] == "tablero"
        assert len(tablero["jugadores"]) == 6
        assert sum(j["tipo"] == "humano" for j in tablero["jugadores"]) == 1
        assert len(main.conexiones[codigo][jugador_id]) == 1

    sala = main.gestor.obtener(codigo)
    assert sala is not None
    assert sala.jugador_por_id(jugador_id) is not None
    assert len(sala.jugadores) == 6
    assert jugador_id not in main.conexiones.get(codigo, {})


def test_dos_pantallas_del_mismo_jugador_no_duplican_asiento_ni_tareas(cliente):
    datos = crear(cliente)
    codigo = datos["codigo"]
    jugador_id = datos["jugador_id"]
    sala = main.gestor.obtener(codigo)
    sala.elegir_personaje(jugador_id, "vera")
    sala.iniciar(jugador_id)
    sala.pausar_partida(jugador_id, sala.credencial_admin)
    jugadores_antes = [jugador["id"] for jugador in sala.jugadores]

    with cliente.websocket_connect(f"/ws/{codigo}/{jugador_id}") as primera:
        assert primera.receive_json()["sala"]["estado"] == "iniciada"
        with cliente.websocket_connect(f"/ws/{codigo}/{jugador_id}") as segunda:
            assert segunda.receive_json()["sala"]["estado"] == "iniciada"
            assert len(main.conexiones[codigo][jugador_id]) == 2
            assert [jugador["id"] for jugador in sala.jugadores] == jugadores_antes
            assert not main.tareas_pnj
            assert not main.tareas_refutacion
            assert not main.tareas_presentacion
            assert not main.tareas_bloqueo

        assert len(main.conexiones[codigo][jugador_id]) == 1
        assert sala.jugador_por_id(jugador_id) is not None

    assert jugador_id not in main.conexiones.get(codigo, {})
    assert [jugador["id"] for jugador in sala.jugadores] == jugadores_antes


def test_reconexion_secuencial_en_partida_reutiliza_identidad(cliente):
    datos = crear(cliente)
    codigo = datos["codigo"]
    jugador_id = datos["jugador_id"]
    sala = main.gestor.obtener(codigo)
    sala.elegir_personaje(jugador_id, "vera")
    sala.iniciar(jugador_id)
    sala.pausar_partida(jugador_id, sala.credencial_admin)
    jugadores_antes = [jugador["id"] for jugador in sala.jugadores]

    for _ in range(3):
        with cliente.websocket_connect(f"/ws/{codigo}/{jugador_id}") as ws:
            privado = ws.receive_json()["sala"]
            assert privado["personaje_id"] == "vera"
            assert len(main.conexiones[codigo][jugador_id]) == 1
        assert jugador_id not in main.conexiones.get(codigo, {})

    assert [jugador["id"] for jugador in sala.jugadores] == jugadores_antes
    assert len(set(jugadores_antes)) == 6


def test_cerrar_una_conexion_duplicada_del_lobby_no_deberia_expulsar(cliente):
    datos = crear(cliente)
    codigo = datos["codigo"]
    jugador_id = datos["jugador_id"]

    with cliente.websocket_connect(f"/ws/{codigo}/{jugador_id}") as primera:
        primera.receive_json()
        with cliente.websocket_connect(f"/ws/{codigo}/{jugador_id}") as segunda:
            segunda.receive_json()
            assert len(main.conexiones[codigo][jugador_id]) == 2

        sala = main.gestor.obtener(codigo)
        assert sala is not None
        assert sala.jugador_por_id(jugador_id) is not None
        assert len(main.conexiones[codigo][jugador_id]) == 1

    assert main.gestor.obtener(codigo) is None
    assert codigo not in main.conexiones
