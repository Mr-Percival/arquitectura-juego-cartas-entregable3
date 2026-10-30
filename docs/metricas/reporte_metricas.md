# Métricas estructurales del MVP

| Componente | Ca | Ce | I | A | D | Zona | Deméter |
|---|---:|---:|---:|---:|---:|---|---:|
| arranque | 0 | 9 | 1.00 | 0.00 | 0.00 | cerca de la secuencia principal | 0 |
| nucleo.contrato | 8 | 0 | 0.00 | 0.36 | 0.64 | zona del dolor (estable y concreto) | 0 |
| nucleo.evaluacion | 1 | 1 | 0.50 | 0.50 | 0.00 | cerca de la secuencia principal | 1 |
| nucleo.partida | 2 | 5 | 0.71 | 0.50 | 0.21 | cerca de la secuencia principal | 5 |
| nucleo.puntuacion | 2 | 2 | 0.50 | 0.33 | 0.17 | cerca de la secuencia principal | 4 |
| nucleo.registro | 1 | 1 | 0.50 | 0.00 | 0.50 | zona del dolor (estable y concreto) | 0 |
| nucleo.sala | 3 | 1 | 0.25 | 0.29 | 0.46 | zona del dolor (estable y concreto) | 1 |
| nucleo.soporte | 6 | 0 | 0.00 | 0.14 | 0.86 | zona del dolor (estable y concreto) | 0 |
| nucleo.turno | 3 | 2 | 0.40 | 0.33 | 0.27 | cerca de la secuencia principal | 0 |
| persistencia | 1 | 1 | 0.50 | 0.00 | 0.50 | zona del dolor (estable y concreto) | 0 |
| plugins.apuntado | 0 | 1 | 1.00 | 0.00 | 0.00 | cerca de la secuencia principal | 0 |
| plugins.clasica | 0 | 1 | 1.00 | 0.00 | 0.00 | cerca de la secuencia principal | 0 |
| presentacion | 1 | 4 | 0.80 | 0.33 | 0.13 | cerca de la secuencia principal | 0 |

## Complejidad ciclomática (radon)

- Bloques medidos: 241; promedio 2.32; máximo 10.
- Evaluación de ternas, cuartas y cierres: 42 bloques, promedio 3.24, máximo 10 (umbral 10, deseable < 5).

| Archivo | Bloque | CC |
|---|---|---:|
| plugins/clasica/plugin.py | CierreClasico433._que_falta | 10 |
| nucleo/contrato/combinaciones.py | es_escalera | 9 |
| nucleo/puntuacion/liquidador.py | LiquidadorRonda.liquidar | 9 |
| nucleo/contrato/combinaciones.py | particiones | 8 |
| nucleo/partida/servicio.py | GameService.vista | 8 |
| nucleo/partida/servicio.py | GameService._analizar | 8 |
| plugins/apuntado/plugin.py | UmbralEliminacion.evaluar | 8 |
| plugins/clasica/plugin.py | CierreClasico433 | 8 |
| persistencia/postgres.py | PostgresRepositoryAdapter.liquidar_ronda | 7 |
| nucleo/contrato/combinaciones.py | mejor_cobertura | 7 |

## Ley de Deméter: llamadas encadenadas a objetos ajenos

- `nucleo/evaluacion/evaluador.py:23`: `self._registro.resolver(variante).regla_cierre`
- `nucleo/partida/servicio.py:162`: `self._variantes.resolver(partida.variante).tabla_puntos`
- `nucleo/partida/servicio.py:178`: `self._salas.obtener(codigo_sala).codigo`
- `nucleo/partida/servicio.py:228`: `self._variantes.resolver(sala.variante).tabla_puntos`
- `nucleo/partida/servicio.py:239`: `self._salas.obtener(codigo_sala).codigo`
- `nucleo/partida/servicio.py:124`: `self._salas.obtener(codigo_sala).codigo`
- `nucleo/puntuacion/liquidador.py:25`: `self._registro.resolver(variante).tabla_puntos`
- `nucleo/puntuacion/liquidador.py:38`: `self._registro.resolver(variante).politica_fin(config).evaluar`
- `nucleo/puntuacion/liquidador.py:78`: `self._registro.resolver(ronda.variante).tabla_puntos`
- `nucleo/puntuacion/liquidador.py:38`: `self._registro.resolver(variante).politica_fin`
- `nucleo/sala/configuracion.py:23`: `self._registro.resolver(variante).esquema_configuracion`

## Dependencias entre componentes (Ce)

- **arranque** → nucleo.evaluacion, nucleo.partida, nucleo.puntuacion, nucleo.registro, nucleo.sala, nucleo.soporte, nucleo.turno, persistencia, presentacion
- **nucleo.contrato** → (ninguna)
- **nucleo.evaluacion** → nucleo.contrato
- **nucleo.partida** → nucleo.contrato, nucleo.puntuacion, nucleo.sala, nucleo.soporte, nucleo.turno
- **nucleo.puntuacion** → nucleo.contrato, nucleo.soporte
- **nucleo.registro** → nucleo.contrato
- **nucleo.sala** → nucleo.contrato
- **nucleo.soporte** → (ninguna)
- **nucleo.turno** → nucleo.contrato, nucleo.soporte
- **persistencia** → nucleo.soporte
- **plugins.apuntado** → nucleo.contrato
- **plugins.clasica** → nucleo.contrato
- **presentacion** → nucleo.partida, nucleo.sala, nucleo.soporte, nucleo.turno
