import pytest
from fastapi.testclient import TestClient

from app.main import app, gestor
from app.datos.jarandilla import CARTA_POR_ID
from app.motor.sala import (
    ESTADO_INICIADA,
    JUGADA_ESPERANDO_DESTINO,
    JUGADA_ESPERANDO_MOVIMIENTO,
    JUGADA_ESPERANDO_SOSPECHA,
    MODO_RAPIDO,
    MODO_TABLERO,
    POSICIONES_INICIALES,
    TIPO_PNJ,
    Sala,
)
from app.motor.tablero import TABLERO

def cerrar_resultado(sala):
    """8B.31C: el turno avanza al cerrarse la presentacion del resultado.

    No-op si no hay resultado publico pendiente: las aserciones intermedias
    siguen viendo el turno sin avanzar.
    """
    presentacion = getattr(sala, "presentacion_sospecha", None)
    if presentacion and presentacion.get("tipo") == "resultado":
        assert sala.actualizar_presentacion_sospecha(ahora=float("inf"))


cliente = TestClient(app)


class DadoFijo:
    def __init__(self, valor):
        self.valor = valor

    def randint(self, minimo, maximo):
        assert (minimo, maximo) == (1, 6)
        return self.valor


def sala_tablero_controlada():
    sala = Sala("JARA-TABLERO", modo=MODO_TABLERO)
    a = sala.agregar_jugador("A", True, personaje_id="vera")
    b = sala.agregar_jugador("B", personaje_id="bruno")
    pnj = sala.agregar_jugador("Lucía", tipo=TIPO_PNJ, personaje_id="lucia")
    sala.estado = ESTADO_INICIADA
    sala.orden_turnos = [a["id"], b["id"], pnj["id"]]
    sala.turno_actual = 0
    sala.estado_jugada = JUGADA_ESPERANDO_MOVIMIENTO
    for j in sala.jugadores:
        sala.posiciones.asignar(j["id"], POSICIONES_INICIALES[j["personaje_id"]])
    sala.manos = {j["id"]: [] for j in sala.jugadores}
    return sala, a, b, pnj


def test_creacion_api_rapido_por_defecto_y_tablero_explicito():
    assert "/static/js/inicio.js?v=8b15" in cliente.get("/").text
    rapido = cliente.post(
        "/api/partidas", json={"alias": "R", "modo": "rapido"}
    ).json()
    tablero = cliente.post(
        "/api/partidas", json={"alias": "T", "modo": "tablero"}
    ).json()
    assert rapido["sala"]["modo"] == MODO_RAPIDO
    assert tablero["sala"]["modo"] == MODO_TABLERO
    assert cliente.get(
        f"/api/partidas/{rapido['codigo']}"
    ).json()["sala"]["modo"] == MODO_RAPIDO
    assert cliente.get(
        f"/api/partidas/{tablero['codigo']}"
    ).json()["sala"]["modo"] == MODO_TABLERO

    sala = gestor.obtener(tablero["codigo"])
    sala.elegir_personaje(tablero["jugador_id"], "vera")
    sala.iniciar(tablero["jugador_id"])
    sala.turno_actual = sala.orden_turnos.index(tablero["jugador_id"])
    estado = sala.estado_privado(tablero["jugador_id"])
    assert estado["movimiento"]["fase"] == JUGADA_ESPERANDO_MOVIMIENTO
    assert estado["movimiento"]["puede_tirar"] is True


def test_modo_inmutable_tras_inicio():
    sala, a, _, _ = sala_tablero_controlada()
    with pytest.raises(ValueError):
        sala.cambiar_modo(MODO_RAPIDO)


def test_rapido_sin_posiciones_y_con_flujo_pnj_existente():
    sala = Sala("JARA-R", modo=MODO_RAPIDO)
    pnj = sala.agregar_jugador("Vera", tipo=TIPO_PNJ, personaje_id="vera")
    sala.estado = ESTADO_INICIADA
    sala.orden_turnos = [pnj["id"]]
    sala.manos = {pnj["id"]: []}
    sala.ejecutar_turno_pnj(rng=type("R", (), {"choices": lambda s, o, weights, k: [o[0]]})())
    sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    assert sala.posiciones.obtener(pnj["id"]) is None
    assert sala.ultima_jugada is not None


