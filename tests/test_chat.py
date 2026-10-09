"""Pruebas del chat efímero integrado en los WebSockets de cada sala."""

import asyncio
from collections import deque

from fastapi.testclient import TestClient

from app import main
from app.motor.persistencia import exportar
from app.motor.sala import Sala, TIPO_PNJ


cliente = TestClient(main.app)


def setup_function(_):
    main.gestor.salas.clear()
    main.conexiones.clear()
    main.historial_chat.clear()
    main.envios_chat.clear()
    main.cerrojos_chat.clear()


def crear_jugador(alias, codigo=None):
    if codigo is None:
        respuesta = cliente.post("/api/partidas", json={"alias": alias})
    else:
        respuesta = cliente.post(
            f"/api/partidas/{codigo}/unirse", json={"alias": alias}
        )
    assert respuesta.status_code == 200
    return respuesta.json()


def recibir_estado_y_chat(ws):
    mensaje = ws.receive_json()
    assert mensaje["tipo"] == "estado_privado"
    return mensaje


def test_chat_entrega_alias_autentico_texto_plano_y_historial_al_reconectar():
    anfitrion = crear_jugador("Alicia")
    invitada = crear_jugador("Bea", anfitrion["codigo"])
    ruta = f"/ws/{anfitrion['codigo']}"

    with cliente.websocket_connect(f"{ruta}/{anfitrion['jugador_id']}") as ws_alicia:
        assert recibir_estado_y_chat(ws_alicia)["sala"]["chat_historial"] == []
        with cliente.websocket_connect(
            f"{ruta}/{invitada['jugador_id']}"
        ) as ws_bea:
            assert recibir_estado_y_chat(ws_bea)["sala"]["chat_historial"] == []
            ws_alicia.send_json({
                "accion": "chat",
                "texto": "<script>alert('no ejecutar')</script>",
                "alias": "Alias suplantado",
            })
            recibido_alicia = ws_alicia.receive_json()
            recibido_bea = ws_bea.receive_json()
            esperado = {
                "tipo": "chat_mensaje",
                "mensaje": {
                    "jugador_id": anfitrion["jugador_id"],
                    "alias": "Alicia",
                    "texto": "<script>alert('no ejecutar')</script>",
                },
            }
            assert recibido_alicia == esperado
            assert recibido_bea == esperado

            with cliente.websocket_connect(
                f"{ruta}/{invitada['jugador_id']}"
            ) as ws_recargada:
                estado = ws_recargada.receive_json()
                assert estado["tipo"] == "estado_privado"
                assert estado["sala"]["chat_historial"] == [esperado["mensaje"]]


def test_historial_aislado_por_sala_y_sin_entrega_a_pnj():
    sala_a = Sala("JARA-CHAT-A")
    humano_a = sala_a.agregar_jugador("Ana", es_anfitrion=True)
    pnj_a = sala_a.agregar_jugador(
        "Bruno", tipo=TIPO_PNJ, personaje_id="bruno"
    )
    sala_b = Sala("JARA-CHAT-B")
    humano_b = sala_b.agregar_jugador("Bea", es_anfitrion=True)
    main.gestor.salas[sala_a.codigo] = sala_a
    main.gestor.salas[sala_b.codigo] = sala_b

    class SocketFalso:
        def __init__(self):
            self.mensajes = []

        async def send_json(self, mensaje):
            self.mensajes.append(mensaje)

    socket_humano = SocketFalso()
    socket_pnj = SocketFalso()
    socket_otra_sala = SocketFalso()
    main.conexiones[sala_a.codigo] = {
        humano_a["id"]: [socket_humano],
        pnj_a["id"]: [socket_pnj],
    }
    main.conexiones[sala_b.codigo] = {humano_b["id"]: [socket_otra_sala]}

    mensaje = {"jugador_id": humano_a["id"], "alias": "Ana", "texto": "Hola"}
    asyncio.run(main._difundir_mensaje_chat(sala_a, mensaje))

    assert socket_humano.mensajes == [
        {"tipo": "chat_mensaje", "mensaje": mensaje}
    ]
    assert socket_pnj.mensajes == []
    assert socket_otra_sala.mensajes == []


def test_rechaza_mensajes_vacios_largos_y_limita_frecuencia():
    jugador = crear_jugador("Ana")
    ruta = f"/ws/{jugador['codigo']}/{jugador['jugador_id']}"
    with cliente.websocket_connect(ruta) as ws:
        recibir_estado_y_chat(ws)

        ws.send_json({"accion": "chat", "texto": "  "})
        assert ws.receive_json()["tipo"] == "error_chat"
        ws.send_json({"accion": "chat", "texto": "x" * 301})
        assert ws.receive_json()["tipo"] == "error_chat"

        for numero in range(main.MENSAJES_CHAT_POR_VENTANA):
            ws.send_json({"accion": "chat", "texto": f"mensaje {numero}"})
            assert ws.receive_json()["tipo"] == "chat_mensaje"

        ws.send_json({"accion": "chat", "texto": "demasiado pronto"})
        error = ws.receive_json()
        assert error["tipo"] == "error_chat"
        assert "Espera" in error["detalle"]


def test_conserva_solo_los_cien_mensajes_mas_recientes(monkeypatch):
    jugador = crear_jugador("Ana")
    monkeypatch.setattr(main, "VENTANA_CHAT_SEGUNDOS", 0)
    ruta = f"/ws/{jugador['codigo']}/{jugador['jugador_id']}"
    with cliente.websocket_connect(ruta) as ws:
        recibir_estado_y_chat(ws)
        for numero in range(101):
            ws.send_json({"accion": "chat", "texto": f"mensaje {numero}"})
            assert ws.receive_json()["tipo"] == "chat_mensaje"

        historial = list(main.historial_chat[jugador["codigo"]])
        assert len(historial) == 100
        assert historial[0]["texto"] == "mensaje 1"
        assert historial[-1]["texto"] == "mensaje 100"


def test_el_chat_no_se_incluye_en_el_archivo_de_guardado():
    jugador = crear_jugador("Ana")
    sala = main.gestor.obtener(jugador["codigo"])
    main.historial_chat[sala.codigo] = deque(
        [{"jugador_id": jugador["jugador_id"], "alias": "Ana", "texto": "Hola"}],
        maxlen=main.HISTORIAL_CHAT_MAXIMO,
    )

    guardado = exportar(sala)

    assert "chat" not in guardado
    assert "historial_chat" not in guardado["estado"]
    restaurada, _ = main.gestor.importar_partida(guardado)
    assert restaurada.codigo not in main.historial_chat
