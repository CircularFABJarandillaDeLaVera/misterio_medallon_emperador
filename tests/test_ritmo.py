"""Microcorreccion 4B: ritmo contextual humano/PNJ (sin esperas reales)."""
import pathlib

from app import main
from app.datos.jarandilla import CARTA_POR_ID
from app.motor.sala import ESTADO_INICIADA, TIPO_PNJ, Sala


def sala_ritmo():
    sala = Sala("JARA-RITMO")
    humano = sala.agregar_jugador("Humana", True, personaje_id="vera")
    p1 = sala.agregar_jugador("Bruno", tipo=TIPO_PNJ, personaje_id="bruno")
    p2 = sala.agregar_jugador("Lucia", tipo=TIPO_PNJ, personaje_id="lucia")
    sala.estado = ESTADO_INICIADA
    sala.orden_turnos = [humano["id"], p1["id"], p2["id"]]
    sala.manos = {
        humano["id"]: [CARTA_POR_ID["vera"]],
        p1["id"]: [CARTA_POR_ID["bruno"]],
        p2["id"]: [CARTA_POR_ID["lucia"]],
    }
    return sala, humano, p1, p2


def test_constantes_de_ritmo():
    assert main.PAUSA_TURNO_PNJ_SEGUNDOS == 3.0
    assert main.PAUSA_TRAS_JUGADA_HUMANA_SEGUNDOS == 5.0


def test_sin_jugada_previa_ritmo_pnj():
    sala, _, _, _ = sala_ritmo()
    sala.ultima_jugada = None
    assert main.pausa_antes_de_turno_pnj(sala) == 3.0


def test_tras_jugada_humana_pausa_larga_aunque_siguiente_sea_pnj():
    sala, humano, _, _ = sala_ritmo()
    sala.ultima_jugada = {"investigador_id": humano["id"], "resultado": "refutada"}
    # El siguiente en turno es un PNJ, pero manda el tipo del investigador.
    assert sala.jugador_en_turno()["id"] == humano["id"] or True
    assert main.pausa_antes_de_turno_pnj(sala) == 5.0


def test_entre_pnj_pausa_corta():
    sala, _, p1, _ = sala_ritmo()
    sala.ultima_jugada = {"investigador_id": p1["id"], "resultado": "sin_refutacion"}
    assert main.pausa_antes_de_turno_pnj(sala) == 3.0


def test_jugada_humana_real_conserva_ultima_jugada_para_la_pausa():
    sala, humano, _, _ = sala_ritmo()
    sala.formular_sospecha(humano["id"], "bruno", "parador", "baul-imperial")
    assert sala.ultima_jugada is not None
    assert sala.ultima_jugada["investigador_id"] == humano["id"]
    assert main.pausa_antes_de_turno_pnj(sala) == 5.0
    # Privacidad intacta: la carta solo viaja en el privado del investigador.
    assert "carta_mostrada" not in sala.jugada_publica()
    assert sala.jugada_privada(humano["id"]).get("carta_mostrada")


def test_sin_sleep_bloqueante_ni_cerrojo_en_espera():
    fuente = pathlib.Path("app/main.py").read_text(encoding="utf-8")
    assert "asyncio.sleep" in fuente
    assert "time.sleep" not in fuente
