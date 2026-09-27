import pytest

from app.datos.jarandilla import CARTA_POR_ID
from app.motor.sala import (


    ESTADO_INICIADA,
    JUGADA_PRESENTANDO_SOSPECHA,
    TIPO_PNJ,
    Sala,
)

def cerrar_resultado(sala):
    """8B.31C: el turno avanza al cerrarse la presentacion del resultado.

    No-op si no hay resultado publico pendiente: las aserciones intermedias
    siguen viendo el turno sin avanzar.
    """
    presentacion = getattr(sala, "presentacion_sospecha", None)
    if presentacion and presentacion.get("tipo") == "resultado":
        assert sala.actualizar_presentacion_sospecha(ahora=float("inf"))


SOSPECHA = ("vera", "parador", "baul-imperial")


def mesa(humanos=1):
    sala = Sala("JARA-PRESENTA")
    participantes = [
        sala.agregar_jugador(f"H{i}", i == 0, personaje_id=("vera", "bruno", "lucia")[i])
        for i in range(humanos)
    ]
    personajes = ("alvaro", "mateo", "eulalia", "lucia", "bruno")
    for indice, personaje in enumerate(personajes[: 6 - humanos]):
        participantes.append(
            sala.agregar_jugador(personaje.title(), tipo=TIPO_PNJ, personaje_id=personaje)
        )
    sala.estado = ESTADO_INICIADA
    sala.orden_turnos = [j["id"] for j in participantes]
    sala.manos = {j["id"]: [] for j in participantes}
    return sala, participantes


def test_humano_autor_listo_y_cinco_pnj_esperan_tres_segundos():
    sala, jugadores = mesa(1)
    autor = jugadores[0]
    sala.formular_sospecha(autor["id"], *SOSPECHA, ahora=100.0)
    presentacion = sala.presentacion_sospecha
    assert sala.estado_jugada == JUGADA_PRESENTANDO_SOSPECHA
    assert presentacion["participantes"][autor["id"]]["listo"]
    assert not sala.actualizar_presentacion_sospecha(ahora=102.999)
    assert sala.actualizar_presentacion_sospecha(ahora=103.0)
    cerrar_resultado(sala)
    assert sala.turno_actual == 1


def test_pnj_autor_humano_bloquea_hasta_confirmar_en_segundo_siete():
    sala, jugadores = mesa(1)
    humano, autor = jugadores[0], jugadores[1]
    sala.turno_actual = 1
    sala.formular_sospecha(autor["id"], *SOSPECHA, ahora=200.0)
    pid = sala.presentacion_sospecha["id"]
    assert not sala.actualizar_presentacion_sospecha(ahora=203.0)
    assert sala.estado_jugada == JUGADA_PRESENTANDO_SOSPECHA
    assert sala.confirmar_presentacion_sospecha(humano["id"], pid, ahora=207.0)
    cerrar_resultado(sala)
    assert sala.turno_actual == 2


def test_humano_sin_responder_avanza_en_deadline_diez_original():
    sala, jugadores = mesa(1)
    humano, autor = jugadores[0], jugadores[1]
    sala.turno_actual = 1
    sala.formular_sospecha(autor["id"], *SOSPECHA, ahora=300.0)
    assert not sala.actualizar_presentacion_sospecha(ahora=309.999)
    assert sala.actualizar_presentacion_sospecha(ahora=310.0)
    cerrar_resultado(sala)
    assert sala.turno_actual == 2


def test_dos_humanos_confirman_independientemente_y_ultimo_desbloquea():
    sala, jugadores = mesa(3)
    autor, humano_a, humano_b = jugadores[:3]
    sala.formular_sospecha(autor["id"], *SOSPECHA, ahora=400.0)
    pid = sala.presentacion_sospecha["id"]
    assert not sala.confirmar_presentacion_sospecha(humano_a["id"], pid, ahora=402.0)
    assert sala.confirmar_presentacion_sospecha(humano_b["id"], pid, ahora=406.0)
    cerrar_resultado(sala)
    assert sala.turno_actual == 1


def test_recarga_reconstruye_popup_sin_reiniciar_deadline_y_confirmado_no_reaparece():
    sala, jugadores = mesa(1)
    humano, autor = jugadores[0], jugadores[1]
    sala.turno_actual = 1
    sala.formular_sospecha(autor["id"], *SOSPECHA, ahora=500.0)
    pid = sala.presentacion_sospecha["id"]
    privado = sala.estado_privado(humano["id"])["jugada"]
    assert privado["presentacion_id"] == pid
    assert privado["presentacion_pendiente"]
    deadline = sala.presentacion_sospecha["participantes"][humano["id"]]["deadline"]
    sala.estado_privado(humano["id"])
    assert sala.presentacion_sospecha["participantes"][humano["id"]]["deadline"] == deadline
    assert sala.confirmar_presentacion_sospecha(humano["id"], pid, ahora=507.0)
    # 8B.31C: la sospecha ya no reaparece; lo pendiente es el resultado
    # pÃºblico, con identidad PROPIA (nunca la misma pid).
    privada = sala.estado_privado(humano["id"])["jugada"]
    if privada.get("presentacion_pendiente"):
        assert privada["presentacion_id"] != pid
        assert privada["presentacion_tipo"] == "resultado"


