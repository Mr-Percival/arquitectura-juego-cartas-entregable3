"""GameService: fachada del núcleo para la presentación (IComandosJuego).

Coordina sala (H1), mesa y orquestador (H2) y el cierre de ronda (H3 y H4). No conoce ninguna
variante concreta: las reglas y la tabla de puntos se piden al registro por código (ADR-03). Cada
comando que cambia el estado termina en un evento del bus; la presentación lo usa para avisarles a
los demás jugadores. El marcador y la ronda siguiente cambian al oír RondaLiquidada, que solo se
publica si la ronda quedó guardada (ADR-05).
"""
from __future__ import annotations

import secrets
from typing import Any, Callable, Protocol

from juegocartas.nucleo.contrato import Carta, EvaluacionCierre, Marcador, VariantePlugin
from juegocartas.nucleo.contrato.codigos import codigo, desde_codigo
from juegocartas.nucleo.contrato.combinaciones import cartas_sueltas
from juegocartas.nucleo.sala.salas import ErrorSala, Sala, SalaService
from juegocartas.nucleo.soporte.eventos import EventoPartida
from juegocartas.nucleo.soporte.historial import CierreRonda, RondaYaLiquidada
from juegocartas.nucleo.turno.mesa import CARTAS_POR_MANO, Mesa
from juegocartas.nucleo.turno.orquestador import ComandoFueraDeTurno, TurnOrchestrator

from .partidas import Partida, PartidasEnCurso

ORIGENES = ("MAZO", "POZO")
JUGADAS_VISIBLES = 8


class IResolverVariante(Protocol):
    def resolver(self, codigo: str) -> VariantePlugin: ...


class IEventos(Protocol):
    def publicar(self, evento: EventoPartida) -> None: ...

    def suscribir(self, tipo: str, suscriptor: Callable[[EventoPartida], None]) -> None: ...


