"""Microfase 6 · Cargar partida desde la portada.

Contrato:
- El anfitrión recupera SU identidad: mismo jugador_id, misma credencial,
  mismo personaje, misma mano, misma hoja y mismos permisos.
- No se reparte nada ni se crea un jugador nuevo.
- Las tareas NO se reactivan al cargar: eso pasa al abrir la sala.
- Un archivo inválido no deja sala a medias ni pisa una partida viva.
- La credencial del archivo solo vale para la copia que restaura.
"""
import json
import time

import pytest
from fastapi.testclient import TestClient

from app import main
from app.motor import persistencia
from app.motor.sala import ESTADO_TERMINADA, JUGADA_ESPERANDO_REFUTADOR, TIPO_PNJ


@pytest.fixture(autouse=True)
def limpiar_registros():
    tablas = (
        main.gestor.salas,
        main.conexiones,
        main.cerrojos,
        main.tareas_pnj,
        main.tareas_refutacion,
        main.tareas_presentacion,
        main.tareas_bloqueo,
    )
    for tabla in tablas:
        tabla.clear()
    yield
    for tabla in tablas:
        tabla.clear()


@pytest.fixture
def cliente():
    return TestClient(main.app)


def partida_lista(modo="tablero"):
    sala, anfitrion = main.gestor.crear_sala("Ana", modo)
    _, invitado = main.gestor.unirse(sala.codigo, "Luis")
    sala.elegir_personaje(anfitrion["id"], "vera")
    sala.elegir_personaje(invitado["id"], "bruno")
    sala.iniciar(anfitrion["id"])
    return sala, anfitrion, invitado


def archivo_de(sala) -> str:
    return persistencia.a_json(persistencia.exportar(sala))


def cargar(cliente, texto):
    return cliente.post(
        "/api/cargar",
        content=texto,
        headers={"Content-Type": "application/json"},
    )


# --- Carga válida --------------------------------------------------------


def test_la_pantalla_inicial_tiene_el_boton_y_el_popup(cliente):
    pagina = cliente.get("/").text
    assert 'id="btn-cargar"' in pagina
    assert "CARGAR PARTIDA" in pagina
    assert 'id="modal-cargar"' in pagina
    assert 'id="archivo-partida"' in pagina
    assert 'type="file"' in pagina
    assert 'id="btn-confirmar-cargar"' in pagina
    assert 'id="btn-cancelar-cargar"' in pagina
    # Y el botón está junto a los otros dos, no en un sitio aparte.
    assert pagina.index('id="btn-cargar"') < pagina.index('portada-menu-secundario')


def test_cargar_un_archivo_valido_devuelve_la_sala(cliente):
    sala, anfitrion, _ = partida_lista()
    respuesta = cargar(cliente, archivo_de(sala))
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["codigo"] in main.gestor.salas
    assert datos["sala"]["modo"] == "tablero"
    assert datos["sala"]["estado"] == "iniciada"
    assert datos["resumen"]["anfitrion"] == "Ana"


def test_el_anfitrion_recupera_su_identidad_original(cliente):
    sala, anfitrion, _ = partida_lista()
    respuesta = cargar(cliente, archivo_de(sala))
    datos = respuesta.json()
    assert datos["jugador_id"] == anfitrion["id"]
    assert datos["alias"] == "Ana"
    assert datos["credencial_admin"] == sala.credencial_admin


def test_recupera_credencial_y_permisos(cliente):
    sala, anfitrion, _ = partida_lista()
    cargada = cargar(cliente, archivo_de(sala)).json()
    nueva = main.gestor.obtener(cargada["codigo"])
    # La credencial sirve para administrar SU sala.
    nueva.exigir_credencial_admin(cargada["jugador_id"], cargada["credencial_admin"])
    assert nueva.es_anfitrion(cargada["jugador_id"])
    # Y solo ahí: no vale para otra sala distinta.
    otra, _, _ = partida_lista()
    assert not otra.credencial_admin_valida(cargada["credencial_admin"])