def test_eliminado_participa_identidad_evitar_confirmacion_atrasada_y_privacidad():
    sala, jugadores = mesa(2)
    autor, eliminado = jugadores[:2]
    eliminado["activo_investigacion"] = False
    sala.manos[eliminado["id"]] = [CARTA_POR_ID["vera"]]
    sala.formular_sospecha(autor["id"], *SOSPECHA, ahora=600.0)
    pid = sala.presentacion_sospecha["id"]
    publico = repr(sala.estado_publico())
    assert "participantes" not in publico and "deadline" not in publico
    assert sala.estado_privado(eliminado["id"])["jugada"]["presentacion_pendiente"]
    assert sala.confirmar_presentacion_sospecha(eliminado["id"], pid, ahora=603.0)
    assert sala.ultima_jugada is None
    assert [
        carta["id"]
        for carta in sala.estado_privado(eliminado["id"])["jugada"]["opciones_refutacion"]
    ] == ["vera"]
    sala.mostrar_carta(eliminado["id"], "vera")
    assert sala.ultima_jugada["refutador_id"] == eliminado["id"]
    with pytest.raises(ValueError):
        sala.confirmar_presentacion_sospecha(eliminado["id"], pid, ahora=604.0)


# ---------------------------------------------------------------------------
# 8B.31C · RESULTADO PÚBLICO de la sospecha.
# Cierra el flujo canónico: PRESENTACIÓN → REFUTACIÓN → RESULTADO → TURNO.
# ---------------------------------------------------------------------------


def mesa_sospecha_con_refutador(con_pnj_refutador=False):
    """Sala donde H0 investiga y H1 (o un PNJ) puede refutar con 'vera'."""
    sala = Sala("JARA-RESULTADO")
    inv = sala.agregar_jugador("Inv", True, personaje_id="vera")
    ref = sala.agregar_jugador("Ref", personaje_id="lucia")
    pnj = sala.agregar_jugador("Pnj", tipo=TIPO_PNJ, personaje_id="alvaro")
    sala.estado = ESTADO_INICIADA
    sala.orden_turnos = [inv["id"], ref["id"], pnj["id"]]
    sala.turno_actual = 0
    # Con con_pnj_refutador el humano NO tiene coincidencias: refuta el PNJ.
    carta_refutador = "mateo" if con_pnj_refutador else "vera"
    sala.manos = {
        inv["id"]: [CARTA_POR_ID["eulalia"]],
        ref["id"]: [CARTA_POR_ID[carta_refutador]],
        pnj["id"]: [CARTA_POR_ID["vera" if con_pnj_refutador else "lucia"]],
    }
    return sala, inv, ref, pnj


def mesa_pnj_sospecha(refutador_es_pnj):
    """El PNJ 'Alvaro' sospecha; refuta quien tenga 'vera' (humano o PNJ)."""
    sala = Sala("JARA-PNJ-SOSPECHA")
    pnj = sala.agregar_jugador("Alvaro", True, tipo=TIPO_PNJ, personaje_id="alvaro")
    ref = sala.agregar_jugador("Ref", personaje_id="lucia")
    rival = sala.agregar_jugador(
        "Mateo" if refutador_es_pnj else "Bruno",
        tipo=TIPO_PNJ if refutador_es_pnj else None,
        personaje_id="mateo" if refutador_es_pnj else "bruno",
    )
    sala.estado = ESTADO_INICIADA
    sala.orden_turnos = [pnj["id"], ref["id"], rival["id"]]
    sala.turno_actual = 0
    sala.manos = {
        pnj["id"]: [CARTA_POR_ID["eulalia"]],
        ref["id"]: [CARTA_POR_ID["mateo" if refutador_es_pnj else "vera"]],
        rival["id"]: [CARTA_POR_ID["vera"]],
    }
    return sala, ref, pnj


def abrir_ciclo(sala, investigador):
    sala.formular_sospecha(investigador["id"], *SOSPECHA)
    assert sala.actualizar_presentacion_sospecha(ahora=float("inf"))


