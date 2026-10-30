"""GameGateway: adaptador de entrada por WebSocket.

Traduce los mensajes del navegador a comandos de GameService y, cuando el bus avisa que algo
cambió en una sala, le manda a cada jugador conectado su propia vista (cada uno ve solo su mano).
Solo habla con el núcleo a través de sus interfaces de servicio; no importa persistencia (regla R1).
No depende del framework web: sirve cualquier conexión con `send_json` (FastAPI o un doble de prueba).
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from juegocartas.nucleo.partida.servicio import GameService
from juegocartas.nucleo.sala.salas import ErrorSala
from juegocartas.nucleo.soporte.eventos import EventoPartida, LocalEventBus
from juegocartas.nucleo.turno.mesa import JugadaInvalida
from juegocartas.nucleo.turno.orquestador import ComandoFueraDeTurno

EVENTOS = ("SalaActualizada", "PartidaIniciada", "CartaRobada", "CartaDescartada",
           "RondaLiquidada", "PartidaFinalizada")
RECHAZOS = (ErrorSala, ComandoFueraDeTurno, JugadaInvalida)


class Conexion(Protocol):
    async def send_json(self, datos: Any) -> None: ...


@dataclass(frozen=True)
class Sesion:
    token: str
    sala: str
    jugador: str


class GameGateway:
    def __init__(self, juego: GameService, eventos: LocalEventBus) -> None:
        self._juego = juego
        self._sesiones: dict[str, Sesion] = {}
        self._conexiones: dict[str, dict[str, Conexion]] = {}
        self._pendientes: set[str] = set()
        for tipo in EVENTOS:
            eventos.suscribir(tipo, self._al_evento)

    async def atender(self, conexion: Conexion, sesion: Sesion | None, mensaje: Mapping[str, Any]) -> Sesion | None:
        """Procesa un mensaje del navegador y devuelve la sesión de esa conexión (nueva si acaba de entrar)."""
        accion = mensaje.get("accion")
        try:
            if accion in ("crear", "unirse", "reconectar"):
                sesion = self._entrar(accion, mensaje)
                self._conexiones.setdefault(sesion.sala, {})[sesion.jugador] = conexion
                await conexion.send_json({"tipo": "sesion", "token": sesion.token,
                                          "sala": sesion.sala, "jugador": sesion.jugador})
                self._pendientes.add(sesion.sala)
            elif sesion is None:
                raise ErrorSala("Primero entra a una sala.")
            else:
                self._ejecutar(sesion, accion, mensaje)
        except RECHAZOS as exc:
            await self._enviar(conexion, {"tipo": "error", "accion": accion, "mensaje": str(exc)})
        await self._difundir()
        return sesion

    def desconectar(self, sesion: Sesion | None, conexion: Conexion) -> None:
        """El jugador sigue en la sala: puede volver con su token (H5)."""
        if sesion and self._conexiones.get(sesion.sala, {}).get(sesion.jugador) is conexion:
            del self._conexiones[sesion.sala][sesion.jugador]

    def _entrar(self, accion: str, mensaje: Mapping[str, Any]) -> Sesion:
        if accion == "reconectar":
            sesion = self._sesiones.get(str(mensaje.get("token", "")))
            if sesion is None:
                raise ErrorSala("Tu partida anterior ya no existe. Entra de nuevo con el código.")
            return sesion
        nombre = str(mensaje.get("nombre", ""))
        if accion == "crear":
            sala = self._juego.crear_sala(nombre, str(mensaje.get("variante", "")))
        else:
            sala = self._juego.unirse(str(mensaje.get("sala", "")), nombre)
        jugador = sala.jugadores[-1] if accion == "unirse" else sala.anfitrion
        sesion = Sesion(secrets.token_urlsafe(16), sala.codigo, jugador)
        self._sesiones[sesion.token] = sesion
        return sesion

    def _ejecutar(self, sesion: Sesion, accion: Any, mensaje: Mapping[str, Any]) -> None:
        if accion == "empezar":
            self._juego.empezar(sesion.sala, sesion.jugador)
        elif accion == "robar":
            self._juego.robar(sesion.sala, sesion.jugador, str(mensaje.get("origen", "")))
        elif accion == "descartar":
            self._juego.descartar(sesion.sala, sesion.jugador, str(mensaje.get("carta", "")))
        elif accion == "cerrar":
            self._juego.cerrar(sesion.sala, sesion.jugador)
        else:
            raise ErrorSala("Acción desconocida.")

    def _al_evento(self, evento: EventoPartida) -> None:
        self._pendientes.add(evento.partida_id)  # se envía al terminar el comando (ADR-05)

    async def _difundir(self) -> None:
        pendientes, self._pendientes = self._pendientes, set()
        for sala in pendientes:
            for jugador, conexion in list(self._conexiones.get(sala, {}).items()):
                await self._enviar(conexion, {"tipo": "estado", **self._juego.vista(sala, jugador)})

    @staticmethod
    async def _enviar(conexion: Conexion, datos: dict) -> None:
        try:
            await conexion.send_json(datos)
        except Exception:  # una conexión caída no tumba el turno de los demás
            pass