def test_tablero_asigna_seis_posiciones_por_personaje_humano_o_pnj(monkeypatch):
    sala = Sala("JARA-I", modo=MODO_TABLERO)
    humano = sala.agregar_jugador("Mateo humano", True)
    sala.elegir_personaje(humano["id"], "mateo")
    sala.iniciar(humano["id"])
    assert len(sala.jugadores) == 6
    for jugador in sala.jugadores:
        assert sala.posiciones.obtener(jugador["id"]) == POSICIONES_INICIALES[jugador["personaje_id"]]
    assert sala.posiciones.obtener(humano["id"]) == "museo-escobazos"
    assert sala.estado_jugada == JUGADA_ESPERANDO_MOVIMIENTO


def test_inicio_turno_en_ubicacion_no_ofrece_sospecha_pero_si_dado_y_pasadizo():
    sala, a, _, _ = sala_tablero_controlada()
    sala.posiciones.asignar(a["id"], "plaza-constitucion")
    assert TABLERO.es_ubicacion(sala.posiciones.obtener(a["id"]))
    movimiento = sala.estado_privado(a["id"])["movimiento"]
    assert not movimiento.get("puede_sospechar_aqui", False)
    assert not movimiento["puede_sospechar"]
    assert movimiento["puede_tirar"]
    assert movimiento["pasadizo"]["id"] == "nuestra-senora-torre"


def test_peticion_falsificada_de_sospecha_inicial_es_rechazada_por_backend():
    sala, a, _, _ = sala_tablero_controlada()
    sala.posiciones.asignar(a["id"], "plaza-constitucion")
    with pytest.raises(ValueError, match="sospecha pendiente"):
        sala.formular_sospecha(a["id"], "vera", "parador", "libro-hueco")
    movimiento = sala.estado_privado(a["id"])["movimiento"]
    assert movimiento["puede_tirar"]
    assert movimiento["pasadizo"]["id"] == "nuestra-senora-torre"


def test_sospecha_inicial_rechaza_lugar_falso_eliminado_y_fuera_turno():
    sala, a, b, _ = sala_tablero_controlada()
    with pytest.raises(ValueError, match="sospecha pendiente"):
        sala.formular_sospecha(a["id"], "vera", "picota", "libro-hueco")
    assert sala.estado_privado(a["id"])["movimiento"]["puede_tirar"]
    with pytest.raises(ValueError, match="turno"):
        sala.formular_sospecha(b["id"], "vera", "iglesia-san-agustin", "libro-hueco")
    a["activo_investigacion"] = False
    with pytest.raises(ValueError, match="eliminado"):
        sala.formular_sospecha(a["id"], "vera", "parador", "libro-hueco")


def test_tirar_elimina_sospecha_en_origen_y_reconexion_no_la_restaura():
    sala, a, _, _ = sala_tablero_controlada()
    sala.tirar_dado_tablero(a["id"], DadoFijo(2))
    movimiento = sala.estado_privado(a["id"])["movimiento"]
    assert movimiento["fase"] == JUGADA_ESPERANDO_DESTINO
    assert not movimiento.get("puede_sospechar_aqui", False)
    assert movimiento["destinos"]
    with pytest.raises(ValueError):
        sala.formular_sospecha(a["id"], "vera", "parador", "libro-hueco")


def test_refutacion_tras_entrar_reconecta_sin_acciones_y_avanza_una_vez():
    sala, a, b, _ = sala_tablero_controlada()
    sala.manos[b["id"]] = [CARTA_POR_ID["vera"], CARTA_POR_ID["libro-hueco"]]
    sala.tirar_dado_tablero(a["id"], DadoFijo(4))
    destino = next(d for d in sala.rutas_pendientes if TABLERO.es_ubicacion(d))
    sala.mover(a["id"], destino)
    sala.formular_sospecha(a["id"], "vera", destino, "libro-hueco")
    sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    movimiento = sala.estado_privado(a["id"])["movimiento"]
    assert movimiento["fase"] == "esperando_eleccion_refutador"
    assert not movimiento.get("puede_tirar", False)
    assert not movimiento.get("puede_sospechar_aqui", False)
    assert "pasadizo" not in movimiento
    with pytest.raises(ValueError):
        sala.tirar_dado_tablero(a["id"], DadoFijo(2))
    with pytest.raises(ValueError):
        sala.usar_pasadizo(a["id"])
    sala.mostrar_carta(b["id"], "vera")
    cerrar_resultado(sala)  # 8B.31C
    assert sala.jugador_en_turno()["id"] == b["id"]


