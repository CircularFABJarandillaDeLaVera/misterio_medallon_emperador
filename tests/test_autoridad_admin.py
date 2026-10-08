"""Microfase 1 · Autoridad administrativa del anfitrión.

La autoridad NO se apoya en la visibilidad de un botón ni en el jugador_id
suelto: hacen falta el asiento de anfitrión Y su secreto de sala. Estos
pruebas fijan ese contrato, incluida la promesa de que el secreto nunca sale
en un estado ni en una difusión general.
"""
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.motor.sala import (
    GestorSalas,
    MENSAJE_SIN_AUTORIDAD_ADMIN,
    MODO_RAPIDO,
    Sala,
    TIPO_PNJ,
)

RAIZ = Path(__file__).parents[1]


@pytest.fixture(autouse=True)
def limpiar_registros():
    """Las salas viven en globales de módulo: cada prueba empieza limpio."""
    main.gestor.salas.clear()
    main.conexiones.clear()
    main.cerrojos.clear()
    main.tareas_pnj.clear()
    yield
    main.gestor.salas.clear()
    main.conexiones.clear()
    main.cerrojos.clear()
    main.tareas_pnj.clear()


def sala_con_dos_humanos() -> tuple[Sala, dict, dict]:
    gestor = GestorSalas()
    sala, anfitrion = gestor.crear_sala("Ana")
    _, invitado = gestor.unirse(sala.codigo, "Luis")
    return sala, anfitrion, invitado


def sala_iniciada() -> tuple[Sala, dict, dict]:
    """Sala con los dos humanos con personaje y la partida empezada."""
    sala, anfitrion, invitado = sala_con_dos_humanos()
    sala.elegir_personaje(anfitrion["id"], "vera")
    sala.elegir_personaje(invitado["id"], "bruno")
    sala.iniciar(anfitrion["id"])
    return sala, anfitrion, invitado


# --- Existencia y unicidad del secreto -----------------------------------


def test_cada_sala_tiene_un_unico_secreto_admin():
    primera, _, _ = sala_con_dos_humanos()
    segunda, _, _ = sala_con_dos_humanos()
    assert primera.credencial_admin
    assert segunda.credencial_admin
    assert primera.credencial_admin != segunda.credencial_admin


def test_el_secreto_es_largo_y_aleatorio():
    sala, _, _ = sala_con_dos_humanos()
    # 32 bytes -> 43 caracteres URL-safe. Suficientemente largo para no
    # poder adivinarse ni forzarse por fuerza bruta.
    assert len(sala.credencial_admin) >= 40
    assert sala.credencial_admin != sala.codigo


def test_rotar_invalida_el_secreto_anterior():
    sala, anfitrion, _ = sala_con_dos_humanos()
    anterior = sala.credencial_admin
    sala.rotar_credencial_admin(anfitrion["id"])
    assert sala.credencial_admin != anterior
    assert not sala.credencial_admin_valida(anterior)
    assert sala.credencial_admin_valida(sala.credencial_admin)


# --- El secreto pertenece solo al anfitrión -----------------------------


def test_solo_el_anfitrion_recibe_el_secreto():
    sala, anfitrion, invitado = sala_con_dos_humanos()
    assert sala.credencial_admin_de(anfitrion["id"]) == sala.credencial_admin
    assert sala.credencial_admin_de(invitado["id"]) is None


def test_es_anfitrion_reconoce_solo_el_asiento_actual():
    sala, anfitrion, invitado = sala_con_dos_humanos()
    assert sala.es_anfitrion(anfitrion["id"])
    assert not sala.es_anfitrion(invitado["id"])
    assert not sala.es_anfitrion("jugador-inexistente")


def test_el_secreto_no_se_guarda_en_ningun_jugador():
    """Es de la SALA, no de cada jugador: nada queda en el dict del jugador."""
    sala, anfitrion, _ = sala_con_dos_humanos()
    assert not any("credencial" in clave for clave in anfitrion)


# --- Validación: asiento + secreto ---------------------------------------


def test_anfitrion_con_secreto_correcto_pasa():
    sala, anfitrion, _ = sala_con_dos_humanos()
    sala.exigir_credencial_admin(anfitrion["id"], sala.credencial_admin)


def test_anfitrion_con_secreto_incorrecto_es_rechazado():
    sala, anfitrion, _ = sala_con_dos_humanos()
    with pytest.raises(ValueError):
        sala.exigir_credencial_admin(anfitrion["id"], "no-es-el-secreto")


def test_anfitrion_sin_secreto_es_rechazado():
    sala, anfitrion, _ = sala_con_dos_humanos()
    for ausente in (None, "", 0, [], {}, True):
        with pytest.raises(ValueError):
            sala.exigir_credencial_admin(anfitrion["id"], ausente)


