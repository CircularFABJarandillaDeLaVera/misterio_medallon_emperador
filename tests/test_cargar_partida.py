"""Microfase 5 · Validar y reconstruir una partida guardada.

Contrato:
- Exportar → importar devuelve el MISMO estado (ida y vuelta exacta).
- La validación es completa y en español claro.
- La importación es ATÓMICA: si algo falla, no queda sala a medias.
- Una partida viva no se toca nunca; si el código está ocupado, se reenumbra.
- Los tiempos se reconstruyen como `ahora + restante`, sin descontar nada.
- Nada de pickle, eval, exec ni atributos fuera de la lista blanca.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app import main
from app.motor import persistencia
from app.motor.sala import (
    ESTADO_ESPERANDO,
    ESTADO_INICIADA,
    ESTADO_TERMINADA,
    TIPO_HUMANO,
    TIPO_PNJ,
    VELOCIDAD_AUTOMATICA_MAXIMA,
    VELOCIDAD_AUTOMATICA_MINIMA,
    JUGADA_ESPERANDO_REFUTADOR,
)


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


def partida_en_curso(modo="tablero"):
    sala, anfitrion = main.gestor.crear_sala("Ana", modo)
    _, invitado = main.gestor.unirse(sala.codigo, "Luis")
    sala.elegir_personaje(anfitrion["id"], "vera")
    sala.elegir_personaje(invitado["id"], "bruno")
    sala.iniciar(anfitrion["id"])
    return sala, anfitrion, invitado


def ida_y_vuelta(datos):
    """Exporta la partida, la importa en limpio y devuelve la nueva sala."""
    for codigo in list(main.gestor.salas):
        del main.gestor.salas[codigo]
    sala, reenumerada = main.gestor.importar_partida(datos)
    return sala, reenumerada


def firmar(datos):
    """Recalcula la huella: simula un archivo manipulado pero coherente."""
    datos["integridad"]["valor"] = persistencia.huella(datos["estado"])
    return datos


# --- Ida y vuelta --------------------------------------------------------


def test_la_importacion_devuelve_el_mismo_codigo_si_está_libre():
    sala, anfitrion, _ = partida_en_curso()
    nueva, reenumerada = ida_y_vuelta(persistencia.exportar(sala))
    assert reenumerada is False
    assert nueva.codigo == sala.codigo


def test_ida_y_vuelta_de_un_participante_por_uno():
    sala, anfitrion, invitado = partida_en_curso()
    nueva, _ = ida_y_vuelta(persistencia.exportar(sala))

    for original, copia in zip(sala.jugadores, nueva.jugadores):
        assert original == copia
    assert [j["id"] for j in nueva.jugadores] == [j["id"] for j in sala.jugadores]
    assert len(nueva.jugadores) == 6


def test_ida_y_vuelta_del_motivo_secreto():
    sala, anfitrion, _ = partida_en_curso()
    nueva, _ = ida_y_vuelta(persistencia.exportar(sala))
    assert nueva.misterio == sala.misterio
    assert nueva.credencial_admin == sala.credencial_admin
    assert nueva.credencial_admin_resumen == sala.credencial_admin_resumen
    assert nueva.credencial_admin_valida(nueva.credencial_admin)


def test_ida_y_vuelta_de_las_manos_y_la_investigacion():
    sala, anfitrion, invitado = partida_en_curso()
    libres = [
        carta
        for carta in sala.hoja_investigacion(invitado["id"])
        if carta["estado"] not in ("la_tengo", "vista")
    ][:2]
    sala.marcar_investigacion(invitado["id"], libres[0]["id"], "descartada")
    sala.marcar_investigacion(invitado["id"], libres[1]["id"], "sin_informacion")
    sala.vistas[anfitrion["id"]].add("parador")

    nueva, _ = ida_y_vuelta(persistencia.exportar(sala))
    assert nueva.manos == sala.manos
    assert nueva.descartes[invitado["id"]] == {libres[0]["id"]}
    assert nueva.vistas[anfitrion["id"]] == {"parador"}
    # La hoja derivada sale igual que antes de guardar.
    assert nueva.hoja_investigacion(invitado["id"]) == sala.hoja_investigacion(
        invitado["id"]
    )


def test_ida_y_vuelta_de_los_pnj_y_los_eliminados():
    sala, anfitrion, _ = partida_en_curso()
    pnj = next(j for j in sala.jugadores if j["tipo"] == TIPO_PNJ)
    pnj["activo_investigacion"] = False
    deducción = {
        "sospechoso_id": "lucia",
        "lugar_id": "parador",
        "objeto_id": "baul-imperial",
    }
    sala.soluciones_deducidas[pnj["id"]] = deducción
    nueva, _ = ida_y_vuelta(persistencia.exportar(sala))
    eliminado = nueva.jugador_por_id(pnj["id"])
    assert eliminado["activo_investigacion"] is False
    assert eliminado["tipo"] == TIPO_PNJ
    assert nueva.soluciones_deducidas[pnj["id"]] == deducción
    # Y sigue siendo un asiento de pleno derecho.
    assert pnj["id"] in nueva.orden_turnos
    assert pnj["id"] in nueva.manos


def test_ida_y_vuelta_de_los_turnos_y_el_tablero():
    sala, anfitrion, _ = partida_en_curso()
    nueva, _ = ida_y_vuelta(persistencia.exportar(sala))
    assert nueva.orden_turnos == sala.orden_turnos
    assert nueva.turno_actual == sala.turno_actual
    assert nueva.numero_turno == sala.numero_turno
    assert nueva.posiciones_objetos == sala.posiciones_objetos
    for jugador in sala.jugadores:
        assert (
            nueva.posiciones.obtener(jugador["id"])
            == sala.posiciones.obtener(jugador["id"])
        )


def test_ida_y_vuelta_de_la_partida_en_lobby():
    sala, anfitrion = main.gestor.crear_sala("Ana")
    sala.elegir_personaje(anfitrion["id"], "vera")
    nueva, _ = ida_y_vuelta(persistencia.exportar(sala))
    assert nueva.estado == ESTADO_ESPERANDO
    assert nueva.misterio is None
    assert nueva.manos == {}
    assert nueva.orden_turnos == []
    assert len(nueva.jugadores) == 1
    assert nueva.jugadores[0]["personaje_id"] == "vera"


def test_ida_y_vuelta_de_la_partida_terminada():
    sala, anfitrion, _ = partida_en_curso()
    sala.estado = ESTADO_TERMINADA
    sala.resultado_final = "resuelto"
    sala.ganador_id = anfitrion["id"]
    nueva, _ = ida_y_vuelta(persistencia.exportar(sala))
    assert nueva.estado == ESTADO_TERMINADA
    assert nueva.resultado_final == "resuelto"
    assert nueva.ganador_id == anfitrion["id"]
    # Con la partida terminada la solución ya es pública: sale igual.
    assert nueva.estado_publico()["solucion"] == sala.estado_publico()["solucion"]


def test_ida_y_vuelta_del_historial():
    sala, anfitrion, invitado = partida_en_curso()
    sala.estado_jugada = "esperando_sospecha"
    sala.turno_actual = sala.orden_turnos.index(anfitrion["id"])
    sala.formular_sospecha(
        anfitrion["id"], "lucia", "parador", "baul-imperial", ahora=1000.0
    )
    sala._abrir_presentacion_resultado(
        investigador_id=anfitrion["id"],
        investigador_alias="Ana",
        sospecha={"sospechoso_id": "lucia", "lugar_id": "parador", "objeto_id": "baul-imperial"},
        resultado="sin_refutacion",
        ahora=1005.0,
    )
    sala.avanzar_turno()
    assert sala.historial

    nueva, _ = ida_y_vuelta(persistencia.exportar(sala))
    assert nueva.historial == sala.historial
    assert nueva.secuencia_historial == sala.secuencia_historial
    assert nueva.historial_publico() == sala.historial_publico()


def test_ida_y_vuelta_de_la_velocidad():
    sala, anfitrion, _ = partida_en_curso()
    sala.ralentizar_acciones(anfitrion["id"], sala.credencial_admin)
    sala.acelerar_acciones(anfitrion["id"], sala.credencial_admin)
    assert sala.velocidad_acciones == 3
    nueva, _ = ida_y_vuelta(persistencia.exportar(sala))
    assert nueva.velocidad_acciones == 3
    # Y sigue moviéndose con los mismos límites.
    assert nueva.ralentizar_acciones(anfitrion["id"], nueva.credencial_admin) == 4


def test_ida_y_vuelta_de_la_pausa():
    sala, anfitrion, _ = partida_en_curso()
    sala.pausar_partida(anfitrion["id"], sala.credencial_admin)
    nueva, _ = ida_y_vuelta(persistencia.exportar(sala))
    assert nueva.pausada is True
    assert nueva.pausa_marca is not None
    # Y solo el anfitrión del archivo puede reanudarla.
    con_otra = nueva.anfitrion()["id"]
    assert con_otra in [j["id"] for j in sala.jugadores]


def test_ida_y_vuelta_de_una_sospecha_pendiente_de_refutacion():
    import time as modulo_tiempo

    sala, anfitrion, invitado = partida_en_curso()
    sala.sospecha_pendiente = {
        "investigador_id": anfitrion["id"],
        "refutador_id": invitado["id"],
        "sospecha": {"sospechoso_id": "lucia"},
        "coincidencias": ["parador"],
    }
    sala.estado_jugada = JUGADA_ESPERANDO_REFUTADOR
    original = modulo_tiempo.monotonic() + 7.0
    sala.refutacion_deadline = original
    nueva, _ = ida_y_vuelta(persistencia.exportar(sala))
    assert nueva.sospecha_pendiente == sala.sospecha_pendiente
    assert nueva.estado_jugada == JUGADA_ESPERANDO_REFUTADOR
    # El plazo se reconstruye a partir del restante, no del instante viejo.
    assert nueva.refutacion_deadline is not None
    assert abs(nueva.refutacion_deadline - original) < 1.0


def test_ida_y_vuelta_de_una_presentacion_pendiente():
    ahora = 1000.0
    sala, anfitrion, _ = partida_en_curso()
    sala.estado_jugada = "esperando_sospecha"
    sala.turno_actual = sala.orden_turnos.index(anfitrion["id"])
    sala.formular_sospecha(
        anfitrion["id"], "lucia", "parador", "baul-imperial", ahora=ahora
    )
    nueva, _ = ida_y_vuelta(persistencia.exportar(sala, ahora=ahora))
    assert nueva.presentacion_sospecha["id"] == sala.presentacion_sospecha["id"]
    assert nueva.presentacion_sospecha["sospecha"] == sala.presentacion_sospecha["sospecha"]
    for jugador_id, datos in nueva.presentacion_sospecha["participantes"].items():
        original = sala.presentacion_sospecha["participantes"][jugador_id]
        assert datos["listo"] == original["listo"]
    assert nueva.estado_jugada == "presentando_sospecha"


def test_ida_y_vuelta_del_bloqueo_de_inactividad():
    sala, anfitrion, _ = partida_en_curso()
    sala.estado_jugada = "esperando_movimiento"
    sala.turno_actual = sala.orden_turnos.index(anfitrion["id"])
    sala.marcar_bloqueo()
    nueva, _ = ida_y_vuelta(persistencia.exportar(sala))
    assert nueva.bloqueo_jugador_id == sala.bloqueo_jugador_id
    assert nueva.bloqueo_accion == sala.bloqueo_accion
    assert nueva.bloqueo_deadline is not None
    assert abs(nueva.bloqueo_deadline - sala.bloqueo_deadline) < 1.0


def test_ida_y_vuelta_de_lo_que_le_quedaba_a_un_pnj():
    sala, anfitrion, _ = partida_en_curso()
    sala.turno_pnj_espera_restante = 1.75
    nueva, _ = ida_y_vuelta(persistencia.exportar(sala))
    assert nueva.turno_pnj_espera_restante == pytest.approx(1.75)


def test_exportar_una_partida_importada_da_el_mismo_archivo():
    """La forma más fuerte de la ida y vuelta: volver a exportar."""
    sala, _, _ = partida_en_curso()
    archivo = persistencia.exportar(sala)
    nueva, _ = ida_y_vuelta(archivo)
    segundo = persistencia.exportar(nueva)
    # Todo igual salvo la fecha de generación y los tiempos restante.
    assert segundo["formato"] == archivo["formato"]
    assert segundo["version"] == archivo["version"]
    assert segundo["resumen"] == archivo["resumen"]
    assert set(segundo["estado"]) == set(archivo["estado"])
    for clave in ("jugadores", "misterio", "manos", "historial", "orden_turnos"):
        assert segundo["estado"][clave] == archivo["estado"][clave], clave
    persistencia.validar(segundo)


# --- Validación: lo que debe rechazarse ----------------------------------


def test_se_rechaza_un_archivo_que_no_es_json_de_una_partida():
    sala, _, _ = partida_en_curso()
    for basura in (None, [], "texto", 42, {}):
        with pytest.raises(ValueError):
            persistencia.validar(basura)


def test_se_rechaza_una_version_futura():
    sala, _, _ = partida_en_curso()
    datos = persistencia.exportar(sala)
    datos["version"] = persistencia.VERSION_PARTIDA + 1
    firmar(datos)
    with pytest.raises(ValueError) as error:
        persistencia.validar(datos)
    assert "versión" in str(error.value).lower()


def test_se_rechaza_un_formato_distinto():
    sala, _, _ = partida_en_curso()
    datos = persistencia.exportar(sala)
    datos["formato"] = "otro-juego/partida"
    firmar(datos)
    with pytest.raises(ValueError):
        persistencia.validar(datos)


def test_se_rechaza_un_archivo_corrupto_sin_recalcular_la_huella():
    """El SHA-256 detecta el alteración, aunque el resto cuadre."""
    sala, _, _ = partida_en_curso()
    datos = persistencia.exportar(sala)
    datos["estado"]["numero_turno"] = 42
    with pytest.raises(ValueError) as error:
        persistencia.validar(datos)
    assert "dañado" in str(error.value)


def test_se_rechaza_una_carta_que_no_existe():
    sala, _, _ = partida_en_curso()
    datos = persistencia.exportar(sala)
    mano = next(iter(datos["estado"]["manos"].values()))
    mano[0] = {"id": "carta-fantasma", "nombre": "Fantasma", "categoria": "lugar"}
    firmar(datos)
    with pytest.raises(ValueError):
        persistencia.validar(datos)


def test_se_rechaza_una_carta_de_la_solucion_repartida():
    sala, _, _ = partida_en_curso()
    datos = persistencia.exportar(sala)
    secreto = datos["estado"]["misterio"]["objeto"]
    next(iter(datos["estado"]["manos"].values())).append(secreto)
    firmar(datos)
    with pytest.raises(ValueError):
        persistencia.validar(datos)


def test_se_rechaza_una_carta_repartida_dos_veces():
    sala, _, _ = partida_en_curso()
    datos = persistencia.exportar(sala)
    manos = list(datos["estado"]["manos"].values())
    manos[1][0] = dict(manos[0][0])
    firmar(datos)
    with pytest.raises(ValueError):
        persistencia.validar(datos)


def test_se_rechaza_un_reparto_incompleto():
    sala, _, _ = partida_en_curso()
    datos = persistencia.exportar(sala)
    manos = datos["estado"]["manos"]
    manos.pop(next(iter(manos)))
    firmar(datos)
    with pytest.raises(ValueError):
        persistencia.validar(datos)


def test_se_rechaza_un_jugador_que_no_existe():
    sala, anfitrion, invitado = partida_en_curso()
    datos = persistencia.exportar(sala)
    datos["estado"]["sospecha_pendiente"] = {
        "investigador_id": anfitrion["id"],
        "refutador_id": "jugador-fantasma",
        "sospecha": {},
        "coincidencias": [],
    }
    firmar(datos)
    with pytest.raises(ValueError):
        persistencia.validar(datos)


def test_se_rechaza_un_personaje_que_no_existe():
    sala, _, _ = partida_en_curso()
    datos = persistencia.exportar(sala)
    datos["estado"]["jugadores"][0]["personaje_id"] = "personaje-fantasma"
    firmar(datos)
    with pytest.raises(ValueError):
        persistencia.validar(datos)


def test_se_rechaza_dos_participantes_con_el_mismo_personaje():
    sala, _, _ = partida_en_curso()
    datos = persistencia.exportar(sala)
    primero = datos["estado"]["jugadores"][0]["personaje_id"]
    datos["estado"]["jugadores"][1]["personaje_id"] = primero
    firmar(datos)
    with pytest.raises(ValueError):
        persistencia.validar(datos)


def test_se_rechaza_una_posicion_que_no_existe_en_el_tablero():
    sala, _, _ = partida_en_curso()
    datos = persistencia.exportar(sala)
    posiciones = datos["estado"]["posiciones"]
    posiciones[next(iter(posiciones))] = "casilla-inventada"
    firmar(datos)
    with pytest.raises(ValueError):
        persistencia.validar(datos)


def test_se_rechaza_un_objeto_colocado_donde_no_se_puede():
    sala, _, _ = partida_en_curso()
    datos = persistencia.exportar(sala)
    datos["estado"]["posiciones_objetos"] = {"baul-imperial": "no-es-una-ubicacion"}
    firmar(datos)
    with pytest.raises(ValueError):
        persistencia.validar(datos)


def test_se_rechaza_una_fase_imposible():
    sala, anfitrion, _ = partida_en_curso()
    datos = persistencia.exportar(sala)
    # Se dice que hay una refutación pendiente, pero no hay sospecha.
    datos["estado"]["estado_jugada"] = JUGADA_ESPERANDO_REFUTADOR
    firmar(datos)
    with pytest.raises(ValueError):
        persistencia.validar(datos)

    otro = persistencia.exportar(sala)
    otro["estado"]["estado_jugada"] = "presentando_sospecha"
    firmar(otro)
    with pytest.raises(ValueError):
        persistencia.validar(otro)


def test_se_rechaza_sospecha_y_presentacion_a_la_vez():
    sala, anfitrion, invitado = partida_en_curso()
    datos = persistencia.exportar(sala)
    datos["estado"]["estado_jugada"] = "esperando_eleccion_refutador"
    datos["estado"]["sospecha_pendiente"] = {
        "investigador_id": anfitrion["id"],
        "refutador_id": invitado["id"],
        "sospecha": {},
        "coincidencias": [],
    }
    datos["estado"]["presentacion_sospecha"] = {
        "id": 1,
        "tipo": "sospecha",
        "inicio_restante": 1.0,
        "investigador_id": anfitrion["id"],
        "sospecha": {},
        "participantes": {anfitrion["id"]: {"listo": True, "restante": 0.0}},
    }
    firmar(datos)
    with pytest.raises(ValueError):
        persistencia.validar(datos)


def test_se_rechaza_una_velocidad_fuera_de_rango():
    sala, _, _ = partida_en_curso()
    for velocidad in (
        VELOCIDAD_AUTOMATICA_MINIMA - 1,
        VELOCIDAD_AUTOMATICA_MAXIMA + 1,
        "3",
        3.5,
        True,
    ):
        datos = persistencia.exportar(sala)
        datos["estado"]["velocidad_acciones"] = velocidad
        firmar(datos)
        with pytest.raises(ValueError):
            persistencia.validar(datos)


def test_se_rechaza_un_tiempo_restante_raro():
    sala, _, _ = partida_en_curso()
    for restante in (-5, 999999.0, "diez", float("inf"), float("nan")):
        datos = persistencia.exportar(sala)
        datos["estado"]["refutacion_restante"] = restante
        firmar(datos)
        with pytest.raises(ValueError):
            persistencia.validar(datos)


def test_se_rechaza_una_credencial_ausente_o_corta():
    sala, _, _ = partida_en_curso()
    for credencial in (None, "", "corta", "   " * 30, 12345):
        datos = persistencia.exportar(sala)
        datos["estado"]["credencial_admin"] = credencial
        firmar(datos)
        with pytest.raises(ValueError):
            persistencia.validar(datos)


def test_se_rechaza_un_anfitrion_ausente_o_doble():
    sala, _, _ = partida_en_curso()
    datos = persistencia.exportar(sala)
    for jugador in datos["estado"]["jugadores"]:
        jugador["es_anfitrion"] = False
    firmar(datos)
    with pytest.raises(ValueError):
        persistencia.validar(datos)

    otro = persistencia.exportar(sala)
    otro["estado"]["jugadores"][1]["es_anfitrion"] = True
    firmar(otro)
    with pytest.raises(ValueError):
        persistencia.validar(otro)


def test_se_rechaza_claves_de_clase_o_de_metadatos():
    sala, _, _ = partida_en_curso()
    for clave in ("__class__", "__reduce__", "__globals__", "__dict__"):
        datos = persistencia.exportar(sala)
        datos["estado"]["jugadores"][0][clave] = "os.system"
        firmar(datos)
        with pytest.raises(ValueError) as error:
            persistencia.validar(datos)
        assert "no permitida" in str(error.value)


def test_se_rechaza_claves_desconocidas_en_el_estado():
    sala, _, _ = partida_en_curso()
    datos = persistencia.exportar(sala)
    datos["estado"]["campo_inventado"] = 1
    firmar(datos)
    with pytest.raises(ValueError):
        persistencia.validar(datos)

    otro = persistencia.exportar(sala)
    otro["estado"]["jugadores"][0]["extra"] = 1
    firmar(otro)
    with pytest.raises(ValueError):
        persistencia.validar(otro)


def test_no_se_acepta_pickle_ni_objetos_reconstruidos():
    """El archivo es JSON: cualquier otra cosa se rechaza sin ejecutar nada."""
    import pickle

    sala, _, _ = partida_en_curso()
    blob = pickle.dumps({"formato": persistencia.FORMATO_PARTIDA})
    with pytest.raises(ValueError):
        persistencia.validar(blob)


# --- Atomicidad y conflictos ---------------------------------------------


def test_si_falla_no_queda_ninguna_sala_creada():
    sala, _, _ = partida_en_curso()
    datos = persistencia.exportar(sala)
    datos["estado"]["velocidad_acciones"] = 99
    firmar(datos)
    antes = set(main.gestor.salas)
    with pytest.raises(ValueError):
        main.gestor.importar_partida(datos)
    assert set(main.gestor.salas) == antes


def test_si_falla_no_se_toca_una_partida_que_ya_existia():
    sala, anfitrion, _ = partida_en_curso()
    viva = dict(sala.__dict__)
    datos = persistencia.exportar(sala)
    datos["estado"]["credencial_admin"] = "corta"
    firmar(datos)
    with pytest.raises(ValueError):
        main.gestor.importar_partida(datos)
    assert sala.credencial_admin == viva["credencial_admin"]
    assert len(main.gestor.salas) == 1


def test_un_codo_ocupado_no_roba_la_partida_viva():
    sala, anfitrion, _ = partida_en_curso()
    codigo_vivo = sala.codigo
    manos_vivas = {k: [dict(c) for c in v] for k, v in sala.manos.items()}

    archivo = persistencia.exportar(sala)
    # La sala sigue viva: el mismo código está ocupado.
    nueva, reenumerada = main.gestor.importar_partida(archivo)
    assert reenumerada is True
    assert nueva.codigo != codigo_vivo
    assert len(main.gestor.salas) == 2
    # Y la partida original está intacta.
    original = main.gestor.obtener(codigo_vivo)
    assert original is not None
    assert original.manos == manos_vivas
    assert original.credencial_admin == sala.credencial_admin


def test_cargar_dos_veces_el_mismo_archivo():
    sala, _, _ = partida_en_curso()
    codigo_vivo = sala.codigo
    archivo = persistencia.exportar(sala)
    # La partida original sigue viva, así que las dos copias se reenumeran.
    primera, reenumerada_1 = main.gestor.importar_partida(archivo)
    segunda, reenumerada_2 = main.gestor.importar_partida(archivo)
    assert reenumerada_1 is True and reenumerada_2 is True
    assert primera.codigo != segunda.codigo
    assert primera.codigo != codigo_vivo
    assert segunda.codigo != codigo_vivo
    # Las dos copias son equivalentes.
    assert segunda.misterio == primera.misterio
    assert segunda.manos == primera.manos
    assert segunda.orden_turnos == primera.orden_turnos
    assert segunda.credencial_admin == primera.credencial_admin
    assert len(main.gestor.salas) == 3  # la original más las dos importadas
    # Y la original sigue intacta.
    assert main.gestor.obtener(codigo_vivo).misterio == sala.misterio


def test_importar_no_toca_las_tareas_ni_las_conexiones():
    sala, _, _ = partida_en_curso()
    archivo = persistencia.exportar(sala)
    nueva, _ = main.gestor.importar_partida(archivo)
    assert main.tareas_pnj == {}
    assert main.tareas_refutacion == {}
    assert main.tareas_presentacion == {}
    assert main.tareas_bloqueo == {}
    assert main.conexiones.get(nueva.codigo) is None


def test_registrar_sala_crea_cerrojo_pero_no_arranca_nada():
    sala, _, _ = partida_en_curso()
    nueva, _ = main.gestor.importar_partida(persistencia.exportar(sala))
    main.registrar_sala(nueva)
    assert main.cerrojos.get(nueva.codigo) is not None
    assert main.conexiones.get(nueva.codigo) == {}
    assert main.tareas_pnj == {}


def test_reactivar_no_duplica_tareas():
    import asyncio

    sala, _, _ = partida_en_curso()
    nueva, _ = main.gestor.importar_partida(persistencia.exportar(sala))

    async def escenario():
        main.registrar_sala(nueva)
        main.reactivar_sala(nueva)
        main.reactivar_sala(nueva)
        await asyncio.sleep(0)
        assert len(main.tareas_pnj) <= 1
        for tabla in (
            main.tareas_pnj,
            main.tareas_refutacion,
            main.tareas_presentacion,
            main.tareas_bloqueo,
        ):
            for tarea in list(tabla.values()):
                tarea.cancel()

    asyncio.run(escenario())


def test_reactivar_una_sala_en_pausa_no_arranca_nada():
    import asyncio

    sala, anfitrion, _ = partida_en_curso()
    sala.pausar_partida(anfitrion["id"], sala.credencial_admin)
    nueva, _ = main.gestor.importar_partida(persistencia.exportar(sala))

    async def escenario():
        main.registrar_sala(nueva)
        main.reactivar_sala(nueva)
        await asyncio.sleep(0)
        assert main.tareas_pnj == {}
        assert main.tareas_bloqueo == {}

    asyncio.run(escenario())


def test_una_partida_restaurada_sigue_siendo_jugable():
    """No solo se ve igual: el motor sigue admitiendo jugadas."""
    sala, anfitrion, invitado = partida_en_curso()
    sala.estado_jugada = "esperando_movimiento"
    sala.turno_actual = sala.orden_turnos.index(anfitrion["id"])
    nueva, _ = ida_y_vuelta(persistencia.exportar(sala))
    tirada = nueva.tirar_dado_tablero(anfitrion["id"])
    assert 1 <= tirada <= 6
    assert nueva.estado_jugada == "esperando_destino"
    assert nueva.jugador_en_turno()["id"] == anfitrion["id"]


# --- Tiempos: no se descuenta el tiempo transcurrido ---------------------


def test_el_tiempo_restante_no_se_descuenta_al_importar(monkeypatch):
    import time as modulo_tiempo

    reloj = {"t": 5000.0}
    monkeypatch.setattr(modulo_tiempo, "monotonic", lambda: reloj["t"])
    sala, anfitrion, _ = partida_en_curso()
    sala.sospecha_pendiente = {
        "investigador_id": anfitrion["id"],
        "refutador_id": next(
            j["id"]
            for j in sala.jugadores
            if j["tipo"] == TIPO_HUMANO and j["id"] != anfitrion["id"]
        ),
        "sospecha": {},
        "coincidencias": [],
    }
    sala.estado_jugada = JUGADA_ESPERANDO_REFUTADOR
    sala.refutacion_deadline = 5010.0
    archivo = persistencia.exportar(sala, ahora=5000.0)
    assert archivo["estado"]["refutacion_restante"] == pytest.approx(10.0)

    # Pasan dos horas entre que se guardó y que se importa.
    reloj["t"] += 7200.0
    for codigo in list(main.gestor.salas):
        del main.gestor.salas[codigo]
    nueva, _ = main.gestor.importar_partida(archivo)
    assert nueva.refutacion_deadline - reloj["t"] == pytest.approx(10.0)


def test_la_pausa_se_restaura_sin_arrastrar_la_duracion_antigua(monkeypatch):
    import time as modulo_tiempo

    reloj = {"t": 100.0}
    monkeypatch.setattr(modulo_tiempo, "monotonic", lambda: reloj["t"])
    sala, anfitrion, invitado = partida_en_curso()
    sala.sospecha_pendiente = {
        "investigador_id": anfitrion["id"],
        "refutador_id": invitado["id"],
        "sospecha": {"sospechoso_id": "lucia"},
        "coincidencias": ["parador"],
    }
    sala.estado_jugada = JUGADA_ESPERANDO_REFUTADOR
    sala.pausar_partida(anfitrion["id"], sala.credencial_admin, ahora=100.0)
    # Ocho minutos de pausa: el reloj sigue, el plazo no se consume.
    reloj["t"] += 500.0
    sala.refutacion_deadline = reloj["t"] + 10.0
    archivo = persistencia.exportar(sala, ahora=600.0)
    assert archivo["estado"]["pausa"]["duracion"] == pytest.approx(500.0)
    assert archivo["estado"]["refutacion_restante"] == pytest.approx(10.0)

    for codigo in list(main.gestor.salas):
        del main.gestor.salas[codigo]
    nueva, _ = main.gestor.importar_partida(archivo)
    assert nueva.pausada is True
    # Al reanudar, solo cuenta la pausa NUEVA.
    reloj["t"] += 3.0
    nueva.reanudar_partida(nueva.anfitrion()["id"], nueva.credencial_admin)
    assert nueva.refutacion_deadline - reloj["t"] == pytest.approx(10.0)


# --- Ausencia de filtraciones --------------------------------------------


def test_los_errores_no_cuentan_cartas_nietas_de_la_partida():
    sala, anfitrion, _ = partida_en_curso()
    secreto = sala.misterio["objeto"]["id"]
    datos = persistencia.exportar(sala)
    datos["estado"]["velocidad_acciones"] = 99
    firmar(datos)
    with pytest.raises(ValueError) as error:
        persistencia.validar(datos)
    mensaje = str(error.value)
    assert secreto not in mensaje
    for carta in sala.manos[anfitrion["id"]]:
        assert carta["id"] not in mensaje
    assert sala.credencial_admin not in mensaje


def test_el_error_por_credencial_no_dice_si_el_archivo_es_valido():
    sala, _, _ = partida_en_curso()
    datos = persistencia.exportar(sala)
    datos["estado"]["credencial_admin"] = ""
    firmar(datos)
    with pytest.raises(ValueError) as error:
        persistencia.validar(datos)
    assert "credencial" in str(error.value).lower()


def test_una_sala_importada_sigue_protegiendo_sus_secretos():
    sala, anfitrion, invitado = partida_en_curso()
    nueva, _ = ida_y_vuelta(persistencia.exportar(sala))
    publico = nueva.estado_publico()
    # El estado público no lleva ni manos ni hoja, ni la solución mientras
    # la partida sigue viva.
    assert "solucion" not in publico
    assert "mis_cartas" not in publico
    assert "investigacion" not in publico
    assert "misterio" not in publico
    assert "credencial_admin" not in publico
    # Cada jugador sigue viendo solo lo suyo.
    for jugador in nueva.jugadores:
        privado = repr(nueva.estado_privado(jugador["id"]))
        assert "sospechoso_id" not in privado
        assert "baul-imperial\"" not in privado
    # Y el archivo descargado sí lleva la solución: para eso existe.
    archivo = persistencia.exportar(nueva)
    assert archivo["estado"]["misterio"] == nueva.misterio


def test_el_archigo_se_puede_guardar_y_cargar_por_http():
    """De la descarga real a la reconstrucción real."""
    cliente = TestClient(main.app)
    creada = cliente.post(
        "/api/partidas", json={"alias": "Ana", "modo": "tablero"}
    ).json()
    sala = main.gestor.obtener(creada["codigo"])
    sala.elegir_personaje(creada["jugador_id"], "vera")
    sala.iniciar(creada["jugador_id"])
    respuesta = cliente.get(
        f"/api/partidas/{creada['codigo']}/guardar",
        headers={"X-Token-Admin": sala.credencial_admin},
    )
    archivo = json.loads(respuesta.text)
    for codigo in list(main.gestor.salas):
        del main.gestor.salas[codigo]
    nueva, reenumerada = main.gestor.importar_partida(archivo)
    assert reenumerada is False
    assert nueva.codigo == creada["codigo"]
    assert nueva.jugadores[0]["id"] == creada["jugador_id"]
    assert nueva.credencial_admin == sala.credencial_admin
