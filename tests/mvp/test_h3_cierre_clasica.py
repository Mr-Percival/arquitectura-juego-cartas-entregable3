"""H3. Cerrar ronda en Clásica.

Acepta si: 1 cuarta + 2 ternas + 1 descarte gana la ronda; un cierre inválido se rechaza diciendo qué falta.
"""
import pytest

from juegocartas.nucleo.contrato.codigos import desde_codigo
from juegocartas.nucleo.sala.salas import ErrorSala
from juegocartas.nucleo.turno.orquestador import ComandoFueraDeTurno
from armado import gateway, juego  # noqa: F401  (fixtures)

GANADORA = "7H 7S 7D 7C 3C 4C 5C KS KH KD 2D"


@pytest.fixture
def sala(juego):
    sala = juego.crear_sala("Nico", "CLASICA_433")
    juego.unirse(sala.codigo, "Caro")
    juego.empezar(sala.codigo, "Nico")
    return sala.codigo


def con_mano(juego, sala, jugador, texto):
    """Roba (para quedar con 11 cartas) y fija la mano para que la prueba no dependa del azar."""
    juego.robar(sala, jugador, "MAZO")
    juego._partidas.obtener(sala).mesa.manos[jugador] = [desde_codigo(c) for c in texto.split()]


def test_cuarta_dos_ternas_y_descarte_gana(juego, sala):
    con_mano(juego, sala, "Nico", GANADORA)
    juego.cerrar(sala, "Nico")
    vista = juego.vista(sala, "Caro")
    resumen = vista["partida"]["resumen"]
    assert vista["partida"]["ganador"] == "Nico" and resumen["terminada"]
    assert resumen["descarte"] == "2D" and sorted(len(c["cartas"]) for c in resumen["combos"]) == [3, 3, 4]
    assert vista["partida"]["bitacora"][-1] == {"jugador": "Nico", "accion": "CERRAR", "carta": None}


@pytest.mark.parametrize("mano, mensaje", [
    ("7H 7S 7D 3C 4C 5C KS KH 9D 2D QC", "Te falta 1 cuarta. Tienes 2 ternas"),
    ("7H 7S 7D 7C 3C 4C 5C KS 9H 2D QC", "Te falta 1 terna. Tienes 1 cuarta y 1 terna"),
    ("7H 7S 2C 4C 6C KS QH 9D 2D 5H AS", "Te faltan 1 cuarta y 2 ternas. No tienes ninguna combinación"),
])
def test_cierre_invalido_dice_que_falta(juego, sala, mano, mensaje):
    con_mano(juego, sala, "Nico", mano)
    with pytest.raises(ErrorSala, match="No puedes cerrar todavía. " + mensaje):
        juego.cerrar(sala, "Nico")
    vista = juego.vista(sala, "Nico")["partida"]
    assert vista["en_turno"] == "Nico" and vista["fase"] == "ESPERANDO_DESCARTE" and vista["ganador"] is None


def test_no_se_cierra_sin_robar_ni_fuera_de_turno(juego, sala):
    with pytest.raises(ComandoFueraDeTurno, match="Primero toma una carta"):
        juego.cerrar(sala, "Nico")
    with pytest.raises(ComandoFueraDeTurno, match="No es tu turno"):
        juego.cerrar(sala, "Caro")


def test_el_anfitrion_puede_empezar_otra_partida(juego, sala):
    con_mano(juego, sala, "Nico", GANADORA)
    juego.cerrar(sala, "Nico")
    with pytest.raises(ErrorSala, match="la empieza Nico"):
        juego.empezar(sala, "Caro")
    juego.empezar(sala, "Nico")
    vista = juego.vista(sala, "Caro")["partida"]
    assert vista["ganador"] is None and vista["resumen"] is None and len(vista["mano"]) == 10


def test_si_no_se_puede_guardar_nada_cambia_y_se_puede_reintentar():
    """ADR-05: si la persistencia falla, la ronda no se da por cerrada."""
    from juegocartas.arranque import armar_gateway
    from juegocartas.persistencia.memoria import RepositorioEnMemoria

    class Caido(RepositorioEnMemoria):
        fallas = 1

        def liquidar_ronda(self, cierre):
            if self.fallas:
                self.fallas -= 1
                raise ConnectionError("sin base de datos")
            super().liquidar_ronda(cierre)

    juego = armar_gateway(Caido())._juego
    codigo = juego.crear_sala("Nico", "CLASICA_433").codigo
    juego.unirse(codigo, "Caro")
    juego.empezar(codigo, "Nico")
    con_mano(juego, codigo, "Nico", GANADORA)
    with pytest.raises(ErrorSala, match="No se pudo guardar"):
        juego.cerrar(codigo, "Nico")
    assert juego.vista(codigo, "Nico")["partida"]["ganador"] is None
    juego.cerrar(codigo, "Nico")
    assert juego.vista(codigo, "Nico")["partida"]["ganador"] == "Nico"
