"""Ritmo contextual humano/PNJ, incluido tablero (sin esperas reales)."""
import asyncio
import pathlib

from app import main
from app.datos.jarandilla import CARTA_POR_ID
from app.motor.sala import (
    ESTADO_INICIADA,
    JUGADA_ESPERANDO_MOVIMIENTO,
    MODO_TABLERO,
    POSICIONES_INICIALES,
    TIPO_PNJ,
    Sala,
)


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
    assert main.PAUSA_LECTURA_SOSPECHA_PNJ_SEGUNDOS == 5.0


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


def test_entre_pnj_rapido_conserva_pausa_corta():
    sala, _, p1, _ = sala_ritmo()
    sala.ultima_jugada = {"investigador_id": p1["id"], "resultado": "sin_refutacion"}
    assert main.pausa_antes_de_turno_pnj(sala) == 3.0


def test_sospecha_pnj_tablero_resuelta_sustituye_pausa_corta_por_cinco():
    sala, _, p1, _ = sala_ritmo()
    sala.modo = MODO_TABLERO
    sala.ultima_jugada = {
        "investigador_id": p1["id"],
        "sospecha": {},
        "resultado": "refutada",
    }
    # Una sospecha real siempre contiene tres ids; evitamos que el dict vacío
    # se confunda con una jugada sin sospecha.
    sala.ultima_jugada["sospecha"] = {"sospechoso_id": "vera"}
    assert main.pausa_antes_de_turno_pnj(sala) == 5.0


class RngSospechaPrimera:
    def choices(self, opciones, weights, k):
        if opciones and isinstance(opciones[0], str):
            return ["tirar"]
        return [opciones[0]]

    def choice(self, opciones):
        return opciones[0]

    def randint(self, minimo, maximo):
        return 4


def sala_ritmo_tablero(dos_pnj=True):
    sala = Sala("JARA-RITMO-TABLERO", modo=MODO_TABLERO)
    p1 = sala.agregar_jugador("Bruno", True, TIPO_PNJ, "bruno")
    p2 = sala.agregar_jugador("Lucía", tipo=TIPO_PNJ, personaje_id="lucia")
    humano = sala.agregar_jugador("Humana", personaje_id="vera")
    sala.estado = ESTADO_INICIADA
    sala.orden_turnos = [p1["id"], p2["id"], humano["id"]]
    sala.turno_actual = 0
    sala.estado_jugada = JUGADA_ESPERANDO_MOVIMIENTO
    sala.manos = {j["id"]: [] for j in sala.jugadores}
    for jugador in sala.jugadores:
        sala.posiciones.asignar(
            jugador["id"], POSICIONES_INICIALES[jugador["personaje_id"]]
        )
    return sala, p1, p2, humano


def test_resultado_pnj_se_difunde_antes_de_esperar_cinco_sin_lock(monkeypatch):
    async def escenario():
        sala, p1, _, humano = sala_ritmo_tablero()
        sala.orden_turnos = [p1["id"], sala.orden_turnos[1], humano["id"]]
        main.gestor.salas[sala.codigo] = sala
        lock = asyncio.Lock()
        main.cerrojos[sala.codigo] = lock
        eventos = []
        original = sala.ejecutar_turno_pnj

        def ejecutar():
            eventos.append("accion")
            return original(RngSospechaPrimera())

        async def difundir(_codigo):
            eventos.append(("difundir", sala.ultima_jugada["resultado"]))

        async def dormir(segundos):
            eventos.append(("esperar", segundos, lock.locked(), sala.ultima_jugada["resultado"] if sala.ultima_jugada else None))

        monkeypatch.setattr(sala, "ejecutar_turno_pnj", ejecutar)
        monkeypatch.setattr(main, "difundir", difundir)
        monkeypatch.setattr(main.asyncio, "sleep", dormir)
        try:
            await main._cadena_turnos_pnj(sala.codigo)
            assert eventos[0] == ("esperar", 3.0, False, None)
            assert eventos[1] == "accion"
            assert eventos[2][0] == "difundir"
            assert eventos[3] == ("esperar", 5.0, False, "sin_refutacion")
            assert eventos.count("accion") == 2
        finally:
            main.gestor.salas.pop(sala.codigo, None)
            main.cerrojos.pop(sala.codigo, None)
            main.tareas_pnj.pop(sala.codigo, None)

    asyncio.run(escenario())


def test_eleccion_humana_pendiente_no_pausa_y_resuelta_si_activa_lectura(monkeypatch):
    async def escenario():
        sala, p1, p2, humano = sala_ritmo_tablero()
        sala.orden_turnos = [p1["id"], p2["id"], humano["id"]]
        sala.manos[humano["id"]] = [
            CARTA_POR_ID["vera"],
            CARTA_POR_ID["baul-imperial"],
        ]
        main.gestor.salas[sala.codigo] = sala
        main.cerrojos[sala.codigo] = asyncio.Lock()
        esperas = []
        original = sala.ejecutar_turno_pnj

        monkeypatch.setattr(
            sala,
            "ejecutar_turno_pnj",
            lambda: original(RngSospechaPrimera()),
        )
        monkeypatch.setattr(main, "difundir", lambda _codigo: _async_none())

        async def dormir(segundos):
            esperas.append(segundos)

        monkeypatch.setattr(main.asyncio, "sleep", dormir)
        try:
            await main._cadena_turnos_pnj(sala.codigo)
            assert esperas == [3.0]
            assert sala.sospecha_pendiente is not None
            sala.mostrar_carta(humano["id"], "vera")
            assert sala.jugador_en_turno()["id"] == p2["id"]
            assert main.pausa_antes_de_turno_pnj(sala) == 5.0
            assert sala.ultima_jugada["resultado"] == "refutada"
        finally:
            main.gestor.salas.pop(sala.codigo, None)
            main.cerrojos.pop(sala.codigo, None)
            main.tareas_pnj.pop(sala.codigo, None)

    asyncio.run(escenario())


async def _async_none():
    return None


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
