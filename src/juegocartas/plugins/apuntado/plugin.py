"""ReglaApuntadoPlugin: 3 ternas + sobrantes < umbralTocar, con penalización acumulada hasta 101.

Solo importa el contrato del núcleo (regla R2: no depende de otros plug-ins).
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from juegocartas.nucleo.contrato import (VERSION_CONTRATO, Carta, DecisionFin, EvaluacionCierre,
                                         Marcador)
from juegocartas.nucleo.contrato.codigos import etiqueta
from juegocartas.nucleo.contrato.combinaciones import mejor_cobertura, particiones

# Tipos de cierre propios de la variante: los define el plug-in, no el núcleo ni el esquema SQL.
TOCAR, COMPLETO, PINTAS = "TOCAR", "COMPLETO", "PINTAS"


class TablaPuntosEstandar:
    """As, J, Q y K valen 10; del 2 al 10, su valor; el comodín, 0."""

    def puntos(self, carta: Carta) -> int:
        if carta.es_comodin:
            return 0
        return 10 if carta.rango == 1 or carta.rango > 10 else carta.rango


class CierreApuntado:
    def __init__(self, umbral_tocar: int, tabla: TablaPuntosEstandar) -> None:
        self._umbral = umbral_tocar
        self._tabla = tabla

    def evaluar(self, mano: Sequence[Carta]) -> EvaluacionCierre:
        completo = self._completo(mano)
        return completo if completo else self._tocar(mano)

    def _completo(self, mano: Sequence[Carta]) -> EvaluacionCierre | None:
        for combinaciones, sobrantes in particiones(mano, (3, 3, 4)):
            tipo = PINTAS if self._misma_pinta(combinaciones) else COMPLETO
            return EvaluacionCierre(True, tipo, tuple(combinaciones), tuple(sobrantes))
        return None

    def _tocar(self, mano: Sequence[Carta]) -> EvaluacionCierre:
        menor: tuple[int, list[Carta]] | None = None  # el sobrante más bajo, para explicar el rechazo
        for combinaciones, sobrantes in particiones(mano, (3, 3, 3)):
            restantes = sorted(sobrantes, key=self._tabla.puntos)[:-1]  # la más alta se descarta
            puntos = sum(self._tabla.puntos(c) for c in restantes)
            if puntos < self._umbral:
                return EvaluacionCierre(True, TOCAR, tuple(combinaciones), tuple(restantes))
            if menor is None or puntos < menor[0]:
                menor = (puntos, restantes)
        return EvaluacionCierre(False, motivo_rechazo=self._por_que_no(mano, menor))

    def _por_que_no(self, mano: Sequence[Carta], menor: tuple[int, list[Carta]] | None) -> str:
        """Mensaje de la historia H4: cuánto suma el sobrante o cuántas ternas faltan."""
        if menor is None:
            formadas = len(mejor_cobertura(mano, lambda c: 1)[0])
            return f"Tienes {formadas} de las 3 ternas o escaleras que se necesitan para cerrar."
        puntos, restantes = menor
        cartas = " y ".join(etiqueta(c) for c in restantes)
        if puntos == self._umbral:
            detalle = f"Con exactamente {self._umbral} no se puede: tienen que ser menos de {self._umbral}."
        else:
            detalle = f"Para cerrar tienen que ser menos de {self._umbral}, después de descartar tu carta más alta."
        return f"Te quedan {puntos} puntos sueltos ({cartas}). {detalle}"

    @staticmethod
    def _misma_pinta(combinaciones) -> bool:
        pintas = {c.pinta for combo in combinaciones for c in combo.cartas if not c.es_comodin}
        return len(pintas) == 1


class UmbralEliminacion:
    def __init__(self, umbral: int) -> None:
        self._umbral = umbral

    def evaluar(self, marcador: Marcador) -> DecisionFin:
        eliminados = tuple(j for j, s in marcador.saldos.items() if s >= self._umbral)
        vivos = [j for j in marcador.saldos if j not in eliminados]
        if len(vivos) == 1:
            return DecisionFin(True, eliminados, vivos[0])
        if not vivos and eliminados:
            return self._desempatar(marcador, eliminados)
        return DecisionFin(False, eliminados)

    @staticmethod
    def _desempatar(marcador: Marcador, eliminados: tuple[str, ...]) -> DecisionFin:
        """R-11 (sección 4.3): todos los que seguían vivos llegaron al umbral en la misma ronda.

        Gana el de menor saldo entre ellos; si empatan, el primero en el orden del marcador.
        """
        ultimos = [j for j in eliminados if j not in marcador.eliminados] or list(eliminados)
        ganador = min(ultimos, key=lambda j: marcador.saldos[j])
        return DecisionFin(True, tuple(j for j in eliminados if j != ganador), ganador)


class ReglaApuntadoPlugin:
    codigo = "APUNTADO_101"
    version_contrato = VERSION_CONTRATO

    def esquema_configuracion(self) -> Mapping[str, Any]:
        return {
            "umbral_tocar": {"tipo": int, "defecto": 5},
            "umbral_eliminacion": {"tipo": int, "defecto": 101},
            "bono_completo": {"tipo": int, "defecto": 10},
            "bono_pintas": {"tipo": int, "defecto": 25},
            "comodines_habilitados": {"tipo": bool, "defecto": True},
            "tiempo_limite_turno_s": {"tipo": int, "defecto": 60},
        }

    def regla_cierre(self, config: Mapping[str, Any]) -> CierreApuntado:
        return CierreApuntado(config.get("umbral_tocar", 5), TablaPuntosEstandar())

    def tabla_puntos(self, config: Mapping[str, Any]) -> TablaPuntosEstandar:
        return TablaPuntosEstandar()

    def politica_fin(self, config: Mapping[str, Any]) -> UmbralEliminacion:
        return UmbralEliminacion(config.get("umbral_eliminacion", 101))
