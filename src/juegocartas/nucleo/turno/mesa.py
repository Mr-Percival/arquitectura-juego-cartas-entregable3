"""Mesa de una ronda: mazo, pozo y la mano de cada jugador (el estado de las cartas que el orquestador protege)."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Sequence

from juegocartas.nucleo.contrato import Carta

from .repartidor import DeckDealer

CARTAS_POR_MANO = 10


class JugadaInvalida(Exception):
    """La mesa no permite la jugada (pozo vacío, carta que no está en la mano)."""


@dataclass
class Mesa:
    mazo: list[Carta]
    pozo: list[Carta]
    manos: dict[str, list[Carta]]
    semilla: int = 0
    rebarajadas: int = field(default=0)

    @classmethod
    def repartir(cls, jugadores: Sequence[str], comodines: bool, semilla: int) -> "Mesa":
        dealer = DeckDealer()
        mazo = dealer.construir(1, comodines)
        manos = dealer.repartir(mazo, list(jugadores), CARTAS_POR_MANO, semilla)
        return cls(mazo, [mazo.pop()], manos, semilla)

    def robar_mazo(self, jugador: str) -> Carta:
        if not self.mazo:
            self._rebarajar_pozo()
        carta = self.mazo.pop()
        self.manos[jugador].append(carta)
        return carta

    def tomar_pozo(self, jugador: str) -> Carta:
        if not self.pozo:
            raise JugadaInvalida("El pozo está vacío: roba del mazo.")
        carta = self.pozo.pop()
        self.manos[jugador].append(carta)
        return carta

    def descartar(self, jugador: str, carta: Carta) -> None:
        if carta not in self.manos[jugador]:
            raise JugadaInvalida("Esa carta no está en tu mano.")
        self.manos[jugador].remove(carta)
        self.pozo.append(carta)

    def _rebarajar_pozo(self) -> None:
        """Mazo agotado: el pozo, menos su carta de arriba, se baraja y vuelve a ser el mazo."""
        if len(self.pozo) < 2:
            raise JugadaInvalida("No quedan cartas para robar.")
        tope = self.pozo.pop()
        self.mazo, self.pozo = self.pozo, [tope]
        self.rebarajadas += 1
        random.Random(self.semilla + self.rebarajadas).shuffle(self.mazo)
