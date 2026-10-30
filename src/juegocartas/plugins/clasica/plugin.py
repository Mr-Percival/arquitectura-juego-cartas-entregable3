"""ReglaClasicaPlugin: 1 cuarta + 2 ternas + 1 carta de descarte, en una sola ronda.

Solo importa el contrato del núcleo (regla R2: no depende de otros plug-ins).
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from juegocartas.nucleo.contrato import (VERSION_CONTRATO, Carta, DecisionFin, EvaluacionCierre,
                                         Marcador)
from juegocartas.nucleo.contrato.combinaciones import mejor_cobertura, particiones

# Tipos de cierre propios de la variante: los define el plug-in, no el núcleo ni el esquema SQL.
CLASICO_433 = "CLASICO_433"

TAMANOS = (4, 3, 3)


class CierreClasico433:
    def evaluar(self, mano: Sequence[Carta]) -> EvaluacionCierre:
        if len(mano) != sum(TAMANOS) + 1:
            return EvaluacionCierre(False, motivo_rechazo=f"Se requieren {sum(TAMANOS) + 1} cartas")
        for combinaciones, sobrantes in particiones(mano, TAMANOS):
            return EvaluacionCierre(True, CLASICO_433, tuple(combinaciones), tuple(sobrantes))
        return EvaluacionCierre(False, motivo_rechazo=self._que_falta(mano))

    @staticmethod
    def _que_falta(mano: Sequence[Carta]) -> str:
        """Dice qué combinaciones faltan, contando las que ya están formadas (historia H3)."""
        combinaciones, _ = mejor_cobertura(mano, lambda c: 1)
        cuartas = sum(len(c.cartas) == 4 for c in combinaciones)
        ternas = len(combinaciones) - cuartas
        faltan_ternas = max(0, 2 - ternas - max(0, cuartas - 1))
        falta = (["1 cuarta"] if cuartas == 0 else []) + ([_contar(faltan_ternas, "terna")] if faltan_ternas else [])
        verbo = "Te falta" if len(falta) == 1 and falta[0].startswith("1 ") else "Te faltan"
        tienes = " y ".join(([_contar(cuartas, "cuarta")] if cuartas else []) + ([_contar(ternas, "terna")] if ternas else []))
        tienes = f"Tienes {tienes}" if tienes else "No tienes ninguna combinación"
        return (f"{verbo} {' y '.join(falta) or 'acomodar las combinaciones'}. {tienes}; "
                f"para cerrar se necesita 1 cuarta + 2 ternas + 1 carta para descartar.")


def _contar(n: int, palabra: str) -> str:
    return f"{n} {palabra}{'s' if n > 1 else ''}"


class SinPenalizacion:
    """La Clásica no acumula penalizaciones entre rondas."""

    def puntos(self, carta: Carta) -> int:
        return 0


class FinEnUnaRonda:
    def evaluar(self, marcador: Marcador) -> DecisionFin:
        return DecisionFin(terminada=True)  # el orquestador declara ganador a quien cerró


class ReglaClasicaPlugin:
    codigo = "CLASICA_433"
    version_contrato = VERSION_CONTRATO

    def esquema_configuracion(self) -> Mapping[str, Any]:
        return {
            "comodines_habilitados": {"tipo": bool, "defecto": True},
            "tiempo_limite_turno_s": {"tipo": int, "defecto": 60},
        }

    def regla_cierre(self, config: Mapping[str, Any]) -> CierreClasico433:
        return CierreClasico433()

    def tabla_puntos(self, config: Mapping[str, Any]) -> SinPenalizacion:
        return SinPenalizacion()

    def politica_fin(self, config: Mapping[str, Any]) -> FinEnUnaRonda:
        return FinEnUnaRonda()