def test_no_anfitrion_es_rechazado_aunque_conozca_el_secreto():
    """Manipular la petición desde el navegador no cambia nada."""
    sala, _, invitado = sala_con_dos_humanos()
    with pytest.raises(ValueError):
        sala.exigir_credencial_admin(invitado["id"], sala.credencial_admin)


def test_no_anfitrion_es_rechazado_con_cualquier_secreto():
    sala, _, invitado = sala_con_dos_humanos()
    for candidato in (sala.credencial_admin, "otro", None):
        with pytest.raises(ValueError):
            sala.exigir_credencial_admin(invitado["id"], candidato)


def test_el_rechazo_no_revela_si_falla_el_asiento_o_el_secreto():
    """Mismo mensaje en ambos casos: no regala un oráculo al atacante."""
    sala, anfitrion, invitado = sala_con_dos_humanos()
    with pytest.raises(ValueError) as por_secreto:
        sala.exigir_credencial_admin(anfitrion["id"], "inventado")
    with pytest.raises(ValueError) as por_asiento:
        sala.exigir_credencial_admin(invitado["id"], sala.credencial_admin)
    assert str(por_secreto.value) == str(por_asiento.value)


def test_jugador_desconocido_es_rechazado():
    sala, _, _ = sala_con_dos_humanos()
    with pytest.raises(ValueError):
        sala.exigir_credencial_admin("fantasma", sala.credencial_admin)


def test_un_pnj_nunca_administra():
    sala = Sala("JARA-TEST", modo=MODO_RAPIDO)
    pnj = sala.agregar_jugador("Vera", tipo=TIPO_PNJ, personaje_id="vera")
    assert not sala.es_anfitrion(pnj["id"])
    assert sala.credencial_admin_de(pnj["id"]) is None
    with pytest.raises(ValueError):
        sala.exigir_credencial_admin(pnj["id"], sala.credencial_admin)


# --- Herencia del rol ----------------------------------------------------


def test_al_irse_el_anfitrion_el_secreto_cambia_de_manos():
    sala, anfitrion, invitado = sala_con_dos_humanos()
    viejo = sala.credencial_admin
    sala.quitar_jugador(anfitrion["id"])
    assert sala.es_anfitrion(invitado["id"])
    assert sala.credencial_admin != viejo
    # El anfitrión saliente deja de poder administrar, aunque conserve
    # el jugador_id con el que estaba conectado.
    with pytest.raises(ValueError):
        sala.exigir_credencial_admin(invitado["id"], viejo)
    sala.exigir_credencial_admin(invitado["id"], sala.credencial_admin)


def test_irse_el_anfitrion_no_rompe_la_partida():
    """Solo cambia el rol y el secreto: cartas, turno y misterio intactos."""
    sala, anfitrion, invitado = sala_con_dos_humanos()
    sala.manos[anfitrion["id"]] = [{"id": "vera"}]
    sala.manos[invitado["id"]] = [{"id": "bruno"}]
    sala.orden_turnos = [anfitrion["id"], invitado["id"]]
    sala.misterio = {"sospechoso": {"id": "lucia"}}

    sala.quitar_jugador(anfitrion["id"])

    assert sala.manos[invitado["id"]] == [{"id": "bruno"}]
    assert sala.orden_turnos == [anfitrion["id"], invitado["id"]]
    assert sala.misterio == {"sospechoso": {"id": "lucia"}}


# --- El secreto nunca viaja en un estado ni en una difusión --------------


def test_el_secreto_no_esta_en_el_estado_publico():
    sala, anfitrion, _ = sala_iniciada()
    assert sala.credencial_admin not in repr(sala.estado_publico())
    assert "credencial_admin" not in repr(sala.estado_publico())


def test_el_secreto_no_esta_en_el_estado_privado_de_nadie():
    """Ni siquiera en el del propio anfitrión."""
    sala, anfitrion, invitado = sala_iniciada()
    for jugador_id in (anfitrion["id"], invitado["id"]):
        privado = repr(sala.estado_privado(jugador_id))
        assert sala.credencial_admin not in privado
        assert "credencial_admin" not in privado


def test_tras_el_final_tampoco_se_filtra():
    sala, anfitrion, _ = sala_iniciada()
    sala.estado = "terminada"
    assert sala.credencial_admin not in repr(sala.estado_publico())
    assert sala.credencial_admin not in repr(sala.estado_privado(anfitrion["id"]))


# --- Reparto por HTTP ----------------------------------------------------


def test_crear_partida_devuelve_el_secreto_solo_al_anfitrion():
    cliente = TestClient(main.app)
    respuesta = cliente.post("/api/partidas", json={"alias": "Ana", "modo": "rapido"})
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["credencial_admin"]
    sala = main.gestor.obtener(datos["codigo"])
    assert sala.credencial_admin_de(datos["jugador_id"]) == datos["credencial_admin"]


