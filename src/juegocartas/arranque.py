"""Composition root: arma el núcleo, descubre los plug-ins e inyecta los adaptadores.

Es el único módulo que conoce todas las piezas (R1: nadie más importa los adaptadores).
Se levanta con `uvicorn juegocartas.arranque:app`. Con la variable DATABASE_URL guarda los cierres
y la bitácora en PostgreSQL (crea el esquema si la base está vacía); sin ella, en memoria.
"""
from __future__ import annotations

import logging
import os

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
from juegocartas.persistencia.postgres import PostgresRepositoryAdapter
from juegocartas.presentacion.gateway import GameGateway
from juegocartas.presentacion.web import crear_app


def armar_gateway(repositorio: IRepositorioPartidas | None = None) -> GameGateway:
    variantes = PluginRegistry()
    variantes.descubrir()
    eventos = LocalEventBus()
    partidas = PartidasEnCurso()
    registro = MatchRecord(repositorio or RepositorioEnMemoria())
    orquestador = TurnOrchestrator(HandEvaluator(variantes), LiquidadorRonda(variantes, partidas), registro, eventos)
    juego = GameService(SalaService(RoomSetup(variantes)), orquestador, variantes, eventos, registro, partidas)
    return GameGateway(juego, eventos)


def repositorio_del_entorno() -> IRepositorioPartidas:
    """PostgreSQL si hay DATABASE_URL y responde; si la base no está disponible, el juego arranca en memoria.

    Plan de reversa del Release Checklist: una base caída o vencida no debe tumbar el juego.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        return RepositorioEnMemoria()
    try:
        return PostgresRepositoryAdapter.desde_url(url)
    except Exception:
        logging.getLogger(__name__).exception("PostgreSQL no disponible: el juego arranca con el repositorio en memoria")
        return RepositorioEnMemoria()


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = crear_app(armar_gateway(repositorio_del_entorno()))