def test_conserva_cartas_hoja_y_historial(cliente):
    sala, anfitrion, invitado = partida_lista()
    libre = next(
        carta
        for carta in sala.hoja_investigacion(anfitrion["id"])
        if carta["estado"] not in ("la_tengo", "vista")
    )
    sala.marcar_investigacion(anfitrion["id"], libre["id"], "descartada")
    sala._registrar_historial_sospecha(
        investigador_id=anfitrion["id"],
        sospecha={"sospechoso_id": "lucia", "lugar_id": "parador", "objeto_id": "baul-imperial"},
        resultado="refutada",
        refutador_id=invitado["id"],
    )

    cargada = cargar(cliente, archivo_de(sala)).json()
    nueva = main.gestor.obtener(cargada["codigo"])
    assert nueva.manos[anfitrion["id"]] == sala.manos[anfitrion["id"]]
    assert nueva.descartes[anfitrion["id"]] == {libre["id"]}
    assert nueva.historial == sala.historial
    assert nueva.secuencia_historial == 1
    assert (
        nueva.hoja_investigacion(anfitrion["id"])
        == sala.hoja_investigacion(anfitrion["id"])
    )


def test_conserva_los_pnj_sin_repartir(cliente):
    sala, anfitrion, _ = partida_lista()
    antes = {j["id"]: len(sala.manos[j["id"]]) for j in sala.jugadores}
    cargada = cargar(cliente, archivo_de(sala)).json()
    nueva = main.gestor.obtener(cargada["codigo"])
    despues = {j["id"]: len(nueva.manos[j["id"]]) for j in nueva.jugadores}
    assert despues == antes
    assert sum(1 for j in nueva.jugadores if j["tipo"] == TIPO_PNJ) == 4
    assert nueva.misterio == sala.misterio


def test_el_anfitrion_mantiene_su_personaje(cliente):
    sala, anfitrion, _ = partida_lista()
    cargada = cargar(cliente, archivo_de(sala)).json()
    nueva = main.gestor.obtener(cargada["codigo"])
    asiento = nueva.jugador_por_id(cargada["jugador_id"])
    assert asiento["personaje_id"] == "vera"
    assert asiento["es_anfitrion"] is True
    assert asiento["tipo"] == "humano"


def test_no_se_crea_ningun_jugador_nuevo(cliente):
    sala, anfitrion, _ = partida_lista()
    cargada = cargar(cliente, archivo_de(sala)).json()
    nueva = main.gestor.obtener(cargada["codigo"])
    assert len(nueva.jugadores) == len(sala.jugadores)
    assert [j["id"] for j in nueva.jugadores] == [j["id"] for j in sala.jugadores]


def test_la_partida_terminada_tambien_se_recupera(cliente):
    sala, anfitrion, _ = partida_lista()
    sala.estado = ESTADO_TERMINADA
    sala.resultado_final = "resuelto"
    sala.ganador_id = anfitrion["id"]
    respuesta = cargar(cliente, archivo_de(sala))
    assert respuesta.status_code == 200
    nueva = main.gestor.obtener(respuesta.json()["codigo"])
    assert nueva.estado == ESTADO_TERMINADA
    assert nueva.resultado_final == "resuelto"


# --- Pausa y reactivación ------------------------------------------------


def test_una_sala_pausada_se_recupera_pausada(cliente):
    sala, anfitrion, _ = partida_lista()
    sala.pausar_partida(anfitrion["id"], sala.credencial_admin)
    cargada = cargar(cliente, archivo_de(sala)).json()
    nueva = main.gestor.obtener(cargada["codigo"])
    assert nueva.pausada is True
    assert nueva.estado_privado(cargada["jugador_id"])["pausada"] is True


def test_cargar_no_arranca_ninguna_tarea(cliente):
    """Lo importante: nada se mueve antes de que el anfitrión entre."""
    sala, anfitrion, _ = partida_lista()
    antes = sala.numero_turno
    cargar(cliente, archivo_de(sala))
    assert main.tareas_pnj == {}
    assert main.tareas_refutacion == {}
    assert main.tareas_presentacion == {}
    assert main.tareas_bloqueo == {}
    nueva = [s for c, s in main.gestor.salas.items() if c != sala.codigo][0]
    assert nueva.numero_turno == antes
    assert nueva.presentacion_sospecha is None


def test_cargar_tampoco_reparte_ni_avanza_turnos(cliente):
    sala, anfitrion, _ = partida_lista()
    orden = list(sala.orden_turnos)
    cargada = cargar(cliente, archivo_de(sala)).json()
    nueva = main.gestor.obtener(cargada["codigo"])
    assert nueva.orden_turnos == orden
    assert nueva.turno_actual == sala.turno_actual
    assert nueva.numero_turno == sala.numero_turno