def test_unirse_no_devuelve_ninguna_credencial():
    cliente = TestClient(main.app)
    creada = cliente.post("/api/partidas", json={"alias": "Ana"}).json()
    unida = cliente.post(
        f"/api/partidas/{creada['codigo']}/unirse", json={"alias": "Luis"}
    ).json()
    assert "credencial_admin" not in unida
    sala = main.gestor.obtener(creada["codigo"])
    assert sala.credencial_admin_de(unida["jugador_id"]) is None


def test_el_secreto_no_esta_en_el_estado_publico_http():
    cliente = TestClient(main.app)
    creada = cliente.post("/api/partidas", json={"alias": "Ana"}).json()
    sala = main.gestor.obtener(creada["codigo"])
    consulta = cliente.get(f"/api/partidas/{creada['codigo']}").text
    assert sala.credencial_admin not in consulta


# --- Reparto por WebSocket ----------------------------------------------


def test_solo_el_anfitrion_puede_pedir_y_recibir_su_secreto():
    """No se empuja al conectar: lo pide el propio anfitrión, por su socket."""
    cliente = TestClient(main.app)
    creada = cliente.post("/api/partidas", json={"alias": "Ana"}).json()
    sala = main.gestor.obtener(creada["codigo"])
    with cliente.websocket_connect(
        f"/ws/{creada['codigo']}/{creada['jugador_id']}"
    ) as ws:
        # Conectar no añade ningún mensaje nuevo al flujo de la partida.
        assert ws.receive_json()["tipo"] == "estado_privado"
        ws.send_json({"accion": "pedir_credencial_admin"})
        entrega = ws.receive_json()
    assert entrega["tipo"] == "credencial_admin"
    assert entrega["credencial"] == sala.credencial_admin


def test_la_peticion_no_altera_el_estado_de_la_partida():
    cliente = TestClient(main.app)
    creada = cliente.post("/api/partidas", json={"alias": "Ana"}).json()
    sala = main.gestor.obtener(creada["codigo"])
    sala.elegir_personaje(creada["jugador_id"], "vera")
    sala.iniciar(creada["jugador_id"])
    estado = sala.estado
    secuencia = sala.secuencia_presentacion
    misterio = sala.misterio
    with cliente.websocket_connect(
        f"/ws/{creada['codigo']}/{creada['jugador_id']}"
    ) as ws:
        ws.receive_json()
        ws.send_json({"accion": "pedir_credencial_admin"})
        assert ws.receive_json()["tipo"] == "credencial_admin"
        # La partida no se ha movido: ni estado, ni misterio, ni secuencia.
        assert sala.estado == estado
        assert sala.misterio is misterio
        assert sala.secuencia_presentacion == secuencia
        assert sala.jugador_por_id(creada["jugador_id"])["tipo"] == "humano"


def test_un_invitado_no_puede_pedir_ningun_secreto():
    cliente = TestClient(main.app)
    creada = cliente.post("/api/partidas", json={"alias": "Ana"}).json()
    unida = cliente.post(
        f"/api/partidas/{creada['codigo']}/unirse", json={"alias": "Luis"}
    ).json()
    sala = main.gestor.obtener(creada["codigo"])
    with cliente.websocket_connect(
        f"/ws/{creada['codigo']}/{unida['jugador_id']}"
    ) as ws:
        ws.receive_json()
        ws.send_json({"accion": "pedir_credencial_admin"})
        error = ws.receive_json()
    assert error["tipo"] == "error"
    assert error["detalle"] == MENSAJE_SIN_AUTORIDAD_ADMIN
    assert sala.credencial_admin not in repr(error)


def test_un_invitado_tampoco_puede_pedirlo_si_conoce_el_secreto():
    """Aunque lo Haya visto en otro sitio, el asiento no le sirve."""
    cliente = TestClient(main.app)
    creada = cliente.post("/api/partidas", json={"alias": "Ana"}).json()
    unida = cliente.post(
        f"/api/partidas/{creada['codigo']}/unirse", json={"alias": "Luis"}
    ).json()
    sala = main.gestor.obtener(creada["codigo"])
    with cliente.websocket_connect(
        f"/ws/{creada['codigo']}/{unida['jugador_id']}"
    ) as ws:
        ws.receive_json()
        ws.send_json(
            {
                "accion": "pedir_credencial_admin",
                "credencial_admin": sala.credencial_admin,
            }
        )
        assert ws.receive_json()["tipo"] == "error"


def test_conectar_no_omite_ningun_mensaje_del_flujo_existente():
    """Compatibilidad: quien no pide el secreto recibe exactamente lo mismo
    que antes de esta microfase."""
    cliente = TestClient(main.app)
    creada = cliente.post("/api/partidas", json={"alias": "Ana"}).json()
    with cliente.websocket_connect(
        f"/ws/{creada['codigo']}/{creada['jugador_id']}"
    ) as ws:
        primero = ws.receive_json()
        ws.send_json({"accion": "pedir_credencial_admin"})
        segundo = ws.receive_json()
    assert primero["tipo"] == "estado_privado"
    assert segundo["tipo"] == "credencial_admin"


