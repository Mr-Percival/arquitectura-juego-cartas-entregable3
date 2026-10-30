"""Partidas en curso: la mesa, el marcador y la bitácora de cada sala mientras se juega.

GameService las escribe y el liquidador las lee (IConsultarRonda) al cerrar una ronda; por eso
viven aparte y no dentro del servicio, que a su vez depende del orquestador que usa al liquidador.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Any

from juegocartas.nucleo.contrato import Carta, Marcador
from juegocartas.nucleo.puntuacion.liquidador import RondaEnCurso
from juegocartas.nucleo.turno.mesa import Mesa


@dataclass
class Partida:
    mesa: Mesa
    variante: str
    config: dict[str, Any]
    marcador: Marcador
    abre: str  # quién empezó la ronda actual; la siguiente la abre el que sigue
    ronda: int = 1
    turno: int = 1
    serie: str = field(default_factory=lambda: secrets.token_hex(4))  # distingue partidas de la misma sala
    bitacora: list[dict[str, Any]] = field(default_factory=list)
    nueva: dict[str, Carta] = field(default_factory=dict)  # carta que cada jugador tomó en su turno
    resumen: dict[str, Any] | None = None  # la última ronda liquidada, para el diálogo de la pantalla
    ganador: str | None = None

    @property
    def jugadores(self) -> list[str]:
        return list(self.marcador.saldos)

    def vivos(self) -> list[str]:
        return [j for j in self.marcador.saldos if j not in self.marcador.eliminados]


class PartidasEnCurso:
    """Provee IConsultarRonda."""

    def __init__(self) -> None:
        self._partidas: dict[str, Partida] = {}

    def guardar(self, codigo_sala: str, partida: Partida) -> None:
        self._partidas[codigo_sala] = partida

    def obtener(self, codigo_sala: str) -> Partida | None:
        return self._partidas.get(codigo_sala)

    def ronda_en_curso(self, partida_id: str) -> RondaEnCurso:
        p = self._partidas[partida_id]
        return RondaEnCurso(f"{partida_id}-{p.serie}-R{p.ronda}", p.variante, p.config, p.turno,
                            {j: list(m) for j, m in p.mesa.manos.items()}, p.marcador)
