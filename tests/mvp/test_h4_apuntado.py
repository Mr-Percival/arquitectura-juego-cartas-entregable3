"""H4. Cerrar ronda y acumular en Apuntado.

Acepta si: 3 ternas con sobrante < 5 cierra; sobrante de exactamente 5 se rechaza; a los demás se
les suman sus sobrantes; quien llega a 101 queda eliminado y la partida declara ganador (el
desempate R-11 está en tests/unidad/test_apuntado_fin_partida.py).
"""
import pytest

from juegocartas.nucleo.contrato.codigos import desde_codigo
from juegocartas.nucleo.sala.salas import ErrorSala
from armado import gateway, juego  # noqa: F401  (fixtures)

TOCA = "7H 7S 7D 3C 4C 5C KS KH KD 2D QC"   # 3 ternas; sueltas 2D y QC: Q se descarta, quedan 2 puntos
CARO = "2H 2S 2D 3D 3H 4S 5D 6C 8S 9D"       # terna de 2; sueltas 3+3+4+5+6+8+9 = 38
ELI = "AH AS AD JH JS JD 9C 9H 9S 4D"        # tres ternas; suelto el 4
NUEVO_REPARTO = 54 - 1


@pytest.fixture
def sala(juego):
    sala = juego.crear_sala("Nico", "APUNTADO_101")
    juego.unirse(sala.codigo, "Caro")
    juego.unirse(sala.codigo, "Eli")
    juego.empezar(sala.codigo, "Nico")
    juego.robar(sala.codigo, "Nico", "MAZO")
    manos = juego._partidas.obtener(sala.codigo).mesa.manos
    for jugador, texto in (("Nico", TOCA), ("Caro", CARO), ("Eli", ELI)):
        manos[jugador] = [desde_codigo(c) for c in texto.split()]
    return sala.codigo


def poner_mano(juego, sala, texto):
    juego._partidas.obtener(sala).mesa.manos["Nico"] = [desde_codigo(c) for c in texto.split()]


def filas(juego, sala):
    return {f["jugador"]: (f["ronda"], f["total"], f["fuera"]) for f in juego.vista(sala, "Nico")["partida"]["resumen"]["filas"]}


def test_tocar_con_menos_de_5_cierra_y_a_los_demas_se_les_suman_sus_sueltas(juego, sala):
    sueltas_caro = juego.vista(sala, "Caro")["partida"]["analisis"]["puntos_sueltos"]
    juego.cerrar(sala, "Nico")
    assert filas(juego, sala) == {"Nico": (0, 0, False), "Caro": (38, 38, False), "Eli": (4, 4, False)}
    assert sueltas_caro == 38  # lo mismo que la pantalla le mostraba a Caro junto a su mano
    resumen = juego.vista(sala, "Nico")["partida"]["resumen"]
    assert resumen["descarte"] == "QC" and resumen["quedan"] == ["2D"] and resumen["puntos_quedan"] == 2


def test_sobrante_de_exactamente_5_se_rechaza(juego, sala):
    poner_mano(juego, sala, "7H 7S 7D 3C 4C 5C KS KH KD 5H QC")
    with pytest.raises(ErrorSala, match=r"Te quedan 5 puntos sueltos \(5♥\)\. Con exactamente 5 no se puede"):
        juego.cerrar(sala, "Nico")


def test_sobrante_mayor_y_ternas_que_faltan_tambien_se_explican(juego, sala):
    poner_mano(juego, sala, "7H 7S 7D 3C 4C 5C KS KH KD 8H QC")
    with pytest.raises(ErrorSala, match=r"Te quedan 8 puntos sueltos \(8♥\)\. Para cerrar tienen que ser menos de 5"):
        juego.cerrar(sala, "Nico")
    poner_mano(juego, sala, "7H 7S 7D 3C 4C 5C KS QH 2D 9S JC")
    with pytest.raises(ErrorSala, match="Tienes 2 de las 3 ternas o escaleras"):
        juego.cerrar(sala, "Nico")


def test_ganar_completo_abona_el_bono(juego, sala):
    poner_mano(juego, sala, "7H 7S 7D 7C 3C 4C 5C KS KH KD 2D")
    juego.cerrar(sala, "Nico")
    assert filas(juego, sala)["Nico"] == (-10, -10, False)


def test_despues_de_cerrar_se_reparte_otra_ronda_y_la_abre_el_siguiente(juego, sala):
    juego.cerrar(sala, "Nico")
    vista = juego.vista(sala, "Caro")["partida"]
    assert vista["ronda"] == 2 and vista["en_turno"] == "Caro" and vista["fase"] == "ESPERANDO_ROBO"
    assert len(vista["mano"]) == 10 and vista["mazo"] == NUEVO_REPARTO - 3 * 10


def test_quien_llega_a_101_sale_y_la_partida_sigue_con_los_demas(juego, sala):
    juego._partidas.obtener(sala).marcador.saldos["Caro"] = 70
    juego.cerrar(sala, "Nico")
    assert filas(juego, sala)["Caro"] == (38, 108, True)
    vista = juego.vista(sala, "Caro")
    assert vista["partida"]["ronda"] == 2 and vista["partida"]["en_turno"] == "Eli"  # Caro ya no juega
    assert vista["partida"]["mano"] == [] and {j["nombre"]: j["fuera"] for j in vista["jugadores"]}["Caro"]


def test_cuando_queda_uno_solo_la_partida_declara_ganador(juego, sala):
    marcador = juego._partidas.obtener(sala).marcador
    marcador.saldos.update({"Caro": 70, "Eli": 99})
    juego.cerrar(sala, "Nico")
    vista = juego.vista(sala, "Eli")
    assert vista["partida"]["ganador"] == "Nico" and vista["partida"]["resumen"]["terminada"]
    assert vista["estado"] == "ABIERTA"  # el anfitrión puede empezar otra


def test_el_cierre_queda_en_el_registro(gateway, sala):
    juego = gateway._juego
    juego.cerrar(sala, "Nico")
    registro = juego._orquestador._registro
    filas_guardadas = {(f["jugador_id"], f["penalizacion"]) for f in registro.consultar_historial(sala)}
    assert filas_guardadas == {("Nico", 0), ("Caro", 38), ("Eli", 4)}