def test_una_difusion_general_no_entrega_el_secreto():
    """difundir() es el canal general: nunca puede llevar la credencial."""
    cliente = TestClient(main.app)
    creada = cliente.post("/api/partidas", json={"alias": "Ana"}).json()
    unida = cliente.post(
        f"/api/partidas/{creada['codigo']}/unirse", json={"alias": "Luis"}
    ).json()
    sala = main.gestor.obtener(creada["codigo"])
    with cliente.websocket_connect(
        f"/ws/{creada['codigo']}/{unida['jugador_id']}"
    ) as invitado:
        assert invitado.receive_json()["tipo"] == "estado_privado"
        # Entra un tercer jugador: el servidor ejecuta difundir() y empuja
        # el estado a todas las conexiones de la sala.
        cliente.post(
            f"/api/partidas/{creada['codigo']}/unirse", json={"alias": "Marta"}
        )
        recibidos = [invitado.receive_json()]
    assert sala.credencial_admin not in repr(recibidos)
    assert all(m.get("tipo") != "credencial_admin" for m in recibidos)


# --- La credencial no viaja en la URL ------------------------------------


def test_el_secreto_no_forma_parte_de_la_url_del_websocket():
    ruta = [linea for linea in main.app.routes if getattr(linea, "path", "") == "/ws/{codigo}/{jugador_id}"]
    assert ruta, "la ruta del WebSocket debe seguir siendo solo código y jugador"
    assert "credencial" not in ruta[0].path
    assert "admin" not in ruta[0].path


def test_el_cliente_no_manda_la_credencial_en_la_url():
    fuente = (RAIZ / "app" / "static" / "js" / "sala.js").read_text(encoding="utf-8")
    construccion = fuente[
        fuente.index("new WebSocket(") : fuente.index(");", fuente.index("new WebSocket("))
    ]
    assert "/ws/" in construccion
    assert "credencial" not in construccion
    assert "admin" not in construccion


def test_el_cliente_pide_el_secreto_solo_si_es_anfitrion_y_no_lo_tiene():
    """Lo pide una vez y solo si le falta; la microfase 1 no añade botones."""
    fuente = (RAIZ / "app" / "static" / "js" / "sala.js").read_text(encoding="utf-8")
    assert 'accion: "pedir_credencial_admin"' in fuente
    assert '!sessionStorage.getItem("credencial_admin")' in fuente
    assert 'sessionStorage.setItem("credencial_admin"' in fuente
    assert 'mensaje.sala.credencial_admin' not in fuente


def test_ningun_otro_endpoint_expone_el_secreto():
    cliente = TestClient(main.app)
    creada = cliente.post("/api/partidas", json={"alias": "Ana"}).json()
    sala = main.gestor.obtener(creada["codigo"])
    for url in ("/api/personajes", "/api/recursos", "/api/tablero"):
        assert sala.credencial_admin not in cliente.get(url).text
    assert sala.credencial_admin not in cliente.get("/").text


# --- Compatibilidad: no se altera el juego ------------------------------


def test_secreto_es_independiente_del_reloj_y_del_misterio():
    """El secreto no se deriva de nada que ya exista: es aleatorio puro."""
    sala, anfitrion, _ = sala_iniciada()
    otro = Sala(sala.codigo, modo=MODO_RAPIDO)
    assert otro.credencial_admin != sala.credencial_admin
    assert otro.credencial_admin_resumen


def test_la_comparacion_usa_tiempo_constante():
    """No se compara el secreto en claro, sino su resumen SHA-256."""
    fuente = (RAIZ / "app" / "motor" / "sala.py").read_text(encoding="utf-8")
    assert "secrets.compare_digest" in fuente
    bloque = fuente[
        fuente.index("def credencial_admin_valida") : fuente.index("def exigir_credencial_admin")
    ]
    assert (
        "secrets.compare_digest(\n"
        "            resumen_credencial_admin(credencial), self.credencial_admin_resumen"
    ) in bloque


def test_el_plazo_de_inactividad_no_cambia():
    """Microfase 1 no toca los tiempos: siguen en 60 s."""
    from app.motor.sala import INACTIVIDAD_BLOQUEO_SEGUNDOS

    sala, anfitrion, _ = sala_iniciada()
    sala.turno_actual = sala.orden_turnos.index(anfitrion["id"])
    sala.marcar_bloqueo()
    assert INACTIVIDAD_BLOQUEO_SEGUNDOS == 60.0
    assert 0 < sala.bloqueo_deadline - time.monotonic() <= 60.0
