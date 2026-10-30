"""Pruebas del esquema (sección 2) y de la estrategia transaccional (sección 2.4) sobre PostgreSQL real.

Usa pgserver (PostgreSQL 16 embebido) para no depender de una instalación local.
"""
import threading
import uuid
from pathlib import Path

import pytest

pgserver = pytest.importorskip("pgserver")
psycopg = pytest.importorskip("psycopg")

from juegocartas.nucleo.soporte.historial import CierreRonda, RondaYaLiquidada  # noqa: E402
from juegocartas.persistencia.postgres import PostgresRepositoryAdapter  # noqa: E402

SQL = Path(__file__).resolve().parents[2] / "docs" / "modelos" / "sql"


@pytest.fixture(scope="module")
def uri(tmp_path_factory):
    servidor = pgserver.get_server(tmp_path_factory.mktemp("pg"), cleanup_mode="stop")
    with psycopg.connect(servidor.get_uri(), autocommit=True) as cx:
        cx.execute((SQL / "esquema.sql").read_text(encoding="utf-8"))
        cx.execute((SQL / "datos_iniciales.sql").read_text(encoding="utf-8"))
    yield servidor.get_uri()
    servidor.cleanup()


def conectar(uri):
    return psycopg.connect(uri, autocommit=True)


def nueva_partida(cx, variante, n_jugadores=3):
    """Crea jugadores, sala, partida en curso, participaciones y marcadores en cero."""
    jugadores = [cx.execute("INSERT INTO jugador (alias) VALUES (%s) RETURNING jugador_id",
                            (f"j{uuid.uuid4().hex[:8]}",)).fetchone()[0] for _ in range(n_jugadores)]
    sala = cx.execute("INSERT INTO sala (codigo_invitacion, anfitrion_id, capacidad) VALUES (%s, %s, 6) "
                      "RETURNING sala_id", (uuid.uuid4().hex[:6], jugadores[0])).fetchone()[0]
    partida = cx.execute("INSERT INTO partida (sala_id, variante_codigo, estado, iniciada_en) "
                         "VALUES (%s, %s, 'EN_CURSO', now()) RETURNING partida_id", (sala, variante)).fetchone()[0]
    cx.execute("INSERT INTO parametro_partida VALUES (%s, 'umbral_eliminacion', '101')", (partida,))
    for asiento, j in enumerate(jugadores, start=1):
        cx.execute("INSERT INTO participacion (partida_id, jugador_id, asiento) VALUES (%s, %s, %s)",
                   (partida, j, asiento))
        cx.execute("INSERT INTO puntaje_acumulado (partida_id, jugador_id) VALUES (%s, %s)", (partida, j))
    return partida, jugadores


def nueva_ronda(cx, partida, jugadores, numero):
    ronda = cx.execute("INSERT INTO ronda (partida_id, numero, semilla) VALUES (%s, %s, 42) RETURNING ronda_id",
                       (partida, numero)).fetchone()[0]
    for j in jugadores:
        cx.execute("INSERT INTO mano_jugador (ronda_id, jugador_id) VALUES (%s, %s)", (ronda, j))
    return ronda


def cierre(partida, ronda, quien, penalizaciones, **extra):
    datos = dict(partida_id=partida, ronda_id=ronda, jugador_cierra=quien, tipo_cierre="TOCAR",
                 penalizaciones=penalizaciones, bonificaciones={}, eliminados=(), partida_terminada=False,
                 ganador=None, comando_id=str(uuid.uuid4()), numero_turno=7)
    datos.update(extra)
    return CierreRonda(**datos)


def test_catalogo_de_54_cartas(uri):
    with conectar(uri) as cx:
        assert cx.execute("SELECT count(*) FROM carta").fetchone()[0] == 54


