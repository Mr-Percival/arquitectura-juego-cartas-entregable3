"""Mejoras 1 y 2 de la validación con usuarios (sección 3.4 del informe).

1. Cada modalidad trae su ayuda: el texto lo declara el plug-in y el núcleo solo lo reenvía.
2. Con la carta del turno en la mano, la vista dice si ya se puede cerrar y, si no, el motivo de la regla.
"""
import pytest

from juegocartas.nucleo.contrato.codigos import desde_codigo
from armado import gateway, juego  # noqa: F401  (fixtures)


@pytest.fixture
def sala(juego):
    sala = juego.crear_sala("Nico", "CLASICA_433")
    juego.unirse(sala.codigo, "Caro")
    juego.empezar(sala.codigo, "Nico")
    return sala.codigo


def con_mano(juego, sala, jugador, texto):
    juego.robar(sala, jugador, "MAZO")
    juego._partidas.obtener(sala).mesa.manos[jugador] = [desde_codigo(c) for c in texto.split()]


@pytest.mark.parametrize("variante, palabra", [("CLASICA_433", "cuarta"), ("APUNTADO_101", "101")])
def test_la_vista_trae_las_reglas_del_plugin(juego, variante, palabra):
    sala = juego.crear_sala("Ana", variante)
    reglas = juego.vista(sala.codigo, "Ana")["reglas"]
    assert len(reglas) >= 3 and any(palabra in r for r in reglas)


def test_avisa_que_ya_puede_cerrar(juego, sala):
    con_mano(juego, sala, "Nico", "7H 7S 7D 7C 3C 4C 5C KS KH KD 2D")
    analisis = juego.vista(sala, "Nico")["partida"]["analisis"]
    assert analisis["puede_cerrar"] is True and analisis["motivo_cierre"] is None


def test_avisa_que_falta_antes_de_intentar(juego, sala):
    con_mano(juego, sala, "Nico", "7H 7S 7D 3C 4C 5C KS KH 9D 2D QC")
    analisis = juego.vista(sala, "Nico")["partida"]["analisis"]
    assert analisis["puede_cerrar"] is False and analisis["motivo_cierre"].startswith("Te falta 1 cuarta")


def test_sin_la_carta_del_turno_no_se_evalua(juego, sala):
    analisis = juego.vista(sala, "Caro")["partida"]["analisis"]
    assert analisis["puede_cerrar"] is False and analisis["motivo_cierre"] is None
