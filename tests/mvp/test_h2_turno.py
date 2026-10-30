"""H2. Jugar un turno.

Acepta si: fuera de turno no puedo jugar; robar dos veces o descartar sin robar se rechaza con
un mensaje; los demás ven el descarte en menos de 1 s (esto último, en test_h2_websocket.py).
"""
import pytest

from juegocartas.nucleo.sala.salas import ErrorSala
from juegocartas.nucleo.turno.mesa import JugadaInvalida
from juegocartas.nucleo.turno.orquestador import ComandoFueraDeTurno
from armado import gateway, juego  # noqa: F401  (fixtures)


@pytest.fixture
def sala(juego):
    sala = juego.crear_sala("Nico", "APUNTADO_101")
    juego.unirse(sala.codigo, "Caro")
    juego.unirse(sala.codigo, "Eli")
    juego.empezar(sala.codigo, "Nico")
    return sala.codigo


def partida(juego, sala, jugador):
    return juego.vista(sala, jugador)["partida"]


def test_reparto_inicial(juego, sala):
    vista = partida(juego, sala, "Nico")
    assert len(vista["mano"]) == 10 and vista["pozo"] is not None
    assert vista["mazo"] == 54 - 3 * 10 - 1
    assert vista["en_turno"] == "Nico" and vista["fase"] == "ESPERANDO_ROBO"


def test_cada_jugador_ve_solo_su_mano(juego, sala):
    nico, caro = juego.vista(sala, "Nico"), juego.vista(sala, "Caro")
    assert nico["partida"]["mano"] != caro["partida"]["mano"]
    assert [j["cartas"] for j in nico["jugadores"]] == [10, 10, 10]


def test_turno_completo_robar_del_pozo_y_descartar(juego, sala):
    tope = partida(juego, sala, "Nico")["pozo"]
    juego.robar(sala, "Nico", "POZO")
    vista = partida(juego, sala, "Nico")
    assert tope in vista["mano"] and vista["nueva"] == tope and len(vista["mano"]) == 11
    descarte = vista["mano"][0]
    juego.descartar(sala, "Nico", descarte)
    caro = partida(juego, sala, "Caro")
    assert caro["pozo"] == descarte and caro["en_turno"] == "Caro" and caro["fase"] == "ESPERANDO_ROBO"
    assert caro["bitacora"][-2:] == [{"jugador": "Nico", "accion": "ROBAR_POZO", "carta": tope},
                                     {"jugador": "Nico", "accion": "DESCARTAR", "carta": descarte}]


def test_lo_robado_del_mazo_no_lo_ven_los_demas(juego, sala):
    antes = partida(juego, sala, "Nico")["mazo"]
    juego.robar(sala, "Nico", "MAZO")
    caro = partida(juego, sala, "Caro")
    assert caro["mazo"] == antes - 1
    assert caro["bitacora"][-1] == {"jugador": "Nico", "accion": "ROBAR_MAZO", "carta": None}


def test_fuera_de_turno_no_se_juega(juego, sala):
    with pytest.raises(ComandoFueraDeTurno, match="No es tu turno: ahora juega Nico"):
        juego.robar(sala, "Caro", "MAZO")


def test_robar_dos_veces_se_rechaza_con_mensaje(juego, sala):
    juego.robar(sala, "Nico", "MAZO")
    with pytest.raises(ComandoFueraDeTurno, match="Ya tomaste una carta"):
        juego.robar(sala, "Nico", "MAZO")


def test_descartar_sin_robar_se_rechaza_con_mensaje(juego, sala):
    carta = partida(juego, sala, "Nico")["mano"][0]
    with pytest.raises(ComandoFueraDeTurno, match="Primero toma una carta"):
        juego.descartar(sala, "Nico", carta)


def test_descartar_una_carta_ajena_no_cambia_el_turno(juego, sala):
    juego.robar(sala, "Nico", "MAZO")
    mia = partida(juego, sala, "Nico")["mano"]
    ajena = next(c for c in partida(juego, sala, "Caro")["mano"] if c not in mia)
    with pytest.raises(JugadaInvalida):
        juego.descartar(sala, "Nico", ajena)
    vista = partida(juego, sala, "Nico")
    assert vista["en_turno"] == "Nico" and vista["fase"] == "ESPERANDO_DESCARTE" and len(vista["mano"]) == 11


def test_el_turno_rota_y_vuelve_al_primero(juego, sala):
    for jugador in ("Nico", "Caro", "Eli"):
        juego.robar(sala, jugador, "MAZO")
        juego.descartar(sala, jugador, partida(juego, sala, jugador)["mano"][0])
    assert partida(juego, sala, "Eli")["en_turno"] == "Nico"


def test_jugar_antes_de_empezar(juego):
    sala = juego.crear_sala("Nico", "CLASICA_433")
    with pytest.raises(ErrorSala, match="todavía no empieza"):
        juego.robar(sala.codigo, "Nico", "MAZO")


def test_mazo_agotado_se_rebaraja_el_pozo(juego, sala):
    """Robar del mazo cuando se acaba no deja la partida trabada (23 cartas en el mazo, 40 robos)."""
    for _ in range(40):
        jugador = partida(juego, sala, "Nico")["en_turno"]
        juego.robar(sala, jugador, "MAZO")
        juego.descartar(sala, jugador, partida(juego, sala, jugador)["mano"][0])
    mesa = juego._partidas.obtener(sala).mesa
    assert mesa.rebarajadas >= 1
    assert len(mesa.mazo) + len(mesa.pozo) + sum(map(len, mesa.manos.values())) == 54  # ni se pierden ni se duplican
