"""H1. Crear y unirse a una sala.

Acepta si: 2 a 4 jugadores entran con el código desde dispositivos distintos; no se puede pasar
del cupo, ni siquiera con dos uniones simultáneas (riesgo de Elizabeth en el Risk Storming).
"""
import threading

import pytest

from juegocartas.nucleo.sala.salas import ALFABETO, LARGO_CODIGO, ErrorSala
from armado import gateway, juego  # noqa: F401  (fixtures)


def test_crear_sala_da_un_codigo_para_compartir(juego):
    sala = juego.crear_sala("Nico", "APUNTADO_101")
    assert len(sala.codigo) == LARGO_CODIGO and set(sala.codigo) <= set(ALFABETO)
    assert sala.jugadores == ["Nico"] and sala.config["umbral_eliminacion"] == 101


def test_entran_hasta_cuatro_con_el_codigo_sin_importar_mayusculas(juego):
    sala = juego.crear_sala("Nico", "CLASICA_433")
    for nombre in ("Caro", "Eli", "Juan"):
        juego.unirse(sala.codigo.lower(), nombre)
    assert sala.jugadores == ["Nico", "Caro", "Eli", "Juan"]


def test_el_quinto_no_entra(juego):
    sala = juego.crear_sala("Nico", "CLASICA_433")
    for nombre in ("Caro", "Eli", "Juan"):
        juego.unirse(sala.codigo, nombre)
    with pytest.raises(ErrorSala, match="llena"):
        juego.unirse(sala.codigo, "Pepe")


def test_dos_uniones_simultaneas_por_el_ultimo_puesto_solo_entra_una(juego):
    for _ in range(50):  # se repite para darle a la carrera la oportunidad de aparecer
        sala = juego.crear_sala("Nico", "CLASICA_433")
        juego.unirse(sala.codigo, "Caro")
        juego.unirse(sala.codigo, "Eli")
        barrera, resultados = threading.Barrier(2), []

        def entrar(nombre):
            barrera.wait()
            try:
                juego.unirse(sala.codigo, nombre)
                resultados.append("entró")
            except ErrorSala:
                resultados.append("rechazado")

        hilos = [threading.Thread(target=entrar, args=(n,)) for n in ("Juan", "Pepe")]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        assert sorted(resultados) == ["entró", "rechazado"]
        assert len(sala.jugadores) == 4


@pytest.mark.parametrize("codigo", ["ZZZZZZ", ""])
def test_codigo_que_no_existe(juego, codigo):
    with pytest.raises(ErrorSala, match="No hay ninguna sala"):
        juego.unirse(codigo, "Caro")


def test_nombre_repetido_o_vacio(juego):
    sala = juego.crear_sala("Nico", "APUNTADO_101")
    with pytest.raises(ErrorSala, match="Ya hay alguien"):
        juego.unirse(sala.codigo, " nico ")
    with pytest.raises(ErrorSala, match="nombre"):
        juego.unirse(sala.codigo, "   ")


def test_solo_el_anfitrion_empieza_y_con_al_menos_dos(juego):
    sala = juego.crear_sala("Nico", "APUNTADO_101")
    with pytest.raises(ErrorSala, match="al menos otra persona"):
        juego.empezar(sala.codigo, "Nico")
    juego.unirse(sala.codigo, "Caro")
    with pytest.raises(ErrorSala, match="la empieza Nico"):
        juego.empezar(sala.codigo, "Caro")
    juego.empezar(sala.codigo, "Nico")
    with pytest.raises(ErrorSala, match="ya empezó"):
        juego.unirse(sala.codigo, "Eli")


def test_modalidad_inexistente(juego):
    with pytest.raises(ErrorSala, match="modalidad"):
        juego.crear_sala("Nico", "CONTINENTAL")