def _resultado_pendiente(sala):
    presentacion = sala.presentacion_sospecha
    assert presentacion is not None
    assert presentacion["tipo"] == "resultado"
    return presentacion


# 1. Humano sospecha, humano refuta: resultado público y turno aún quieto.
def test_humano_sospecha_humano_refuta_abre_resultado_publico():
    sala, inv, ref, _ = mesa_sospecha_con_refutador()
    abrir_ciclo(sala, inv)
    sala.mostrar_carta(ref["id"], "vera")
    resultado = _resultado_pendiente(sala)
    assert resultado["resultado"] == "refutada"
    assert resultado["investigador_alias"] == "Inv"
    assert resultado["refutador_alias"] == "Ref"
    assert sala.estado_jugada == JUGADA_PRESENTANDO_SOSPECHA
    assert sala.turno_actual == 0  # todavía no avanza
    cerrar_resultado(sala)
    assert sala.turno_actual == 1  # y avanza UNA vez


# 2. Humano sospecha, PNJ refuta.
def test_humano_sospecha_pnj_refuta_abre_resultado_publico():
    sala, inv, _, pnj = mesa_sospecha_con_refutador(con_pnj_refutador=True)
    abrir_ciclo(sala, inv)
    resultado = _resultado_pendiente(sala)
    assert resultado["resultado"] == "refutada"
    assert resultado["refutador_alias"] == "Pnj"
    # Los PNJ quedan listos de inmediato: solo los humanos esperan.
    assert resultado["participantes"][pnj["id"]]["listo"]
    assert not resultado["participantes"][inv["id"]]["listo"]
    cerrar_resultado(sala)
    assert sala.turno_actual == 1


# 3. PNJ sospecha, humano refuta.
def test_pnj_sospecha_humano_refuta_abre_resultado_publico():
    sala, ref, pnj = mesa_pnj_sospecha(False)
    sala.turno_actual = 0
    sala.formular_sospecha(pnj["id"], *SOSPECHA)
    assert sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    sala.mostrar_carta(ref["id"], "vera")
    resultado = _resultado_pendiente(sala)
    assert resultado["resultado"] == "refutada"
    assert resultado["investigador_alias"] == "Alvaro"
    assert resultado["refutador_alias"] == "Ref"
    cerrar_resultado(sala)


# 4. PNJ sospecha, PNJ refuta.
def test_pnj_sospecha_pnj_refuta_abre_resultado_publico():
    sala, _, pnj = mesa_pnj_sospecha(True)
    sala.turno_actual = 0
    sala.formular_sospecha(pnj["id"], *SOSPECHA)
    assert sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    resultado = _resultado_pendiente(sala)
    assert resultado["resultado"] == "refutada"
    assert resultado["investigador_alias"] == "Alvaro"
    assert resultado["refutador_alias"] == "Mateo"
    cerrar_resultado(sala)


# 5. Nadie puede refutar: también hay resultado público.
def test_nadie_refuta_abre_resultado_publico_sin_refutador():
    sala = Sala("JARA-SIN-REFUTAR")
    inv = sala.agregar_jugador("Inv", True, personaje_id="vera")
    otro = sala.agregar_jugador("Otro", personaje_id="lucia")
    sala.estado = ESTADO_INICIADA
    sala.orden_turnos = [inv["id"], otro["id"]]
    sala.turno_actual = 0
    sala.manos = {inv["id"]: [], otro["id"]: []}
    sala.formular_sospecha(inv["id"], *SOSPECHA)
    assert sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    resultado = _resultado_pendiente(sala)
    assert resultado["resultado"] == "sin_refutacion"
    assert "refutador_alias" not in resultado
    assert sala.ultima_jugada["resultado"] == "sin_refutacion"
    cerrar_resultado(sala)
    assert sala.turno_actual == 1


# 6. El eliminado sigue pudiendo refutar (y abre resultado).
def test_eliminado_refuta_y_abre_resultado_publico():
    sala, inv, ref, _ = mesa_sospecha_con_refutador()
    ref["activo_investigacion"] = False
    abrir_ciclo(sala, inv)
    sala.mostrar_carta(ref["id"], "vera")
    resultado = _resultado_pendiente(sala)
    assert resultado["resultado"] == "refutada"
    cerrar_resultado(sala)
    assert sala.jugador_en_turno()["id"] != ref["id"]  # el eliminado no recibe turno


