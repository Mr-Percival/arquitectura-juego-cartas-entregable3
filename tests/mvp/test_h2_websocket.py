"""H1 y H2 de punta a punta por WebSocket, como los usa el navegador.

Acepta si: dos jugadores entran a la misma sala desde conexiones distintas, un comando fuera de
turno vuelve como mensaje de error, y el otro jugador ve el descarte en menos de 1 s.
"""
import time

from fastapi.testclient import TestClient

from juegocartas.arranque import armar_gateway
from juegocartas.presentacion.web import crear_app


def esperar(ws, tipo, cumple=lambda m: True):
    """Lee mensajes hasta el primero del tipo pedido que cumpla la condición."""
    while True:
        mensaje = ws.receive_json()
        if mensaje["tipo"] == tipo and cumple(mensaje):
            return mensaje


def test_partida_entre_dos_conexiones():
    cliente = TestClient(crear_app(armar_gateway()))
    assert cliente.get("/salud").json() == {"estado": "ok"}
    assert "<title>" in cliente.get("/").text

    with cliente.websocket_connect("/ws") as nico, cliente.websocket_connect("/ws") as caro:
        nico.send_json({"accion": "crear", "nombre": "Nico", "variante": "APUNTADO_101"})
        sala = esperar(nico, "sesion")["sala"]
        caro.send_json({"accion": "unirse", "sala": sala, "nombre": "Caro"})
        assert esperar(caro, "sesion")["jugador"] == "Caro"
        esperar(nico, "estado", lambda m: [j["nombre"] for j in m["jugadores"]] == ["Nico", "Caro"])

        nico.send_json({"accion": "empezar"})
        assert esperar(caro, "estado", lambda m: m["partida"])["partida"]["en_turno"] == "Nico"

        caro.send_json({"accion": "robar", "origen": "MAZO"})
        assert esperar(caro, "error")["mensaje"] == "No es tu turno: ahora juega Nico."

        nico.send_json({"accion": "robar", "origen": "POZO"})
        mano = esperar(nico, "estado", lambda m: m["partida"]["fase"] == "ESPERANDO_DESCARTE")["partida"]["mano"]
        inicio = time.perf_counter()
        nico.send_json({"accion": "descartar", "carta": mano[0]})
        vista = esperar(caro, "estado", lambda m: m["partida"]["en_turno"] == "Caro")["partida"]
        assert time.perf_counter() - inicio < 1.0
        assert vista["pozo"] == mano[0]


def test_reconexion_con_el_token():
    """Adelanto de H5: al refrescar, el navegador vuelve con su token y recupera su mano."""
    cliente = TestClient(crear_app(armar_gateway()))
    with cliente.websocket_connect("/ws") as nico:
        nico.send_json({"accion": "crear", "nombre": "Nico", "variante": "CLASICA_433"})
        token = esperar(nico, "sesion")["token"]
    with cliente.websocket_connect("/ws") as otra_pestana:
        otra_pestana.send_json({"accion": "reconectar", "token": token})
        assert esperar(otra_pestana, "sesion")["jugador"] == "Nico"
        otra_pestana.send_json({"accion": "reconectar", "token": "no-existe"})
        assert "ya no existe" in esperar(otra_pestana, "error")["mensaje"]
