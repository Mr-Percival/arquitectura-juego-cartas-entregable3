"""R9. Comportamiento del mediador (ADR-05 y sección 2.4, capa 1), con dobles de prueba.

- El evento RondaLiquidada se publica solo después de persistir; si la persistencia falla, no se publica.
- Dos solicitudes de cierre simultáneas en la misma partida: solo una llega a persistir.
"""
import threading

import pytest

from juegocartas.nucleo.contrato import EvaluacionCierre
from juegocartas.nucleo.turno.orquestador import ComandoFueraDeTurno, TurnOrchestrator


class EvaluadorValido:
    def evaluar_cierre(self, variante, config, mano):
        return EvaluacionCierre(True, "TOCAR")


class Liquidador:
    def liquidar(self, partida_id, quien, evaluacion):
        return {"partida": partida_id, "cierra": quien}


class Registro:
    def __init__(self, falla=False):
        self.falla, self.cierres, self.orden = falla, [], []

    def registrar_ronda(self, cierre):
        self.orden.append("persistir")
        if self.falla:
            raise RuntimeError("la base de datos rechazó la transacción")
        self.cierres.append(cierre)


class Bus:
    def __init__(self, orden):
        self.eventos, self.orden = [], orden

    def publicar(self, evento):
        if evento.tipo != "RondaLiquidada":  # robar y descartar también publican; aquí interesa el cierre
            return
        self.orden.append("publicar")
        self.eventos.append(evento)


def armar(falla=False):
    registro = Registro(falla)
    bus = Bus(registro.orden)
    orq = TurnOrchestrator(EvaluadorValido(), Liquidador(), registro, bus)
    orq.iniciar("p1", "APUNTADO_101", {}, primero="ana")
    orq.robar("p1", "ana")
    return orq, registro, bus


def test_publica_despues_de_persistir():
    orq, registro, bus = armar()
    orq.solicitar_cierre("p1", "ana", [])
    assert registro.orden == ["persistir", "publicar"]


def test_no_publica_si_la_persistencia_falla():
    orq, registro, bus = armar(falla=True)
    with pytest.raises(RuntimeError):
        orq.solicitar_cierre("p1", "ana", [])
    assert bus.eventos == []


def test_dos_cierres_simultaneos_solo_uno_persiste():
    orq, registro, bus = armar()
    barrera, resultados = threading.Barrier(2), []

    def cerrar():
        barrera.wait()
        try:
            orq.solicitar_cierre("p1", "ana", [])
            resultados.append("ok")
        except ComandoFueraDeTurno:
            resultados.append("rechazado")

    hilos = [threading.Thread(target=cerrar) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert sorted(resultados) == ["ok", "rechazado"]
    assert len(registro.cierres) == 1 and len(bus.eventos) == 1


def test_jugador_fuera_de_turno_es_rechazado():
    orq, _, _ = armar()
    with pytest.raises(ComandoFueraDeTurno):
        orq.solicitar_cierre("p1", "beto", [])