def test_las_tareas_arrancan_al_conectar_el_anfitrion(cliente):
    """Reactivación: ocurre con la conexión, no al cargar."""
    sala, anfitrion, _ = partida_lista()
    cargada = cargar(cliente, archivo_de(sala)).json()
    assert main.tareas_pnj == {}
    with cliente.websocket_connect(
        f"/ws/{cargada['codigo']}/{cargada['jugador_id']}"
    ) as ws:
        estado = ws.receive_json()["sala"]
    assert estado["pausada"] is False
    # Al reconectar, la cadena queda armada (y sola).
    assert len(main.tareas_pnj) <= 1
    for tabla in (main.tareas_pnj, main.tareas_bloqueo):
        for tarea in list(tabla.values()):
            tarea.cancel()


def test_reconectar_dos_veces_no_duplica_tareas(cliente):
    sala, anfitrion, _ = partida_lista()
    cargada = cargar(cliente, archivo_de(sala)).json()
    for _ in range(2):
        with cliente.websocket_connect(
            f"/ws/{cargada['codigo']}/{cargada['jugador_id']}"
        ) as ws:
            ws.receive_json()
    assert len(main.tareas_pnj) <= 1
    for tabla in (main.tareas_pnj, main.tareas_bloqueo):
        for tarea in list(tabla.values()):
            tarea.cancel()


def test_una_sala_pausada_no_arranca_tareas_al_conectar(cliente):
    sala, anfitrion, _ = partida_lista()
    sala.pausar_partida(anfitrion["id"], sala.credencial_admin)
    cargada = cargar(cliente, archivo_de(sala)).json()
    with cliente.websocket_connect(
        f"/ws/{cargada['codigo']}/{cargada['jugador_id']}"
    ) as ws:
        assert ws.receive_json()["sala"]["pausada"] is True
    assert main.tareas_pnj == {}
    assert main.tareas_bloqueo == {}


def test_la_refutacion_pendiente_sobrevive_a_la_carga(cliente):
    sala, anfitrion, invitado = partida_lista()
    # La sospecha usa una carta que el invitado tiene de verdad, para que
    # el reparto siga cuadrando como en una partida real.
    suya = sala.manos[invitado["id"]][0]
    sala.sospecha_pendiente = {
        "investigador_id": anfitrion["id"],
        "refutador_id": invitado["id"],
        "sospecha": {"sospechoso_id": suya["id"]},
        "coincidencias": [suya["id"]],
    }
    sala.estado_jugada = JUGADA_ESPERANDO_REFUTADOR
    sala.refutacion_deadline = time.monotonic() + 10.0

    cargada = cargar(cliente, archivo_de(sala)).json()
    nueva = main.gestor.obtener(cargada["codigo"])
    assert nueva.sospecha_pendiente is not None
    assert nueva.estado_jugada == JUGADA_ESPERANDO_REFUTADOR
    assert nueva.refutacion_deadline is not None


# --- Conflictos ----------------------------------------------------------


def test_si_el_codigo_esta_ocupado_se_reenumeria(cliente):
    sala, anfitrion, _ = partida_lista()
    respuesta = cargar(cliente, archivo_de(sala))
    datos = respuesta.json()
    assert datos["codigo_reenumerado"] is True
    assert datos["codigo_original"] == sala.codigo
    assert datos["codigo"] != sala.codigo
    # Y la partida viva sigue intacta.
    assert main.gestor.obtener(sala.codigo) is sala
    assert main.gestor.obtener(sala.codigo).credencial_admin == sala.credencial_admin


def test_reenumerar_no_rompe_los_identificadores(cliente):
    sala, anfitrion, _ = partida_lista()
    datos = cargar(cliente, archivo_de(sala)).json()
    nueva = main.gestor.obtener(datos["codigo"])
    # Cambia el código, no las personas.
    assert nueva.jugador_por_id(anfitrion["id"]) is not None
    assert nueva.anfitrion()["id"] == anfitrion["id"]


def test_cargar_el_archivo_dos_veces(cliente):
    sala, anfitrion, _ = partida_lista()
    texto = archivo_de(sala)
    primera = cargar(cliente, texto).json()
    segunda = cargar(cliente, texto).json()
    assert primera["codigo"] != segunda["codigo"]
    assert primera["jugador_id"] == segunda["jugador_id"]
    assert primera["credencial_admin"] == segunda["credencial_admin"]
    assert len(main.gestor.salas) == 3


# --- Archivos inválidos --------------------------------------------------


def test_un_cuerpo_vacio_se_rechaza(cliente):
    respuesta = cargar(cliente, "")
    assert respuesta.status_code == 400
    assert "archivo" in respuesta.json()["detalle"].lower()