def test_partida_multironda_apuntado_acumula_hasta_101(uri):
    with conectar(uri) as cx:
        partida, (a, b, c) = nueva_partida(cx, "APUNTADO_101")
        repo = PostgresRepositoryAdapter(cx)
        rondas = [({a: 0, b: 40, c: 30}, ()), ({a: 4, b: 35, c: 50}, ()), ({a: 0, b: 30, c: 25}, (b, c))]
        for numero, (penal, eliminados) in enumerate(rondas, start=1):
            ronda = nueva_ronda(cx, partida, [a, b, c], numero)
            fin = numero == 3
            repo.liquidar_ronda(cierre(partida, ronda, a, penal, eliminados=eliminados,
                                       partida_terminada=fin, ganador=a if fin else None))
        totales = dict(cx.execute("SELECT jugador_id, total FROM puntaje_acumulado WHERE partida_id = %s",
                                  (partida,)).fetchall())
        assert totales == {a: 4, b: 105, c: 105}
        assert cx.execute("SELECT estado, ganador_id FROM partida WHERE partida_id = %s",
                          (partida,)).fetchone() == ("FINALIZADA", a)
        assert len(repo.historial(partida)) == 9
        assert cx.execute("SELECT count(*) FROM v_inconsistencias_marcador").fetchone()[0] == 0


def test_partida_clasica_es_atomica_de_una_ronda(uri):
    with conectar(uri) as cx:
        partida, (a, b, c) = nueva_partida(cx, "CLASICA_433")
        ronda = nueva_ronda(cx, partida, [a, b, c], 1)
        PostgresRepositoryAdapter(cx).liquidar_ronda(
            cierre(partida, ronda, b, {a: 0, b: 0, c: 0}, tipo_cierre="CLASICO_433", partida_terminada=True, ganador=b))
        assert cx.execute("SELECT count(*) FROM ronda WHERE partida_id = %s", (partida,)).fetchone()[0] == 1
        # la Clásica también deja una fila en 0 por jugador: la PK de puntaje_ronda la protege de la doble liquidación
        assert cx.execute("SELECT count(*), sum(penalizacion) FROM puntaje_ronda WHERE ronda_id = %s",
                          (ronda,)).fetchone() == (3, 0)
        assert cx.execute("SELECT ganador_id FROM partida WHERE partida_id = %s", (partida,)).fetchone()[0] == b