# 7. CONTINUAR humano cierra el resultado.
def test_continuar_humano_cierra_el_resultado_publico():
    sala, inv, ref, _ = mesa_sospecha_con_refutador()
    abrir_ciclo(sala, inv)
    sala.mostrar_carta(ref["id"], "vera")
    resultado = _resultado_pendiente(sala)
    pid = resultado["id"]
    assert not sala.confirmar_presentacion_sospecha(inv["id"], pid, ahora=200.0)
    assert sala.presentacion_sospecha["participantes"][inv["id"]]["listo"]
    assert sala.confirmar_presentacion_sospecha(ref["id"], pid, ahora=200.0)
    assert sala.presentacion_sospecha is None
    assert sala.turno_actual == 1


# 8. Sin respuesta, vence el plazo y continúa.
def test_humano_sin_responder_cierra_el_resultado_en_el_plazo():
    sala, inv, ref, _ = mesa_sospecha_con_refutador()
    abrir_ciclo(sala, inv)
    sala.mostrar_carta(ref["id"], "vera")
    resultado = _resultado_pendiente(sala)
    inicio = resultado["inicio"]
    assert 0 < resultado["participantes"][ref["id"]]["deadline"] - inicio <= 10.0
    assert not sala.actualizar_presentacion_sospecha(ahora=inicio + 9.999)
    assert sala.actualizar_presentacion_sospecha(ahora=inicio + 10.0)
    assert sala.turno_actual == 1


# 9. Reload conserva el deadline original (no se reinicia).
def test_recarga_conserva_el_plazo_del_resultado_publico():
    sala, inv, ref, _ = mesa_sospecha_con_refutador()
    abrir_ciclo(sala, inv)
    sala.mostrar_carta(ref["id"], "vera")
    resultado = _resultado_pendiente(sala)
    deadline = resultado["participantes"][ref["id"]]["deadline"]
    for _ in range(3):  # relecturas del estado privado = reconexión
        sala.estado_privado(ref["id"])
    assert _resultado_pendiente(sala)["participantes"][ref["id"]]["deadline"] == deadline
    assert sala.presentacion_sospecha["id"] == resultado["id"]


# 10. Una confirmación vieja no afecta a la presentación nueva.
def test_confirmacion_antigua_no_afecta_al_resultado_siguiente():
    sala, inv, ref, _ = mesa_sospecha_con_refutador()
    abrir_ciclo(sala, inv)
    pid_sospecha = sala.secuencia_presentacion
    sala.mostrar_carta(ref["id"], "vera")
    resultado = _resultado_pendiente(sala)
    assert resultado["id"] != pid_sospecha
    with pytest.raises(ValueError):
        sala.confirmar_presentacion_sospecha(inv["id"], pid_sospecha, ahora=300.0)
    assert sala.presentacion_sospecha["id"] == resultado["id"]
    assert not resultado["participantes"][ref["id"]]["listo"]


# 11-13. Privacidad: la carta la ve el investigador; nadie más.
def test_privacidad_del_resultado_publico():
    sala, inv, ref, pnj = mesa_sospecha_con_refutador()
    abrir_ciclo(sala, inv)
    sala.mostrar_carta(ref["id"], "vera")
    _resultado_pendiente(sala)
    # El investigador conserva su revelación privada.
    privada_inv = sala.estado_privado(inv["id"])["jugada"]
    assert privada_inv["carta_mostrada"]["id"] == "vera"
    assert sala.estado_carta(inv["id"], "vera") == "vista"
    # El resto no ve la carta ni las opciones de la refutación.
    for otro in (ref, pnj):
        privada = sala.estado_privado(otro["id"])["jugada"]
        assert "carta_mostrada" not in privada
        assert "opciones_refutacion" not in privada
    # El payload público solo dice quién y qué; ni carta ni opciones.
    publico = repr(sala.jugada_publica())
    assert "carta_id" not in publico
    assert "carta_mostrada" not in publico
    assert "coincidencias" not in publico
    assert "opciones_refutacion" not in publico
    assert sala.jugada_publica()["resultado"] == "refutada"
    assert sala.jugada_publica()["refutador_alias"] == "Ref"
    assert sala.jugada_publica()["presentacion_tipo"] == "resultado"


# 14. El turno avanza exactamente una vez aunque se cierre dos veces.
def test_el_turno_avanza_exactamente_una_vez():
    sala, inv, ref, _ = mesa_sospecha_con_refutador()
    abrir_ciclo(sala, inv)
    sala.mostrar_carta(ref["id"], "vera")
    assert sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    turno = sala.turno_actual
    assert turno == 1
    # Una segunda actualización ya no tiene presentación que cerrar.
    assert not sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    assert sala.turno_actual == turno
    # Y la refutación sigue cerrada: nadie puede refutar dos veces.
    with pytest.raises(ValueError):
        sala.mostrar_carta(ref["id"], "vera")
    with pytest.raises(ValueError):
        sala.continuar_refutacion(ref["id"])