def test_nuevo_turno_en_misma_ubicacion_no_regala_otra_sospecha():
    sala, a, _, _ = sala_tablero_controlada()
    sala.posiciones.asignar(a["id"], "plaza-constitucion")
    sala.manos = {j["id"]: [] for j in sala.jugadores}
    sala.usar_pasadizo(a["id"])
    destino = sala.posiciones.obtener(a["id"])
    sala.formular_sospecha(a["id"], "vera", destino, "libro-hueco")
    sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    cerrar_resultado(sala)  # 8B.31C
    while sala.jugador_en_turno()["id"] != a["id"]:
        sala.avanzar_turno()
    assert sala.posiciones.obtener(a["id"]) == destino
    movimiento = sala.estado_privado(a["id"])["movimiento"]
    assert movimiento["puede_tirar"]
    assert not movimiento.get("puede_sospechar_aqui", False)
    with pytest.raises(ValueError, match="sospecha pendiente"):
        sala.formular_sospecha(a["id"], "vera", destino, "libro-hueco")


def test_solo_humano_actual_activo_tira_una_vez_y_dado_es_server_side():
    sala, a, b, _ = sala_tablero_controlada()
    with pytest.raises(ValueError):
        sala.tirar_dado_tablero(b["id"], DadoFijo(6))
    assert sala.tirar_dado_tablero(a["id"], DadoFijo(2)) == 2
    assert sala.tirada_pendiente == 2
    assert sala.estado_jugada == JUGADA_ESPERANDO_DESTINO
    with pytest.raises(ValueError):
        sala.tirar_dado_tablero(a["id"], DadoFijo(6))


def test_eliminado_no_puede_tirar():
    sala, a, _, _ = sala_tablero_controlada()
    a["activo_investigacion"] = False
    with pytest.raises(ValueError):
        sala.tirar_dado_tablero(a["id"], DadoFijo(2))


def test_destinos_proceden_motor_y_movimiento_ilegal_rechazado():
    sala, a, _, _ = sala_tablero_controlada()
    origen = sala.posiciones.obtener(a["id"])
    sala.tirar_dado_tablero(a["id"], DadoFijo(2))
    assert set(sala.rutas_pendientes) == set(TABLERO.destinos_alcanzables(origen, 2))
    with pytest.raises(ValueError):
        sala.mover(a["id"], "plaza-constitucion")


def test_llegada_intermedia_actualiza_posicion_y_termina_turno():
    sala, a, b, _ = sala_tablero_controlada()
    sala.tirar_dado_tablero(a["id"], DadoFijo(2))
    destino = next(iter(sala.rutas_pendientes))
    assert destino in TABLERO.casillas
    sala.mover(a["id"], destino)
    assert sala.posiciones.obtener(a["id"]) == destino
    assert sala.jugador_en_turno()["id"] == b["id"]
    assert sala.estado_jugada == JUGADA_ESPERANDO_MOVIMIENTO


def test_llegada_ubicacion_habilita_sospecha_y_fija_lugar():
    sala, a, _, _ = sala_tablero_controlada()
    sala.tirar_dado_tablero(a["id"], DadoFijo(4))
    destino = next(d for d in sala.rutas_pendientes if TABLERO.es_ubicacion(d))
    sala.mover(a["id"], destino)
    assert sala.estado_jugada == JUGADA_ESPERANDO_SOSPECHA
    with pytest.raises(ValueError):
        sala.formular_sospecha(a["id"], "vera", "picota", "libro-hueco")
    sala.formular_sospecha(a["id"], "vera", destino, "libro-hueco")
    sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    assert sala.ultima_jugada["sospecha"]["lugar_id"] == destino


def test_pasadizo_excluye_dado_llega_y_habilita_sospecha():
    sala, a, _, _ = sala_tablero_controlada()
    sala.posiciones.asignar(a["id"], "plaza-constitucion")
    privado = sala.estado_privado(a["id"])
    assert privado["movimiento"]["pasadizo"]["id"] == "nuestra-senora-torre"
    assert sala.usar_pasadizo(a["id"]) == "nuestra-senora-torre"
    assert sala.estado_jugada == JUGADA_ESPERANDO_SOSPECHA
    with pytest.raises(ValueError, match="ubicación actual"):
        sala.formular_sospecha(a["id"], "vera", "parador", "libro-hueco")
    sala.formular_sospecha(
        a["id"], "vera", "nuestra-senora-torre", "libro-hueco"
    )
    sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    assert sala.ultima_jugada["sospecha"]["lugar_id"] == "nuestra-senora-torre"
    with pytest.raises(ValueError):
        sala.tirar_dado_tablero(a["id"], DadoFijo(2))


