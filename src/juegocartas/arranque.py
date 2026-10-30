"""Composition root: arma el núcleo, descubre los plug-ins e inyecta los adaptadores.

Es el único módulo que conoce todas las piezas (R1: nadie más importa los adaptadores).
Se levanta con `uvicorn juegocartas.arranque:app`.
"""
from __future__ import annotations

from juegocartas.nucleo.evaluacion.evaluador import HandEvaluator
from juegocartas.nucleo.partida.partidas import PartidasEnCurso
from juegocartas.nucleo.partida.servicio import GameService
from juegocartas.nucleo.puntuacion.liquidador import LiquidadorRonda
from juegocartas.nucleo.registro.registro import PluginRegistry
from juegocartas.nucleo.sala.configuracion import RoomSetup
from juegocartas.nucleo.sala.salas import SalaService
from juegocartas.nucleo.soporte.eventos import LocalEventBus
from juegocartas.nucleo.soporte.historial import IRepositorioPartidas, MatchRecord
from juegocartas.nucleo.turno.orquestador import TurnOrchestrator
from juegocartas.persistencia.memoria import RepositorioEnMemoria
from juegocartas.presentacion.gateway import GameGateway
from juegocartas.presentacion.web import crear_app


def armar_gateway(repositorio: IRepositorioPartidas | None = None) -> GameGateway:
    variantes = PluginRegistry()
    variantes.descubrir()
    eventos = LocalEventBus()
    partidas = PartidasEnCurso()
    registro = MatchRecord(repositorio or RepositorioEnMemoria())
    orquestador = TurnOrchestrator(HandEvaluator(variantes), LiquidadorRonda(variantes, partidas), registro, eventos)
    juego = GameService(SalaService(RoomSetup(variantes)), orquestador, variantes, eventos, partidas)
    return GameGateway(juego, eventos)


app = crear_app(armar_gateway())
