"""RoomSetupComponent (historia H1): crear una sala con código, unirse respetando el cupo y empezar.

Un candado por sala hace atómica la unión: dos jugadores que entran a la vez por el último
puesto no pueden pasarse del cupo (riesgo del Risk Storming del E2).
"""
from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol

# Sin 0/O ni 1/I para que el código se pueda dictar sin confusiones.
ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
LARGO_CODIGO = 6  # codigo_invitacion CHAR(6) del esquema
CAPACIDAD = 4
MINIMO_PARA_EMPEZAR = 2
LARGO_NOMBRE = 12


class ErrorSala(Exception):
    """Mensaje que se le muestra tal cual al jugador."""


class IValidarConfiguracion(Protocol):
    def validar(self, variante: str, config: Mapping[str, Any]) -> dict[str, Any]: ...


@dataclass
class Sala:
    codigo: str
    variante: str
    config: dict[str, Any]
    anfitrion: str
    capacidad: int = CAPACIDAD
    jugadores: list[str] = field(default_factory=list)
    estado: str = "ABIERTA"  # ABIERTA, EN_PARTIDA (mismos estados que la tabla sala)
    candado: threading.Lock = field(default_factory=threading.Lock, repr=False)


def generar_codigo() -> str:
    return "".join(secrets.choice(ALFABETO) for _ in range(LARGO_CODIGO))


def limpiar_nombre(nombre: str) -> str:
    nombre = " ".join((nombre or "").split())
    if not nombre:
        raise ErrorSala("Escribe tu nombre para entrar.")
    if len(nombre) > LARGO_NOMBRE:
        raise ErrorSala(f"El nombre puede tener hasta {LARGO_NOMBRE} letras.")
    return nombre


class SalaService:
    def __init__(self, configuracion: IValidarConfiguracion, codigos: Callable[[], str] = generar_codigo) -> None:
        self._configuracion = configuracion
        self._codigos = codigos
        self._salas: dict[str, Sala] = {}
        self._candado = threading.Lock()

    def crear(self, anfitrion: str, variante: str, config: Mapping[str, Any] | None = None) -> Sala:
        anfitrion = limpiar_nombre(anfitrion)
        final = self._configuracion.validar(variante, config or {})
        with self._candado:
            codigo = self._codigos()
            while codigo in self._salas:
                codigo = self._codigos()
            sala = Sala(codigo, variante, final, anfitrion, jugadores=[anfitrion])
            self._salas[codigo] = sala
        return sala

    def obtener(self, codigo: str) -> Sala:
        sala = self._salas.get((codigo or "").strip().upper())
        if sala is None:
            raise ErrorSala("No hay ninguna sala con ese código. Revisa que esté bien escrito.")
        return sala

    def unirse(self, codigo: str, nombre: str) -> Sala:
        nombre = limpiar_nombre(nombre)
        sala = self.obtener(codigo)
        with sala.candado:
            if sala.estado != "ABIERTA":
                raise ErrorSala("Esa partida ya empezó.")
            if len(sala.jugadores) >= sala.capacidad:
                raise ErrorSala(f"La sala está llena ({sala.capacidad} jugadores).")
            if nombre.casefold() in (j.casefold() for j in sala.jugadores):
                raise ErrorSala(f"Ya hay alguien llamado {nombre} en la sala. Usa otro nombre.")
            sala.jugadores.append(nombre)
        return sala

    def empezar(self, codigo: str, quien: str) -> Sala:
        sala = self.obtener(codigo)
        with sala.candado:
            if quien != sala.anfitrion:
                raise ErrorSala(f"La partida la empieza {sala.anfitrion}, que creó la sala.")
            if sala.estado != "ABIERTA":
                raise ErrorSala("La partida ya empezó.")
            if len(sala.jugadores) < MINIMO_PARA_EMPEZAR:
                raise ErrorSala("Hace falta al menos otra persona. Compártele el código.")
            sala.estado = "EN_PARTIDA"
        return sala
