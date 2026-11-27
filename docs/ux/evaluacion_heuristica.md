# Evaluación heurística y accesibilidad (WCAG 2.2)

Hecha antes de la validación con usuarios (sección 3.1 del informe); el estado final refleja los ajustes de la sección 3.4 (commit `cfd9d81`).

| Heurística / criterio | Pregunta | Hallazgo inicial | Estado final |
|---|---|---|---|
| Visibilidad del estado (Nielsen 1) | ¿El jugador sabe si le toca y qué hacer? | Sí; faltaba ver qué hace el rival | Rival: «Tomando carta…» / «Eligiendo descarte…»; pestaña «¡Te toca!» |
| Prevención de errores (Nielsen 5) | ¿Se evitan jugadas ilegales antes de enviarlas? | «Cerrar» activo aunque la mano no cierre | «Cerrar ronda ✓» o «Aún no puedes cerrar: …» |
| Reconocer antes que recordar (Nielsen 6) | ¿Se ven las combinaciones formadas? | Sí: marcas de color y contador de sueltas | Sin cambios |
| Ayuda y documentación (Nielsen 10) | ¿Un jugador nuevo encuentra las reglas? | No había reglas en pantalla | «¿Cómo se juega?» con las reglas que trae cada plug-in |
| WCAG 1.4.3 Contraste | ¿Texto ≥ 4,5:1? | Por medir | Medido: texto 8,58:1, secundario 5,45:1, rojo 5,66:1, negro 15,7:1 |
| WCAG 2.5.8 / 2.5.5 Tamaño del objetivo | ¿Objetivos ≥ 24 px (AA) / 44 px (AAA)? | Cartas solapadas con la mano llena | Mano en dos filas: 56 px por carta |
| WCAG 1.4.1 Uso del color | ¿La información depende solo del color? | Las pintas llevan símbolo | Sin cambios |
