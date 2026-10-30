"""RepositorioEnMemoria: implementa IRepositorioPartidas sin base de datos.

Sirve para las pruebas y para correr el MVP sin PostgreSQL; la bitácora en PostgreSQL llega con H6.
Igual que el adaptador de PostgreSQL, rechaza liquidar dos veces la misma ronda.
"""
from __future__ import annotations

import threading

from juegocartas.nucleo.soporte.historial import CierreRonda, RondaYaLiquidada


class RepositorioEnMemoria:
    def __init__(self) -> None:
        self._cierres: dict[str, CierreRonda] = {}
        self._candado = threading.Lock()

    def liquidar_ronda(self, cierre: CierreRonda) -> None:
        with self._candado:
            if cierre.ronda_id in self._cierres:
                raise RondaYaLiquidada(cierre.ronda_id)
            self._cierres[cierre.ronda_id] = cierre

    def historial(self, partida_id: str) -> list[dict]:
        return [{"ronda_id": c.ronda_id, "jugador_id": j, "penalizacion": p,
                 "bonificacion": c.bonificaciones.get(j, 0)}
                for c in self._cierres.values() if c.partida_id == partida_id
                for j, p in c.penalizaciones.items()]
