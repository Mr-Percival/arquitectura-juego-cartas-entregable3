# Software Release Checklist (Entregable 3)

Basada en el cap. 24 de Richards y Ford y en la lista de pre-lanzamiento que aportó Elizabeth (revisión y QA, regresión y rendimiento, documentación, plan de reversa, seguridad y aprobación). Se pasa antes de cada versión entregada.

| Bloque | Ítem | Cómo se verifica | Estado |
|---|---|---|---|
| Base de datos | El esquema 3FN se crea al arrancar si la base está vacía | Log «Esquema creado» (job `despliegue` del CI y Render) | ✔ |
| Configuración | `DATABASE_URL` y `PORT` por entorno; health check en `/salud` | `render.yaml`; `/salud` responde 200 | ✔ |
| Build | Jobs `arquitectura` y `despliegue` en verde en `main` | GitHub Actions | ✔ |
| Revisión y QA | Cada historia entra con sus pruebas; revisión cruzada | `tests/mvp/`, historial de commits | ✔ |
| Regresión y rendimiento | Suite completa en cada push; p95 del evaluador < 50 ms (R8) | `docs/evidencia_pytest.txt` | ✔ |
| Documentación y notas de versión | README con manual, limitaciones y enlace; ADR al día | `README.md`, `docs/adrs/` | ✔ |
| Plan de reversa | Rollback al despliegue anterior en Render; si PostgreSQL no responde, el juego arranca en memoria | `arranque.py`, `tests/mvp/test_arranque_sin_base.py` | ✔ |
| Seguridad | Sin secretos en el repo; la bitácora solo expone rondas cerradas; el informe con datos personales no se sube | `.gitignore`, H6 | ✔ |
| Aprobación | El equipo aprueba la versión tras la validación con usuarios | Sección 3 del informe | ✔ |

## Developer Code-Completion Checklist

- [x] Sin `print` en `src/` (todo por `logging`).
- [x] Sin excepciones absorbidas en silencio: cada `except` responde al jugador o escribe en el log.
- [x] Plug-ins solo importan `nucleo.contrato`; la presentación no importa la persistencia (R1, R2).
- [x] CC ≤ 10 en evaluadores y ≤ 15 en el resto (R5).
- [x] Mensajes al jugador en español y accionables.

## Unit & Functional Testing Checklist

- [x] Mano con ternas incompletas rechazada con el motivo (H3, H4).
- [x] Sobrante de exactamente 5 en Apuntado rechazado (`test_sobrante_de_exactamente_5_se_rechaza`).
- [x] Detección exacta a 101 y desempate R-11.
- [x] Dos cierres simultáneos: solo uno se liquida (R9).
- [x] Jugada fuera de turno, robar dos veces, descartar sin robar (H2).
