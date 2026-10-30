"""PostgresRepositoryAdapter: implementa IRepositorioPartidas con una transacción por cierre (sección 2.4).

El núcleo identifica con textos legibles (código de sala, nombre del jugador, `{sala}-{serie}-R{n}`)
y el esquema usa UUID: el adaptador los deriva con uuid5, así el mismo texto da siempre el mismo
UUID y no hace falta una tabla de equivalencias. Un texto que ya es un UUID se usa tal cual (así
crean sus filas las pruebas de la sección 2.4). En el MVP no hay cuentas: cada nombre es un jugador
distinto en cada sala, con alias `nombre#SALA` para respetar el UNIQUE de jugador.alias.
"""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

from juegocartas.nucleo.soporte.historial import CierreRonda, Jugada, RondaYaLiquidada

ESPACIO = uuid.UUID("6f1c2a44-3b8e-4f8a-9d0c-5a7e21b3c901")
SQL = Path(os.environ.get("JUEGO_SQL", Path(__file__).resolve().parents[3] / "docs" / "modelos" / "sql"))
registro = logging.getLogger(__name__)

BLOQUEAR_RONDA = "SELECT estado, partida_id FROM ronda WHERE ronda_id = %s FOR UPDATE"
REGISTRAR_JUGADA = ("INSERT INTO turno_jugada (mano_id, numero_turno, accion, resultado, comando_id) "
                    "SELECT mano_id, %s, 'SOLICITAR_CIERRE', 'ACEPTADA', %s FROM mano_jugador "
                    "WHERE ronda_id = %s AND jugador_id = %s")
CERRAR_RONDA = ("UPDATE ronda SET estado = 'LIQUIDADA', cerrada_por = %s, tipo_cierre = %s, "
                "cerrada_en = now() WHERE ronda_id = %s")
INSERTAR_PUNTAJE_RONDA = ("INSERT INTO puntaje_ronda (ronda_id, jugador_id, penalizacion, bonificacion) "
                          "VALUES (%s, %s, %s, %s)")
ACUMULAR = ("UPDATE puntaje_acumulado SET total = total + %s, version = version + 1, actualizado_en = now() "
            "WHERE partida_id = %s AND jugador_id = %s")
ELIMINAR = ("UPDATE participacion SET estado_jugador = 'ELIMINADO' "
            "WHERE partida_id = %s AND jugador_id = %s")
FINALIZAR = ("UPDATE partida SET estado = 'FINALIZADA', ganador_id = %s, finalizada_en = now() "
             "WHERE partida_id = %s")

INSERTAR_JUGADOR = "INSERT INTO jugador (jugador_id, alias) VALUES (%s, %s) ON CONFLICT DO NOTHING"
INSERTAR_SALA = ("INSERT INTO sala (sala_id, codigo_invitacion, anfitrion_id, capacidad) VALUES (%s, %s, %s, %s) "
                 "ON CONFLICT DO NOTHING")
# Una partida que quedó a medias (todos se fueron) no puede impedir la siguiente en la misma sala.
DEJAR_A_MEDIAS = ("UPDATE partida SET estado = 'FINALIZADA', finalizada_en = now() "
                  "WHERE sala_id = %s AND estado = 'EN_CURSO'")
INSERTAR_PARTIDA = ("INSERT INTO partida (partida_id, sala_id, variante_codigo, estado, iniciada_en) "
                    "VALUES (%s, %s, %s, 'EN_CURSO', now())")
INSERTAR_PARAMETRO = "INSERT INTO parametro_partida (partida_id, clave, valor) VALUES (%s, %s, %s)"
INSERTAR_PARTICIPACION = "INSERT INTO participacion (partida_id, jugador_id, asiento) VALUES (%s, %s, %s)"
INSERTAR_MARCADOR = "INSERT INTO puntaje_acumulado (partida_id, jugador_id) VALUES (%s, %s)"
INSERTAR_RONDA = "INSERT INTO ronda (ronda_id, partida_id, numero, semilla) VALUES (%s, %s, %s, %s)"
INSERTAR_MANO = "INSERT INTO mano_jugador (ronda_id, jugador_id) VALUES (%s, %s)"
ANOTAR = ("INSERT INTO turno_jugada (mano_id, numero_turno, accion, carta_codigo, mazo_numero, resultado, "
          "motivo_rechazo, comando_id) SELECT mano_id, %s, %s, %s, %s, %s, %s, %s FROM mano_jugador "
          "WHERE ronda_id = %s AND jugador_id = %s")
BITACORA = """
SELECT tj.ocurrida_en, dense_rank() OVER (ORDER BY p.iniciada_en) AS partida, r.numero AS ronda,
       tj.numero_turno AS turno, left(j.alias, length(j.alias) - 7) AS jugador, tj.accion,
       tj.carta_codigo AS carta, tj.resultado, tj.motivo_rechazo AS motivo
FROM turno_jugada tj
JOIN mano_jugador m ON m.mano_id = tj.mano_id
JOIN jugador j ON j.jugador_id = m.jugador_id
JOIN ronda r ON r.ronda_id = m.ronda_id
JOIN partida p ON p.partida_id = r.partida_id
JOIN sala s ON s.sala_id = p.sala_id
WHERE s.codigo_invitacion = %s AND r.estado = 'LIQUIDADA'
ORDER BY tj.jugada_id
"""


def _id(texto: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(texto))
    except ValueError:
        return uuid.uuid5(ESPACIO, texto)


