# Sistema Digital de Juego de Cartas: Entregable 3 (MVP)

Fundamentos de Arquitectura de Software, 2026-2, Universidad Nacional de Colombia, sede Medellín.
Equipo «Los Fabulosos Cadillacs»: Catalina Arango Sierra, Elizabeth Alzate Zapata y Nicolas Meza Ortega.

Juego de cartas en el navegador y en tiempo real (WebSocket) con dos modalidades: **Clásica 4-3-3** (1 cuarta, 2 ternas y 1 descarte) y **Apuntado a 101** (3 ternas o escaleras y menos de 5 puntos sueltos, con penalizaciones acumuladas hasta 101).

Arquitectura **microkernel**: un núcleo (sala, turnos, evaluación, puntuación, registro y soporte) más plug-ins de reglas descubiertos por *entry points* (ADR-03). Los cierres y la bitácora de jugadas se guardan en PostgreSQL con el esquema en 3FN del Entregable 2.

## Jugar

- **En línea:** *(enlace de Render: pendiente de publicar)*. El plan gratuito se duerme tras 15 minutos sin uso; la primera visita tarda unos 30 segundos en despertarlo.
- **En local con Docker** (levanta PostgreSQL 16 y el juego):

  ```bash
  docker compose up --build
  ```

  Abre http://localhost:8000, escribe tu nombre y crea una sala. Los demás entran con el código de 6 letras desde su celular o su computador (en la misma red, con la IP del equipo en lugar de `localhost`).

- **En local sin Docker** (partidas y bitácora en memoria):

  ```bash
  python -m venv .venv
  .venv/Scripts/activate        # en Linux/macOS: source .venv/bin/activate
  pip install -e ".[dev]"
  uvicorn juegocartas.arranque:app --host 0.0.0.0 --port 8000
  ```

  Con la variable `DATABASE_URL=postgresql://usuario:clave@host:5432/base` usa PostgreSQL; si la base está vacía, el servidor crea el esquema al arrancar.

## Bitácora de auditoría

Cada robo, descarte e intento de cierre (aceptado o rechazado, con el motivo) queda en la tabla `turno_jugada` con su hora. Se descarga como CSV en `/bitacora/<CÓDIGO>.csv` (por ejemplo, http://localhost:8000/bitacora/ABC123.csv). Solo trae las rondas ya cerradas, para no revelar las manos de una ronda en juego. Es la evidencia de la sección 3.2 del informe.

## Pruebas, fitness functions y métricas

```bash
pytest tests -v                                   # 96 pruebas: R1–R9, historias H1–H6 y PostgreSQL (pgserver)
python herramientas/metricas.py --exigir          # Ca, Ce, I, A, D, CC y ley de Deméter
radon cc src -s -a                                # complejidad ciclomática detallada
```

En CI corren con `.github/workflows/fitness-functions.yml` en cada *push* y *pull request*: el job `arquitectura` ejecuta las pruebas y publica el reporte de métricas en el resumen del pipeline (falla si un plug-in se aleja de la secuencia principal o un evaluador supera CC 10), y el job `despliegue` levanta `docker compose` y comprueba que el juego responde conectado a PostgreSQL. El último reporte está en `docs/metricas/reporte_metricas.md`.

## Desplegar en Render

1. En https://dashboard.render.com, **New > Blueprint** y conecta este repositorio.
2. Render lee `render.yaml`: crea el servicio web desde el `Dockerfile` y una base PostgreSQL 16, y les pasa `DATABASE_URL`.
3. Al terminar, el enlace queda como `https://juego-cartas.onrender.com` (o el nombre que asigne Render).

## Estructura

```
docs/
  adrs/                ADR-01 a ADR-05 (.md)
  metricas/            reporte_metricas.md (lo genera herramientas/metricas.py)
  modelos/
    plantuml/          componentes, relacional físico, clases de persistencia, secuencia de cierre
    er/                E-R en notación de Barker (lo genera herramientas/generar_er_barker.py)
    sql/               esquema.sql (DDL) y datos_iniciales.sql
  risk_storming/       kit de la sesión y respuestas de la fase 1
src/juegocartas/
  nucleo/              core system (contrato, sala, partida, turno, evaluacion, puntuacion, registro, soporte)
  plugins/             clasica, apuntado (solo importan nucleo.contrato)
  presentacion/        GameGateway (WebSocket), servidor web y pantalla (static/index.html)
  persistencia/        PostgresRepositoryAdapter y RepositorioEnMemoria
  arranque.py          composition root
tests/
  architecture/        fitness functions R1–R9 (PyTestArch, ast, radon, pytest)
  mvp/                 historias H1–H6 (salas, turnos, cierres, reconexión, bitácora)
  integracion/         esquema, transacciones y el MVP completo sobre PostgreSQL 16 (pgserver)
Dockerfile, docker-compose.yml, render.yaml
```

## Limitaciones conocidas

- Las partidas en curso viven en la memoria del servidor (un solo proceso). Si el servidor se reinicia, las partidas abiertas se pierden; lo ya cerrado sigue en PostgreSQL. Por eso el servicio corre con un solo *worker*.
- Al refrescar el navegador o perder la red, el jugador vuelve a su mano y a su turno con el token guardado en su navegador (H5), mientras el servidor no se reinicie.
- La base gratuita de Render vence a los 30 días.

## Agregar una variante sin tocar el núcleo (ADR-03)

1. Crea un paquete que implemente `juegocartas.nucleo.contrato.VariantePlugin`.
2. Declara el *entry point* en su `pyproject.toml`:

   ```toml
   [project.entry-points."juegocartas.variantes"]
   CONTINENTAL = "juegocartas_continental:Plugin"
   ```

3. Instálalo con `pip install` y reinicia el servidor. `PluginRegistry` lo descubre al arrancar.

## Regenerar diagramas

```bash
# Requiere herramientas/plantuml.jar (https://github.com/plantuml/plantuml/releases, v1.2024.7) y Java
java -jar herramientas/plantuml.jar -tsvg -o ../../informe/build docs/modelos/plantuml/*.puml
python herramientas/generar_er_barker.py
java -jar herramientas/plantuml.jar -tsvg -o ../../informe/build docs/modelos/er/er_barker.puml
```
