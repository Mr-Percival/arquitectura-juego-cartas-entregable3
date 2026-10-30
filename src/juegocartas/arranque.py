"""Composition root: arma el núcleo, descubre los plug-ins e inyecta los adaptadores.

Es el único módulo que conoce todas las piezas (R1: nadie más importa los adaptadores).
Se levanta con `uvicorn juegocartas.arranque:app`.
"""
from __future__ import annotations

from juegocartas.nucleo.evaluacion.evaluador import HandEvaluator
from juegocartas.nucleo.partida.servicio import GameService
from juegocartas.nucleo.registro.registro import PluginRegistry
from juegocartas.nucleo.sala.configuracion import RoomSetup
from juegocartas.nucleo.sala.salas import SalaService
from juegocartas.nucleo.soporte.eventos import LocalEventBus
from juegocartas.nucleo.turno.orquestador import TurnOrchestrator
from juegocartas.presentacion.gateway import GameGateway
from juegocartas.presentacion.web import crear_app


class CierrePendiente:
    """El cierre de ronda (H3 y H4) aún no está conectado: se completa en la siguiente historia."""

    def liquidar(self, partida_id, quien_cierra, evaluacion):
        raise NotImplementedError("H3/H4")

    def registrar_ronda(self, cierre) -> None:
        raise NotImplementedError("H3/H4")


def armar_gateway() -> GameGateway:
    variantes = PluginRegistry()
    variantes.descubrir()
    eventos = LocalEventBus()
    pendiente = CierrePendiente()
    orquestador = TurnOrchestrator(HandEvaluator(variantes), pendiente, pendiente, eventos)
    juego = GameService(SalaService(RoomSetup(variantes)), orquestador, variantes, eventos)
    return GameGateway(juego, eventos)


app = crear_app(armar_gateway())
