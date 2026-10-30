"""H6. Bitácora de auditoría.

Acepta si: cada partida deja un log de jugadas y cierres (aceptados y rechazados, con su hora) que
sirve de evidencia en la sección 3.2. Se descarga como CSV; la ronda en juego no sale, para no revelar
las manos. El mismo flujo contra PostgreSQL está en tests/integracion/test_persistencia_postgres.py.
"""
from fastapi.testclient import TestClient

from juegocartas.nucleo.contrato.codigos import desde_codigo
from juegocartas.presentacion.web import crear_app
from armado import gateway, juego  # noqa: F401  (fixtures)

TOCA = "7H 7S 7D 3C 4C 5C KS KH KD 2D QC"
NO_ALCANZA = "7H 7S 7D 3C 4C 5C KS KH KD 8H QC"


def jugar_una_ronda(juego):
    """Nico roba y descarta, Caro roba y descarta, Nico roba, intenta cerrar sin poder y luego cierra."""
    sala = juego.crear_sala("Nico", "APUNTADO_101").codigo
    juego.unirse(sala, "Caro")
    juego.empezar(sala, "Nico")
    for jugador in ("Nico", "Caro"):
        juego.robar(sala, jugador, "MAZO")
        juego.descartar(sala, jugador, juego.vista(sala, jugador)["partida"]["mano"][0])
    juego.robar(sala, "Nico", "POZO")
    manos = juego._partidas.obtener(sala).mesa.manos
    manos["Nico"] = [desde_codigo(c) for c in NO_ALCANZA.split()]
    try:
        juego.cerrar(sala, "Nico")
    except Exception:
        pass
    assert juego.bitacora(sala) == []  # la ronda sigue en juego: todavía no se publica
    manos["Nico"] = [desde_codigo(c) for c in TOCA.split()]
    juego.cerrar(sala, "Nico")
    return sala


def test_la_ronda_queda_registrada_jugada_por_jugada(juego):
    sala = jugar_una_ronda(juego)
    filas = juego.bitacora(sala)
    resumen = [(f["turno"], f["jugador"], f["accion"], f["resultado"]) for f in filas]
    assert resumen == [
        (1, "Nico", "ROBAR_MAZO", "ACEPTADA"), (1, "Nico", "DESCARTAR", "ACEPTADA"),
        (2, "Caro", "ROBAR_MAZO", "ACEPTADA"), (2, "Caro", "DESCARTAR", "ACEPTADA"),
        (3, "Nico", "ROBAR_DESCARTE", "ACEPTADA"),
        (3, "Nico", "SOLICITAR_CIERRE", "RECHAZADA"), (3, "Nico", "SOLICITAR_CIERRE", "ACEPTADA"),
    ]
    assert all(f["carta"] for f in filas[:5])  # la auditoría sí guarda lo robado del mazo
    assert filas[5]["motivo"].startswith("Te quedan 8 puntos sueltos")
    assert [f["ocurrida_en"] for f in filas] == sorted(f["ocurrida_en"] for f in filas)
    assert {(f["partida"], f["ronda"]) for f in filas} == {(1, 1)}


def test_se_descarga_como_csv(gateway):
    sala = jugar_una_ronda(gateway._juego)
    respuesta = TestClient(crear_app(gateway)).get(f"/bitacora/{sala.lower()}.csv")
    assert respuesta.status_code == 200 and respuesta.headers["content-type"].startswith("text/csv")
    lineas = respuesta.text.strip().splitlines()
    assert lineas[0] == "ocurrida_en,partida,ronda,turno,jugador,accion,carta,resultado,motivo"
    assert len(lineas) == 1 + 7
    assert TestClient(crear_app(gateway)).get("/bitacora/NOEXIS.csv").status_code == 404
