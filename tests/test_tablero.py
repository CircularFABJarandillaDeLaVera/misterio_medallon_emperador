import pytest

from app.motor.tablero import (
    CENTRO_ID,
    EXTERIORES,
    PAREJAS_PASADIZOS,
    PLAZA_ID,
    PosicionesParticipantes,
    TABLERO,
    Tablero,
    tirar_dado,
)


def test_nueve_ubicaciones_canonicas_y_centro_unico():
    assert len(TABLERO.ubicaciones) == 9
    assert CENTRO_ID == "parador"
    assert CENTRO_ID in TABLERO.ubicaciones
    assert CENTRO_ID not in TABLERO.casillas
    assert PLAZA_ID in TABLERO.ubicaciones
    assert set(EXTERIORES) == set(TABLERO.ubicaciones) - {CENTRO_ID}


def test_ocho_caminos_perimetrales_y_ocho_radiales():
    perimetrales = [c for c in TABLERO.caminos.values() if CENTRO_ID not in {c.origen, c.destino}]
    radiales = [c for c in TABLERO.caminos.values() if CENTRO_ID in {c.origen, c.destino}]
    assert len(perimetrales) == 8
    assert len(radiales) == 8
    assert len(TABLERO.caminos) == 16


def test_cada_camino_tiene_tres_posiciones_intermedias_unicas():
    assert all(len(camino.casillas) == 3 for camino in TABLERO.caminos.values())
    ids = [c for camino in TABLERO.caminos.values() for c in camino.casillas]
    assert len(ids) == 48 == len(set(ids))
    assert len(TABLERO.posiciones_validas) == 57


def test_caminos_bidireccionales_y_distancia_cuatro_entre_lugares():
    camino = TABLERO.caminos["camino-plaza-constitucion-iglesia-san-agustin"]
    secuencia = (camino.origen, *camino.casillas, camino.destino)
    for a, b in zip(secuencia, secuencia[1:]):
        assert b in TABLERO.vecinos_normales(a)
        assert a in TABLERO.vecinos_normales(b)
    assert camino.destino not in TABLERO.destinos_alcanzables(camino.origen, 3)
    assert camino.destino in TABLERO.destinos_alcanzables(camino.origen, 4)
    assert TABLERO.distancia_normal(camino.origen, camino.destino) == 4


def test_todas_las_conexiones_normales_directas_tienen_distancia_cuatro():
    for camino in TABLERO.caminos.values():
        assert TABLERO.distancia_normal(camino.origen, camino.destino) == 4
        assert TABLERO.distancia_normal(camino.destino, camino.origen) == 4


def test_conexiones_normales_del_centro_parador():
    destinos = TABLERO.destinos_alcanzables("parador", 4)
    assert set(EXTERIORES) <= destinos
    # La torre ya no es solo pasadizo: el centro conecta con ella por radial.
    assert "nuestra-senora-torre" in destinos


def test_plaza_exterior_conecta_con_centro_y_vecinas():
    destinos = TABLERO.destinos_alcanzables("plaza-constitucion", 4)
    assert {"parador", "iglesia-san-agustin", "picota"} <= destinos
    assert "nuestra-senora-torre" not in destinos  # solo es pasadizo


class DadoFijo:
    def __init__(self, valor):
        self.valor = valor
        self.llamada = None

    def randint(self, minimo, maximo):
        self.llamada = (minimo, maximo)
        return self.valor


@pytest.mark.parametrize("valor", range(1, 7))
def test_dado_1d6_e_inyeccion_rng(valor):
    rng = DadoFijo(valor)
    assert tirar_dado(rng) == valor
    assert rng.llamada == (1, 6)


@pytest.mark.parametrize("valor", [0, 7])
def test_dado_rechaza_rng_fuera_de_rango(valor):
    with pytest.raises(ValueError):
        tirar_dado(DadoFijo(valor))


def test_movimiento_de_una_y_varias_casillas():
    camino = TABLERO.caminos["camino-plaza-constitucion-iglesia-san-agustin"]
    rutas1 = TABLERO.rutas_legales("plaza-constitucion", 1)
    assert any(r.posiciones == (camino.casillas[0],) for r in rutas1)
    rutas3 = TABLERO.rutas_legales("plaza-constitucion", 3)
    assert any(r.posiciones == camino.casillas[:3] for r in rutas3)