def _jugador(sala: str, nombre: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(nombre))
    except ValueError:
        return uuid.uuid5(ESPACIO, f"{sala}/{nombre}")


def _carta(texto: str | None) -> str | None:
    return "JK1" if texto == "JK" else texto  # el catálogo distingue los dos comodines; el MVP no


class PostgresRepositoryAdapter:
    def __init__(self, conexion, url: str | None = None) -> None:  # conexión psycopg 3 en autocommit
        self._cx = conexion
        self._url = url

    @classmethod
    def desde_url(cls, url: str) -> "PostgresRepositoryAdapter":
        """Conecta y, si la base está vacía, crea el esquema del E2 con su catálogo de cartas."""
        adaptador = cls(psycopg.connect(url, autocommit=True), url)
        if adaptador._cx.execute("SELECT to_regclass('public.carta')").fetchone()[0] is None:
            for archivo in ("esquema.sql", "datos_iniciales.sql"):
                adaptador._cx.execute((SQL / archivo).read_text(encoding="utf-8"))
            registro.info("Esquema creado en la base de datos")
        return adaptador

    def liquidar_ronda(self, c: CierreRonda) -> None:
        """Todo o nada: si algo falla (o la ronda ya fue liquidada) no queda ninguna escritura parcial."""
        quien, ronda = _jugador(c.partida_id, c.jugador_cierra), _id(c.ronda_id)
        cx = self._conexion()
        with cx.transaction(), cx.cursor() as cur:
            cur.execute(BLOQUEAR_RONDA, (ronda,))
            fila = cur.fetchone()
            if fila is None:
                raise LookupError(f"La ronda {c.ronda_id} no está registrada")
            if fila[0] != "EN_JUEGO":
                raise RondaYaLiquidada(c.ronda_id)
            partida = fila[1]
            cur.execute(REGISTRAR_JUGADA, (c.numero_turno, _id(c.comando_id), ronda, quien))
            cur.execute(CERRAR_RONDA, (quien, c.tipo_cierre, ronda))
            for nombre, penalizacion in c.penalizaciones.items():
                jugador, bono = _jugador(c.partida_id, nombre), c.bonificaciones.get(nombre, 0)
                cur.execute(INSERTAR_PUNTAJE_RONDA, (ronda, jugador, penalizacion, bono))
                cur.execute(ACUMULAR, (penalizacion - bono, partida, jugador))
            for nombre in c.eliminados:
                cur.execute(ELIMINAR, (partida, _jugador(c.partida_id, nombre)))
            if c.partida_terminada:
                cur.execute(FINALIZAR, (_jugador(c.partida_id, c.ganador) if c.ganador else None, partida))

    def historial(self, partida_id: str) -> list[dict]:
        with self._conexion().cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM v_historial_puntajes WHERE partida_id = %s ORDER BY numero", (partida_id,))
            return cur.fetchall()

    def abrir_partida(self, sala: str, serie: str, variante: str, config: Mapping[str, Any],
                      jugadores: Sequence[str], capacidad: int) -> None:
        partida, sala_id = _id(f"{sala}-{serie}"), _id(sala)
        cx = self._conexion()
        with cx.transaction(), cx.cursor() as cur:
            for nombre in jugadores:
                cur.execute(INSERTAR_JUGADOR, (_jugador(sala, nombre), f"{nombre}#{sala}"))
            cur.execute(INSERTAR_SALA, (sala_id, sala, _jugador(sala, jugadores[0]), capacidad))
            cur.execute(DEJAR_A_MEDIAS, (sala_id,))
            cur.execute(INSERTAR_PARTIDA, (partida, sala_id, variante))
            for clave, valor in config.items():
                cur.execute(INSERTAR_PARAMETRO, (partida, clave, str(valor)[:60]))
            for asiento, nombre in enumerate(jugadores, start=1):
                cur.execute(INSERTAR_PARTICIPACION, (partida, _jugador(sala, nombre), asiento))
                cur.execute(INSERTAR_MARCADOR, (partida, _jugador(sala, nombre)))

    def abrir_ronda(self, sala: str, serie: str, ronda_id: str, numero: int, semilla: int,
                    jugadores: Sequence[str]) -> None:
        cx = self._conexion()
        with cx.transaction(), cx.cursor() as cur:
            cur.execute(INSERTAR_RONDA, (_id(ronda_id), _id(f"{sala}-{serie}"), numero, semilla))
            for nombre in jugadores:
                cur.execute(INSERTAR_MANO, (_id(ronda_id), _jugador(sala, nombre)))

    def anotar_jugada(self, j: Jugada) -> None:
        carta, motivo = _carta(j.carta), j.motivo_rechazo and j.motivo_rechazo[:200]
        self._conexion().execute(ANOTAR, (
            j.numero_turno, j.accion, carta, 1 if carta else None, "RECHAZADA" if motivo else "ACEPTADA",
            motivo, uuid.uuid4(), _id(j.ronda_id), _jugador(j.partida_id, j.jugador)))

    def bitacora(self, sala: str) -> list[dict]:
        with self._conexion().cursor(row_factory=dict_row) as cur:
            cur.execute(BITACORA, (sala,))
            return cur.fetchall()

    def _conexion(self):
        """Si la base cortó la conexión (p. ej. tras un reinicio del servicio), se abre otra."""
        if self._url and (self._cx.closed or self._cx.broken):
            registro.warning("Conexión con la base perdida: reconectando")
            self._cx = psycopg.connect(self._url, autocommit=True)
        return self._cx