def test_dos_cierres_simultaneos_solo_uno_gana(uri):
    with conectar(uri) as cx:
        partida, (a, b, c) = nueva_partida(cx, "APUNTADO_101")
        ronda = nueva_ronda(cx, partida, [a, b, c], 1)
    barrera, resultados = threading.Barrier(2), []

    def cerrar(quien):
        with conectar(uri) as propia:
            barrera.wait()
            try:
                PostgresRepositoryAdapter(propia).liquidar_ronda(cierre(partida, ronda, quien, {a: 3, b: 3, c: 3}))
                resultados.append(("ok", quien))
            except RondaYaLiquidada:
                resultados.append(("rechazado", quien))

    hilos = [threading.Thread(target=cerrar, args=(j,)) for j in (a, b)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert sorted(r[0] for r in resultados) == ["ok", "rechazado"]
    with conectar(uri) as cx:
        assert cx.execute("SELECT count(*) FROM puntaje_ronda WHERE ronda_id = %s", (ronda,)).fetchone()[0] == 3
        assert cx.execute("SELECT count(*) FROM v_inconsistencias_marcador").fetchone()[0] == 0


def test_fallo_a_mitad_del_cierre_no_deja_escrituras_parciales(uri):
    with conectar(uri) as cx:
        partida, (a, b, c) = nueva_partida(cx, "APUNTADO_101")
        ronda = nueva_ronda(cx, partida, [a, b, c], 1)
        malo = cierre(partida, ronda, a, {a: 0, b: 12, c: -1})  # -1 viola CHECK (penalizacion >= 0) al final
        with pytest.raises(psycopg.errors.CheckViolation):
            PostgresRepositoryAdapter(cx).liquidar_ronda(malo)
        assert cx.execute("SELECT estado FROM ronda WHERE ronda_id = %s", (ronda,)).fetchone()[0] == "EN_JUEGO"
        assert cx.execute("SELECT count(*) FROM puntaje_ronda WHERE ronda_id = %s", (ronda,)).fetchone()[0] == 0
        assert cx.execute("SELECT sum(total) FROM puntaje_acumulado WHERE partida_id = %s",
                          (partida,)).fetchone()[0] == 0


def test_no_puede_haber_dos_rondas_abiertas(uri):
    with conectar(uri) as cx:
        partida, jugadores = nueva_partida(cx, "APUNTADO_101")
        nueva_ronda(cx, partida, jugadores, 1)
        with pytest.raises(psycopg.errors.UniqueViolation):
            nueva_ronda(cx, partida, jugadores, 2)



# ---------- H6: el MVP completo contra PostgreSQL ----------

def test_partida_del_mvp_queda_en_la_base_con_su_bitacora(uri):
    """GameService con el adaptador real: dos rondas de Apuntado y luego otra partida en la misma sala."""
    from juegocartas.arranque import armar_gateway
    from juegocartas.nucleo.contrato.codigos import desde_codigo

    juego = armar_gateway(PostgresRepositoryAdapter.desde_url(uri))._juego
    sala = juego.crear_sala("Nico", "APUNTADO_101").codigo
    juego.unirse(sala, "Caro")

    def cerrar(quien, mano):
        """Fija las dos manos: al otro le quedan 4 puntos, así nadie llega a 101 por azar."""
        juego.robar(sala, quien, "MAZO")
        manos = juego._partidas.obtener(sala).mesa.manos
        otro = next(j for j in manos if j != quien)
        manos[otro] = [desde_codigo(c) for c in "2H 2S 2D 3H 3S 3D 5H 5S 5D 4C".split()]
        manos[quien] = [desde_codigo(c) for c in mano.split()]
        juego.cerrar(sala, quien)

    juego.empezar(sala, "Nico")
    juego.robar(sala, "Nico", "MAZO")
    juego.descartar(sala, "Nico", juego.vista(sala, "Nico")["partida"]["mano"][0])
    cerrar("Caro", "7H 7S 7D 3C 4C 5C KS KH KD 2D QC")                    # ronda 1
    cerrar(juego.vista(sala, "Nico")["partida"]["en_turno"], "AH AS AD JH JS JD 9C 9H 9S 2D QC")  # ronda 2

    filas = juego.bitacora(sala)
    assert [(f["ronda"], f["turno"], f["jugador"], f["accion"]) for f in filas] == [
        (1, 1, "Nico", "ROBAR_MAZO"), (1, 1, "Nico", "DESCARTAR"),
        (1, 2, "Caro", "ROBAR_MAZO"), (1, 2, "Caro", "SOLICITAR_CIERRE"),
        (2, 1, "Caro", "ROBAR_MAZO"), (2, 1, "Caro", "SOLICITAR_CIERRE"),  # la ronda 2 la abre Caro
    ]
    with conectar(uri) as cx:
        assert cx.execute("SELECT count(*) FROM v_inconsistencias_marcador").fetchone()[0] == 0
        assert cx.execute("SELECT count(*) FROM ronda r JOIN partida p USING (partida_id) JOIN sala s USING (sala_id) "
                          "WHERE s.codigo_invitacion = %s AND r.estado = 'EN_JUEGO'", (sala,)).fetchone()[0] == 1

    # Clásica en otra sala: la partida termina y el anfitrión empieza otra en la misma sala
    sala = juego.crear_sala("Ana", "CLASICA_433").codigo
    juego.unirse(sala, "Beto")
    juego.empezar(sala, "Ana")
    juego.robar(sala, "Ana", "MAZO")
    juego._partidas.obtener(sala).mesa.manos["Ana"] = [desde_codigo(c) for c in "7H 7S 7D 7C 3C 4C 5C KS KH KD 2D".split()]
    juego.cerrar(sala, "Ana")
    juego.empezar(sala, "Ana")
    with conectar(uri) as cx:
        estados = cx.execute("SELECT p.estado, j.alias FROM partida p JOIN sala s USING (sala_id) "
                             "LEFT JOIN jugador j ON j.jugador_id = p.ganador_id "
                             "WHERE s.codigo_invitacion = %s ORDER BY p.iniciada_en", (sala,)).fetchall()
    assert estados == [("FINALIZADA", f"Ana#{sala}"), ("EN_CURSO", None)]
    assert [f["partida"] for f in juego.bitacora(sala)] == [1, 1]