class GameService:
    def __init__(self, salas: SalaService, orquestador: TurnOrchestrator, variantes: IResolverVariante,
                 eventos: IEventos, partidas: PartidasEnCurso | None = None) -> None:
        self._salas = salas
        self._orquestador = orquestador
        self._variantes = variantes
        self._eventos = eventos
        self._partidas = partidas or PartidasEnCurso()
        eventos.suscribir("RondaLiquidada", self._al_liquidar)

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
        partida = Partida(self._repartir(sala, sala.jugadores), sala.variante, sala.config,
                          Marcador({j: 0 for j in sala.jugadores}), abre=sala.jugadores[0])
        self._partidas.guardar(sala.codigo, partida)
        self._orquestador.iniciar(sala.codigo, sala.variante, sala.config, partida.abre, sala.jugadores)
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
        partida.turno += 1
        self._anotar(partida, jugador, "DESCARTAR", carta_codigo)

    # ---------- Cierre (H3 y H4) ----------
    def cerrar(self, codigo_sala: str, jugador: str) -> None:
        """Pide el cierre con la mano completa; si la regla lo rechaza, el mensaje dice qué falta."""
        partida = self._partida(codigo_sala)
        mano = list(partida.mesa.manos.get(jugador, []))
        try:
            evaluacion = self._orquestador.solicitar_cierre(self._salas.obtener(codigo_sala).codigo, jugador, mano)
        except ComandoFueraDeTurno:
            raise
        except RondaYaLiquidada as exc:
            raise ErrorSala("Esta ronda ya se cerró.") from exc
        except Exception as exc:  # no se pudo guardar: nada cambió (ADR-05) y el jugador sigue en su turno
            raise ErrorSala("No se pudo guardar el cierre. Intenta otra vez.") from exc
        if not evaluacion.valida:
            raise ErrorSala("No puedes cerrar todavía. " + evaluacion.motivo_rechazo)
        self._anotar(partida, jugador, "CERRAR", None)

    def _al_liquidar(self, evento: EventoPartida) -> None:
        """La ronda ya quedó guardada: se actualiza el marcador y se reparte otra o se declara el ganador."""
        cierre: CierreRonda = evento.datos["cierre"]
        partida = self._partidas.obtener(evento.partida_id)
        nuevos = [j for j in cierre.eliminados if j not in partida.marcador.eliminados]
        partida.marcador.aplicar({j: p - cierre.bonificaciones.get(j, 0) for j, p in cierre.penalizaciones.items()})
        partida.marcador.eliminados.update(cierre.eliminados)
        partida.resumen = self._resumir(partida, cierre, evento.datos["evaluacion"], nuevos)
        if cierre.partida_terminada:
            partida.ganador = cierre.ganador
            self._salas.reabrir(evento.partida_id)  # el anfitrión puede empezar otra con la misma sala
            self._eventos.publicar(EventoPartida("PartidaFinalizada", evento.partida_id, {"ganador": cierre.ganador}))
        else:
            self._siguiente_ronda(self._salas.obtener(evento.partida_id), partida)

    def _siguiente_ronda(self, sala: Sala, partida: Partida) -> None:
        vivos, orden = partida.vivos(), partida.jugadores
        partida.abre = next(j for j in orden[orden.index(partida.abre) + 1:] + orden if j in vivos)
        partida.mesa = self._repartir(sala, vivos)
        partida.ronda, partida.turno, partida.nueva = partida.ronda + 1, 1, {}
        self._orquestador.iniciar(sala.codigo, sala.variante, sala.config, partida.abre, vivos)

    def _resumir(self, partida: Partida, cierre: CierreRonda, evaluacion: EvaluacionCierre,
                 nuevos: list[str]) -> dict[str, Any]:
        """Lo que muestra el diálogo de fin de ronda: con qué cerró, qué descartó y cómo va cada uno."""
        tabla = self._variantes.resolver(partida.variante).tabla_puntos(partida.config)
        descarte, resto = self._sobrante(partida.mesa.manos[cierre.jugador_cierra], evaluacion, tabla.puntos)
        return {
            "numero": partida.ronda, "cerro": cierre.jugador_cierra,
            "combos": [{"tipo": c.tipo.value, "cartas": [codigo(x) for x in c.cartas]} for c in evaluacion.combinaciones],
            "descarte": codigo(descarte) if descarte else None,
            "quedan": [codigo(c) for c in resto], "puntos_quedan": sum(tabla.puntos(c) for c in resto),
            "bono": cierre.bonificaciones.get(cierre.jugador_cierra, 0),
            "filas": [{"jugador": j, "ronda": cierre.penalizaciones.get(j, 0) - cierre.bonificaciones.get(j, 0),
                       "total": partida.marcador.saldos[j], "fuera": j in nuevos} for j in partida.jugadores],
            "terminada": cierre.partida_terminada, "ganador": cierre.ganador,
        }

    # ---------- Consulta ----------
    def vista(self, codigo_sala: str, jugador: str) -> dict[str, Any]:
        """Lo que ve un jugador: la sala, y si hay partida, su mano y lo público de la mesa."""
        sala = self._salas.obtener(codigo_sala)
        partida = self._partidas.obtener(sala.codigo)
        if partida and jugador not in partida.jugadores:
            partida = None  # entró a la sala después de que esa partida empezó
        manos = partida.mesa.manos if partida else {}
        saldos = partida.marcador.saldos if partida else {}
        fuera = partida.marcador.eliminados if partida else set()
        vista = {
            "sala": sala.codigo, "variante": sala.variante, "estado": sala.estado, "config": sala.config,
            "anfitrion": sala.anfitrion, "capacidad": sala.capacidad, "yo": jugador,
            "jugadores": [{"nombre": j, "cartas": len(manos.get(j, ())), "puntos": saldos.get(j, 0),
                           "fuera": j in fuera} for j in sala.jugadores],
            "partida": None,
        }
        if partida:
            vista["partida"] = self._vista_partida(sala, partida, jugador)
        return vista

    @staticmethod
    def _sobrante(mano: list[Carta], evaluacion: EvaluacionCierre,
                  puntos: Callable[[Carta], int]) -> tuple[Carta | None, list[Carta]]:
        """Lo que quedó fuera de las combinaciones: la carta más alta se descarta y el resto queda suelto."""
        resto = list(mano)
        for carta in (c for combo in evaluacion.combinaciones for c in combo.cartas):
            resto.remove(carta)
        descarte = max(resto, key=puntos) if resto else None
        if descarte:
            resto.remove(descarte)
        return descarte, resto

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
            "resumen": partida.resumen, "ganador": partida.ganador,
        }

    def _analizar(self, sala: Sala, mano: list[Carta]) -> dict[str, Any]:
        """Combinaciones ya formadas y puntos sueltos, con la tabla de puntos de la variante."""
        tabla = self._variantes.resolver(sala.variante).tabla_puntos(sala.config)
        combos, sueltas = cartas_sueltas(mano, tabla.puntos)
        # Con la carta del turno en la mano, al cerrar sale una: se cuenta sin la suelta más alta.
        descarte = max(sueltas, key=tabla.puntos) if sueltas and len(mano) > CARTAS_POR_MANO else None
        return {
            "combos": [{"tipo": c.tipo.value, "cartas": [codigo(x) for x in c.cartas]} for c in combos],
            "puntos_sueltos": sum(tabla.puntos(c) for c in sueltas) - (tabla.puntos(descarte) if descarte else 0),
            "sin_contar": codigo(descarte) if descarte else None,
        }

    def _partida(self, codigo_sala: str) -> Partida:
        partida = self._partidas.obtener(self._salas.obtener(codigo_sala).codigo)
        if partida is None:
            raise ErrorSala("La partida todavía no empieza.")
        return partida

    @staticmethod
    def _repartir(sala: Sala, jugadores: list[str]) -> Mesa:
        return Mesa.repartir(jugadores, sala.config.get("comodines_habilitados", True), secrets.randbelow(2**31))

    def _anotar(self, partida: Partida, jugador: str, accion: str, carta: str | None) -> None:
        partida.bitacora.append({"jugador": jugador, "accion": accion, "carta": carta})