def test_un_json_roto_se_rechaza(cliente):
    respuesta = cargar(cliente, "{esto no es json")
    assert respuesta.status_code == 400
    assert "JSON" in respuesta.json()["detalle"]


def test_un_archivo_demasiado_grande_se_rechaza(cliente):
    relleno = "x" * (main.TAMANO_MAXIMO_CARGA + 1024)
    respuesta = cargar(cliente, '{"formato":"' + relleno + '"}')
    assert respuesta.status_code == 413
    assert "grande" in respuesta.json()["detalle"].lower()


def test_un_archivo_corrupto_se_rechaza(cliente):
    sala, _, _ = partida_lista()
    datos = json.loads(archivo_de(sala))
    datos["estado"]["numero_turno"] = 999
    respuesta = cargar(cliente, json.dumps(datos))
    assert respuesta.status_code == 400
    assert "dañado" in respuesta.json()["detalle"]


def test_una_version_futura_se_rechaza(cliente):
    sala, _, _ = partida_lista()
    datos = json.loads(archivo_de(sala))
    datos["version"] = 99
    datos["integridad"]["valor"] = persistencia.huella(datos["estado"])
    respuesta = cargar(cliente, json.dumps(datos))
    assert respuesta.status_code == 400
    assert "versión" in respuesta.json()["detalle"].lower()


def test_un_archivo_de_otro_juego_se_rechaza(cliente):
    respuesta = cargar(cliente, json.dumps({"formato": "ajedrez/partida", "version": 1}))
    assert respuesta.status_code == 400


def test_una_carta_inventada_se_rechaza(cliente):
    sala, _, _ = partida_lista()
    datos = json.loads(archivo_de(sala))
    next(iter(datos["estado"]["manos"].values()))[0] = {
        "id": "fantasma",
        "nombre": "Fantasma",
        "categoria": "lugar",
    }
    datos["integridad"]["valor"] = persistencia.huella(datos["estado"])
    respuesta = cargar(cliente, json.dumps(datos))
    assert respuesta.status_code == 400


def test_un_archivo_rechazado_no_deja_sala_ni_toca_las_vivas(cliente):
    sala, _, _ = partida_lista()
    antes = set(main.gestor.salas)
    credencial = sala.credencial_admin
    respuesta = cargar(cliente, "{roto")
    assert respuesta.status_code == 400
    assert set(main.gestor.salas) == antes
    assert sala.credencial_admin == credencial
    assert main.tareas_pnj == {}


def test_los_errores_no_filtran_cartas_ni_credenciales(cliente):
    sala, anfitrion, _ = partida_lista()
    datos = json.loads(archivo_de(sala))
    datos["estado"]["velocidad_acciones"] = 99
    datos["integridad"]["valor"] = persistencia.huella(datos["estado"])
    respuesta = cargar(cliente, json.dumps(datos))
    detalle = respuesta.json()["detalle"]
    assert sala.credencial_admin not in detalle
    assert sala.misterio["objeto"]["id"] not in detalle
    for carta in sala.manos[anfitrion["id"]]:
        assert carta["nombre"] not in detalle
    # La respuesta tampoco lleva la sala ni su contenido.
    assert "sala" not in respuesta.json()
    assert "credencial_admin" not in respuesta.json()


def test_la_credencial_del_archivo_no_abre_otra_sala(cliente):
    """Tener el archivo autoriza a restaurar ESA copia, no a mandar en otra."""
    sala, anfitrion, _ = partida_lista()
    cargada = cargar(cliente, archivo_de(sala)).json()
    otra, _, _ = partida_lista()
    # El archivo de la sala A (y el de la copia restaurada) no abren la B.
    assert cargada["credencial_admin"] == sala.credencial_admin
    assert not otra.credencial_admin_valida(cargada["credencial_admin"])
    respuesta = cliente.get(
        f"/api/partidas/{otra.codigo}/guardar",
        headers={"X-Token-Admin": cargada["credencial_admin"]},
    )
    assert respuesta.status_code == 403


def test_el_mensaje_de_error_no_dice_si_el_archivo_es_valido(cliente):
    """Un rechazo no confirma que el resto del archivo esté bien."""
    sala, _, _ = partida_lista()
    datos = json.loads(archivo_de(sala))
    datos["estado"]["misterio"] = None
    datos["integridad"]["valor"] = persistencia.huella(datos["estado"])
    respuesta = cargar(cliente, json.dumps(datos))
    detalle = respuesta.json()["detalle"].lower()
    assert "credencial" not in detalle
    assert "firma" not in detalle
