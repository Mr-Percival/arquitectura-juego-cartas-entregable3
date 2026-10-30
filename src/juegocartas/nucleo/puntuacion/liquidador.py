"""RoundScoringComponent y MatchStandingsComponent, y el liquidador que el orquestador usa al cerrar."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol, Sequence

from juegocartas.nucleo.contrato import Carta, DecisionFin, EvaluacionCierre, Marcador, VariantePlugin
from juegocartas.nucleo.contrato.combinaciones import cartas_sueltas
from juegocartas.nucleo.soporte.historial import CierreRonda


class IResolverVariante(Protocol):
    def resolver(self, codigo: str) -> VariantePlugin: ...


class RoundScoring:
    """Provee ILiquidarRonda: convierte las manos sobrantes en penalizaciones con la tabla de la variante."""

    def __init__(self, registro: IResolverVariante) -> None:
        self._registro = registro

    def penalizaciones(self, variante: str, config: Mapping[str, Any],
                       sobrantes: Mapping[str, Sequence[Carta]]) -> dict[str, int]:
        tabla = self._registro.resolver(variante).tabla_puntos(config)
        return {jugador: sum(tabla.puntos(c) for c in cartas) for jugador, cartas in sobrantes.items()}


class MatchStandings:
    """Provee IActualizarMarcador: aplica deltas y consulta la política de fin de la variante."""

    def __init__(self, registro: IResolverVariante) -> None:
        self._registro = registro

    def actualizar(self, variante: str, config: Mapping[str, Any], marcador: Marcador,
                   deltas: Mapping[str, int]) -> DecisionFin:
        marcador.aplicar(dict(deltas))
        decision = self._registro.resolver(variante).politica_fin(config).evaluar(marcador)
        marcador.eliminados.update(decision.eliminados)
        return decision


@dataclass(frozen=True)
class RondaEnCurso:
    """Lo que el liquidador necesita saber de la ronda que se cierra (lo arma quien lleva la partida)."""

    ronda_id: str
    variante: str
    config: Mapping[str, Any]
    numero_turno: int
    manos: Mapping[str, Sequence[Carta]]  # solo los jugadores que siguen en la partida
    marcador: Marcador


class IConsultarRonda(Protocol):
    def ronda_en_curso(self, partida_id: str) -> RondaEnCurso: ...


class LiquidadorRonda:
    """Provee ILiquidarRonda (historias H3 y H4).

    A quien cierra no se le suma nada (si el plug-in declara `bono_<tipo>` en su configuración,
    se le abona ese bono); a los demás, los puntos de sus cartas sueltas. El fin de la partida se
    decide sobre una copia del marcador: el marcador real cambia solo cuando la ronda quedó
    guardada (ADR-05).
    """

    def __init__(self, registro: IResolverVariante, rondas: IConsultarRonda,
                 nuevo_id: Callable[[], str] = lambda: str(uuid.uuid4())) -> None:
        self._registro = registro
        self._rondas = rondas
        self._nuevo_id = nuevo_id
        self._contador = RoundScoring(registro)
        self._posiciones = MatchStandings(registro)

    def liquidar(self, partida_id: str, quien_cierra: str, evaluacion: EvaluacionCierre) -> CierreRonda:
        ronda = self._rondas.ronda_en_curso(partida_id)
        tabla = self._registro.resolver(ronda.variante).tabla_puntos(ronda.config)
        sueltas = {j: cartas_sueltas(mano, tabla.puntos)[1] for j, mano in ronda.manos.items() if j != quien_cierra}
        penalizaciones = {quien_cierra: 0, **self._contador.penalizaciones(ronda.variante, ronda.config, sueltas)}
        bono = ronda.config.get(f"bono_{(evaluacion.tipo or '').lower()}", 0)
        bonificaciones = {quien_cierra: bono} if bono else {}
        copia = Marcador(dict(ronda.marcador.saldos), set(ronda.marcador.eliminados))
        deltas = {j: p - bonificaciones.get(j, 0) for j, p in penalizaciones.items()}
        decision = self._posiciones.actualizar(ronda.variante, ronda.config, copia, deltas)
        ganador = decision.ganador or (quien_cierra if decision.terminada else None)  # Clásica: gana quien cerró
        return CierreRonda(partida_id, ronda.ronda_id, quien_cierra, evaluacion.tipo or "", penalizaciones,
                           bonificaciones, decision.eliminados, decision.terminada, ganador,
                           self._nuevo_id(), ronda.numero_turno)
