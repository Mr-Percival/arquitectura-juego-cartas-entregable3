"""Señalar ternas y escaleras y contar puntos sueltos (decisiones.md del E3, 2026-10-30)."""
from juegocartas.nucleo.contrato.codigos import codigo, desde_codigo
from juegocartas.nucleo.contrato.combinaciones import mejor_cobertura
from juegocartas.plugins.apuntado.plugin import TablaPuntosEstandar
from armado import gateway, juego  # noqa: F401  (fixtures)

TABLA = TablaPuntosEstandar()


def mano(texto):
    return [desde_codigo(c) for c in texto.split()]


def test_codigos_ida_y_vuelta():
    for texto in ("AH", "10S", "KD", "7C", "JK"):
        assert codigo(desde_codigo(texto)) == texto


def test_cobertura_minimiza_los_puntos_sueltos():
    combos, sueltas = mejor_cobertura(mano("7H 7S 7D 3C 4C 5C KS KH KD 2D QC"), TABLA.puntos)
    assert len(combos) == 3
    assert sorted(codigo(c) for c in sueltas) == ["2D", "QC"]


def test_cobertura_usa_el_comodin_para_llenar_un_hueco():
    combos, sueltas = mejor_cobertura(mano("4S JK 6S 9H"), TABLA.puntos)
    assert [len(c.cartas) for c in combos] == [3] and [codigo(c) for c in sueltas] == ["9H"]


def test_con_11_cartas_se_cuenta_sin_la_suelta_mas_alta(juego):
    sala = juego.crear_sala("Nico", "APUNTADO_101")
    analisis = juego._analizar(sala, mano("7H 7S 7D 3C 4C 5C KS KH KD 2D QC"))
    assert analisis["puntos_sueltos"] == 2 and analisis["sin_contar"] == "QC"
