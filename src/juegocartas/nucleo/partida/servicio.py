"""GameService: fachada del núcleo para la presentación (IComandosJuego).

Coordina sala (H1), mesa y orquestador (H2). No conoce ninguna variante concreta: las reglas y
la tabla de puntos se piden al registro por código (ADR-03). Cada comando que cambia el estado
termina en un evento del bus; la presentación lo usa para avisarles a los demás jugadores.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Any, Protocol

from juegocartas.nucleo.contrato import Carta, VariantePlugin
from juegocartas.nucleo.contrato.codigos import codigo, desde_codigo
from juegocartas.nucleo.contrato.combinaciones import mejor_cobertura
from juegocartas.nucleo.sala.salas import ErrorSala, Sala, SalaService
from juegocartas.nucleo.soporte.eventos import EventoPartida
from juegocartas.nucleo.turno.mesa import CARTAS_POR_MANO, Mesa
from juegocartas.nucleo.turno.orquestador import TurnOrchestrator

ORIGENES = ("MAZO", "POZO")
JUGADAS_VISIBLES = 8


class IResolverVariante(Protocol):
    def resolver(self, codigo: str) -> VariantePlugin: ...


class IPublicarEvento(Protocol):
    def publicar(self, evento: EventoPartida) -> None: ...


@dataclass
class Partida:
    mesa: Mesa
    ronda: int = 1
    bitacora: list[dict[str, Any]] = field(default_factory=list)
    nueva: dict[str, Carta] = field(default_factory=dict)  # carta que cada jugador tomó en su turno


class GameService:
    def __init__(self, salas: SalaService, orquestador: TurnOrchestrator,
                 variantes: IResolverVariante, eventos: IPublicarEvento) -> None:
        self._salas = salas
        self._orquestador = orquestador
        self._variantes = variantes
        self._eventos = eventos
        self._partidas: dict[str, Partida] = {}

    # ---------- Sala (H1) ----------
    def crear_sala(self, nombre: str, variante: str) -> Sala:
        try:
            return self._salas.crear(nombre, variante)
        except KeyError as exc:
            raise ErrorSala("Esa modalidad no existe.") from exc

    def unirse(self, codigo_sala: str, nombre: str) -> Sala:
        sala = self._salas.unirse(codigo_sala, nombre)
        self._eventos.publicar(EventoPartida("SalaActualizada", sala.codigo, {"entro": sala.jugadores[-1]}))
        return sala

    def empezar(self, codigo_sala: str, quien: str) -> None:
        sala = self._salas.empezar(codigo_sala, quien)
        comodines = sala.config.get("comodines_habilitados", True)
        mesa = Mesa.repartir(sala.jugadores, comodines, secrets.randbelow(2**31))
        self._partidas[sala.codigo] = Partida(mesa)
        self._orquestador.iniciar(sala.codigo, sala.variante, sala.config, sala.jugadores[0], sala.jugadores)
        self._eventos.publicar(EventoPartida("PartidaIniciada", sala.codigo, {}))

    # ---------- Turno (H2) ----------
    def robar(self, codigo_sala: str, jugador: str, origen: str) -> None:
        if origen not in ORIGENES:
            raise ErrorSala("Toma la carta del mazo o del pozo.")
        partida = self._partida(codigo_sala)
        mesa = partida.mesa
        tomar = mesa.robar_mazo if origen == "MAZO" else mesa.tomar_pozo
        carta = self._orquestador.robar(codigo_sala, jugador, lambda: tomar(jugador))
        partida.nueva = {jugador: carta}
        visible = codigo(carta) if origen == "POZO" else None  # lo robado del mazo no lo ven los demás
        self._anotar(partida, jugador, "ROBAR_" + origen, visible)

    def descartar(self, codigo_sala: str, jugador: str, carta_codigo: str) -> None:
        partida = self._partida(codigo_sala)
        try:
            carta = desde_codigo(carta_codigo)
        except (ValueError, KeyError, IndexError) as exc:
            raise ErrorSala("Esa carta no existe.") from exc
        self._orquestador.descartar(codigo_sala, jugador, lambda: partida.mesa.descartar(jugador, carta))
        partida.nueva = {}
        self._anotar(partida, jugador, "DESCARTAR", carta_codigo)

    # ---------- Consulta ----------
    def vista(self, codigo_sala: str, jugador: str) -> dict[str, Any]:
        """Lo que ve un jugador: la sala, y si hay partida, su mano y lo público de la mesa."""
        sala = self._salas.obtener(codigo_sala)
        partida = self._partidas.get(sala.codigo)
        manos = partida.mesa.manos if partida else {}
        vista = {
            "sala": sala.codigo, "variante": sala.variante, "estado": sala.estado,
            "anfitrion": sala.anfitrion, "capacidad": sala.capacidad, "yo": jugador,
            "jugadores": [{"nombre": j, "cartas": len(manos.get(j, ()))} for j in sala.jugadores],
            "partida": None,
        }
        if partida:
            vista["partida"] = self._vista_partida(sala, partida, jugador)
        return vista

    def _vista_partida(self, sala: Sala, partida: Partida, jugador: str) -> dict[str, Any]:
        turno = self._orquestador.estado(sala.codigo)
        mesa = partida.mesa
        mano = mesa.manos.get(jugador, [])
        return {
            "ronda": partida.ronda, "en_turno": turno.en_turno, "fase": turno.fase.value,
            "mazo": len(mesa.mazo), "pozo": codigo(mesa.pozo[-1]) if mesa.pozo else None,
            "mano": [codigo(c) for c in mano],
            "nueva": codigo(partida.nueva[jugador]) if jugador in partida.nueva else None,
            "analisis": self._analizar(sala, mano),
            "bitacora": partida.bitacora[-JUGADAS_VISIBLES:],
        }

    def _analizar(self, sala: Sala, mano: list[Carta]) -> dict[str, Any]:
        """Combinaciones ya formadas y puntos sueltos, con la tabla de puntos de la variante."""
        tabla = self._variantes.resolver(sala.variante).tabla_puntos(sala.config)
        combos, sueltas = mejor_cobertura(mano, lambda c: tabla.puntos(c) * 100 + 1)
        # Con la carta del turno en la mano, al cerrar sale una: se cuenta sin la suelta más alta.
        descarte = max(sueltas, key=tabla.puntos) if sueltas and len(mano) > CARTAS_POR_MANO else None
        return {
            "combos": [{"tipo": c.tipo.value, "cartas": [codigo(x) for x in c.cartas]} for c in combos],
            "puntos_sueltos": sum(tabla.puntos(c) for c in sueltas) - (tabla.puntos(descarte) if descarte else 0),
            "sin_contar": codigo(descarte) if descarte else None,
        }

    def _partida(self, codigo_sala: str) -> Partida:
        partida = self._partidas.get(self._salas.obtener(codigo_sala).codigo)
        if partida is None:
            raise ErrorSala("La partida todavía no empieza.")
        return partida

    def _anotar(self, partida: Partida, jugador: str, accion: str, carta: str | None) -> None:
        partida.bitacora.append({"jugador": jugador, "accion": accion, "carta": carta})

