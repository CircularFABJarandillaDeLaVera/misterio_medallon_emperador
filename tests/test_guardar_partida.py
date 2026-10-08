"""Microfase 4 · Guardado de partida (SOLO exportación).

Contrato:
- Lista blanca explícita y cerrada: lo que no está, no se guarda.
- La exportación NO muta la sala (ni un solo campo).
- Los tiempos se guardan como RESTANTE, nunca como instantes absolutos.
- El archivo lleva la credencial del anfitrión: quien lo tiene, es anfitrión
  en cualquier ordenador.
- Solo el anfitrión descarga, con la credencial en CABECERA, nunca en la URL.
- El contenido confidencial nunca sale por WebSocket ni en estado público.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app import main
from app.motor import persistencia
from app.motor.sala import (
    ESTADO_TERMINADA,
    MENSAJE_SIN_AUTORIDAD_ADMIN,
    TIPO_HUMANO,
    TIPO_PNJ,
)


@pytest.fixture(autouse=True)
def limpiar_registros():
    for tabla in (
        main.gestor.salas,
        main.conexiones,
        main.cerrojos,
        main.tareas_pnj,
        main.tareas_refutacion,
        main.tareas_presentacion,
        main.tareas_bloqueo,
    ):
        tabla.clear()
    yield
    for tabla in (
        main.gestor.salas,
        main.conexiones,
        main.cerrojos,
        main.tareas_pnj,
        main.tareas_refutacion,
        main.tareas_presentacion,
        main.tareas_bloqueo,
    ):
        tabla.clear()


def sala_en_curso(modo="tablero"):
    sala, anfitrion = main.gestor.crear_sala("Ana", modo)
    _, invitado = main.gestor.unirse(sala.codigo, "Luis")
    sala.elegir_personaje(anfitrion["id"], "vera")
    sala.elegir_personaje(invitado["id"], "bruno")
    sala.iniciar(anfitrion["id"])
    return sala, anfitrion, invitado


def descarga(cliente, codigo, credencial, **kwargs):
    return cliente.get(
        f"/api/partidas/{codigo}/guardar",
        headers={"X-Token-Admin": credencial} if credencial is not None else {},
        **kwargs,
    )


# --- Formato -------------------------------------------------------------


def test_el_archivo_se_identifica_y_versiona():
    sala, _, _ = sala_en_curso()
    datos = persistencia.exportar(sala)
    assert datos["formato"] == "misterio-medallon/partida"
    assert datos["version"] == 1
    assert datos["generado"].endswith("+00:00")
    assert isinstance(datos["resumen"], dict)
    assert "valor" in datos["integridad"]


def test_el_resumen_es_legible_y_no_trae_secretos():
    sala, anfitrion, _ = sala_en_curso()
    resumen = persistencia.exportar(sala)["resumen"]
    assert resumen["codigo"] == sala.codigo
    assert resumen["modo"] == "tablero"
    assert resumen["participantes"] == len(sala.jugadores)
    assert resumen["humanos"] == 2
    assert resumen["anfitrion"] == "Ana"
    assert resumen["velocidad_acciones"] == 3
    texto = json.dumps(resumen, ensure_ascii=False)
    assert sala.credencial_admin not in texto
    for jugador in sala.jugadores:
        assert jugador["id"] not in texto


def test_el_json_es_texto_plano_y_reconstruible():
    sala, _, _ = sala_en_curso()
    datos = persistencia.exportar(sala)
    texto = persistencia.a_json(datos)
    assert json.loads(texto) == datos
    # Sin pickle ni nada ejecutable: solo JSON.
    assert "pickle" not in texto and "__reduce__" not in texto


def test_el_nombre_de_archivo_usa_el_codigo():
    assert persistencia.nombre_archivo("JARA-ABCD") == "misterio-medallon-JARA-ABCD.json"
    assert persistencia.nombre_archivo("JARA-A/B") == "misterio-medallon-JARA-AB.json"
    assert persistencia.nombre_archivo("") == "misterio-medallon-sala.json"


# --- Lista blanca: se guarda todo lo importante --------------------------


def test_se_guarda_el_reparto_y_las_identidades():
    sala, anfitrion, _ = sala_en_curso()
    estado = persistencia.exportar(sala)["estado"]
    assert estado["codigo"] == sala.codigo
    assert estado["modo"] == sala.modo
    assert estado["estado"] == sala.estado
    assert estado["estado_jugada"] == sala.estado_jugada
    assert [j["id"] for j in estado["jugadores"]] == [j["id"] for j in sala.jugadores]
    for guardado, original in zip(estado["jugadores"], sala.jugadores):
        for campo in persistencia.CAMPOS_DE_JUGADOR:
            assert guardado[campo] == original[campo]
    assert estado["orden_turnos"] == sala.orden_turnos
    assert estado["turno_actual"] == sala.turno_actual
    assert estado["numero_turno"] == sala.numero_turno


def test_se_guarda_la_solucion_y_las_manos():
    sala, anfitrion, _ = sala_en_curso()
    estado = persistencia.exportar(sala)["estado"]
    assert estado["misterio"] == sala.misterio
    assert set(estado["manos"]) == set(sala.manos)
    for jugador_id, cartas in sala.manos.items():
        assert estado["manos"][jugador_id] == cartas


def test_se_guardan_investigacion_vistas_y_deducciones():
    sala, anfitrion, invitado = sala_en_curso()
    # Una carta que el invitado NO tiene en la mano, para poder descartarla.
    ajena = next(
        carta
        for carta in sala.hoja_investigacion(invitado["id"])
        if carta["estado"] not in ("la_tengo", "vista")
    )
    sala.marcar_investigacion(invitado["id"], ajena["id"], "descartada")
    sala.vistas[anfitrion["id"]].add("parador")
    sala.soluciones_deducidas["pnj-vera"] = {
        "sospechoso_id": "lucia",
        "lugar_id": "parador",
        "objeto_id": "baul-imperial",
    }
    estado = persistencia.exportar(sala)["estado"]
    assert estado["descartes"][invitado["id"]] == [ajena["id"]]
    assert sorted(estado["vistas"][anfitrion["id"]]) == ["parador"]
    assert estado["soluciones_deducidas"]["pnj-vera"]["sospechoso_id"] == "lucia"


def test_se_guarda_el_tablero_y_las_piezas():
    sala, _, _ = sala_en_curso()
    estado = persistencia.exportar(sala)["estado"]
    for jugador in sala.jugadores:
        assert estado["posiciones"][jugador["id"]] == sala.posiciones.obtener(jugador["id"])
    assert estado["posiciones_objetos"] == dict(sala.posiciones_objetos)


def test_se_guardan_las_tuplas_de_ruta_como_listas():
    sala, anfitrion, _ = sala_en_curso()
    sala.rutas_pendientes[anfitrion["id"]] = ("casilla-1", "casilla-2")
    estado = persistencia.exportar(sala)["estado"]
    assert estado["rutas_pendientes"][anfitrion["id"]] == ["casilla-1", "casilla-2"]
    # Y el JSON sigue siendo válido.
    json.loads(persistencia.a_json(persistencia.exportar(sala)))


def test_se_guardan_sospecha_presentacion_y_acusacion():
    sala, anfitrion, invitado = sala_en_curso()
    sala.estado_jugada = "esperando_sospecha"
    sala.turno_actual = sala.orden_turnos.index(anfitrion["id"])
    sala.formular_sospecha(
        anfitrion["id"], "lucia", "parador", "baul-imperial", ahora=1000.0
    )
    estado = persistencia.exportar(sala, ahora=1001.0)["estado"]
    assert estado["presentacion_sospecha"]["id"] == sala.presentacion_sospecha["id"]
    assert estado["presentacion_sospecha"]["sospecha"]["sospechoso_id"] == "lucia"
    assert estado["presentacion_sospecha"]["inicio_restante"] == pytest.approx(1.0)

    # Con refutación pendiente, y con el resultado ya abierto.
    sala.sospecha_pendiente = {
        "investigador_id": anfitrion["id"],
        "refutador_id": invitado["id"],
        "sospecha": {"sospechoso_id": "lucia"},
        "coincidencias": ["parador"],
    }
    estado = persistencia.exportar(sala, ahora=1002.0)["estado"]
    assert estado["sospecha_pendiente"]["coincidencias"] == ["parador"]

    sala._abrir_presentacion_resultado(
        investigador_id=anfitrion["id"],
        investigador_alias="Ana",
        sospecha={"sospechoso_id": "lucia"},
        resultado="refutada",
        refutador_alias="Luis",
        ahora=1100.0,
    )
    estado = persistencia.exportar(sala, ahora=1105.0)["estado"]
    assert estado["presentacion_sospecha"]["tipo"] == "resultado"
    assert estado["presentacion_sospecha"]["resultado"] == "refutada"
    assert estado["presentacion_sospecha"]["refutador_alias"] == "Luis"


def test_se_guardan_historial_y_contadores():
    sala, anfitrion, _ = sala_en_curso()
    sala.historial.append({"id": 1, "turno": 1, "resultado": "refutada"})
    sala.secuencia_historial = 1
    sala.cartas_sospechadas.add("lucia")
    sala.secuencia_movimiento = 7
    sala.secuencia_presentacion = 3
    estado = persistencia.exportar(sala)["estado"]
    assert estado["historial"] == sala.historial
    assert estado["secuencia_historial"] == 1
    assert estado["cartas_sospechadas"] == ["lucia"]
    assert estado["secuencia_movimiento"] == 7
    assert estado["secuencia_presentacion"] == 3


def test_se_guardan_el_final_y_el_estado_de_pausa():
    sala, anfitrion, _ = sala_en_curso()
    sala.ralentizar_acciones(anfitrion["id"], sala.credencial_admin)
    sala.pausar_partida(anfitrion["id"], sala.credencial_admin, ahora=1900.0)
    estado = persistencia.exportar(sala, ahora=2000.0)["estado"]
    assert estado["velocidad_acciones"] == 4
    assert estado["pausa"] == {"pausada": True, "duracion": pytest.approx(100.0)}
    assert "jugador_id" in estado["bloqueo"]
    assert "aviso_emitido" in estado["bloqueo"]

    # Y el final de partida, con el estado en el que esté.
    sala.estado = ESTADO_TERMINADA
    sala.resultado_final = "resuelto"
    sala.ganador_id = anfitrion["id"]
    estado = persistencia.exportar(sala, ahora=2010.0)["estado"]
    assert estado["estado"] == ESTADO_TERMINADA
    assert estado["resultado_final"] == "resuelto"
    assert estado["ganador_id"] == anfitrion["id"]


def test_se_guardan_los_pnj_con_su_identidad():
    sala, _, _ = sala_en_curso()
    estado = persistencia.exportar(sala)["estado"]
    pnj = [j for j in estado["jugadores"] if j["tipo"] == TIPO_PNJ]
    assert len(pnj) == 4
    assert all(j["id"].startswith("pnj-") for j in pnj)
    assert all(j["personaje_id"] for j in pnj)
    # Los PNJ no tienen credencial propia: la de la sala es única.
    assert estado["credencial_admin"] == sala.credencial_admin


def test_se_guarda_la_credencial_del_anfitrion():
    sala, _, _ = sala_en_curso()
    estado = persistencia.exportar(sala)["estado"]
    assert estado["credencial_admin"] == sala.credencial_admin
    assert len(estado["credencial_admin"]) >= 40


def test_no_se_guarda_nada_fuera_de_la_lista_blanca():
    sala, anfitrion, _ = sala_en_curso()
    sala.atributo_inventado = "no debe viajar"
    sala.jugadores[0]["atributo_inventado"] = "tampoco"
    estado = persistencia.exportar(sala)["estado"]
    assert "atributo_inventado" not in estado
    assert all("atributo_inventado" not in j for j in estado["jugadores"])
    assert set(estado) == set(persistencia.CLAVES_OBLIGATORIAS_ESTADO) | {
        campo for campo in persistencia.CAMPOS_DE_SALA
    }


def test_los_conjuntos_se_guardan_ordenados():
    sala, anfitrion, _ = sala_en_curso()
    sala.vistas[anfitrion["id"]].update({"parador", "ermita-sopetran"})
    estado = persistencia.exportar(sala)["estado"]
    assert estado["vistas"][anfitrion["id"]] == ["ermita-sopetran", "parador"]


# --- La exportación no toca la partida ----------------------------------


def test_exportar_no_muta_la_sala():
    sala, anfitrion, _ = sala_en_curso()
    sala.estado_jugada = "esperando_movimiento"
    sala.turno_actual = sala.orden_turnos.index(anfitrion["id"])
    sala.marcar_bloqueo()
    sala.sospecha_pendiente = {
        "investigador_id": anfitrion["id"],
        "refutador_id": next(j["id"] for j in sala.jugadores if j["tipo"] == TIPO_HUMANO and j["id"] != anfitrion["id"]),
        "sospecha": {},
        "coincidencias": ["parador"],
    }
    sala.estado_jugada = "esperando_eleccion_refutador"
    sala.refutacion_deadline = 12345.678
    sala.espera_pnj_en_curso = {"segundos": 3.0, "inicio": 1000.0}

    antes = {
        "estado": sala.estado,
        "estado_jugada": sala.estado_jugada,
        "numero_turno": sala.numero_turno,
        "refutacion": sala.refutacion_deadline,
        "bloqueo": sala.bloqueo_deadline,
        "espera": dict(sala.espera_pnj_en_curso),
        "velocidad": sala.velocidad_acciones,
        "manos": {k: len(v) for k, v in sala.manos.items()},
    }
    persistencia.exportar(sala)
    assert sala.estado == antes["estado"]
    assert sala.estado_jugada == antes["estado_jugada"]
    assert sala.numero_turno == antes["numero_turno"]
    assert sala.refutacion_deadline == antes["refutacion"]
    assert sala.bloqueo_deadline == antes["bloqueo"]
    assert sala.espera_pnj_en_curso == antes["espera"]
    assert sala.velocidad_acciones == antes["velocidad"]
    assert {k: len(v) for k, v in sala.manos.items()} == antes["manos"]


def test_exportar_no_enciende_ni_apaga_la_pausa():
    sala, anfitrion, _ = sala_en_curso()
    sala.pausar_partida(anfitrion["id"], sala.credencial_admin)
    marca = sala.pausa_marca
    persistencia.exportar(sala)
    assert sala.pausada is True
    assert sala.pausa_marca == marca


def test_las_copias_no_se_comparten_con_la_sala():
    sala, anfitrion, _ = sala_en_curso()
    estado = persistencia.exportar(sala)["estado"]
    estado["manos"][anfitrion["id"]].append({"id": "inventada"})
    estado["jugadores"][0]["alias"] = "CAMBIADO"
    estado["historial"].append("contaminado")
    assert all(carta["id"] != "inventada" for carta in sala.manos[anfitrion["id"]])
    assert sala.jugadores[0]["alias"] == "Ana"
    assert sala.historial == []


# --- Tiempos como restante, no como fechas absolutas --------------------


def test_los_tiempos_se_guardan_como_restante():
    sala, anfitrion, _ = sala_en_curso()
    sala.refutacion_deadline = 1100.0
    sala.bloqueo_deadline = 1300.0
    estado = persistencia.exportar(sala, ahora=1050.0)["estado"]
    assert estado["refutacion_restante"] == pytest.approx(50.0)
    assert estado["bloqueo"]["restante"] == pytest.approx(250.0)


def test_un_plazo_vencido_se_guarda_en_cero_y_no_en_negativo():
    sala, anfitrion, _ = sala_en_curso()
    sala.refutacion_deadline = 900.0
    estado = persistencia.exportar(sala, ahora=1050.0)["estado"]
    assert estado["refutacion_restante"] == 0.0


def test_un_reloj_apagado_se_guarda_como_null():
    sala, anfitrion, _ = sala_en_curso()
    sala.refutacion_deadline = None
    sala.bloqueo_deadline = None
    estado = persistencia.exportar(sala)["estado"]
    assert estado["refutacion_restante"] is None
    assert estado["bloqueo"]["restante"] is None


def test_el_archivo_no_contiene_ningun_instante_de_reloj_absoluto():
    """Formato del archivo: no debe colarse ningún monotonic como número."""
    sala, anfitrion, _ = sala_en_curso()
    sala.espera_pnj_en_curso = {"segundos": 3.0, "inicio": 987654.321}
    sala.turno_pnj_espera_restante = 1.5
    sala.pausar_partida(anfitrion["id"], sala.credencial_admin)
    texto = json.dumps(persistencia.exportar(sala), ensure_ascii=False)
    assert "987654" not in texto, "ha colado el instante de la espera del PNJ"
    assert "_marca" not in texto
    assert "deadline" not in texto
    assert "monotonic" not in texto


def test_la_espera_en_curso_del_pnj_se_guarda_como_restante():
    sala, anfitrion, _ = sala_en_curso()
    sala.espera_pnj_en_curso = {"segundos": 3.0, "inicio": 1000.0}
    estado = persistencia.exportar(sala, ahora=1002.0)["estado"]
    assert estado["espera_pnj"]["restante"] == pytest.approx(1.0)


def test_el_resto_guardado_al_pausar_tambien_se_guarda():
    sala, anfitrion, _ = sala_en_curso()
    sala.turno_pnj_espera_restante = 2.25
    sala.espera_pnj_en_curso = None
    estado = persistencia.exportar(sala, ahora=1000.0)["estado"]
    assert estado["espera_pnj"]["restante"] == pytest.approx(2.25)
    assert estado["espera_pnj"]["turno_pnj_espera_restante"] == pytest.approx(2.25)


# --- Validación del formato ---------------------------------------------


def test_un_archivo_propio_valida():
    sala, _, _ = sala_en_curso()
    datos = persistencia.exportar(sala)
    estado = persistencia.validar(json.loads(persistencia.a_json(datos)))
    assert estado["codigo"] == sala.codigo


def test_validar_rechaza_un_archivo_que_no_es_una_partida():
    sala, _, _ = sala_en_curso()
    for mal in ({}, {"formato": "otro"}, {"formato": persistencia.FORMATO_PARTIDA, "version": 99}):
        with pytest.raises(ValueError):
            persistencia.validar(mal)
    with pytest.raises(ValueError):
        persistencia.validar("no soy un objeto")


def test_validar_rechaza_un_estado_incompleto():
    sala, _, _ = sala_en_curso()
    datos = persistencia.exportar(sala)
    datos["estado"].pop("misterio")
    with pytest.raises(ValueError) as error:
        persistencia.validar(datos)
    assert "misterio" in str(error.value)


def test_validar_rechaza_un_archivo_dañado():
    sala, _, _ = sala_en_curso()
    datos = persistencia.exportar(sala)
    datos["estado"]["numero_turno"] = 999
    with pytest.raises(ValueError) as error:
        persistencia.validar(datos)
    assert "dañado" in str(error.value)


def test_validar_rechaza_identidades_colgadas():
    sala, _, _ = sala_en_curso()
    datos = persistencia.exportar(sala)
    datos["estado"]["orden_turnos"].append("fantasma")
    datos["integridad"]["valor"] = persistencia.huella(datos["estado"])
    with pytest.raises(ValueError) as error:
        persistencia.validar(datos)
    assert "turnos" in str(error.value)


def test_validar_exige_un_anfitrion_y_unico():
    sala, anfitrion, _ = sala_en_curso()
    datos = persistencia.exportar(sala)
    for jugador in datos["estado"]["jugadores"]:
        jugador["es_anfitrion"] = False
    datos["integridad"]["valor"] = persistencia.huella(datos["estado"])
    with pytest.raises(ValueError):
        persistencia.validar(datos)


def test_validar_rechaza_identificadores_repetidos():
    sala, anfitrion, _ = sala_en_curso()
    datos = persistencia.exportar(sala)
    datos["estado"]["jugadores"][1]["id"] = datos["estado"]["jugadores"][0]["id"]
    datos["integridad"]["valor"] = persistencia.huella(datos["estado"])
    with pytest.raises(ValueError):
        persistencia.validar(datos)


def test_el_archivo_no_puede_ejecutar_codigo_al_validarse():
    sala, _, _ = sala_en_curso()
    datos = json.loads(persistencia.a_json(persistencia.exportar(sala)))
    datos["estado"]["__class__"] = "os.system"
    datos["estado"]["jugadores"][0]["__reduce__"] = ["rm -rf /"]
    # Solo se mira forma y tipos: validar no interpreta nada.
    with pytest.raises(ValueError):
        persistencia.validar(datos)


# --- Endpoint HTTP -------------------------------------------------------


def test_el_anfitrion_descarga_el_archivo():
    cliente = TestClient(main.app)
    creada = cliente.post("/api/partidas", json={"alias": "Ana"}).json()
    sala = main.gestor.obtener(creada["codigo"])
    respuesta = descarga(cliente, creada["codigo"], sala.credencial_admin)
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("application/json")
    assert "attachment" in respuesta.headers["content-disposition"]
    assert creada["codigo"] in respuesta.headers["content-disposition"]
    assert respuesta.headers["x-content-type-options"] == "nosniff"
    assert respuesta.headers["cache-control"] == "no-store"
    datos = respuesta.json()
    assert datos["formato"] == "misterio-medallon/partida"
    assert datos["estado"]["credencial_admin"] == sala.credencial_admin
    persistencia.validar(datos)


def test_sin_credenencial_no_se_descarga_nada():
    cliente = TestClient(main.app)
    creada = cliente.post("/api/partidas", json={"alias": "Ana"}).json()
    assert descarga(cliente, creada["codigo"], None).status_code == 403
    assert descarga(cliente, creada["codigo"], "").status_code == 403
    assert descarga(cliente, creada["codigo"], "inventada").status_code == 403


def test_el_rechazo_no_distingue_entre_error_de_credencial_y_de_rol():
    """Una credencial que no vale simplemente no vale."""
    sala, anfitrion, _ = sala_en_curso()
    for credencial in (None, "", "inventada", 0, [], {}):
        assert sala.credencial_admin_valida(credencial) is False
    assert sala.credencial_admin_valida(sala.credencial_admin) is True
    assert MENSAJE_SIN_AUTORIDAD_ADMIN == (
        "Solo el anfitrión puede administrar la partida."
    )


def test_un_invitado_no_puede_descargar_aunque_conozca_el_codigo():
    """La credencial es de la SALA y solo la tiene el anfitrión."""
    cliente = TestClient(main.app)
    creada = cliente.post("/api/partidas", json={"alias": "Ana"}).json()
    unida = cliente.post(
        f"/api/partidas/{creada['codigo']}/unirse", json={"alias": "Luis"}
    ).json()
    sala = main.gestor.obtener(creada["codigo"])
    assert "credencial_admin" not in unida
    assert descarga(cliente, creada["codigo"], unida["jugador_id"]).status_code == 403
    assert descarga(cliente, creada["codigo"], sala.credencial_admin).status_code == 200


def test_una_sala_inexistente_da_404():
    cliente = TestClient(main.app)
    assert descarga(cliente, "JARA-ZZZZ", "lo-que-sea").status_code == 404


def test_la_credencial_no_va_en_la_url():
    cliente = TestClient(main.app)
    creada = cliente.post("/api/partidas", json={"alias": "Ana"}).json()
    sala = main.gestor.obtener(creada["codigo"])
    # La ruta no admite credenciales: un query param no sirve de nada.
    respuesta = cliente.get(
        f"/api/partidas/{creada['codigo']}/guardar?token={sala.credencial_admin}"
    )
    assert respuesta.status_code == 403
    rutas = [r.path for r in main.app.routes if "guardar" in getattr(r, "path", "")]
    assert rutas == ["/api/partidas/{codigo}/guardar"]
    assert "token" not in rutas[0] and "admin" not in rutas[0]


def test_lo_descargado_no_aparece_en_ningun_estado():
    """El contenido del archivo no sale por WebSocket ni en estado público."""
    cliente = TestClient(main.app)
    creada = cliente.post(
        "/api/partidas", json={"alias": "Ana", "modo": "tablero"}
    ).json()
    unida = cliente.post(
        f"/api/partidas/{creada['codigo']}/unirse", json={"alias": "Luis"}
    ).json()
    sala = main.gestor.obtener(creada["codigo"])
    sala.elegir_personaje(creada["jugador_id"], "vera")
    sala.elegir_personaje(unida["jugador_id"], "bruno")
    sala.iniciar(creada["jugador_id"])

    with cliente.websocket_connect(
        f"/ws/{creada['codigo']}/{creada['jugador_id']}"
    ) as anfitrion:
        del_anfitrion = anfitrion.receive_json()["sala"]
    with cliente.websocket_connect(
        f"/ws/{creada['codigo']}/{unida['jugador_id']}"
    ) as invitado:
        del_invitado = invitado.receive_json()["sala"]

    with cliente.websocket_connect(
        f"/ws/{creada['codigo']}/{creada['jugador_id']}"
    ) as anfitrion:
        del_anfitrion = anfitrion.receive_json()["sala"]
    with cliente.websocket_connect(
        f"/ws/{creada['codigo']}/{unida['jugador_id']}"
    ) as invitado:
        del_invitado = invitado.receive_json()["sala"]

    for estado, propio_id, otro_id in (
        (del_anfitrion, creada["jugador_id"], unida["jugador_id"]),
        (del_invitado, unida["jugador_id"], creada["jugador_id"]),
    ):
        recibido = json.dumps(estado, ensure_ascii=False)
        # Ni la credencial administrativa...
        assert sala.credencial_admin not in recibido
        assert "credencial_admin" not in recibido
        # ...ni la solución, que solo se publica al terminar.
        assert "solucion" not in estado
        # ...ni la mano del otro: cada uno ve la suya y solo la suya.
        propias = {carta["id"] for carta in estado["mis_cartas"]}
        ajenas = {carta["id"] for carta in sala.manos[otro_id]}
        assert not (propias & ajenas), "una carta ajena se ha filtrado"
        assert propias <= {carta["id"] for carta in sala.manos[propio_id]}
        # La hoja no marca como propia ninguna carta que no lo sea.
        marcadas = {
            carta["id"] for carta in estado["investigacion"]
            if carta["estado"] == "la_tengo"
        }
        assert marcadas == propias

    publico = cliente.get(f"/api/partidas/{creada['codigo']}").text
    assert sala.credencial_admin not in publico
    assert "credencial_admin" not in publico
    assert "solucion" not in publico


def test_descargar_no_muta_la_partida():
    cliente = TestClient(main.app)
    creada = cliente.post("/api/partidas", json={"alias": "Ana", "modo": "tablero"}).json()
    sala = main.gestor.obtener(creada["codigo"])
    sala.elegir_personaje(creada["jugador_id"], "vera")
    sala.iniciar(creada["jugador_id"])
    antes = (sala.estado, sala.estado_jugada, sala.numero_turno, sala.velocidad_acciones)
    descarga(cliente, creada["codigo"], sala.credencial_admin)
    assert (sala.estado, sala.estado_jugada, sala.numero_turno, sala.velocidad_acciones) == antes


def test_el_archivo_deja_la_partida_jugable_despues_de_guardar():
    """Guardar no consume turnos ni resortea nada."""
    cliente = TestClient(main.app)
    creada = cliente.post("/api/partidas", json={"alias": "Ana", "modo": "tablero"}).json()
    sala = main.gestor.obtener(creada["codigo"])
    sala.elegir_personaje(creada["jugador_id"], "vera")
    sala.iniciar(creada["jugador_id"])
    assert len(sala.jugadores) == 6
    assert all(sala.manos[j["id"]] for j in sala.jugadores)
    assert sala.estado == "iniciada"
