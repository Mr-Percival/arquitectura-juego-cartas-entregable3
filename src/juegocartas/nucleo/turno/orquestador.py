"""TurnOrchestratorComponent: único mediador del flujo de turno (FSM).

Solo conoce interfaces (IEvaluarMano, ILiquidarRonda, IRegistrarRonda, IPublicarEvento).
No importa plug-ins, ni la base de datos, ni la presentación (reglas R1, R3 y R6).
Sección 2.4, capa 1: un candado por partida envuelve TODO el cierre (validar, evaluar,
liquidar, persistir y publicar). ADR-05: el evento se publica solo si la persistencia confirmó.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Protocol, Sequence

from juegocartas.nucleo.contrato import Carta, EvaluacionCierre
from juegocartas.nucleo.soporte.eventos import EventoPartida


class FaseTurno(Enum):
    ESPERANDO_ROBO = "ESPERANDO_ROBO"
    ESPERANDO_DESCARTE = "ESPERANDO_DESCARTE"
    FINALIZADO = "FINALIZADO"


class IEvaluarMano(Protocol):
    def evaluar_cierre(self, variante: str, config: Mapping[str, Any], mano: Sequence[Carta]) -> EvaluacionCierre: ...


class ILiquidarRonda(Protocol):
    def liquidar(self, partida_id: str, quien_cierra: str, evaluacion: EvaluacionCierre) -> Any:
        """Devuelve el CierreRonda listo para persistir (penalizaciones, eliminados, fin)."""


class IRegistrarRonda(Protocol):
    def registrar_ronda(self, cierre: Any) -> None: ...


class IPublicarEvento(Protocol):
    def publicar(self, evento: Any) -> None: ...


class ComandoFueraDeTurno(Exception):
    pass


# Lo que se le dice al jugador cuando intenta una acción que no toca en la fase actual (historia H2).
QUE_HACER = {
    FaseTurno.ESPERANDO_ROBO: "Primero toma una carta del mazo o del pozo.",
    FaseTurno.ESPERANDO_DESCARTE: "Ya tomaste una carta en este turno: ahora descarta o cierra la ronda.",
    FaseTurno.FINALIZADO: "La ronda ya terminó.",
}


@dataclass
class EstadoTurno:
    variante: str
    config: Mapping[str, Any]
    en_turno: str
    orden: list[str] = field(default_factory=list)
    fase: FaseTurno = FaseTurno.ESPERANDO_ROBO
    numero_turno: int = 1
    candado: threading.Lock = field(default_factory=threading.Lock)


class TurnOrchestrator:
    """Provee IComandosTurno."""

    def __init__(self, evaluador: IEvaluarMano, liquidador: ILiquidarRonda,
                 registro: IRegistrarRonda, eventos: IPublicarEvento) -> None:
        self._evaluador = evaluador
        self._liquidador = liquidador
        self._registro = registro
        self._eventos = eventos
        self._partidas: dict[str, EstadoTurno] = {}

    def iniciar(self, partida_id: str, variante: str, config: Mapping[str, Any], primero: str,
                orden: Sequence[str] = ()) -> None:
        self._partidas[partida_id] = EstadoTurno(variante, config, primero, list(orden) or [primero])

    def estado(self, partida_id: str) -> EstadoTurno:
        return self._partidas[partida_id]

    def robar(self, partida_id: str, jugador: str, accion: Callable[[], Any] | None = None) -> Any:
        """`accion` mueve la carta en la mesa bajo el mismo candado; si falla, la fase no cambia."""
        estado = self._partidas[partida_id]
        with estado.candado:
            self._exigir(estado, jugador, FaseTurno.ESPERANDO_ROBO)
            resultado = accion() if accion else None
            estado.fase = FaseTurno.ESPERANDO_DESCARTE
            self._eventos.publicar(EventoPartida("CartaRobada", partida_id, {"jugador": jugador}))
            return resultado

    def descartar(self, partida_id: str, jugador: str, accion: Callable[[], Any] | None = None) -> str:
        """Termina el turno: pasa al siguiente jugador del orden y devuelve quién juega ahora."""
        estado = self._partidas[partida_id]
        with estado.candado:
            self._exigir(estado, jugador, FaseTurno.ESPERANDO_DESCARTE)
            if accion:
                accion()
            siguiente = estado.orden[(estado.orden.index(jugador) + 1) % len(estado.orden)]
            estado.en_turno, estado.fase = siguiente, FaseTurno.ESPERANDO_ROBO
            estado.numero_turno += 1
            self._eventos.publicar(EventoPartida("CartaDescartada", partida_id,
                                                 {"jugador": jugador, "en_turno": siguiente}))
            return siguiente

    def solicitar_cierre(self, partida_id: str, jugador: str, mano: Sequence[Carta]) -> EvaluacionCierre:
        estado = self._partidas[partida_id]
        with estado.candado:
            self._exigir(estado, jugador, FaseTurno.ESPERANDO_DESCARTE)
            evaluacion = self._evaluador.evaluar_cierre(estado.variante, estado.config, mano)
            if not evaluacion.valida:
                return evaluacion
            cierre = self._liquidador.liquidar(partida_id, jugador, evaluacion)
            self._registro.registrar_ronda(cierre)  # si falla, la excepción sale y no se publica nada
            estado.fase = FaseTurno.FINALIZADO
            self._eventos.publicar(EventoPartida("RondaLiquidada", partida_id, {"cerrada_por": jugador, "cierre": cierre,
                                                                                "evaluacion": evaluacion}))
            return evaluacion

    @staticmethod
    def _exigir(estado: EstadoTurno, jugador: str, fase: FaseTurno) -> None:
        if estado.fase is not FaseTurno.FINALIZADO and jugador != estado.en_turno:
            raise ComandoFueraDeTurno(f"No es tu turno: ahora juega {estado.en_turno}.")
        if estado.fase is not fase:
            raise ComandoFueraDeTurno(QUE_HACER[estado.fase])
