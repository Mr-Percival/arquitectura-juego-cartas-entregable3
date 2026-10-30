"""Código corto de cada carta, el mismo de la tabla `carta` del esquema: 'AH', '10S', 'KD'; el comodín es 'JK'."""
from __future__ import annotations

from .modelo import Carta, Pinta

RANGOS = {1: "A", 11: "J", 12: "Q", 13: "K"}
COMODIN = "JK"
SIMBOLOS = {Pinta.CORAZONES: "♥", Pinta.DIAMANTES: "♦", Pinta.TREBOLES: "♣", Pinta.PICAS: "♠"}


def codigo(carta: Carta) -> str:
    if carta.es_comodin:
        return COMODIN
    return f"{RANGOS.get(carta.rango, carta.rango)}{carta.pinta.value}"


def desde_codigo(texto: str, mazo: int = 1) -> Carta:
    if texto == COMODIN:
        return Carta.comodin(mazo)
    rango, pinta = texto[:-1], texto[-1]
    numero = {v: k for k, v in RANGOS.items()}.get(rango) or int(rango)
    if not 1 <= numero <= 13:
        raise ValueError(texto)
    return Carta(numero, Pinta(pinta), mazo)


def etiqueta(carta: Carta) -> str:
    """Cómo se le nombra la carta al jugador en un mensaje: '5♥', 'Q♣', 'Comodín'."""
    if carta.es_comodin:
        return "Comodín"
    return f"{RANGOS.get(carta.rango, carta.rango)}{SIMBOLOS[carta.pinta]}"