def test_tirar_impide_pasadizo():
    sala, a, _, _ = sala_tablero_controlada()
    sala.tirar_dado_tablero(a["id"], DadoFijo(1))
    with pytest.raises(ValueError):
        sala.usar_pasadizo(a["id"])


def test_reconexion_reconstruye_antes_y_despues_de_tirar_y_sospecha():
    sala, a, _, _ = sala_tablero_controlada()
    antes = sala.estado_privado(a["id"])["movimiento"]
    assert antes["puede_tirar"]
    sala.tirar_dado_tablero(a["id"], DadoFijo(4))
    despues = sala.estado_privado(a["id"])["movimiento"]
    assert despues["tirada"] == 4 and despues["destinos"]
    destino = next(d for d in sala.rutas_pendientes if TABLERO.es_ubicacion(d))
    sala.mover(a["id"], destino)
    assert sala.estado_privado(a["id"])["movimiento"]["puede_sospechar"]


def test_resolver_permitido_antes_movimiento_no_durante_destino():
    sala, a, _, _ = sala_tablero_controlada()
    sala.misterio = {
        "sospechoso": {"id": "vera"}, "lugar": {"id": "parador"}, "objeto": {"id": "libro-hueco"}
    }
    assert sala.resolver_misterio(a["id"], "vera", "parador", "libro-hueco")
    sala, a, _, _ = sala_tablero_controlada()
    sala.tirar_dado_tablero(a["id"], DadoFijo(2))
    with pytest.raises(ValueError):
        sala.resolver_misterio(a["id"], "vera", "parador", "libro-hueco")


def test_pnj_tablero_se_detiene_y_rapido_no():
    sala, _, _, pnj = sala_tablero_controlada()
    sala.turno_actual = 2
    sala.manos = {j["id"]: [] for j in sala.jugadores}
    sala.ejecutar_turno_pnj(RngTablero("pasadizo"))
    sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    cerrar_resultado(sala)  # 8B.31C
    assert sala.jugador_en_turno()["id"] != pnj["id"]


def test_ws_tablero_envia_capacidad_de_tirar_al_humano_en_turno():
    creada = cliente.post(
        "/api/partidas", json={"alias": "Humano WS", "modo": "tablero"}
    ).json()
    codigo = creada["codigo"]
    jugador_id = creada["jugador_id"]
    sala = gestor.obtener(codigo)
    sala.elegir_personaje(jugador_id, "vera")
    sala.iniciar(jugador_id)
    sala.turno_actual = sala.orden_turnos.index(jugador_id)
    sala.estado_jugada = JUGADA_ESPERANDO_MOVIMIENTO

    with cliente.websocket_connect(f"/ws/{codigo}/{jugador_id}") as ws:
        mensaje = ws.receive_json()

    assert mensaje["tipo"] == "estado_privado"
    estado = mensaje["sala"]
    assert estado["modo"] == MODO_TABLERO
    assert estado["estado"] == ESTADO_INICIADA
    assert estado["turno_tipo"] == "humano"
    assert estado["es_mi_turno"]
    assert estado["movimiento"]["fase"] == JUGADA_ESPERANDO_MOVIMIENTO
    assert estado["movimiento"]["puede_tirar"] is True


def test_estado_privado_identifica_turno_pnj_sin_habilitar_dado_humano():
    sala, humano, _, pnj = sala_tablero_controlada()
    sala.turno_actual = sala.orden_turnos.index(pnj["id"])

    estado = sala.estado_privado(humano["id"])

    assert estado["turno_tipo"] == TIPO_PNJ
    assert estado["movimiento"]["fase"] == JUGADA_ESPERANDO_MOVIMIENTO
    assert estado["movimiento"]["puede_tirar"] is False


class RngTablero:
    def __init__(self, accion, dado=1):
        self.accion = accion
        self.dado = dado

    def choices(self, opciones, weights, k):
        if opciones and isinstance(opciones[0], str):
            return [self.accion]
        return [opciones[0]]

    def choice(self, opciones):
        return opciones[0]

    def randint(self, minimo, maximo):
        return self.dado