def test_entrada_sin_tirada_exacta_pierde_sobrantes():
    camino = TABLERO.caminos["camino-plaza-constitucion-iglesia-san-agustin"]
    origen = camino.casillas[1]
    rutas = TABLERO.rutas_legales(origen, 6)
    entrada = next(r for r in rutas if r.destino == "iglesia-san-agustin")
    assert entrada.posiciones == (camino.casillas[2], "iglesia-san-agustin")
    assert entrada.puntos_usados == 2
    assert entrada.termina_en_ubicacion


def test_no_se_atraviesa_ubicacion_con_puntos_sobrantes():
    camino = TABLERO.caminos["camino-plaza-constitucion-iglesia-san-agustin"]
    rutas = TABLERO.rutas_legales(camino.casillas[1], 6)
    for ruta in rutas:
        if "iglesia-san-agustin" in ruta.posiciones:
            assert ruta.destino == "iglesia-san-agustin"
            assert ruta.posiciones[-1] == "iglesia-san-agustin"


@pytest.mark.parametrize("puntos", [4, 5, 6])
def test_desde_ubicacion_entrar_con_cuatro_o_mas_siempre_termina(puntos):
    camino = TABLERO.caminos["camino-plaza-constitucion-iglesia-san-agustin"]
    rutas = TABLERO.rutas_legales("plaza-constitucion", puntos)
    entrada = next(r for r in rutas if r.destino == "iglesia-san-agustin")
    assert entrada.puntos_usados == 4
    assert entrada.posiciones == (*camino.casillas, "iglesia-san-agustin")
    assert entrada.termina_en_ubicacion


def test_bifurcaciones_y_sin_teletransporte():
    rutas = TABLERO.rutas_legales("plaza-constitucion", 1)
    assert len({r.destino for r in rutas}) == 3
    assert not TABLERO.validar_movimiento("plaza-constitucion", "puente-parral", 1)


def test_rutas_no_repiten_posiciones_ni_crean_bucles():
    for origen in TABLERO.posiciones_validas:
        for ruta in TABLERO.rutas_legales(origen, 6):
            recorrido = (origen, *ruta.posiciones)
            assert len(recorrido) == len(set(recorrido))


def test_validacion_server_side_de_destino_y_ruta():
    camino = TABLERO.caminos["camino-plaza-constitucion-parador"]
    ruta = list(camino.casillas[:3])
    assert TABLERO.validar_movimiento("plaza-constitucion", camino.casillas[2], 3, ruta)
    assert not TABLERO.validar_movimiento("plaza-constitucion", camino.casillas[2], 2, ruta)
    assert not TABLERO.validar_movimiento("sitio-falso", "plaza-constitucion", 3)


def test_dos_pasadizos_canonicos_bidireccionales():
    assert len(TABLERO.pasadizos) == 2
    for a, b in PAREJAS_PASADIZOS:
        assert TABLERO.destinos_pasadizo(a) == (b,)
        assert TABLERO.destinos_pasadizo(b) == (a,)
        assert TABLERO.usar_pasadizo(a, b) == b
        assert TABLERO.usar_pasadizo(b, a) == a


def test_pasadizo_solo_desde_ubicacion_no_usa_dado_y_termina_directo():
    casilla = next(iter(TABLERO.casillas))
    assert TABLERO.destinos_pasadizo(casilla) == ()
    with pytest.raises(ValueError):
        TABLERO.usar_pasadizo(casilla, "parador")
    # La API especial no recibe puntos ni RNG: el destino es inmediato.
    assert TABLERO.usar_pasadizo("plaza-constitucion", "nuestra-senora-torre") == "nuestra-senora-torre"


def test_posicion_unica_y_ocupacion_compartida():
    posiciones = PosicionesParticipantes(Tablero())
    posiciones.asignar("a", "parador")
    posiciones.asignar("b", "parador")
    assert posiciones.obtener("a") == posiciones.obtener("b") == "parador"
    posiciones.asignar("a", PLAZA_ID)
    assert posiciones.obtener("a") == PLAZA_ID
    with pytest.raises(ValueError):
        posiciones.asignar("a", "inexistente")


def test_modo_rapido_no_depende_del_tablero():
    from app.motor.sala import ESTADO_INICIADA, Sala

    sala = Sala("JARA-RAPIDO")
    jugadores = [sala.agregar_jugador(x, i == 0) for i, x in enumerate(("A", "B", "C"))]
    sala.estado = ESTADO_INICIADA
    sala.orden_turnos = [j["id"] for j in jugadores]
    sala.manos = {j["id"]: [] for j in jugadores}
    sala.formular_sospecha(jugadores[0]["id"], "vera", "puente-parral", "libro-hueco")
    sala.actualizar_presentacion_sospecha(ahora=float("inf"))
    assert sala.ultima_jugada["resultado"] == "sin_refutacion"
