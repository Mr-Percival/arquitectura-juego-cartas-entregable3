"""RepositorioEnMemoria: implementa IRepositorioPartidas sin base de datos.

Sirve para las pruebas y para correr el MVP sin PostgreSQL (si no hay DATABASE_URL).
Igual que el adaptador de PostgreSQL, rechaza liquidar dos veces la misma ronda y solo
entrega la bitácora de las rondas ya liquidadas.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from juegocartas.nucleo.soporte.historial import CierreRonda, Jugada, RondaYaLiquidada


class RepositorioEnMemoria:
    def __init__(self) -> None:
        self._cierres: dict[str, CierreRonda] = {}
        self._rondas: dict[str, tuple[str, int]] = {}  # ronda_id -> (serie, número)
        self._series: dict[str, list[str]] = {}  # sala -> series de sus partidas, en orden
        self._jugadas: list[dict[str, Any]] = []
        self._candado = threading.Lock()

    def liquidar_ronda(self, cierre: CierreRonda) -> None:
        with self._candado:
            if cierre.ronda_id in self._cierres:
                raise RondaYaLiquidada(cierre.ronda_id)
            self._cierres[cierre.ronda_id] = cierre
            self._agregar(Jugada(cierre.partida_id, cierre.ronda_id, cierre.jugador_cierra,
                                 cierre.numero_turno, "SOLICITAR_CIERRE"))

    def historial(self, partida_id: str) -> list[dict]:
        return [{"ronda_id": c.ronda_id, "jugador_id": j, "penalizacion": p,
                 "bonificacion": c.bonificaciones.get(j, 0)}
                for c in self._cierres.values() if c.partida_id == partida_id
                for j, p in c.penalizaciones.items()]

    def abrir_partida(self, sala: str, serie: str, variante: str, config: Mapping[str, Any],
                      jugadores: Sequence[str], capacidad: int) -> None:
        with self._candado:
            self._series.setdefault(sala, []).append(serie)

    def abrir_ronda(self, sala: str, serie: str, ronda_id: str, numero: int, semilla: int,
                    jugadores: Sequence[str]) -> None:
        with self._candado:
            self._rondas[ronda_id] = (serie, numero)

    def anotar_jugada(self, jugada: Jugada) -> None:
        with self._candado:
            self._agregar(jugada)

    def bitacora(self, sala: str) -> list[dict]:
        series = self._series.get(sala, [])
        return [{**j, "partida": series.index(self._rondas[j["ronda_id"]][0]) + 1,
                 "ronda": self._rondas[j["ronda_id"]][1]}
                for j in self._jugadas if j["sala"] == sala and j["ronda_id"] in self._cierres]

    def _agregar(self, jugada: Jugada) -> None:
        self._jugadas.append({
            "ocurrida_en": datetime.now(timezone.utc), "sala": jugada.partida_id, "ronda_id": jugada.ronda_id,
            "turno": jugada.numero_turno, "jugador": jugada.jugador, "accion": jugada.accion,
            "carta": jugada.carta, "resultado": "RECHAZADA" if jugada.motivo_rechazo else "ACEPTADA",
            "motivo": jugada.motivo_rechazo,
        })
