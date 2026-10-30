"""H5. Reconexión.

Acepta si: al refrescar el navegador el jugador vuelve a su mano y su turno (riesgo R-01 del E2).
Además, los demás ven quién está sin conexión, y si abre el juego en otra pestaña la vieja se entera.
"""
from fastapi.testclient import TestClient

from juegocartas.arranque import armar_gateway
from juegocartas.presentacion.web import crear_app
from test_h2_websocket import esperar


def partida(cliente):
    """Nico crea, Caro entra, empieza la partida y Nico roba: queda a mitad de su turno."""
    nico, caro = cliente.websocket_connect("/ws"), cliente.websocket_connect("/ws")
    nico.__enter__(), caro.__enter__()
    nico.send_json({"accion": "crear", "nombre": "Nico", "variante": "APUNTADO_101"})
    sesion = esperar(nico, "sesion")
    caro.send_json({"accion": "unirse", "sala": sesion["sala"], "nombre": "Caro"})
    esperar(caro, "sesion")
    nico.send_json({"accion": "empezar"})
    nico.send_json({"accion": "robar", "origen": "MAZO"})
    antes = esperar(nico, "estado", lambda m: m["partida"] and m["partida"]["fase"] == "ESPERANDO_DESCARTE")
    return nico, caro, sesion["token"], antes["partida"]


def test_al_refrescar_vuelve_a_su_mano_y_a_su_turno_a_mitad_de_jugada():
    cliente = TestClient(crear_app(armar_gateway()))
    nico, caro, token, antes = partida(cliente)
    nico.__exit__(None, None, None)  # refrescar = se cierra la conexión y se abre otra
    with cliente.websocket_connect("/ws") as de_nuevo:
        de_nuevo.send_json({"accion": "reconectar", "token": token})
        despues = esperar(de_nuevo, "estado", lambda m: m["partida"])["partida"]
    assert despues["mano"] == antes["mano"] and len(despues["mano"]) == 11
    assert (despues["en_turno"], despues["fase"], despues["nueva"]) == ("Nico", "ESPERANDO_DESCARTE", antes["nueva"])
    caro.__exit__(None, None, None)


def test_los_demas_ven_quien_esta_sin_conexion_y_cuando_vuelve():
    cliente = TestClient(crear_app(armar_gateway()))
    nico, caro, token, _ = partida(cliente)
    nico.__exit__(None, None, None)
    assert esperar(caro, "estado", lambda m: m["conectados"] == ["Caro"])
    with cliente.websocket_connect("/ws") as de_nuevo:
        de_nuevo.send_json({"accion": "reconectar", "token": token})
        assert esperar(caro, "estado", lambda m: sorted(m["conectados"]) == ["Caro", "Nico"])
    caro.__exit__(None, None, None)


def test_si_abre_otra_pestana_la_anterior_se_entera():
    cliente = TestClient(crear_app(armar_gateway()))
    nico, caro, token, _ = partida(cliente)
    with cliente.websocket_connect("/ws") as otra:
        otra.send_json({"accion": "reconectar", "token": token})
        esperar(otra, "sesion")
        assert esperar(nico, "reemplazada")
        otra.send_json({"accion": "descartar", "carta": esperar(otra, "estado")["partida"]["mano"][0]})
        assert esperar(caro, "estado", lambda m: m["partida"] and m["partida"]["en_turno"] == "Caro")
    nico.__exit__(None, None, None), caro.__exit__(None, None, None)
