"""MatchRecordComponent y su puerto de salida IRepositorioPartidas.

El núcleo define el puerto; el adaptador de PostgreSQL (paquete persistencia) lo
implementa. Así el núcleo nunca importa la base de datos (regla R1).
Además del cierre (sección 2.4), guarda la bitácora de auditoría de cada partida (H6):
quién robó, qué descartó y cada intento de cierre, aceptado o rechazado, con su hora.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

ACCIONES = ("ROBAR_MAZO", "ROBAR_DESCARTE", "DESCARTAR", "SOLICITAR_CIERRE")  # CHECK de turno_jugada


@dataclass(frozen=True)
class CierreRonda:
    partida_id: str
    ronda_id: str
    jugador_cierra: str
    tipo_cierre: str
    penalizaciones: dict[str, int]
    bonificaciones: dict[str, int]
    eliminados: tuple[str, ...]
    partida_terminada: bool
    ganador: str | None
    comando_id: str
    numero_turno: int


@dataclass(frozen=True)
class Jugada:
    partida_id: str  # código de la sala
    ronda_id: str
    jugador: str
    numero_turno: int
    accion: str  # una de ACCIONES
    carta: str | None = None
    motivo_rechazo: str | None = None  # solo en un cierre rechazado


class RondaYaLiquidada(Exception):
    """Otro jugador cerró primero: la transacción encontró la ronda en estado LIQUIDADA."""


class IRepositorioPartidas(Protocol):
    def liquidar_ronda(self, cierre: CierreRonda) -> None:
        """Escribe todo el cierre en UNA transacción (ver sección 2.4)."""

    def historial(self, partida_id: str) -> list[dict]: ...

    def abrir_partida(self, sala: str, serie: str, variante: str, config: Mapping[str, Any],
                      jugadores: Sequence[str], capacidad: int) -> None: ...

    def abrir_ronda(self, sala: str, serie: str, ronda_id: str, numero: int, semilla: int,
                    jugadores: Sequence[str]) -> None: ...

    def anotar_jugada(self, jugada: Jugada) -> None: ...

    def bitacora(self, sala: str) -> list[dict]:
        """Jugadas de las rondas ya liquidadas (las de la ronda en juego revelarían las manos)."""


class MatchRecord:
    """Provee IRegistrarRonda, IConsultarHistorial e IBitacora; requiere IRepositorioPartidas."""

    def __init__(self, repositorio: IRepositorioPartidas) -> None:
        self._repo = repositorio

    def registrar_ronda(self, cierre: CierreRonda) -> None:
        self._repo.liquidar_ronda(cierre)

    def consultar_historial(self, partida_id: str) -> list[dict]:
        return self._repo.historial(partida_id)

    def abrir_partida(self, sala: str, serie: str, variante: str, config: Mapping[str, Any],
                      jugadores: Sequence[str], capacidad: int) -> None:
        self._repo.abrir_partida(sala, serie, variante, config, jugadores, capacidad)

    def abrir_ronda(self, sala: str, serie: str, ronda_id: str, numero: int, semilla: int,
                    jugadores: Sequence[str]) -> None:
        self._repo.abrir_ronda(sala, serie, ronda_id, numero, semilla, jugadores)

    def anotar_jugada(self, jugada: Jugada) -> None:
        self._repo.anotar_jugada(jugada)

    def consultar_bitacora(self, sala: str) -> list[dict]:
        return self._repo.bitacora(sala)
