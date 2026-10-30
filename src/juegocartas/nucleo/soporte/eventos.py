"""LocalEventBus: notificaciones en proceso, publicadas después de confirmar la transacción (ADR-05)."""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class EventoPartida:
    tipo: str  # CartaDescartada, TurnoCambiado, RondaLiquidada, PartidaFinalizada
    partida_id: str
    datos: dict[str, Any] = field(default_factory=dict)


Suscriptor = Callable[[EventoPartida], None]
registro = logging.getLogger(__name__)


class LocalEventBus:
    """Provee IPublicarEvento e ISuscribirEventos."""

    def __init__(self) -> None:
        self._suscriptores: dict[str, list[Suscriptor]] = defaultdict(list)

    def suscribir(self, tipo: str, suscriptor: Suscriptor) -> None:
        self._suscriptores[tipo].append(suscriptor)

    def publicar(self, evento: EventoPartida) -> None:
        for suscriptor in self._suscriptores[evento.tipo]:
            try:
                suscriptor(evento)
            except Exception:  # un suscriptor que falla no tumba el turno, pero queda en el log
                registro.exception("Falló un suscriptor de %s en %s", evento.tipo, evento.partida_id)
